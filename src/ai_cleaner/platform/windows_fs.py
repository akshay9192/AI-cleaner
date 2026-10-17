"""Narrow Win32 adapter used for identity-bound, non-overwriting file operations."""

from __future__ import annotations

import ctypes
import hashlib
import os
import sys
from contextlib import ExitStack
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Final, NoReturn


class UnsupportedFilesystemError(RuntimeError):
    """The requested path has semantics AI-cleaner cannot safely mutate."""


class BoundaryError(ValueError):
    """A path or root is outside the explicitly approved scope."""


class FileChangedError(RuntimeError):
    """A file no longer matches the identity approved by the user."""


@dataclass(frozen=True, slots=True)
class FileIdentity:
    volume_serial: int
    file_index: int
    size: int
    modified_100ns: int
    attributes: int
    link_count: int
    final_path: str

    @property
    def stable_key(self) -> tuple[int, int]:
        return self.volume_serial, self.file_index


@dataclass(frozen=True, slots=True)
class ValidatedRoots:
    project: Path
    recovery: Path
    volume_serial: int


if sys.platform == "win32":
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
else:  # pragma: no cover - imported for documentation/type checking on other hosts
    kernel32 = None


INVALID_HANDLE_VALUE: Final[int] = -1
GENERIC_READ: Final[int] = 0x80000000
DELETE: Final[int] = 0x00010000
FILE_READ_ATTRIBUTES: Final[int] = 0x00000080
FILE_SHARE_READ: Final[int] = 0x00000001
FILE_SHARE_WRITE: Final[int] = 0x00000002
FILE_SHARE_DELETE: Final[int] = 0x00000004
OPEN_EXISTING: Final[int] = 3
FILE_FLAG_BACKUP_SEMANTICS: Final[int] = 0x02000000
FILE_FLAG_OPEN_REPARSE_POINT: Final[int] = 0x00200000
FILE_ATTRIBUTE_REPARSE_POINT: Final[int] = 0x00000400
FILE_ATTRIBUTE_OFFLINE: Final[int] = 0x00001000
FILE_ATTRIBUTE_RECALL_ON_OPEN: Final[int] = 0x00040000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS: Final[int] = 0x00400000
FILE_ATTRIBUTE_DIRECTORY: Final[int] = 0x00000010
FILE_RENAME_INFO_CLASS: Final[int] = 3
FILE_DISPOSITION_INFO_CLASS: Final[int] = 4
DRIVE_FIXED: Final[int] = 3


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", FILETIME),
        ("ftLastAccessTime", FILETIME),
        ("ftLastWriteTime", FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    ]


class FILE_RENAME_INFO(ctypes.Structure):
    _fields_ = [
        ("ReplaceIfExists", wintypes.BOOL),
        ("RootDirectory", wintypes.HANDLE),
        ("FileNameLength", wintypes.DWORD),
        ("FileName", wintypes.WCHAR * 1),
    ]


class FILE_DISPOSITION_INFO(ctypes.Structure):
    _fields_ = [("DeleteFile", wintypes.BOOL)]


def _raise_last_error(operation: str, path: Path) -> NoReturn:
    code = ctypes.get_last_error()
    raise OSError(code, f"{operation} failed: {ctypes.FormatError(code).strip()}", str(path))


def _win_path(path: Path) -> str:
    absolute = str(path.absolute())
    if absolute.startswith("\\\\?\\"):
        return absolute
    if absolute.startswith("\\\\"):
        return "\\\\?\\UNC\\" + absolute[2:]
    return "\\\\?\\" + absolute


def _display_final_path(value: str) -> str:
    if value.startswith("\\\\?\\UNC\\"):
        return "\\\\" + value[8:]
    if value.startswith("\\\\?\\"):
        return value[4:]
    return value


def _normal(path: str | Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def _is_within(path: str | Path, root: str | Path) -> bool:
    try:
        return os.path.commonpath([_normal(path), _normal(root)]) == _normal(root)
    except ValueError:
        return False


class WindowsHandle:
    def __init__(self, value: int, path: Path) -> None:
        self.value = value
        self.path = path

    def __enter__(self) -> WindowsHandle:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self.value != INVALID_HANDLE_VALUE:
            assert kernel32 is not None
            kernel32.CloseHandle(wintypes.HANDLE(self.value))
            self.value = INVALID_HANDLE_VALUE


class WindowsFilesystem:
    """Validated Windows operations; methods fail closed on unsupported semantics."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise UnsupportedFilesystemError("filesystem mutation is supported only on Windows")
        assert kernel32 is not None
        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.GetFileInformationByHandle.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(BY_HANDLE_FILE_INFORMATION),
        ]
        kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
        kernel32.GetFinalPathNameByHandleW.argtypes = [
            wintypes.HANDLE,
            wintypes.LPWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        kernel32.GetFinalPathNameByHandleW.restype = wintypes.DWORD
        kernel32.SetFileInformationByHandle.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        kernel32.SetFileInformationByHandle.restype = wintypes.BOOL
        kernel32.ReadFile.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        kernel32.ReadFile.restype = wintypes.BOOL
        kernel32.SetFilePointerEx.argtypes = [
            wintypes.HANDLE,
            ctypes.c_longlong,
            ctypes.POINTER(ctypes.c_longlong),
            wintypes.DWORD,
        ]
        kernel32.SetFilePointerEx.restype = wintypes.BOOL
        kernel32.FindFirstStreamW.argtypes = [
            wintypes.LPCWSTR,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        kernel32.FindFirstStreamW.restype = wintypes.HANDLE
        kernel32.FindNextStreamW.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
        kernel32.FindNextStreamW.restype = wintypes.BOOL
        kernel32.FindClose.argtypes = [wintypes.HANDLE]
        kernel32.FindClose.restype = wintypes.BOOL
        kernel32.GetVolumePathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        kernel32.GetVolumePathNameW.restype = wintypes.BOOL
        kernel32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetDriveTypeW.restype = wintypes.UINT

    def open_handle(
        self,
        path: Path,
        *,
        access: int = FILE_READ_ATTRIBUTES,
        share: int = FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        directory: bool = False,
    ) -> WindowsHandle:
        flags = FILE_FLAG_OPEN_REPARSE_POINT
        if directory:
            flags |= FILE_FLAG_BACKUP_SEMANTICS
        assert kernel32 is not None
        raw = kernel32.CreateFileW(
            _win_path(path), access, share, None, OPEN_EXISTING, flags, None
        )
        value = ctypes.cast(raw, ctypes.c_void_p).value
        if value is None or value == ctypes.c_void_p(-1).value:
            _raise_last_error("CreateFileW", path)
        return WindowsHandle(int(value), path)

    def identity_from_handle(self, handle: WindowsHandle) -> FileIdentity:
        info = BY_HANDLE_FILE_INFORMATION()
        assert kernel32 is not None
        if not kernel32.GetFileInformationByHandle(
            wintypes.HANDLE(handle.value), ctypes.byref(info)
        ):
            _raise_last_error("GetFileInformationByHandle", handle.path)
        capacity = 32768
        buffer = ctypes.create_unicode_buffer(capacity)
        length = kernel32.GetFinalPathNameByHandleW(
            wintypes.HANDLE(handle.value), buffer, capacity, 0
        )
        if length == 0 or length >= capacity:
            _raise_last_error("GetFinalPathNameByHandleW", handle.path)
        modified = (info.ftLastWriteTime.dwHighDateTime << 32) | info.ftLastWriteTime.dwLowDateTime
        return FileIdentity(
            volume_serial=int(info.dwVolumeSerialNumber),
            file_index=(int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow),
            size=(int(info.nFileSizeHigh) << 32) | int(info.nFileSizeLow),
            modified_100ns=modified,
            attributes=int(info.dwFileAttributes),
            link_count=int(info.nNumberOfLinks),
            final_path=_display_final_path(buffer.value),
        )

    def inspect(self, path: Path) -> FileIdentity:
        with self.open_handle(path, directory=path.is_dir()) as handle:
            return self.identity_from_handle(handle)

    def _filesystem_name(self, path: Path) -> str:
        volume_path = ctypes.create_unicode_buffer(32768)
        fs_name = ctypes.create_unicode_buffer(64)
        assert kernel32 is not None
        if not kernel32.GetVolumePathNameW(_win_path(path), volume_path, len(volume_path)):
            _raise_last_error("GetVolumePathNameW", path)
        if kernel32.GetDriveTypeW(volume_path.value) != DRIVE_FIXED:
            raise UnsupportedFilesystemError(f"not a fixed local drive: {path}")
        if not kernel32.GetVolumeInformationW(
            volume_path.value, None, 0, None, None, None, fs_name, len(fs_name)
        ):
            _raise_last_error("GetVolumeInformationW", path)
        return fs_name.value.upper()

    def validate_roots(
        self,
        project: Path,
        recovery: Path,
        *,
        app_state: Path | None = None,
    ) -> ValidatedRoots:
        project = project.absolute()
        recovery = recovery.absolute()
        if not project.is_dir() or not recovery.is_dir():
            raise BoundaryError("project and recovery roots must already exist")
        if project == Path(project.anchor):
            raise BoundaryError("drive roots cannot be selected as projects")
        if recovery == Path(recovery.anchor):
            raise BoundaryError("drive roots cannot be used as recovery storage")
        forbidden = [Path.home(), Path(os.environ.get("WINDIR", "C:/Windows"))]
        for variable in ("ProgramFiles", "ProgramFiles(x86)"):
            if os.environ.get(variable):
                forbidden.append(Path(os.environ[variable]))
        if any(_normal(project) == _normal(path) for path in forbidden):
            raise BoundaryError("the selected project root is protected")
        if _is_within(recovery, project) or _is_within(project, recovery):
            raise BoundaryError("project and recovery roots must not overlap")
        if app_state and (_is_within(project, app_state) or _is_within(app_state, project)):
            raise BoundaryError("the project root overlaps AI-cleaner state")
        if self._filesystem_name(project) != "NTFS" or self._filesystem_name(recovery) != "NTFS":
            raise UnsupportedFilesystemError("mutation requires local NTFS roots")
        self._reject_reparse_chain(project)
        self._reject_reparse_chain(recovery)
        project_id = self.inspect(project)
        recovery_id = self.inspect(recovery)
        if project_id.volume_serial != recovery_id.volume_serial:
            raise UnsupportedFilesystemError("cross-volume recovery is not supported")
        return ValidatedRoots(project, recovery, project_id.volume_serial)

    def validate_project_root(
        self, project: Path, *, app_state: Path | None = None
    ) -> FileIdentity:
        project = project.absolute()
        if not project.is_dir():
            raise BoundaryError("the project root must already exist")
        if project == Path(project.anchor):
            raise BoundaryError("drive roots cannot be selected as projects")
        forbidden = [Path.home(), Path(os.environ.get("WINDIR", "C:/Windows"))]
        for variable in ("ProgramFiles", "ProgramFiles(x86)"):
            if os.environ.get(variable):
                forbidden.append(Path(os.environ[variable]))
        if any(_normal(project) == _normal(path) for path in forbidden):
            raise BoundaryError("the selected project root is protected")
        if app_state and (_is_within(project, app_state) or _is_within(app_state, project)):
            raise BoundaryError("the project root overlaps AI-cleaner state")
        if self._filesystem_name(project) != "NTFS":
            raise UnsupportedFilesystemError("mutation requires a local NTFS project")
        self._reject_reparse_chain(project)
        return self.inspect(project)

    def _reject_reparse_chain(self, path: Path) -> None:
        current = path
        while current != current.parent:
            with self.open_handle(current, directory=True) as handle:
                identity = self.identity_from_handle(handle)
            if identity.attributes & FILE_ATTRIBUTE_REPARSE_POINT:
                raise UnsupportedFilesystemError(f"reparse point is unsupported: {current}")
            current = current.parent

    def validate_candidate(self, path: Path, root: Path) -> FileIdentity:
        root_id = self.inspect(root)
        if not _is_within(path.absolute(), root.absolute()) or path.absolute() == root.absolute():
            raise BoundaryError(f"path is outside the selected project: {path}")
        if any(":" in part for part in path.absolute().parts[1:]):
            raise UnsupportedFilesystemError("alternate data stream paths are unsupported")
        self._reject_reparse_chain(path.parent)
        identity = self.inspect(path)
        if not _is_within(identity.final_path, root_id.final_path):
            raise BoundaryError("final file path escapes the selected project")
        if identity.volume_serial != root_id.volume_serial:
            raise BoundaryError("file crosses the selected project volume boundary")
        unsupported = (
            FILE_ATTRIBUTE_REPARSE_POINT
            | FILE_ATTRIBUTE_OFFLINE
            | FILE_ATTRIBUTE_RECALL_ON_OPEN
            | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
            | FILE_ATTRIBUTE_DIRECTORY
        )
        if identity.attributes & unsupported:
            raise UnsupportedFilesystemError("file attributes are unsupported for mutation")
        if identity.link_count != 1:
            raise UnsupportedFilesystemError("hard-linked files are unsupported for mutation")
        self._reject_extra_streams(path)
        return identity

    def validate_destination(
        self, destination: Path, root: Path, *, expected_volume: int
    ) -> FileIdentity:
        """Validate an absent destination and its existing parent against a root."""
        destination = destination.absolute()
        root = root.absolute()
        if destination.exists():
            raise FileExistsError(destination)
        if not destination.parent.is_dir():
            raise BoundaryError("destination parent must already exist")
        if ":" in destination.name:
            raise UnsupportedFilesystemError("alternate data stream destinations are unsupported")
        self._reject_reparse_chain(root)
        self._reject_reparse_chain(destination.parent)
        root_identity = self.inspect(root)
        parent_identity = self.inspect(destination.parent)
        if not _is_within(parent_identity.final_path, root_identity.final_path):
            raise BoundaryError("destination parent resolves outside the approved root")
        if parent_identity.volume_serial != expected_volume:
            raise UnsupportedFilesystemError("cross-volume move is not supported")
        return parent_identity

    def _reject_extra_streams(self, path: Path) -> None:
        class WIN32_FIND_STREAM_DATA(ctypes.Structure):
            _fields_ = [
                ("StreamSize", ctypes.c_longlong),
                ("cStreamName", wintypes.WCHAR * 296),
            ]

        assert kernel32 is not None
        data = WIN32_FIND_STREAM_DATA()
        handle = kernel32.FindFirstStreamW(_win_path(path), 0, ctypes.byref(data), 0)
        value = ctypes.cast(handle, ctypes.c_void_p).value
        if value is None or value == ctypes.c_void_p(-1).value:
            code = ctypes.get_last_error()
            if code in (38, 87):
                raise UnsupportedFilesystemError("stream enumeration is unavailable")
            _raise_last_error("FindFirstStreamW", path)
        names: list[str] = []
        try:
            names.append(data.cStreamName)
            while kernel32.FindNextStreamW(handle, ctypes.byref(data)):
                names.append(data.cStreamName)
            code = ctypes.get_last_error()
            if code != 38:
                _raise_last_error("FindNextStreamW", path)
        finally:
            kernel32.FindClose(handle)
        if names != ["::$DATA"]:
            raise UnsupportedFilesystemError("alternate data streams are unsupported")

    def open_exclusive_file(self, path: Path) -> WindowsHandle:
        return self.open_handle(path, access=GENERIC_READ | DELETE, share=FILE_SHARE_READ)

    def hash_handle(self, handle: WindowsHandle) -> str:
        assert kernel32 is not None
        position = ctypes.c_longlong(0)
        if not kernel32.SetFilePointerEx(
            wintypes.HANDLE(handle.value), ctypes.c_longlong(0), ctypes.byref(position), 0
        ):
            _raise_last_error("SetFilePointerEx", handle.path)
        digest = hashlib.sha256()
        buffer = ctypes.create_string_buffer(1024 * 1024)
        while True:
            read = wintypes.DWORD()
            if not kernel32.ReadFile(
                wintypes.HANDLE(handle.value), buffer, len(buffer), ctypes.byref(read), None
            ):
                _raise_last_error("ReadFile", handle.path)
            if read.value == 0:
                return digest.hexdigest()
            digest.update(buffer.raw[: read.value])

    def read_handle_prefix(self, handle: WindowsHandle, limit: int) -> bytes:
        """Read at most limit bytes from an already validated, exclusively opened file."""
        if limit < 0:
            raise ValueError("read limit must be non-negative")
        assert kernel32 is not None
        position = ctypes.c_longlong(0)
        if not kernel32.SetFilePointerEx(
            wintypes.HANDLE(handle.value), ctypes.c_longlong(0), ctypes.byref(position), 0
        ):
            _raise_last_error("SetFilePointerEx", handle.path)
        if limit == 0:
            return b""
        buffer = ctypes.create_string_buffer(limit)
        read = wintypes.DWORD()
        if not kernel32.ReadFile(
            wintypes.HANDLE(handle.value), buffer, limit, ctypes.byref(read), None
        ):
            _raise_last_error("ReadFile", handle.path)
        return buffer.raw[: read.value]

    def move_open_file(
        self,
        handle: WindowsHandle,
        destination: Path,
        *,
        expected: FileIdentity,
        destination_root: Path | None = None,
    ) -> FileIdentity:
        observed = self.identity_from_handle(handle)
        if observed != expected:
            raise FileChangedError("file identity or metadata changed before move")
        expected_parent = (
            self.validate_destination(
                destination, destination_root, expected_volume=expected.volume_serial
            )
            if destination_root is not None
            else None
        )
        if destination.exists():
            raise FileExistsError(destination)
        with ExitStack() as stack:
            stack.enter_context(
                self.open_handle(
                    destination.parent.parent,
                    directory=True,
                    access=FILE_READ_ATTRIBUTES | DELETE,
                    share=FILE_SHARE_READ,
                )
            )
            parent = stack.enter_context(self.open_handle(destination.parent, directory=True))
            parent_id = self.identity_from_handle(parent)
            if expected_parent is not None and parent_id != expected_parent:
                raise FileChangedError("destination parent changed before move")
            if parent_id.volume_serial != expected.volume_serial:
                raise UnsupportedFilesystemError("cross-volume move is not supported")
            # SetFileInformationByHandle currently rejects its documented relative-name/
            # RootDirectory form on some Windows builds. Holding the validated parent
            # handle without delete sharing prevents parent replacement while the same
            # documented API renames the already-open source to an absolute path.
            name_bytes = _win_path(destination).encode("utf-16-le")
            size = (
                FILE_RENAME_INFO.FileName.offset
                + len(name_bytes)
                + ctypes.sizeof(wintypes.WCHAR)
            )
            raw = ctypes.create_string_buffer(size)
            rename = FILE_RENAME_INFO.from_buffer(raw)
            rename.ReplaceIfExists = False
            rename.RootDirectory = None
            rename.FileNameLength = len(name_bytes)
            ctypes.memmove(
                ctypes.addressof(raw) + FILE_RENAME_INFO.FileName.offset,
                name_bytes,
                len(name_bytes),
            )
            assert kernel32 is not None
            if not kernel32.SetFileInformationByHandle(
                wintypes.HANDLE(handle.value),
                FILE_RENAME_INFO_CLASS,
                raw,
                size,
            ):
                _raise_last_error("SetFileInformationByHandle(rename)", handle.path)
        return self.identity_from_handle(handle)

    def delete_open_file(self, handle: WindowsHandle, *, expected: FileIdentity) -> None:
        if self.identity_from_handle(handle) != expected:
            raise FileChangedError("payload identity or metadata changed before purge")
        disposition = FILE_DISPOSITION_INFO(True)
        assert kernel32 is not None
        if not kernel32.SetFileInformationByHandle(
            wintypes.HANDLE(handle.value),
            FILE_DISPOSITION_INFO_CLASS,
            ctypes.byref(disposition),
            ctypes.sizeof(disposition),
        ):
            _raise_last_error("SetFileInformationByHandle(delete)", handle.path)

    def guarded_move(
        self,
        source: Path,
        destination: Path,
        *,
        root: Path,
        destination_root: Path,
        expected: FileIdentity,
        expected_sha256: str,
    ) -> FileIdentity:
        self.validate_candidate(source, root)
        with ExitStack() as stack:
            handle = stack.enter_context(self.open_exclusive_file(source))
            if self.identity_from_handle(handle) != expected:
                raise FileChangedError("file changed since proposal preparation")
            if self.hash_handle(handle) != expected_sha256:
                raise FileChangedError("file content changed since proposal preparation")
            return self.move_open_file(
                handle,
                destination,
                expected=expected,
                destination_root=destination_root,
            )
