# AI-cleaner

AI-cleaner is a Windows-first desktop application for reviewing project artifacts before moving selected files into recoverable storage. Quarantine does not reclaim disk space. Permanent removal is a separate, explicitly confirmed action.

The v0.1 implementation follows `AI_CLEANER_PROJECT_PLAN.md`. It runs locally without accounts, telemetry, API keys, or network services.

## Development setup

Requirements: Windows 11 x64, Python 3.12, Git, and [uv](https://docs.astral.sh/uv/).

```powershell
uv sync --frozen --all-groups
uv run ai-cleaner doctor
uv run ai-cleaner --help
uv run ai-cleaner gui
```

The CLI is read-only with respect to selected project files. Cleanup, restore, and purge confirmation are available only through the desktop interface.

## Verification

```powershell
uv run ruff check .
uv run mypy src
uv run pytest
```

See `docs/SAFETY.md`, `docs/CODEX_WORKFLOW.md`, and `docs/VALIDATION.md` for the supported boundary and recorded checks.
