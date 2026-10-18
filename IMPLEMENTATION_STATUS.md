# Implementation status

Authoritative contract: `AI_CLEANER_PROJECT_PLAN.md` v1.1, revised 18 October 2026 for the terminal-first product. Implementation branch: `codex/implement-ai-cleaner-v0.1`.

Starting state (17 October 2026): branch `main` at `97f91e96231df24f006ba64b081a296b9e3e067a`; only `LICENSE` was tracked and the project plan was intentional user input. No `AGENTS.md` or `thinking.md` exists. The earlier BMAD execution map is retained as historical material. The BMAD renderer is unavailable in this managed session because its sole resolved `uv.exe` cannot be accessed; it was not rerun and no BMAD checks are claimed.

Statuses are evidence-based: **pending**, **in progress**, **verified**, **blocked**, or **superseded**.

| Requirement | Current implementation | Verification evidence | Status |
|---|---|---|---|
| R01 Explicit roots and filesystem boundaries | `platform/windows_fs.py` | Historical native Windows matrix passed; current native rerun reaches a managed `CreateFileW` denial on the profile ancestor | blocked |
| R02 Bounded, cancellable read-only inventory | `services/scan.py` | Current managed-boundary integration coverage plus historical native coverage | verified |
| R03 Protection, declarations, Git context, explanations | `services/classify.py`, `services/tasks.py` | Current policy and terminal workflow tests | verified |
| R04 Task baseline and honest ending diff | `services/tasks.py`, terminal `start`/`complete` | Start, automatic single-task resolution, ambiguity handling, and no-baseline preview tests | verified |
| R05 Immutable exact proposals and stale checks | `services/proposals.py`, storage | Digest-bound subset, content/identity/policy/replay tests | verified |
| R06 Human terminal approval | `terminal.py`, `cli.py` | Test-only interaction adapter covers keep/select/protect/cancel and exact confirmation; real human TTY journey remains blocked by the execution environment | in progress |
| R07 Same-volume quarantine with whole-plan preflight | `services/operations.py` | Current disposable managed-boundary tests cover exact move, stale item, interruption, and truthful outcomes | verified |
| R08 Reconciliation and collision-safe restore | `services/recovery.py` | Current disposable managed-boundary restore, collision, integrity, and interruption tests | verified |
| R09 Separately reviewed permanent purge | `services/purge.py` | Current disposable managed-boundary separate approval, stale payload, replay, and interruption tests | verified |
| R10 Truthful history and byte reporting | CLI and storage | Terminal workflow verifies run/recovery IDs and quarantined versus reclaimed reporting | verified |
| R11 Local, versioned state without account/API/network runtime | package/storage/config | Runtime dependency set is empty; schema and local-state tests pass | verified |
| R12 Practical script and installed command | `scripts/project_cleanup.py`, `ai-cleaner` entry point | Both entry points report version/help from the editable install | verified |
| R13 Native Qt desktop and PyInstaller package | Removed from product, dependencies, tests, and CI by the owner’s 18 October redesign | Nine earlier Qt tests are historical only | superseded |
| R14 Terminal acceptance suite | `tests/unit`, `tests/integration`, `tests/terminal` | 51 managed-boundary tests pass; full native filesystem run remains environment-blocked | in progress |
| R15 Reproducible installation and lock | `pyproject.toml`, `uv.lock`, README, CI | Normal editable pip install and entry points pass; `uv sync --frozen` cannot run in this session | in progress |
| R16 Traceability and Git hygiene | plan, validation record, tracker, local commits | Final diff review passed; focused implementation and documentation commits created locally | verified |

## Milestone gates

| Milestone | Scope | Current evidence | Status |
|---|---|---|---|
| M0–M4 | Foundation, Windows safety, scanner, classification, task lifecycle | Existing implementation retained; current tests cover all except the managed native ancestor check | in progress |
| M5 | Immutable proposal and terminal approval | Exact selections, digest binding, default-retain behavior, staleness and replay covered; real TTY walkthrough blocked | in progress |
| M6–M8 | Quarantine, recovery/history, purge | Disposable managed-boundary service and terminal tests pass | verified |
| M9 | Terminal workflow | Installed command and repository script implemented; test adapter journey passes | in progress |
| M10 | Documentation | Plan, README, Codex workflow, safety and validation updated for terminal product | verified |
| M11 | CI, installation and final audit | Terminal CI and editable install implemented; final checks pass and local commits are recorded; uv frozen check remains blocked | in progress |

## Superseded and blocked evidence

- Desktop UI, Qt responsiveness/DPI, GUI-only approval, and PyInstaller onedir are no longer release requirements. Their nine historical Qt tests and old package smoke are **superseded**, not current passes.
- On 18 October 2026 the current runner’s native full suite reached 23 passes and 35 failures; all 35 stopped at the same managed `CreateFileW` denial on `C:\Users\aksha` before the affected behavior ran. They remain environment-blocked, not passing evidence.
- The managed-boundary test configuration replaces only the unavailable ancestor reparse-chain call. It still exercises hashing, guarded moves, journaling, restore, and deletion on disposable fixtures. It does not validate the patched boundary itself.
- The root dependency metadata in `uv.lock` was adjusted for the removed desktop dependencies, but the unavailable `uv.exe` prevents regenerating or frozen-validating that lock in this session.
- Local implementation commit: `ba2db6a` (`feat: replace desktop flow with safe terminal workflow`). The plan, documentation, validation evidence, and tracker are recorded in the following focused documentation commit.
