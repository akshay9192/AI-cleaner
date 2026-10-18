from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ai_cleaner.domain.actions import RecoveryActionPlan
from ai_cleaner.domain.proposals import Proposal


@dataclass(frozen=True, slots=True)
class CleanupDecision:
    selected: frozenset[str]
    protected: frozenset[str]
    cancelled: bool = False


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    selected: frozenset[str]
    cancelled: bool = False


class ReviewInteraction(Protocol):
    @property
    def interactive(self) -> bool: ...

    def choose_cleanup(self, proposal: Proposal) -> CleanupDecision: ...

    def choose_recovery(self, plan: RecoveryActionPlan) -> RecoveryDecision: ...

    def confirm_exact(self, action: str, digest: str, summary: tuple[str, ...]) -> bool: ...
