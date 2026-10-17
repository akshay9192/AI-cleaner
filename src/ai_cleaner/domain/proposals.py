from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ProposalItem:
    relative_path: str
    action: str
    volume_serial: int
    file_index: int
    size: int
    modified_100ns: int
    attributes: int
    sha256: str
    explanation: str
    recovery_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Proposal:
    proposal_id: str
    project_id: str
    task_id: str | None
    root: str
    recovery_root: str
    policy_digest: str
    items: tuple[ProposalItem, ...]
    items_digest: str
    created_at: str

    @property
    def logical_bytes(self) -> int:
        return sum(item.size for item in self.items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "root": self.root,
            "recovery_root": self.recovery_root,
            "policy_digest": self.policy_digest,
            "items": [item.to_dict() for item in self.items],
            "items_digest": self.items_digest,
            "created_at": self.created_at,
            "logical_bytes": self.logical_bytes,
            "recovery_behavior": "same-volume quarantine; no disk space is reclaimed",
        }


def digest_items(policy_digest: str, items: tuple[ProposalItem, ...]) -> str:
    payload = {
        "policy_digest": policy_digest,
        "items": [
            item.to_dict()
            for item in sorted(items, key=lambda value: value.relative_path.casefold())
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
