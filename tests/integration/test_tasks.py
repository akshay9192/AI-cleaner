from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_cleaner.cli import main
from ai_cleaner.platform.windows_fs import BoundaryError, WindowsFilesystem
from ai_cleaner.services.scan import Scanner
from ai_cleaner.services.tasks import TaskConflictError, TaskService
from ai_cleaner.storage.database import Database


@pytest.fixture
def service(tmp_path: Path) -> TaskService:
    database = Database(tmp_path / "state" / "state.db")
    database.migrate()
    filesystem = WindowsFilesystem()
    return TaskService(database, filesystem, Scanner(filesystem))


def test_task_diff_is_honest_and_preexisting_changes_are_distinct(
    service: TaskService, tmp_path: Path
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    modified = root / "existing.txt"
    missing = root / "removed.txt"
    modified.write_text("before", encoding="utf-8")
    missing.write_text("remove later", encoding="utf-8")
    task_id = service.start(root, "fixture")
    modified.write_text("after with a different size", encoding="utf-8")
    missing.unlink()
    (root / "new scratch.aux").write_text("new", encoding="utf-8")

    result = service.finish(task_id)

    assert result.added == ("new scratch.aux",)
    assert result.modified == ("existing.txt",)
    assert result.missing == ("removed.txt",)
    assert result.status == "finished"


def test_active_task_blocks_cleanup_and_registration_stays_scoped(
    service: TaskService, tmp_path: Path
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    task_id = service.start(root, "fixture")
    with pytest.raises(TaskConflictError, match="cannot be proposed"):
        service.require_finished(task_id)
    with pytest.raises(BoundaryError):
        service.register(task_id, "..\\escape.tmp", "scratch")
    service.register(task_id, "scratch\\preview.png", "scratch")
    service.register(task_id, "final\\report.pdf", "deliverable")
    assert service.database.task_declarations(task_id) == {
        "scratch\\preview.png": "scratch",
        "final\\report.pdf": "deliverable",
    }


def test_only_one_active_task_per_root(service: TaskService, tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    service.start(root, "first")
    with pytest.raises(TaskConflictError, match="one active task"):
        service.start(root, "second")


def test_cli_task_start_register_finish_journey(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    root = tmp_path / "project"
    state = tmp_path / "state"
    root.mkdir()
    (root / "existing.txt").write_text("keep", encoding="utf-8")
    assert main(
        [
            "task",
            "start",
            "--root",
            str(root),
            "--label",
            "fixture",
            "--state-dir",
            str(state),
        ]
    ) == 0
    task_id = json.loads(capsys.readouterr().out)["task_id"]
    assert main(
        [
            "task",
            "register",
            "--task",
            task_id,
            "--path",
            "scratch\\preview.png",
            "--role",
            "scratch",
            "--state-dir",
            str(state),
        ]
    ) == 0
    capsys.readouterr()
    (root / "new.aux").write_text("observed", encoding="utf-8")
    assert main(
        ["task", "finish", "--task", task_id, "--state-dir", str(state)]
    ) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["added"] == ["new.aux"]
