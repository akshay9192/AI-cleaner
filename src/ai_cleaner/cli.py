"""Command-line entry points; mutation approval intentionally lives only in the GUI."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from collections.abc import Sequence

from ai_cleaner import __version__


def _doctor(as_json: bool) -> int:
    result = {
        "application": "AI-cleaner",
        "version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "windows_supported_for_mutation": sys.platform == "win32",
        "status": "ok" if sys.version_info[:2] == (3, 12) else "unsupported-python",
    }
    if as_json:
        print(json.dumps(result, sort_keys=True))
    else:
        for key, value in result.items():
            print(f"{key}: {value}")
    return 0 if result["status"] == "ok" else 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-cleaner",
        description="Review project artifacts safely; cleanup approval is GUI-only.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor = subparsers.add_parser("doctor", help="report runtime support")
    doctor.add_argument("--json", action="store_true", help="emit JSON to stdout")
    subparsers.add_parser("gui", help="open the desktop application")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        return _doctor(args.json)
    if args.command == "gui":
        from ai_cleaner.ui.app import main as gui_main

        return gui_main()
    return 2
