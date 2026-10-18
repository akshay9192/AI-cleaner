from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Protocol, TextIO

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


class ConsoleInteraction:
    """Production TTY interaction. It has no automated-confirmation mode."""

    def __init__(self, stdin: TextIO | None = None, stdout: TextIO | None = None) -> None:
        self.stdin = sys.stdin if stdin is None else stdin
        self.stdout = sys.stdout if stdout is None else stdout

    @property
    def interactive(self) -> bool:
        return self.stdin.isatty() and self.stdout.isatty()

    def choose_cleanup(self, proposal: Proposal) -> CleanupDecision:
        selected: set[str] = set()
        protected: set[str] = set()
        self._write("Cleanup candidates (default: keep every file):")
        for index, item in enumerate(proposal.items, start=1):
            self._write(
                f"[{index}/{len(proposal.items)}] {item.relative_path} | {item.size} bytes\n"
                f"  {item.explanation}"
            )
            choice = self._read("  [Enter/k]eep, [s]elect, [p]rotect, [q]uit: ").casefold()
            if choice in {"q", "quit"}:
                return CleanupDecision(frozenset(), frozenset(), True)
            if choice in {"s", "select"}:
                selected.add(item.relative_path)
            elif choice in {"p", "protect"}:
                protected.add(item.relative_path)
            elif choice not in {"", "k", "keep"}:
                self._write("  Unrecognized choice; file kept.")
        return CleanupDecision(frozenset(selected), frozenset(protected))

    def choose_recovery(self, plan: RecoveryActionPlan) -> RecoveryDecision:
        selected: set[str] = set()
        self._write(f"{plan.action.title()} candidates (default: keep every payload):")
        for index, item in enumerate(plan.items, start=1):
            self._write(
                f"[{index}/{len(plan.items)}] {item.recovery_id} | {item.size} bytes\n"
                f"  source: {item.source}\n  destination: {item.destination}"
            )
            choice = self._read("  [Enter/k]eep, [s]elect, [q]uit: ").casefold()
            if choice in {"q", "quit"}:
                return RecoveryDecision(frozenset(), True)
            if choice in {"s", "select"}:
                selected.add(item.recovery_id)
            elif choice not in {"", "k", "keep"}:
                self._write("  Unrecognized choice; payload kept.")
        return RecoveryDecision(frozenset(selected))

    def confirm_exact(self, action: str, digest: str, summary: tuple[str, ...]) -> bool:
        for line in summary:
            self._write(line)
        prefix = digest[:12]
        phrase = f"{action.upper()} {prefix}"
        self._write(f"Proposal digest: {digest}")
        entered = self._read(f"Type {phrase} to confirm these exact operations: ")
        return entered == phrase

    def _read(self, prompt: str) -> str:
        self.stdout.write(prompt)
        self.stdout.flush()
        line = self.stdin.readline()
        if line == "":
            return "q"
        return line.strip()

    def _write(self, message: str) -> None:
        self.stdout.write(f"{message}\n")
        self.stdout.flush()
