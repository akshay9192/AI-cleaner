# Safety boundary

AI-cleaner v0.1 intentionally supports mutation only for individual ordinary files in a user-selected local NTFS project, with recovery storage on the same volume. It is not a whole-PC cleaner and does not control deletion performed independently by another program or privileged agent.

## Filesystem adapter

The Windows adapter uses `ctypes` bindings to documented Win32 handle APIs. It obtains volume/file identity with `GetFileInformationByHandle`, verifies the final handle path, hashes the open file while denying competing write/delete access, and renames or marks the already-open file through `SetFileInformationByHandle`. Destination parent identity is checked while handles prevent replacement of the relevant ancestor. Existing destinations are never replaced.

The documented `FILE_RENAME_INFO` relative-name/`RootDirectory` form returned `ERROR_INVALID_PARAMETER` on the validated Windows build. The implementation therefore uses the documented absolute-name form while holding both the verified destination parent and an exclusive ancestor handle. Native tests cover parent replacement and same-volume moves.

Mutation fails closed for symlinks, junctions and other reparse points; alternate data streams; hard links; cloud/offline placeholders; non-regular files; drive roots; overlapping roots; cross-volume paths; non-NTFS or non-fixed volumes; inaccessible or locked files; and identity, metadata, or content changes. Directory trees are never recursively deleted.

Scanning reads metadata only and never intentionally writes inspected files. It does not follow
reparse points, has a default 100,000-entry bound, and reports cancellation, limits, and access
errors as incomplete results. A file being old, untracked, ignored, AI-adjacent, or named like a
temporary file is not proof that it can be removed. Unknown classifications remain unselectable.
The app state, recovery storage, VCS metadata, credentials, configurations, source, original
inputs, and user pins are protected by default.

## Approval boundary

Scanning, preview, tracking, registration, and completion do not mutate inspected user files. A
cleanup proposal is an exact immutable list. Production code creates an ephemeral, single-use
capability only after interactive terminal review shows the exact selection, count, logical size,
recovery destination, and digest and receives the matching typed confirmation. Every candidate
defaults to keep. Completion is analysis authorisation, not cleanup approval.

Both stdin and stdout must be TTYs. Piped answers, redirected input, EOF, serialized approval,
agent-supplied booleans, and automated `--yes`/`--force` modes cannot approve supported mutation.
Non-interactive completion stores a pending proposal, moves nothing, exits 6, and shows the exact
interactive review command. The TTY check is a practical interaction safeguard, not proof that a
human is present against malware or a privileged process controlling the same account or terminal.

Cancellation or missing, stale, expired, replayed, previously executed, or mismatched approval
fails closed. The entire exact plan is revalidated before its first mutation. Restore is
non-overwriting and collision alternatives are included in the reviewed digest. Purge has a
separate plan and fresh irreversible confirmation and applies only to verified app-owned payloads;
retention age is only a reminder.

These safeguards reduce accidental deletion through supported interfaces. They are not a security boundary against malware or a process with unrestricted access to the same Windows account, UI, files, or application code.

AI-cleaner records logical bytes moved into recovery separately from logical payload bytes
permanently removed. It does not claim those values are physical free-space changes; compressed
files, sparse files, allocation units, and concurrent disk activity make such an inference
unreliable. Retention age creates a review reminder only and never schedules a purge. Recovery
storage is not the Windows Recycle Bin.

All processing is local. The application contains no telemetry, network client, cloud account,
or external AI integration, and it never sends file paths or contents elsewhere. Text preview is
explicit, read-only, and limited to 64 KiB; binary content is not rendered or executed.
