from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ai_cleaner.domain.actions import RecoveryActionItem, RecoveryActionPlan
from ai_cleaner.domain.approval import ApprovalBroker
from ai_cleaner.platform.windows_fs import FileIdentity, WindowsFilesystem
from ai_cleaner.services.operations import (
    InjectedInterruption,
    ItemOutcome,
    OperationLock,
    OperationResult,
)
from ai_cleaner.services.tasks import utc_now
from ai_cleaner.storage.database import Database


class PurgeService:
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

    def prepare(self, recovery_ids: list[str]) -> RecoveryActionPlan:
        if not recovery_ids:
            raise ValueError("select at least one recovery item")
        items: list[RecoveryActionItem] = []
        project_id: str | None = None
        for recovery_id in recovery_ids:
            row = self.database.recovery_item(recovery_id)
            if row is None or row["state"] != "quarantined":
                raise ValueError(f"recovery item is unavailable: {recovery_id}")
            if project_id is None:
                project_id = str(row["project_id"])
            elif project_id != row["project_id"]:
                raise ValueError("one purge plan cannot span projects")
            items.append(
                RecoveryActionItem(
                    recovery_id,
                    str(row["payload_path"]),
                    "permanent-delete",
                    int(row["volume_serial"]),
                    int(row["file_index"]),
                    int(row["size"]),
                    str(row["sha256"]),
                )
            )
        assert project_id is not None
        return RecoveryActionPlan.create(project_id, "purge", tuple(items))

    def execute(
        self,
        plan: RecoveryActionPlan,
        approval: object,
        *,
        failure_stage: str | None = None,
    ) -> OperationResult:
        self.approvals.consume(approval, proposal_digest=plan.digest, action="purge")
        project = self.database.project(plan.project_id)
        if project is None or not project["recovery_root"]:
            raise RuntimeError("project recovery metadata is missing")
        recovery_root = Path(str(project["recovery_root"]))
        run_id = str(uuid.uuid4())
        outcomes: list[ItemOutcome] = []
        with OperationLock(self.filesystem, self.lock_path):
            self.database.create_operation_run(
                run_id=run_id,
                project_id=plan.project_id,
                proposal_digest=plan.digest,
                action="purge",
                started_at=utc_now(),
            )
            try:
                for item in plan.items:
                    operation_id = str(uuid.uuid4())
                    self.database.create_operation_item(
                        item_id=operation_id,
                        run_id=run_id,
                        source=item.source,
                        destination="permanent-delete",
                        expected_volume=item.volume_serial,
                        expected_file=item.file_index,
                        expected_sha256=item.sha256,
                        intent_at=utc_now(),
                    )
                    try:
                        path = Path(item.source)
                        observed = self.filesystem.validate_candidate(path, recovery_root)
                        expected = FileIdentity(
                            item.volume_serial,
                            item.file_index,
                            item.size,
                            observed.modified_100ns,
                            observed.attributes,
                            1,
                            observed.final_path,
                        )
                        with self.filesystem.open_exclusive_file(path) as handle:
                            if self.filesystem.identity_from_handle(handle) != expected:
                                raise RuntimeError("recovery payload identity changed")
                            if self.filesystem.hash_handle(handle) != item.sha256:
                                raise RuntimeError("recovery payload content changed")
                            self.filesystem.delete_open_file(handle, expected=expected)
                        if failure_stage == "after-delete":
                            raise InjectedInterruption("injected after payload deletion")
                        self.database.update_recovery_state(item.recovery_id, "purged")
                        self.database.set_operation_outcome(operation_id, "purged", None)
                        outcomes.append(ItemOutcome(item.source, "purged", None, item.size))
                    except InjectedInterruption:
                        raise
                    except (OSError, RuntimeError, ValueError) as error:
                        self.database.set_operation_outcome(operation_id, "failed", str(error))
                        outcomes.append(ItemOutcome(item.source, "failed", str(error), 0))
            except InjectedInterruption:
                self.database.set_run_status(run_id, "interrupted", utc_now())
                raise
            status = "complete" if all(row.outcome == "purged" for row in outcomes) else "partial"
            self.database.set_run_status(run_id, status, utc_now())
        return OperationResult(
            run_id,
            status,
            tuple(outcomes),
            0,
            sum(row.logical_bytes for row in outcomes),
            None,
        )

    def reconcile_interrupted(self) -> int:
        reconciled = 0
        with OperationLock(self.filesystem, self.lock_path):
            for row in self.database.pending_operation_items():
                if row["action"] != "purge":
                    continue
                recovery = self.database.recovery_by_payload(str(row["source"]))
                if recovery is None:
                    self.database.set_operation_outcome(
                        str(row["id"]), "unresolved", "recovery metadata missing"
                    )
                elif not Path(str(row["source"])).exists():
                    self.database.update_recovery_state(str(recovery["id"]), "purged")
                    self.database.set_operation_outcome(str(row["id"]), "purged", None)
                    reconciled += 1
                else:
                    self.database.set_operation_outcome(
                        str(row["id"]), "unresolved", "payload remains; purge not resumed"
                    )
                self.database.set_run_status(str(row["run_id"]), "interrupted", utc_now())
        return reconciled

    def retention_reminders(self, *, days: int) -> list[str]:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        return [
            str(row["id"])
            for row in self.database.recovery_items()
            if row["state"] == "quarantined"
            and datetime.fromisoformat(str(row["quarantined_at"])) <= cutoff
        ]
