# Safety boundary

AI-cleaner v0.1 intentionally supports mutation only for individual ordinary files in a user-selected local NTFS project, with recovery storage on the same volume. It is not a whole-PC cleaner and does not control deletion performed independently by another program or privileged agent.

## Filesystem adapter

The Windows adapter uses `ctypes` bindings to documented Win32 handle APIs. It obtains volume/file identity with `GetFileInformationByHandle`, verifies the final handle path, hashes the open file while denying competing write/delete access, and renames or marks the already-open file through `SetFileInformationByHandle`. Destination parent identity is checked while handles prevent replacement of the relevant ancestor. Existing destinations are never replaced.

The documented `FILE_RENAME_INFO` relative-name/`RootDirectory` form returned `ERROR_INVALID_PARAMETER` on the validated Windows build. The implementation therefore uses the documented absolute-name form while holding both the verified destination parent and an exclusive ancestor handle. Native tests cover parent replacement and same-volume moves.

Mutation fails closed for symlinks, junctions and other reparse points; alternate data streams; hard links; cloud/offline placeholders; non-regular files; drive roots; overlapping roots; cross-volume paths; non-NTFS or non-fixed volumes; inaccessible or locked files; and identity, metadata, or content changes. Directory trees are never recursively deleted.

## Approval boundary

Scanning and CLI metadata commands do not mutate inspected user files. A cleanup proposal is an exact immutable list, and only an ephemeral, single-use capability created by the desktop confirmation can authorize quarantine. Cancellation or missing, stale, expired, replayed, or mismatched approval fails closed. Restore is non-overwriting. Purge has a separate proposal and confirmation and applies only to verified app-owned payloads; retention age is only a reminder.

These safeguards reduce accidental deletion through supported interfaces. They are not a security boundary against malware or a process with unrestricted access to the same Windows account, UI, files, or application code.
