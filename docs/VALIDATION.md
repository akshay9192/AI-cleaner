# Validation record

This file records observed checks; it is not a claim of zero data-loss risk. Mutation tests use
only disposable fixtures. Native results apply only to Windows 11 x64 and local NTFS; they do not
establish support for macOS, Linux, network filesystems, FAT/exFAT, cloud placeholders, or
cross-volume mutation.

## Minimal popup revision

The owner replaced the desktop/PyInstaller product with a minimal Python script and tkinter popup
on 18 October 2026. An intermediate terminal-only design was also superseded.
The earlier nine Qt tests, GUI smoke, and PyInstaller build are preserved as historical evidence
but are superseded release gates, not current passes. Core scanner, policy, task, proposal,
filesystem, journal, quarantine, recovery, and purge evidence remains relevant where those modules
were unchanged. Popup approval, fingerprinted registration, proposal lifecycle, whole-plan
preflight, script entry points, and updated CLI behavior require current evidence.

## Reproduce

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe src
.\.venv\Scripts\pytest.exe -p no:cacheprovider
.\.venv\Scripts\python.exe ai_cleaner.py --help
.\.venv\Scripts\ai-cleaner.exe --help
.\.venv\Scripts\python.exe scripts\project_cleanup.py --help
```

The root script uses the checkout's `src` tree and is not standalone. A normal user install
is `python -m pip install -e .` followed by `ai-cleaner --help`.

## Current popup/script results

The current popup/script-focused run in this managed session recorded:

- Ruff passed for the new CLI/script after formatting.
- mypy 2.4.0 strict mode passed for 23 source files.
- Unit, integration, and workflow tests: 58 passed in 25.02 seconds on the final managed-boundary run.
- `python -m pip install -e . --no-deps` completed and rebuilt the editable installation.
- The root `ai_cleaner.py`, installed `ai-cleaner`, and compatibility script help/version checks completed.
- Disposable tests covered missing-popup pending review, baseline rejection, fingerprinted
  registration, changed/unregistered retention, protected descendants, task completion, exact
  quarantine, truthful bytes, restore, keep/protect/cancel, and separately reviewed purge.
- Tkinter was available and the production review window displayed during a smoke attempt. It was
  closed without agent approval; production mutation was not exercised through the real popup.

The workflow orchestration tests patch only `_reject_reparse_chain` because this managed runner
denies opening the user-profile ancestor. Actual disposable file hashing, guarded
moves, journaling, recovery, and deletion still execute. This patch is test-only and is not exposed
by the CLI. It is not evidence for ancestor-chain protection; that remains environment-blocked in
the current session and historically covered by the native Windows tests.

## Historical results and current boundary

On 17 October 2026 the desktop-era implementation recorded 62 passing tests on Windows/NTFS,
including the native filesystem suite and nine Qt tests. On 18 October, before the design change,
a full rerun collected 62 tests: 18 passed and 44 failed at the managed `CreateFileW` denial on
the user-profile ancestor, before the affected behavior ran. `C:\tmp` was also not writable. Those 44 are
environment-blocked checks, not passes or established product regressions. After the popup
revision, the native 63-test run recorded 27 passes and 36 failures, all at the same ancestor
access denial before the affected behavior ran.

PowerShell resolves only
`%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe`.
This session is denied access to its ACL, signature, streams, hash, and execution; `where.exe uv`
finds no executable and no competing normal installation exists. Evidence points to the managed
Codex boundary, not a stale path or demonstrated Windows application-control decision. No security
settings were changed and `uv` was not reinstalled. The lock root metadata was updated manually
for the removed desktop dependencies, but `uv sync --frozen` cannot be rerun in this session.

The BMAD renderer previously failed through that boundary and, per its instructions, was not
rerun. BMAD automation was unavailable; no BMAD review or verification is claimed. Standard plan
review, bounded parallel audits, diff inspection, static analysis, and direct workspace-local
verification were used instead.

## Manual disposable popup journey

1. Create a new disposable NTFS project and a separate same-volume state/recovery location.
2. Run `python ai_cleaner.py start --root <fixture> --label "fixture"`.
3. Create a scratch artifact, register it with `register-temp`, and protect a deliverable.
4. Run `python ai_cleaner.py complete --task TASK_ID` in a graphical user session.
5. Verify every checkbox defaults to keep; select only the scratch item and inspect the final
   paths, reasons, count, bytes, recovery destination, and digest.
6. Approve the separate exact confirmation popup. Verify the deliverable remains and the
   result reports quarantined bytes, not reclaimed bytes.
7. Run `python ai_cleaner.py restore --run RUN_ID`, confirm the exact restore, and compare bytes.
8. Quarantine again, then run `python ai_cleaner.py purge --run RUN_ID`; verify the separate irreversible
   review removes only the selected recovery payload.

Never substitute a real Downloads, Documents, home, repository, or assignment directory for this
fixture.
