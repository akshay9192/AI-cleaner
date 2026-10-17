# Implementation status

Authoritative contract: `AI_CLEANER_PROJECT_PLAN.md` v1.0. BMAD execution map: `_bmad-output/plan-implement-ai-cleaner-v0-1.md`.

Starting state (2026-10-17): branch `main` at `97f91e96231df24f006ba64b081a296b9e3e067a`; only `LICENSE` tracked; the authoritative plan was intentional, untracked user input. Implementation branch: `codex/implement-ai-cleaner-v0.1`. No `AGENTS.md` or `thinking.md` existed.

Statuses are evidence-based: **pending**, **in progress**, **verified**, or **blocked**.

| Requirement | Plan task / dependencies | Code | Acceptance criterion | Verification evidence | Status |
|---|---|---|---|---|---|
| R01 | M1 root and filesystem boundary validation; M0 | `src/ai_cleaner/platform/windows_fs.py` | Only supported, explicit project roots and same-volume recovery | Native root/boundary/handle matrix: 7 passed | verified |
| R02 | M2 bounded cancellable read-only inventory; M1 | `src/ai_cleaner/services/scan.py` | No inspected-file mutation; incomplete scans explicit | Read-only/cancel/limit/link tests passed in 13-test gate | verified |
| R03 | M3 protection, pins, Git, explanations; M2 | `src/ai_cleaner/services/classify.py` | Protected never selectable; unknown remains unknown | Mixed valuables, pins, real Git/NUL and Git-failure tests: 4 passed | verified |
| R04 | M4 task snapshots/declarations; M3 | `src/ai_cleaner/services/tasks.py` | Honest observed-during-task diff and active-task block | Snapshot/diff/scope/conflict/CLI journey: 4 passed | verified |
| R05 | M5 immutable proposals and stale checks; M4 | `src/ai_cleaner/services/proposals.py` | Exact digest; changed state requires new review | Pending M5 tests | pending |
| R06 | M5/M9 ephemeral desktop approval; M4/M8 | `src/ai_cleaner/domain/approval.py`, `src/ai_cleaner/ui/` | Missing/cancelled/stale/replayed approval cannot mutate | Pending M5/M9 tests | pending |
| R07 | M6 same-volume quarantine; M5 | `src/ai_cleaner/services/operations.py` | Only approved unchanged files move; per-file outcomes | Pending M6 tests | pending |
| R08 | M7 reconciliation and restore; M6 | `src/ai_cleaner/services/recovery.py` | Interrupted work reviewable; restore never overwrites | Pending M7 tests | pending |
| R09 | M8 separately approved purge; M7 | `src/ai_cleaner/services/purge.py` | No automatic or unapproved permanent deletion | Pending M8 tests | pending |
| R10 | M7–M9 truthful history and totals | storage/services/UI | Individual outcomes; quarantined vs reclaimed bytes | Pending integration/UI tests | pending |
| R11 | M0/M2/M9 local versioned bounded state | `pyproject.toml`, storage/config/UI | No accounts/network; schema/config versioned | Schema v1 migration/rejection and local state passed; UI pending | in progress |
| R12 | M4/M10 safe CLI and workflow docs | `src/ai_cleaner/cli.py`, `docs/` | Required read-only/metadata commands and exit codes | Scan/task commands and workflow verified; propose/history pending | in progress |
| R13 | M9 responsive native Qt workflow | `src/ai_cleaner/ui/` | Complete connected Windows desktop journey | Pending M9 UI tests | pending |
| R14 | Every milestone/M11 safety tests | `tests/` | Acceptance matrix on disposable fixtures | M1 native matrix 7 passed; later gates pending | in progress |
| R15 | M0/M10/M11 reproducible setup/package | manifests/docs/packaging | Clean setup and standalone Windows onedir smoke | `uv.lock` resolved on Python 3.12.6; M11 package pending | in progress |
| R16 | Every gate traceability/Git hygiene | this tracker, local commits | Plan mapped, changes reviewed, evidence current | Starting state recorded | in progress |

## Milestone gates

| Milestone | Scope | Check command / evidence | Platform | Remaining limitation | Status |
|---|---|---|---|---|---|
| M0 | Foundation | Frozen sync passed; doctor/help passed; Ruff passed; mypy passed; pytest 2 passed | Windows 11 x64 / Python 3.12.6 | None for M0 | verified |
| M1 | Windows safety adapter | Ruff/mypy passed; `pytest tests/windows/test_windows_fs.py`: 7 passed | Windows 11 x64 / NTFS | Other acceptance cases continue in M6–M8 | verified |
| M2 | Storage and scanner | Ruff/mypy passed; integration+Windows pytest: 13 passed | Windows 11 x64 / NTFS | None for M2 | verified |
| M3 | Classification | Ruff/mypy passed; policy tests: 4 passed | Windows 11 x64 | None for M3 | verified |
| M4 | Task lifecycle | Ruff/mypy passed; task service+CLI: 4 passed | Windows 11 x64 / NTFS | None for M4 | verified |
| M5 | Proposal/approval | State-machine adversarial tests | Windows 11 x64 | Not implemented | pending |
| M6 | Quarantine | Native failure-injection tests | Windows 11 x64 | Not implemented | pending |
| M7 | Restore/history | Restart/collision/integrity tests | Windows 11 x64 | Not implemented | pending |
| M8 | Purge | Separate approval/replay/retention tests | Windows 11 x64 | Not implemented | pending |
| M9 | Desktop | pytest-qt plus real fixture journey | Windows 11 x64 | Not implemented | pending |
| M10 | Documentation | Follow commands in clean disposable environment | Windows 11 x64 | Not implemented | pending |
| M11 | CI/package/audit | Full suite and packaged-app smoke | Windows 11 x64 | Not implemented | pending |
