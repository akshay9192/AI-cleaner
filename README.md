# AI-cleaner

AI-cleaner is a Windows-first terminal tool for tracking task artifacts, reviewing conservative
cleanup suggestions, and moving only human-approved files into recoverable storage. Quarantine
does not reclaim disk space. Restore and permanent purge are separate actions.

The v0.1 implementation is local: no desktop window, browser, account, API key, telemetry,
network service, or LLM is required.

## Requirements and installation

- Windows 11 x64 with a local NTFS project folder
- CPython 3.12
- Git is optional, but enables tracked-file protection

Install the command from this checkout:

```powershell
py -3.12 -m venv .venv
& ".\.venv\Scripts\Activate.ps1"
python -m pip install -e .
ai-cleaner doctor
ai-cleaner --help
```

The repository wrapper uses the same implementation without duplicating cleanup logic:

```powershell
python scripts/project_cleanup.py --help
```

The wrapper is not standalone; it requires this checkout and its `src` tree. Copying only the
wrapper file does not install AI-cleaner.

## Tracked task workflow

```powershell
ai-cleaner start --root . --label "Implement feature"
ai-cleaner register --root . --path "scratch\preview.aux" --role scratch
ai-cleaner protect --root . --path "dist\final-output.zip"
# Work normally, then explicitly signal completion:
ai-cleaner complete --root .
```

`complete` records the end state and prepares a proposal. It does not approve cleanup. In a real
interactive terminal, review defaults every candidate to keep and requires an exact final
confirmation. Without an interactive stdin and stdout, it moves nothing, exits 6, stores the
pending proposal, and prints the command to run later:

```powershell
ai-cleaner review --proposal PROPOSAL_ID
```

After quarantine, the result prints a run ID:

```powershell
ai-cleaner history --root .
ai-cleaner restore --run RUN_ID
ai-cleaner purge --run RUN_ID
```

Restore never overwrites an occupied destination. Purge has its own irreversible review and fresh
confirmation. There is no `--yes`, `--force`, piped-answer approval, or unattended mutation mode.

For an untracked folder, use `ai-cleaner preview --root .`. It can identify conservative existing
clutter candidates but cannot establish historical ownership without a task baseline.

State is stored in `%LOCALAPPDATA%\AI-cleaner` by default. Recovery must be on the same supported
volume as the selected project and outside it.

## Development verification

With the locked development environment already synchronized:

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe src
.\.venv\Scripts\pytest.exe
```

See `docs/SAFETY.md`, `docs/CODEX_WORKFLOW.md`, `docs/VALIDATION.md`, and
`AI_CLEANER_PROJECT_PLAN.md` for the exact safety boundary and recorded evidence.
