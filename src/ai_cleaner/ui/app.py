"""Native Qt desktop workflow for review, quarantine, restore, and purge."""

from __future__ import annotations

import sys
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ai_cleaner.domain.actions import RecoveryActionPlan
from ai_cleaner.domain.approval import ApprovalBroker
from ai_cleaner.domain.models import ClassifiedFile, ScanResult, ScanStatus
from ai_cleaner.domain.proposals import Proposal
from ai_cleaner.platform.windows_fs import WindowsFilesystem
from ai_cleaner.services.classify import classify_files, git_evidence
from ai_cleaner.services.operations import OperationResult, QuarantineService
from ai_cleaner.services.proposals import ProposalService
from ai_cleaner.services.purge import PurgeService
from ai_cleaner.services.recovery import RecoveryService
from ai_cleaner.services.scan import Scanner
from ai_cleaner.services.tasks import TaskService
from ai_cleaner.storage.config import StatePaths
from ai_cleaner.storage.database import Database

PREVIEW_LIMIT = 64 * 1024


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KiB"
    return f"{size / (1024 * 1024):.1f} MiB"


class ScanWorker(QObject):
    """Run inventory work away from the GUI thread."""

    progress = Signal(int)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        scanner: Scanner,
        root: Path,
        excluded_roots: tuple[Path, ...],
        cancel: threading.Event,
    ) -> None:
        super().__init__()
        self.scanner = scanner
        self.root = root
        self.excluded_roots = excluded_roots
        self.cancel = cancel

    @Slot()
    def run(self) -> None:
        try:
            result = self.scanner.scan(
                self.root,
                cancel=self.cancel,
                excluded_roots=self.excluded_roots,
                progress=self.progress.emit,
            )
        except Exception as error:  # Qt worker boundary: surface every failure to the user.
            self.failed.emit(f"{type(error).__name__}: {error}")
        else:
            self.finished.emit(result)


class TaskWorker(QObject):
    """Capture task start/end snapshots without blocking the event loop."""

    progress = Signal(int)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        service: TaskService,
        *,
        root: Path | None,
        label: str | None,
        task_id: str | None,
        excluded_roots: tuple[Path, ...],
        cancel: threading.Event,
    ) -> None:
        super().__init__()
        self.service = service
        self.root = root
        self.label = label
        self.task_id = task_id
        self.excluded_roots = excluded_roots
        self.cancel = cancel

    @Slot()
    def run(self) -> None:
        try:
            if self.task_id is None:
                assert self.root is not None and self.label is not None
                result: object = self.service.start(
                    self.root,
                    self.label,
                    excluded_roots=self.excluded_roots,
                    cancel=self.cancel,
                    progress=self.progress.emit,
                )
            else:
                result = self.service.finish(
                    self.task_id,
                    excluded_roots=self.excluded_roots,
                    cancel=self.cancel,
                    progress=self.progress.emit,
                )
        except Exception as error:  # Qt worker boundary: surface every failure to the user.
            self.failed.emit(f"{type(error).__name__}: {error}")
        else:
            self.finished.emit(result)


class ConfirmationDialog(QDialog):
    """Concrete, inspectable review dialog for one exact immutable action plan."""

    def __init__(
        self,
        *,
        title: str,
        warning: str,
        rows: list[tuple[str, int, str, str]],
        confirm_text: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("confirmationDialog")
        self.setWindowTitle(title)
        self.setModal(True)
        layout = QVBoxLayout(self)
        heading = QLabel(warning)
        heading.setWordWrap(True)
        heading.setObjectName("confirmationWarning")
        layout.addWidget(heading)
        table = QTableWidget(len(rows), 4)
        table.setObjectName("confirmationTable")
        table.setHorizontalHeaderLabels(["Path", "Size", "Reason", "Recovery behavior"])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(str(value)))
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table)
        total = sum(row[1] for row in rows)
        layout.addWidget(QLabel(f"{len(rows)} item(s), {_format_size(total)} logical data"))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        confirm = buttons.addButton(confirm_text, QDialogButtonBox.ButtonRole.AcceptRole)
        confirm.setObjectName("confirmActionButton")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(900, 430)


class MainWindow(QMainWindow):
    """Top-level application window; filesystem mutation remains in services."""

    def __init__(
        self,
        *,
        root: Path | None = None,
        state_override: Path | None = None,
        filesystem: WindowsFilesystem | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("mainWindow")
        self.setWindowTitle("AI-cleaner")
        self.resize(1180, 760)

        self.state = StatePaths.discover(state_override)
        self.state.ensure()
        self.database = Database(self.state.database)
        self.database.migrate()
        self.filesystem = filesystem or WindowsFilesystem()
        self.scanner = Scanner(self.filesystem)
        self.tasks = TaskService(self.database, self.filesystem, self.scanner)
        self.approvals = ApprovalBroker()
        self.proposals = ProposalService(self.database, self.filesystem)
        lock_path = self.state.locks / "operations.lock"
        self.quarantine = QuarantineService(
            self.database, self.filesystem, self.approvals, lock_path
        )
        self.recovery = RecoveryService(self.database, self.filesystem, self.approvals, lock_path)
        self.purge = PurgeService(self.database, self.filesystem, self.approvals, lock_path)

        self.project_root: Path | None = None
        self.recovery_root: Path | None = None
        self.project_id: str | None = None
        self.scan_result: ScanResult | None = None
        self.classified: list[ClassifiedFile] = []
        self._scan_thread: QThread | None = None
        self._scan_worker: ScanWorker | None = None
        self._scan_cancel: threading.Event | None = None
        self._task_thread: QThread | None = None
        self._task_worker: TaskWorker | None = None
        self._task_cancel: threading.Event | None = None

        self._build_ui()
        if root is not None:
            self.set_project_root(root)
        self._reconcile_on_startup()

    def _build_ui(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)

        project = QGroupBox("Selected project")
        project_layout = QGridLayout(project)
        self.root_edit = QLineEdit()
        self.root_edit.setObjectName("rootPath")
        self.root_edit.setReadOnly(True)
        self.root_edit.setPlaceholderText(
            "Choose one project folder; AI-cleaner never scans elsewhere"
        )
        self.choose_button = QPushButton("Choose folder…")
        self.choose_button.setObjectName("chooseProjectButton")
        self.choose_button.clicked.connect(self.choose_project)
        self.scan_button = QPushButton("Scan")
        self.scan_button.setObjectName("scanButton")
        self.scan_button.setEnabled(False)
        self.scan_button.clicked.connect(self.start_scan)
        self.cancel_button = QPushButton("Cancel scan")
        self.cancel_button.setObjectName("cancelScanButton")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_scan)
        self.start_task_button = QPushButton("Start tracked task…")
        self.start_task_button.setObjectName("startTaskButton")
        self.start_task_button.setEnabled(False)
        self.start_task_button.clicked.connect(self.start_tracked_task)
        self.finish_task_button = QPushButton("Finish tracked task")
        self.finish_task_button.setObjectName("finishTaskButton")
        self.finish_task_button.setEnabled(False)
        self.finish_task_button.clicked.connect(self.finish_tracked_task)
        project_layout.addWidget(self.root_edit, 0, 0)
        project_layout.addWidget(self.choose_button, 0, 1)
        project_layout.addWidget(self.scan_button, 0, 2)
        project_layout.addWidget(self.cancel_button, 0, 3)
        project_layout.addWidget(self.start_task_button, 1, 1)
        project_layout.addWidget(self.finish_task_button, 1, 2)
        self.progress = QProgressBar()
        self.progress.setObjectName("scanProgress")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        project_layout.addWidget(self.progress, 2, 0, 1, 4)
        outer.addWidget(project)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("workflowTabs")
        self.tabs.addTab(self._build_review_tab(), "Review")
        self.tabs.addTab(self._build_history_tab(), "Recovery & history")
        outer.addWidget(self.tabs, 1)

        self.status_label = QLabel("Choose a project folder to begin.")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        self.statusBar().addWidget(self.status_label, 1)
        self.setCentralWidget(central)

    def _build_review_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("searchReview")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._filter_review)
        toolbar.addWidget(self.search_edit, 1)
        self.pin_button = QPushButton("Pin highlighted")
        self.pin_button.setObjectName("pinButton")
        self.pin_button.setEnabled(False)
        self.pin_button.clicked.connect(self.pin_highlighted)
        toolbar.addWidget(self.pin_button)
        self.preview_button = QPushButton("Preview highlighted")
        self.preview_button.setObjectName("previewButton")
        self.preview_button.setEnabled(False)
        self.preview_button.clicked.connect(self.preview_highlighted)
        toolbar.addWidget(self.preview_button)
        layout.addLayout(toolbar)

        self.review_table = QTableWidget(0, 8)
        self.review_table.setObjectName("reviewTable")
        self.review_table.setHorizontalHeaderLabels(
            ["Select", "Path", "Size", "Category", "Reason", "Evidence", "Modified", "Action"]
        )
        self.review_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.review_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.review_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.review_table.setSortingEnabled(True)
        self.review_table.itemSelectionChanged.connect(self._update_review_actions)
        header = self.review_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.group_tree = QTreeWidget()
        self.group_tree.setObjectName("reviewGroups")
        self.group_tree.setHeaderLabel("Expandable groups")
        self.group_tree.setMinimumWidth(190)
        self.group_tree.itemSelectionChanged.connect(
            lambda: self._filter_review(self.search_edit.text())
        )
        split = QSplitter()
        split.setObjectName("reviewSplit")
        split.addWidget(self.group_tree)
        split.addWidget(self.review_table)
        split.setStretchFactor(1, 1)
        layout.addWidget(split, 3)

        self.empty_label = QLabel("No scan results yet. Scanning is read-only and selects nothing.")
        self.empty_label.setObjectName("emptyState")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_label)

        preview_group = QGroupBox("Bounded plain-text preview")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_text = QPlainTextEdit()
        self.preview_text.setObjectName("previewText")
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumBlockCount(4000)
        self.preview_text.setPlaceholderText(
            "Choose a row and request a preview. Scripts, HTML, and macros are never executed."
        )
        preview_layout.addWidget(self.preview_text)
        layout.addWidget(preview_group, 1)

        self.move_button = QPushButton("Review selected files for quarantine…")
        self.move_button.setObjectName("reviewQuarantineButton")
        self.move_button.setEnabled(False)
        self.move_button.clicked.connect(self.review_quarantine)
        layout.addWidget(self.move_button)
        return page

    def _build_history_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel(
            "Quarantine is recoverable and does not itself reclaim disk space. "
            "Permanent purge is a separate irreversible action."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.history_table = QTableWidget(0, 5)
        self.history_table.setObjectName("historyTable")
        self.history_table.setHorizontalHeaderLabels(
            ["Select", "Original path", "Size", "State", "Recovery payload"]
        )
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.history_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.history_table, 2)
        layout.addWidget(QLabel("Operation history"))
        self.operation_table = QTableWidget(0, 6)
        self.operation_table.setObjectName("operationHistoryTable")
        self.operation_table.setHorizontalHeaderLabels(
            ["Action", "Status", "Items", "Succeeded", "Failed", "Started"]
        )
        self.operation_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.operation_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.operation_table.itemSelectionChanged.connect(self._show_history_details)
        self.operation_table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.operation_table, 1)
        actions = QHBoxLayout()
        self.refresh_history_button = QPushButton("Refresh")
        self.refresh_history_button.setObjectName("refreshHistoryButton")
        self.refresh_history_button.clicked.connect(self.refresh_history)
        self.restore_button = QPushButton("Review restore…")
        self.restore_button.setObjectName("restoreButton")
        self.restore_button.clicked.connect(self.review_restore)
        self.purge_button = QPushButton("Review permanent purge…")
        self.purge_button.setObjectName("purgeButton")
        self.purge_button.clicked.connect(self.review_purge)
        actions.addWidget(self.refresh_history_button)
        actions.addStretch()
        actions.addWidget(self.restore_button)
        actions.addWidget(self.purge_button)
        layout.addLayout(actions)
        self.results_text = QPlainTextEdit()
        self.results_text.setObjectName("operationResults")
        self.results_text.setReadOnly(True)
        self.results_text.setPlaceholderText("Per-file outcomes and errors appear here.")
        layout.addWidget(self.results_text, 1)
        return page

    def _reconcile_on_startup(self) -> None:
        try:
            recovery = self.recovery.reconcile_interrupted()
            purged = self.purge.reconcile_interrupted()
        except (OSError, RuntimeError, ValueError) as error:
            self._set_status(
                f"Interrupted-operation review could not be completed: {error}", error=True
            )
            return
        if recovery or purged:
            self.results_text.setPlainText(
                f"Startup reconciliation reviewed {len(recovery)} move(s) and "
                f"{purged} completed purge(s). No destructive work was resumed."
            )
            self._set_status(
                "Interrupted operations were reconciled for review; no cleanup was resumed."
            )

    @Slot()
    def choose_project(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Choose project folder")
        if selected:
            self.set_project_root(Path(selected))

    def set_project_root(self, root: Path) -> bool:
        if self._scan_thread is not None or self._task_thread is not None:
            self._set_status(
                "Wait for the current background scan before changing projects.", error=True
            )
            return False
        try:
            root = root.absolute()
            identity = self.filesystem.validate_project_root(root, app_state=self.state.root)
            recovery = self.state.recovery
            try:
                self.filesystem.validate_roots(root, recovery, app_state=self.state.root)
            except (OSError, RuntimeError, ValueError) as recovery_error:
                selected = QFileDialog.getExistingDirectory(
                    self,
                    "Choose same-volume recovery folder outside the project",
                    str(root.parent),
                )
                if not selected:
                    raise RuntimeError(
                        "A separate existing same-volume recovery folder is required"
                    ) from recovery_error
                recovery = Path(selected).absolute()
                self.filesystem.validate_roots(root, recovery, app_state=self.state.root)
            self.project_id = self.database.ensure_project(
                root=root,
                resolved_root=identity.final_path,
                volume_serial=identity.volume_serial,
                recovery_root=recovery,
                created_at=_now(),
            )
        except (OSError, RuntimeError, ValueError) as error:
            self._set_status(f"Project unavailable: {error}", error=True)
            return False
        self.project_root = root
        self.recovery_root = recovery
        self.root_edit.setText(str(root))
        self.scan_button.setEnabled(True)
        self.scan_result = None
        self.classified = []
        self._populate_review()
        self.refresh_history()
        self._refresh_task_buttons()
        self._set_status("Project ready. Scan to build a read-only inventory.")
        return True

    def _refresh_task_buttons(self) -> None:
        unresolved = (
            self.database.unresolved_task(self.project_id) if self.project_id else None
        )
        idle = self._scan_thread is None and self._task_thread is None
        self.start_task_button.setEnabled(
            idle and self.project_root is not None and unresolved is None
        )
        self.finish_task_button.setEnabled(idle and unresolved is not None)

    @Slot()
    def start_tracked_task(self) -> None:
        if self.project_root is None or self._task_thread is not None:
            return
        label, accepted = QInputDialog.getText(self, "Start tracked task", "Task label:")
        if not accepted or not label.strip():
            self._set_status("Tracked task start cancelled; no baseline was recorded.")
            return
        self._start_task_worker(label=label.strip(), task_id=None)

    @Slot()
    def finish_tracked_task(self) -> None:
        if self.project_id is None or self._task_thread is not None:
            return
        unresolved = self.database.unresolved_task(self.project_id)
        if unresolved is None:
            self._set_status("No active or interrupted tracked task is available.", error=True)
            return
        self._start_task_worker(label=None, task_id=str(unresolved["id"]))

    def _start_task_worker(self, *, label: str | None, task_id: str | None) -> None:
        assert self.project_root is not None
        self._task_cancel = threading.Event()
        thread = QThread(self)
        worker = TaskWorker(
            self.tasks,
            root=self.project_root,
            label=label,
            task_id=task_id,
            excluded_roots=(self.state.root, self.state.recovery),
            cancel=self._task_cancel,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._scan_progress)
        worker.finished.connect(self._task_finished)
        worker.failed.connect(self._task_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._task_thread_finished)
        self._task_thread = thread
        self._task_worker = worker
        self.scan_button.setEnabled(False)
        self.choose_button.setEnabled(False)
        self.start_task_button.setEnabled(False)
        self.finish_task_button.setEnabled(False)
        self.progress.setRange(0, 0)
        action = "Finishing" if task_id else "Starting"
        self._set_status(f"{action} tracked task in the background…")
        thread.start()

    @Slot(object)
    def _task_finished(self, result: object) -> None:
        if isinstance(result, str):
            self._set_status(f"Tracked task started: {result}")
        else:
            self._set_status("Tracked task finished; its observed changes are ready for review.")

    @Slot(str)
    def _task_failed(self, message: str) -> None:
        self._set_status(f"Tracked task update failed: {message}", error=True)

    @Slot()
    def _task_thread_finished(self) -> None:
        self._task_thread = None
        self._task_worker = None
        self._task_cancel = None
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.scan_button.setEnabled(self.project_root is not None)
        self.choose_button.setEnabled(True)
        self._refresh_task_buttons()

    @Slot()
    def start_scan(self) -> None:
        if (
            self.project_root is None
            or self._scan_thread is not None
            or self._task_thread is not None
        ):
            return
        self._scan_cancel = threading.Event()
        thread = QThread(self)
        worker = ScanWorker(
            self.scanner,
            self.project_root,
            (self.state.root, self.state.recovery),
            self._scan_cancel,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._scan_progress)
        worker.finished.connect(self._scan_finished)
        worker.failed.connect(self._scan_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._scan_thread_finished)
        self._scan_thread = thread
        self._scan_worker = worker
        self.scan_button.setEnabled(False)
        self.choose_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.move_button.setEnabled(False)
        self.start_task_button.setEnabled(False)
        self.finish_task_button.setEnabled(False)
        self.progress.setRange(0, 0)
        self._set_status("Scanning in the background… 0 entries visited")
        thread.start()

    @Slot()
    def cancel_scan(self) -> None:
        if self._scan_cancel is not None:
            self._scan_cancel.set()
            self.cancel_button.setEnabled(False)
            self._set_status("Cancellation requested; finishing the current filesystem read…")

    @Slot(int)
    def _scan_progress(self, count: int) -> None:
        self._set_status(f"Scanning in the background… {count:,} entries visited")

    @Slot(object)
    def _scan_finished(self, value: object) -> None:
        assert isinstance(value, ScanResult)
        result = value
        self.scan_result = result
        if self.project_id is None or self.project_root is None:
            self._set_status("Scan result ignored because the project changed.", error=True)
            return
        self.database.save_scan(self.project_id, result, _now())
        self.classified = classify_files(
            result.observations,
            git=git_evidence(self.project_root),
            pins=self.database.protections(self.project_id),
        )
        self._populate_review()
        issue_text = f"; {len(result.issues)} issue(s)" if result.issues else ""
        self._set_status(
            f"Scan {result.status.value}: {len(result.observations)} files{issue_text}. "
            "Cleanup selections remain unchecked."
        )

    @Slot(str)
    def _scan_failed(self, message: str) -> None:
        self.scan_result = None
        self.classified = []
        self._populate_review()
        self._set_status(f"Scan failed: {message}. Check access and retry.", error=True)

    @Slot()
    def _scan_thread_finished(self) -> None:
        self._scan_thread = None
        self._scan_worker = None
        self._scan_cancel = None
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.scan_button.setEnabled(self.project_root is not None)
        self.choose_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self._update_move_button()
        self._refresh_task_buttons()

    def _populate_review(self) -> None:
        self.group_tree.clear()
        groups: dict[str, QTreeWidgetItem] = {}
        directories: dict[tuple[str, str], QTreeWidgetItem] = {}
        for classified in self.classified:
            category = classified.category.value
            group = groups.get(category)
            if group is None:
                group = QTreeWidgetItem([category])
                group.setData(0, Qt.ItemDataRole.UserRole, (category, ""))
                self.group_tree.addTopLevelItem(group)
                groups[category] = group
            parent = str(Path(classified.observation.relative_path).parent)
            label = "(project root)" if parent == "." else parent
            key = (category, parent)
            if key not in directories:
                child = QTreeWidgetItem([label])
                child.setData(0, Qt.ItemDataRole.UserRole, key)
                group.addChild(child)
                directories[key] = child
        self.group_tree.expandAll()
        self.review_table.setSortingEnabled(False)
        self.review_table.setRowCount(len(self.classified))
        for row, item in enumerate(self.classified):
            checkbox = QCheckBox()
            checkbox.setObjectName(f"candidateCheck{row}")
            checkbox.setChecked(False)
            checkbox.setEnabled(item.selectable)
            checkbox.setAccessibleName(f"Select {item.observation.relative_path} for quarantine")
            checkbox.stateChanged.connect(self._update_move_button)
            holder = QWidget()
            holder_layout = QHBoxLayout(holder)
            holder_layout.setContentsMargins(0, 0, 0, 0)
            holder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            holder_layout.addWidget(checkbox)
            self.review_table.setCellWidget(row, 0, holder)
            values = (
                item.observation.relative_path,
                _format_size(item.observation.size),
                item.category.value,
                item.explanation,
                item.ownership_evidence,
                datetime.fromtimestamp(
                    item.observation.modified_ns / 1_000_000_000, UTC
                ).astimezone().isoformat(timespec="seconds"),
                "Quarantine (recoverable)" if item.selectable else "Keep / unavailable",
            )
            for column, value in enumerate(values, start=1):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, row)
                self.review_table.setItem(row, column, cell)
        self.review_table.setSortingEnabled(True)
        self.empty_label.setVisible(not self.classified)
        self.pin_button.setEnabled(False)
        self.preview_button.setEnabled(False)
        self._update_move_button()

    @Slot(str)
    def _filter_review(self, text: str) -> None:
        needle = text.casefold().strip()
        current_group = self.group_tree.currentItem()
        group_data = (
            current_group.data(0, Qt.ItemDataRole.UserRole)
            if current_group is not None
            else None
        )
        for row in range(self.review_table.rowCount()):
            values: list[str] = []
            for column in range(1, self.review_table.columnCount()):
                item = self.review_table.item(row, column)
                if item is not None:
                    values.append(item.text())
            haystack = " ".join(values).casefold()
            source_index = self._source_index(row)
            group_matches = True
            if group_data and source_index is not None:
                category, directory = group_data
                classified = self.classified[source_index]
                actual_directory = str(Path(classified.observation.relative_path).parent)
                group_matches = classified.category.value == category and (
                    not directory or actual_directory == directory
                )
            self.review_table.setRowHidden(
                row, not group_matches or bool(needle and needle not in haystack)
            )

    @Slot()
    def _update_review_actions(self) -> None:
        selected = bool(self.review_table.selectionModel().selectedRows())
        self.pin_button.setEnabled(selected and self.project_id is not None)
        self.preview_button.setEnabled(selected and self.project_root is not None)

    @Slot()
    def _update_move_button(self) -> None:
        complete = self.scan_result is not None and self.scan_result.status is ScanStatus.COMPLETE
        self.move_button.setEnabled(complete and bool(self._checked_classified()))

    def _source_index(self, visual_row: int) -> int | None:
        item = self.review_table.item(visual_row, 1)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return int(value) if value is not None else None

    def _checked_classified(self) -> list[ClassifiedFile]:
        result: list[ClassifiedFile] = []
        for visual_row in range(self.review_table.rowCount()):
            holder = self.review_table.cellWidget(visual_row, 0)
            checkbox = holder.findChild(QCheckBox) if holder else None
            source_index = self._source_index(visual_row)
            if checkbox and checkbox.isChecked() and source_index is not None:
                result.append(self.classified[source_index])
        return result

    def _highlighted_indices(self) -> list[int]:
        indices: list[int] = []
        for model_index in self.review_table.selectionModel().selectedRows():
            source = self._source_index(model_index.row())
            if source is not None and source not in indices:
                indices.append(source)
        return indices

    @Slot()
    def pin_highlighted(self) -> None:
        if self.project_id is None:
            return
        indices = self._highlighted_indices()
        if not indices:
            return
        for index in indices:
            relative = self.classified[index].observation.relative_path
            self.database.add_protection(
                protection_id=str(uuid.uuid4()),
                project_id=self.project_id,
                relative_path=relative,
                reason="Pinned in desktop review",
                origin="user",
                created_at=_now(),
            )
        if self.scan_result is not None and self.project_root is not None:
            self.classified = classify_files(
                self.scan_result.observations,
                git=git_evidence(self.project_root),
                pins=self.database.protections(self.project_id),
            )
            self._populate_review()
        self._set_status(f"Pinned {len(indices)} item(s); pinned files cannot be selected.")

    @Slot()
    def preview_highlighted(self) -> None:
        if self.project_root is None:
            return
        indices = self._highlighted_indices()
        if len(indices) != 1:
            self.preview_text.setPlainText("Highlight exactly one file to preview.")
            return
        relative = self.classified[indices[0]].observation.relative_path
        path = self.project_root / relative
        try:
            expected = self.filesystem.validate_candidate(path, self.project_root)
            with self.filesystem.open_exclusive_file(path) as handle:
                if self.filesystem.identity_from_handle(handle) != expected:
                    raise OSError("the selected file changed before preview")
                payload = self.filesystem.read_handle_prefix(handle, PREVIEW_LIMIT + 1)
            if b"\x00" in payload:
                raise ValueError("binary content is not previewed")
            truncated = len(payload) > PREVIEW_LIMIT
            text = payload[:PREVIEW_LIMIT].decode("utf-8", errors="strict")
            if truncated:
                text += "\n\n[Preview truncated at 64 KiB]"
            self.preview_text.setPlainText(text)
        except (OSError, UnicodeError, ValueError) as error:
            self.preview_text.setPlainText(f"Preview unavailable: {error}")

    @Slot()
    def review_quarantine(self) -> None:
        selected = self._checked_classified()
        if (
            not selected
            or self.project_id is None
            or self.project_root is None
            or self.recovery_root is None
        ):
            return
        try:
            proposal = self.proposals.prepare(
                project_id=self.project_id,
                root=self.project_root,
                recovery_root=self.recovery_root,
                selected=selected,
            )
        except (OSError, RuntimeError, ValueError) as error:
            self._set_status(f"Proposal could not be prepared: {error}", error=True)
            return
        rows = [
            (
                item.relative_path,
                item.size,
                item.explanation,
                f"Move to private recovery payload: {item.recovery_path}",
            )
            for item in proposal.items
        ]
        dialog = ConfirmationDialog(
            title="Confirm recoverable quarantine",
            warning=(
                "Review every exact operation below. Files move to private recovery storage; "
                "this does not reclaim disk space. Cancel leaves all user files unchanged."
            ),
            rows=rows,
            confirm_text="Move reviewed files",
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._set_status("Quarantine cancelled; no approved operation was executed.")
            return
        # Approval is minted only in this concrete accepted confirmation handler.
        capability = self.approvals._grant_from_ui(
            proposal_digest=proposal.items_digest,
            reviewed_digest=proposal.items_digest,
            action="quarantine",
        )
        self._execute_quarantine(proposal, capability)

    def _execute_quarantine(self, proposal: Proposal, capability: object) -> None:
        try:
            result = self.quarantine.execute(proposal, capability)
        except (OSError, RuntimeError, ValueError) as error:
            self._set_status(f"Quarantine failed before completion: {error}", error=True)
            return
        self._show_operation_result(result, "Quarantine")
        self.refresh_history()
        self.start_scan()

    def refresh_history(self) -> None:
        rows = self.database.recovery_items(self.project_id) if self.project_id else []
        self.history_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            checkbox = QCheckBox()
            checkbox.setObjectName(f"recoveryCheck{row_index}")
            checkbox.setEnabled(str(row["state"]) == "quarantined")
            checkbox.setAccessibleName(f"Select recovery item {row['original_path']}")
            holder = QWidget()
            holder_layout = QHBoxLayout(holder)
            holder_layout.setContentsMargins(0, 0, 0, 0)
            holder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            holder_layout.addWidget(checkbox)
            self.history_table.setCellWidget(row_index, 0, holder)
            recovery_values = (
                str(row["original_path"]),
                _format_size(int(row["size"])),
                str(row["state"]),
                str(row["payload_path"]),
            )
            for column, value in enumerate(recovery_values, start=1):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, str(row["id"]))
                self.history_table.setItem(row_index, column, item)
        has_quarantined = any(str(row["state"]) == "quarantined" for row in rows)
        self.restore_button.setEnabled(has_quarantined)
        self.purge_button.setEnabled(has_quarantined)
        operations = self.database.history(self.project_id) if self.project_id else []
        self.operation_table.setRowCount(len(operations))
        for row_index, operation in enumerate(operations):
            operation_values = (
                operation["action"],
                operation["status"],
                operation["item_count"],
                operation["success_count"],
                operation["failure_count"],
                operation["started_at"],
            )
            for column, operation_value in enumerate(operation_values):
                self.operation_table.setItem(
                    row_index, column, QTableWidgetItem(str(operation_value))
                )
            first = self.operation_table.item(row_index, 0)
            if first is not None:
                first.setData(Qt.ItemDataRole.UserRole, operation["items"])

    @Slot()
    def _show_history_details(self) -> None:
        selected = self.operation_table.selectionModel().selectedRows()
        if len(selected) != 1:
            return
        item = self.operation_table.item(selected[0].row(), 0)
        details = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not isinstance(details, list):
            return
        lines = ["Recorded per-file outcomes:"]
        for detail in details:
            if not isinstance(detail, dict):
                continue
            error = f" — {detail['error']}" if detail.get("error") else ""
            lines.append(f"{detail['outcome']}: {detail['source']}{error}")
        self.results_text.setPlainText("\n".join(lines))

    def _checked_recovery_ids(self) -> list[str]:
        selected: list[str] = []
        for row in range(self.history_table.rowCount()):
            holder = self.history_table.cellWidget(row, 0)
            checkbox = holder.findChild(QCheckBox) if holder else None
            item = self.history_table.item(row, 1)
            if checkbox and checkbox.isChecked() and item is not None:
                selected.append(str(item.data(Qt.ItemDataRole.UserRole)))
        return selected

    @Slot()
    def review_restore(self) -> None:
        recovery_ids = self._checked_recovery_ids()
        if not recovery_ids:
            self._set_status("Select at least one quarantined item to restore.", error=True)
            return
        try:
            plan = self.recovery.prepare_restore(recovery_ids)
        except FileExistsError:
            if len(recovery_ids) != 1:
                self._set_status(
                    "A restore destination is occupied. Select one item and choose an alternate.",
                    error=True,
                )
                return
            row = self.database.recovery_item(recovery_ids[0])
            suggested = str(row["original_path"]) if row is not None else ""
            alternative, _ = QFileDialog.getSaveFileName(
                self, "Choose an alternate restore name", suggested
            )
            if not alternative:
                self._set_status("Restore cancelled; recovery payload remains unchanged.")
                return
            try:
                plan = self.recovery.prepare_restore(
                    recovery_ids, alternatives={recovery_ids[0]: Path(alternative)}
                )
            except (OSError, RuntimeError, ValueError) as error:
                self._set_status(f"Restore plan unavailable: {error}", error=True)
                return
        except (OSError, RuntimeError, ValueError) as error:
            self._set_status(f"Restore plan unavailable: {error}", error=True)
            return
        rows = [
            (
                item.destination,
                item.size,
                "Restore reviewed payload",
                "Recoverable item is moved back",
            )
            for item in plan.items
        ]
        dialog = ConfirmationDialog(
            title="Confirm restore",
            warning=(
                "Review the exact restore destinations. Existing files are never overwritten; "
                "a collision preserves both versions."
            ),
            rows=rows,
            confirm_text="Restore reviewed files",
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._set_status("Restore cancelled; recovery payloads remain unchanged.")
            return
        # Restore approval is distinct and minted only after this exact review is accepted.
        capability = self.approvals._grant_from_ui(
            proposal_digest=plan.digest,
            reviewed_digest=plan.digest,
            action="restore",
        )
        self._execute_restore(plan, capability)

    def _execute_restore(self, plan: RecoveryActionPlan, capability: object) -> None:
        try:
            result = self.recovery.restore(plan, capability)
        except (OSError, RuntimeError, ValueError) as error:
            self._set_status(f"Restore failed before completion: {error}", error=True)
            return
        self._show_operation_result(result, "Restore")
        self.refresh_history()

    @Slot()
    def review_purge(self) -> None:
        recovery_ids = self._checked_recovery_ids()
        if not recovery_ids:
            self._set_status(
                "Select at least one quarantined item to permanently purge.", error=True
            )
            return
        try:
            plan = self.purge.prepare(recovery_ids)
        except (OSError, RuntimeError, ValueError) as error:
            self._set_status(f"Purge plan unavailable: {error}", error=True)
            return
        rows = [
            (
                item.source,
                item.size,
                "Permanent deletion of app-owned recovery payload",
                "No restore is possible after successful purge",
            )
            for item in plan.items
        ]
        dialog = ConfirmationDialog(
            title="Confirm permanent purge",
            warning=(
                "IRREVERSIBLE: this permanently deletes only the selected AI-cleaner recovery "
                "payloads. This is separate from quarantine approval and cannot be undone."
            ),
            rows=rows,
            confirm_text="Permanently delete reviewed payloads",
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._set_status("Permanent purge cancelled; recovery payloads remain unchanged.")
            return
        # Purge requires its own capability after the irreversible-action review.
        capability = self.approvals._grant_from_ui(
            proposal_digest=plan.digest,
            reviewed_digest=plan.digest,
            action="purge",
        )
        self._execute_purge(plan, capability)

    def _execute_purge(self, plan: RecoveryActionPlan, capability: object) -> None:
        try:
            result = self.purge.execute(plan, capability)
        except (OSError, RuntimeError, ValueError) as error:
            self._set_status(f"Permanent purge failed before completion: {error}", error=True)
            return
        self._show_operation_result(result, "Permanent purge")
        self.refresh_history()

    def _show_operation_result(self, result: OperationResult, label: str) -> None:
        lines = [f"{label}: {result.status} (run {result.run_id})"]
        for outcome in result.outcomes:
            detail = f" — {outcome.error}" if outcome.error else ""
            lines.append(
                f"{outcome.outcome.upper()}: {outcome.relative_path} "
                f"({_format_size(outcome.logical_bytes)}){detail}"
            )
        lines.append(f"Quarantined logical bytes: {result.quarantined_bytes}")
        lines.append(f"Permanently removed logical bytes: {result.logical_bytes_removed}")
        reclaimed = (
            "not measured" if result.reclaimed_bytes is None else str(result.reclaimed_bytes)
        )
        lines.append(f"Physically reclaimed disk bytes: {reclaimed}")
        self.results_text.setPlainText("\n".join(lines))
        self.tabs.setCurrentIndex(1)
        self._set_status(
            f"{label} {result.status}. Inspect the per-file outcomes in Recovery & history."
        )

    def _set_status(self, text: str, *, error: bool = False) -> None:
        self.status_label.setText(text)
        self.status_label.setStyleSheet("color: #a40000;" if error else "")

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override
        if self._scan_cancel is not None:
            self._scan_cancel.set()
        if self._scan_thread is not None and self._scan_thread.isRunning():
            self._scan_thread.quit()
            self._scan_thread.wait(2000)
        if self._task_cancel is not None:
            self._task_cancel.set()
        if self._task_thread is not None and self._task_thread.isRunning():
            self._task_thread.quit()
            self._task_thread.wait(2000)
        super().closeEvent(event)


def main(*, root: Path | None = None, state_override: Path | None = None) -> int:
    application = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(root=root, state_override=state_override)
    window.show()
    return application.exec()
