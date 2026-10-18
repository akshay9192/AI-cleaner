from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import NoReturn


class ApprovalError(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class _ApprovalCapability:
    nonce: str
    proposal_digest: str
    action: str
    expires_at: float
    broker_secret: object

    def __reduce__(self) -> NoReturn:
        raise TypeError("approval capabilities cannot be serialized")


class ApprovalBroker:
    """Owns ephemeral capabilities issued only after an interactive human review."""

    def __init__(self, *, lifetime_seconds: int = 600) -> None:
        self._secret = object()
        self._lifetime_seconds = lifetime_seconds
        self._unused: set[str] = set()

    def _grant_after_human_review(
        self,
        *,
        proposal_digest: str,
        reviewed_digest: str,
        action: str,
        now: float | None = None,
    ) -> _ApprovalCapability:
        if reviewed_digest != proposal_digest:
            raise ApprovalError("reviewed operations do not match the current proposal")
        if action not in {"quarantine", "restore", "purge"}:
            raise ApprovalError("unsupported approval action")
        issued_at = time.monotonic() if now is None else now
        nonce = secrets.token_urlsafe(32)
        self._unused.add(nonce)
        return _ApprovalCapability(
            nonce,
            proposal_digest,
            action,
            issued_at + self._lifetime_seconds,
            self._secret,
        )

    def consume(
        self,
        capability: object,
        *,
        proposal_digest: str,
        action: str,
        now: float | None = None,
    ) -> None:
        if not isinstance(capability, _ApprovalCapability):
            raise ApprovalError("human approval capability is missing")
        if capability.broker_secret is not self._secret:
            raise ApprovalError("approval capability was not issued by this application session")
        if capability.nonce not in self._unused:
            raise ApprovalError("approval capability has already been used")
        current = time.monotonic() if now is None else now
        if current > capability.expires_at:
            self._unused.discard(capability.nonce)
            raise ApprovalError("approval expired; review and confirm again")
        if capability.proposal_digest != proposal_digest or capability.action != action:
            raise ApprovalError("approval is bound to different operations")
        self._unused.remove(capability.nonce)
