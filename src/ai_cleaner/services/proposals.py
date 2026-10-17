from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from ai_cleaner.domain.models import ClassifiedFile
from ai_cleaner.domain.proposals import Proposal, ProposalItem, digest_items
from ai_cleaner.platform.windows_fs import FileChangedError, FileIdentity, WindowsFilesystem
from ai_cleaner.services.classify import POLICY_VERSION
from ai_cleaner.services.tasks import utc_now
from ai_cleaner.storage.database import Database


class ProposalError(RuntimeError):
    pass


def policy_digest(version: str = POLICY_VERSION) -> str:
    return hashlib.sha256(f"ai-cleaner-policy:{version}".encode()).hexdigest()


class ProposalService:
    def __init__(self, database: Database, filesystem: WindowsFilesystem) -> None:
        self.database = database
        self.filesystem = filesystem

    def prepare(
        self,
        *,
        project_id: str,
        root: Path,
        recovery_root: Path,
        selected: list[ClassifiedFile],
        task_id: str | None = None,
        policy_version: str = POLICY_VERSION,
    ) -> Proposal:
        if not selected:
            raise ProposalError("select at least one eligible item")
        self.filesystem.validate_roots(root, recovery_root)
        unresolved = self.database.unresolved_task(project_id)
        if unresolved is not None:
            raise ProposalError(
                "active or interrupted tasks must be finished before cleanup review"
            )
        if task_id:
            task = self.database.task(task_id)
            if task is None:
                raise ProposalError(f"unknown task: {task_id}")
            if task["status"] != "finished":
                raise ProposalError("active or interrupted tasks cannot be proposed for cleanup")
        items: list[ProposalItem] = []
        seen: set[str] = set()
        proposal_id = str(uuid.uuid4())
        for classified in selected:
            observation = classified.observation
            normalized = observation.relative_path.casefold()
            if normalized in seen:
                raise ProposalError("duplicate selected path")
            seen.add(normalized)
            if not classified.selectable:
                raise ProposalError(f"item is protected or uncertain: {observation.relative_path}")
            source = root / observation.relative_path
            expected = self.filesystem.validate_candidate(source, root)
            with self.filesystem.open_exclusive_file(source) as handle:
                before = self.filesystem.identity_from_handle(handle)
                sha256 = self.filesystem.hash_handle(handle)
                after = self.filesystem.identity_from_handle(handle)
            if before != after or before != expected:
                raise FileChangedError("file changed while proposal was prepared")
            payload = recovery_root / f"{uuid.uuid4().hex}.payload"
            items.append(
                ProposalItem(
                    relative_path=observation.relative_path,
                    action="quarantine",
                    volume_serial=expected.volume_serial,
                    file_index=expected.file_index,
                    size=expected.size,
                    modified_100ns=expected.modified_100ns,
                    attributes=expected.attributes,
                    sha256=sha256,
                    explanation=classified.explanation,
                    recovery_path=str(payload),
                )
            )
        frozen = tuple(sorted(items, key=lambda item: item.relative_path.casefold()))
        policy = policy_digest(policy_version)
        absolute_root = str(root.absolute())
        absolute_recovery = str(recovery_root.absolute())
        proposal = Proposal(
            proposal_id=proposal_id,
            project_id=project_id,
            task_id=task_id,
            root=absolute_root,
            recovery_root=absolute_recovery,
            policy_digest=policy,
            items=frozen,
            items_digest=digest_items(
                policy,
                frozen,
                project_id=project_id,
                task_id=task_id,
                root=absolute_root,
                recovery_root=absolute_recovery,
            ),
            created_at=utc_now(),
        )
        self.database.save_proposal(proposal)
        return proposal

    def revalidate(self, proposal: Proposal, *, policy_version: str = POLICY_VERSION) -> None:
        if proposal.policy_digest != policy_digest(policy_version):
            raise FileChangedError("cleanup policy changed after review")
        if proposal.items_digest != digest_items(
            proposal.policy_digest,
            proposal.items,
            project_id=proposal.project_id,
            task_id=proposal.task_id,
            root=proposal.root,
            recovery_root=proposal.recovery_root,
        ):
            raise FileChangedError("proposal operations changed after review")
        root = Path(proposal.root)
        for item in proposal.items:
            path = root / item.relative_path
            observed = self.filesystem.validate_candidate(path, root)
            expected = self.identity(item, observed.final_path)
            if observed != expected:
                raise FileChangedError(f"file state changed after review: {item.relative_path}")
            with self.filesystem.open_exclusive_file(path) as handle:
                if self.filesystem.hash_handle(handle) != item.sha256:
                    raise FileChangedError(
                        f"file content changed after review: {item.relative_path}"
                    )

    @staticmethod
    def identity(item: ProposalItem, final_path: str) -> FileIdentity:
        return FileIdentity(
            volume_serial=item.volume_serial,
            file_index=item.file_index,
            size=item.size,
            modified_100ns=item.modified_100ns,
            attributes=item.attributes,
            link_count=1,
            final_path=final_path,
        )
