from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Callable
from pathlib import Path

from ai_cleaner.domain.models import FileObservation, ScanIssue, ScanResult, ScanStatus
from ai_cleaner.platform.windows_fs import FILE_ATTRIBUTE_REPARSE_POINT, WindowsFilesystem

DEFAULT_ENTRY_LIMIT = 100_000
EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "node_modules",
    "_bmad",
    "_bmad-output",
}


class Scanner:
    def __init__(self, filesystem: WindowsFilesystem) -> None:
        self.filesystem = filesystem

    def scan(
        self,
        root: Path,
        *,
        cancel: threading.Event | None = None,
        entry_limit: int = DEFAULT_ENTRY_LIMIT,
        excluded_roots: tuple[Path, ...] = (),
        progress: Callable[[int], None] | None = None,
    ) -> ScanResult:
        root = root.absolute()
        result = ScanResult(str(uuid.uuid4()), root, ScanStatus.COMPLETE)
        stack = [root]
        excluded = {os.path.normcase(str(path.absolute())) for path in excluded_roots}
        while stack:
            if cancel and cancel.is_set():
                result.status = ScanStatus.CANCELLED
                break
            directory = stack.pop()
            try:
                entries = list(os.scandir(directory))
            except OSError as error:
                result.issues.append(self._issue(root, directory, "directory-inaccessible", error))
                result.status = ScanStatus.PARTIAL
                continue
            for entry in entries:
                if cancel and cancel.is_set():
                    result.status = ScanStatus.CANCELLED
                    break
                result.visited_entries += 1
                if progress:
                    progress(result.visited_entries)
                if result.visited_entries > entry_limit:
                    result.status = ScanStatus.LIMIT_REACHED
                    break
                path = Path(entry.path)
                relative = str(path.relative_to(root))
                try:
                    stat = entry.stat(follow_symlinks=False)
                    attributes = int(getattr(stat, "st_file_attributes", 0))
                    if entry.is_symlink() or attributes & FILE_ATTRIBUTE_REPARSE_POINT:
                        result.issues.append(
                            ScanIssue(
                                relative, "unsupported-link", "link/reparse point not traversed"
                            )
                        )
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name.casefold() in EXCLUDED_DIRECTORY_NAMES:
                            result.issues.append(
                                ScanIssue(
                                    relative, "excluded-directory", "protected tree not scanned"
                                )
                            )
                        elif os.path.normcase(str(path.absolute())) in excluded:
                            result.issues.append(
                                ScanIssue(
                                    relative, "excluded-state", "app state/recovery not scanned"
                                )
                            )
                        else:
                            stack.append(path)
                        continue
                    if not entry.is_file(follow_symlinks=False):
                        result.issues.append(
                            ScanIssue(relative, "unsupported-type", "not an ordinary regular file")
                        )
                        continue
                    identity = self.filesystem.inspect(path)
                    result.observations.append(
                        FileObservation(
                            relative_path=relative,
                            size=int(stat.st_size),
                            modified_ns=int(stat.st_mtime_ns),
                            created_ns=int(stat.st_ctime_ns),
                            attributes=attributes,
                            volume_serial=identity.volume_serial,
                            file_index=identity.file_index,
                        )
                    )
                except OSError as error:
                    result.issues.append(self._issue(root, path, "entry-inaccessible", error))
                    result.status = ScanStatus.PARTIAL
            if result.status in (ScanStatus.CANCELLED, ScanStatus.LIMIT_REACHED):
                break
        result.observations.sort(key=lambda item: item.relative_path.casefold())
        return result

    @staticmethod
    def _issue(root: Path, path: Path, code: str, error: OSError) -> ScanIssue:
        try:
            relative = str(path.relative_to(root))
        except ValueError:
            relative = str(path)
        return ScanIssue(relative, code, str(error))
