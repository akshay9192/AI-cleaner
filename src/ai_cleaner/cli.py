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
from ai_cleaner.services.classify import classify_files, git_evidence
from ai_cleaner.services.proposals import ProposalError, ProposalService
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
    propose = subparsers.add_parser("propose", help="prepare a reviewable cleanup proposal")
    propose.add_argument("--root", required=True, type=Path)
    propose.add_argument("--task")
    propose.add_argument("--json", action="store_true")
    propose.add_argument("--state-dir", type=Path, help=argparse.SUPPRESS)
    history = subparsers.add_parser("history", help="show cleanup and recovery history")
    history.add_argument("--root", required=True, type=Path)
    history.add_argument("--json", action="store_true")
    history.add_argument("--state-dir", type=Path, help=argparse.SUPPRESS)
    gui = subparsers.add_parser("gui", help="open the desktop application")
    gui.add_argument("--root", type=Path)
    gui.add_argument("--state-dir", type=Path, help=argparse.SUPPRESS)
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


def _propose(args: argparse.Namespace) -> int:
    try:
        state = StatePaths.discover(args.state_dir)
        state.ensure()
        database = Database(state.database)
        database.migrate()
        filesystem = WindowsFilesystem()
        identity = filesystem.validate_project_root(args.root, app_state=state.root)
        now = datetime.now(UTC).isoformat()
        project_id = database.ensure_project(
            root=args.root.absolute(),
            resolved_root=identity.final_path,
            volume_serial=identity.volume_serial,
            recovery_root=state.recovery,
            created_at=now,
        )
        task_service = TaskService(database, filesystem, Scanner(filesystem))
        protected_by_task: set[str] = set()
        declarations: dict[str, str] = {}
        if args.task:
            task_service.require_finished(args.task)
            task_diff = task_service.diff(args.task)
            declarations = database.task_declarations(args.task)
            scan = Scanner(filesystem).scan(
                args.root, excluded_roots=(state.root, state.recovery)
            )
            added = {path.casefold() for path in task_diff.added}
            protected_by_task = {
                item.relative_path
                for item in scan.observations
                if item.relative_path.casefold() not in added
            }
        else:
            scan = Scanner(filesystem).scan(
                args.root, excluded_roots=(state.root, state.recovery)
            )
        if not scan.complete:
            print("proposal requires a complete scan", file=sys.stderr)
            return 4
        classified = classify_files(
            scan.observations,
            git=git_evidence(args.root),
            pins=database.protections(project_id),
            declarations=declarations,
            active_task_paths=protected_by_task,
        )
        selected = [item for item in classified if item.selectable]
        proposal = ProposalService(database, filesystem).prepare(
            project_id=project_id,
            root=args.root,
            recovery_root=state.recovery,
            selected=selected,
            task_id=args.task,
        )
        payload = proposal.to_dict()
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            print(
                f"reviewable proposal {proposal.proposal_id}: {len(proposal.items)} items, "
                f"{proposal.logical_bytes} logical bytes; no files moved"
            )
        return 0
    except (ValueError, BoundaryError, ProposalError) as error:
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


def _history(args: argparse.Namespace) -> int:
    try:
        state = StatePaths.discover(args.state_dir)
        database = Database(state.database)
        database.migrate()
        project = database.project_by_root(args.root)
        if project is None:
            print("the selected project has no AI-cleaner history", file=sys.stderr)
            return 2
        project_id = str(project["id"])
        payload = {
            "project_id": project_id,
            "root": str(args.root.absolute()),
            "operations": database.history(project_id),
            "recovery_items": [
                dict(item) for item in database.recovery_items(project_id)
            ],
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            print(
                f"{len(payload['operations'])} operations; "
                f"{len(payload['recovery_items'])} recovery items"
            )
        return 0
    except (ValueError, OSError) as error:
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
    if args.command == "propose":
        return _propose(args)
    if args.command == "history":
        return _history(args)
    if args.command == "gui":
        from ai_cleaner.ui.app import main as gui_main

        return gui_main(root=args.root, state_override=args.state_dir)
    return 2
