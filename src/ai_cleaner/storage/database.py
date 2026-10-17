from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from ai_cleaner.domain.models import ScanResult

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    root TEXT NOT NULL UNIQUE COLLATE NOCASE,
    resolved_root TEXT NOT NULL,
    volume_serial INTEGER NOT NULL,
    recovery_root TEXT,
    policy_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scans (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    visited_entries INTEGER NOT NULL,
    issue_count INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS observations (
    scan_id TEXT NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL COLLATE NOCASE,
    original_path TEXT NOT NULL,
    volume_serial INTEGER,
    file_index INTEGER,
    size INTEGER NOT NULL,
    modified_ns INTEGER NOT NULL,
    created_ns INTEGER NOT NULL,
    attributes INTEGER NOT NULL,
    observed_state TEXT NOT NULL,
    PRIMARY KEY (scan_id, relative_path)
);
CREATE TABLE IF NOT EXISTS scan_issues (
    scan_id TEXT NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    code TEXT NOT NULL,
    message TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS protections (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    relative_path TEXT NOT NULL COLLATE NOCASE,
    reason TEXT NOT NULL,
    origin TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(project_id, relative_path, origin)
);
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    label TEXT NOT NULL,
    status TEXT NOT NULL,
    baseline_scan_id TEXT NOT NULL REFERENCES scans(id),
    end_scan_id TEXT REFERENCES scans(id),
    started_at TEXT NOT NULL,
    ended_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_task_per_project
ON tasks(project_id) WHERE status = 'active';
CREATE TABLE IF NOT EXISTS artifact_declarations (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    relative_path TEXT NOT NULL COLLATE NOCASE,
    role TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(task_id, relative_path, role)
);
CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    task_id TEXT REFERENCES tasks(id),
    policy_digest TEXT NOT NULL,
    items_digest TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS proposal_items (
    proposal_id TEXT NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL COLLATE NOCASE,
    action TEXT NOT NULL,
    volume_serial INTEGER NOT NULL,
    file_index INTEGER NOT NULL,
    size INTEGER NOT NULL,
    modified_100ns INTEGER NOT NULL,
    attributes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    explanation TEXT NOT NULL,
    recovery_path TEXT NOT NULL,
    PRIMARY KEY (proposal_id, relative_path)
);
CREATE TABLE IF NOT EXISTS operation_runs (
    id TEXT PRIMARY KEY,
    proposal_digest TEXT NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT
);
CREATE TABLE IF NOT EXISTS operation_items (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES operation_runs(id),
    source TEXT NOT NULL,
    destination TEXT NOT NULL,
    expected_volume INTEGER NOT NULL,
    expected_file INTEGER NOT NULL,
    expected_sha256 TEXT NOT NULL,
    intent_at TEXT NOT NULL,
    outcome TEXT NOT NULL,
    error TEXT,
    completed_at TEXT
);
CREATE TABLE IF NOT EXISTS recovery_items (
    id TEXT PRIMARY KEY,
    operation_item_id TEXT NOT NULL UNIQUE REFERENCES operation_items(id),
    project_id TEXT NOT NULL REFERENCES projects(id),
    original_path TEXT NOT NULL,
    payload_path TEXT NOT NULL UNIQUE,
    volume_serial INTEGER NOT NULL,
    file_index INTEGER NOT NULL,
    size INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    quarantined_at TEXT NOT NULL,
    state TEXT NOT NULL,
    restored_path TEXT,
    updated_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def migrate(self) -> None:
        with self.connect() as connection:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if version > SCHEMA_VERSION:
                raise RuntimeError(
                    f"database schema {version} is newer than supported {SCHEMA_VERSION}"
                )
            if version == 0:
                connection.executescript(SCHEMA)
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            elif version != SCHEMA_VERSION:
                raise RuntimeError(f"no migration path from schema {version}")

    @contextmanager
    def transaction(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def save_scan(self, project_id: str, result: ScanResult, created_at: str) -> None:
        with self.transaction(immediate=True) as connection:
            connection.execute(
                "INSERT INTO scans VALUES (?, ?, ?, ?, ?, ?)",
                (
                    result.scan_id,
                    project_id,
                    created_at,
                    result.status.value,
                    result.visited_entries,
                    len(result.issues),
                ),
            )
            connection.executemany(
                "INSERT INTO observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        result.scan_id,
                        item.relative_path,
                        item.relative_path,
                        item.volume_serial,
                        item.file_index,
                        item.size,
                        item.modified_ns,
                        item.created_ns,
                        item.attributes,
                        item.state,
                    )
                    for item in result.observations
                ],
            )
            connection.executemany(
                "INSERT INTO scan_issues VALUES (?, ?, ?, ?)",
                [
                    (result.scan_id, issue.relative_path, issue.code, issue.message)
                    for issue in result.issues
                ],
            )

    def ensure_project(
        self,
        *,
        root: Path,
        resolved_root: str,
        volume_serial: int,
        created_at: str,
        recovery_root: Path | None = None,
        policy_version: str = "1",
    ) -> str:
        with self.transaction(immediate=True) as connection:
            existing = connection.execute(
                "SELECT id FROM projects WHERE root = ? COLLATE NOCASE", (str(root),)
            ).fetchone()
            if existing:
                return str(existing["id"])
            project_id = str(uuid.uuid4())
            connection.execute(
                "INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    project_id,
                    str(root),
                    resolved_root,
                    volume_serial,
                    str(recovery_root) if recovery_root else None,
                    policy_version,
                    created_at,
                ),
            )
            return project_id

    def add_protection(
        self,
        *,
        protection_id: str,
        project_id: str,
        relative_path: str,
        reason: str,
        origin: str,
        created_at: str,
    ) -> None:
        with self.transaction(immediate=True) as connection:
            connection.execute(
                """INSERT OR IGNORE INTO protections
                   (id, project_id, relative_path, reason, origin, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (protection_id, project_id, relative_path, reason, origin, created_at),
            )

    def protections(self, project_id: str) -> dict[str, str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT relative_path, reason FROM protections WHERE project_id = ?",
                (project_id,),
            ).fetchall()
        return {str(row["relative_path"]).casefold(): str(row["reason"]) for row in rows}

    def project_by_root(self, root: Path) -> sqlite3.Row | None:
        with self.connect() as connection:
            return cast(
                sqlite3.Row | None,
                connection.execute(
                    "SELECT * FROM projects WHERE root = ? COLLATE NOCASE",
                    (str(root.absolute()),),
                ).fetchone(),
            )

    def task(self, task_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return cast(
                sqlite3.Row | None,
                connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone(),
            )

    def task_declarations(self, task_id: str) -> dict[str, str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT relative_path, role FROM artifact_declarations WHERE task_id = ?",
                (task_id,),
            ).fetchall()
        return {str(row["relative_path"]): str(row["role"]) for row in rows}

    def observations(self, scan_id: str) -> dict[str, sqlite3.Row]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM observations WHERE scan_id = ?", (scan_id,)
            ).fetchall()
        return {str(row["relative_path"]).casefold(): row for row in rows}
