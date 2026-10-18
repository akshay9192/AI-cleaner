# Validation record

This file records observed checks; it is not a claim of zero data-loss risk. Mutation tests use
only disposable fixtures. Native results apply only to Windows 11 x64 and local NTFS; they do not
establish support for macOS, Linux, network filesystems, FAT/exFAT, cloud placeholders, or
cross-volume mutation.

## Terminal-first revision

The owner replaced the desktop/PyInstaller product with a terminal-first tool on 18 October 2026.
The earlier nine Qt tests, GUI smoke, and PyInstaller build are preserved as historical evidence
but are superseded release gates, not current passes. Core scanner, policy, task, proposal,
filesystem, journal, quarantine, recovery, and purge evidence remains relevant where those modules
were unchanged. Terminal approval, proposal lifecycle, whole-plan preflight, both entry points,
and updated CLI behavior require current evidence.

## Reproduce

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe src
.\.venv\Scripts\pytest.exe -p no:cacheprovider
.\.venv\Scripts\ai-cleaner.exe --help
.\.venv\Scripts\python.exe scripts\project_cleanup.py --help
```

The repository script uses the checkout's `src` tree and is not standalone. A normal user install
is `python -m pip install -e .` followed by `ai-cleaner --help`.

## Current terminal results

The final terminal-focused run in this managed session recorded:

- Ruff passed for the new CLI/script after formatting.
- mypy 2.4.0 strict mode passed for 22 source files after removing the UI package.
- Unit, integration, and terminal orchestration tests: 51 passed in 10.87 seconds on the final run.
- `python -m pip install -e . --no-deps` completed and rebuilt the editable installation.
- Both the installed `ai-cleaner --help` entry point and repository script help completed.
- Disposable terminal tests covered non-interactive pending review, protected deliverables,
  task completion, exact quarantine, truthful bytes, restore, default keep/protect, and separately
  reviewed purge.

The terminal orchestration tests patch only `_reject_reparse_chain` because this managed runner
denies opening the profile ancestor `C:\Users\aksha`. Actual disposable file hashing, guarded
moves, journaling, recovery, and deletion still execute. This patch is test-only and is not exposed
by the CLI. It is not evidence for ancestor-chain protection; that remains environment-blocked in
the current session and historically covered by the native Windows tests.

## Historical results and current boundary

On 17 October 2026 the desktop-era implementation recorded 62 passing tests on Windows/NTFS,
including the native filesystem suite and nine Qt tests. On 18 October, before the design change,
a full rerun collected 62 tests: 18 passed and 44 failed at the managed `CreateFileW` denial on
`C:\Users\aksha`, before the affected behavior ran. `C:\tmp` was also not writable. Those 44 are
environment-blocked checks, not passes or established product regressions.

PowerShell resolves only
`C:\Users\aksha\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe`.
This session is denied access to its ACL, signature, streams, hash, and execution; `where.exe uv`
finds no executable and no competing normal installation exists. Evidence points to the managed
Codex boundary, not a stale path or demonstrated Windows application-control decision. No security
settings were changed and `uv` was not reinstalled. The lock root metadata was updated manually
for the removed desktop dependencies, but `uv sync --frozen` cannot be rerun in this session.

The BMAD renderer previously failed through that boundary and, per its instructions, was not
rerun. BMAD automation was unavailable; no BMAD review or verification is claimed. Standard plan
review, bounded parallel audits, diff inspection, static analysis, and direct workspace-local
verification were used instead.

## Manual disposable terminal journey

1. Create a new disposable NTFS project and a separate same-volume state/recovery location.
2. Run `ai-cleaner start --root <fixture> --label "fixture"`.
3. Register a scratch artifact and protect a deliverable, then create both files.
4. Run `ai-cleaner complete --root <fixture>` in a human terminal.
5. Verify every candidate defaults to keep; select only the scratch item and inspect the final
   paths, reasons, count, bytes, recovery destination, and digest.
6. Enter the exact requested `MOVE <digest-prefix>` phrase. Verify the deliverable remains and the
   result reports quarantined bytes, not reclaimed bytes.
7. Run the printed `ai-cleaner restore --run RUN_ID`, confirm the exact restore, and compare bytes.
8. Quarantine again, then run `ai-cleaner purge --run RUN_ID`; verify the separate irreversible
   review removes only the selected recovery payload.

Never substitute a real Downloads, Documents, home, repository, or assignment directory for this
fixture.
