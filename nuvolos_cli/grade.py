"""Instructor assignment testing and grading.

The commands are intended for the instructor application in a teaching
space. They collect submissions and run the configured validation command in
each selected student application.
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import click
from click import ClickException
from tabulate import tabulate

from .api_client import (
    distribute_content,
    execute_command_in_app,
    list_apps,
    list_files,
    list_instances,
    list_spaces,
    start_app,
    stop_app,
    wait_for_app_running,
    wait_for_task,
)
from .config import check_api_key_configured
from .logging import clog
from .utils import _model_to_dict

import shutil
import shlex

MANIFEST_FILENAME = "nvcollect_manifest.json"
TEACHING_SPACE_TYPE = "TEACHING"


def _cmd_work_dir(run_id: str, instance_slug: str) -> str:
    return f"/files/grade_results/{run_id}/{instance_slug}"


def _cmd_done_path(run_id: str, instance_slug: str) -> str:
    """Side-channel completion file written after the student command finishes."""
    return f"{_cmd_work_dir(run_id, instance_slug)}/.cmd_done"


def _cmd_output_paths(run_id: str, instance_slug: str) -> tuple[str, str]:
    """Known stdout/stderr paths owned by grade (not platform default redirects)."""
    base = _cmd_work_dir(run_id, instance_slug)
    return f"{base}/output.log", f"{base}/error.log"


def _wrap_command_with_done_file(
    command: str,
    *,
    done_file: str,
    output_log: str,
    error_log: str,
) -> str:
    """Run command with explicit redirects, then write a completion/exit marker.

    Nuvolos default capture only keeps the last segment of a command sequence
    and skips defaults entirely when the submitted string contains `>`. Grade
    therefore owns stdout/stderr paths: redirect the validation body itself,
    then write `.cmd_done` / `.cmd_exit.<code>` with POSIX shell only (no
    Python runtime required in the student app).
    """
    work = str(Path(done_file).parent)
    work_q = shlex.quote(work)
    out_q = shlex.quote(output_log)
    err_q = shlex.quote(error_log)
    done_q = shlex.quote(done_file)
    # Marker writes must stay pure shell so RStudio / python3-only / no-Python
    # images can still signal completion. `.cmd_exit.$ec` is listed via the
    # files API (name encodes the exit code); content may be empty.
    return (
        f"work={work_q}\n"
        f"done_file={done_q}\n"
        f"mkdir -p \"$work\"\n"
        f"{{\n{command}\n}} > {out_q} 2> {err_q}\n"
        f"ec=$?\n"
        f"printf '%s' \"$ec\" > \"$done_file\"\n"
        f": > \"$work/.cmd_exit.$ec\"\n"
        f"exit \"$ec\""
    )







def _require_teaching_master(org_slug: str, space_slug: str) -> None:
    """Require the current context to be a teaching-space master instance."""
    try:
        context = json.loads(os.environ.get("NV_CONTEXT", ""))
    except json.JSONDecodeError as exc:
        raise ClickException("NV_CONTEXT must contain valid JSON") from exc
    if not isinstance(context, dict):
        raise ClickException("NV_CONTEXT must contain a JSON object")

    context_org = context.get("org_slug") or context.get("org")
    context_space = context.get("space_slug") or context.get("space")
    context_instance = context.get("instance_slug") or context.get("instance")
    if (context_org, context_space) != (org_slug, space_slug):
        raise ClickException(
            "nuvolos grade must run in the selected organization and space "
            "from NV_CONTEXT"
        )
    if context_instance != "master":
        raise ClickException(
            "nuvolos grade must run from the master instance of a teaching space"
        )

    spaces = list_spaces(org_slug=org_slug)
    selected = None
    for space in spaces:
        data = _model_to_dict(space) if not isinstance(space, dict) else space
        if (data.get("slug") or data.get("short_id")) == space_slug:
            selected = data
            break
    if selected is None:
        raise ClickException(f"Space '{space_slug}' is not visible in organization '{org_slug}'")
    space_type = str(selected.get("type") or selected.get("space_type") or "").upper()
    if space_type != TEACHING_SPACE_TYPE:
        raise ClickException(
            f"nuvolos grade is only supported in teaching spaces; "
            f"'{space_slug}' is {space_type or 'unknown'}"
        )
    clog.info(f"Validated teaching-space master context: {org_slug}/{space_slug}.")


def _validate_grade_environment(org_slug: str, space_slug: str) -> None:
    # Same API-key resolution as `nuvolos apps list` and other CLI commands.
    check_api_key_configured()
    _require_teaching_master(org_slug, space_slug)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _require_nuvolos_collect():
    try:
        import nuvolos_collect  # noqa: F401
    except ImportError as exc:
        raise ClickException(
            "nuvolos_collect is required for grade collect. Install it, e.g.\n"
            "  pip install git+https://github.com/alphacruncher/nv-collect.git\n"
            f"Original error: {exc}"
        ) from exc


def collect_submissions(
    assignment_name: str,
    assignment_folder: str,
    target_folder: str,
) -> int:
    """Run nvcollect collect() in-process."""
    clog.info(
        f"Collecting submissions: assignment={assignment_name!r}, "
        f"folder={assignment_folder!r}, destination={target_folder}."
    )
    _require_nuvolos_collect()
    from nuvolos_collect.collect import collect as nv_collect

    code = nv_collect(assignment_name, assignment_folder, target_folder)
    if code not in (0, None):
        raise ClickException(f"Collect failed with code {code}")
    clog.info(f"Collect completed into {target_folder}")
    return 0


def read_manifest(manifest_path: str | Path) -> dict:
    """Load nvcollect_manifest.json from a file or collect target directory."""
    path = Path(manifest_path).expanduser().resolve()

    if path.is_dir():
        try:
            from nuvolos_collect.handback.utils import read_manifest as nv_read

            return nv_read(str(path))
        except ImportError:
            path = path / MANIFEST_FILENAME
        except Exception:
            path = path / MANIFEST_FILENAME

    if path.is_dir():
        path = path / MANIFEST_FILENAME

    if not path.is_file():
        raise ClickException(
            f"Manifest not found: {path}. Expected {MANIFEST_FILENAME} "
            "or a directory containing one."
        )

    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ClickException(f"Invalid manifest JSON at {path}: {exc}") from exc

    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ClickException(
            f"Manifest at {path} must be an object with an 'items' array."
        )
    return data


def instance_slug_from_item(item: dict) -> str:
    """Derive instance_slug from a nvcollect manifest item."""
    if not isinstance(item, dict):
        raise ClickException(f"Manifest item must be an object, got {type(item)!r}")

    target = item.get("target") or ""
    if target:
        slug = Path(str(target).rstrip("/")).name
        if slug:
            return slug

    src = item.get("src") or ""
    parts = Path(str(src)).parts
    try:
        handin_idx = parts.index("handin")
        return parts[handin_idx + 1]
    except (ValueError, IndexError) as exc:
        raise ClickException(
            f"Cannot derive instance_slug from manifest item: {item!r}"
        ) from exc


def expand_command_template(
    template: str, *, instance_slug: str, target: str = ""
) -> str:
    return (
        template.replace("{instance_slug}", instance_slug)
        .replace("{instance}", instance_slug)
        .replace("{target}", target or "")
    )


def resolve_students(
    manifest: dict,
    org_slug: str,
    space_slug: str,
    *,
    instance_filter: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Map manifest items to instance slugs; verify visibility via instances list."""
    clog.info(
        f"Resolving students from manifest for {org_slug}/{space_slug}"
        + (f" (filter={instance_filter})" if instance_filter else "") + "."
    )
    instances = list_instances(org_slug=org_slug, space_slug=space_slug)
    clog.info(f"Found {len(instances)} visible instance(s) in the selected space.")
    by_slug: dict[str, dict] = {}
    for inst in instances:
        d = _model_to_dict(inst) if not isinstance(inst, dict) else inst
        slug = d.get("slug") or d.get("short_id")
        if slug:
            by_slug[str(slug)] = d

    students: list[dict] = []
    for idx, item in enumerate(manifest.get("items") or []):
        slug = instance_slug_from_item(item)
        if instance_filter and slug != instance_filter:
            continue
        meta = by_slug.get(slug)
        students.append({
            "index": idx, "instance_slug": slug, "src": item.get("src"),
            "target": item.get("target"),
            "instance_name": (meta or {}).get("name"),
            "found_in_space": meta is not None,
        })

    if instance_filter and not students:
        raise ClickException(f"No manifest item matched --instance {instance_filter!r}")
    if limit is not None:
        students = students[: max(0, limit)]
    clog.info(f"Resolved {len(students)} student submission(s).")
    return students


def _serialize_execute_result(result) -> dict:
    if result is None:
        return {}
    if isinstance(result, dict):
        return result
    try:
        return _model_to_dict(result)
    except Exception:
        return {"raw": str(result)}


def _files_area_rel(path: str | None) -> str | None:
    """Convert /files/... app path to files-area relative path for list_files."""
    if not path:
        return None
    p = str(path).strip()
    for prefix in ("/files/", "files/"):
        if p.startswith(prefix):
            return p[len(prefix) :]
    return p.lstrip("/")


def _instructor_instance_slug() -> str:
    try:
        context = json.loads(os.environ.get("NV_CONTEXT", "") or "{}")
    except json.JSONDecodeError:
        context = {}
    if isinstance(context, dict):
        return (
            context.get("instance_slug")
            or context.get("instance")
            or "master"
        )
    return "master"


def _task_id(task) -> int | None:
    if task is None:
        return None
    d = _model_to_dict(task) if not isinstance(task, dict) else task
    for key in ("tkid", "id", "task_id"):
        val = d.get(key)
        if val is not None:
            try:
                return int(val)
            except (TypeError, ValueError):
                continue
    return None


def _wait_for_files_area_path(
    *,
    org_slug: str,
    space_slug: str,
    instance_slug: str,
    rel_path: str,
    timeout_secs: int = 90,
    stable_rounds: int = 2,
    require_nonzero_size: bool = True,
) -> bool:
    """Poll files list until path exists and size is stable.

    When require_nonzero_size is True (default), size 0 is not treated as
    complete — empty files can appear while a command is still running.
    """
    start = time.time()
    last_size = None
    stable = 0
    parent = str(Path(rel_path).parent).replace("\\", "/")
    name = Path(rel_path).name
    if parent in (".", ""):
        parent = ""
    while time.time() - start < timeout_secs:
        try:
            entries = list_files(
                org_slug=org_slug,
                space_slug=space_slug,
                instance_slug=instance_slug,
                snapshot_slug="development",
                area="files",
                local_path=parent or None,
            )
        except Exception as exc:
            clog.debug(f"list_files poll failed for {rel_path}: {exc}")
            time.sleep(2)
            continue
        size = None
        for entry in entries or []:
            d = _model_to_dict(entry) if not isinstance(entry, dict) else entry
            short = d.get("short_id") or d.get("name") or d.get("slug") or ""
            os_path = str(d.get("os_path") or d.get("path") or "")
            if short == name or os_path.endswith(rel_path) or os_path.endswith(name):
                size = d.get("size")
                if size is None:
                    size = d.get("storage_used")
                break
        if size is not None:
            try:
                size_n = int(size)
            except (TypeError, ValueError):
                size_n = -1
            if require_nonzero_size and size_n <= 0:
                stable = 0
                last_size = size_n
            elif size_n == last_size:
                stable += 1
                if stable >= stable_rounds:
                    return True
            else:
                stable = 0
                last_size = size_n
        time.sleep(2)
    return False


def _parse_exit_code_from_listing(
    *,
    org_slug: str,
    space_slug: str,
    instance_slug: str,
    work_rel: str,
) -> int | None:
    """Read `.cmd_exit.<code>` from a files-area listing (no content fetch)."""
    try:
        entries = list_files(
            org_slug=org_slug,
            space_slug=space_slug,
            instance_slug=instance_slug,
            snapshot_slug="development",
            area="files",
            local_path=work_rel or None,
        )
    except Exception as exc:
        clog.debug(f"list_files exit-code probe failed for {work_rel}: {exc}")
        return None
    best = None
    for entry in entries or []:
        d = _model_to_dict(entry) if not isinstance(entry, dict) else entry
        short = str(d.get("short_id") or d.get("name") or d.get("slug") or "")
        if not short.startswith(".cmd_exit."):
            continue
        suffix = short[len(".cmd_exit.") :]
        try:
            best = int(suffix)
        except ValueError:
            continue
    return best


def _wait_for_execute_completion(
    *,
    org_slug: str,
    space_slug: str,
    instance_slug: str,
    done_file: str,
    timeout_secs: int | None = None,
) -> int:
    """Block until the done-file exists; return the validation exit code."""
    if timeout_secs is None:
        timeout_secs = int(os.environ.get("GRADE_EXEC_TIMEOUT_SECS", "600"))
    rel = _files_area_rel(done_file)
    if not rel:
        raise ClickException(f"Invalid done file path: {done_file}")
    work_rel = str(Path(rel).parent).replace("\\", "/")
    if work_rel in (".", ""):
        work_rel = ""
    clog.info(
        f"[{instance_slug}] waiting for command completion via {done_file} "
        f"(timeout={timeout_secs}s)."
    )
    ok = _wait_for_files_area_path(
        org_slug=org_slug,
        space_slug=space_slug,
        instance_slug=instance_slug,
        rel_path=rel,
        timeout_secs=timeout_secs,
        stable_rounds=1,
        require_nonzero_size=True,
    )
    if not ok:
        raise ClickException(
            f"Timed out after {timeout_secs}s waiting for command completion "
            f"on [{instance_slug}] ({done_file}). "
            f"Will attempt to pull any output/error logs already written "
            f"before stopping the app."
        )
    exit_code = _parse_exit_code_from_listing(
        org_slug=org_slug,
        space_slug=space_slug,
        instance_slug=instance_slug,
        work_rel=work_rel,
    )
    if exit_code is None:
        # Done file present but sentinel missing — treat as failure to avoid
        # false "ok" when the writer partially ran.
        clog.warning(
            f"[{instance_slug}] completion file present but no .cmd_exit.<code> "
            f"sentinel under {work_rel or '/'}; assuming exit_code=1."
        )
        exit_code = 1
    clog.info(
        f"[{instance_slug}] command completion signal observed (exit_code={exit_code})."
    )
    return exit_code




def _files_area_entry_exists(
    *,
    org_slug: str,
    space_slug: str,
    instance_slug: str,
    rel_path: str,
) -> bool:
    parent = str(Path(rel_path).parent).replace("\\", "/")
    name = Path(rel_path).name
    if parent in (".", ""):
        parent = ""
    try:
        entries = list_files(
            org_slug=org_slug,
            space_slug=space_slug,
            instance_slug=instance_slug,
            snapshot_slug="development",
            area="files",
            local_path=parent or None,
        )
    except Exception as exc:
        clog.debug(f"list_files existence check failed for {rel_path}: {exc}")
        return False
    for entry in entries or []:
        d = _model_to_dict(entry) if not isinstance(entry, dict) else entry
        short = d.get("short_id") or d.get("name") or d.get("slug") or ""
        os_path = str(d.get("os_path") or d.get("path") or "")
        if short == name or os_path.endswith(rel_path) or os_path.endswith(name):
            return True
    return False



def _read_text_if_exists(path: Path, max_bytes: int = 512_000) -> str | None:
    try:
        if not path.is_file():
            return None
        data = path.read_bytes()[:max_bytes]
        return data.decode("utf-8", errors="replace")
    except OSError:
        return None


def pull_student_logs_to_instructor(
    *,
    org_slug: str,
    space_slug: str,
    student_instance_slug: str,
    app_slug: str,
    execute_info: dict,
    run_id: str,
    results_dir: Path,
    instructor_instance_slug: str = "master",
) -> dict:
    """Copy execute logs from student instance onto instructor instance + results_dir.

    1) Stage unique copies under /files/grade_results/{run_id}/{student}/ on student
    2) Distribute those files to instructor (master) development snapshot
    3) Copy into local results_dir/{student}/ on instructor FS
    """
    pull = {
        "status": "pending",
        "staging_dir": None,
        "instructor_paths": {},
        "local_paths": {},
        "log_excerpts": {},
        "error": None,
    }
    out_p = execute_info.get("output_path")
    err_p = execute_info.get("error_path")
    meta_p = execute_info.get("metadata_path")
    if not out_p and not err_p:
        pull["status"] = "skipped"
        pull["error"] = "execute result had no output/error paths"
        return pull

    # Output/error may legitimately be empty; existence is enough once the
    # command done-file has already been observed by the caller.
    for label, abs_path in (("output", out_p), ("error", err_p), ("metadata", meta_p)):
        rel = _files_area_rel(abs_path)
        if not rel:
            continue
        ok = _wait_for_files_area_path(
            org_slug=org_slug,
            space_slug=space_slug,
            instance_slug=student_instance_slug,
            rel_path=rel,
            timeout_secs=90,
            stable_rounds=1,
            require_nonzero_size=False,
        )
        if not ok:
            clog.warning(
                f"[{student_instance_slug}] timed out waiting for {label} log at {abs_path}"
            )

    staging_dir = f"/files/grade_results/{run_id}/{student_instance_slug}"
    pull["staging_dir"] = staging_dir
    staged_names: list[str] = []
    # Validation already wrote grade-owned logs under staging_dir — distribute
    # those paths directly. Only copy when execute_info points elsewhere
    # (e.g. platform metadata.json under nuvolos_api_out/).
    copies: list[tuple[str, str, str]] = []  # (label, src, dest_name)
    if out_p:
        if out_p.rstrip("/") == f"{staging_dir}/output.log":
            staged_names.append("output.log")
        else:
            copies.append(("output", out_p, "output.log"))
    if err_p:
        if err_p.rstrip("/") == f"{staging_dir}/error.log":
            staged_names.append("error.log")
        else:
            copies.append(("error", err_p, "error.log"))
    if meta_p:
        if meta_p.rstrip("/") == f"{staging_dir}/metadata.json":
            staged_names.append("metadata.json")
        else:
            copies.append(("metadata", meta_p, "metadata.json"))

    try:
        if copies:
            parts = [f"mkdir -p {shlex.quote(staging_dir)}"]
            for _label, src, dest_name in copies:
                parts.append(
                    f"cp -f {shlex.quote(src)} {shlex.quote(staging_dir + '/' + dest_name)}"
                )
                staged_names.append(dest_name)
            parts.append(f"ls -la {shlex.quote(staging_dir)}")
            stage_cmd = " && ".join(parts)
            stage_done = f"{staging_dir}/.stage_done"
            stage_out = f"{staging_dir}/.stage_out.log"
            stage_err = f"{staging_dir}/.stage_err.log"
            clog.info(
                f"[{student_instance_slug}] staging logs under {staging_dir} for instructor pull."
            )
            execute_command_in_app(
                org_slug=org_slug,
                space_slug=space_slug,
                instance_slug=student_instance_slug,
                app_slug=app_slug,
                command=_wrap_command_with_done_file(
                    stage_cmd,
                    done_file=stage_done,
                    output_log=stage_out,
                    error_log=stage_err,
                ),
            )
            _wait_for_execute_completion(
                org_slug=org_slug,
                space_slug=space_slug,
                instance_slug=student_instance_slug,
                done_file=stage_done,
                timeout_secs=int(os.environ.get("GRADE_STAGE_TIMEOUT_SECS", "120")),
            )
        else:
            clog.info(
                f"[{student_instance_slug}] validation logs already under {staging_dir}; "
                f"skipping stage copy."
            )


        # Only distribute files that were requested and actually landed.
        source_files = []
        for name in staged_names:
            abs_staged = f"{staging_dir}/{name}"
            rel_staged = _files_area_rel(abs_staged)
            if rel_staged and _files_area_entry_exists(
                org_slug=org_slug,
                space_slug=space_slug,
                instance_slug=student_instance_slug,
                rel_path=rel_staged,
            ):
                source_files.append(abs_staged)
            else:
                clog.warning(
                    f"[{student_instance_slug}] staged file missing, skipping distribute: "
                    f"{abs_staged}"
                )

        if not source_files:
            pull["status"] = "failed"
            pull["error"] = (
                f"No staged log files found under {staging_dir} after staging command."
            )
            return pull


        clog.info(
            f"[{student_instance_slug}] distributing logs to instructor "
            f"instance [{instructor_instance_slug}]."
        )
        task = distribute_content(
            org_slug=org_slug,
            space_slug=space_slug,
            instance_slug=student_instance_slug,
            snapshot_slug="development",
            target_instances=[
                {
                    "org_slug": org_slug,
                    "space_slug": space_slug,
                    "instance_slug": instructor_instance_slug,
                }
            ],
            source_files=source_files,
            auto_snapshot=False,
            notify_target_users=False,
        )
        tkid = _task_id(task)
        if tkid is not None:
            wait_for_task(tkid)
        else:
            clog.warning(
                f"[{student_instance_slug}] distribute returned no tkid; "
                "waiting briefly for FS sync."
            )
            time.sleep(5)
        # On instructor FS after distribute, same paths under /files/...
        local_dir = results_dir / student_instance_slug
        local_dir.mkdir(parents=True, exist_ok=True)
        distributed_names = [Path(p).name for p in source_files]
        for name in distributed_names:
            instructor_path = Path(staging_dir) / name
            # allow short FS settle
            for _ in range(15):
                if instructor_path.is_file():
                    break
                time.sleep(1)
            pull["instructor_paths"][name] = str(instructor_path)
            if instructor_path.is_file():
                dest = local_dir / name
                shutil.copy2(instructor_path, dest)
                pull["local_paths"][name] = str(dest)
                if name.endswith(".log"):
                    pull["log_excerpts"][name] = _read_text_if_exists(dest)
            else:
                clog.warning(
                    f"[{student_instance_slug}] expected instructor file missing: "
                    f"{instructor_path}"
                )

        if pull["local_paths"]:
            pull["status"] = "pulled"
            # convenience combined view
            summary_txt = local_dir / "combined.txt"
            chunks = []
            for name in ("output.log", "error.log"):
                text = pull["log_excerpts"].get(name)
                if text is not None:
                    chunks.append(f"===== {name} =====\n{text}")
            if chunks:
                summary_txt.write_text("\n\n".join(chunks), encoding="utf-8")
                pull["local_paths"]["combined.txt"] = str(summary_txt)
            clog.info(
                f"[{student_instance_slug}] logs saved under {local_dir}"
            )
        else:
            pull["status"] = "failed"
            pull["error"] = (
                "Distribute finished but logs not visible on instructor FS yet. "
                f"Check {staging_dir} on master after a refresh."
            )
    except Exception as exc:
        pull["status"] = "failed"
        pull["error"] = str(exc)
        clog.error(f"[{student_instance_slug}] log pull failed: {exc}")
    return pull


def test_one_student(
    *,
    org_slug: str,
    space_slug: str,
    instance_slug: str,
    app_slug: str,
    command: str,
    dry_run: bool = False,
    skip_app_preflight: bool = False,
    run_id: str | None = None,
    results_dir: Path | None = None,
    instructor_instance_slug: str = "master",
    pull_logs: bool = True,
) -> dict:
    """Start → wait RUNNING → execute → pull logs to instructor → stop."""
    record = {
        "instance_slug": instance_slug,
        "app_slug": app_slug,
        "command": command,
        "status": "pending",
        "started_at": _utc_now_iso(),
        "execute": None,
        "instructor_logs": None,
        "error": None,
        "stopped": None,
    }
    clog.info(f"[{instance_slug}] check queued for app [{app_slug}].")
    if dry_run:
        record["status"] = "dry_run"
        record["finished_at"] = _utc_now_iso()
        clog.info(
            f"[dry-run] would start/execute/stop app={app_slug} "
            f"on {org_slug}/{space_slug}/{instance_slug}: {command!r}"
        )
        if pull_logs:
            clog.info(
                f"[dry-run] would pull execute logs to instructor "
                f"[{instructor_instance_slug}] and {results_dir}"
            )
        return record

    if not skip_app_preflight:
        clog.info(f"[{instance_slug}] checking app availability.")
        apps = list_apps(
            org_slug=org_slug,
            space_slug=space_slug,
            instance_slug=instance_slug,
            snapshot_slug="development",
        )
        app_slugs = set()
        for a in apps:
            d = _model_to_dict(a) if not isinstance(a, dict) else a
            s = d.get("slug") or d.get("short_id")
            if s:
                app_slugs.add(s)
        if app_slug not in app_slugs:
            record["status"] = "failed"
            record["error"] = (
                f"App slug '{app_slug}' not found on instance '{instance_slug}'. "
                f"Available: {sorted(app_slugs)}"
            )
            record["finished_at"] = _utc_now_iso()
            clog.error(f"[{instance_slug}] app preflight failed: {record['error']}")
            return record

    started = False
    logs_pulled = False

    def _try_pull_logs(reason: str) -> None:
        """Best-effort instructor log pull while the student app is still up."""
        nonlocal logs_pulled
        if logs_pulled:
            return
        if not pull_logs or results_dir is None or not run_id:
            return
        execute_info = record.get("execute") or {}
        if not execute_info.get("output_path") and not execute_info.get("error_path"):
            return
        try:
            clog.info(
                f"[{instance_slug}] pulling logs to instructor ({reason})."
            )
            record["instructor_logs"] = pull_student_logs_to_instructor(
                org_slug=org_slug,
                space_slug=space_slug,
                student_instance_slug=instance_slug,
                app_slug=app_slug,
                execute_info=execute_info,
                run_id=run_id,
                results_dir=results_dir,
                instructor_instance_slug=instructor_instance_slug,
            )
            logs_pulled = True
            excerpts = (record["instructor_logs"] or {}).get("log_excerpts") or {}
            out_ex = excerpts.get("output.log")
            err_ex = excerpts.get("error.log")
            if out_ex:
                clog.info(
                    f"[{instance_slug}] stdout (excerpt):\n{out_ex[:2000]}"
                )
            if err_ex:
                clog.info(
                    f"[{instance_slug}] stderr (excerpt):\n{err_ex[:2000]}"
                )
        except Exception as pull_exc:
            clog.error(
                f"[{instance_slug}] log pull failed ({reason}): {pull_exc}"
            )
            record["instructor_logs"] = {
                "status": "failed",
                "error": str(pull_exc),
            }

    try:
        clog.info(f"[{instance_slug}] starting app [{app_slug}] (1/5).")
        start_app(
            org_slug=org_slug,
            space_slug=space_slug,
            instance_slug=instance_slug,
            app_slug=app_slug,
            node_pool=None,
        )
        started = True
        wait_for_app_running(
            org_slug=org_slug,
            space_slug=space_slug,
            instance_slug=instance_slug,
            app_slug=app_slug,
        )
        clog.info(f"[{instance_slug}] app is running (2/5).")
        if not run_id:
            raise ClickException(
                f"[{instance_slug}] internal error: run_id required to track command completion."
            )
        done_file = _cmd_done_path(run_id, instance_slug)
        output_log, error_log = _cmd_output_paths(run_id, instance_slug)
        wrapped_command = _wrap_command_with_done_file(
            command,
            done_file=done_file,
            output_log=output_log,
            error_log=error_log,
        )
        clog.info(f"[{instance_slug}] executing command (3/5): {command!r}")
        exec_result = execute_command_in_app(
            org_slug=org_slug,
            space_slug=space_slug,
            instance_slug=instance_slug,
            app_slug=app_slug,
            command=wrapped_command,
        )
        record["execute"] = _serialize_execute_result(exec_result)
        # Grade owns these paths (wrapper uses explicit redirects).
        record["execute"]["output_path"] = output_log
        record["execute"]["error_path"] = error_log
        record["execute"]["done_file"] = done_file
        record["execute"]["submitted_command"] = command
        # Execute returns 202 immediately; wait for the done-file before
        # treating the run as finished, pulling logs, or stopping the app.
        exit_code = _wait_for_execute_completion(
            org_slug=org_slug,
            space_slug=space_slug,
            instance_slug=instance_slug,
            done_file=done_file,
        )
        record["execute"]["exit_code"] = exit_code
        if exit_code != 0:
            record["status"] = "failed"
            record["error"] = f"Validation command exited with code {exit_code}"
            clog.error(
                f"[{instance_slug}] command failed (4/5): exit_code={exit_code}."
            )
        else:
            record["status"] = "executed"
            clog.info(f"[{instance_slug}] command completed (4/5).")

        _try_pull_logs("after command completion")

    except Exception as exc:
        record["status"] = "failed"
        record["error"] = str(exc)
        clog.error(f"Student [{instance_slug}] failed: {exc}")
        # Timeouts / mid-flight failures: salvage any logs already under
        # grade_results before the app is stopped.
        _try_pull_logs("after failure/timeout")
    finally:
        if started and not logs_pulled:
            _try_pull_logs("before stop")
        if started:
            try:
                clog.info(f"[{instance_slug}] stopping app [{app_slug}].")
                stop_app(
                    org_slug=org_slug,
                    space_slug=space_slug,
                    instance_slug=instance_slug,
                    app_slug=app_slug,
                )
                record["stopped"] = True
            except Exception as stop_exc:
                record["stopped"] = False
                record["stop_error"] = str(stop_exc)
                clog.error(
                    f"Failed to stop app [{app_slug}] on [{instance_slug}]: {stop_exc}"
                )
        record["finished_at"] = _utc_now_iso()
        clog.info(
            f"[{instance_slug}] finished: status={record['status']}, "
            f"stopped={record['stopped']}."
        )
    return record




def run_grade_check(
    *,
    org_slug: str,
    space_slug: str,
    app_slug: str,
    command: str,
    results_dir: str,
    target_folder: str | None = None,
    assignment_name: str | None = None,
    assignment_folder: str | None = None,
    skip_collect: bool = False,
    manifest_path: str | None = None,
    instance_filter: str | None = None,
    dry_run: bool = False,
    continue_on_error: bool = False,
    skip_missing_instances: bool = False,
    limit: int | None = None,
    parallel: int = 1,
    pull_logs: bool = True,
    instructor_instance_slug: str | None = None,
) -> dict:
    """Orchestrator: optional collect → resolve → lifecycle batch → instructor logs."""
    instructor_instance_slug = instructor_instance_slug or _instructor_instance_slug()
    clog.info(
        f"Starting grade run for {org_slug}/{space_slug}: app={app_slug}, "
        f"parallel={max(1, parallel)}, dry_run={dry_run}, pull_logs={pull_logs}, "
        f"instructor_instance={instructor_instance_slug}."
    )
    if not skip_collect:
        if not assignment_name or not assignment_folder or not target_folder:
            raise ClickException(
                "Collect requires --assignment-name, --assignment-folder, "
                "and --target-folder (or pass --skip-collect with --manifest)."
            )
        if not dry_run:
            collect_submissions(assignment_name, assignment_folder, target_folder)
        else:
            clog.info(
                f"[dry-run] would collect assignment_name={assignment_name!r} "
                f"assignment_folder={assignment_folder!r} target_folder={target_folder!r}"
            )
        manifest_source = target_folder
    else:
        manifest_source = manifest_path or target_folder
        if not manifest_source:
            raise ClickException(
                "--skip-collect requires --manifest or --target-folder "
                "pointing at an existing collect output."
            )

    if skip_collect or not dry_run:
        manifest = read_manifest(manifest_source)
    else:
        try:
            manifest = read_manifest(manifest_source)
        except ClickException:
            clog.warning("No existing manifest for dry-run; student list is empty.")
            manifest = {"meta": {}, "items": []}

    students = resolve_students(
        manifest,
        org_slug,
        space_slug,
        instance_filter=instance_filter,
        limit=limit,
    )
    clog.info(f"Prepared {len(students)} student(s) for grading.")
    results_path = Path(results_dir).expanduser().resolve()
    results_path.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_results_dir = results_path / run_id
    run_results_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "run_id": run_id,
        "started_at": _utc_now_iso(),
        "org_slug": org_slug,
        "space_slug": space_slug,
        "app_slug": app_slug,
        "command_template": command,
        "target_folder": target_folder,
        "assignment_name": assignment_name,
        "assignment_folder": assignment_folder,
        "skip_collect": skip_collect,
        "instance_filter": instance_filter,
        "dry_run": dry_run,
        "parallel": parallel,
        "pull_logs": pull_logs,
        "instructor_instance_slug": instructor_instance_slug,
        "results_run_dir": str(run_results_dir),
        "counts": {
            "total": len(students),
            "ok": 0,
            "failed": 0,
            "skipped": 0,
            "dry_run": 0,
        },
        "students": [],
    }

    def process(student):
        slug = student["instance_slug"]
        rec = test_one_student(
            org_slug=org_slug,
            space_slug=space_slug,
            instance_slug=slug,
            app_slug=app_slug,
            command=expand_command_template(
                command,
                instance_slug=slug,
                target=str(student.get("target") or ""),
            ),
            dry_run=dry_run,
            run_id=run_id,
            results_dir=run_results_dir,
            instructor_instance_slug=instructor_instance_slug,
            pull_logs=pull_logs,
        )
        rec.update(
            {
                "src": student.get("src"),
                "target": student.get("target"),
                "instance_name": student.get("instance_name"),
            }
        )
        return rec

    runnable = []
    for student in students:
        if student["found_in_space"]:
            runnable.append(student)
            continue
        slug = student["instance_slug"]
        msg = f"Instance '{slug}' not found in org={org_slug} space={space_slug} (or API key lacks access)."
        if not (skip_missing_instances or continue_on_error):
            raise ClickException(msg)
        clog.warning(msg + " Skipping.")
        summary["students"].append({**student, "status": "skipped", "error": msg,
                                     "finished_at": _utc_now_iso()})
        summary["counts"]["skipped"] += 1

    worker_count = max(1, parallel)
    if not continue_on_error and not dry_run and worker_count > 1:
        clog.warning(
            "--continue-on-error is not set; forcing sequential processing so "
            "the run can stop after the first student failure."
        )
        worker_count = 1
    clog.info(
        f"Processing {len(runnable)} runnable student(s) with {worker_count} worker(s); "
        f"{summary['counts']['skipped']} skipped; "
        f"continue_on_error={continue_on_error}."
    )
    records: list[dict] = []
    if dry_run or worker_count == 1:
        for idx, student in enumerate(runnable):
            rec = process(student)
            records.append(rec)
            failed = rec.get("status") not in ("executed", "dry_run", "skipped")
            if failed and not continue_on_error and not dry_run:
                remaining = runnable[idx + 1 :]
                if remaining:
                    clog.error(
                        f"Stopping after failure on [{rec.get('instance_slug')}]; "
                        f"{len(remaining)} student(s) not processed "
                        f"(pass --continue-on-error to keep going)."
                    )
                for skipped_student in remaining:
                    records.append(
                        {
                            **skipped_student,
                            "status": "skipped",
                            "error": (
                                "Skipped because a previous student failed and "
                                "--continue-on-error was not set."
                            ),
                            "finished_at": _utc_now_iso(),
                        }
                    )
                break
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(process, student) for student in runnable]
            records = [future.result() for future in futures]

    for rec in records:
        summary["students"].append(rec)
        status = rec.get("status")
        if status == "dry_run":
            summary["counts"]["dry_run"] += 1
        elif status == "executed":
            summary["counts"]["ok"] += 1
        elif status == "skipped":
            summary["counts"]["skipped"] += 1
        else:
            summary["counts"]["failed"] += 1
        clog.info(
            f"Grade progress: {len(summary['students'])}/{len(students)} completed "
            f"(ok={summary['counts']['ok']}, failed={summary['counts']['failed']}, "
            f"skipped={summary['counts']['skipped']})."
        )
        if not dry_run and worker_count == 1:
            time.sleep(1)


    summary["finished_at"] = _utc_now_iso()
    out_file = results_path / f"grade_run_{run_id}.json"
    with out_file.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, default=str)
    summary["results_file"] = str(out_file)
    clog.info(
        f"Grade run complete: ok={summary['counts']['ok']}, "
        f"failed={summary['counts']['failed']}, skipped={summary['counts']['skipped']}, "
        f"results={out_file}."
    )
    return summary


# ---------------------------------------------------------------------------
# Click commands
# ---------------------------------------------------------------------------


@click.group("grade")
def nv_grade():
    """Student assignment testing / grading (instructor)."""


@nv_grade.command("collect")
@click.option(
    "--assignment-name",
    required=True,
    help="Assignment / bundle name under handin (nvcollect).",
)
@click.option(
    "--assignment-folder",
    required=True,
    help="Leaf folder name inside each submission (nvcollect).",
)
@click.option(
    "--target-folder",
    required=True,
    type=click.Path(),
    help="Destination for collected trees + nvcollect_manifest.json.",
)
def nv_grade_collect(assignment_name, assignment_folder, target_folder):
    """Collect submissions by calling nuvolos_collect.collect in-process."""
    check_api_key_configured()
    collect_submissions(assignment_name, assignment_folder, target_folder)
    click.echo(f"Collect completed into {target_folder}")


@nv_grade.command("resolve-manifest")
@click.option(
    "--manifest",
    "-m",
    required=True,
    type=click.Path(exists=True),
    help="Path to nvcollect_manifest.json or its parent directory.",
)
@click.option("--org", "-o", required=True, help="Organization slug.")
@click.option("--space", "-s", required=True, help="Space slug.")
@click.option(
    "--instance",
    "-i",
    default=None,
    help="Optional filter: only this student instance_slug.",
)
@click.option(
    "-f",
    "--format",
    "fmt",
    type=click.Choice(["json", "table"]),
    default="table",
)
def nv_grade_resolve_manifest(manifest, org, space, instance, fmt):
    """Map manifest entries to instance slugs and check space membership."""
    _validate_grade_environment(org, space)
    manifest_data = read_manifest(manifest)
    students = resolve_students(manifest_data, org, space, instance_filter=instance)
    if fmt == "json":
        click.echo(json.dumps(students, indent=2, default=str))
        return
    rows = [
        [
            s["instance_slug"],
            s.get("instance_name") or "",
            "yes" if s["found_in_space"] else "NO",
            s.get("target") or "",
        ]
        for s in students
    ]
    click.echo(
        tabulate(
            rows,
            headers=["instance_slug", "name", "in_space", "target"],
            tablefmt="github",
        )
    )


@nv_grade.command("check")
@click.option(
    "--assignment-name",
    default=None,
    help="nvcollect: assignment / bundle name under handin.",
)
@click.option(
    "--assignment-folder",
    default=None,
    help="nvcollect: leaf folder inside each submission.",
)
@click.option(
    "--target-folder",
    default=None,
    type=click.Path(),
    help="nvcollect output dir (manifest written here). Required unless --skip-collect with --manifest.",
)
@click.option("--org", "-o", required=True, help="Organization slug.")
@click.option("--space", "-s", required=True, help="Space slug.")
@click.option(
    "--instance",
    "-i",
    default=None,
    help="Optional: only this student instance_slug (filter).",
)
@click.option(
    "--app-slug",
    "-a",
    required=True,
    help="Application slug to start on each student instance.",
)
@click.option(
    "--command",
    "-c",
    "command",
    default=None,
    required=False,
    help=(
        "Shell command to run inside each student app (cwd=/files). "
        "Example: 'python assignments/main.py'. "
        "Placeholders: {instance_slug}, {instance}, {target}."
    ),
)
@click.option(
    "--test-command",
    "legacy_test_command",
    default=None,
    hidden=True,
    help="Deprecated alias for --command.",
)
@click.option(
    "--results-dir",
    "-r",
    required=True,
    type=click.Path(),
    help=(
        "Instructor-side directory for grade_run_*.json and per-student "
        "output.log / error.log (under results-dir/<run_id>/<instance>/)."
    ),
)
@click.option(
    "--skip-collect",
    is_flag=True,
    help="Do not collect; use existing --manifest or --target-folder manifest.",
)
@click.option(
    "--manifest",
    "-m",
    default=None,
    type=click.Path(exists=True),
    help="With --skip-collect: path to manifest file or collect dir.",
)
@click.option("--dry-run", is_flag=True, help="Plan only; no start/execute/stop.")
@click.option(
    "--continue-on-error",
    is_flag=True,
    help=(
        "Continue to the next student after a lifecycle/validation failure. "
        "Without this flag the run stops after the first failed student "
        "(remaining students are marked skipped)."
    ),
)
@click.option(
    "--skip-missing-instances",
    is_flag=True,
    help="Skip manifest instances not visible via instances list.",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Process at most N students (staging POC).",
)
@click.option(
    "--parallel",
    type=click.IntRange(min=1),
    default=1,
    show_default=True,
    help="Run up to N student checks concurrently.",
)
@click.option(
    "--all",
    "grade_all",
    is_flag=True,
    help="Grade every resolved student; ignores --limit.",
)
@click.option(
    "--pull-logs/--no-pull-logs",
    default=True,
    show_default=True,
    help=(
        "After execute, copy output/error logs from each student instance "
        "onto the instructor instance and into --results-dir."
    ),
)
@click.option(
    "--instructor-instance",
    default=None,
    help="Instructor instance slug to receive logs (default: NV_CONTEXT instance or 'master').",
)
def nv_grade_check(
    assignment_name,
    assignment_folder,
    target_folder,
    org,
    space,
    instance,
    app_slug,
    command,
    legacy_test_command,
    results_dir,
    skip_collect,
    manifest,
    dry_run,
    continue_on_error,
    skip_missing_instances,
    limit,
    parallel,
    grade_all,
    pull_logs,
    instructor_instance,
):
    """Collect, run --command on each student app, pull logs to instructor."""
    _validate_grade_environment(org, space)
    if grade_all:
        limit = None
    run_command = command or legacy_test_command
    if not run_command:
        raise ClickException("--command is required (or deprecated --test-command)")

    if not skip_collect:
        missing = [
            name
            for name, val in (
                ("--assignment-name", assignment_name),
                ("--assignment-folder", assignment_folder),
                ("--target-folder", target_folder),
            )
            if not val
        ]
        if missing:
            raise ClickException(
                "Collect requires: "
                + ", ".join(missing)
                + " (or pass --skip-collect with --manifest)"
            )

    summary = run_grade_check(
        org_slug=org,
        space_slug=space,
        app_slug=app_slug,
        command=run_command,
        results_dir=results_dir,
        target_folder=target_folder,
        assignment_name=assignment_name,
        assignment_folder=assignment_folder,
        skip_collect=skip_collect,
        manifest_path=manifest,
        limit=limit,
        parallel=parallel,
        instance_filter=instance,
        dry_run=dry_run,
        continue_on_error=continue_on_error,
        skip_missing_instances=skip_missing_instances,
        pull_logs=pull_logs,
        instructor_instance_slug=instructor_instance,
    )

    click.echo(json.dumps(summary["counts"], indent=2))
    click.echo(f"results_file: {summary.get('results_file')}")
    click.echo(f"results_run_dir: {summary.get('results_run_dir')}")

    if summary["counts"]["failed"] and not dry_run:
        raise ClickException(
            f"Grade run finished with {summary['counts']['failed']} failure(s). "
            f"See {summary.get('results_file')}"
        )
