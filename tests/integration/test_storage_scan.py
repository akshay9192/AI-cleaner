from __future__ import annotations

import hashlib
import sqlite3
import threading
from pathlib import Path

from ai_cleaner.domain.models import ScanStatus
from ai_cleaner.platform.windows_fs import WindowsFilesystem
from ai_cleaner.services.scan import Scanner
from ai_cleaner.storage.database import SCHEMA_VERSION, Database


def fingerprint(path: Path) -> tuple[int, int, str]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest()


def test_migration_is_versioned_and_repeatable(tmp_path: Path) -> None:
    database = Database(tmp_path / "state" / "state.db")
    database.migrate()
    database.migrate()
    with database.connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert {"projects", "scans", "observations", "recovery_items"} <= tables


def test_newer_database_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "newer.db"
    with sqlite3.connect(path) as connection:
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    database = Database(path)
    try:
        database.migrate()
    except RuntimeError as error:
        assert "newer than supported" in str(error)
    else:
        raise AssertionError("newer schema was accepted")


def test_version_one_database_migrates_operation_project_link(tmp_path: Path) -> None:
    path = tmp_path / "version-one.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """CREATE TABLE operation_runs (
               id TEXT PRIMARY KEY, proposal_digest TEXT NOT NULL, action TEXT NOT NULL,
               status TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT)"""
        )
        connection.execute("PRAGMA user_version = 1")

    Database(path).migrate()

    with sqlite3.connect(path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(operation_runs)")
        }
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert "project_id" in columns


def test_scan_is_read_only_and_excludes_protected_trees(tmp_path: Path) -> None:
    root = tmp_path / "selected root"
    root.mkdir()
    ordinary = root / "notes ünicode.txt"
    ordinary.write_text("keep", encoding="utf-8")
    cache = root / "cache"
    cache.mkdir()
    cached = cache / "item.pyc"
    cached.write_bytes(b"cache")
    git_file = root / ".git" / "config"
    git_file.parent.mkdir()
    git_file.write_text("secret-ish", encoding="utf-8")
    before = {path: fingerprint(path) for path in (ordinary, cached, git_file)}

    result = Scanner(WindowsFilesystem()).scan(root)

    assert result.complete
    assert [item.relative_path for item in result.observations] == [
        "cache\\item.pyc",
        "notes ünicode.txt",
    ]
    assert any(issue.code == "excluded-directory" for issue in result.issues)
    assert before == {path: fingerprint(path) for path in (ordinary, cached, git_file)}


def test_scan_cancellation_and_limit_are_explicit(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    for index in range(10):
        (root / f"{index}.tmp").write_text(str(index), encoding="utf-8")
    cancel = threading.Event()

    def progress(visited: int) -> None:
        if visited == 2:
            cancel.set()

    cancelled = Scanner(WindowsFilesystem()).scan(root, cancel=cancel, progress=progress)
    limited = Scanner(WindowsFilesystem()).scan(root, entry_limit=3)

    assert cancelled.status is ScanStatus.CANCELLED
    assert not cancelled.complete
    assert limited.status is ScanStatus.LIMIT_REACHED
    assert not limited.complete
    assert len(limited.observations) == 3
