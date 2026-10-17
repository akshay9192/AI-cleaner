from __future__ import annotations

import subprocess
from pathlib import Path

from ai_cleaner.domain.models import Category, FileObservation
from ai_cleaner.services.classify import GitEvidence, classify_files, git_evidence


def observation(path: str) -> FileObservation:
    return FileObservation(path, 10, 1, 1, 0, 1, 2)


def test_misleading_valuable_names_are_not_candidates() -> None:
    files = [
        observation("final_temp.py"),
        observation("valuable.log"),
        observation("original.png"),
        observation("raw.csv"),
        observation("__pycache__\\module.pyc"),
        observation("paper.aux"),
    ]
    classified = classify_files(files, git=GitEvidence("not-repository", frozenset()))
    by_path = {item.observation.relative_path: item for item in classified}

    assert by_path["final_temp.py"].category is Category.PROTECTED
    assert by_path["raw.csv"].category is Category.PROTECTED
    assert by_path["valuable.log"].category is Category.UNKNOWN
    assert by_path["original.png"].category is Category.UNKNOWN
    assert not by_path["valuable.log"].selectable
    assert by_path["__pycache__\\module.pyc"].selectable
    assert by_path["paper.aux"].reason_code == "latex-intermediate"


def test_pins_git_and_hard_protection_override_scratch() -> None:
    files = [observation("scratch.py"), observation("tracked.tmp"), observation("pinned.aux")]
    classified = classify_files(
        files,
        git=GitEvidence("available", frozenset({"tracked.tmp"})),
        pins={"pinned.aux"},
        declarations={"scratch.py": "scratch", "tracked.tmp": "scratch"},
    )
    assert all(item.category is Category.PROTECTED for item in classified)
    assert all(not item.selectable for item in classified)


def test_git_failure_protects_conservatively(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / ".git").mkdir()

    def failed(*args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(args[0], 128, b"", b"repository unavailable")

    evidence = git_evidence(tmp_path, runner=failed)
    item = classify_files([observation("cache.aux")], git=evidence)[0]
    assert evidence.state == "error"
    assert item.category is Category.PROTECTED
    assert item.reason_code == "git-evidence-unavailable"


def test_real_git_tracking_uses_nul_separated_paths(tmp_path: Path) -> None:
    tracked = tmp_path / "sp ace-例.aux"
    tracked.write_text("valuable", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, shell=False)
    subprocess.run(["git", "-C", str(tmp_path), "add", "--", tracked.name], check=True, shell=False)

    evidence = git_evidence(tmp_path)
    item = classify_files([observation(tracked.name)], git=evidence)[0]

    assert evidence.state == "available"
    assert item.category is Category.PROTECTED
    assert item.reason_code == "git-tracked"
