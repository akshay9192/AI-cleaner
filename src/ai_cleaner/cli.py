"""Command-line entry points; mutation approval intentionally lives only in the GUI."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from ai_cleaner import __version__
from ai_cleaner.platform.windows_fs import (
    BoundaryError,
    UnsupportedFilesystemError,
    WindowsFilesystem,
)
from ai_cleaner.services.scan import DEFAULT_ENTRY_LIMIT, Scanner
from ai_cleaner.services.tasks import TaskConflictError, TaskService
from ai_cleaner.storage.config import StatePaths
from ai_cleaner.storage.database import Database


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
    scan = subparsers.add_parser("scan", help="inventory one selected project without modifying it")
    scan.add_argument("--root", required=True, type=Path)
    scan.add_argument("--json", action="store_true", help="emit JSON to stdout")
    scan.add_argument("--limit", type=int, default=DEFAULT_ENTRY_LIMIT)
    scan.add_argument("--state-dir", type=Path, help=argparse.SUPPRESS)
    task = subparsers.add_parser("task", help="manage cooperative task snapshots")
    task_subparsers = task.add_subparsers(dest="task_command", required=True)
    task_start = task_subparsers.add_parser("start", help="capture a task baseline")
    task_start.add_argument("--root", required=True, type=Path)
    task_start.add_argument("--label", required=True)
    task_start.add_argument("--state-dir", type=Path, help=argparse.SUPPRESS)
    task_register = task_subparsers.add_parser("register", help="declare a task artifact")
    task_register.add_argument("--task", required=True)
    task_register.add_argument("--path", required=True)
    task_register.add_argument("--role", required=True, choices=("scratch", "deliverable", "input"))
    task_register.add_argument("--state-dir", type=Path, help=argparse.SUPPRESS)
    task_finish = task_subparsers.add_parser("finish", help="capture the task end snapshot")
    task_finish.add_argument("--task", required=True)
    task_finish.add_argument("--state-dir", type=Path, help=argparse.SUPPRESS)
    gui = subparsers.add_parser("gui", help="open the desktop application")
    gui.add_argument("--root", type=Path)
    return parser


def _scan(args: argparse.Namespace) -> int:
    if args.limit < 1:
        print("entry limit must be positive", file=sys.stderr)
        return 2
    try:
        state = StatePaths.discover(args.state_dir)
        state.ensure()
        filesystem = WindowsFilesystem()
        root_identity = filesystem.validate_project_root(args.root, app_state=state.root)
        result = Scanner(filesystem).scan(
            args.root,
            entry_limit=args.limit,
            excluded_roots=(state.root, state.recovery),
        )
        database = Database(state.database)
        database.migrate()
        now = datetime.now(UTC).isoformat()
        project_id = database.ensure_project(
            root=args.root.absolute(),
            resolved_root=root_identity.final_path,
            volume_serial=root_identity.volume_serial,
            created_at=now,
        )
        database.save_scan(project_id, result, now)
        if args.json:
            print(json.dumps(result.to_dict(), sort_keys=True))
        else:
            print(
                f"{result.status.value}: {len(result.observations)} files, "
                f"{len(result.issues)} issues"
            )
        return 0 if result.complete else 4
    except BoundaryError as error:
        print(str(error), file=sys.stderr)
        return 2
    except UnsupportedFilesystemError as error:
        print(str(error), file=sys.stderr)
        return 3
    except OSError as error:
        print(str(error), file=sys.stderr)
        return 1


def _task(args: argparse.Namespace) -> int:
    try:
        state = StatePaths.discover(args.state_dir)
        state.ensure()
        database = Database(state.database)
        database.migrate()
        filesystem = WindowsFilesystem()
        service = TaskService(database, filesystem, Scanner(filesystem))
        if args.task_command == "start":
            task_id = service.start(
                args.root,
                args.label,
                excluded_roots=(state.root, state.recovery),
            )
            print(json.dumps({"task_id": task_id, "status": "active"}, sort_keys=True))
        elif args.task_command == "register":
            service.register(args.task, args.path, args.role)
            print(json.dumps({"task_id": args.task, "registered": args.path, "role": args.role}))
        else:
            result = service.finish(args.task, excluded_roots=(state.root, state.recovery))
            print(json.dumps(result.to_dict(), sort_keys=True))
        return 0
    except (ValueError, BoundaryError) as error:
        print(str(error), file=sys.stderr)
        return 2
    except UnsupportedFilesystemError as error:
        print(str(error), file=sys.stderr)
        return 3
    except TaskConflictError as error:
        print(str(error), file=sys.stderr)
        return 5
    except OSError as error:
        print(str(error), file=sys.stderr)
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        return _doctor(args.json)
    if args.command == "scan":
        return _scan(args)
    if args.command == "task":
        return _task(args)
    if args.command == "gui":
        from ai_cleaner.ui.app import main as gui_main

        return gui_main()
    return 2
