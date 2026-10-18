from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePath
from typing import Any, cast

from ai_cleaner.platform.windows_fs import BoundaryError, FileChangedError, WindowsFilesystem
from ai_cleaner.services.scan import Scanner
from ai_cleaner.storage.database import Database


class TaskConflictError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TaskDiff:
    task_id: str
    status: str
    added: tuple[str, ...]
    modified: tuple[str, ...]
    missing: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class TaskService:
    def __init__(self, database: Database, filesystem: WindowsFilesystem, scanner: Scanner) -> None:
        self.database = database
        self.filesystem = filesystem
        self.scanner = scanner

    def start(
        self,
        root: Path,
        label: str,
        *,
        excluded_roots: tuple[Path, ...] = (),
        cancel: threading.Event | None = None,
        progress: Callable[[int], None] | None = None,
    ) -> str:
        if not label.strip():
            raise ValueError("task label cannot be empty")
        root = root.absolute()
        identity = self.filesystem.validate_project_root(root)
        scan = self.scanner.scan(
            root, excluded_roots=excluded_roots, cancel=cancel, progress=progress
        )
        if not scan.complete:
            raise RuntimeError("a complete baseline scan is required to start a task")
        now = utc_now()
        project_id = self.database.ensure_project(
            root=root,
            resolved_root=identity.final_path,
            volume_serial=identity.volume_serial,
            created_at=now,
        )
        if self.database.unresolved_task(project_id) is not None:
            raise TaskConflictError(
                "one active task already exists, or an interrupted task must be resolved"
            )
        self.database.save_scan(project_id, scan, now)
        task_id = str(uuid.uuid4())
        try:
            with self.database.transaction(immediate=True) as connection:
                connection.execute(
                    "INSERT INTO tasks VALUES (?, ?, ?, 'active', ?, NULL, ?, NULL)",
                    (task_id, project_id, label.strip(), scan.scan_id, now),
                )
        except sqlite3.IntegrityError as error:
            raise TaskConflictError("one active task already exists for this project") from error
        return task_id

    def register(self, task_id: str, relative_path: str, role: str, source: str = "cli") -> None:
        if role not in {"scratch", "deliverable", "input"}:
            raise ValueError("role must be scratch, deliverable, or input")
        task = self._require_task(task_id)
        if task["status"] != "active":
            raise TaskConflictError("artifacts can be registered only for an active task")
        project = self._project(str(task["project_id"]))
        relative = PurePath(relative_path)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise BoundaryError("registered path must be relative and remain inside the project")
        normalized = str(relative).replace("/", os.sep)
        root = Path(str(project["root"]))
        candidate = (root / normalized).absolute()
        if os.path.commonpath([str(candidate), str(root)]) != str(root):
            raise BoundaryError("registered path escapes the project")
        with self.database.transaction(immediate=True) as connection:
            existing = connection.execute(
                """SELECT role FROM artifact_declarations
                   WHERE task_id = ? AND relative_path = ? COLLATE NOCASE""",
                (task_id, normalized),
            ).fetchone()
            if existing and existing["role"] != role:
                raise TaskConflictError("path is already registered with a different role")
            connection.execute(
                """INSERT OR IGNORE INTO artifact_declarations
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), task_id, normalized, role, source, utc_now()),
            )

    def register_temp(self, task_id: str, relative_path: str, source: str = "cli") -> None:
        task = self._require_task(task_id)
        if task["status"] != "active":
            raise TaskConflictError("temporary files can be registered only for an active task")
        project = self._project(str(task["project_id"]))
        relative = PurePath(relative_path)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise BoundaryError("registered path must be relative and remain inside the project")
        normalized = str(relative).replace("/", os.sep)
        baseline = self.database.observations(str(task["baseline_scan_id"]))
        if normalized.casefold() in baseline:
            raise TaskConflictError("files present at task start cannot be registered as temporary")
        root = Path(str(project["root"]))
        candidate = (root / normalized).absolute()
        identity = self.filesystem.validate_candidate(candidate, root)
        with self.filesystem.open_exclusive_file(candidate) as handle:
            before = self.filesystem.identity_from_handle(handle)
            sha256 = self.filesystem.hash_handle(handle)
            after = self.filesystem.identity_from_handle(handle)
        if before != after or before != identity:
            raise FileChangedError("temporary file changed while it was registered")
        now = utc_now()
        with self.database.transaction(immediate=True) as connection:
            existing = connection.execute(
                """SELECT role FROM artifact_declarations
                   WHERE task_id = ? AND relative_path = ? COLLATE NOCASE""",
                (task_id, normalized),
            ).fetchone()
            if existing and existing["role"] != "scratch":
                raise TaskConflictError("path is already registered with a different role")
            connection.execute(
                """INSERT OR IGNORE INTO artifact_declarations
                   VALUES (?, ?, ?, 'scratch', ?, ?)""",
                (str(uuid.uuid4()), task_id, normalized, source, now),
            )
            connection.execute(
                """INSERT INTO task_temp_files VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(task_id, relative_path) DO UPDATE SET
                     volume_serial = excluded.volume_serial,
                     file_index = excluded.file_index,
                     size = excluded.size,
                     modified_100ns = excluded.modified_100ns,
                     attributes = excluded.attributes,
                     sha256 = excluded.sha256,
                     registered_at = excluded.registered_at""",
                (
                    task_id,
                    normalized,
                    identity.volume_serial,
                    identity.file_index,
                    identity.size,
                    identity.modified_100ns,
                    identity.attributes,
                    sha256,
                    now,
                ),
            )

    def finish(
        self,
        task_id: str,
        *,
        excluded_roots: tuple[Path, ...] = (),
        cancel: threading.Event | None = None,
        progress: Callable[[int], None] | None = None,
    ) -> TaskDiff:
        task = self._require_task(task_id)
        if task["status"] not in {"active", "interrupted"}:
            raise TaskConflictError("task is already finished")
        project = self._project(str(task["project_id"]))
        root = Path(str(project["root"]))
        scan = self.scanner.scan(
            root, excluded_roots=excluded_roots, cancel=cancel, progress=progress
        )
        if not scan.complete:
            raise RuntimeError("a complete end scan is required to finish a task")
        now = utc_now()
        self.database.save_scan(str(task["project_id"]), scan, now)
        with self.database.transaction(immediate=True) as connection:
            connection.execute(
                "UPDATE tasks SET status = 'finished', end_scan_id = ?, ended_at = ? WHERE id = ?",
                (scan.scan_id, now, task_id),
            )
        return self.diff(task_id)

    def interrupt(self, task_id: str) -> None:
        task = self._require_task(task_id)
        if task["status"] != "active":
            raise TaskConflictError("only an active task can be interrupted")
        with self.database.transaction(immediate=True) as connection:
            connection.execute("UPDATE tasks SET status = 'interrupted' WHERE id = ?", (task_id,))

    def diff(self, task_id: str) -> TaskDiff:
        task = self._require_task(task_id)
        baseline = self.database.observations(str(task["baseline_scan_id"]))
        end_scan_id = task["end_scan_id"]
        if not end_scan_id:
            return TaskDiff(task_id, str(task["status"]), (), (), ())
        ending = self.database.observations(str(end_scan_id))
        added = tuple(sorted(set(ending) - set(baseline)))
        missing = tuple(sorted(set(baseline) - set(ending)))
        modified = tuple(
            sorted(
                path
                for path in set(baseline) & set(ending)
                if (
                    baseline[path]["size"],
                    baseline[path]["modified_ns"],
                    baseline[path]["file_index"],
                )
                != (
                    ending[path]["size"],
                    ending[path]["modified_ns"],
                    ending[path]["file_index"],
                )
            )
        )
        return TaskDiff(task_id, str(task["status"]), added, modified, missing)

    def require_finished(self, task_id: str) -> None:
        task = self._require_task(task_id)
        if task["status"] != "finished":
            raise TaskConflictError("active or interrupted tasks cannot be proposed for cleanup")

    def _require_task(self, task_id: str) -> sqlite3.Row:
        task = self.database.task(task_id)
        if task is None:
            raise ValueError(f"unknown task: {task_id}")
        return task

    def _project(self, project_id: str) -> sqlite3.Row:
        with self.database.connect() as connection:
            project = connection.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
        if project is None:
            raise RuntimeError("task project is missing")
        return cast(sqlite3.Row, project)
