from __future__ import annotations

from ai_cleaner.domain.proposals import Proposal
from ai_cleaner.popup import PopupInteraction


def test_missing_tkinter_display_fails_closed(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    popup = PopupInteraction()

    def unavailable():  # type: ignore[no-untyped-def]
        raise ImportError("tkinter unavailable")

    monkeypatch.setattr(popup, "_modules", unavailable)

    assert not popup.interactive


def test_popup_error_returns_cancel_and_disables_approval(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    popup = PopupInteraction()
    popup._available = True
    proposal = Proposal(
        "proposal",
        "project",
        "task",
        "C:\\fixture",
        "C:\\recovery",
        "policy",
        (),
        "digest",
        "2026-10-18T00:00:00+00:00",
        "fixture task",
    )

    def fail(_proposal):  # type: ignore[no-untyped-def]
        raise RuntimeError("display disappeared")

    monkeypatch.setattr(popup, "_choose_cleanup_window", fail)
    decision = popup.choose_cleanup(proposal)

    assert decision.cancelled
    assert not decision.selected
    assert not popup.interactive
