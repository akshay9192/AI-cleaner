from __future__ import annotations

import pickle

import pytest

from ai_cleaner.domain.approval import ApprovalBroker, ApprovalError


def test_missing_forged_mismatched_and_replayed_approval_fail_closed() -> None:
    broker = ApprovalBroker()
    with pytest.raises(ApprovalError, match="missing"):
        broker.consume({"approved": True}, proposal_digest="digest", action="quarantine")
    capability = broker._grant_from_ui(
        proposal_digest="digest", reviewed_digest="digest", action="quarantine", now=10
    )
    with pytest.raises(ApprovalError, match="different"):
        broker.consume(capability, proposal_digest="changed", action="quarantine", now=11)
    broker.consume(capability, proposal_digest="digest", action="quarantine", now=11)
    with pytest.raises(ApprovalError, match="already"):
        broker.consume(capability, proposal_digest="digest", action="quarantine", now=11)


def test_expiry_and_serialization_fail_closed() -> None:
    broker = ApprovalBroker(lifetime_seconds=600)
    capability = broker._grant_from_ui(
        proposal_digest="digest", reviewed_digest="digest", action="purge", now=0
    )
    with pytest.raises(TypeError, match="cannot be serialized"):
        pickle.dumps(capability)
    with pytest.raises(ApprovalError, match="expired"):
        broker.consume(capability, proposal_digest="digest", action="purge", now=601)


def test_changed_review_cannot_grant() -> None:
    broker = ApprovalBroker()
    with pytest.raises(ApprovalError, match="do not match"):
        broker._grant_from_ui(
            proposal_digest="current", reviewed_digest="old", action="quarantine"
        )
