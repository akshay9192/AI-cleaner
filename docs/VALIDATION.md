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

The BMAD renderer previously failed through that boundary and, per its instructions, was not
rerun. BMAD automation was unavailable; no BMAD review or verification is claimed. Standard plan
review, bounded parallel audits, diff inspection, static analysis, and direct workspace-local
verification were used instead.

## Native fixture and human popup journey

`scripts/prepare_acceptance_fixture.py` successfully created the ignored
`.ai-cleaner-acceptance/native-popup` fixture with two synthetic projects, separate same-volume
state directories, baseline inputs, and repository-local agent instructions. No real project file
is a cleanup target. The exact cancel/review/quarantine/restore journey and separate purge journey
are in `docs/NATIVE_ACCEPTANCE.md`.

The agent has not selected or approved any production popup. Native start, popup mutation,
restore, and purge remain pending in an ordinary interactive PowerShell session.

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

Run these remaining checks in an ordinary PowerShell session without changing security settings:

```powershell
Set-Location "C:\path\to\AI-cleaner"
.\.venv\Scripts\pytest.exe -p no:cacheprovider
uv lock
git diff -- uv.lock
uv sync --frozen --group dev
```

Review the lock diff before committing it; the intended change is removal of unreachable records,
not dependency upgrades. Do not rerun the failed BMAD renderer. Then follow
`docs/NATIVE_ACCEPTANCE.md` for the human popup journey.

Never substitute a real Downloads, Documents, home, repository, or assignment directory for this
fixture.
