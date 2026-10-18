# Native popup acceptance

Run this only in an ordinary interactive Windows PowerShell session. The fixture is ignored by
Git, contains synthetic files only, and keeps state/recovery outside each selected project while
remaining on the same volume.

## Prepare

From the AI-cleaner checkout:

```powershell
$repo = (Resolve-Path .).Path
$python = "$repo\.venv\Scripts\python.exe"
$fixture = & $python "$repo\scripts\prepare_acceptance_fixture.py" | ConvertFrom-Json
```

The generated `AGENTS.md` files are repository-local task guidance adapted from
`docs/CODEX_WORKFLOW.md`; the script does not alter global instructions.

## Cancel, review, quarantine, and restore

```powershell
$project = $fixture.popup_project
$state = $fixture.popup_state
$task = & $python "$repo\ai_cleaner.py" start --root $project --label "Native popup acceptance" --state-dir $state | ConvertFrom-Json

[System.IO.Directory]::CreateDirectory("$project\scratch") | Out-Null
[System.IO.File]::WriteAllText("$project\scratch\preview.tmp", "synthetic disposable preview`n")
& $python "$repo\ai_cleaner.py" register-temp --task $task.task_id --path "scratch\preview.tmp" --state-dir $state

[System.IO.Directory]::CreateDirectory("$project\deliverables") | Out-Null
[System.IO.File]::WriteAllText("$project\deliverables\final-output.txt", "synthetic protected result`n")
& $python "$repo\ai_cleaner.py" protect --task $task.task_id --path "deliverables" --state-dir $state

$completeOutput = & $python "$repo\ai_cleaner.py" complete --task $task.task_id --state-dir $state
$completeOutput
$proposal = [regex]::Match(($completeOutput -join "`n"), 'review --proposal ([0-9a-f-]+)').Groups[1].Value
& $python "$repo\ai_cleaner.py" review --proposal $proposal --state-dir $state

$history = & $python "$repo\ai_cleaner.py" history --root $project --state-dir $state --json | ConvertFrom-Json
$run = ($history.operations | Where-Object action -eq "quarantine" | Select-Object -First 1).id
& $python "$repo\ai_cleaner.py" restore --run $run --state-dir $state
```

Human actions, in order:

1. In the popup opened by `complete`, leave everything unchecked and click **Cancel**.
2. In the popup opened by `review`, check only `scratch\preview.tmp`, click **Move selected to
   quarantine**, inspect the exact summary/digest, then click **OK**.
3. In the restore popup, check the one payload, click **Continue with restore**, inspect the exact
   summary/digest, then click **OK**.

Confirm afterward that `existing-input.txt`, `AGENTS.md`, and
`deliverables\final-output.txt` never moved, and that `scratch\preview.tmp` was restored with its
original contents. Closing or cancelling any window must retain everything.

## Separate purge fixture

```powershell
$project = $fixture.purge_project
$state = $fixture.purge_state
$task = & $python "$repo\ai_cleaner.py" start --root $project --label "Native purge acceptance" --state-dir $state | ConvertFrom-Json
[System.IO.File]::WriteAllText("$project\purge-me.tmp", "synthetic purge payload`n")
& $python "$repo\ai_cleaner.py" register-temp --task $task.task_id --path "purge-me.tmp" --state-dir $state
& $python "$repo\ai_cleaner.py" complete --task $task.task_id --state-dir $state

$history = & $python "$repo\ai_cleaner.py" history --root $project --state-dir $state --json | ConvertFrom-Json
$run = ($history.operations | Where-Object action -eq "quarantine" | Select-Object -First 1).id
& $python "$repo\ai_cleaner.py" purge --run $run --state-dir $state
```

For `complete`, check only `purge-me.tmp`, choose quarantine, inspect the exact confirmation, and
click **OK**. For `purge`, check the one recovery payload, continue, inspect the separate
irreversible confirmation, and click **OK**. AI-cleaner never purges merely because retention time
has passed.

The popup is an intentional-consent mechanism, not a security boundary against another process
running as the same user. Do not pipe synthetic answers into these commands and do not run them
against Downloads, Documents, a home directory, this source checkout, or other real work.
