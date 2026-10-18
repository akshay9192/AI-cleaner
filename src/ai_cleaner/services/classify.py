from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePath

from ai_cleaner.domain.models import Category, ClassifiedFile, FileObservation

POLICY_VERSION = "1"

SOURCE_SUFFIXES = {
    ".py",
    ".pyw",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".cs",
    ".rs",
    ".go",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".ipynb",
    ".sql",
}
RAW_DATA_SUFFIXES = {".csv", ".tsv", ".parquet", ".feather", ".sqlite", ".db", ".raw"}
MANIFEST_NAMES = {
    "agents.md",
    "ai_cleaner_project_plan.md",
    "implementation_status.md",
    "license",
    "pyproject.toml",
    "uv.lock",
    "package.json",
    "package-lock.json",
    "requirements.txt",
    "dockerfile",
    "compose.yaml",
    "makefile",
}
SECRET_NAMES = {".env", ".env.local", "credentials.json", "secrets.json", "id_rsa", "id_ed25519"}
CACHE_DIRECTORIES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
LATEX_INTERMEDIATES = {".aux", ".toc", ".fls", ".fdb_latexmk", ".synctex.gz"}


@dataclass(frozen=True, slots=True)
class GitEvidence:
    state: str
    tracked: frozenset[str]
    message: str = ""


Runner = Callable[..., subprocess.CompletedProcess[bytes]]


def git_evidence(root: Path, runner: Runner = subprocess.run) -> GitEvidence:
    if not (root / ".git").exists():
        return GitEvidence("not-repository", frozenset())
    try:
        completed = runner(
            ["git", "-C", str(root), "ls-files", "-z", "--cached"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
    except OSError as error:
        return GitEvidence("error", frozenset(), str(error))
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        return GitEvidence("error", frozenset(), message or "git ls-files failed")
    tracked = {
        item.decode("utf-8", errors="surrogateescape").replace("/", "\\").casefold()
        for item in completed.stdout.split(b"\0")
        if item
    }
    return GitEvidence("available", frozenset(tracked))


def _suffix(path: PurePath) -> str:
    name = path.name.casefold()
    if name.endswith(".synctex.gz"):
        return ".synctex.gz"
    return path.suffix.casefold()


def classify_files(
    observations: Sequence[FileObservation],
    *,
    git: GitEvidence,
    pins: Iterable[str] = (),
    declarations: dict[str, str] | None = None,
    active_task_paths: Iterable[str] = (),
) -> list[ClassifiedFile]:
    pin_set = {path.casefold() for path in pins}
    active_set = {path.casefold() for path in active_task_paths}
    declared = {key.casefold(): value for key, value in (declarations or {}).items()}
    return [
        _classify(
            observation,
            git=git,
            pins=pin_set,
            declarations=declared,
            active_task_paths=active_set,
        )
        for observation in observations
    ]


def _classify(
    observation: FileObservation,
    *,
    git: GitEvidence,
    pins: set[str],
    declarations: dict[str, str],
    active_task_paths: set[str],
) -> ClassifiedFile:
    path = PurePath(observation.relative_path)
    normalized = observation.relative_path.casefold()
    parts = {part.casefold() for part in path.parts}
    name = path.name.casefold()
    suffix = _suffix(path)

    def result(
        category: Category,
        code: str,
        explanation: str,
        evidence: str,
        *,
        selectable: bool = False,
    ) -> ClassifiedFile:
        return ClassifiedFile(observation, category, code, explanation, evidence, selectable)

    if normalized in pins or any(
        normalized.startswith(pin.rstrip("\\/") + "\\") for pin in pins
    ):
        return result(Category.PROTECTED, "user-pinned", "Pinned by the user", "explicit pin")
    if normalized in active_task_paths:
        return result(
            Category.PROTECTED,
            "active-task",
            "Active or interrupted task files cannot be cleaned",
            "task state",
        )
    role = declarations.get(normalized)
    if role in {"deliverable", "input"}:
        return result(
            Category.PROTECTED,
            f"declared-{role}",
            f"Explicitly registered as task {role}",
            "agent/user declaration; protected regardless of provenance",
        )
    if name in MANIFEST_NAMES or name in SECRET_NAMES or name.startswith(".env."):
        return result(
            Category.PROTECTED,
            "configuration-or-sensitive",
            "Configuration, credential, plan, or dependency metadata",
            "path-aware hard protection",
        )
    if path.suffix.casefold() in SOURCE_SUFFIXES or path.suffix.casefold() in RAW_DATA_SUFFIXES:
        return result(
            Category.PROTECTED,
            "source-or-input",
            "Source, notebook, database, or raw dataset",
            "file type hard protection",
        )
    if {".git", ".hg", ".svn", "_bmad", "_bmad-output"} & parts:
        return result(
            Category.PROTECTED,
            "protected-metadata",
            "Version-control or workflow metadata",
            "protected path",
        )
    if git.state == "error":
        return result(
            Category.PROTECTED,
            "git-evidence-unavailable",
            "Git tracking could not be determined; protected conservatively",
            git.message,
        )
    if normalized in git.tracked:
        return result(
            Category.PROTECTED,
            "git-tracked",
            "Tracked by Git",
            "git ls-files --cached",
        )
    if role == "scratch":
        return result(
            Category.REGISTERED_TASK_SCRATCH,
            "declared-scratch",
            "Registered as scratch; declaration is not proof of origin",
            "agent/user declaration only",
            selectable=True,
        )
    if parts & CACHE_DIRECTORIES or suffix == ".pyc":
        return result(
            Category.SUGGESTED_INTERMEDIATE,
            "recognized-cache",
            "File is inside a recognized tool cache or is Python bytecode",
            "deterministic cache rule; human review required",
            selectable=True,
        )
    if suffix in LATEX_INTERMEDIATES:
        return result(
            Category.SUGGESTED_INTERMEDIATE,
            "latex-intermediate",
            "Recognized LaTeX compilation intermediate",
            "deterministic extension rule; human review required",
            selectable=True,
        )
    return result(
        Category.UNKNOWN,
        "insufficient-evidence",
        "No reliable evidence that this file is disposable",
        "observed only",
    )
