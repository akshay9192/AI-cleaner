"""Create isolated, synthetic native-acceptance projects without deleting existing data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePath

AGENT_INSTRUCTIONS = """# Synthetic AI-cleaner acceptance fixture

This directory contains synthetic files only. Keep all work inside this fixture.

- Start AI-cleaner tracking before creating task artifacts.
- Register a disposable artifact only after writing it.
- Protect final deliverables.
- Invoke `complete` only when the task is explicitly complete.
- If no popup is available, leave the pending proposal untouched and report its review command.
- Never select files, confirm cleanup, restore, or purge on the user's behalf.
"""
FIXTURE_MARKER = "AI-cleaner synthetic acceptance fixture v1\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="native-popup")
    args = parser.parse_args()
    name = PurePath(args.name)
    if name.is_absolute() or len(name.parts) != 1 or name.parts[0] in {"", ".", ".."}:
        parser.error("--name must be one directory name")

    repo = Path(__file__).resolve().parents[1]
    fixture = repo / ".ai-cleaner-acceptance" / name.parts[0]
    paths = {
        "fixture": fixture,
        "popup_project": fixture / "project",
        "popup_state": fixture / "state",
        "purge_project": fixture / "purge-project",
        "purge_state": fixture / "purge-state",
    }
    marker = fixture / ".ai-cleaner-synthetic-fixture-v1"
    if fixture.exists():
        if not marker.is_file() or marker.read_text(encoding="utf-8") != FIXTURE_MARKER:
            parser.error(f"refusing to reuse an unmarked existing directory: {fixture}")
        missing = [
            str(path)
            for key, path in paths.items()
            if key != "fixture" and not path.is_dir()
        ]
        if missing:
            parser.error(f"marked fixture is incomplete; missing directories: {', '.join(missing)}")
        print(json.dumps({key: str(path) for key, path in paths.items()}, indent=2))
        return 0

    fixture.mkdir(parents=True)
    for key, path in paths.items():
        if key != "fixture":
            path.mkdir()

    for project in (paths["popup_project"], paths["purge_project"]):
        (project / "AGENTS.md").write_text(AGENT_INSTRUCTIONS, encoding="utf-8")
        (project / "existing-input.txt").write_text(
            "Synthetic baseline input. This file must remain protected.\n",
            encoding="utf-8",
        )
    marker.write_text(FIXTURE_MARKER, encoding="utf-8")

    print(json.dumps({key: str(path) for key, path in paths.items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
