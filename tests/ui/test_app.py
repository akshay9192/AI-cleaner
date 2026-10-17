from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QInputDialog,
    QPushButton,
)

from ai_cleaner.domain.models import ScanResult, ScanStatus
from ai_cleaner.ui.app import ConfirmationDialog, MainWindow

pytestmark = [pytest.mark.ui, pytest.mark.windows]


def _window(qtbot: Any, tmp_path: Path, files: dict[str, bytes] | None = None) -> MainWindow:
    root = tmp_path / "selected project"
    state = tmp_path / "application state"
    root.mkdir()
    for name, content in (files or {}).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    window = MainWindow(root=root, state_override=state)
    qtbot.addWidget(window)
    window.show()
    assert window.project_root == root.absolute()
    return window


def _wait_for_scan(qtbot: Any, window: MainWindow) -> None:
    qtbot.waitUntil(lambda: window._scan_thread is None, timeout=10_000)


def _wait_for_task(qtbot: Any, window: MainWindow) -> None:
    qtbot.waitUntil(lambda: window._task_thread is None, timeout=10_000)


def _scan(qtbot: Any, window: MainWindow) -> None:
    qtbot.mouseClick(window.scan_button, Qt.MouseButton.LeftButton)
    _wait_for_scan(qtbot, window)


def _row_for_path(window: MainWindow, relative_path: str) -> int:
    for row in range(window.review_table.rowCount()):
        item = window.review_table.item(row, 1)
        if item is not None and item.text() == relative_path:
            return row
    raise AssertionError(f"missing review row: {relative_path}")


def _candidate_checkbox(window: MainWindow, relative_path: str) -> QCheckBox:
    row = _row_for_path(window, relative_path)
    holder = window.review_table.cellWidget(row, 0)
    assert holder is not None
    checkbox = holder.findChild(QCheckBox)
    assert checkbox is not None
    return checkbox


def _recovery_checkbox(window: MainWindow, row: int = 0) -> QCheckBox:
    holder = window.history_table.cellWidget(row, 0)
    assert holder is not None
    checkbox = holder.findChild(QCheckBox)
    assert checkbox is not None
    return checkbox


def _accept_next_confirmation(qtbot: Any) -> None:
    def accept() -> None:
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, ConfirmationDialog)
        button = dialog.findChild(QPushButton, "confirmActionButton")
        assert button is not None
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    QTimer.singleShot(25, accept)


def _reject_next_confirmation() -> None:
    def reject() -> None:
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, QDialog)
        dialog.reject()

    QTimer.singleShot(25, reject)


def test_empty_state_and_successful_scan_are_read_only_and_unchecked(
    qtbot: Any, tmp_path: Path
) -> None:
    original = b"candidate"
    window = _window(
        qtbot,
        tmp_path,
        {"cache.aux": original, "source.py": b"print('keep')\n"},
    )
    assert window.empty_label.isVisible()
    assert not window.move_button.isEnabled()

    _scan(qtbot, window)

    assert window.review_table.rowCount() == 2
    candidate = _candidate_checkbox(window, "cache.aux")
    source = _candidate_checkbox(window, "source.py")
    assert not candidate.isChecked()
    assert candidate.isEnabled()
    assert not source.isChecked()
    assert not source.isEnabled()
    assert (window.project_root / "cache.aux").read_bytes() == original
    assert "complete" in window.status_label.text()


def test_tracked_task_controls_capture_start_and_finish_snapshots(
    qtbot: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window(qtbot, tmp_path, {"source.py": b"keep"})
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        staticmethod(lambda *args, **kwargs: ("UI tracked task", True)),
    )

    qtbot.mouseClick(window.start_task_button, Qt.MouseButton.LeftButton)
    _wait_for_task(qtbot, window)
    active = window.database.unresolved_task(window.project_id)
    assert active is not None
    assert active["label"] == "UI tracked task"
    assert window.finish_task_button.isEnabled()

    (window.project_root / "observed.aux").write_bytes(b"observed")
    qtbot.mouseClick(window.finish_task_button, Qt.MouseButton.LeftButton)
    _wait_for_task(qtbot, window)
    assert window.database.unresolved_task(window.project_id) is None
    assert "finished" in window.status_label.text()


def test_search_sort_pin_and_bounded_preview(qtbot: Any, tmp_path: Path) -> None:
    window = _window(
        qtbot,
        tmp_path,
        {"one.aux": b"plain preview", "large.aux": b"x" * (64 * 1024 + 10)},
    )
    _scan(qtbot, window)

    window.search_edit.setText("one.aux")
    assert sum(not window.review_table.isRowHidden(row) for row in range(2)) == 1
    row = _row_for_path(window, "one.aux")
    window.review_table.selectRow(row)
    qtbot.mouseClick(window.preview_button, Qt.MouseButton.LeftButton)
    assert window.preview_text.toPlainText() == "plain preview"

    window.search_edit.clear()
    large_row = _row_for_path(window, "large.aux")
    window.review_table.selectRow(large_row)
    qtbot.mouseClick(window.preview_button, Qt.MouseButton.LeftButton)
    assert "truncated at 64 KiB" in window.preview_text.toPlainText()

    one_row = _row_for_path(window, "one.aux")
    window.review_table.selectRow(one_row)
    qtbot.mouseClick(window.pin_button, Qt.MouseButton.LeftButton)
    assert not _candidate_checkbox(window, "one.aux").isEnabled()
    assert "Pinned 1 item" in window.status_label.text()


def test_scan_loading_and_cancel_state_remain_responsive(qtbot: Any, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    entered = threading.Event()

    class SlowScanner:
        def scan(self, root: Path, **kwargs: Any) -> ScanResult:
            cancel = kwargs["cancel"]
            progress = kwargs["progress"]
            entered.set()
            count = 0
            while not cancel.is_set():
                count += 1
                progress(count)
                time.sleep(0.01)
            return ScanResult(str(uuid.uuid4()), root, ScanStatus.CANCELLED, visited_entries=count)

    window.scanner = SlowScanner()  # type: ignore[assignment]
    qtbot.mouseClick(window.scan_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(entered.is_set)
    assert window.cancel_button.isEnabled()
    assert "Scanning in the background" in window.status_label.text()
    qtbot.mouseClick(window.cancel_button, Qt.MouseButton.LeftButton)
    _wait_for_scan(qtbot, window)
    assert window.scan_result is not None
    assert window.scan_result.status is ScanStatus.CANCELLED
    assert not window.move_button.isEnabled()


def test_scan_error_is_actionable_and_does_not_leave_loading_state(
    qtbot: Any, tmp_path: Path
) -> None:
    window = _window(qtbot, tmp_path)

    class FailingScanner:
        def scan(self, root: Path, **kwargs: Any) -> ScanResult:
            del root, kwargs
            raise PermissionError("fixture access denied")

    window.scanner = FailingScanner()  # type: ignore[assignment]
    qtbot.mouseClick(window.scan_button, Qt.MouseButton.LeftButton)
    _wait_for_scan(qtbot, window)
    assert "Scan failed" in window.status_label.text()
    assert "fixture access denied" in window.status_label.text()
    assert window.scan_button.isEnabled()
    assert not window.cancel_button.isEnabled()


def test_cancelled_confirmation_leaves_selected_file_unchanged(
    qtbot: Any, tmp_path: Path
) -> None:
    window = _window(qtbot, tmp_path, {"cancel.aux": b"unchanged"})
    _scan(qtbot, window)
    checkbox = _candidate_checkbox(window, "cancel.aux")
    qtbot.mouseClick(checkbox, Qt.MouseButton.LeftButton)

    _reject_next_confirmation()
    qtbot.mouseClick(window.move_button, Qt.MouseButton.LeftButton)

    assert (window.project_root / "cancel.aux").read_bytes() == b"unchanged"
    assert window.database.recovery_items(window.project_id) == []
    assert "cancelled" in window.status_label.text().casefold()


def test_full_ui_journey_quarantines_and_restores_exact_file(
    qtbot: Any, tmp_path: Path
) -> None:
    payload = b"restore through actual controls"
    window = _window(qtbot, tmp_path, {r"folder\journey.aux": payload})
    _scan(qtbot, window)
    checkbox = _candidate_checkbox(window, "folder\\journey.aux")
    qtbot.mouseClick(checkbox, Qt.MouseButton.LeftButton)

    _accept_next_confirmation(qtbot)
    qtbot.mouseClick(window.move_button, Qt.MouseButton.LeftButton)
    _wait_for_scan(qtbot, window)

    original = window.project_root / "folder" / "journey.aux"
    assert not original.exists()
    recovery_rows = window.database.recovery_items(window.project_id)
    assert len(recovery_rows) == 1
    assert Path(str(recovery_rows[0]["payload_path"])).read_bytes() == payload
    assert "Physically reclaimed disk bytes: not measured" in window.results_text.toPlainText()

    window.refresh_history()
    recovery_checkbox = _recovery_checkbox(window)
    qtbot.mouseClick(recovery_checkbox, Qt.MouseButton.LeftButton)
    _accept_next_confirmation(qtbot)
    qtbot.mouseClick(window.restore_button, Qt.MouseButton.LeftButton)

    assert original.read_bytes() == payload
    assert window.database.recovery_items(window.project_id)[0]["state"] == "restored"
    assert "Restore: complete" in window.results_text.toPlainText()


def test_permanent_purge_has_separate_irreversible_confirmation(
    qtbot: Any, tmp_path: Path
) -> None:
    window = _window(qtbot, tmp_path, {"purge.aux": b"purge payload"})
    _scan(qtbot, window)
    qtbot.mouseClick(_candidate_checkbox(window, "purge.aux"), Qt.MouseButton.LeftButton)
    _accept_next_confirmation(qtbot)
    qtbot.mouseClick(window.move_button, Qt.MouseButton.LeftButton)
    _wait_for_scan(qtbot, window)
    recovery = window.database.recovery_items(window.project_id)[0]
    payload = Path(str(recovery["payload_path"]))

    window.refresh_history()
    qtbot.mouseClick(_recovery_checkbox(window), Qt.MouseButton.LeftButton)
    _reject_next_confirmation()
    qtbot.mouseClick(window.purge_button, Qt.MouseButton.LeftButton)
    assert payload.exists()

    _accept_next_confirmation(qtbot)
    qtbot.mouseClick(window.purge_button, Qt.MouseButton.LeftButton)
    assert not payload.exists()
    assert window.database.recovery_item(str(recovery["id"]))["state"] == "purged"
    assert "Permanently removed logical bytes" in window.results_text.toPlainText()


def test_restore_collision_keeps_newer_file_and_uses_reviewed_alternate(
    qtbot: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window(qtbot, tmp_path, {"collision.aux": b"quarantined version"})
    _scan(qtbot, window)
    qtbot.mouseClick(_candidate_checkbox(window, "collision.aux"), Qt.MouseButton.LeftButton)
    _accept_next_confirmation(qtbot)
    qtbot.mouseClick(window.move_button, Qt.MouseButton.LeftButton)
    _wait_for_scan(qtbot, window)

    occupied = window.project_root / "collision.aux"
    occupied.write_bytes(b"newer version")
    alternate = window.project_root / "collision.restored.aux"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(alternate), "")),
    )
    window.refresh_history()
    qtbot.mouseClick(_recovery_checkbox(window), Qt.MouseButton.LeftButton)
    _accept_next_confirmation(qtbot)
    qtbot.mouseClick(window.restore_button, Qt.MouseButton.LeftButton)

    assert occupied.read_bytes() == b"newer version"
    assert alternate.read_bytes() == b"quarantined version"
