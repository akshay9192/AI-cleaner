from __future__ import annotations

import json

from ai_cleaner.cli import main


def test_doctor_reports_supported_python(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["doctor", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "ok"
    assert result["windows_supported_for_mutation"] is True


def test_help_exposes_terminal_workflow_without_approval_bypass() -> None:
    parser = __import__("ai_cleaner.cli", fromlist=["build_parser"]).build_parser()
    help_text = parser.format_help()
    assert "doctor" in help_text
    assert "complete" in help_text
    assert "register-temp" in help_text
    assert "review" in help_text
    assert "restore" in help_text
    assert "purge" in help_text
    assert "--yes" not in help_text
    assert "--force" not in help_text
