from __future__ import annotations

import json
from pathlib import Path

from ai_cleaner.cli import main


def test_scan_cli_writes_json_and_local_state(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    root = tmp_path / "selected"
    state = tmp_path / "state"
    root.mkdir()
    (root / "one.tmp").write_bytes(b"one")

    code = main(
        ["scan", "--root", str(root), "--state-dir", str(state), "--json"]
    )

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert code == 0
    assert captured.err == ""
    assert result["status"] == "complete"
    assert result["files"][0]["relative_path"] == "one.tmp"
    assert (state / "state.db").is_file()


def test_scan_cli_limit_returns_partial_exit(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    root = tmp_path / "selected"
    state = tmp_path / "state"
    root.mkdir()
    (root / "one.tmp").write_bytes(b"one")
    (root / "two.tmp").write_bytes(b"two")

    code = main(
        [
            "scan",
            "--root",
            str(root),
            "--state-dir",
            str(state),
            "--limit",
            "1",
            "--json",
        ]
    )

    result = json.loads(capsys.readouterr().out)
    assert code == 4
    assert result["complete"] is False
    assert result["status"] == "limit-reached"
