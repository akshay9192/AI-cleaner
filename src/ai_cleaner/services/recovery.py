from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from ai_cleaner.domain.actions import RecoveryActionItem, RecoveryActionPlan
from ai_cleaner.domain.approval import ApprovalBroker
from ai_cleaner.platform.windows_fs import FileIdentity, WindowsFilesystem
from ai_cleaner.services.operations import ItemOutcome, OperationLock, OperationResult
from ai_cleaner.services.tasks import utc_now
from ai_cleaner.storage.database import Database


class RecoveryError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReconciliationOutcome:
    operation_item_id: str
    outcome: str
    message: str


class RecoveryService:
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

    def reconcile_interrupted(self) -> tuple[ReconciliationOutcome, ...]:
        results: list[ReconciliationOutcome] = []
        with OperationLock(self.filesystem, self.lock_path):
            for row in self.database.pending_operation_items():
                if row["action"] != "quarantine":
                    continue
                source = Path(str(row["source"]))
                destination = Path(str(row["destination"]))
                if source.exists() and not destination.exists():
                    self.database.set_operation_outcome(
                        str(row["id"]), "unresolved", "intent persisted; source was not moved"
                    )
                    results.append(
                        ReconciliationOutcome(
                            str(row["id"]), "unresolved", "source remains; no action resumed"
                        )
                    )
                    self.database.set_run_status(str(row["run_id"]), "interrupted", utc_now())
                    continue
                if not source.exists() and destination.is_file():
                    try:
                        identity = self.filesystem.inspect(destination)
                        digest = self._hash(destination)
                        if (
                            identity.volume_serial != int(row["expected_volume"])
                            or identity.file_index != int(row["expected_file"])
                            or digest != row["expected_sha256"]
                        ):
                            raise RecoveryError(
                                "moved payload identity or hash does not match intent"
                            )
                        if self.database.recovery_by_operation(str(row["id"])) is None:
                            self.database.add_recovery_item(
                                recovery_id=str(uuid.uuid4()),
                                operation_item_id=str(row["id"]),
                                project_id=str(row["project_id"]),
                                original_path=str(source),
                                payload_path=str(destination),
                                volume_serial=identity.volume_serial,
                                file_index=identity.file_index,
                                size=identity.size,
                                sha256=digest,
                            )
                        self.database.set_operation_outcome(str(row["id"]), "reconciled", None)
                        results.append(
                            ReconciliationOutcome(
                                str(row["id"]), "reconciled", "moved payload recorded for review"
                            )
                        )
                    except (OSError, RuntimeError) as error:
                        self.database.set_operation_outcome(
                            str(row["id"]), "unresolved", str(error)
                        )
                        results.append(
                            ReconciliationOutcome(str(row["id"]), "unresolved", str(error))
                        )
                else:
                    message = "source and payload are both present or both missing"
                    self.database.set_operation_outcome(str(row["id"]), "unresolved", message)
                    results.append(ReconciliationOutcome(str(row["id"]), "unresolved", message))
                self.database.set_run_status(str(row["run_id"]), "interrupted", utc_now())
        return tuple(results)

    def prepare_restore(
        self, recovery_ids: list[str], *, alternatives: dict[str, Path] | None = None
    ) -> RecoveryActionPlan:
        if not recovery_ids:
            raise RecoveryError("select at least one recovery item")
        items: list[RecoveryActionItem] = []
        project_id: str | None = None
        alternatives = alternatives or {}
        for recovery_id in recovery_ids:
            row = self.database.recovery_item(recovery_id)
            if row is None or row["state"] != "quarantined":
                raise RecoveryError(f"recovery item is unavailable: {recovery_id}")
            if project_id is None:
                project_id = str(row["project_id"])
            elif project_id != row["project_id"]:
                raise RecoveryError("one restore plan cannot span projects")
            destination = alternatives.get(recovery_id, Path(str(row["original_path"]))).absolute()
            project = self.database.project(str(row["project_id"]))
            if project is None:
                raise RecoveryError("project metadata is missing")
            root = Path(str(project["root"]))
            common = os.path.commonpath(
                [os.path.normcase(str(destination)), os.path.normcase(str(root))]
            )
            if common != os.path.normcase(str(root)):
                raise RecoveryError("restore destination is outside the project")
            if not destination.parent.is_dir():
                raise RecoveryError(
                    "restore parent is missing; choose an existing reviewed destination"
                )
            if destination.exists():
                raise FileExistsError(f"restore destination is occupied: {destination}")
            items.append(
                RecoveryActionItem(
                    recovery_id,
                    str(row["payload_path"]),
                    str(destination),
                    int(row["volume_serial"]),
                    int(row["file_index"]),
                    int(row["size"]),
                    str(row["sha256"]),
                )
            )
        assert project_id is not None
        return RecoveryActionPlan.create(project_id, "restore", tuple(items))

    def restore(self, plan: RecoveryActionPlan, approval: object) -> OperationResult:
        self.approvals.consume(approval, proposal_digest=plan.digest, action="restore")
        run_id = str(uuid.uuid4())
        outcomes: list[ItemOutcome] = []
        project = self.database.project(plan.project_id)
        if project is None or not project["recovery_root"]:
            raise RecoveryError("project recovery metadata is missing")
        recovery_root = Path(str(project["recovery_root"]))
        with OperationLock(self.filesystem, self.lock_path):
            self.database.create_operation_run(
                run_id=run_id,
                project_id=plan.project_id,
                proposal_digest=plan.digest,
                action="restore",
                started_at=utc_now(),
            )
            for item in plan.items:
                operation_id = str(uuid.uuid4())
                self.database.create_operation_item(
                    item_id=operation_id,
                    run_id=run_id,
                    source=item.source,
                    destination=item.destination,
                    expected_volume=item.volume_serial,
                    expected_file=item.file_index,
                    expected_sha256=item.sha256,
                    intent_at=utc_now(),
                )
                try:
                    destination = Path(item.destination)
                    if destination.exists():
                        raise FileExistsError("restore destination became occupied")
                    observed = self.filesystem.validate_candidate(
                        Path(item.source), recovery_root
                    )
                    expected = FileIdentity(
                        item.volume_serial,
                        item.file_index,
                        item.size,
                        observed.modified_100ns,
                        observed.attributes,
                        1,
                        observed.final_path,
                    )
                    self.filesystem.guarded_move(
                        Path(item.source),
                        destination,
                        root=recovery_root,
                        expected=expected,
                        expected_sha256=item.sha256,
                    )
                    self.database.update_recovery_state(
                        item.recovery_id, "restored", restored_path=str(destination)
                    )
                    self.database.set_operation_outcome(operation_id, "restored", None)
                    outcomes.append(ItemOutcome(item.destination, "restored", None, item.size))
                except (OSError, RuntimeError, ValueError) as error:
                    outcome = "collision" if isinstance(error, FileExistsError) else "failed"
                    self.database.set_operation_outcome(operation_id, outcome, str(error))
                    outcomes.append(ItemOutcome(item.destination, outcome, str(error), 0))
            status = "complete" if all(row.outcome == "restored" for row in outcomes) else "partial"
            self.database.set_run_status(run_id, status, utc_now())
        return OperationResult(
            run_id,
            status,
            tuple(outcomes),
            0,
            0,
            None,
        )

    def _hash(self, path: Path) -> str:
        with self.filesystem.open_exclusive_file(path) as handle:
            return self.filesystem.hash_handle(handle)
