from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RecoveryActionItem:
    recovery_id: str
    source: str
    destination: str
    volume_serial: int
    file_index: int
    size: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RecoveryActionPlan:
    project_id: str
    action: str
    items: tuple[RecoveryActionItem, ...]
    digest: str

    @classmethod
    def create(
        cls, project_id: str, action: str, items: tuple[RecoveryActionItem, ...]
    ) -> RecoveryActionPlan:
        payload = {
            "project_id": project_id,
            "action": action,
            "items": [item.to_dict() for item in items],
        }
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return cls(project_id, action, items, hashlib.sha256(encoded.encode()).hexdigest())

    @property
    def logical_bytes(self) -> int:
        return sum(item.size for item in self.items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "action": self.action,
            "items": [item.to_dict() for item in self.items],
            "digest": self.digest,
            "logical_bytes": self.logical_bytes,
        }

    def recomputed_digest(self) -> str:
        return self.create(self.project_id, self.action, self.items).digest

    def validate(self) -> None:
        if self.action not in {"restore", "purge"}:
            raise ValueError("unsupported recovery action")
        if not self.items:
            raise ValueError("recovery action plan is empty")
        if self.digest != self.recomputed_digest():
            raise ValueError("recovery action plan changed after review")
