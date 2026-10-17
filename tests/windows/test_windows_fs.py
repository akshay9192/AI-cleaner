from __future__ import annotations

import _winapi
import hashlib
import os
from pathlib import Path

import pytest

from ai_cleaner.platform.windows_fs import (
    BoundaryError,
    UnsupportedFilesystemError,
    WindowsFilesystem,
)

pytestmark = pytest.mark.windows


@pytest.fixture
def fs() -> WindowsFilesystem:
    return WindowsFilesystem()


def roots(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "Project scope"
    recovery = tmp_path / "Recovery store"
    project.mkdir()
    recovery.mkdir()
    return project, recovery


def test_roots_and_handle_move_are_same_volume_and_non_overwriting(
    fs: WindowsFilesystem, tmp_path: Path
) -> None:
    project, recovery = roots(tmp_path)
    source = project / "sp ace-例-[x].tmp"
    payload = recovery / "payload.bin"
    source.write_bytes(b"fixture-data")
    validated = fs.validate_roots(project, recovery)
    expected = fs.validate_candidate(source, project)
    digest = hashlib.sha256(b"fixture-data").hexdigest()

    moved = fs.guarded_move(
        source,
        payload,
        root=project,
        destination_root=recovery,
        expected=expected,
        expected_sha256=digest,
    )

    assert not source.exists()
    assert payload.read_bytes() == b"fixture-data"
    assert moved.stable_key == expected.stable_key
    assert moved.volume_serial == validated.volume_serial
    occupied = recovery / "occupied.bin"
    occupied.write_bytes(b"newer")
    with fs.open_exclusive_file(payload) as handle, pytest.raises(FileExistsError):
        fs.move_open_file(handle, occupied, expected=moved)
    assert occupied.read_bytes() == b"newer"


def test_outside_scope_and_case_prefix_are_rejected(
    fs: WindowsFilesystem, tmp_path: Path
) -> None:
    project, _ = roots(tmp_path)
    outside = tmp_path / "Project scope-other.txt"
    outside.write_text("valuable", encoding="utf-8")
    with pytest.raises(BoundaryError):
        fs.validate_candidate(outside, project)

    nested_recovery = project / "recovery"
    nested_recovery.mkdir()
    with pytest.raises(BoundaryError, match="must not overlap"):
        fs.validate_roots(project, nested_recovery)


def test_hard_links_and_alternate_streams_are_rejected(
    fs: WindowsFilesystem, tmp_path: Path
) -> None:
    project, _ = roots(tmp_path)
    original = project / "artifact.tmp"
    original.write_bytes(b"data")
    os.link(original, project / "second-name.tmp")
    with pytest.raises(UnsupportedFilesystemError, match="hard-linked"):
        fs.validate_candidate(original, project)

    ordinary = project / "streamed.tmp"
    ordinary.write_bytes(b"main")
    Path(f"{ordinary}:private").write_bytes(b"hidden")
    with pytest.raises(UnsupportedFilesystemError, match="alternate data streams"):
        fs.validate_candidate(ordinary, project)


def test_symlink_escape_is_rejected(fs: WindowsFilesystem, tmp_path: Path) -> None:
    project, _ = roots(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.tmp"
    secret.write_text("keep", encoding="utf-8")
    link = project / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        _winapi.CreateJunction(str(outside), str(link))
    with pytest.raises(UnsupportedFilesystemError):
        fs.validate_candidate(link / "secret.tmp", project)
    assert secret.read_text(encoding="utf-8") == "keep"


def test_restore_destination_link_escape_is_rejected(
    fs: WindowsFilesystem, tmp_path: Path
) -> None:
    project, _ = roots(tmp_path)
    outside = tmp_path / "outside-restore"
    outside.mkdir()
    link = project / "restore-link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        _winapi.CreateJunction(str(outside), str(link))
    volume = fs.inspect(project).volume_serial

    with pytest.raises(UnsupportedFilesystemError):
        fs.validate_destination(link / "escaped.tmp", project, expected_volume=volume)

    assert not (outside / "escaped.tmp").exists()


def test_exclusive_handle_blocks_conflicting_open(
    fs: WindowsFilesystem, tmp_path: Path
) -> None:
    project, _ = roots(tmp_path)
    target = project / "locked.tmp"
    target.write_bytes(b"locked")
    with fs.open_exclusive_file(target), pytest.raises(OSError):
        target.open("wb")
    assert target.read_bytes() == b"locked"


def test_open_parent_handle_blocks_replacement(fs: WindowsFilesystem, tmp_path: Path) -> None:
    _, recovery = roots(tmp_path)
    replacement_name = tmp_path / "renamed-recovery"
    with fs.open_handle(
        recovery.parent, directory=True, access=0x00010080, share=1
    ), pytest.raises(OSError):
        recovery.rename(replacement_name)
    assert recovery.is_dir()


def test_handle_delete_only_removes_open_fixture(fs: WindowsFilesystem, tmp_path: Path) -> None:
    project, _ = roots(tmp_path)
    target = project / "payload.tmp"
    neighbour = project / "keep.tmp"
    target.write_bytes(b"payload")
    neighbour.write_bytes(b"keep")
    expected = fs.validate_candidate(target, project)
    with fs.open_exclusive_file(target) as handle:
        fs.delete_open_file(handle, expected=expected)
    assert not target.exists()
    assert neighbour.read_bytes() == b"keep"
