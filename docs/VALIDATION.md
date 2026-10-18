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
is `python -m pip install .` followed by `ai-cleaner --help`; use `-e` only for development.

## Current popup/script results

The current popup/script-focused runs in this managed session recorded:

- Ruff passed after correcting the acceptance helper's import order.
- mypy 2.4.0 strict mode passed for 23 source files.
- Unit, integration, and workflow tests: 58 passed in 18.79 seconds with the documented temporary
  managed-boundary shim. The shim was removed immediately afterward.
- The unmodified full suite collected 66 tests: 29 passed and 37 stopped at the managed
  `CreateFileW` denial on the user-profile ancestor. These are blocked checks, not product failures
  or passes.
- `python -m pip install -e . --no-deps` completed and rebuilt the editable installation.
- The root `ai_cleaner.py`, installed `ai-cleaner`, and compatibility script help/version checks completed.
- Disposable tests covered missing-popup pending review, baseline rejection, fingerprinted
  registration, changed/unregistered retention, protected descendants, task completion, exact
  quarantine, truthful bytes, restore, keep/protect/cancel, and separately reviewed purge.
- Tkinter was available and the production review window displayed during a smoke attempt. It was
  closed without agent approval; production mutation was not exercised through the real popup.
- Cancelling a cleanup review now prints the exact proposal review command. A regression test
  confirms that the proposal remains available and the candidate remains untouched.

## User-performed external Windows validation

On 18 October 2026, the owner reported these results from an ordinary external Windows session.
They are user-performed evidence, not checks executed or independently observed by the finalizing
agent:

- the unmodified suite passed all 66 tests in 13.95 seconds using a fresh, unique pytest
  `--basetemp` directory;
- real popup quarantine and restore succeeded; protected baseline files and the deliverable
  remained present, and the restored preview contained its expected text;
- cancelling the popup retained the temporary file and its expected contents;
- a separate human-approved purge succeeded for the synthetic 24-byte payload;
- `doctor --json` returned status `ok`;
- `uv lock` completed and `git diff -- uv.lock` showed no unstaged changes; and
- after moving the broken `pip-24.2.dist-info` metadata aside, `uv sync --frozen --group dev`
  succeeded and `uv pip check` checked 16 packages and reported all installed packages compatible.

This evidence closes the current native suite, real popup journey, lock/frozen-sync, and package
compatibility checks. It does not erase the historical failures below, verify BMAD, or cover the
six implementation gaps found by the subsequent quick review.

## Finalization quick-review boundary

Inspection after the external run found six untested contract gaps: no supported project-specific
same-volume recovery setup, incomplete hard-protection coverage for common source/configuration
types, no Git-state reclassification immediately before mutation, a replaceable destination
parent during the final move, different locks for quarantine versus restore/purge, and
reconciliation methods that no startup or CLI path invokes. Passing checks remain valid for the
paths they exercised, but the affected safety and final-audit gates remain in progress. Details are
recorded in `IMPLEMENTATION_STATUS.md` and `_bmad-output/deferred-work.md`.

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
revision, the earlier native 63-test run recorded 27 passes and 36 failures. The 18 October
native-acceptance rerun collected 66 tests and recorded 29 passes plus 37 failures. All blocked
failures reached the same ancestor access denial before the affected behavior ran.

PowerShell resolves only
`%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe`.
This session is denied access to its ACL, signature, streams, hash, and execution; `where.exe uv`
finds no executable and no competing normal installation exists. Evidence points to the managed
Codex boundary, not a stale path or demonstrated Windows application-control decision. No security
settings were changed and `uv` was not reinstalled. The lock root metadata matches
`pyproject.toml`: Python 3.12, no runtime dependencies, and the same four development dependency
constraints. The lock still contains unreachable desktop-era package records, including PySide6
and PyInstaller families. They are not root dependencies and were not installed by the clean
product install, but generated lock data was not hand-edited again. `uv lock` and
`uv sync --frozen` cannot run in this session, so clean regeneration and frozen validation remain
blocked.

An earlier BMAD renderer attempt failed through that boundary and, per its instructions for that
run, was not rerun. A later finalization workflow rendered successfully, but its delegated runner
encountered the same access denial. No completed BMAD review or verification is claimed.

## Native fixture and human popup journey

`scripts/prepare_acceptance_fixture.py` successfully created the ignored
`.ai-cleaner-acceptance/native-popup` fixture with two synthetic projects, separate same-volume
state directories, baseline inputs, and repository-local agent instructions. No real project file
is a cleanup target. The exact cancel/review/quarantine/restore journey and separate purge journey
are in `docs/NATIVE_ACCEPTANCE.md`.

At the managed-session handoff, the agent had not selected or approved any production popup and
those checks remained pending. The owner subsequently completed them as user-performed external
validation, recorded above.

## Clean install and external-directory checks

A new Python 3.12.6 virtual environment was created under the ignored acceptance directory and
`python -m pip install --no-deps .` built and installed `ai-cleaner-0.1.0` successfully. Hatchling
was downloaded only as the declared isolated build backend; pip and project dependencies were not
upgraded. From the separate synthetic project directory:

- installed `ai-cleaner --version` returned `0.1.0`;
- installed `ai-cleaner doctor --json` returned status `ok` on Windows 11 / Python 3.12.6;
- `pip check` reported no broken requirements and installed metadata reported no runtime requirements;
- `ai_cleaner.__file__` resolved inside that clean environment's `site-packages`;
- the checkout root script's help worked through an absolute path; and
- installed `ai-cleaner start` reached the native safety adapter, then was blocked only by the
  managed runner's user-profile ancestor denial.

These were the remaining external checks at the managed-session handoff and remain useful
reproduction commands:

```powershell
Set-Location "C:\path\to\AI-cleaner"
.\.venv\Scripts\pytest.exe -p no:cacheprovider
uv lock
git diff -- uv.lock
uv sync --frozen --group dev
```

The owner subsequently reported that the suite, stable-lock check, frozen dev sync, and human popup
journey passed as recorded above. BMAD remains unverified.

Never substitute a real Downloads, Documents, home, repository, or assignment directory for this
fixture.
