# Implementation status

Authoritative contract: `AI_CLEANER_PROJECT_PLAN.md` v1.2, revised 18 October 2026 for the minimal script and tkinter-popup product. Implementation branch: `codex/implement-ai-cleaner-v0.1`.

Starting state (17 October 2026): branch `main` at `97f91e96231df24f006ba64b081a296b9e3e067a`; only `LICENSE` was tracked and the project plan was intentional user input. No `AGENTS.md` or `thinking.md` exists. The earlier BMAD execution map is retained as historical material. The BMAD renderer is unavailable in this managed session because its sole resolved `uv.exe` cannot be accessed; it was not rerun and no BMAD checks are claimed.

Statuses are evidence-based: **pending**, **in progress**, **verified**, **blocked**, or **superseded**.

| Requirement | Current implementation | Verification evidence | Status |
|---|---|---|---|
| R01 Explicit roots and filesystem boundaries | `platform/windows_fs.py` | Historical native Windows matrix passed; current native rerun reaches a managed `CreateFileW` denial on the user-profile ancestor | blocked |
| R02 Bounded, cancellable read-only inventory | `services/scan.py` | Current managed-boundary integration coverage plus historical native coverage | verified |
| R03 Protection, declarations, Git context, explanations | `services/classify.py`, `services/tasks.py` | Current policy and workflow tests | verified |
| R04 Task baseline, fingerprinted temp registration, and honest ending diff | `services/tasks.py`, script commands | Baseline rejection, re-registration, exact diff, and no-baseline retention tests | verified |
| R05 Immutable exact proposals and stale checks | `services/proposals.py`, storage | Digest-bound subset, content/identity/policy/replay tests | verified |
| R06 Human popup approval | `popup.py`, `cli.py` | Tkinter popup display was observed; test adapter covers unchecked/select/protect/cancel and exact confirmation, but no agent-driven production approval was performed | in progress |
| R07 Same-volume quarantine with whole-plan preflight | `services/operations.py` | Current disposable managed-boundary tests cover exact move, stale item, interruption, and truthful outcomes | verified |
| R08 Reconciliation and collision-safe restore | `services/recovery.py` | Current disposable managed-boundary restore, collision, integrity, and interruption tests | verified |
| R09 Separately reviewed permanent purge | `services/purge.py` | Current disposable managed-boundary separate approval, stale payload, replay, and interruption tests | verified |
| R10 Truthful history and byte reporting | CLI and storage | Terminal workflow verifies run/recovery IDs and quarantined versus reclaimed reporting | verified |
| R11 Local, versioned state without account/API/network runtime | package/storage/config | Runtime dependency set is empty; schema and local-state tests pass | verified |
| R12 Practical root script and installed command | `ai_cleaner.py`, compatibility entry points | Root script and installed command report version/help and load one shared implementation | verified |
| R13 Minimal popup completion workflow | `popup.py`, `cli.py` | Popup availability/failure path and complete/review orchestration implemented; human production mutation intentionally not automated | in progress |
| R14 Acceptance suite | `tests/unit`, `tests/integration`, `tests/terminal`, `tests/windows` | 58 managed-boundary tests pass; native full run has 27 passes and 36 boundary-blocked failures | in progress |
| R15 Reproducible installation and lock | `pyproject.toml`, `uv.lock`, README, CI | Normal editable pip install and entry points pass; `uv sync --frozen` cannot run in this session | in progress |
| R16 Traceability and Git hygiene | plan, validation record, tracker, local commits | Final diff review passed; focused implementation and documentation commits created locally | verified |

## Milestone gates

| Milestone | Scope | Current evidence | Status |
|---|---|---|---|
| M0–M4 | Foundation, Windows safety, scanner, classification, task lifecycle | Existing implementation retained; current tests cover all except the managed native ancestor check | in progress |
| M5 | Immutable proposal and popup approval | Exact selections, digest binding, default-retain behavior, staleness and replay covered; human popup approval not automated | in progress |
| M6–M8 | Quarantine, recovery/history, purge | Disposable managed-boundary service and workflow tests pass | verified |
| M9 | Minimal popup workflow | Root script, popup adapter and headless fallback implemented; test-adapter journey passes | in progress |
| M10 | Documentation | Plan, README, Codex workflow, safety and validation updated for popup/script product | verified |
| M11 | CI, installation and final audit | Terminal CI and editable install implemented; final checks pass and local commits are recorded; uv frozen check remains blocked | in progress |

## Superseded and blocked evidence

- PySide6 desktop screens, Qt responsiveness/DPI, and PyInstaller onedir are no longer release requirements. Their nine historical Qt tests and old package smoke are **superseded**, not current passes.
- On 18 October 2026 the current 63-test native run reached 27 passes and 36 failures; all 36 stopped at the same managed `CreateFileW` denial on the user-profile ancestor before the affected behavior ran. They remain environment-blocked, not passing evidence.
- The managed-boundary test configuration replaces only the unavailable ancestor reparse-chain call. It still exercises hashing, guarded moves, journaling, restore, and deletion on disposable fixtures. It does not validate the patched boundary itself.
- The root dependency metadata in `uv.lock` was adjusted for the removed desktop dependencies, but the unavailable `uv.exe` prevents regenerating or frozen-validating that lock in this session.
- Local implementation commit: `ba2db6a` (`feat: replace desktop flow with safe terminal workflow`). The plan, documentation, validation evidence, and tracker are recorded in the following focused documentation commit.
