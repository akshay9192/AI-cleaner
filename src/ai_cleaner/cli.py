"""Terminal-first AI-cleaner commands backed by the shared safety services."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path, PurePath
from typing import Any

from ai_cleaner import __version__
from ai_cleaner.domain.approval import ApprovalBroker, ApprovalError
from ai_cleaner.domain.models import ClassifiedFile
from ai_cleaner.platform.windows_fs import (
    BoundaryError,
    UnsupportedFilesystemError,
    WindowsFilesystem,
)
from ai_cleaner.services.classify import classify_files, git_evidence
from ai_cleaner.services.operations import OperationConflictError, QuarantineService
from ai_cleaner.services.proposals import ProposalError, ProposalService
from ai_cleaner.services.purge import PurgeService
from ai_cleaner.services.recovery import RecoveryError, RecoveryService
from ai_cleaner.services.scan import DEFAULT_ENTRY_LIMIT, Scanner
from ai_cleaner.services.tasks import TaskConflictError, TaskDiff, TaskService
from ai_cleaner.storage.config import StatePaths
from ai_cleaner.storage.database import Database
from ai_cleaner.terminal import ConsoleInteraction, ReviewInteraction

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_INVALID = 2
EXIT_UNSUPPORTED = 3
EXIT_INCOMPLETE = 4
EXIT_CONFLICT = 5
EXIT_REVIEW_REQUIRED = 6
EXIT_CANCELLED = 7
EXIT_PARTIAL = 8


@dataclass(slots=True)
class Runtime:
    state: StatePaths
    database: Database
    filesystem: WindowsFilesystem
    scanner: Scanner
    tasks: TaskService
    proposals: ProposalService


def _add_state_dir(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--state-dir", type=Path, help=argparse.SUPPRESS)


def _add_root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", required=True, type=Path)
    _add_state_dir(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-cleaner",
        description="Track task artifacts and review recoverable cleanup in the terminal.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="report runtime support")
    doctor.add_argument("--json", action="store_true")
    scan = commands.add_parser("scan", help="read-only inventory of one selected project")
    _add_root(scan)
    scan.add_argument("--json", action="store_true")
    scan.add_argument("--limit", type=int, default=DEFAULT_ENTRY_LIMIT)
    preview = commands.add_parser("preview", help="read-only conservative cleanup preview")
    _add_root(preview)
    preview.add_argument("--task")
    preview.add_argument("--json", action="store_true")
    start = commands.add_parser("start", help="start tracking and capture a baseline")
    _add_root(start)
    start.add_argument("--label", required=True)
    register = commands.add_parser("register", help="register a task artifact")
    _add_root(register)
    register.add_argument("--task")
    register.add_argument("--path", required=True)
    register.add_argument("--role", required=True, choices=("scratch", "deliverable", "input"))
    protect = commands.add_parser("protect", help="protect a path as a deliverable")
    _add_root(protect)
    protect.add_argument("--task")
    protect.add_argument("--path", required=True)
    protect.add_argument("--reason", default="Protected explicitly from the terminal")
    complete = commands.add_parser("complete", help="finish a task and prepare/review cleanup")
    _add_root(complete)
    complete.add_argument("--task")
    review = commands.add_parser("review", help="interactively review a pending proposal")
    review.add_argument("--proposal", required=True)
    _add_state_dir(review)
    propose = commands.add_parser("propose", help="prepare a pending proposal (compatibility)")
    _add_root(propose)
    propose.add_argument("--task")
    propose.add_argument("--json", action="store_true")
    history = commands.add_parser("history", help="show operations and recovery payloads")
    _add_root(history)
    history.add_argument("--json", action="store_true")
    restore = commands.add_parser("restore", help="review and restore recovery payloads")
    restore_target = restore.add_mutually_exclusive_group(required=True)
    restore_target.add_argument("--run")
    restore_target.add_argument("--item", action="append")
    restore.add_argument("--destination", action="append", default=[], metavar="ID=RELATIVE_PATH")
    _add_state_dir(restore)
    purge = commands.add_parser("purge", help="separately review permanent payload removal")
    purge_target = purge.add_mutually_exclusive_group(required=True)
    purge_target.add_argument("--run")
    purge_target.add_argument("--item", action="append")
    _add_state_dir(purge)
    task = commands.add_parser("task", help="compatibility aliases for task metadata")
    task_commands = task.add_subparsers(dest="task_command", required=True)
    task_start = task_commands.add_parser("start")
    _add_root(task_start)
    task_start.add_argument("--label", required=True)
    task_register = task_commands.add_parser("register")
    task_register.add_argument("--task", required=True)
    task_register.add_argument("--path", required=True)
    task_register.add_argument("--role", required=True, choices=("scratch", "deliverable", "input"))
    _add_state_dir(task_register)
    task_finish = task_commands.add_parser("finish")
    task_finish.add_argument("--task", required=True)
    _add_state_dir(task_finish)
    return parser


def _runtime(state_dir: Path | None) -> Runtime:
    state = StatePaths.discover(state_dir)
    state.ensure()
    database = Database(state.database)
    database.migrate()
    filesystem = WindowsFilesystem()
    scanner = Scanner(filesystem)
    return Runtime(
        state,
        database,
        filesystem,
        scanner,
        TaskService(database, filesystem, scanner),
        ProposalService(database, filesystem),
    )


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
        print("\n".join(f"{key}: {value}" for key, value in result.items()))
    return EXIT_OK if result["status"] == "ok" else EXIT_UNSUPPORTED


def _ensure_project(runtime: Runtime, root: Path) -> tuple[str, Path]:
    root = root.absolute()
    identity = runtime.filesystem.validate_project_root(root, app_state=runtime.state.root)
    project_id = runtime.database.ensure_project(
        root=root,
        resolved_root=identity.final_path,
        volume_serial=identity.volume_serial,
        recovery_root=runtime.state.recovery,
        created_at=datetime.now(UTC).isoformat(),
    )
    return project_id, root


def _resolve_task(runtime: Runtime, root: Path, task_id: str | None) -> Any:
    project = runtime.database.project_by_root(root.absolute())
    if project is None:
        raise ValueError("no tracked task exists for this root; run 'ai-cleaner start' first")
    if task_id:
        task = runtime.database.task(task_id)
        if task is None or str(task["project_id"]) != str(project["id"]):
            raise ValueError("the task does not belong to the selected root")
        return task
    tasks = runtime.database.unresolved_tasks(str(project["id"]))
    if not tasks:
        raise ValueError("no active or interrupted task exists for this root")
    if len(tasks) > 1:
        choices = ", ".join(f"{row['id']} ({row['label']})" for row in tasks)
        raise TaskConflictError(f"several tasks are possible; pass --task explicitly: {choices}")
    return tasks[0]


def _normalize_relative(root: Path, value: str) -> str:
    relative = PurePath(value)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise BoundaryError("path must be relative and remain inside the selected project")
    normalized = str(relative).replace("/", os.sep)
    candidate = (root.absolute() / normalized).absolute()
    if os.path.commonpath([str(candidate), str(root.absolute())]) != str(root.absolute()):
        raise BoundaryError("path escapes the selected project")
    return normalized


def _classifications(
    runtime: Runtime, root: Path, task_id: str | None
) -> tuple[str, list[ClassifiedFile], TaskDiff | None]:
    project_id, root = _ensure_project(runtime, root)
    scan = runtime.scanner.scan(root, excluded_roots=(runtime.state.root, runtime.state.recovery))
    if not scan.complete:
        raise RuntimeError("a complete scan is required to prepare cleanup")
    declarations: dict[str, str] = {}
    protected_by_task: set[str] = set()
    diff: TaskDiff | None = None
    if task_id:
        runtime.tasks.require_finished(task_id)
        task = runtime.database.task(task_id)
        if task is None or str(task["project_id"]) != project_id:
            raise ValueError("the task does not belong to the selected root")
        diff = runtime.tasks.diff(task_id)
        declarations = runtime.database.task_declarations(task_id)
        added = {path.casefold() for path in diff.added}
        protected_by_task = {
            item.relative_path
            for item in scan.observations
            if item.relative_path.casefold() not in added
        }
    classified = classify_files(
        scan.observations,
        git=git_evidence(root),
        pins=runtime.database.protections(project_id),
        declarations=declarations,
        active_task_paths=protected_by_task,
    )
    return (
        project_id,
        [
            replace(item, explanation=f"{item.explanation}; evidence: {item.ownership_evidence}")
            for item in classified
        ],
        diff,
    )


def _print_classifications(
    classified: list[ClassifiedFile], *, as_json: bool, no_baseline: bool = False
) -> None:
    if as_json:
        print(
            json.dumps(
                [item.to_dict() for item in classified], ensure_ascii=False, sort_keys=True
            )
        )
        return
    if no_baseline:
        print("No task baseline was supplied; historical ownership cannot be established.")
    for item in classified:
        marker = "candidate" if item.selectable else item.category.value
        print(
            f"[{marker}] {item.observation.relative_path} | {item.observation.size} bytes | "
            f"{item.explanation}"
        )


def _prepare_pending(
    runtime: Runtime, root: Path, task_id: str | None, *, emit_human_output: bool = True
) -> Any | None:
    project_id, classified, diff = _classifications(runtime, root, task_id)
    if diff is not None and emit_human_output:
        print(
            f"Task {diff.task_id} complete: {len(diff.added)} added, "
            f"{len(diff.modified)} modified, {len(diff.missing)} missing."
        )
        for label, paths in (
            ("new", diff.added),
            ("modified", diff.modified),
            ("missing", diff.missing),
        ):
            for path in paths:
                print(f"[{label}] {path}")
        print(
            "Added files are observed during the task; "
            "AI-cleaner does not claim who created them."
        )
    if emit_human_output:
        _print_classifications(classified, as_json=False)
    candidates = [item for item in classified if item.selectable]
    if not candidates:
        if emit_human_output:
            print("No eligible cleanup candidates were found; nothing was moved.")
        return None
    return runtime.proposals.prepare(
        project_id=project_id,
        root=root,
        recovery_root=runtime.state.recovery,
        selected=candidates,
        task_id=task_id,
    )


def _review_required(proposal_id: str) -> int:
    print("Human interactive review is required; no files were moved.")
    print(f"Run in a human terminal: ai-cleaner review --proposal {proposal_id}")
    return EXIT_REVIEW_REQUIRED


def _review_proposal(runtime: Runtime, proposal_id: str, interaction: ReviewInteraction) -> int:
    proposal = runtime.database.proposal(proposal_id)
    if proposal is None:
        raise ValueError(f"unknown proposal: {proposal_id}")
    if runtime.database.proposal_state(proposal_id) != "reviewable":
        raise TaskConflictError("proposal is no longer reviewable; prepare a fresh proposal")
    if not interaction.interactive:
        return _review_required(proposal_id)
    decision = interaction.choose_cleanup(proposal)
    for relative_path in decision.protected:
        runtime.database.add_protection(
            protection_id=str(uuid.uuid4()),
            project_id=proposal.project_id,
            relative_path=relative_path,
            reason="Protected during terminal review",
            origin="terminal-review",
            created_at=datetime.now(UTC).isoformat(),
        )
    if decision.cancelled or not decision.selected:
        print("Review cancelled or no files selected; every file was retained.")
        return EXIT_CANCELLED
    exact = runtime.proposals.select_subset(proposal, set(decision.selected))
    summary = (
        "Final cleanup selection:",
        *(
            f"  {item.relative_path} | {item.size} bytes | {item.explanation}"
            for item in exact.items
        ),
        f"Count: {len(exact.items)}",
        f"Logical bytes to quarantine: {exact.logical_bytes}",
        f"Recovery destination: {exact.recovery_root}",
        "Moving files to recovery does not reclaim disk space.",
    )
    if not interaction.confirm_exact("MOVE", exact.items_digest, summary):
        print("Confirmation did not match; every file was retained.")
        return EXIT_CANCELLED
    approvals = ApprovalBroker()
    capability = approvals._grant_after_human_review(
        proposal_digest=exact.items_digest,
        reviewed_digest=exact.items_digest,
        action="quarantine",
    )
    result = QuarantineService(
        runtime.database,
        runtime.filesystem,
        approvals,
        runtime.state.locks / f"{exact.project_id}.lock",
    ).execute(exact, capability)
    print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    print(f"Restore with: ai-cleaner restore --run {result.run_id}")
    return EXIT_OK if result.status == "complete" else EXIT_PARTIAL


def _scan(args: argparse.Namespace) -> int:
    if args.limit < 1:
        raise ValueError("entry limit must be positive")
    runtime = _runtime(args.state_dir)
    project_id, root = _ensure_project(runtime, args.root)
    result = runtime.scanner.scan(
        root,
        entry_limit=args.limit,
        excluded_roots=(runtime.state.root, runtime.state.recovery),
    )
    runtime.database.save_scan(project_id, result, datetime.now(UTC).isoformat())
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    else:
        print(
            f"{result.status.value}: {len(result.observations)} files, {len(result.issues)} issues"
        )
    return EXIT_OK if result.complete else EXIT_INCOMPLETE


def _start(args: argparse.Namespace) -> int:
    runtime = _runtime(args.state_dir)
    task_id = runtime.tasks.start(
        args.root, args.label, excluded_roots=(runtime.state.root, runtime.state.recovery)
    )
    print(json.dumps({"task_id": task_id, "status": "active", "label": args.label}))
    return EXIT_OK


def _register(args: argparse.Namespace, *, protect: bool = False) -> int:
    runtime = _runtime(args.state_dir)
    project_id, root = _ensure_project(runtime, args.root)
    task = _resolve_task(runtime, root, args.task)
    task_id = str(task["id"])
    normalized = _normalize_relative(root, args.path)
    role = "deliverable" if protect else args.role
    runtime.tasks.register(task_id, normalized, role)
    if protect:
        runtime.database.add_protection(
            protection_id=str(uuid.uuid4()),
            project_id=project_id,
            relative_path=normalized,
            reason=args.reason,
            origin="terminal",
            created_at=datetime.now(UTC).isoformat(),
        )
    print(json.dumps({"task_id": task_id, "path": normalized, "role": role}, sort_keys=True))
    return EXIT_OK


def _complete(args: argparse.Namespace, interaction: ReviewInteraction) -> int:
    runtime = _runtime(args.state_dir)
    project_id, root = _ensure_project(runtime, args.root)
    if args.task is None and not runtime.database.unresolved_tasks(project_id):
        print(
            "No tracked task baseline exists. Showing a conservative existing-clutter review; "
            "historical ownership cannot be established."
        )
        proposal = _prepare_pending(runtime, root, None)
        if proposal is None:
            return EXIT_OK
        return _review_proposal(runtime, proposal.proposal_id, interaction)
    task = _resolve_task(runtime, root, args.task)
    task_id = str(task["id"])
    print(f"Completing task {task_id}: {task['label']}")
    runtime.tasks.finish(task_id, excluded_roots=(runtime.state.root, runtime.state.recovery))
    proposal = _prepare_pending(runtime, root, task_id)
    if proposal is None:
        return EXIT_OK
    return _review_proposal(runtime, proposal.proposal_id, interaction)


def _preview(args: argparse.Namespace) -> int:
    runtime = _runtime(args.state_dir)
    _, classified, _ = _classifications(runtime, args.root, args.task)
    _print_classifications(classified, as_json=args.json, no_baseline=args.task is None)
    return EXIT_OK


def _propose(args: argparse.Namespace, interaction: ReviewInteraction) -> int:
    runtime = _runtime(args.state_dir)
    proposal = _prepare_pending(
        runtime, args.root.absolute(), args.task, emit_human_output=not args.json
    )
    if proposal is None:
        return EXIT_OK
    if args.json:
        payload = proposal.to_dict()
        payload.update(
            {
                "status": "review-required",
                "mutation_performed": False,
                "review_command": f"ai-cleaner review --proposal {proposal.proposal_id}",
            }
        )
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return EXIT_REVIEW_REQUIRED
    return _review_proposal(runtime, proposal.proposal_id, interaction)


def _history(args: argparse.Namespace) -> int:
    runtime = _runtime(args.state_dir)
    project = runtime.database.project_by_root(args.root.absolute())
    if project is None:
        raise ValueError("the selected project has no AI-cleaner history")
    project_id = str(project["id"])
    operations = runtime.database.history(project_id)
    recovery_items = [dict(item) for item in runtime.database.recovery_items(project_id)]
    payload = {
        "project_id": project_id,
        "root": str(args.root.absolute()),
        "operations": operations,
        "recovery_items": recovery_items,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        for operation in operations:
            print(
                f"run {operation['id']} | {operation['action']} | {operation['status']} | "
                f"{operation['item_count']} items"
            )
        for item in recovery_items:
            print(
                f"recovery {item['id']} | {item['state']} | {item['size']} bytes | "
                f"{item['original_path']}"
            )
    return EXIT_OK


def _recovery_ids(runtime: Runtime, run_id: str | None, items: list[str] | None) -> list[str]:
    if items:
        return items
    assert run_id is not None
    rows = runtime.database.recovery_items_for_run(run_id)
    if not rows:
        raise ValueError(f"no recovery payloads belong to quarantine run {run_id}")
    available = [str(row["id"]) for row in rows if row["state"] == "quarantined"]
    if not available:
        raise ValueError("the selected run has no quarantined payloads available")
    return available


def _restore(args: argparse.Namespace, interaction: ReviewInteraction) -> int:
    runtime = _runtime(args.state_dir)
    ids = _recovery_ids(runtime, args.run, args.item)
    alternatives: dict[str, Path] = {}
    for value in args.destination:
        recovery_id, separator, relative = value.partition("=")
        if not separator:
            raise ValueError("destination must be RECOVERY_ID=RELATIVE_PATH")
        row = runtime.database.recovery_item(recovery_id)
        if row is None:
            raise ValueError(f"unknown recovery item: {recovery_id}")
        project = runtime.database.project(str(row["project_id"]))
        if project is None:
            raise ValueError("project metadata is missing")
        root = Path(str(project["root"]))
        alternatives[recovery_id] = root / _normalize_relative(root, relative)
    approvals = ApprovalBroker()
    service = RecoveryService(
        runtime.database,
        runtime.filesystem,
        approvals,
        runtime.state.locks / "recovery.lock",
    )
    plan = service.prepare_restore(ids, alternatives=alternatives)
    if not interaction.interactive:
        print(json.dumps(plan.to_dict(), ensure_ascii=False, sort_keys=True))
        print("Human interactive review is required; no payload was restored.")
        print("Run the same ai-cleaner restore command in a human terminal.")
        return EXIT_REVIEW_REQUIRED
    decision = interaction.choose_recovery(plan)
    if decision.cancelled or not decision.selected:
        print("Restore cancelled; every payload was retained.")
        return EXIT_CANCELLED
    selected_alternatives = {
        key: value for key, value in alternatives.items() if key in decision.selected
    }
    exact = service.prepare_restore(list(decision.selected), alternatives=selected_alternatives)
    summary = (
        "Final restore selection:",
        *(f"  {item.recovery_id}: {item.source} -> {item.destination}" for item in exact.items),
        f"Count: {len(exact.items)}",
        f"Logical bytes: {exact.logical_bytes}",
    )
    if not interaction.confirm_exact("RESTORE", exact.digest, summary):
        print("Confirmation did not match; every payload was retained.")
        return EXIT_CANCELLED
    capability = approvals._grant_after_human_review(
        proposal_digest=exact.digest, reviewed_digest=exact.digest, action="restore"
    )
    result = service.restore(exact, capability)
    print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    return EXIT_OK if result.status == "complete" else EXIT_PARTIAL


def _purge(args: argparse.Namespace, interaction: ReviewInteraction) -> int:
    runtime = _runtime(args.state_dir)
    ids = _recovery_ids(runtime, args.run, args.item)
    approvals = ApprovalBroker()
    service = PurgeService(
        runtime.database,
        runtime.filesystem,
        approvals,
        runtime.state.locks / "recovery.lock",
    )
    plan = service.prepare(ids)
    if not interaction.interactive:
        print(json.dumps(plan.to_dict(), ensure_ascii=False, sort_keys=True))
        print("Human interactive review is required; no payload was permanently removed.")
        print("Run the same ai-cleaner purge command in a human terminal.")
        return EXIT_REVIEW_REQUIRED
    decision = interaction.choose_recovery(plan)
    if decision.cancelled or not decision.selected:
        print("Purge cancelled; every payload was retained.")
        return EXIT_CANCELLED
    exact = service.prepare(list(decision.selected))
    summary = (
        "FINAL PERMANENT PURGE SELECTION:",
        *(f"  {item.recovery_id}: {item.source} | {item.size} bytes" for item in exact.items),
        f"Count: {len(exact.items)}",
        f"Logical payload bytes to remove: {exact.logical_bytes}",
        "Physical disk-space change is not inferred.",
    )
    if not interaction.confirm_exact("PURGE", exact.digest, summary):
        print("Confirmation did not match; every payload was retained.")
        return EXIT_CANCELLED
    capability = approvals._grant_after_human_review(
        proposal_digest=exact.digest, reviewed_digest=exact.digest, action="purge"
    )
    result = service.execute(exact, capability)
    print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    return EXIT_OK if result.status == "complete" else EXIT_PARTIAL


def _task_compat(args: argparse.Namespace) -> int:
    if args.task_command == "start":
        return _start(args)
    runtime = _runtime(args.state_dir)
    if args.task_command == "register":
        runtime.tasks.register(args.task, args.path, args.role)
        print(json.dumps({"task_id": args.task, "path": args.path, "role": args.role}))
    else:
        result = runtime.tasks.finish(
            args.task, excluded_roots=(runtime.state.root, runtime.state.recovery)
        )
        print(json.dumps(result.to_dict(), sort_keys=True))
    return EXIT_OK


def run(argv: Sequence[str] | None = None, *, interaction: ReviewInteraction | None = None) -> int:
    args = build_parser().parse_args(argv)
    reviewer = ConsoleInteraction() if interaction is None else interaction
    try:
        handlers = {
            "scan": lambda: _scan(args),
            "preview": lambda: _preview(args),
            "start": lambda: _start(args),
            "register": lambda: _register(args),
            "protect": lambda: _register(args, protect=True),
            "complete": lambda: _complete(args, reviewer),
            "review": lambda: _review_proposal(_runtime(args.state_dir), args.proposal, reviewer),
            "propose": lambda: _propose(args, reviewer),
            "history": lambda: _history(args),
            "restore": lambda: _restore(args, reviewer),
            "purge": lambda: _purge(args, reviewer),
            "task": lambda: _task_compat(args),
        }
        if args.command == "doctor":
            return _doctor(args.json)
        return handlers[args.command]()
    except (ValueError, BoundaryError, ProposalError, RecoveryError, ApprovalError) as error:
        print(str(error), file=sys.stderr)
        return EXIT_INVALID
    except UnsupportedFilesystemError as error:
        print(str(error), file=sys.stderr)
        return EXIT_UNSUPPORTED
    except (TaskConflictError, OperationConflictError) as error:
        print(str(error), file=sys.stderr)
        return EXIT_CONFLICT
    except (RuntimeError, OSError) as error:
        print(str(error), file=sys.stderr)
        return EXIT_ERROR


def main(argv: Sequence[str] | None = None) -> int:
    return run(argv)
