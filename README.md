# AI-cleaner

AI-cleaner is a small Windows-first Python tool for tracking declared temporary task artifacts.
It does not try to identify every file ever created by AI. Only a file created after the task
baseline, explicitly registered after creation, unchanged since registration, and free of all
protections can appear as a cleanup candidate.

Approved files move to recoverable same-volume quarantine. This removes workspace clutter but does
not reclaim disk space; only a separately approved purge can do that.

## Requirements and setup

- Windows 11 x64 and a local NTFS project folder
- CPython 3.12 with standard-library tkinter available for popup approval

From this checkout:

```powershell
py -3.12 -m venv .venv
& ".\.venv\Scripts\Activate.ps1"
python -m pip install .
ai-cleaner doctor
```

For source development, use `python -m pip install -e .` instead. A normal installation provides
the `ai-cleaner` command from other directories. The root script imports the package from this
checkout; it is an entry point, not a portable standalone script:

```powershell
python ai_cleaner.py doctor
```

The root script is the primary interface. The installed `ai-cleaner` command and
`scripts/project_cleanup.py` are compatibility entry points using the same implementation; none is
a standalone file when copied away from the package.

## Complete example

```powershell
$task = python ai_cleaner.py start --root . --label "Build report" | ConvertFrom-Json

# Create scratch\preview.aux first, then fingerprint it as disposable:
python ai_cleaner.py register-temp --task $task.task_id --path "scratch\preview.aux"

# A file or directory protected here, including descendants, cannot be cleaned:
python ai_cleaner.py protect --task $task.task_id --path "dist\final-report.pdf"

python ai_cleaner.py complete --task $task.task_id
```

`complete` captures the ending state and opens a compact popup. Candidate checkboxes start
unchecked. The popup can keep/protect selected files, move selected files to quarantine, or cancel.
A second popup confirms the exact paths, count, size, recovery destination, and proposal digest.

If tkinter or a graphical display is unavailable, nothing moves. The proposal remains pending,
the command exits 6, and it prints:

```powershell
python ai_cleaner.py review --proposal PROPOSAL_ID
```

After quarantine, use the reported run ID:

```powershell
python ai_cleaner.py restore --run RUN_ID
python ai_cleaner.py purge --run RUN_ID
```

Restore verifies the payload and never overwrites an occupied destination. Purge opens its own
unchecked review and irreversible confirmation. There is no `--yes`, automatic approval, timeout
approval, or agent-facing approval bypass.

## Protection and limitations

Files present at task start, unregistered files, modified registrations, protected directory
descendants, source/tests/docs/plans/configuration/lockfiles, credentials, Git metadata, and the
cleaner's state/recovery data are retained. Source-like scratch files remain protected even when
registered in this release. Symlinks, junctions, hard links, alternate streams, unsupported
filesystems, broad roots, and path/identity races fail closed.

The popup is an intentional-consent mechanism, not a security boundary against malicious software
running as the same user. AI-cleaner does not monitor speech, terminal text, private agent logs,
Git commits, or background processes.

## Agent completion convention

Add the repository-local guidance in `docs/CODEX_WORKFLOW.md` to the task context. In short: start
tracking first; register disposable outputs after creating them; protect deliverables; invoke
`complete` when the user explicitly says the task is finished (or at normal completion only when
the user enabled that convention); and never approve the popup for the user.

## Development checks

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe src
.\.venv\Scripts\pytest.exe -p no:cacheprovider
```

See `docs/SAFETY.md`, `docs/VALIDATION.md`, and `IMPLEMENTATION_STATUS.md` for the supported boundary
and current blocked native checks.

For the isolated, synthetic popup journey and the few clicks that must be performed by a human,
follow `docs/NATIVE_ACCEPTANCE.md`.
