---
title: 'Implement AI-cleaner v0.1'
type: 'feature'
ticket: ''
created: '2026-10-17'
status: 'in-progress'
baseline_revision: '97f91e96231df24f006ba64b081a296b9e3e067a'
route: 'full'
route_source: 'auto'
risk: 'high'
review: ''
review_source: ''
lenses_ran: []
review_loop_iteration: 0
context:
  - '{project-root}/AI_CLEANER_PROJECT_PLAN.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The repository contains an authoritative v0.1 contract but no application code. Users need a Windows-first local tool that inventories a selected project, explains conservative cleanup candidates, and never mutates real files without a concrete human review.

**Approach:** Implement M0–M11 from `AI_CLEANER_PROJECT_PLAN.md` in dependency order using a layered Python/PySide6 application, versioned SQLite state, and a narrow Win32 filesystem adapter. Treat the authoritative plan as the complete requirement and acceptance contract; this file is only the BMAD execution map.

## Boundaries & Constraints

**Always:** Scan only a user-selected root; keep discovery read-only; apply hard protection before classification; bind short-lived, single-use UI approval to an immutable exact-item proposal; revalidate identity, contents, policy, boundaries, and volume immediately before mutation; journal per-item intent and outcome; quarantine and restore on the same supported NTFS volume; require a separate UI approval for purge; use disposable fixtures for destructive tests; preserve the plan and LICENSE; record actual evidence in `IMPLEMENTATION_STATUS.md`.

**Never:** Follow links/reparse points for mutation, recursively delete directories, overwrite restore collisions, treat age/name/Git state/agent declaration as deletion proof, mint approval via CLI or serialized input, auto-purge, transmit local data, add an LLM dependency, test against personal folders, claim unverified Windows guarantees, or implement section 17 future scope.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Review journey | Selected NTFS project with eligible intermediates | Scan, unchecked review, exact approval, quarantine, history, and byte-identical restore | Per-item outcomes remain visible and recoverable |
| Missing or stale approval | No UI capability, replay, expiry, selection/policy/content/identity change | No user-file mutation | Fail closed and require fresh review |
| Unsafe filesystem | Traversal, link/reparse point, ADS, hard link, cloud/unsupported volume, locked or replaced file | Item is protected or unsupported | Skip with a precise reason; never use a destructive fallback |
| Interrupted operation | Crash between journal and filesystem steps | Durable intent reconciles observed state without automatic destructive continuation | Mark unresolved/partial state for review |
| Restore collision | New file occupies the original path | Both versions remain intact | Require an explicit safe alternate destination |
| Purge | Selected app-owned recovery payload with fresh purge approval | Only that verified payload is permanently removed | Altered, missing, replayed, or unapproved payload remains |

</frozen-after-approval>

## Code Map

- `AI_CLEANER_PROJECT_PLAN.md` -- authoritative R01–R16, M0–M11, architecture, UX, CLI, and acceptance contract; do not rewrite.
- `LICENSE` -- existing MIT license to preserve and include in distribution.
- `IMPLEMENTATION_STATUS.md` -- single traceability tracker, starting-state record, and verification evidence.
- `pyproject.toml`, `uv.lock`, `src/ai_cleaner/` -- package, locked toolchain, domain/services/storage/platform/UI/CLI implementation.
- `tests/` -- unit, integration, Windows-native, UI, adversarial, and disposable-fixture end-to-end checks.
- `docs/`, `README.md` -- tested setup, safety boundary, Codex workflow, validation evidence, and manual Windows checks.
- `packaging/`, `.github/workflows/ci.yml` -- reproducible PyInstaller one-directory package and Windows CI.
- `_bmad/`, `_bmad-output/` -- project workflow metadata; never scan as cleanup candidates.

## Tasks & Acceptance

**Execution:**
- [ ] M0–M2 -- establish package/tooling/tracker, Win32 boundary adapter, versioned storage, bounded cancellable scanner, and structured CLI.
- [ ] M3–M5 -- implement conservative protection/classification, task snapshots/declarations, immutable proposals, hashing, and in-process approval state machine.
- [ ] M6–M8 -- implement locked journaled quarantine, crash reconciliation, collision-safe restore/history, and separately approved purge.
- [ ] M9 -- connect the real PySide6 project, review, confirm, result, recovery, restore, and purge workflow with responsive workers.
- [ ] M10–M11 -- finalize docs, Windows CI, adversarial/native/UI tests, build and smoke-test the portable package, and audit R01–R16.

**Acceptance Criteria:**
- Given the plan's supported Windows scope, when all M0–M11 gates are exercised on isolated fixtures, then every R01–R16 row has code and passing evidence or is explicitly marked blocked/unverified without an overclaim.
- Given scan, proposal, cancellation, stale state, unsupported filesystem, partial failure, interruption, restore collision, concurrency, and purge cases, when exercised, then user files change only after the corresponding fresh human UI approval and all outcomes are recorded truthfully.
- Given a clean Windows 11 x64 environment with Python 3.12 and uv, when documented commands are followed, then the CLI, desktop app, tests, and one-directory package run without accounts, API keys, network services, or BMAD at runtime.

## Implementation Notes

## Plan Change Log

## Review Triage Log

## Design Notes

Keep policy/proposals independent of Qt. Filesystem mutation is reachable only through application services supplied with ephemeral UI approval capabilities and the verified Windows adapter. SQLite stores durable facts and intents, never reusable approval authority. Cross-platform unit tests may exercise policy, but Windows-native gates remain distinct and cannot be inferred from mocks.

## Verification

**Commands:**
- `uv sync --frozen --all-groups` -- clean dependency installation from the committed lockfile.
- `uv run ruff check .` -- lint passes.
- `uv run mypy src` -- typed core/service/platform interfaces pass.
- `uv run pytest` -- unit, integration, Windows-native where applicable, and UI suites pass with disposable state.
- `uv run ai-cleaner doctor` and `uv run ai-cleaner --help` -- installed entry point reports real capability and commands.
- `uv run pyinstaller --clean packaging/ai-cleaner.spec` -- Windows one-directory package builds.

**Manual checks:**
- Launch the packaged app outside the checkout and complete select → scan → review → approve → quarantine → restore, then separately review and approve purge on disposable fixtures.
