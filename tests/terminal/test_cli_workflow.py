from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from ai_cleaner.cli import EXIT_CANCELLED, EXIT_REVIEW_REQUIRED, main, run
from ai_cleaner.domain.actions import RecoveryActionPlan
from ai_cleaner.domain.proposals import Proposal
from ai_cleaner.storage.database import Database
from ai_cleaner.terminal import CleanupDecision, RecoveryDecision


@dataclass
class ScriptedReview:
    cleanup: CleanupDecision | None = None
    confirm: bool = True

    @property
    def interactive(self) -> bool:
        return True

    def choose_cleanup(self, proposal: Proposal) -> CleanupDecision:
        if self.cleanup is not None:
            return self.cleanup
        return CleanupDecision(
            frozenset(item.relative_path for item in proposal.items), frozenset()
        )

    def choose_recovery(self, plan: RecoveryActionPlan) -> RecoveryDecision:
        return RecoveryDecision(frozenset(item.recovery_id for item in plan.items))

    def confirm_exact(self, action: str, digest: str, summary: tuple[str, ...]) -> bool:
        assert action in {"MOVE", "RESTORE", "PURGE"}
        assert digest
        assert summary
        return self.confirm


@pytest.fixture(autouse=True)
def permit_managed_fixture_ancestors(monkeypatch: pytest.MonkeyPatch) -> None:
    # The managed runner denies opening the user-profile ancestor. Native ancestor-chain behavior
    # remains covered by the Windows suite; terminal orchestration uses disposable descendants.
    monkeypatch.setattr(
        "ai_cleaner.platform.windows_fs.WindowsFilesystem._reject_reparse_chain",
        lambda self, path: None,
    )
    monkeypatch.setattr("ai_cleaner.popup.PopupInteraction._probe", lambda self: False)


def _proposal_id(output: str) -> str:
    match = re.search(r"ai_cleaner\.py review --proposal ([0-9a-f-]+)", output)
    assert match is not None
    return match.group(1)


def _json_line(output: str) -> dict[str, object]:
    return json.loads(next(line for line in output.splitlines() if line.startswith("{")))


def _tracked_proposal(
    root: Path, state: Path, paths: dict[str, bytes], capsys: pytest.CaptureFixture[str]
) -> tuple[str, str]:
    root.mkdir()
    assert (
        main(["start", "--root", str(root), "--label", "fixture", "--state-dir", str(state)])
        == 0
    )
    task_id = str(_json_line(capsys.readouterr().out)["task_id"])
    for relative, content in paths.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        assert main(
            [
                "register-temp",
                "--task",
                task_id,
                "--path",
                relative,
                "--state-dir",
                str(state),
            ]
        ) == 0
        capsys.readouterr()
    assert main(["complete", "--task", task_id, "--state-dir", str(state)]) == 6
    return task_id, _proposal_id(capsys.readouterr().out)


def test_start_protect_complete_noninteractive_then_review_and_restore(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "project"
    state = tmp_path / "state"
    root.mkdir()
    (root / "existing.txt").write_text("input", encoding="utf-8")
    missing = root / "removed-during-task.txt"
    missing.write_text("baseline", encoding="utf-8")

    assert (
        main(["start", "--root", str(root), "--label", "feature", "--state-dir", str(state)])
        == 0
    )
    task_id = str(_json_line(capsys.readouterr().out)["task_id"])
    assert main(
        [
            "protect",
            "--task",
            task_id,
            "--path",
            "final.zip",
            "--state-dir",
            str(state),
        ]
    ) == 0
    capsys.readouterr()
    (root / "final.zip").write_bytes(b"deliverable")
    scratch = root / "scratch.aux"
    scratch.write_bytes(b"intermediate")
    assert main(
        [
            "register-temp",
            "--task",
            task_id,
            "--path",
            "scratch.aux",
            "--state-dir",
            str(state),
        ]
    ) == 0
    capsys.readouterr()
    (root / "existing.txt").write_text("updated input", encoding="utf-8")
    missing.unlink()

    code = main(["complete", "--task", task_id, "--state-dir", str(state)])
    pending_output = capsys.readouterr().out
    assert code == EXIT_REVIEW_REQUIRED
    assert scratch.exists()
    assert "observed during the task" in pending_output
    assert "[modified] existing.txt" in pending_output
    assert "[missing] removed-during-task.txt" in pending_output
    proposal_id = _proposal_id(pending_output)

    assert run(
        ["review", "--proposal", proposal_id, "--state-dir", str(state)],
        interaction=ScriptedReview(),
    ) == 0
    review_output = capsys.readouterr().out
    result = _json_line(review_output)
    run_id = str(result["run_id"])
    assert not scratch.exists()
    assert (root / "final.zip").read_bytes() == b"deliverable"
    assert result["quarantined_bytes"] == len(b"intermediate")
    assert result["reclaimed_bytes"] is None
    database = Database(state / "state.db")
    with database.connect() as connection:
        run_row = connection.execute(
            "SELECT proposal_id, task_id, approved_at FROM operation_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
    assert run_row is not None
    assert run_row["proposal_id"] == proposal_id
    assert run_row["task_id"] == task_id
    assert run_row["approved_at"]

    assert run(
        ["restore", "--run", run_id, "--state-dir", str(state)],
        interaction=ScriptedReview(),
    ) == 0
    capsys.readouterr()
    assert scratch.read_bytes() == b"intermediate"


def test_default_keep_cancel_protect_and_noninteractive_review_are_safe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "project"
    state = tmp_path / "state"
    candidate = root / "preview.tmp"
    _task_id, proposal_id = _tracked_proposal(
        root, state, {"preview.tmp": b"cache"}, capsys
    )
    assert main(["review", "--proposal", proposal_id, "--state-dir", str(state)]) == 6
    assert candidate.exists()
    capsys.readouterr()

    assert run(
        ["review", "--proposal", proposal_id, "--state-dir", str(state)],
        interaction=ScriptedReview(
            cleanup=CleanupDecision(frozenset(), frozenset(), cancelled=True)
        ),
    ) == EXIT_CANCELLED
    assert candidate.exists()
    cancelled_output = capsys.readouterr().out
    assert f"review --proposal {proposal_id}" in cancelled_output

    decision = CleanupDecision(frozenset(), frozenset({"preview.tmp"}))
    assert run(
        ["review", "--proposal", proposal_id, "--state-dir", str(state)],
        interaction=ScriptedReview(cleanup=decision),
    ) == EXIT_CANCELLED
    assert candidate.exists()
    database = Database(state / "state.db")
    project = database.project_by_root(root)
    assert project is not None
    assert "preview.tmp".casefold() in database.protections(str(project["id"]))


def test_modified_registered_and_unregistered_files_are_retained(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "project"
    state = tmp_path / "state"
    root.mkdir()
    assert (
        main(["start", "--root", str(root), "--label", "fixture", "--state-dir", str(state)])
        == 0
    )
    task_id = str(_json_line(capsys.readouterr().out)["task_id"])
    registered = root / "preview.tmp"
    registered.write_bytes(b"registered")
    assert main(
        [
            "register-temp",
            "--task",
            task_id,
            "--path",
            "preview.tmp",
            "--state-dir",
            str(state),
        ]
    ) == 0
    capsys.readouterr()
    registered.write_bytes(b"modified")
    unregistered = root / "other.tmp"
    unregistered.write_bytes(b"unknown")

    assert main(["complete", "--task", task_id, "--state-dir", str(state)]) == 0
    output = capsys.readouterr().out
    assert "re-register before cleanup" in output
    assert "Not explicitly registered" in output
    assert registered.read_bytes() == b"modified"
    assert unregistered.read_bytes() == b"unknown"


def test_registered_temp_can_be_protected_before_completion(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "project"
    state = tmp_path / "state"
    root.mkdir()
    assert (
        main(["start", "--root", str(root), "--label", "fixture", "--state-dir", str(state)])
        == 0
    )
    task_id = str(_json_line(capsys.readouterr().out)["task_id"])
    output = root / "output.tmp"
    output.write_bytes(b"keep")
    assert main(
        ["register-temp", "--task", task_id, "--path", "output.tmp", "--state-dir", str(state)]
    ) == 0
    capsys.readouterr()
    assert main(
        ["protect", "--task", task_id, "--path", "output.tmp", "--state-dir", str(state)]
    ) == 0
    capsys.readouterr()

    assert main(["complete", "--task", task_id, "--state-dir", str(state)]) == 0
    assert output.read_bytes() == b"keep"
    assert "Pinned by the user" in capsys.readouterr().out


def test_complete_without_tracking_uses_conservative_existing_clutter_preview(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "project"
    state = tmp_path / "state"
    cache = root / "__pycache__"
    cache.mkdir(parents=True)
    candidate = cache / "module.pyc"
    candidate.write_bytes(b"cache")

    assert main(["complete", "--root", str(root), "--state-dir", str(state)]) == 0
    output = capsys.readouterr().out
    assert "historical ownership cannot be established" in output
    assert "No eligible cleanup candidates" in output
    assert candidate.read_bytes() == b"cache"


def test_separate_purge_review_removes_only_recovery_payload(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "project"
    state = tmp_path / "state"
    candidate = root / "preview.tmp"
    _task_id, proposal_id = _tracked_proposal(
        root, state, {"preview.tmp": b"cache"}, capsys
    )
    assert run(
        ["review", "--proposal", proposal_id, "--state-dir", str(state)],
        interaction=ScriptedReview(),
    ) == 0
    quarantine = _json_line(capsys.readouterr().out)
    run_id = str(quarantine["run_id"])
    assert not candidate.exists()

    assert main(["purge", "--run", run_id, "--state-dir", str(state)]) == 6
    assert "no payload was permanently removed" in capsys.readouterr().out
    assert run(
        ["purge", "--run", run_id, "--state-dir", str(state)],
        interaction=ScriptedReview(),
    ) == 0
    purge = _json_line(capsys.readouterr().out)
    assert purge["logical_bytes_removed"] == len(b"cache")
    assert purge["reclaimed_bytes"] is None


def test_stale_multi_item_proposal_moves_nothing_and_completed_proposal_cannot_replay(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "project"
    state = tmp_path / "state"
    first = root / "first.tmp"
    second = root / "second.tmp"
    _task_id, proposal_id = _tracked_proposal(
        root, state, {"first.tmp": b"first", "second.tmp": b"second"}, capsys
    )

    second.write_bytes(b"SECOND")
    assert run(
        ["review", "--proposal", proposal_id, "--state-dir", str(state)],
        interaction=ScriptedReview(),
    ) == 1
    capsys.readouterr()
    assert first.read_bytes() == b"first"
    assert second.read_bytes() == b"SECOND"

    fresh_root = tmp_path / "fresh-project"
    fresh_state = tmp_path / "fresh-state"
    _fresh_task, fresh = _tracked_proposal(
        fresh_root, fresh_state, {"fresh.tmp": b"fresh"}, capsys
    )
    assert run(
        ["review", "--proposal", fresh, "--state-dir", str(fresh_state)],
        interaction=ScriptedReview(),
    ) == 0
    capsys.readouterr()
    assert run(
        ["review", "--proposal", fresh, "--state-dir", str(fresh_state)],
        interaction=ScriptedReview(),
    ) == 5
