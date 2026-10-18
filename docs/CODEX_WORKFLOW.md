# Codex and BMAD workflow

Use AI-cleaner cooperatively; do not parse private agent logs or install global hooks.

Before work starts:

```powershell
ai-cleaner start --root . --label "Short task description"
```

During work, declare intermediates and protect useful outputs. Declarations are evidence supplied
by the agent or user, not proof that the agent created a file, and scratch declarations cannot
override hard protections.

```powershell
ai-cleaner register --root . --path "scratch\preview.aux" --role scratch
ai-cleaner protect --root . --path "dist\final-output.zip"
```

When the work is genuinely complete, invoke the explicit completion signal once:

```powershell
ai-cleaner complete --root .
```

Completion records the end snapshot and prepares cleanup; it is not approval. If the command is
running without an interactive human terminal, leave the pending proposal unchanged and show its
review command:

```powershell
ai-cleaner review --proposal PROPOSAL_ID
```

An agent must never approve cleanup, supply piped confirmation, or invoke restore/purge approval
on the user's behalf. Only the human terminal review may select files and confirm the exact digest.
Keep maintainable source and final outputs outside disposable scratch locations.

BMAD is a development workflow, not an application dependency. In the 18 October 2026 managed
session its renderer remained unavailable because the resolved WinGet `uv.exe` could not be read
or executed; it was not rerun contrary to its instructions. Standard planning, review, and
verification continued, and no BMAD check is claimed for that continuation.
