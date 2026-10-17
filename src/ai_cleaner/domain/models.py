from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class ScanStatus(StrEnum):
    COMPLETE = "complete"
    CANCELLED = "cancelled"
    LIMIT_REACHED = "limit-reached"
    PARTIAL = "partial"


@dataclass(frozen=True, slots=True)
class FileObservation:
    relative_path: str
    size: int
    modified_ns: int
    created_ns: int
    attributes: int
    volume_serial: int | None
    file_index: int | None
    state: str = "present"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ScanIssue:
    relative_path: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(slots=True)
class ScanResult:
    scan_id: str
    root: Path
    status: ScanStatus
    observations: list[FileObservation] = field(default_factory=list)
    issues: list[ScanIssue] = field(default_factory=list)
    visited_entries: int = 0

    @property
    def complete(self) -> bool:
        return self.status is ScanStatus.COMPLETE

    def to_dict(self) -> dict[str, Any]:
        return {
            "scan_id": self.scan_id,
            "root": str(self.root),
            "status": self.status.value,
            "complete": self.complete,
            "visited_entries": self.visited_entries,
            "files": [item.to_dict() for item in self.observations],
            "issues": [issue.to_dict() for issue in self.issues],
        }
