from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from types import TracebackType
from typing import Any

from ai_cleaner.domain.approval import ApprovalBroker
from ai_cleaner.domain.proposals import Proposal, ProposalItem, digest_items
from ai_cleaner.platform.windows_fs import GENERIC_READ, WindowsFilesystem, WindowsHandle
from ai_cleaner.services.proposals import ProposalService, policy_digest
from ai_cleaner.services.tasks import utc_now
from ai_cleaner.storage.database import Database


class OperationConflictError(RuntimeError):
    pass


class InjectedInterruption(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ItemOutcome:
    relative_path: str
    outcome: str
    error: str | None
    logical_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class OperationResult:
    run_id: str
    status: str
    outcomes: tuple[ItemOutcome, ...]
    quarantined_bytes: int
    logical_bytes_removed: int = 0
    reclaimed_bytes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
            "quarantined_bytes": self.quarantined_bytes,
            "logical_bytes_removed": self.logical_bytes_removed,
            "reclaimed_bytes": self.reclaimed_bytes,
        }


class OperationLock:
    def __init__(self, filesystem: WindowsFilesystem, path: Path) -> None:
        self.filesystem = filesystem
        self.path = path
        self._handle: WindowsHandle | None = None

    def __enter__(self) -> OperationLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        try:
            self._handle = self.filesystem.open_handle(
                self.path, access=GENERIC_READ, share=0
            )
        except OSError as error:
            raise OperationConflictError("another cleanup/recovery operation is active") from error
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None


FailureHook = Callable[[str, ProposalItem], None]


class QuarantineService:
    def __init__(
        self,
        database: Database,
        filesystem: WindowsFilesystem,
        approvals: ApprovalBroker,
        lock_path: Path,
    ) -> None:
        self.database = database
        self.filesystem = filesystem
        self.approvals = approvals
        self.lock_path = lock_path

    def execute(
        self,
        proposal: Proposal,
        approval: object,
        *,
        cancel: threading.Event | None = None,
        failure_hook: FailureHook | None = None,
    ) -> OperationResult:
        self.approvals.consume(
            approval, proposal_digest=proposal.items_digest, action="quarantine"
        )
        if proposal.policy_digest != policy_digest():
            raise RuntimeError("cleanup policy changed after review")
        if proposal.items_digest != digest_items(
            proposal.policy_digest,
            proposal.items,
            project_id=proposal.project_id,
            task_id=proposal.task_id,
            root=proposal.root,
            recovery_root=proposal.recovery_root,
        ):
            raise RuntimeError("proposal operations changed after review")
        root = Path(proposal.root)
        recovery_root = Path(proposal.recovery_root)
        self.filesystem.validate_roots(root, recovery_root)
        project = self.database.project(proposal.project_id)
        if (
            project is None
            or os.path.normcase(str(root.absolute()))
            != os.path.normcase(str(project["root"]))
            or os.path.normcase(str(recovery_root.absolute()))
            != os.path.normcase(str(project["recovery_root"]))
        ):
            raise RuntimeError("proposal roots no longer match project metadata")
        if proposal.task_id:
            task = self.database.task(proposal.task_id)
            if task is None or task["status"] != "finished":
                raise RuntimeError("proposal task is no longer safely finished")
        for item in proposal.items:
            destination = Path(item.recovery_path).absolute()
            if os.path.normcase(str(destination.parent)) != os.path.normcase(
                str(recovery_root.absolute())
            ):
                raise RuntimeError("proposal recovery destination is outside recovery storage")
        run_id = str(uuid.uuid4())
        outcomes: list[ItemOutcome] = []
        with OperationLock(self.filesystem, self.lock_path):
            self.database.create_operation_run(
                run_id=run_id,
                project_id=proposal.project_id,
                proposal_digest=proposal.items_digest,
                action="quarantine",
                started_at=utc_now(),
            )
            try:
                for item in proposal.items:
                    if cancel and cancel.is_set():
                        outcomes.append(ItemOutcome(item.relative_path, "cancelled", None, 0))
                        continue
                    operation_id = str(uuid.uuid4())
                    source = root / item.relative_path
                    destination = Path(item.recovery_path)
                    self._inject(failure_hook, "before-intent", item)
                    self.database.create_operation_item(
                        item_id=operation_id,
                        run_id=run_id,
                        source=str(source),
                        destination=str(destination),
                        expected_volume=item.volume_serial,
                        expected_file=item.file_index,
                        expected_sha256=item.sha256,
                        intent_at=utc_now(),
                    )
                    self._inject(failure_hook, "after-intent", item)
                    try:
                        observed = self.filesystem.validate_candidate(
                            source, root
                        )
                        expected = ProposalService.identity(item, observed.final_path)
                        moved = self.filesystem.guarded_move(
                            source,
                            destination,
                            root=root,
                            destination_root=recovery_root,
                            expected=expected,
                            expected_sha256=item.sha256,
                        )
                        self._inject(failure_hook, "after-move", item)
                        self.database.add_recovery_item(
                            recovery_id=str(uuid.uuid4()),
                            operation_item_id=operation_id,
                            project_id=proposal.project_id,
                            original_path=str(source),
                            payload_path=str(destination),
                            volume_serial=moved.volume_serial,
                            file_index=moved.file_index,
                            size=item.size,
                            sha256=item.sha256,
                        )
                        self._inject(failure_hook, "after-recovery-record", item)
                        self.database.set_operation_outcome(operation_id, "moved", None)
                        self._inject(failure_hook, "after-outcome", item)
                        outcomes.append(ItemOutcome(item.relative_path, "moved", None, item.size))
                    except InjectedInterruption:
                        raise
                    except (OSError, RuntimeError, ValueError) as error:
                        self.database.set_operation_outcome(operation_id, "failed", str(error))
                        outcomes.append(ItemOutcome(item.relative_path, "failed", str(error), 0))
            except InjectedInterruption:
                self.database.set_run_status(run_id, "interrupted", utc_now())
                raise
            successes = sum(outcome.outcome == "moved" for outcome in outcomes)
            failures = sum(outcome.outcome == "failed" for outcome in outcomes)
            cancelled = any(outcome.outcome == "cancelled" for outcome in outcomes)
            status = "complete" if successes == len(proposal.items) else "partial"
            if failures or cancelled:
                status = "partial"
            self.database.set_run_status(run_id, status, utc_now())
        return OperationResult(
            run_id,
            status,
            tuple(outcomes),
            sum(outcome.logical_bytes for outcome in outcomes),
            0,
            None,
        )

    @staticmethod
    def _inject(hook: FailureHook | None, stage: str, item: ProposalItem) -> None:
        if hook:
            hook(stage, item)
