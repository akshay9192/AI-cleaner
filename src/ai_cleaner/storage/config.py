from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class StatePaths:
    root: Path
    database: Path
    recovery: Path
    locks: Path

    @classmethod
    def discover(cls, override: Path | None = None) -> StatePaths:
        if override is not None:
            root = override.absolute()
        elif configured := os.environ.get("AI_CLEANER_STATE_DIR"):
            root = Path(configured).absolute()
        else:
            local = os.environ.get("LOCALAPPDATA")
            if not local:
                raise RuntimeError(
                    "LOCALAPPDATA is unavailable; state location cannot be determined"
                )
            root = Path(local) / "AI-cleaner"
        return cls(
            root=root,
            database=root / "state.db",
            recovery=root / "recovery",
            locks=root / "locks",
        )

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.recovery.mkdir(exist_ok=True)
        self.locks.mkdir(exist_ok=True)
