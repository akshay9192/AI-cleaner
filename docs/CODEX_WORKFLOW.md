# Repository agent instruction

Use this snippet in the repository task context; do not install global hooks:

> Before generating task artifacts, run `python ai_cleaner.py start --root . --label "TASK"` and
> retain the returned task ID. After creating a disposable output, run `python ai_cleaner.py
> register-temp --task TASK_ID --path PATH`. Protect final deliverables or directories with `python
> ai_cleaner.py protect --task TASK_ID --path PATH`. When the user explicitly says the task is
> finished, invoke `python ai_cleaner.py complete --task TASK_ID`. At normal completion, invoke it
> only if the user enabled this convention. If no popup is available, leave the pending proposal
> untouched and report its exact review command. Never select files, confirm a popup, purge, or
> otherwise approve cleanup on the user's behalf.

Registration is a declaration, not proof that an agent created a file. Register a temporary only
after writing it; later modifications require re-registration before completion. Existing files,
unregistered outputs, maintainable source, and final deliverables remain protected.

AI-cleaner does not listen for arbitrary natural-language completion, parse private agent logs,
watch terminal input, infer completion from Git, or run a background monitor.

For native acceptance only, `scripts/prepare_acceptance_fixture.py` creates an ignored synthetic
project with a repository-local `AGENTS.md` containing the same rules. It does not modify global
Codex or other agent configuration. See `docs/NATIVE_ACCEPTANCE.md` for the exact journey.

BMAD is a development workflow, not a runtime dependency. Its renderer remained unavailable in
the 18 October 2026 managed session because the resolved WinGet `uv.exe` could not be accessed. It
was not rerun or bypassed, and no BMAD check is claimed.
