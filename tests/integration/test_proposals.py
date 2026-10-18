from __future__ import annotations

from pathlib import Path

import pytest

from ai_cleaner.cli import main
from ai_cleaner.domain.models import Category, ClassifiedFile, FileObservation
from ai_cleaner.platform.windows_fs import FileChangedError, WindowsFilesystem
from ai_cleaner.services.proposals import ProposalError, ProposalService
from ai_cleaner.storage.database import Database


def candidate(path: str, size: int) -> ClassifiedFile:
    observation = FileObservation(path, size, 0, 0, 0, None, None)
    return ClassifiedFile(
        observation,
        Category.SUGGESTED_INTERMEDIATE,
        "recognized-cache",
        "Recognized disposable intermediate",
        "deterministic rule",
        True,
    )


def project_setup(tmp_path: Path) -> tuple[Path, Path, Database, ProposalService, str]:
    root = tmp_path / "project"
    recovery = tmp_path / "recovery"
    root.mkdir()
    recovery.mkdir()
    filesystem = WindowsFilesystem()
    identity = filesystem.validate_project_root(root)
    database = Database(tmp_path / "state" / "state.db")
    database.migrate()
    project_id = database.ensure_project(
        root=root,
        resolved_root=identity.final_path,
        volume_serial=identity.volume_serial,
        created_at="2026-10-17T00:00:00+00:00",
        recovery_root=recovery,
    )
    return root, recovery, database, ProposalService(database, filesystem), project_id


def test_proposal_freezes_exact_selection_and_paths(tmp_path: Path) -> None:
    root, recovery, _, service, project_id = project_setup(tmp_path)
    selected = root / "cache" / "sp ace-例.aux"
    excluded = root / "cache" / "exclude.aux"
    selected.parent.mkdir()
    selected.write_bytes(b"selected")
    excluded.write_bytes(b"excluded")

    proposal = service.prepare(
        project_id=project_id,
        root=root,
        recovery_root=recovery,
        selected=[candidate("cache\\sp ace-例.aux", len(b"selected"))],
    )

    assert [item.relative_path for item in proposal.items] == ["cache\\sp ace-例.aux"]
    assert proposal.logical_bytes == len(b"selected")
    assert "no disk space is reclaimed" in proposal.to_dict()["recovery_behavior"]
    assert selected.exists() and excluded.exists()
    service.revalidate(proposal)


def test_same_size_content_change_invalidates_proposal(tmp_path: Path) -> None:
    root, recovery, _, service, project_id = project_setup(tmp_path)
    selected = root / "cache.aux"
    selected.write_bytes(b"AAAA")
    proposal = service.prepare(
        project_id=project_id,
        root=root,
        recovery_root=recovery,
        selected=[candidate("cache.aux", 4)],
    )
    selected.write_bytes(b"BBBB")
    with pytest.raises(FileChangedError):
        service.revalidate(proposal)
    assert selected.read_bytes() == b"BBBB"


def test_same_name_size_and_content_replacement_invalidates_identity(tmp_path: Path) -> None:
    root, recovery, _, service, project_id = project_setup(tmp_path)
    selected = root / "cache.aux"
    selected.write_bytes(b"AAAA")
    proposal = service.prepare(
        project_id=project_id,
        root=root,
        recovery_root=recovery,
        selected=[candidate("cache.aux", 4)],
    )
    selected.unlink()
    selected.write_bytes(b"AAAA")
    with pytest.raises(FileChangedError):
        service.revalidate(proposal)


def test_selection_and_policy_are_part_of_digest(tmp_path: Path) -> None:
    root, recovery, _, service, project_id = project_setup(tmp_path)
    (root / "one.aux").write_bytes(b"one")
    (root / "two.aux").write_bytes(b"two")
    one = service.prepare(
        project_id=project_id,
        root=root,
        recovery_root=recovery,
        selected=[candidate("one.aux", 3)],
    )
    both = service.prepare(
        project_id=project_id,
        root=root,
        recovery_root=recovery,
        selected=[candidate("one.aux", 3), candidate("two.aux", 3)],
    )
    assert one.items_digest != both.items_digest
    with pytest.raises(FileChangedError, match="policy changed"):
        service.revalidate(one, policy_version="future")


def test_protected_or_unknown_item_cannot_enter_proposal(tmp_path: Path) -> None:
    root, recovery, _, service, project_id = project_setup(tmp_path)
    selected = root / "valuable.log"
    selected.write_text("keep", encoding="utf-8")
    observation = FileObservation("valuable.log", 4, 0, 0, 0, None, None)
    unknown = ClassifiedFile(
        observation,
        Category.UNKNOWN,
        "insufficient-evidence",
        "Unknown",
        "observed only",
        False,
    )
    with pytest.raises(ProposalError, match="protected or uncertain"):
        service.prepare(
            project_id=project_id,
            root=root,
            recovery_root=recovery,
            selected=[unknown],
        )
    assert selected.exists()


def test_active_task_blocks_even_unscoped_cleanup_proposal(tmp_path: Path) -> None:
    root, recovery, database, service, project_id = project_setup(tmp_path)
    target = root / "blocked.aux"
    target.write_bytes(b"blocked")
    with database.transaction(immediate=True) as connection:
        connection.execute(
            "INSERT INTO scans VALUES ('baseline', ?, ?, 'complete', 0, 0)",
            (project_id, "2026-10-17T00:00:00+00:00"),
        )
        connection.execute(
            """INSERT INTO tasks
               VALUES ('active-task', ?, 'work', 'active', 'baseline', NULL, ?, NULL)""",
            (project_id, "2026-10-17T00:00:00+00:00"),
        )

    with pytest.raises(ProposalError, match="active or interrupted"):
        service.prepare(
            project_id=project_id,
            root=root,
            recovery_root=recovery,
            selected=[candidate("blocked.aux", 7)],
        )

    assert target.read_bytes() == b"blocked"


def test_cli_propose_without_task_baseline_retains_existing_clutter(
    tmp_path: Path, capsys
) -> None:  # type: ignore[no-untyped-def]
    root = tmp_path / "project"
    state = tmp_path / "state"
    cache = root / "__pycache__"
    cache.mkdir(parents=True)
    payload = cache / "module.pyc"
    payload.write_bytes(b"bytecode")

    code = main(
        [
            "propose",
            "--root",
            str(root),
            "--state-dir",
            str(state),
            "--json",
        ]
    )
    output = capsys.readouterr().out
    assert code == 0
    assert output == ""
    assert payload.read_bytes() == b"bytecode"
