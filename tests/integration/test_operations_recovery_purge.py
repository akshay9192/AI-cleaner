from __future__ import annotations

import json
import threading
from dataclasses import replace
from pathlib import Path

import pytest

from ai_cleaner.cli import main
from ai_cleaner.domain.approval import ApprovalBroker, ApprovalError
from ai_cleaner.domain.models import Category, ClassifiedFile, FileObservation
from ai_cleaner.platform.windows_fs import WindowsFilesystem
from ai_cleaner.services.operations import (
    InjectedInterruption,
    OperationConflictError,
    OperationLock,
    QuarantineService,
)
from ai_cleaner.services.proposals import ProposalService
from ai_cleaner.services.purge import PurgeService
from ai_cleaner.services.recovery import RecoveryService
from ai_cleaner.storage.database import Database


class FixtureApp:
    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "project"
        self.recovery = tmp_path / "recovery"
        self.state = tmp_path / "state"
        self.root.mkdir()
        self.recovery.mkdir()
        self.state.mkdir()
        self.filesystem = WindowsFilesystem()
        identity = self.filesystem.validate_project_root(self.root)
        self.database = Database(self.state / "state.db")
        self.database.migrate()
        self.project_id = self.database.ensure_project(
            root=self.root,
            resolved_root=identity.final_path,
            volume_serial=identity.volume_serial,
            created_at="2026-10-17T00:00:00+00:00",
            recovery_root=self.recovery,
        )
        self.approvals = ApprovalBroker()
        self.lock_path = self.state / "locks" / "operations.lock"

    def proposal(self, files: dict[str, bytes]):
        selected: list[ClassifiedFile] = []
        for name, content in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            selected.append(
                ClassifiedFile(
                    FileObservation(name, len(content), 0, 0, 0, None, None),
                    Category.SUGGESTED_INTERMEDIATE,
                    "fixture",
                    "Recognized fixture intermediate",
                    "test declaration",
                    True,
                )
            )
        return ProposalService(self.database, self.filesystem).prepare(
            project_id=self.project_id,
            root=self.root,
            recovery_root=self.recovery,
            selected=selected,
        )

    def approve(self, digest: str, action: str):
        return self.approvals._grant_after_human_review(
            proposal_digest=digest, reviewed_digest=digest, action=action
        )

    def quarantine(self) -> QuarantineService:
        return QuarantineService(
            self.database, self.filesystem, self.approvals, self.lock_path
        )

    def recovery_service(self) -> RecoveryService:
        return RecoveryService(
            self.database, self.filesystem, self.approvals, self.lock_path
        )

    def purge_service(self) -> PurgeService:
        return PurgeService(self.database, self.filesystem, self.approvals, self.lock_path)


def test_no_approval_and_changed_file_leave_user_file_unchanged(tmp_path: Path) -> None:
    app = FixtureApp(tmp_path)
    proposal = app.proposal({"cache.aux": b"AAAA"})
    with pytest.raises(ApprovalError):
        app.quarantine().execute(proposal, {"approved": True})
    assert (app.root / "cache.aux").read_bytes() == b"AAAA"

    (app.root / "cache.aux").write_bytes(b"BBBB")
    with pytest.raises(RuntimeError, match="changed after review"):
        app.quarantine().execute(
            proposal, app.approve(proposal.items_digest, "quarantine")
        )
    assert (app.root / "cache.aux").read_bytes() == b"BBBB"


def test_approval_is_bound_to_project_and_root_metadata(tmp_path: Path) -> None:
    app = FixtureApp(tmp_path)
    proposal = app.proposal({"bound.aux": b"bound"})
    altered = replace(proposal, project_id="another-project")

    with pytest.raises(RuntimeError, match="operations changed"):
        app.quarantine().execute(
            altered, app.approve(proposal.items_digest, "quarantine")
        )

    assert (app.root / "bound.aux").read_bytes() == b"bound"


def test_exact_approved_files_move_and_report_quarantine_not_reclamation(
    tmp_path: Path,
) -> None:
    app = FixtureApp(tmp_path)
    proposal = app.proposal({"one.aux": b"one"})
    unselected = app.root / "keep.aux"
    unselected.write_bytes(b"keep")
    result = app.quarantine().execute(
        proposal, app.approve(proposal.items_digest, "quarantine")
    )
    assert result.status == "complete"
    assert result.quarantined_bytes == 3
    assert result.reclaimed_bytes is None
    assert not (app.root / "one.aux").exists()
    assert unselected.read_bytes() == b"keep"
    rows = app.database.recovery_items(app.project_id)
    assert len(rows) == 1
    assert Path(str(rows[0]["payload_path"])).read_bytes() == b"one"


def test_space_unicode_and_shell_metacharacters_are_literal_path_data(
    tmp_path: Path,
) -> None:
    app = FixtureApp(tmp_path)
    relative = "nested space\\π;$([literal])&file.aux"
    proposal = app.proposal({relative: b"special"})

    moved = app.quarantine().execute(
        proposal, app.approve(proposal.items_digest, "quarantine")
    )
    recovery_id = str(app.database.recovery_items(app.project_id)[0]["id"])
    restore = app.recovery_service().prepare_restore([recovery_id])
    restored = app.recovery_service().restore(
        restore, app.approve(restore.digest, "restore")
    )

    assert moved.status == "complete"
    assert restored.status == "complete"
    assert (app.root / relative).read_bytes() == b"special"


def test_locked_file_is_skipped_and_partial_result_is_truthful(tmp_path: Path) -> None:
    app = FixtureApp(tmp_path)
    proposal = app.proposal({"a.aux": b"a", "b.aux": b"b"})
    locked = app.root / "b.aux"
    with app.filesystem.open_exclusive_file(locked), pytest.raises(OSError):
        app.quarantine().execute(
            proposal, app.approve(proposal.items_digest, "quarantine")
        )
    assert (app.root / "a.aux").read_bytes() == b"a"
    assert locked.read_bytes() == b"b"
    assert app.database.recovery_items(app.project_id) == []


def test_cancellation_stops_subsequent_items_but_preserves_completed_record(
    tmp_path: Path,
) -> None:
    app = FixtureApp(tmp_path)
    proposal = app.proposal({"a.aux": b"a", "b.aux": b"b"})
    cancel = threading.Event()

    def stop_after_first(stage, item) -> None:  # type: ignore[no-untyped-def]
        if stage == "after-outcome" and item.relative_path == "a.aux":
            cancel.set()

    result = app.quarantine().execute(
        proposal,
        app.approve(proposal.items_digest, "quarantine"),
        cancel=cancel,
        failure_hook=stop_after_first,
    )
    assert [item.outcome for item in result.outcomes] == ["moved", "cancelled"]
    assert len(app.database.recovery_items(app.project_id)) == 1
    assert (app.root / "b.aux").exists()


def test_interrupted_move_is_reconciled_without_resuming_work(tmp_path: Path) -> None:
    app = FixtureApp(tmp_path)
    proposal = app.proposal({"crash.aux": b"recover me"})

    def crash(stage, item) -> None:  # type: ignore[no-untyped-def]
        if stage == "after-move":
            raise InjectedInterruption(item.relative_path)

    with pytest.raises(InjectedInterruption):
        app.quarantine().execute(
            proposal,
            app.approve(proposal.items_digest, "quarantine"),
            failure_hook=crash,
        )
    assert not (app.root / "crash.aux").exists()
    assert app.database.recovery_items(app.project_id) == []

    result = app.recovery_service().reconcile_interrupted()

    assert result[0].outcome == "reconciled"
    assert len(app.database.recovery_items(app.project_id)) == 1


@pytest.mark.parametrize(
    ("stage", "moved"),
    [
        ("before-intent", False),
        ("after-intent", False),
        ("after-move", True),
        ("after-recovery-record", True),
        ("after-outcome", True),
    ],
)
def test_each_quarantine_interruption_boundary_preserves_a_reviewable_state(
    tmp_path: Path, stage: str, moved: bool
) -> None:
    app = FixtureApp(tmp_path)
    proposal = app.proposal({"boundary.aux": b"boundary"})

    def crash(current: str, _item: object) -> None:
        if current == stage:
            raise InjectedInterruption(stage)

    with pytest.raises(InjectedInterruption):
        app.quarantine().execute(
            proposal,
            app.approve(proposal.items_digest, "quarantine"),
            failure_hook=crash,
        )

    source = app.root / "boundary.aux"
    payload = Path(proposal.items[0].recovery_path)
    assert source.exists() is not moved
    assert payload.exists() is moved
    app.recovery_service().reconcile_interrupted()
    if moved:
        assert len(app.database.recovery_items(app.project_id)) == 1
    else:
        assert source.read_bytes() == b"boundary"


def test_operation_lock_rejects_concurrent_operation(tmp_path: Path) -> None:
    app = FixtureApp(tmp_path)
    with OperationLock(app.filesystem, app.lock_path), pytest.raises(
        OperationConflictError
    ), OperationLock(app.filesystem, app.lock_path):
        raise AssertionError("unreachable")


def test_restore_is_byte_exact_and_collision_requires_reviewed_alternative(
    tmp_path: Path,
) -> None:
    app = FixtureApp(tmp_path)
    original = b"restore bytes"
    proposal = app.proposal({"folder\\file.aux": original})
    app.quarantine().execute(
        proposal, app.approve(proposal.items_digest, "quarantine")
    )
    recovery_id = str(app.database.recovery_items(app.project_id)[0]["id"])
    occupied = app.root / "folder" / "file.aux"
    occupied.write_bytes(b"newer")
    with pytest.raises(FileExistsError):
        app.recovery_service().prepare_restore([recovery_id])
    assert occupied.read_bytes() == b"newer"

    alternate = app.root / "folder" / "file.restored.aux"
    plan = app.recovery_service().prepare_restore(
        [recovery_id], alternatives={recovery_id: alternate}
    )
    result = app.recovery_service().restore(plan, app.approve(plan.digest, "restore"))
    assert result.status == "complete"
    assert alternate.read_bytes() == original
    assert occupied.read_bytes() == b"newer"


def test_interrupted_restore_is_reconciled_without_repeating_the_move(
    tmp_path: Path,
) -> None:
    app = FixtureApp(tmp_path)
    proposal = app.proposal({"restore-crash.aux": b"restored after crash"})
    app.quarantine().execute(
        proposal, app.approve(proposal.items_digest, "quarantine")
    )
    recovery_id = str(app.database.recovery_items(app.project_id)[0]["id"])
    plan = app.recovery_service().prepare_restore([recovery_id])

    def crash(stage: str, _item: object) -> None:
        if stage == "after-move":
            raise InjectedInterruption(stage)

    with pytest.raises(InjectedInterruption):
        app.recovery_service().restore(
            plan,
            app.approve(plan.digest, "restore"),
            failure_hook=crash,
        )

    destination = app.root / "restore-crash.aux"
    assert destination.read_bytes() == b"restored after crash"
    assert app.database.recovery_item(recovery_id)["state"] == "quarantined"
    result = app.recovery_service().reconcile_interrupted()
    assert result[0].outcome == "reconciled"
    assert app.database.recovery_item(recovery_id)["state"] == "restored"


def test_purge_requires_separate_approval_and_detects_altered_payload(tmp_path: Path) -> None:
    app = FixtureApp(tmp_path)
    proposal = app.proposal({"purge.aux": b"payload"})
    app.quarantine().execute(
        proposal, app.approve(proposal.items_digest, "quarantine")
    )
    recovery = app.database.recovery_items(app.project_id)[0]
    recovery_id = str(recovery["id"])
    plan = app.purge_service().prepare([recovery_id])
    with pytest.raises(ApprovalError):
        app.purge_service().execute(plan, {"approved": True})
    payload = Path(str(recovery["payload_path"]))
    payload.write_bytes(b"altered")
    with pytest.raises(RuntimeError, match="content changed after review"):
        app.purge_service().execute(plan, app.approve(plan.digest, "purge"))
    assert payload.read_bytes() == b"altered"


def test_interrupted_purge_reconciles_and_retention_never_deletes(tmp_path: Path) -> None:
    app = FixtureApp(tmp_path)
    proposal = app.proposal({"old.aux": b"old"})
    app.quarantine().execute(
        proposal, app.approve(proposal.items_digest, "quarantine")
    )
    recovery = app.database.recovery_items(app.project_id)[0]
    recovery_id = str(recovery["id"])
    payload = Path(str(recovery["payload_path"]))
    with app.database.transaction(immediate=True) as connection:
        connection.execute(
            "UPDATE recovery_items SET quarantined_at = '2000-01-01T00:00:00+00:00' WHERE id = ?",
            (recovery_id,),
        )
    assert app.purge_service().retention_reminders(days=30) == [recovery_id]
    assert payload.exists()

    plan = app.purge_service().prepare([recovery_id])
    with pytest.raises(InjectedInterruption):
        app.purge_service().execute(
            plan, app.approve(plan.digest, "purge"), failure_stage="after-delete"
        )
    assert not payload.exists()
    assert app.purge_service().reconcile_interrupted() == 1
    assert app.database.recovery_item(recovery_id)["state"] == "purged"


def test_history_cli_reports_operation_and_recovery_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app = FixtureApp(tmp_path)
    proposal = app.proposal({"history.aux": b"history"})
    app.quarantine().execute(
        proposal, app.approve(proposal.items_digest, "quarantine")
    )

    code = main(
        [
            "history",
            "--root",
            str(app.root),
            "--json",
            "--state-dir",
            str(app.state),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["operations"][0]["action"] == "quarantine"
    assert payload["operations"][0]["items"][0]["outcome"] == "moved"
    assert payload["recovery_items"][0]["state"] == "quarantined"
