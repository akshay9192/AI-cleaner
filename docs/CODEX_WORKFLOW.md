# Cooperative Codex workflow

AI-cleaner uses explicit task snapshots and declarations. It does not parse private Codex databases or claim that timing proves which process created a file.

From the selected project directory, start a task before work begins:

```powershell
uv run ai-cleaner task start --root "C:\Projects\Example" --label "Report revision"
```

Keep disposable render/cache outputs in a designated project scratch directory. Preserve maintainable source, original inputs, configuration, and final deliverables. Register relevant paths using the returned task ID:

```powershell
uv run ai-cleaner task register --task TASK_ID --path "scratch\preview.png" --role scratch
uv run ai-cleaner task register --task TASK_ID --path "final\report.pdf" --role deliverable
uv run ai-cleaner task register --task TASK_ID --path "inputs\source.csv" --role input
```

Scratch registration is only a declaration and cannot override built-in protection. Deliverables and inputs are protected. Finish the task to capture the end snapshot:

```powershell
uv run ai-cleaner task finish --task TASK_ID
uv run ai-cleaner propose --root "C:\Projects\Example" --task TASK_ID
uv run ai-cleaner gui --root "C:\Projects\Example"
```

The diff labels additions as **observed during task**, not “created by Codex.” Pre-existing modified files remain protected. An active or interrupted task blocks cleanup proposal preparation. The CLI can inventory, record metadata, and prepare a proposal, but it cannot approve or execute quarantine, restore, or purge. Do not add `--yes`, fabricate approval input, modify global Codex configuration, or install hooks.
