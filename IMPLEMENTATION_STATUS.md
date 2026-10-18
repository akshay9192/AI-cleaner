# Implementation status

Authoritative contract: `AI_CLEANER_PROJECT_PLAN.md` v1.2, revised 18 October 2026 for the minimal script and tkinter-popup product. Implementation branch: `codex/implement-ai-cleaner-v0.1`.

Starting state (17 October 2026): branch `main` at `97f91e96231df24f006ba64b081a296b9e3e067a`; only `LICENSE` was tracked and the project plan was intentional user input. No `AGENTS.md` or `thinking.md` exists. The earlier BMAD execution map is retained as historical material. An earlier managed-session BMAD renderer attempt failed because its resolved `uv.exe` could not be accessed. A later workflow renderer invocation succeeded, but the delegated implementation runner encountered the same access denial; BMAD verification remains unperformed and is not claimed.

Statuses are evidence-based: **pending**, **in progress**, **verified**, **blocked**, or **superseded**.

| Requirement | Current implementation | Verification evidence | Status |
|---|---|---|---|
| R01 Explicit roots and filesystem boundaries | `platform/windows_fs.py` | User-performed external Windows validation: unmodified 66-test suite passed with a fresh unique pytest base directory | verified |
| R02 Bounded, cancellable read-only inventory | `services/scan.py` | Current managed-boundary integration coverage plus historical native coverage | verified |
| R03 Protection, declarations, Git context, explanations | `services/classify.py`, `services/tasks.py` | Current tests pass, but quick review found common source/configuration types outside hard protection | in progress |
| R04 Task baseline, fingerprinted temp registration, and honest ending diff | `services/tasks.py`, script commands | Baseline rejection, re-registration, exact diff, and no-baseline retention tests | verified |
| R05 Immutable exact proposals and stale checks | `services/proposals.py`, storage | Digest/content/identity/pin/replay checks pass; Git tracking changes are not revalidated immediately before mutation | in progress |
| R06 Human popup approval | `popup.py`, `cli.py` | User-performed external validation completed the real popup quarantine/restore journey and confirmed cancellation retained the temporary file and contents | verified |
| R07 Same-volume quarantine with whole-plan preflight | `services/operations.py` | User-performed popup quarantine passed, but no supported project-level same-volume recovery setup, shared mutation lock, or fully held destination-parent boundary exists | in progress |
| R08 Reconciliation and collision-safe restore | `services/recovery.py` | User-performed restore passed; crash reconciliation exists as a service method but is not invoked by a product path | in progress |
| R09 Separately reviewed permanent purge | `services/purge.py` | User-performed purge passed; purge uses a different lock from quarantine and its crash reconciliation is not invoked by a product path | in progress |
| R10 Truthful history and byte reporting | CLI and storage | Terminal workflow verifies run/recovery IDs and quarantined versus reclaimed reporting | verified |
| R11 Local, versioned state without account/API/network runtime | package/storage/config | Runtime dependency set is empty; schema and local-state tests pass | verified |
| R12 Practical root script and installed command | `ai_cleaner.py`, compatibility entry points | Clean wheel install succeeded; installed command and package import work from a separate synthetic project directory | verified |
| R13 Minimal popup completion workflow | `popup.py`, `cli.py` | User-performed external validation covered real popup quarantine, cancellation, restore, and separately approved purge | verified |
| R14 Acceptance suite | `tests/unit`, `tests/integration`, `tests/terminal`, `tests/windows` | User-performed external Windows run passed all 66 tests and the popup journey; quick review identified six contract paths not covered by that suite | in progress |
| R15 Reproducible installation and lock | `pyproject.toml`, `uv.lock`, README, CI | User-performed external validation: `uv lock` left no unstaged lock diff; after isolating broken pip 24.2 metadata, frozen dev sync succeeded and `uv pip check` found all 16 packages compatible | verified |
| R16 Traceability and Git hygiene | plan, validation record, tracker, local commits | External evidence and quick-review findings are recorded; six findings remain deferred | in progress |

## Milestone gates

| Milestone | Scope | Current evidence | Status |
|---|---|---|---|
| M0–M4 | Foundation, Windows safety, scanner, classification, task lifecycle | User-performed 66-test Windows suite passed; hard-protection coverage remains incomplete | in progress |
| M5 | Immutable proposal and popup approval | Popup and existing stale-state checks pass; post-review Git tracking changes are not revalidated | in progress |
| M6–M8 | Quarantine, recovery/history, purge | External journeys pass; recovery-root setup, parent locking, shared operation locking, and invoked crash reconciliation remain unresolved | in progress |
| M9 | Minimal popup workflow | User-performed real popup quarantine, cancellation, restore, and separate purge journey passed | verified |
| M10 | Documentation | Plan, README, Codex workflow, safety and validation updated for popup/script product | verified |
| M11 | CI, installation and final audit | Installation, lock, native suite, and popup evidence pass; quick review found six unresolved contract gaps | in progress |

## Superseded and blocked evidence

- PySide6 desktop screens, Qt responsiveness/DPI, and PyInstaller onedir are no longer release requirements. Their nine historical Qt tests and old package smoke are **superseded**, not current passes.
- On 18 October 2026 the current 66-test native run reached 29 passes and 37 failures; all 37 stopped at the same managed `CreateFileW` denial on the user-profile ancestor before the affected behavior ran. They remain environment-blocked, not passing evidence.
- The managed-boundary test configuration replaces only the unavailable ancestor reparse-chain call. It still exercises hashing, guarded moves, journaling, restore, and deletion on disposable fixtures. It does not validate the patched boundary itself.
- The root dependency metadata in `uv.lock` matches `pyproject.toml`, but unreachable desktop-era records remain. The unavailable `uv.exe` prevents clean regeneration or frozen validation in this session.
- Acceptance work continues from pushed implementation commit `cc081d3`; no release or merge is claimed.

## User-performed external validation

On 18 October 2026, the owner reported the following checks from an ordinary external Windows
session. These results were not executed or independently observed by the finalizing agent:

- the unmodified suite passed all 66 tests in 13.95 seconds with a fresh, unique pytest
  `--basetemp` directory;
- real popup quarantine and restore succeeded, protected baseline files and the deliverable stayed
  present, and the restored preview contained its expected text;
- popup cancellation retained the temporary file with its expected contents;
- a separate human-approved purge succeeded for the synthetic 24-byte payload;
- `doctor --json` returned status `ok`;
- `uv lock` completed and `git diff -- uv.lock` showed no unstaged changes; and
- after the damaged `pip-24.2.dist-info` metadata was moved aside, `uv sync --frozen --group dev`
  succeeded and `uv pip check` checked 16 packages with all packages compatible.

The historical managed-session failures above remain part of the record. BMAD verification is
still unresolved and no BMAD pass is claimed.

## Quick-review findings

The finalization quick review found six real gaps that are not disproved by the passing suite:

- project-specific same-volume recovery selection is unavailable when the default state volume
  differs from the project volume;
- common source and configuration types can escape hard protection;
- Git tracking changes after proposal preparation are not revalidated before mutation;
- the actual destination parent remains replaceable during the final rename;
- quarantine and recovery operations do not share one lock; and
- crash-reconciliation methods are not invoked by a startup or CLI product path.

These pre-existing implementation gaps were not fixed because this finalization was explicitly
limited to adding no features. They are recorded in `_bmad-output/deferred-work.md` and keep the
affected requirement and milestone gates in progress.
