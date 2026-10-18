# AI-cleaner — Authoritative implementation plan

Version: 1.2 · Created: 17 October 2026 · Revised: 18 October 2026
Repository: https://github.com/akshay9192/AI-cleaner.git  
Owner: Akshay Harwalkar  
Target: Minimal Windows-first Python cleanup script with a lightweight tkinter approval popup.

## 0. Scope revisions

### Version 1.2 minimal-popup revision

On 18 October 2026 the owner revised the interaction layer again. The primary entry point is now
`python ai_cleaner.py ...`; explicit completion opens one compact standard-library tkinter review
popup. The installed `ai-cleaner` command and earlier repository wrapper remain compatible entry
points into the same core. A large desktop application, background service, PySide6, installer,
PyInstaller package, dashboard, and terminal-only approval are not release requirements.

Only files absent from the task baseline, explicitly registered with `register-temp` after they
exist, unchanged since their identity/content fingerprint was captured, and clear of every hard
protection may be selected. Other new files are retained as uncertain. If tkinter or a display is
unavailable, the immutable proposal remains pending and the exact `review` command is printed;
no terminal or automated approval fallback is provided.

The owner changed the final product design on 18 October 2026. This revision supersedes the
PySide6 desktop application, GUI-only approval, responsive-widget, DPI, PyInstaller, portable
desktop executable, and desktop-screen requirements. Those implementations and results remain
historical evidence only; they are not v1.1 release gates.

Unchanged requirements are explicit selected roots, bounded read-only scanning, conservative
protection and uncertainty, honest task snapshots, immutable exact-file proposals, fresh human
approval, same-volume recoverable quarantine, journaling and reconciliation, collision-safe
restore, separately approved purge, truthful byte reporting, local privacy, Windows/NTFS safety,
adversarial tests, and respectful Git/file handling.

Version 1.1 introduced the installable command and shared core. Version 1.2 retains that work but
makes root `ai_cleaner.py` and a tkinter popup the primary experience. Explicit `complete` is the
only v1 task-completion signal. Completion authorises an end snapshot and pending proposal, never
file mutation. Missing popup support stores the proposal and moves nothing.

## 1. How to use this document

Place this file at the repository root as `AI_CLEANER_PROJECT_PLAN.md`. This is the authoritative product and implementation contract for v0.1. The repository's remote main branch contained only LICENSE when inspected on 17 October 2026; inspect the actual local checkout before starting because local files and branches may differ.

Implement milestones M0–M11 in order, following their dependencies and acceptance gates. “Complete code” means all v0.1 requirements in this document are implemented and verified. Section 17 is explicitly future scope and must not be silently included in v0.1.

Read applicable AGENTS.md instructions, this complete plan, and the current implementation tracker before coding. Use the BMAD skills actually installed in the terminal; inspect their instructions instead of assuming command names or versions. BMAD is the implementation workflow, not an application runtime dependency.

Do not replace this plan with a newly generated specification. Use `IMPLEMENTATION_STATUS.md` for evidence and progress. Material changes to scope, safety, or architecture require a concrete proposal to the owner. Routine function names and UI spacing do not require permission. Do not weaken acceptance criteria to make incomplete work appear finished.

## 2. Product purpose and success

Help people understand what AI-assisted tasks leave in their project folders, preserve useful files, and approve removal of disposable intermediates.

Product promise: **See what a task left behind, keep the useful outputs, and approve the cleanup.**

Initial user: a Windows user running Codex for coding, documents, reports, or media preparation. The application must also work on ordinary project folders without Git or Codex installed.

Separate two outcomes:
- Workspace clarity: remove selected clutter from the working folder into recovery storage.
- Disk reclamation: explicitly delete selected recovery payloads after a separate human confirmation.

Moving files to recovery on the same volume does not reclaim disk space. Never report otherwise.

Success for v0.1 is a functioning installable application that completes scan → review → human confirmation → quarantine → restore, plus a separate confirmed purge, using only selected files in selected project folders. It must also support a reproducible task start/end workflow and honestly label unknown file origin.

No claim is made that the idea is unique or commercially validated. Existing tools cover substantial parts of this space; the intended improvement is an understandable Windows review experience linked to task outputs.

## 3. Fixed v0.1 scope and non-goals

### Required

- Minimal Python 3.12 script with a tkinter approval popup, operated as a standard user.
- Local NTFS project folders; one selected root per scan/task and one mutation batch at a time.
- Read-only discovery with explanations and explicit uncertainty.
- Protected files and folders; user pinning; Git-aware protection when Git is available.
- Human-reviewed quarantine, recovery, history, and separate permanent purge.
- Task snapshots and explicit registration of scratch artifacts and deliverables.
- Explicit task commands suitable for Codex/BMAD integration; mutation remains popup-approved.
- Automated tests, Windows-specific tests, and documented manual smoke checks.
- Local persistence without accounts, telemetry, API keys, network services, or paid model calls.

### Excluded from v0.1

- Whole-PC cleaning, registry repair, system optimization, or antivirus functions.
- Cleaning Codex's or other vendors' internal databases, credentials, histories, or installed skill directories.
- Background deletion, scheduled purge, service/daemon installation, or automatic approval.
- Cloud file synchronization, network shares, removable drives, cloud placeholder files, and non-NTFS mutation.
- Destructive agent-facing MCP tools or a headless `--yes` cleanup mode.
- Cross-volume quarantine or restore; reject these clearly.
- General duplicate deletion, source-code refactoring, or proving that a file is unused by every possible program.
- Paid subscriptions, remote dashboards, a website, Linux/macOS release packages, and vendor-specific log parsers.

Reject unsupported operations clearly rather than pretending to support them. A read-only inventory may still explain why an item cannot be acted upon.

## 4. Requirement register

Use these IDs in the tracker, tests, and milestone commits.

| ID | Requirement | Primary gate |
|---|---|---|
| R01 | Explicit project-root selection and filesystem boundaries | M1 |
| R02 | Read-only inventory, cancellation, incomplete-scan reporting | M2 |
| R03 | Explainable classifications and protected files | M3 |
| R04 | Baseline/end snapshots and honest task attribution | M4 |
| R05 | Immutable, exact-item cleanup proposals and stale-state checks | M5 |
| R06 | Human approval through an exact, default-retain tkinter popup | M5/M9 |
| R07 | Same-volume quarantine with per-file outcomes | M6 |
| R08 | Crash recovery, collision-safe restore, payload integrity | M7 |
| R09 | Separate approved permanent purge; no automatic expiry deletion | M8 |
| R10 | Accurate history, sizes, errors, and recovery status | M7–M9 |
| R11 | Local privacy, bounded state, versioned configuration | M0/M9 |
| R12 | Safe CLI and documented Codex/BMAD usage | M4/M10 |
| R13 | Complete minimal-script/popup workflow and pending headless review | M9 |
| R14 | Meaningful safety, integration, and adversarial tests | Every gate/M11 |
| R15 | Reproducible script installation, entry points, CI, and clean handoff | M11 |
| R16 | Iterative plan compliance and respectful Git/file handling | Every gate |

## 5. Technology decisions

- Python 3.12 as the initial development and CI baseline. Do not claim other versions are supported until tested.
- `uv` for environment creation and a committed dependency lockfile; `pyproject.toml` for project metadata and commands.
- Standard-library `argparse` for commands and `tkinter` for the approval popup. No browser server,
  third-party GUI framework, account, API key, or LLM is required.
- Standard-library `sqlite3` for structured local state, with explicit transactions, schema versioning, foreign keys, and migration tests.
- Dataclasses, enums, pathlib, hashlib, JSON, and argparse where sufficient.
- A narrow Windows filesystem adapter using documented Win32 facilities, via a carefully scoped binding. Choose ctypes or pywin32 in M1 based on verified handle-based operations; record the choice.
- pytest, Ruff, and a type checker for core/services/platform interfaces. Tests must use real
  fixtures as well as targeted mocks.

Resolve compatible current dependency versions during M0 and lock them. Do not invent package versions. Preserve the repository LICENSE and record third-party notices and distribution obligations before packaging. A repository license does not automatically cover its dependencies.

Do not add an LLM dependency to v0.1. Classification is deterministic; the product name does not require generative AI inside the application.

## 6. Architecture and file layout

Dependency direction: root script/CLI and popup → application services → domain models and
storage/platform adapters. The script is a lightweight wrapper around the same CLI; cleanup logic
must not be duplicated in it. Terminal handlers must not perform filesystem mutation themselves.

Suggested layout; keep responsibilities stable even if small modules are combined:

```text
AI-cleaner/
  LICENSE
  AI_CLEANER_PROJECT_PLAN.md
  IMPLEMENTATION_STATUS.md
  AGENTS.md
  README.md
  pyproject.toml
  uv.lock
  .gitignore
  src/ai_cleaner/
    __init__.py
    __main__.py
    cli.py
    domain/          # records, statuses, policies, proposal invariants
    services/        # scan, classify, task, proposal, recovery, purge
    storage/         # SQLite repositories, migrations, local configuration
    platform/        # Windows identity, boundaries, locks, filesystem operations
    popup.py         # tkinter selection and exact confirmation
    terminal.py      # shared interaction protocol and test/compatibility adapter
  ai_cleaner.py      # primary checkout entry point
  scripts/project_cleanup.py
  tests/
    unit/
    integration/
    windows/
    terminal/
  docs/
    SAFETY.md
    CODEX_WORKFLOW.md
    VALIDATION.md
  .github/workflows/ci.yml
```

Do not create empty scaffolding for speculative future features. If AGENTS.md exists, preserve it and add only compatible project guidance. Do not overwrite it wholesale.

Application state: `%LOCALAPPDATA%\AI-cleaner\` for state DB, logs, and configuration. Recovery storage defaults to a directory there only when it is on the same supported volume as the project. Otherwise ask the user, through initial setup, to choose a dedicated same-volume recovery directory outside the project root. Reject overlapping roots, recovery-inside-project, reparse-point recovery paths, and unsupported volumes.

Never scan the app's own state/recovery storage as cleanup candidates. Use a distinct test state directory for tests. Bounded logs must not contain file contents, credentials, or full agent conversations.

## 7. User experience

Version 1.2 uses one small popup rather than a desktop application or terminal-only approval. It
shows candidates individually with unchecked checkboxes, paths, sizes and reasons; supports
keeping/protecting selected files, quarantine, and cancel; then shows a separate exact
confirmation. Restore and purge use their own popup selection and confirmation.

Serialized approval, `--yes`, `--force`, completion itself, agent text, and timeout defaults must
never approve mutation. Closing or cancelling a popup keeps everything. A popup is an intentional
consent mechanism, not a security boundary against a malicious same-user process.

### Screen A — Project

The `start` command receives one explicit root and returns a task ID. It displays actionable
unsupported-root errors and never scans the user's entire home or drive.

Reject drive roots, the entire user profile, Windows/Program Files directories, and the cleaner's own storage. Allow explicitly selected project directories beneath Documents or Downloads after checking actual path attributes. Do not assume those folders are never cloud-backed.

### Screen B — Review

Display each eligible relative path, size, and plain-language reason in one compact scrollable
popup. All cleanup checkboxes are initially unchecked. Buttons keep/protect the checked files,
move checked files to quarantine, or cancel. Protected and uncertain items are not selectable.

Categories:
- Protected: pinned, deliverable, required input, sensitive/configuration, source, Git-tracked, or active-task file.
- Registered task temporary: absent from the baseline, explicitly registered after creation, and
  still matching its captured handle identity and content fingerprint.
- Unknown: insufficient evidence; no default cleanup recommendation.
- Unsupported: unsafe/unimplemented filesystem semantics; explanatory only.

Do not execute or render candidate content. File contents are hashed only for identity binding.

### Screen C — Confirm

Show the exact selected item list, count, logical size, recovery destination, digest, and statement
that quarantine does not free disk space. Buttons: Cancel and approve the exact operation.

### Screen D — Results and recovery

Print per-file results and the restore command. Restore requires a popup action. A collision leaves
both files intact and accepts only an explicitly reviewed alternate destination. Permanent removal
has a separate popup with irreversible-action wording and its own confirmation.

Retention age is a review reminder only. Never auto-purge. Do not silently empty the Windows Recycle Bin or describe private recovery storage as the system Recycle Bin.

## 8. Policy and scope rules

Protection takes priority over classification. Protect .git and other VCS metadata, AGENTS.md, this plan, BMAD configuration/output, credentials and secret files, dependency/configuration manifests, source and notebook files, raw datasets, and user-pinned paths. Use path-aware rules and file attributes; a filename glob alone cannot establish safety.

For Git roots, obtain tracked paths through a read-only, argument-array Git command with NUL-separated output. Git errors must not silently become “nothing is tracked.” Fall back to conservative protection and clearly show unavailable Git evidence. Never treat ignored or untracked status as deletion permission.

Without a task baseline and fingerprinted registration, existing clutter is retained as unknown.
Recognized cache names may explain a file but cannot make it selectable in this minimal release.
Never broadly classify every `.log`, image, document, source file, build directory, or file named
draft as disposable. A known directory name is not ownership proof.

Delete no directories recursively in v0.1. Enumerate and review individual regular files. Directory rows are UI groups of frozen child items, not permission to include future children. Leave empty directories in place; optional empty-directory removal is deferred.

Do not automatically unprotect files because an agent registered them as scratch. Source/configuration and other hard protections cannot be bypassed through metadata commands. Users may pin additional files; v0.1 need not provide a dangerous blanket override for built-in protections.

## 9. Data model and state transitions

Use stable UUIDs, UTC timestamps, explicit schema versions, and parameterized SQL. Preserve original path spelling for display while using Windows-aware identity and comparison semantics for policy.

Minimum records:

| Record | Essential fields |
|---|---|
| Project | ID, selected/resolved root, volume identity, recovery root, policy version |
| Task | ID, project, label, active/finished/interrupted status, start/end times |
| FileObservation | scan ID, relative path, volume/file ID, size, timestamps, attributes, observed state |
| ArtifactDeclaration | task, path, scratch/deliverable/input role, declaration source, time |
| Protection | project/path rule, reason, origin, creation time |
| Proposal | ID, project, policy digest, immutable items digest, creation time, state |
| ProposalItem | path, action, captured identity, selected size, SHA-256, explanation |
| OperationRun | ID, proposal digest, action, start/end, pending/running/partial/complete/interrupted |
| OperationItem | source/destination, expected identity/hash, durable intent, observed outcome, error |
| RecoveryItem | original path, payload ID/path, size/hash, quarantine time, current state |

Proposal states: draft → reviewable → human-approved → executing → complete/partial. Changed selection or file state invalidates approval. Cancelled, expired, or reused approvals cannot execute. Set approval expiry to 10 minutes after confirmation; expiry before execution requires another confirmation.

Approval is an in-process capability created only after the real popup selection and confirmation
and bound to the exact proposal digest. It is single-use and is not loaded from a JSON `approved`
field or persisted for unattended reuse. History may record approval occurred, but history is not
a reusable execution credential. Non-interactive commands cannot mint execution approval.

This prevents accidental automated approval through supported interfaces; it is not a security boundary against malware or an agent with unrestricted control of the same OS account, UI, or application code. State that limit in SAFETY.md.

## 10. Filesystem execution protocol

### Discovery

Walk without following reparse points or symlinks. Record errors and skipped entries. Do not hydrate cloud placeholders. Reject unsupported attributes, alternate data streams, hard-linked files, and unusual file types for mutation until explicitly supported and tested. Show the reason; never silently drop data-bearing semantics.

Gather metadata first. Do not hash an entire drive. Hash only selected eligible candidates during proposal preparation, with progress and cancellation. Reading metadata may affect OS-managed access records; “read-only” means no intentional writes to inspected user files.

### Prepare and approve

Freeze individual files, action, source identity, size, SHA-256, policy version, and recovery destination. Check space/volume and boundary conditions. Show the actual proposal. Reject approval if preparation failed or relevant task activity remains unresolved.

### Quarantine

1. Acquire the project/recovery operation lock; the UI and CLI must share the same lock discipline for conflicting state updates.
2. Recheck policy, task state, proposal expiry, and root/recovery identities.
3. Open the target using appropriate Windows handle semantics, verify final path, volume/file ID, attributes, and content. Use sharing flags that prevent conflicting write/delete access while processing; if exclusivity cannot be established, skip the item.
4. Protect relevant parent-path boundaries against replacement during the operation. A one-time `resolve()` followed by a path-based rename is insufficient for race-sensitive mutation. Encapsulate documented handle-based operations; no destructive fallback if the platform primitive is unavailable.
5. Persist operation intent before moving the file. Choose a unique app-owned payload name, never an overwrite destination.
6. Perform a same-volume move preserving file data and supported metadata. Verify the destination and record its actual outcome.
7. If filesystem and DB states disagree after an interruption, reconcile from durable intent plus file identity/hash. Do not guess or blindly repeat a deletion.

SQLite and the filesystem do not form one atomic transaction. Design per-item crash recovery explicitly. Do not claim atomic batches or guaranteed survival of every disk failure. Interrupted batches require review on restart; they must not automatically resume destructive work.

### Restore and purge

Restore verifies payload integrity and validates the destination and its parents using the same safety adapter. Do not overwrite or create unsafe parent chains. Missing parents require a reviewed restoration decision. Use a unique alternative path only after approval and record it.

Purge operates only on explicitly selected app-owned recovery payloads, never original workspace paths. Validate payload identity and boundaries; write intent and outcomes. Require fresh human confirmation. Do not follow links or recursively delete a directory tree. On failures, retain recoverable metadata and mark the exact unresolved state.

Report logical payload bytes removed, and optionally measured free-space change separately. Compression, sparse files, concurrent disk activity, and allocation details mean logical file size is not guaranteed physical space reclaimed.

## 11. Task tracking and CLI contract

Use a cooperative wrapper workflow, not undocumented parsing of Codex's private storage.

Version 1.2 canonical commands are:

```powershell
python ai_cleaner.py start --root . --label "Implement feature"
python ai_cleaner.py register-temp --task TASK_ID --path "scratch\preview.aux"
python ai_cleaner.py protect --task TASK_ID --path "dist\final-output.zip"
python ai_cleaner.py complete --task TASK_ID
python ai_cleaner.py review --proposal PROPOSAL_ID
python ai_cleaner.py restore --run RUN_ID
python ai_cleaner.py purge --run RUN_ID
```

`complete` records the end state and prepares a proposal. With exactly one unresolved task for the
root it resolves that task and displays its ID and label; ambiguity requires `--task`. Without a
baseline, `preview` may conservatively show existing clutter but must state that historical
ownership is unknown. Added files are “observed during task,” never claimed as AI-created.

Popup review defaults every candidate to keep. Selection changes produce a new exact digest;
file, identity, policy, expiry, or replay changes require fresh review. Non-interactive completion
stores a pending proposal, performs no mutation, exits 6, and prints `ai-cleaner review --proposal
PROPOSAL_ID`. Exit 7 means user cancellation/no selection and exit 8 means an operation completed
partially. No production confirmation bypass is permitted. The nested `task` commands may remain
as compatibility aliases, but the commands above are the documented workflow.

Output one valid structured JSON document without progress noise on stdout when `--json` is
supplied; send diagnostics to stderr. Return 0 for success, 1 for other errors, 2 for invalid
input, 3 for unsupported scope, 4 for incomplete scans, 5 for state/lock conflicts, 6 when human
review is required, 7 for cancellation/no selection, and 8 for partial mutation results. Never
report an incomplete scan as full success.

`scan` and `propose` may write their own app-state records but never mutate inspected user files. Metadata commands may create app state and task records only. No `clean --yes`, `purge --yes`, or CLI approval token minting.

Task start stores a baseline inventory and a protected pre-existing set for task-specific cleanup. Task finish records added/modified/missing files; it never deletes anything. Pre-existing modified files remain protected in task mode. Another editor may create files during the same task, so the label must be “observed during task,” not “created by Codex,” without additional reliable evidence.

`register-temp` validates scope, rejects baseline files, and captures handle identity plus a content
hash after the file exists. A later change makes it ineligible until re-registered. Protection
always wins; source-like files remain protected even when registered. Deliverables, protected
directories, and all descendants become protected.

An active or interrupted task protects its declared scratch and observed changing files. For v0.1, allow only one active tracked task per root. The user must explicitly finish or resolve an abandoned task before proposing its cleanup. Snapshot tracking must exclude app state, recovery storage, dependency trees, VCS internals, and unsupported paths to avoid unnecessary overhead.

CODEX_WORKFLOW.md must explain starting a task, registering final outputs and intermediates, ending the task, and opening the human review screen. Include an instruction for Codex to use a designated scratch directory and preserve maintainable source. Do not modify the user's global Codex configuration or install hooks automatically.

## 12. Milestones and small implementation tasks

Each task below should be a reviewable iteration. Do not commit a milestone as complete until its gate is satisfied. Use local commits; pushing is controlled by the owner's explicit session instruction.

### M0 — Repository and development foundation
Dependencies: none. Requirements: R11, R15, R16.
- T0.1 Inspect repo, AGENTS.md, user changes, branch, and this plan; preserve LICENSE.
- T0.2 Create package metadata, locked environment, lint/type/test configuration, and minimal launch entry points.
- T0.3 Create tracker, README outline, and narrow temporary/generated-file exclusions.
Gate: clean environment can import the package and run doctor/help; no fake product behavior; tracker maps every R ID and milestone.

### M1 — Windows filesystem safety spike
Dependencies: M0. Requirements: R01, R14.
- T1.1 Implement root/recovery selection validation and volume/file identity inspection.
- T1.2 Prove handle-based same-volume move/delete and path-boundary protection on disposable Windows fixtures.
- T1.3 Test reparse/junction, hard-link, alternate-stream, locked-file, and parent-replacement cases; document unsupported cases.
Gate: demonstrate no out-of-scope mutation under the test matrix. If the critical native operation cannot be made reliable, keep mutation disabled and report the blocker; do not substitute a string-prefix check.

### M2 — Storage and read-only scanner
Dependencies: M1. Requirements: R02, R11.
- T2.1 Implement migrations, records, configuration, and state-location handling.
- T2.2 Implement bounded incremental directory inventory with cancellation and error reporting.
- T2.3 Wire scan CLI and structured output.
Gate: expected file inventory; no user-file content changes; unsupported links not traversed; cancellation and incomplete scans explicit.

### M3 — Protection and candidate explanations
Dependencies: M2. Requirements: R03.
- T3.1 Implement hard protections, pins, and Git tracking detection.
- T3.2 Add conservative cache/intermediate rules and reason codes.
- T3.3 Test mixed project fixtures containing valuables with misleading names.
Gate: protected examples never selectable; every suggestion has evidence and reason; unknown files stay unknown; Git failures fail conservatively.

### M4 — Task lifecycle and attribution
Dependencies: M3. Requirements: R04, R12.
- T4.1 Implement task start/baseline, registration, finish/diff, and interrupted-task handling.
- T4.2 Protect pre-existing/modified files and explicitly declared outputs.
- T4.3 Document a runnable Codex task workflow and validate its metadata commands.
Gate: added/modified/deleted differences correct; manual concurrent edits not falsely attributed; active tasks cannot be cleaned; CLI cannot approve mutations.

### M5 — Proposals and approval boundary
Dependencies: M4. Requirements: R05, R06.
- T5.1 Implement immutable selected-item proposals, digest/version, hashing and cancellation.
- T5.2 Implement single-use in-process approval capabilities, expiry and invalidation.
- T5.3 Test changed files, selection changes, replay, forged serialized approval, and policy changes.
Gate: absent/stale/replayed approval never authorizes execution; exact selected set and policy are bound; no public automated bypass.

### M6 — Recoverable quarantine
Dependencies: M5. Requirements: R07, R14.
- T6.1 Add operation locks, durable intent, payload naming, and native execution adapter.
- T6.2 Implement per-file revalidation, move, verification, and outcomes.
- T6.3 Inject failures before/after the filesystem move and before/after journal updates.
Gate: only approved unchanged eligible files move; recovery data exists for every moved item; partial results truthful; cancellation stops subsequent items and preserves completed recovery records.

### M7 — Reconciliation, restore, and history
Dependencies: M6. Requirements: R08, R10.
- T7.1 Reconcile interrupted runs without automatic destructive continuation.
- T7.2 Implement integrity-checked restore, conflict decisions, and missing-parent handling.
- T7.3 Display/query history with meaningful errors and payload status.
Gate: restored bytes match fixtures; occupied destinations survive unchanged; restart recovers state correctly; unresolved cases remain visible and non-destructive.

### M8 — Explicit permanent purge
Dependencies: M7. Requirements: R09, R10.
- T8.1 Prepare a purge-only recovery-item proposal and dedicated confirmation.
- T8.2 Implement validated per-file removal with intent/outcome recording.
- T8.3 Test altered payloads, replay, interrupted purge, and retention reminders.
Gate: no purge without its own approval; only selected app-owned payloads affected; age never triggers deletion; logical and physical-byte claims separated.

### M9 — Complete minimal popup experience (revised 18 October 2026)
Dependencies: M2–M8. Requirements: R06, R10, R11, R13.
- T9.1 Provide the root script and explicit start/register-temp/protect/complete commands.
- T9.2 Build the compact unchecked checkbox review, keep/protect action, and no-candidate message.
- T9.3 Connect separate exact confirmation, quarantine outcomes, restore, and purge popups.
- T9.4 Fail closed when tkinter/display/popup construction is unavailable or closes unexpectedly.
Gate: real disposable fixture workflow works through popup orchestration; candidates default to
keep; unavailable GUI sessions leave reviewable proposals without mutation; approval is
digest-bound; the root script and installed command work. Earlier large-desktop tasks are
superseded.

### M10 — Integration and project documentation
Dependencies: M9. Requirements: R12, R15, R16.
- T10.1 Finalize README and CODEX_WORKFLOW.md with tested PowerShell commands.
- T10.2 Write SAFETY.md with exact supported-filesystem and approval threat boundaries.
- T10.3 Verify clean setup and documented task workflow against disposable examples.
Gate: a new user can run from documentation; no requirement for an API key, cloud account, or BMAD at application runtime; no undocumented CLI mutations.

### M11 — Native validation and script handoff (revised 18 October 2026)
Dependencies: M10. Requirements: R14, R15, R16.
- T11.1 Add Windows CI for lint, typing, core/integration/native tests, and popup logic tests.
- T11.2 Smoke-test the root script, installed command, and missing-popup pending path.
- T11.3 Execute the complete acceptance matrix, record platform/versions/results, and remove owned disposable development artifacts.
- T11.4 Audit every R ID and plan section against delivered behavior; fix gaps.
Gate: all required core/native/workflow tests and entry-point smoke checks pass on Windows, or
report a specifically incomplete release. Desktop packaging is not required. No claim of full
completion based only on mocked/non-Windows tests. Do not publish or push without authorisation.

## 13. Acceptance test matrix

Tests must use disposable fixtures with unique test roots and app-state directories. Never clean actual user folders. Native safety checks skipped due to platform or privileges remain unverified release gates.

| Test | Required observation |
|---|---|
| Scan cancellation | No user-file mutation; incomplete status and stop progress |
| Misleading names | `final_temp.py`, valuable `.log`, original PNG and raw data protected/uncertain, not auto-junk |
| Git protection | Tracked files and VCS metadata never selected; failed Git lookup reported |
| Task baseline | Pre-existing files preserved; added files marked observed rather than proven agent-created |
| Active task | Cleanup denied until task is resolved |
| Approval | None/cancel/replay/expired/serialized-forgery causes no execution |
| Changed selection | New proposal and human confirmation required |
| Content changed | Same-size changed content detected; no stale move |
| Identity changed | Replaced file with matching name/size does not inherit approval |
| Boundary escape | Symlinks, junctions, parent swaps, traversal and case-prefix traps fail closed |
| Unsupported types | ADS, hard links, placeholders, unsupported volumes skipped with reason |
| Locked files | No forced access; clear skipped/error outcome |
| Partial batch | Completed items recoverable; failed items untouched; totals correct |
| Crash injection | Restart reconciles intent and reality without blindly deleting/retrying |
| Restore | Byte equality and supported metadata preserved; original path recovered where free |
| Restore conflict | Existing destination untouched; explicit alternative handling |
| Purge | Separate approval; only selected verified payloads removed |
| Retention | Old recovery payload remains until human approval |
| Concurrency | Second conflicting operation rejected; journal and payloads consistent |
| User strings | Spaces, Unicode, quotes and shell metacharacters are data, never commands |
| Privacy | No unexpected network calls, telemetry, secret-content previews or uploads |
| Script entry points | Root script and installed command use the same implementation |
| Missing popup | Pending proposal stored; no mutation; exit 6 and exact review command shown |
| Popup decisions | Unchecked/select/protect/cancel default safely and exact confirmation binds the digest |

Use unit tests for policy/state machines, real filesystem integration tests for operations, native Windows tests for OS behavior, and UI tests for confirmation/cancellation. Avoid tests that merely repeat implementation logic.

Performance target, measured not asserted: on the recorded test machine, scan 10,000 small ordinary local fixture files with visible progress, cancellation acknowledgement within about 2 seconds, and a responsive UI. Report duration and machine details; cold disks/antivirus may vary. Do not set a marketing performance claim from synthetic results alone. Cap displayed preview content at 64 KiB and use batched UI updates. Set a default 100,000-entry scan limit with explicit incomplete status; a user can deliberately raise it.

## 14. Execution discipline for Codex

For each small task: read relevant plan → inspect current code → implement → test → review diff → update tracker → continue. At milestone completion reread this plan's applicable sections and verify all listed acceptance conditions.

Tracker columns: task ID, requirement IDs, status, code location, check command, observed result, platform, remaining limitation. Mark completion only with evidence. Record failures honestly. Do not create separate daily narrative logs.

If context is lost, reload this plan, tracker, applicable AGENTS.md, Git status, and recent commits before editing. Never assume an earlier passing result applies after related code changed.

Routine decisions are autonomous. Stop only for real blockers or material plan conflicts. Do not ask permission after every small iteration. The human approval required by the finished product is separate from authority to implement and test on synthetic fixtures.

The tracker and prompts guide behavior; they are not a security sandbox or proof of correctness. Automated acceptance tests and actual review provide evidence. An agent must never claim that merely reading a Markdown plan guarantees compliance.

## 15. Git, temporary files, and deliverables

Verify origin points to akshay9192/AI-cleaner. Preserve the existing license and user changes. Use a dedicated implementation branch or the owner's existing appropriate branch. Make focused local milestone commits after relevant tests pass. Inspect staged content explicitly; never blindly stage credentials, personal paths, recovery data, screenshots, or large artifacts.

Owner intends to place this plan locally and push it. This document does not itself authorise the agent to push implementation, publish releases, or deploy. Follow explicit session authorisation; never force-push or rewrite unrelated history.

Maintain one disposable development-artifact directory when needed. Fixture cleanup must target only paths created and recorded by the current test/task, with no link traversal. Remove owned temporary scripts, sample outputs, intermediate build scratch, and temporary validation images once no longer required.

Do not delete pre-existing files or classify all new/untracked files as temporary. Preserve source,
tests, manifests, uv.lock, required configuration, this plan, tracker, docs, and the root script.
The virtual environment is reusable development state, not automatically garbage. User recovery
payloads must never be removed as development cleanup.

Use targeted .gitignore entries for environment, app/test state, logs, cache, build outputs and transient files. Do not ignore all Markdown, images, or data indiscriminately.

Final repository deliverables:
- Complete source and functioning minimal script/popup tool with one shared core.
- Tests and Windows CI definition.
- pyproject.toml and locked dependencies.
- README, SAFETY.md, CODEX_WORKFLOW.md, concise VALIDATION.md.
- This plan and completed evidence tracker.
- Root `ai_cleaner.py` script and compatible installable command.

## 16. Definition of done

All R01–R16 and M0–M11 revised gates satisfied for the supported Windows scope. No required TODOs,
fake results, approval bypasses, unreviewed dangerous fallbacks, or silent exceptions. The real
tool supports task start, fingerprinted temp registration/protection, explicit completion, pending
review, exact popup approval, quarantine, restore, history, and separately approved purge. Native
safety tests and both script/package entry points have actual evidence. PySide6 and PyInstaller
results are superseded historical evidence, not release gates.

Report exact setup/launch/test commands and package location. Distinguish verified, implemented-but-unverified, and blocked work. Report branch/commits and whether anything was pushed. State native platform gaps if any. Do not call an unverified build production-ready or guarantee zero data loss.

Keep the final response concise; detailed evidence belongs in the tracker and VALIDATION.md.

## 17. Future work — explicitly not required for v0.1

- Benchmark against existing cleanup tools and interview frequent AI users.
- Add supported adapters for Claude Code/Cursor and documented vendor events.
- macOS/Linux filesystem adapters and platform-specific packages.
- More file types, safe cross-volume recovery, and cloud-provider-aware behavior.
- Better evidence of task ownership, optional filesystem observation, multi-task attribution.
- Optional local language-model explanations that cannot approve or execute removal.
- Signed installer, verified update channel, accessibility audit, and broader compatibility testing.
- Team policies and commercial packaging after repeated-use and willingness-to-pay validation.

Do not build these because they sound useful. Add them only through an explicitly approved later plan revision.

## 18. Research and technical references

These sources informed the plan; they are not runtime dependencies or evidence that this implementation has been audited. External pages can change. Recheck exact APIs while implementing, especially Windows filesystem operations. Product decisions and scope above are this project's choices, not claims that competitors lack them.

- Project Artifact Cleanup: https://github.com/ShiYuPro/project-artifact-cleanup
- Workspace Metabolism: https://github.com/metabolism-tools/workspace-metabolism
- codex-clean: https://github.com/Merlin-Arthur05/codex-clean
- ai-trash: https://github.com/forethought-studio/ai-trash
- Git clean semantics: https://git-scm.com/docs/git-clean
- BMAD setup and workflow guidance: https://docs.bmad-method.org/start/install-bmad/
- Qt for Python: https://doc.qt.io/qtforpython-6/
- Python sqlite3 documentation: https://docs.python.org/3.12/library/sqlite3.html
- PyInstaller platform/build behavior: https://pyinstaller.org/en/stable/operating-mode.html
- Windows reparse points: https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-points
- Related deliverables/clutter feature request (user report): https://github.com/openai/codex/issues/21104

## 19. One-message implementation kickoff

Paste into Codex from the AI-cleaner checkout after placing this file there:

```text
Use AI_CLEANER_PROJECT_PLAN.md as the authoritative v0.1 contract.
Read it completely and inspect AGENTS.md, Git state, and existing code.
Use the installed BMAD build/review workflow and implement M0 through M11
in small verified iterations. Maintain IMPLEMENTATION_STATUS.md with
requirement-to-code-to-test evidence. Reread the relevant plan sections
before each task and audit the full plan at completion. Continue through
routine decisions without asking me to proceed. Preserve user changes,
use disposable fixtures for cleanup tests, and remove only temporary
artifacts you created. Do not push, publish, or run cleanup on my real
files. Report genuine blockers and platform checks you cannot perform.
```
