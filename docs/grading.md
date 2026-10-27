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

The table columns are `instance_slug`, `email`, `name`, `role`, `in_space`,
`target`, and `in_app_target ({target})`. Email is taken from instance
metadata first (display name / owner fields), then from the Client API
space-members endpoint when available. Role comes only from space members
(left blank if that lookup fails). Fix any `in_space = NO` rows (missing
instance or API key without access) before a full check, or pass
`--skip-missing-instances` on `check`.
`in_app_target` is empty when the manifest item's handin `src` can't be
mapped under `/assignments/handin/<instance_slug>/...` — check that student's
`src` before relying on `{target}` in `-c`.


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

1. Queue for the student app until no other grade job holds it
   (see [Queuing per student app](#queuing-per-student-app)).
2. Start `-a` on the student instance (development snapshot).
3. Wait until the app is `RUNNING`.
4. Execute `-c` (with grade-owned stdout/stderr redirects and a completion
   marker under `/files/grade_results/<run_id>/<instance_slug>/`).
5. Optionally distribute logs to the instructor instance and copy them into
   `--results-dir`.
6. Stop the app.

## Queuing per student app

Only one grade job runs on a given `(org, space, instance, app)` at a time.
A job that arrives while another holds the app **waits its turn** (FIFO) and
then runs — it is not dropped, and no second workload is started, so two
instructors triggering `grade check` together cannot double the resource
usage on a student instance.

Admission has three stages, each announced on the console:

| Stage | Covers | Mechanism |
|-------|--------|-----------|
| Local queue | `--parallel N` workers, a manifest listing a student twice | In-memory FIFO per app key |
| Shared queue | A second `grade check` from another shell or another instructor | Ticket files under `<staging-root>/.nuvolos_grade_queue/`, lowest sequence wins |
| App free | Student-started apps, leftovers from an aborted run | Polls running workloads for the app until none remain |

While queued, the student line shows the position:

```
>>> [stu_a] queued for app [bot] (1 ahead from other runs); waiting…
>>> [stu_a] app [bot] busy (1 workload(s)); queued behind it…
>>> [stu_a] queue turn reached.
```

Admitted students report their wait in the summary
(`queued : 182.0s waiting for the app`).

### Queue wait limit

`--queue-timeout N` bounds the wait (default `0` = wait indefinitely).
A student still queued after *N* seconds is reported **failed** with
`timed out … waiting in the queue`, never force-started. Use it when a run
must not block behind a colleague's long validation:

```
nuvolos grade check --queue-timeout 1800 ...
```

### Stuck queues

Ticket files are self-healing: an entry older than one hour (a crashed CLI,
a closed shell) is pruned automatically and the next job proceeds. A leftover
*workload* is not force-stopped — if an aborted run left an app up and nobody
will clear it, stop it explicitly:

```
nuvolos apps stop -o <org> -s <space> -i <student_instance> -a <app_slug>
```

The shared queue needs a writable staging tree (`/files/.nuvolos_grade` by
default). If tickets cannot be written, `check` logs a warning and falls back
to the running-workload check, which still prevents concurrent starts.

## Command placeholders

`-c` / `--command` is expanded per student:

| Placeholder | Value |
|-------------|--------|
| `{instance_slug}` | Student instance slug |
| `{instance}` | Same as `{instance_slug}` |
| `{target}` | In-app path to the student's own submission (see below) |

### `{target}`: in-app submission path

`check` starts your instructor workload on each student instance
(`start_app`) to run the validation command. Whenever an instructor's API
key starts an app on a student/group instance that has a visible assignment
bundle, the platform automatically bind-mounts that student's own submitted
files, read-only, under `/assignments/handin/...` inside the app container —
the same handin storage nvcollect reads from at
`/files/assignments-review/handin/<instance_slug>/...` on the master.

`{target}` is pre-computed per student from the manifest and expands to that
in-app path, so it always points at real files inside the student app (never
at a master-only path):

```
-c 'python {target}/main.py'
```

If the manifest has no derivable handin `src` for a student (e.g. a manually
authored manifest), `{target}` expands to an empty string — inspect the
`resolve-manifest` output first if you rely on it.

Example combining `{target}` with the per-student slug for logging:

```
-c 'python grade_script.py --student {instance_slug} --submission {target}'
```

## Useful flags on `check`

| Flag | Effect |
|------|--------|
| `--dry-run` | Plan only; no collect (unless you already have a manifest), start, execute, or stop |
| `--limit N` | Process at most *N* students (useful for staging) |
| `--all` | Process every resolved student; ignores `--limit` |
| `-i` / `--instance` | Only this student instance slug |
| `--parallel N` | Run up to *N* student checks concurrently (requires `--continue-on-error` for true parallelism; otherwise forced sequential so the run can stop on first failure) |
| `--exec-timeout N` | Seconds to wait for the validation command to finish before giving up. `0` disables the timeout (wait indefinitely) — use when the command itself must stay up for a long external test run. Default: `GRADE_EXEC_TIMEOUT_SECS` env var, or `600` |
| `--queue-timeout N` | Seconds to wait in the queue when another grade job holds a student app. `0` (default) waits indefinitely in FIFO order; a student still queued after *N* seconds is reported failed |
| `--continue-on-error` | Keep going after a lifecycle/validation failure |
| `--skip-missing-instances` | Skip manifest instances not visible via `instances list` |
| `--pull-logs` / `--no-pull-logs` | After execute, copy logs to instructor (default: pull) |
| `--instructor-instance` | Instructor instance that receives distributed logs (default: `NV_CONTEXT` instance or `master`) |

If your validation command needs to keep a server running for a long
external test (e.g. a chatbot server polled by another platform for up to an
hour), make `-c` itself block for that duration — e.g. wrap it with
`timeout 3600 ...` or have it wait on a signal from the external platform —
and raise `--exec-timeout` above that duration (or pass `0` to disable it
entirely):

```
nuvolos grade check \
  -c 'timeout 3600 python server.py' \
  --exec-timeout 4200 \
  ...
```

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

!!! note "Waiting for results"

    The per-student work directory is created by the validation command itself
    (`mkdir -p`), so it does not exist when grade starts watching for it. All
    readiness checks run through a shared queue that treats a missing directory
    as "not ready yet" — the backend answers `404` for it — and widens the poll
    interval while it stays absent, instead of each student spinning at a fixed
    rate. `.cmd_done` and `.cmd_exit.<code>` are read from the same directory
    listing, so completion costs one request per check rather than two.

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
| Run appears to hang at "queued for app …" | Another grade job holds that app; it starts automatically when the holder finishes, or bound it with `--queue-timeout` ([Queuing per student app](#queuing-per-student-app)) |
| Student failed: "timed out … waiting in the queue" | `--queue-timeout` elapsed while another job held the app; raise it or clear a leftover workload |
| Student failed: "timed out … waiting for command completion" | The validation command never wrote `.cmd_done`; check `output.log` under the results dir, or raise `--exec-timeout` (`0` waits indefinitely) |

## Related guides

- [Execute commands](execute_commands.md) — how `apps execute` works and default log locations
- [List running applications](list_running_applications.md) — verify app state
- [Distribution management](distribution_management.md) — how files move between instances (used for log pull)
- [Command reference](commands.md) — full CLI surface (auto-generated section includes `grade` once released)
