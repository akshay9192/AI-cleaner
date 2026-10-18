- source_plan: `_bmad-output/plan-implement-ai-cleaner-v0-1.md`
  summary: Add supported project-level selection of a same-volume recovery root.
  evidence: The global state recovery path can be cross-volume from a valid project, and the CLI has no project-level setup flow.
- source_plan: `_bmad-output/plan-implement-ai-cleaner-v0-1.md`
  summary: Expand deterministic hard protection to the source and configuration types promised by the contract.
  evidence: Common source and configuration files can currently become selectable when registered as temporary.
- source_plan: `_bmad-output/plan-implement-ai-cleaner-v0-1.md`
  summary: Revalidate Git tracking and full classification immediately before quarantine.
  evidence: A file added to Git after proposal preparation can retain the same identity and hash and still be moved.
- source_plan: `_bmad-output/plan-implement-ai-cleaner-v0-1.md`
  summary: Hold the actual validated destination parent against replacement through the final rename.
  evidence: The current parent handle allows delete sharing, so the checked directory can be replaced during the race-sensitive move.
- source_plan: `_bmad-output/plan-implement-ai-cleaner-v0-1.md`
  summary: Use one shared conflict lock for quarantine, restore, and purge operations affecting the same project.
  evidence: Project-specific quarantine locks and the global recovery lock do not exclude each other.
- source_plan: `_bmad-output/plan-implement-ai-cleaner-v0-1.md`
  summary: Invoke quarantine, restore, and purge crash reconciliation through a normal startup or CLI path.
  evidence: Reconciliation code is test-callable only, so a moved payload can remain absent from normal recovery history after a crash.
