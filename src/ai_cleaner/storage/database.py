from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from ai_cleaner.domain.models import ScanResult
from ai_cleaner.domain.proposals import Proposal, ProposalItem

SCHEMA_VERSION = 3

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
CREATE TABLE IF NOT EXISTS task_temp_files (
    task_id TEXT NOT NULL REFERENCES tasks(id),
    relative_path TEXT NOT NULL COLLATE NOCASE,
    volume_serial INTEGER NOT NULL,
    file_index INTEGER NOT NULL,
    size INTEGER NOT NULL,
    modified_100ns INTEGER NOT NULL,
    attributes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    PRIMARY KEY (task_id, relative_path)
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
    project_id TEXT NOT NULL REFERENCES projects(id),
    proposal_digest TEXT NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    proposal_id TEXT,
    task_id TEXT,
    approved_at TEXT
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
                return
            if version == 1:
                connection.execute("ALTER TABLE operation_runs ADD COLUMN project_id TEXT")
                version = 2
            if version == 2:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS task_temp_files (
                        task_id TEXT NOT NULL REFERENCES tasks(id),
                        relative_path TEXT NOT NULL COLLATE NOCASE,
                        volume_serial INTEGER NOT NULL,
                        file_index INTEGER NOT NULL,
                        size INTEGER NOT NULL,
                        modified_100ns INTEGER NOT NULL,
                        attributes INTEGER NOT NULL,
                        sha256 TEXT NOT NULL,
                        registered_at TEXT NOT NULL,
                        PRIMARY KEY (task_id, relative_path)
                    );
                    ALTER TABLE operation_runs ADD COLUMN proposal_id TEXT;
                    ALTER TABLE operation_runs ADD COLUMN task_id TEXT;
                    ALTER TABLE operation_runs ADD COLUMN approved_at TEXT;
                    """
                )
                version = 3
            if version != SCHEMA_VERSION:
                raise RuntimeError(f"no migration path from schema {version}")
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

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
                project_id = str(existing["id"])
                if recovery_root is not None:
                    connection.execute(
                        """UPDATE projects SET resolved_root = ?, volume_serial = ?,
                           recovery_root = ?, policy_version = ? WHERE id = ?""",
                        (
                            resolved_root,
                            volume_serial,
                            str(recovery_root),
                            policy_version,
                            project_id,
                        ),
                    )
                return project_id
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

    def unresolved_task(self, project_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return cast(
                sqlite3.Row | None,
                connection.execute(
                    """SELECT * FROM tasks WHERE project_id = ?
                       AND status IN ('active', 'interrupted')
                       ORDER BY started_at DESC LIMIT 1""",
                    (project_id,),
                ).fetchone(),
            )

    def unresolved_tasks(self, project_id: str) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return list(
                connection.execute(
                    """SELECT * FROM tasks WHERE project_id = ?
                       AND status IN ('active', 'interrupted')
                       ORDER BY started_at""",
                    (project_id,),
                ).fetchall()
            )

    def task_declarations(self, task_id: str) -> dict[str, str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT relative_path, role FROM artifact_declarations WHERE task_id = ?",
                (task_id,),
            ).fetchall()
        return {str(row["relative_path"]): str(row["role"]) for row in rows}

    def temp_registrations(self, task_id: str) -> dict[str, sqlite3.Row]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM task_temp_files WHERE task_id = ?", (task_id,)
            ).fetchall()
        return {str(row["relative_path"]).casefold(): row for row in rows}

    def observations(self, scan_id: str) -> dict[str, sqlite3.Row]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM observations WHERE scan_id = ?", (scan_id,)
            ).fetchall()
        return {str(row["relative_path"]).casefold(): row for row in rows}

    def save_proposal(self, proposal: Proposal) -> None:
        with self.transaction(immediate=True) as connection:
            connection.execute(
                "INSERT INTO proposals VALUES (?, ?, ?, ?, ?, 'reviewable', ?)",
                (
                    proposal.proposal_id,
                    proposal.project_id,
                    proposal.task_id,
                    proposal.policy_digest,
                    proposal.items_digest,
                    proposal.created_at,
                ),
            )
            connection.executemany(
                """INSERT INTO proposal_items
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        proposal.proposal_id,
                        item.relative_path,
                        item.action,
                        item.volume_serial,
                        item.file_index,
                        item.size,
                        item.modified_100ns,
                        item.attributes,
                        item.sha256,
                        item.explanation,
                        item.recovery_path,
                    )
                    for item in proposal.items
                ],
            )

    def proposal(self, proposal_id: str) -> Proposal | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT p.*, pr.root, pr.recovery_root, t.label AS task_label
                   FROM proposals p JOIN projects pr ON pr.id = p.project_id
                   LEFT JOIN tasks t ON t.id = p.task_id
                   WHERE p.id = ?""",
                (proposal_id,),
            ).fetchone()
            if row is None or not row["recovery_root"]:
                return None
            items = tuple(
                ProposalItem(
                    relative_path=str(item["relative_path"]),
                    action=str(item["action"]),
                    volume_serial=int(item["volume_serial"]),
                    file_index=int(item["file_index"]),
                    size=int(item["size"]),
                    modified_100ns=int(item["modified_100ns"]),
                    attributes=int(item["attributes"]),
                    sha256=str(item["sha256"]),
                    explanation=str(item["explanation"]),
                    recovery_path=str(item["recovery_path"]),
                )
                for item in connection.execute(
                    """SELECT * FROM proposal_items WHERE proposal_id = ?
                       ORDER BY relative_path COLLATE NOCASE""",
                    (proposal_id,),
                ).fetchall()
            )
        return Proposal(
            proposal_id=str(row["id"]),
            project_id=str(row["project_id"]),
            task_id=str(row["task_id"]) if row["task_id"] is not None else None,
            root=str(row["root"]),
            recovery_root=str(row["recovery_root"]),
            policy_digest=str(row["policy_digest"]),
            items=items,
            items_digest=str(row["items_digest"]),
            created_at=str(row["created_at"]),
            task_label=str(row["task_label"]) if row["task_label"] is not None else None,
        )

    def proposal_by_digest(self, items_digest: str) -> Proposal | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id FROM proposals WHERE items_digest = ?", (items_digest,)
            ).fetchone()
        return self.proposal(str(row["id"])) if row is not None else None

    def proposal_state(self, proposal_id: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT state FROM proposals WHERE id = ?", (proposal_id,)
            ).fetchone()
        return str(row["state"]) if row is not None else None

    def set_proposal_state(
        self, proposal_id: str, state: str, *, expected: tuple[str, ...] | None = None
    ) -> None:
        with self.transaction(immediate=True) as connection:
            if expected:
                placeholders = ", ".join("?" for _ in expected)
                cursor = connection.execute(
                    f"UPDATE proposals SET state = ? WHERE id = ? AND state IN ({placeholders})",
                    (state, proposal_id, *expected),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("proposal is no longer reviewable")
            else:
                cursor = connection.execute(
                    "UPDATE proposals SET state = ? WHERE id = ?", (state, proposal_id)
                )
                if cursor.rowcount != 1:
                    raise ValueError(f"unknown proposal: {proposal_id}")

    def create_operation_run(
        self,
        *,
        run_id: str,
        project_id: str,
        proposal_digest: str,
        action: str,
        started_at: str,
        proposal_id: str | None = None,
        task_id: str | None = None,
        approved_at: str | None = None,
    ) -> None:
        with self.transaction(immediate=True) as connection:
            connection.execute(
                """INSERT INTO operation_runs
                   (id, project_id, proposal_digest, action, status, started_at, ended_at,
                    proposal_id, task_id, approved_at)
                   VALUES (?, ?, ?, ?, 'running', ?, NULL, ?, ?, ?)""",
                (
                    run_id,
                    project_id,
                    proposal_digest,
                    action,
                    started_at,
                    proposal_id,
                    task_id,
                    approved_at,
                ),
            )

    def set_run_status(self, run_id: str, status: str, ended_at: str | None) -> None:
        with self.transaction(immediate=True) as connection:
            connection.execute(
                "UPDATE operation_runs SET status = ?, ended_at = ? WHERE id = ?",
                (status, ended_at, run_id),
            )

    def create_operation_item(
        self,
        *,
        item_id: str,
        run_id: str,
        source: str,
        destination: str,
        expected_volume: int,
        expected_file: int,
        expected_sha256: str,
        intent_at: str,
    ) -> None:
        with self.transaction(immediate=True) as connection:
            connection.execute(
                """INSERT INTO operation_items
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', NULL, NULL)""",
                (
                    item_id,
                    run_id,
                    source,
                    destination,
                    expected_volume,
                    expected_file,
                    expected_sha256,
                    intent_at,
                ),
            )

    def set_operation_outcome(self, item_id: str, outcome: str, error: str | None) -> None:
        with self.transaction(immediate=True) as connection:
            connection.execute(
                """UPDATE operation_items
                   SET outcome = ?, error = ?, completed_at = ? WHERE id = ?""",
                (outcome, error, utc_timestamp(), item_id),
            )

    def add_recovery_item(
        self,
        *,
        recovery_id: str,
        operation_item_id: str,
        project_id: str,
        original_path: str,
        payload_path: str,
        volume_serial: int,
        file_index: int,
        size: int,
        sha256: str,
        state: str = "quarantined",
    ) -> None:
        now = utc_timestamp()
        with self.transaction(immediate=True) as connection:
            connection.execute(
                """INSERT OR IGNORE INTO recovery_items
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)""",
                (
                    recovery_id,
                    operation_item_id,
                    project_id,
                    original_path,
                    payload_path,
                    volume_serial,
                    file_index,
                    size,
                    sha256,
                    now,
                    state,
                    now,
                ),
            )

    def pending_operation_items(self) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return list(
                connection.execute(
                    """SELECT oi.*, r.project_id, r.action, r.status AS run_status
                       FROM operation_items oi JOIN operation_runs r ON r.id = oi.run_id
                       WHERE oi.outcome = 'pending'"""
                ).fetchall()
            )

    def recovery_item(self, recovery_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return cast(
                sqlite3.Row | None,
                connection.execute(
                    "SELECT * FROM recovery_items WHERE id = ?", (recovery_id,)
                ).fetchone(),
            )

    def recovery_by_operation(self, operation_item_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return cast(
                sqlite3.Row | None,
                connection.execute(
                    "SELECT * FROM recovery_items WHERE operation_item_id = ?",
                    (operation_item_id,),
                ).fetchone(),
            )

    def recovery_by_payload(self, payload_path: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return cast(
                sqlite3.Row | None,
                connection.execute(
                    "SELECT * FROM recovery_items WHERE payload_path = ? COLLATE NOCASE",
                    (payload_path,),
                ).fetchone(),
            )

    def project(self, project_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return cast(
                sqlite3.Row | None,
                connection.execute(
                    "SELECT * FROM projects WHERE id = ?", (project_id,)
                ).fetchone(),
            )

    def recovery_items(self, project_id: str | None = None) -> list[sqlite3.Row]:
        with self.connect() as connection:
            if project_id:
                rows = connection.execute(
                    """SELECT * FROM recovery_items WHERE project_id = ?
                       ORDER BY quarantined_at DESC""",
                    (project_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM recovery_items ORDER BY quarantined_at DESC"
                ).fetchall()
        return list(rows)

    def recovery_items_for_run(self, run_id: str) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return list(
                connection.execute(
                    """SELECT ri.* FROM recovery_items ri
                       JOIN operation_items oi ON oi.id = ri.operation_item_id
                       JOIN operation_runs r ON r.id = oi.run_id
                       WHERE r.id = ? AND r.action = 'quarantine'
                       ORDER BY oi.intent_at""",
                    (run_id,),
                ).fetchall()
            )

    def update_recovery_state(
        self, recovery_id: str, state: str, *, restored_path: str | None = None
    ) -> None:
        with self.transaction(immediate=True) as connection:
            connection.execute(
                """UPDATE recovery_items
                   SET state = ?, restored_path = ?, updated_at = ? WHERE id = ?""",
                (state, restored_path, utc_timestamp(), recovery_id),
            )

    def history(self, project_id: str) -> list[dict[str, object]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT r.id, r.action, r.status, r.started_at, r.ended_at,
                          COUNT(i.id) AS item_count,
                          SUM(CASE WHEN i.outcome IN ('moved', 'restored', 'purged', 'reconciled')
                                   THEN 1 ELSE 0 END) AS success_count,
                          SUM(CASE WHEN i.outcome IN ('failed', 'collision', 'unresolved')
                                   THEN 1 ELSE 0 END) AS failure_count
                   FROM operation_runs r
                   LEFT JOIN operation_items i ON i.run_id = r.id
                   WHERE r.project_id = ?
                   GROUP BY r.id ORDER BY r.started_at DESC""",
                (project_id,),
            ).fetchall()
        history: list[dict[str, object]] = []
        with self.connect() as connection:
            for row in rows:
                entry = dict(row)
                entry["items"] = [
                    dict(item)
                    for item in connection.execute(
                        """SELECT source, destination, outcome, error, completed_at
                           FROM operation_items WHERE run_id = ? ORDER BY intent_at""",
                        (row["id"],),
                    ).fetchall()
                ]
                history.append(entry)
        return history


def utc_timestamp() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
