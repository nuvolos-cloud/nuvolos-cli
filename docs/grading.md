# Grading

`nuvolos grade` is an instructor workflow for teaching spaces. From the
**master** instance it collects student hand-ins, starts the chosen application
on each student instance, runs a validation command, pulls logs back to the
instructor, and stops the app.

The commands are:

| Command | Purpose |
|---------|---------|
| `nuvolos grade collect` | Copy hand-ins into a local target folder and write `nvcollect_manifest.json` |
| `nuvolos grade resolve-manifest` | Map manifest entries to instance slugs and check space membership |
| `nuvolos grade check` | Optional collect + start / execute / stop per student + pull logs |

## Prerequisites

1. **API key** configured for the instructor account (`nuvolos config`, same as
   other CLI commands).
2. Run from a **teaching space**, on the **master** instance. `NV_CONTEXT` must
   match the `-o` / `-s` you pass, and the instance must be `master`.
3. For `collect` (or `check` without `--skip-collect`): install
   [`nuvolos_collect`](https://github.com/alphacruncher/nv-collect) separately:

```
pip install git+https://github.com/alphacruncher/nv-collect.git
```

`nuvolos_collect` is not bundled with `nuvolos-cli` (dependency and packaging
constraints). You can still run `check` with `--skip-collect` if you already
have a manifest from a previous collect or from the `nvcollect` CLI.

!!! note

    Grade starts **your** instructor workload on each student instance and runs
    the validation command there. It does not attach to a student-started app.
    The working directory for the command is `/files`, same as
    [`nuvolos apps execute`](execute_commands.md).

## Typical workflow

### 1. Collect submissions

Run on the instructor master instance, where hand-ins are visible to
`nuvolos_collect` (default hand-in root under
`/files/assignments-review/handin/`):

```
nuvolos grade collect \
  --assignment-name <bundle_name> \
  --assignment-folder <leaf_folder> \
  --target-folder /files/collected/<assignment>
```

- `--assignment-name` — assignment / bundle name under hand-in.
- `--assignment-folder` — leaf folder name inside each student submission.
- `--target-folder` — destination for collected trees and
  `nvcollect_manifest.json`.

### 2. (Optional) Inspect the manifest

```
nuvolos grade resolve-manifest \
  -m /files/collected/<assignment> \
  -o <org_slug> \
  -s <space_slug>
```

`-m` accepts either the collect directory or the path to
`nvcollect_manifest.json`. Use `-f json` for machine-readable output, or
`-i <instance_slug>` to filter one student.

The table columns are `instance_slug`, `email`, `name`, `role`, `in_space`, and
`target`. Email and role come from the Client API space-members endpoint when
available (fallback: instance display name). Fix any `in_space = NO` rows
(missing instance or API key without access) before a full check, or pass
`--skip-missing-instances` on `check`.


### 3. Run validation on student apps

End-to-end (collect + check):

```
nuvolos grade check \
  -o <org_slug> \
  -s <space_slug> \
  -a <app_slug> \
  -c 'python assignments/main.py' \
  -r /files/grade_runs \
  --assignment-name <bundle_name> \
  --assignment-folder <leaf_folder> \
  --target-folder /files/collected/<assignment> \
  --limit 3
```

Reuse an existing collect:

```
nuvolos grade check \
  -o <org_slug> \
  -s <space_slug> \
  -a <app_slug> \
  -c 'python assignments/main.py' \
  -r /files/grade_runs \
  --skip-collect \
  -m /files/collected/<assignment>
```

Per student, `check` does:

1. Start `-a` on the student instance (development snapshot).
2. Wait until the app is `RUNNING`.
3. Execute `-c` (with grade-owned stdout/stderr redirects and a completion
   marker under `/files/grade_results/<run_id>/<instance_slug>/`).
4. Optionally distribute logs to the instructor instance and copy them into
   `--results-dir`.
5. Stop the app.

## Command placeholders

`-c` / `--command` is expanded per student:

| Placeholder | Value |
|-------------|--------|
| `{instance_slug}` | Student instance slug |
| `{instance}` | Same as `{instance_slug}` |
| `{target}` | Manifest `target` path for that item |

Example:

```
-c 'python grade_script.py --student {instance_slug}'
```

## Useful flags on `check`

| Flag | Effect |
|------|--------|
| `--dry-run` | Plan only; no collect (unless you already have a manifest), start, execute, or stop |
| `--limit N` | Process at most *N* students (useful for staging) |
| `--all` | Process every resolved student; ignores `--limit` |
| `-i` / `--instance` | Only this student instance slug |
| `--parallel N` | Run up to *N* student checks concurrently (requires `--continue-on-error` for true parallelism; otherwise forced sequential so the run can stop on first failure) |
| `--continue-on-error` | Keep going after a lifecycle/validation failure |
| `--skip-missing-instances` | Skip manifest instances not visible via `instances list` |
| `--pull-logs` / `--no-pull-logs` | After execute, copy logs to instructor (default: pull) |
| `--instructor-instance` | Instructor instance that receives distributed logs (default: `NV_CONTEXT` instance or `master`) |

If any student fails and `--dry-run` is not set, `check` exits non-zero and
points at the results JSON.

## Results layout

Each run gets a UTC timestamp id (`run_id`, e.g. `20260910T141522Z`).

On the **instructor** side (`-r` / `--results-dir`):

```
<results-dir>/
  grade_run_<run_id>.json          # full run summary
  <run_id>/
    <student_instance_slug>/
      output.log
      error.log
      combined.txt                 # stdout + stderr excerpts when available
      metadata.json                # when present
```

On each **student** instance during the run:

```
/files/grade_results/<run_id>/<student_instance_slug>/
  output.log
  error.log
  .cmd_done                        # exit code written when the command finishes
  .cmd_exit.<code>
```

`grade_run_*.json` includes counts (`ok`, `failed`, `skipped`, `dry_run`),
per-student status, execute metadata, and log-pull details. Console output
prints the counts plus `results_file` and `results_run_dir`.

!!! note

    Grade owns stdout/stderr paths. Platform default capture only keeps the last
    segment of a command sequence and skips defaults when the command string
    contains `>`. You do not need to add your own redirects in `-c` for normal
    grading; grade wraps the body and waits on `.cmd_done` before pulling logs
    or stopping the app. See also [Execute commands](execute_commands.md).

## Staging a first run

Recommended order on a new assignment:

1. `resolve-manifest` on an existing collect (or collect once, then resolve).
2. `check --dry-run --limit 1 ...` to validate flags and student selection.
3. `check --limit 1 --continue-on-error ...` on one real student.
4. Scale with `--limit` / `--all` and optional `--parallel` once the single-student path is clean.

## Common failures

| Symptom | Likely cause |
|---------|----------------|
| Must run from master / teaching space | Wrong `NV_CONTEXT`, non-teaching space, or not on `master` |
| `nuvolos_collect is required` | Collect path without nv-collect installed; install it or use `--skip-collect -m ...` |
| Manifest not found | Bad `-m` / `--target-folder`; expect `nvcollect_manifest.json` |
| Instance not found in space | Manifest slug missing from `instances list`, or API key lacks access |
| App slug not found on instance | `-a` not present on that student's development snapshot |
| Validation command exited with code ≠ 0 | Student script failed; inspect `output.log` / `error.log` under results |
| Log pull failed / files missing on master | Distribute/FS settle issue; check `/files/grade_results/<run_id>/...` on master after refresh |
| Parallelism ignored | Without `--continue-on-error`, workers are forced to 1 so the run can stop after the first failure |

## Related guides

- [Execute commands](execute_commands.md) — how `apps execute` works and default log locations
- [List running applications](list_running_applications.md) — verify app state
- [Distribution management](distribution_management.md) — how files move between instances (used for log pull)
- [Command reference](commands.md) — full CLI surface (auto-generated section includes `grade` once released)
