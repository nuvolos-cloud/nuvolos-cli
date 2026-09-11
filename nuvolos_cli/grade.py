"""Instructor assignment testing and grading.

The commands are intended for the instructor application in a teaching
space. They collect submissions and run the configured validation command in
each selected student application.
"""

from __future__ import annotations

import json
import os
import re
import signal
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
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
HANDIN_REVIEW_ROOT = "/files/assignments-review/handin"
HANDBACK_REVIEW_ROOT = "/files/assignments-review/handback"
# Ephemeral staging only (execute + distribute). Durable output is handin/handback.
DEFAULT_GRADE_WORK_ROOT = "/files/.nuvolos_grade"
GRADE_META_FILENAME = "grade_meta.json"
# Grading artifacts (output.log, grade_meta.json) are published under a
# dedicated child directory so they never collide with identically named
# files already present in a student's submission.
GRADE_ARTIFACTS_DIRNAME = "_grading"

# Hold-mode (concurrent evaluation window) state under the grade work root.
# Used by `grade check --hold-duration` and crash-recovery `grade stop`.
GRADE_RUN_STATE_FILENAME = "run_state.json"


def _as_files_abs_path(path: str | Path) -> str:
    """Normalize a results path to an absolute /files/... path for cross-instance use."""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = Path("/files") / p
    text = os.path.normpath(str(p))
    # Prefer the shared /files mount form (drop resolve()-only host paths).
    if not text.startswith("/files/") and "/files/" in text:
        text = "/files/" + text.split("/files/", 1)[1]
        text = os.path.normpath(text)
    if text != "/files" and not text.startswith("/files/"):
        raise ClickException(
            "results_dir must be under /files for student→instructor log distribution, got: "
            + text
        )
    return text


def _safe_student_folder_name(label: str | None, fallback: str) -> str:
    """Filesystem-safe folder name; prefer email, fall back to instance slug."""
    raw = (label or "").strip() or fallback
    # Strip path separators / NULs; keep @ so emails stay readable.
    cleaned = (
        raw.replace("\0", "")
        .replace("/", "_")
        .replace("\\", "_")
        .replace("\n", "_")
        .replace("\r", "_")
        .strip(" .")
    )
    return cleaned or fallback


def _email_from_instance_meta(meta: dict | None) -> str | None:
    """Best-effort student email.

    Teaching single-user instances set instance name (long_id) to the invitee
    email (see nv-backend create_instances_with_single_editor).
    """
    if not meta:
        return None
    for key in ("email", "user_email", "owner_email"):
        val = meta.get(key)
        if val and "@" in str(val):
            return str(val).strip()
    name = str(meta.get("name") or "").strip()
    # Invite flow stores email as the instance display name.
    if "@" in name and " " not in name and "/" not in name:
        return name
    return None


def _cmd_work_dir(results_dir: str | Path, run_id: str, student_folder: str) -> str:
    """Per-student work dir: <results-dir>/<run_id>/<student-email>/."""
    base = _as_files_abs_path(results_dir)
    return f"{base.rstrip('/')}/{run_id}/{student_folder}"


def _cmd_done_path(results_dir: str | Path, run_id: str, student_folder: str) -> str:
    """Side-channel completion file written after the student command finishes."""
    return f"{_cmd_work_dir(results_dir, run_id, student_folder)}/.cmd_done"


def _cmd_output_path(results_dir: str | Path, run_id: str, student_folder: str) -> str:
    """Single combined stdout+stderr log path owned by grade."""
    return f"{_cmd_work_dir(results_dir, run_id, student_folder)}/output.log"


def _wrap_command_with_done_file(
    command: str,
    *,
    done_file: str,
    output_log: str,
) -> str:
    """Run command with one merged log file, then write a completion/exit marker.

    Nuvolos default capture only keeps the last segment of a command sequence
    and skips defaults entirely when the submitted string contains `>`. Grade
    therefore owns the log path: redirect the validation body with ``> out 2>&1``
    so stdout and stderr land in a single ``output.log``, then write
    ``.cmd_done`` / ``.cmd_exit.<code>`` with POSIX shell only (no Python
    runtime required in the student app).
    """
    work = str(Path(done_file).parent)
    work_q = shlex.quote(work)
    out_q = shlex.quote(output_log)
    done_q = shlex.quote(done_file)
    # Marker writes must stay pure shell so RStudio / python3-only / no-Python
    # images can still signal completion. `.cmd_exit.$ec` is listed via the
    # files API (name encodes the exit code); content may be empty.
    return (
        f"work={work_q}\n"
        f"done_file={done_q}\n"
        f"mkdir -p \"$work\"\n"
        f"{{\n{command}\n}} > {out_q} 2>&1\n"
        f"ec=$?\n"
        f"printf '%s' \"$ec\" > \"$done_file\"\n"
        f": > \"$work/.cmd_exit.$ec\"\n"
        f"exit \"$ec\""
    )


def _wrap_command_detached(
    command: str,
    *,
    output_log: str,
    pid_file: str,
) -> str:
    """Background a long-lived process; return immediately (no done-file wait).

    Used by hold-mode evaluation windows where the student app must stay up for
    an external platform. Prefer images whose primary process is already the
    server and omit --command when possible.
    """
    work = str(Path(output_log).parent)
    work_q = shlex.quote(work)
    out_q = shlex.quote(output_log)
    pid_q = shlex.quote(pid_file)
    # nohup + background; write pid and exit 0 so the k8s exec returns at once.
    return (
        f"work={work_q}\n"
        f"mkdir -p \"$work\"\n"
        f"nohup bash -lc {shlex.quote(command)} >>{out_q} 2>&1 & echo $! > {pid_q}\n"
        f"exit 0"
    )


def _parse_duration_seconds(value: str | int | float | None) -> int | None:
    """Parse duration like 1800, 30m, 1h, 2h30m into seconds. None/empty → None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        secs = int(value)
        if secs < 0:
            raise ClickException(f"duration must be >= 0, got {value!r}")
        return secs
    text = str(value).strip().lower()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    total = 0
    matched = False
    for amount, unit in re.findall(r"(\d+)\s*([smhd])", text):
        matched = True
        n = int(amount)
        if unit == "s":
            total += n
        elif unit == "m":
            total += n * 60
        elif unit == "h":
            total += n * 3600
        elif unit == "d":
            total += n * 86400
    if not matched or re.sub(r"[\d\ssmhd]", "", text):
        raise ClickException(
            f"Invalid duration {value!r}; use seconds or forms like 30m, 1h, 2h30m"
        )
    return total


def _run_state_dir(work_root: str | Path, run_id: str) -> Path:
    return Path(_as_files_abs_path(work_root)) / run_id


def _run_state_path(work_root: str | Path, run_id: str) -> Path:
    return _run_state_dir(work_root, run_id) / GRADE_RUN_STATE_FILENAME


def save_run_state(state: dict, *, work_root: str | Path | None = None) -> Path:
    """Persist hold-mode run state for crash-safe bulk stop."""
    run_id = state.get("run_id")
    if not run_id:
        raise ClickException("run state missing run_id")
    root = work_root or state.get("staging_root") or DEFAULT_GRADE_WORK_ROOT
    path = _run_state_path(root, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    payload = dict(state)
    payload["updated_at"] = _utc_now_iso()
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)
        fh.write("\n")
    os.replace(tmp, path)
    return path


def load_run_state(
    run_id: str,
    *,
    work_root: str | Path | None = None,
    path: str | Path | None = None,
) -> dict:
    """Load run_state.json by run_id or explicit path."""
    if path:
        state_path = Path(path).expanduser()
    else:
        root = work_root or DEFAULT_GRADE_WORK_ROOT
        state_path = _run_state_path(root, run_id)
    if not state_path.is_file():
        raise ClickException(f"Run state not found: {state_path}")
    with open(state_path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ClickException(f"Invalid run state (not an object): {state_path}")
    return data


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
    *,
    org_slug: str | None = None,
    space_slug: str | None = None,
) -> int:
    """Run nvcollect collect() in-process, then rename dirs to student email."""
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
    if org_slug and space_slug:
        relabel_collect_targets_by_email(target_folder, org_slug, space_slug)
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


def instance_slug_from_handin_src(src: str | None) -> str | None:
    """Extract instance slug from nvcollect handin src path."""
    if not src:
        return None
    parts = Path(str(src)).parts
    try:
        handin_idx = parts.index("handin")
        slug = parts[handin_idx + 1]
        return slug or None
    except (ValueError, IndexError):
        return None


def instance_slug_from_item(item: dict) -> str:
    """Derive instance_slug from a nvcollect manifest item.

    Prefer the handin ``src`` path (stable after email folder rename). Fall back
    to the target basename for older manifests.
    """
    if not isinstance(item, dict):
        raise ClickException(f"Manifest item must be an object, got {type(item)!r}")

    slug = instance_slug_from_handin_src(item.get("src"))
    if slug:
        return slug

    target = item.get("target") or ""
    if target:
        name = Path(str(target).rstrip("/")).name
        if name:
            return name

    raise ClickException(f"Cannot derive instance_slug from manifest item: {item!r}")


def _manifest_file_path(target_folder: str | Path) -> Path:
    path = Path(target_folder).expanduser()
    if path.is_file():
        return path
    return path / MANIFEST_FILENAME


def relabel_collect_targets_by_email(
    target_folder: str | Path,
    org_slug: str,
    space_slug: str,
) -> dict:
    """Rename collected submission dirs from instance_slug → student email.

    nvcollect writes ``<target>/<instance_slug>/``. After collect, rename each
    tree to ``<target>/<student-email>/`` and rewrite ``nvcollect_manifest.json``
    targets accordingly. Idempotent when folders are already email-named.
    """
    root = Path(target_folder).expanduser()
    if not root.is_dir():
        raise ClickException(f"Collect target folder not found: {root}")

    manifest_path = _manifest_file_path(root)
    data = read_manifest(root)
    items = list(data.get("items") or [])
    if not items:
        clog.info("No collect items to relabel by email.")
        return data

    instances = list_instances(org_slug=org_slug, space_slug=space_slug)
    by_slug: dict[str, dict] = {}
    for inst in instances:
        d = _model_to_dict(inst) if not isinstance(inst, dict) else inst
        slug = d.get("slug") or d.get("short_id")
        if slug:
            by_slug[str(slug)] = d

    used_folders: set[str] = set()
    new_items: list[dict] = []
    renamed = 0

    for item in items:
        if not isinstance(item, dict):
            continue
        slug = instance_slug_from_item(item)
        meta = by_slug.get(slug)
        email = _email_from_instance_meta(meta)
        folder = _safe_student_folder_name(
            email or (meta or {}).get("name"),
            slug,
        )
        # Avoid two students collapsing into one directory name.
        base_folder = folder
        n = 2
        while folder in used_folders:
            folder = f"{base_folder}_{n}"
            n += 1
        used_folders.add(folder)

        old_target = str(item.get("target") or "").rstrip("/")
        old_dir = Path(old_target) if old_target else root / slug
        if not old_dir.is_absolute():
            old_dir = root / old_dir.name
        # If target was relative-ish, prefer sibling under root by basename.
        if old_dir.parent != root and (root / old_dir.name).exists():
            candidate = root / old_dir.name
            if candidate.is_dir():
                old_dir = candidate
        if not old_dir.exists():
            # Try slug dir under root (fresh nvcollect layout).
            alt = root / slug
            if alt.is_dir():
                old_dir = alt

        new_dir = root / folder
        new_target = str(new_dir) + "/"

        if old_dir.resolve() != new_dir.resolve():
            if not old_dir.exists():
                clog.warning(
                    f"Collect folder missing for {slug} (expected {old_dir}); "
                    f"manifest target will still use {folder}."
                )
            elif new_dir.exists():
                clog.warning(
                    f"Email folder already exists ({new_dir}); leaving {old_dir} in place."
                )
                new_target = str(old_dir) + "/"
                folder = old_dir.name
            else:
                clog.info(f"Renaming collect {old_dir.name} → {folder}")
                old_dir.rename(new_dir)
                renamed += 1

        new_items.append(
            {
                **item,
                "target": new_target,
                "instance_slug": slug,
                "email": email,
                "folder_name": folder,
            }
        )

    data["items"] = new_items
    data.setdefault("meta", {})
    data["meta"]["relabeled_by_email"] = True
    data["meta"]["relabel_time"] = _utc_now_iso()

    with manifest_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    clog.info(
        f"Collect tree under {root}: {renamed} folder(s) renamed to student email; "
        f"manifest updated ({manifest_path.name})."
    )
    return data




def _handback_path_from_handin_src(src: str | None) -> str | None:
    """Map a handin review path to the parallel handback path."""
    if not src:
        return None
    text = str(src)
    if "/assignments-review/handin" in text:
        return text.replace(
            "/assignments-review/handin",
            "/assignments-review/handback",
            1,
        )
    if text.startswith(HANDIN_REVIEW_ROOT):
        return HANDBACK_REVIEW_ROOT + text[len(HANDIN_REVIEW_ROOT) :]
    return None


def _chmod_tree_readonly(path: Path) -> None:
    """Best-effort make files under path read-only (students must not edit feedback)."""
    if not path.exists():
        return
    try:
        if path.is_file():
            os.chmod(path, 0o444)
            return
        for root, dirs, files in os.walk(path):
            try:
                os.chmod(root, 0o555)
            except OSError:
                pass
            for name in files:
                fp = Path(root) / name
                try:
                    os.chmod(fp, 0o444)
                except OSError:
                    pass
    except OSError as exc:
        clog.debug(f"chmod readonly failed for {path}: {exc}")


def _safe_copy_into(src_file: Path, dest_dir: Path, name: str | None = None) -> Path | None:
    """Copy a file into dest_dir; create parents. Returns dest path or None."""
    if not src_file.is_file():
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / (name or src_file.name)
    try:
        if dest.exists() and (dest.is_file() or dest.is_symlink()):
            try:
                dest.unlink()
            except OSError:
                pass
        shutil.copy2(src_file, dest)
        return dest
    except OSError as exc:
        clog.warning(f"Failed to copy {src_file} → {dest}: {exc}")
        return None


def publish_student_results_to_handin_structure(
    *,
    student_record: dict,
    run_id: str,
) -> dict:
    """Copy grade artifacts into handin + handback trees on the instructor FS.

    Layout (existing platform structure)::

        /files/assignments-review/handin/<instance>/<assignment>/<ts>_…/…
        /files/assignments-review/handback/<instance>/<assignment>/<ts>_…/…

    Handback is what students see (read-only). We also place files under the
    original handin src folder so instructors viewing handins see the same
    artifacts next to the submission.
    """
    pub = {
        "handin_dir": None,
        "handback_dir": None,
        "files": [],
        "error": None,
    }
    logs = student_record.get("instructor_logs") or {}
    local_paths = logs.get("local_paths") or {}
    output_log = local_paths.get("output.log")
    src = student_record.get("src")
    target = student_record.get("target")

    # Prefer the handin submission folder from the collect manifest src.
    handin_dir = Path(str(src)).expanduser() if src else None
    handback_dir = None
    hb = _handback_path_from_handin_src(src)
    if hb:
        handback_dir = Path(hb)

    # Fallback: collect target folder on instructor.
    collect_dir = Path(str(target)).expanduser() if target else None

    artifact_files: list[Path] = []
    if output_log:
        p = Path(output_log)
        if p.is_file():
            artifact_files.append(p)

    # Write a small grade_meta.json next to the log when we have execute info.
    meta = {
        "run_id": run_id,
        "instance_slug": student_record.get("instance_slug"),
        "email": student_record.get("email") or student_record.get("folder_name"),
        "status": student_record.get("status"),
        "error": student_record.get("error"),
        "exit_code": (student_record.get("execute") or {}).get("exit_code"),
        "finished_at": student_record.get("finished_at") or _utc_now_iso(),
        "command": student_record.get("command"),
    }
    meta_tmp = None
    try:
        work = logs.get("work_dir")
        meta_dir = Path(work) if work else (
            collect_dir if collect_dir else Path("/tmp")
        )
        meta_dir.mkdir(parents=True, exist_ok=True)
        meta_tmp = meta_dir / GRADE_META_FILENAME
        meta_tmp.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
        artifact_files.append(meta_tmp)
    except OSError as exc:
        clog.debug(f"Could not write grade_meta.json: {exc}")

    destinations: list[Path] = []
    if handin_dir is not None:
        destinations.append(handin_dir)
        pub["handin_dir"] = str(handin_dir)
    if handback_dir is not None:
        destinations.append(handback_dir)
        pub["handback_dir"] = str(handback_dir)
    # Always keep a copy in the collect/results student folder when present.
    if collect_dir is not None and collect_dir not in destinations:
        destinations.append(collect_dir)

    if not destinations:
        pub["error"] = "No handin/handback/collect destination available"
        return pub

    if not artifact_files:
        pub["error"] = "No grade artifact files to publish"
        return pub

    published: list[str] = []
    for dest_dir in destinations:
        artifacts_dir = dest_dir / GRADE_ARTIFACTS_DIRNAME
        for art in artifact_files:
            copied = _safe_copy_into(art, artifacts_dir)
            if copied is not None:
                published.append(str(copied))
                _chmod_tree_readonly(copied)

    pub["files"] = published
    if not published:
        pub["error"] = "Publish copied no files"
    else:
        clog.info(
            f"[{student_record.get('instance_slug')}] published grade artifacts to "
            f"handin/handback structure ({len(published)} file(s))."
        )
    return pub


def handback_collected_results(collect_dir: str | Path) -> dict:
    """Push collect+grade folders into assignments-review/handback via nvcollect.

    Students see handback content in the assignment UI (read-only). Instructor
    already has the parallel tree under assignments-review/handback after this.
    """
    result = {"status": "pending", "error": None}
    root = Path(collect_dir).expanduser()
    if not root.is_dir():
        result["status"] = "skipped"
        result["error"] = f"collect dir missing: {root}"
        return result
    manifest = root / MANIFEST_FILENAME
    if not manifest.is_file():
        result["status"] = "skipped"
        result["error"] = f"no {MANIFEST_FILENAME} in {root}"
        return result
    try:
        _require_nuvolos_collect()
        from nuvolos_collect.handback import handback as nv_handback

        clog.info(f"Handing back graded results from {root} → assignments-review/handback.")
        code = nv_handback(str(root))
        if code not in (0, None):
            result["status"] = "failed"
            result["error"] = f"handback returned {code}"
            return result
        # Enforce read-only on handback targets listed in manifest.
        data = read_manifest(root)
        for item in data.get("items") or []:
            if not isinstance(item, dict):
                continue
            hb = item.get("handback_target") or _handback_path_from_handin_src(
                item.get("src")
            )
            if hb:
                _chmod_tree_readonly(Path(hb))
        result["status"] = "ok"
        clog.info("Handback completed; student-visible feedback is read-only under handback.")
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = str(exc)
        clog.error(f"Handback failed: {exc}")
    return result


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
        instance_name = (meta or {}).get("name")
        email = _email_from_instance_meta(meta)
        folder_name = item.get("folder_name") or _safe_student_folder_name(
            email or instance_name, slug
        )
        students.append({
            "index": idx,
            "instance_slug": slug,
            "src": item.get("src"),
            "target": item.get("target"),
            "instance_name": instance_name,
            "email": email,
            "folder_name": folder_name,
            "found_in_space": meta is not None,
        })

    if instance_filter and not students:
        raise ClickException(f"No manifest item matched --instance {instance_filter!r}")
    if limit is not None:
        students = students[: max(0, limit)]
    clog.info(f"Resolved {len(students)} student submission(s).")
    return students


def resolve_students_from_instances(
    org_slug: str,
    space_slug: str,
    *,
    instance_filter: str | None = None,
    limit: int | None = None,
    include_master: bool = False,
) -> list[dict]:
    """Build student list from space instances (no collect/manifest required).

    Excludes the teaching ``master`` instance by default — hold-mode evaluation
    targets student editor instances only.
    """
    clog.info(
        f"Resolving students from instances for {org_slug}/{space_slug}"
        + (f" (filter={instance_filter})" if instance_filter else "") + "."
    )
    instances = list_instances(org_slug=org_slug, space_slug=space_slug)
    students: list[dict] = []
    for idx, inst in enumerate(instances):
        d = _model_to_dict(inst) if not isinstance(inst, dict) else inst
        slug = str(d.get("slug") or d.get("short_id") or "")
        if not slug:
            continue
        if not include_master and slug == "master":
            continue
        if instance_filter and slug != instance_filter:
            continue
        instance_name = d.get("name")
        email = _email_from_instance_meta(d)
        folder_name = _safe_student_folder_name(email or instance_name, slug)
        students.append(
            {
                "index": idx,
                "instance_slug": slug,
                "src": None,
                "target": None,
                "instance_name": instance_name,
                "email": email,
                "folder_name": folder_name,
                "found_in_space": True,
            }
        )
    if instance_filter and not students:
        raise ClickException(
            f"No visible instance matched --instance {instance_filter!r}"
        )
    if limit is not None:
        students = students[: max(0, limit)]
    clog.info(f"Resolved {len(students)} instance(s) for hold-mode.")
    return students


def _count_hold_statuses(students: list[dict]) -> dict:
    counts = {
        "total": len(students),
        "running": 0,
        "start_failed": 0,
        "stopped": 0,
        "stop_failed": 0,
        "pending": 0,
        "dry_run": 0,
        "skipped": 0,
        "ok": 0,
        "failed": 0,
    }
    for rec in students:
        status = rec.get("status") or "pending"
        if status in counts:
            counts[status] += 1
        if status == "running":
            counts["ok"] += 1
        elif status in ("start_failed", "stop_failed", "failed"):
            counts["failed"] += 1
    return counts


def start_one_student_hold(
    *,
    org_slug: str,
    space_slug: str,
    instance_slug: str,
    app_slug: str,
    command: str | None = None,
    dry_run: bool = False,
    skip_app_preflight: bool = False,
    run_id: str | None = None,
    results_root: str | Path | None = None,
    student_folder: str | None = None,
) -> dict:
    """Start app and optionally detach a long-running command — do not stop.

    Caller owns bulk stop after the evaluation window (or ``grade stop``).
    """
    folder = student_folder or instance_slug
    record = {
        "instance_slug": instance_slug,
        "student_folder": folder,
        "email": folder if "@" in folder else None,
        "app_slug": app_slug,
        "command": command,
        "status": "pending",
        "started_at": _utc_now_iso(),
        "execute": None,
        "error": None,
        "stopped": None,
        "mode": "hold",
    }
    clog.info(
        f"[{instance_slug}] hold start queued for app [{app_slug}] "
        f"(folder={folder})."
    )
    if dry_run:
        record["status"] = "dry_run"
        record["finished_at"] = _utc_now_iso()
        clog.info(
            f"[dry-run] would start/hold app={app_slug} "
            f"on {org_slug}/{space_slug}/{instance_slug}"
            + (f" with detached {command!r}" if command else "")
        )
        return record

    if not skip_app_preflight:
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
            record["status"] = "start_failed"
            record["error"] = (
                f"App slug '{app_slug}' not found on instance '{instance_slug}'. "
                f"Available: {sorted(app_slugs)}"
            )
            record["finished_at"] = _utc_now_iso()
            clog.error(f"[{instance_slug}] app preflight failed: {record['error']}")
            return record

    try:
        click.echo(
            f"\n>>> [{instance_slug}] ({folder}) starting app [{app_slug}] for hold…"
        )
        start_app(
            org_slug=org_slug,
            space_slug=space_slug,
            instance_slug=instance_slug,
            app_slug=app_slug,
            node_pool=None,
        )
        click.echo(f">>> [{instance_slug}] waiting until app is RUNNING…")
        wait_for_app_running(
            org_slug=org_slug,
            space_slug=space_slug,
            instance_slug=instance_slug,
            app_slug=app_slug,
        )
        clog.info(f"[{instance_slug}] app is RUNNING (hold).")
        click.echo(f">>> [{instance_slug}] app is RUNNING.")

        if command:
            if not run_id or results_root is None:
                raise ClickException(
                    f"[{instance_slug}] internal error: run_id and results_root "
                    f"required for detached command."
                )
            output_log = _cmd_output_path(results_root, run_id, folder)
            pid_file = f"{_cmd_work_dir(results_root, run_id, folder)}/server.pid"
            wrapped = _wrap_command_detached(
                command, output_log=output_log, pid_file=pid_file
            )
            clog.info(
                f"[{instance_slug}] launching detached command: {command!r}"
            )
            click.echo(
                f">>> [{instance_slug}] detached exec (no wait): {command!r}"
            )
            exec_result = execute_command_in_app(
                org_slug=org_slug,
                space_slug=space_slug,
                instance_slug=instance_slug,
                app_slug=app_slug,
                command=wrapped,
            )
            record["execute"] = _serialize_execute_result(exec_result)
            record["execute"]["output_path"] = output_log
            record["execute"]["pid_file"] = pid_file
            record["execute"]["detached"] = True
            record["execute"]["submitted_command"] = command

        record["status"] = "running"
        record["running_at"] = _utc_now_iso()
    except Exception as exc:
        record["status"] = "start_failed"
        record["error"] = str(exc)
        record["finished_at"] = _utc_now_iso()
        clog.error(f"[{instance_slug}] hold start failed: {exc}")
    return record


def bulk_stop_students(
    *,
    org_slug: str,
    space_slug: str,
    app_slug: str,
    students: list[dict],
    dry_run: bool = False,
    parallel: int = 1,
    stagger_secs: float = 0.0,
    only_statuses: tuple[str, ...] = ("running", "stop_failed"),
) -> list[dict]:
    """Best-effort stop for students in the given statuses; mutates records."""
    stop_list: list[dict] = []
    seen = set()
    for rec in students:
        key = id(rec)
        if key in seen:
            continue
        status = rec.get("status")
        err = str(rec.get("error") or "")
        should = status in only_statuses
        # Partial start failure after start_app: still attempt stop.
        if status == "start_failed" and "not found on instance" not in err:
            should = True
        if rec.get("stopped") is False:
            should = True
        if should:
            seen.add(key)
            stop_list.append(rec)


    def _stop_one(rec: dict) -> dict:
        slug = rec.get("instance_slug")
        if dry_run:
            rec["status"] = "dry_run"
            rec["stopped"] = None
            clog.info(f"[dry-run] would stop app={app_slug} on {slug}")
            return rec
        try:
            click.echo(f">>> [{slug}] stopping app [{app_slug}]…")
            stop_app(
                org_slug=org_slug,
                space_slug=space_slug,
                instance_slug=slug,
                app_slug=app_slug,
            )
            rec["stopped"] = True
            rec["status"] = "stopped"
            rec["stopped_at"] = _utc_now_iso()
            rec.pop("stop_error", None)
            clog.info(f"[{slug}] stopped.")
        except Exception as stop_exc:
            rec["stopped"] = False
            rec["status"] = "stop_failed"
            rec["stop_error"] = str(stop_exc)
            clog.error(f"[{slug}] stop failed: {stop_exc}")
        return rec

    if not stop_list:
        clog.info("No running students to stop.")
        return students

    worker_count = max(1, int(parallel or 1))
    clog.info(
        f"Bulk-stopping {len(stop_list)} app(s) with parallel={worker_count}, "
        f"stagger_secs={stagger_secs}."
    )
    if worker_count == 1:
        for rec in stop_list:
            _stop_one(rec)
            if stagger_secs and stagger_secs > 0:
                time.sleep(stagger_secs)
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {}
            pending = list(stop_list)
            while pending or futures:
                while pending and len(futures) < worker_count:
                    rec = pending.pop(0)
                    futures[executor.submit(_stop_one, rec)] = rec
                    if stagger_secs and stagger_secs > 0:
                        time.sleep(stagger_secs)
                if not futures:
                    break
                done, _ = wait(futures.keys(), return_when=FIRST_COMPLETED)
                for fut in done:
                    futures.pop(fut, None)
                    fut.result()
    return students


def hold_evaluation_window(
    *,
    duration_seconds: int,
    state: dict,
    work_root: str | Path,
    stop_event: threading.Event | None = None,
    heartbeat_secs: int = 30,
) -> str:
    """Block until duration elapses or stop_event is set. Returns reason."""
    stop_event = stop_event or threading.Event()
    if duration_seconds <= 0:
        return "no_hold"
    ends_at = time.monotonic() + duration_seconds
    state["hold_started_at"] = _utc_now_iso()
    state["hold_ends_at_unix_hint"] = time.time() + duration_seconds
    state_path = save_run_state(state, work_root=work_root)
    click.echo(
        f"\n>>> Holding evaluation window for {duration_seconds}s "
        f"(run_id={state.get('run_id')}). "
        f"Ctrl-C triggers bulk stop. State: {state_path}"
    )
    clog.info(
        f"Hold window started: duration={duration_seconds}s run_id={state.get('run_id')}"
    )
    reason = "duration_elapsed"
    while True:
        if stop_event.is_set():
            reason = "signal"
            break
        remaining = ends_at - time.monotonic()
        if remaining <= 0:
            break
        sleep_for = min(float(heartbeat_secs), remaining)
        # Wait that is interruptible via stop_event.
        if stop_event.wait(timeout=sleep_for):
            reason = "signal"
            break
        state["hold_heartbeat_at"] = _utc_now_iso()
        state["hold_remaining_secs"] = max(0, int(ends_at - time.monotonic()))
        try:
            save_run_state(state, work_root=work_root)
        except Exception as exc:
            clog.warning(f"Failed to write hold heartbeat state: {exc}")
    state["hold_finished_at"] = _utc_now_iso()
    state["hold_end_reason"] = reason
    save_run_state(state, work_root=work_root)
    clog.info(f"Hold window ended: reason={reason}")
    click.echo(f">>> Hold ended ({reason}).")
    return reason


def _run_bounded_pool(
    items: list,
    *,
    worker_count: int,
    stagger_secs: float,
    process_fn,
) -> list:
    """Process items with at most worker_count in-flight starts + optional stagger."""
    worker_count = max(1, int(worker_count or 1))
    results: list = []
    if worker_count == 1:
        for item in items:
            results.append(process_fn(item))
            if stagger_secs and stagger_secs > 0:
                time.sleep(stagger_secs)
        return results

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {}
        pending = list(items)
        while pending or futures:
            while pending and len(futures) < worker_count:
                item = pending.pop(0)
                futures[executor.submit(process_fn, item)] = item
                if stagger_secs and stagger_secs > 0:
                    time.sleep(stagger_secs)
            if not futures:
                break
            done, _ = wait(futures.keys(), return_when=FIRST_COMPLETED)
            for fut in done:
                futures.pop(fut, None)
                results.append(fut.result())
    return results





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



def _read_text_if_exists(path: Path, max_bytes: int = 5_000_000) -> tuple[str, bool] | None:
    """Read a text file's contents; returns ``(text, truncated)`` or None if missing.

    Reads at most ``max_bytes + 1`` bytes so large logs are not fully loaded.
    """
    try:
        if not path.is_file():
            return None
        with path.open("rb") as fh:
            data = fh.read(max_bytes + 1)
        truncated = len(data) > max_bytes
        if truncated:
            data = data[:max_bytes]
        return data.decode("utf-8", errors="replace"), truncated
    except OSError:
        return None


def pull_student_logs_to_instructor(
    *,
    org_slug: str,
    space_slug: str,
    student_instance_slug: str,
    student_folder: str,
    app_slug: str,
    execute_info: dict,
    run_id: str,
    results_dir: Path,
    instructor_instance_slug: str = "master",
) -> dict:
    """Distribute execute logs from student instance into results-dir on instructor.

    Logs already live under ``<results-dir>/<run_id>/<student-email>/`` on the
    student FS. Distribute that folder's files to the instructor instance, then
    read them from the same path locally.
    """
    pull = {
        "status": "pending",
        "student_folder": student_folder,
        "work_dir": None,
        "instructor_paths": {},
        "local_paths": {},
        "log_excerpts": {},
        "log_truncated": {},
        "error": None,
    }
    out_p = execute_info.get("output_path")
    err_p = execute_info.get("error_path")  # legacy dual-log runs only
    meta_p = execute_info.get("metadata_path")
    if not out_p and not err_p:
        pull["status"] = "skipped"
        pull["error"] = "execute result had no output path"
        return pull

    # Log may legitimately be empty; existence is enough once the command
    # done-file has already been observed by the caller.
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

    # Final layout: <results-dir>/<run_id>/<student-email>/output.log
    work_dir = _cmd_work_dir(results_dir, run_id, student_folder)
    pull["work_dir"] = work_dir
    staged_names: list[str] = []
    # Validation already wrote the merged log under work_dir — distribute it
    # directly. Only copy when execute_info points elsewhere (legacy error.log
    # or platform metadata.json under nuvolos_api_out/).
    copies: list[tuple[str, str, str]] = []  # (mode, src, dest_name)
    if out_p:
        if out_p.rstrip("/") == f"{work_dir}/output.log":
            staged_names.append("output.log")
        else:
            copies.append(("cp", out_p, "output.log"))
    # Legacy separate stderr → append into the single output.log.
    if err_p and err_p.rstrip("/") != f"{work_dir}/output.log":
        copies.append(("append", err_p, "output.log"))
        if "output.log" not in staged_names:
            staged_names.append("output.log")
    if meta_p:
        if meta_p.rstrip("/") == f"{work_dir}/metadata.json":
            staged_names.append("metadata.json")
        else:
            copies.append(("cp", meta_p, "metadata.json"))

    try:
        if copies:
            parts = [f"mkdir -p {shlex.quote(work_dir)}"]
            for mode, src, dest_name in copies:
                dest = f"{work_dir}/{dest_name}"
                if mode == "append":
                    parts.append(
                        f"cat {shlex.quote(src)} >> {shlex.quote(dest)} 2>/dev/null || true"
                    )
                else:
                    parts.append(f"cp -f {shlex.quote(src)} {shlex.quote(dest)}")
                if dest_name not in staged_names:
                    staged_names.append(dest_name)
            parts.append(f"ls -la {shlex.quote(work_dir)}")
            stage_cmd = " && ".join(parts)
            stage_done = f"{work_dir}/.stage_done"
            stage_out = f"{work_dir}/.stage_out.log"
            clog.info(
                f"[{student_instance_slug}] staging logs under {work_dir} for instructor pull."
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
                f"[{student_instance_slug}] validation logs already under {work_dir}; "
                f"skipping stage copy."
            )


        # Only distribute files that were requested and actually landed.
        source_files = []
        for name in staged_names:
            abs_staged = f"{work_dir}/{name}"
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
                f"No log files found under {work_dir} after staging."
            )
            return pull

        clog.info(
            f"[{student_instance_slug}] distributing logs to instructor "
            f"instance [{instructor_instance_slug}] → {work_dir}."
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

        # After distribute, same absolute paths appear on instructor under /files/...
        local_dir = Path(work_dir)
        local_dir.mkdir(parents=True, exist_ok=True)
        distributed_names = [Path(p).name for p in source_files]
        for name in distributed_names:
            instructor_path = local_dir / name
            for _ in range(15):
                if instructor_path.is_file():
                    break
                time.sleep(1)
            pull["instructor_paths"][name] = str(instructor_path)
            if instructor_path.is_file():
                # Already at final results-dir location; no secondary copy.
                pull["local_paths"][name] = str(instructor_path)
                if name.endswith(".log"):
                    read_result = _read_text_if_exists(instructor_path)
                    if read_result is not None:
                        text, truncated = read_result
                        pull["log_excerpts"][name] = text
                        pull["log_truncated"][name] = truncated
            else:
                clog.warning(
                    f"[{student_instance_slug}] expected instructor file missing: "
                    f"{instructor_path}"
                )

        if pull["local_paths"]:
            pull["status"] = "pulled"
            clog.info(
                f"[{student_instance_slug}] logs saved under {local_dir} "
                f"(folder={student_folder}, file=output.log)"
            )
        else:
            pull["status"] = "failed"
            pull["error"] = (
                "Distribute finished but logs not visible on instructor FS yet. "
                f"Check {work_dir} on master after a refresh."
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
    results_root: str | Path | None = None,
    student_folder: str | None = None,
    instructor_instance_slug: str = "master",
    pull_logs: bool = True,
) -> dict:
    """Start → wait RUNNING → execute → pull logs to instructor → stop."""
    folder = student_folder or instance_slug
    record = {
        "instance_slug": instance_slug,
        "student_folder": folder,
        "email": folder if "@" in folder else None,
        "app_slug": app_slug,
        "command": command,
        "status": "pending",
        "started_at": _utc_now_iso(),
        "execute": None,
        "instructor_logs": None,
        "error": None,
        "stopped": None,
    }
    clog.info(
        f"[{instance_slug}] check queued for app [{app_slug}] "
        f"(folder={folder})."
    )
    if dry_run:
        record["status"] = "dry_run"
        record["finished_at"] = _utc_now_iso()
        clog.info(
            f"[dry-run] would start/execute/stop app={app_slug} "
            f"on {org_slug}/{space_slug}/{instance_slug}: {command!r}"
        )
        if pull_logs and results_root and run_id:
            work = _cmd_work_dir(results_root, run_id, folder)
            clog.info(
                f"[dry-run] would pull execute logs to instructor "
                f"[{instructor_instance_slug}] under {work}"
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
        if not pull_logs or results_root is None or not run_id:
            return
        execute_info = record.get("execute") or {}
        if not execute_info.get("output_path") and not execute_info.get("error_path"):
            return
        try:
            clog.info(
                f"[{instance_slug}] pulling logs to instructor ({reason})."
            )
            click.echo(f">>> [{instance_slug}] pulling logs ({reason})…")
            record["instructor_logs"] = pull_student_logs_to_instructor(
                org_slug=org_slug,
                space_slug=space_slug,
                student_instance_slug=instance_slug,
                student_folder=folder,
                app_slug=app_slug,
                execute_info=execute_info,
                run_id=run_id,
                results_dir=Path(results_root),
                instructor_instance_slug=instructor_instance_slug,
            )
            pull = record["instructor_logs"] or {}
            logs_pulled = pull.get("status") == "pulled"
            clog.info(
                f"[{instance_slug}] log pull status={pull.get('status')!r} "
                f"work_dir={pull.get('work_dir')!r} "
                f"local_paths={list((pull.get('local_paths') or {}).keys())}"
            )
            if pull.get("error"):
                clog.warning(f"[{instance_slug}] log pull note: {pull.get('error')}")
            excerpts = pull.get("log_excerpts") or {}
            out_ex = excerpts.get("output.log")
            out_truncated = (pull.get("log_truncated") or {}).get("output.log")
            if out_ex is not None:
                label = "(truncated)" if out_truncated else "(full)"
                ban = f"===== [{instance_slug}] output.log {label} ====="
                click.echo(ban)
                click.echo(out_ex if out_ex.endswith("\n") else out_ex + "\n")
                click.echo("=" * len(ban))
                clog.info(
                    f"[{instance_slug}] output.log length={len(out_ex)} chars "
                    + ("(truncated above)." if out_truncated else "(printed in full above).")
                )
            else:
                click.echo(
                    f">>> [{instance_slug}] no output.log content available after pull "
                    f"(status={pull.get('status')!r})."
                )
        except Exception as pull_exc:
            clog.error(
                f"[{instance_slug}] log pull failed ({reason}): {pull_exc}"
            )
            click.echo(f"!!! [{instance_slug}] log pull failed: {pull_exc}")
            record["instructor_logs"] = {
                "status": "failed",
                "error": str(pull_exc),
            }


    try:
        click.echo(
            f"\n>>> [{instance_slug}] ({folder}) starting app [{app_slug}] (1/5)…"
        )
        clog.info(f"[{instance_slug}] starting app [{app_slug}] (1/5).")
        start_app(
            org_slug=org_slug,
            space_slug=space_slug,
            instance_slug=instance_slug,
            app_slug=app_slug,
            node_pool=None,
        )
        started = True
        click.echo(f">>> [{instance_slug}] waiting until app is RUNNING…")
        wait_for_app_running(
            org_slug=org_slug,
            space_slug=space_slug,
            instance_slug=instance_slug,
            app_slug=app_slug,
        )
        clog.info(f"[{instance_slug}] app is running (2/5).")
        click.echo(f">>> [{instance_slug}] app is RUNNING (2/5).")
        if not run_id or results_root is None:
            raise ClickException(
                f"[{instance_slug}] internal error: run_id and results_root "
                f"required to track command completion."
            )
        done_file = _cmd_done_path(results_root, run_id, folder)
        output_log = _cmd_output_path(results_root, run_id, folder)
        wrapped_command = _wrap_command_with_done_file(
            command,
            done_file=done_file,
            output_log=output_log,
        )
        clog.info(f"[{instance_slug}] executing command (3/5): {command!r}")
        click.echo(f">>> [{instance_slug}] executing (3/5): {command!r}")
        click.echo(f"    log path on student: {output_log}")
        exec_result = execute_command_in_app(
            org_slug=org_slug,
            space_slug=space_slug,
            instance_slug=instance_slug,
            app_slug=app_slug,
            command=wrapped_command,
        )
        record["execute"] = _serialize_execute_result(exec_result)
        record["execute"]["output_path"] = output_log
        record["execute"].pop("error_path", None)
        record["execute"]["done_file"] = done_file
        record["execute"]["submitted_command"] = command
        clog.info(
            f"[{instance_slug}] execute accepted; waiting for completion "
            f"(done_file={done_file})."
        )
        click.echo(f">>> [{instance_slug}] waiting for command completion…")
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
            click.echo(f"!!! [{instance_slug}] command FAILED exit_code={exit_code}")
        else:
            record["status"] = "executed"
            clog.info(f"[{instance_slug}] command completed (4/5).")
            click.echo(f">>> [{instance_slug}] command OK exit_code=0 (4/5).")

        _try_pull_logs("after command completion")



    except Exception as exc:
        record["status"] = "failed"
        record["error"] = str(exc)
        clog.error(f"Student [{instance_slug}] failed: {exc}")
        # Timeouts / mid-flight failures: salvage any logs already under
        # results-dir before the app is stopped.
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
    command: str | None = None,
    results_dir: str | None = None,
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
    hold_duration_seconds: int | None = None,
    keep_running: bool = False,
    stagger_secs: float = 0.0,
    from_instances: bool = False,
) -> dict:
    """Orchestrator for validation check or concurrent hold evaluation.

    **Validation mode** (default): collect → start → execute → pull logs → stop
    → publish handin/handback.

    **Hold mode** (``hold_duration_seconds is not None`` or ``keep_running``):
    resolve students → wave-start apps (optional detached command) → hold
    window → bulk stop. Persists ``run_state.json`` so ``grade stop`` can
    recover after a CLI crash. Does not publish handin/handback.
    """
    hold_mode = hold_duration_seconds is not None or keep_running
    if hold_mode and hold_duration_seconds is None:
        hold_duration_seconds = 0
    if hold_mode:
        # Partial cohort is the useful outcome for an evaluation window.
        continue_on_error = True
        pull_logs = False

    instructor_instance_slug = instructor_instance_slug or _instructor_instance_slug()

    # Scratch tree for collect + in-app execute/distribute (not the durable store).
    work_root = _as_files_abs_path(results_dir or DEFAULT_GRADE_WORK_ROOT)
    work_path = Path(work_root)
    work_path.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_results_dir = work_path / run_id
    run_results_dir.mkdir(parents=True, exist_ok=True)
    run_results_abs = _as_files_abs_path(run_results_dir)

    collect_dest = run_results_abs
    if target_folder and not skip_collect and not from_instances:
        clog.warning(
            "--target-folder is deprecated for grade check; using internal staging "
            f"under {run_results_abs}. Final artifacts go to handin/handback."
        )

    mode_label = "hold" if hold_mode else "check"
    clog.info(
        f"Starting grade {mode_label} for {org_slug}/{space_slug}: app={app_slug}, "
        f"parallel={max(1, parallel)}, stagger_secs={stagger_secs}, "
        f"dry_run={dry_run}, pull_logs={pull_logs}, "
        f"instructor_instance={instructor_instance_slug}, "
        f"staging={run_results_abs}"
        + (
            f", hold_duration={hold_duration_seconds}s, keep_running={keep_running}."
            if hold_mode
            else ", durable=handin+handback."
        )
    )

    manifest_source: str | None = None
    if from_instances:
        skip_collect = True
        students = resolve_students_from_instances(
            org_slug,
            space_slug,
            instance_filter=instance_filter,
            limit=limit,
        )
    else:
        if not skip_collect:
            if not assignment_name or not assignment_folder:
                raise ClickException(
                    "Collect requires --assignment-name and --assignment-folder "
                    "(or pass --skip-collect with --manifest, or --from-instances)."
                )
            if not dry_run:
                collect_submissions(
                    assignment_name,
                    assignment_folder,
                    collect_dest,
                    org_slug=org_slug,
                    space_slug=space_slug,
                )
            else:
                clog.info(
                    f"[dry-run] would collect assignment_name={assignment_name!r} "
                    f"assignment_folder={assignment_folder!r} into {collect_dest} "
                    f"(student-email folders + later output.log in the same dirs)"
                )
            manifest_source = collect_dest
        else:
            manifest_source = manifest_path or target_folder
            if not manifest_source:
                raise ClickException(
                    "--skip-collect requires --manifest or --target-folder "
                    "pointing at an existing collect / prior results run directory "
                    "(or pass --from-instances)."
                )
            # Existing collect trees may still use instance_slug folder names.
            relabel_root = target_folder or (
                str(Path(manifest_source).parent)
                if Path(manifest_source).is_file()
                else manifest_source
            )
            if not dry_run and relabel_root and Path(relabel_root).is_dir():
                relabel_collect_targets_by_email(relabel_root, org_slug, space_slug)

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

    clog.info(f"Prepared {len(students)} student(s) for grade {mode_label}.")

    summary = {
        "run_id": run_id,
        "mode": mode_label,
        "started_at": _utc_now_iso(),
        "org_slug": org_slug,
        "space_slug": space_slug,
        "app_slug": app_slug,
        "command_template": command,
        "target_folder": (
            None
            if from_instances
            else (collect_dest if not skip_collect else (target_folder or manifest_source))
        ),
        "assignment_name": assignment_name,
        "assignment_folder": assignment_folder,
        "skip_collect": skip_collect,
        "from_instances": from_instances,
        "instance_filter": instance_filter,
        "dry_run": dry_run,
        "parallel": parallel,
        "stagger_secs": stagger_secs,
        "pull_logs": pull_logs,
        "hold_duration_seconds": hold_duration_seconds if hold_mode else None,
        "keep_running": keep_running if hold_mode else False,
        "instructor_instance_slug": instructor_instance_slug,
        "staging_root": work_root,
        "staging_run_dir": run_results_abs,
        "durable_store": (
            None
            if hold_mode
            else f"{HANDIN_REVIEW_ROOT} + {HANDBACK_REVIEW_ROOT}"
        ),
        "counts": {
            "total": len(students),
            "ok": 0,
            "failed": 0,
            "skipped": 0,
            "dry_run": 0,
            "running": 0,
            "stopped": 0,
            "start_failed": 0,
            "stop_failed": 0,
            "pending": 0,
        },
        "students": [],
    }

    runnable = []
    for student in students:
        if student["found_in_space"]:
            runnable.append(student)
            continue
        slug = student["instance_slug"]
        msg = (
            f"Instance '{slug}' not found in org={org_slug} space={space_slug} "
            f"(or API key lacks access)."
        )
        if not (skip_missing_instances or continue_on_error):
            raise ClickException(msg)
        clog.warning(msg + " Skipping.")
        summary["students"].append(
            {
                **student,
                "status": "skipped",
                "error": msg,
                "finished_at": _utc_now_iso(),
            }
        )
        summary["counts"]["skipped"] += 1

    if hold_mode:
        return _run_hold_check(
            summary=summary,
            runnable=runnable,
            org_slug=org_slug,
            space_slug=space_slug,
            app_slug=app_slug,
            command=command,
            dry_run=dry_run,
            parallel=parallel,
            stagger_secs=stagger_secs,
            hold_duration_seconds=int(hold_duration_seconds or 0),
            keep_running=keep_running,
            work_root=work_root,
            run_id=run_id,
        )

    if not command:
        raise ClickException("--command is required for validation grade check")

    def process(student):
        slug = student["instance_slug"]
        folder = student.get("folder_name") or slug
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
            results_root=work_root,
            student_folder=folder,
            instructor_instance_slug=instructor_instance_slug,
            pull_logs=pull_logs,
        )
        rec.update(
            {
                "src": student.get("src"),
                "target": student.get("target"),
                "instance_name": student.get("instance_name"),
                "email": student.get("email"),
                "folder_name": folder,
            }
        )
        return rec

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
        # Bounded in-flight starts (not all futures at once when stagger set).
        records = _run_bounded_pool(
            runnable,
            worker_count=worker_count,
            stagger_secs=stagger_secs,
            process_fn=process,
        )

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
        if not dry_run and worker_count == 1 and stagger_secs <= 0:
            time.sleep(1)

    summary["finished_at"] = _utc_now_iso()

    # Publish each student's artifacts into handin + handback path structure.
    if not dry_run:
        for rec in summary["students"]:
            if rec.get("status") in ("skipped", "dry_run", "pending"):
                continue
            try:
                rec["handin_publish"] = publish_student_results_to_handin_structure(
                    student_record=rec,
                    run_id=run_id,
                )
            except Exception as exc:
                rec["handin_publish"] = {"error": str(exc)}
                clog.warning(
                    f"[{rec.get('instance_slug')}] handin publish failed: {exc}"
                )
            publish_error = (rec.get("handin_publish") or {}).get("error")
            if publish_error and rec.get("status") == "executed":
                rec["status"] = "failed"
                rec["error"] = rec.get("error") or f"publish failed: {publish_error}"
                summary["counts"]["ok"] -= 1
                summary["counts"]["failed"] += 1

        # Full-tree handback so students see feedback in the assignment UI (readonly).
        collect_for_handback = summary.get("target_folder") or run_results_abs
        if collect_for_handback and Path(collect_for_handback).expanduser().is_file():
            collect_for_handback = str(Path(collect_for_handback).expanduser().parent)
        summary["handback"] = handback_collected_results(collect_for_handback)
        if summary["handback"].get("status") == "failed":
            summary["counts"]["failed"] += 1

    # No _nuvolos_grade_runs / grade_run_*.json — durable artifacts are only
    # per-student output.log + grade_meta.json under handin/handback.
    summary.pop("results_file", None)
    summary.pop("results_run_dir", None)
    clog.info(
        f"Grade run complete: ok={summary['counts']['ok']}, "
        f"failed={summary['counts']['failed']}, skipped={summary['counts']['skipped']}, "
        f"dry_run={summary['counts']['dry_run']}. "
        f"Per-student files: handin+handback output.log / grade_meta.json."
    )
    click.echo(
        f"\n=== Grade run {run_id} complete ===\n"
        f"  ok={summary['counts']['ok']}  failed={summary['counts']['failed']}  "
        f"skipped={summary['counts']['skipped']}  dry_run={summary['counts']['dry_run']}\n"
        f"  Durable paths: {HANDIN_REVIEW_ROOT}/… and {HANDBACK_REVIEW_ROOT}/… "
        f"(students see handback, read-only)."
    )
    return summary


def _run_hold_check(
    *,
    summary: dict,
    runnable: list[dict],
    org_slug: str,
    space_slug: str,
    app_slug: str,
    command: str | None,
    dry_run: bool,
    parallel: int,
    stagger_secs: float,
    hold_duration_seconds: int,
    keep_running: bool,
    work_root: str,
    run_id: str,
) -> dict:
    """Wave-start → optional hold → bulk stop. Mutates and returns summary."""
    worker_count = max(1, int(parallel or 1))
    state_path = _run_state_path(work_root, run_id)

    def process(student):
        slug = student["instance_slug"]
        folder = student.get("folder_name") or slug
        cmd = None
        if command:
            cmd = expand_command_template(
                command,
                instance_slug=slug,
                target=str(student.get("target") or ""),
            )
        rec = start_one_student_hold(
            org_slug=org_slug,
            space_slug=space_slug,
            instance_slug=slug,
            app_slug=app_slug,
            command=cmd,
            dry_run=dry_run,
            run_id=run_id,
            results_root=work_root,
            student_folder=folder,
        )
        rec.update(
            {
                "src": student.get("src"),
                "target": student.get("target"),
                "instance_name": student.get("instance_name"),
                "email": student.get("email"),
                "folder_name": folder,
            }
        )
        return rec

    clog.info(
        f"Hold-mode starting {len(runnable)} student app(s): parallel={worker_count}, "
        f"stagger_secs={stagger_secs}."
    )
    # Seed durable state before starts so crash mid-ramp still has a roster.
    summary["students"] = [
        {
            **s,
            "status": "pending",
            "app_slug": app_slug,
        }
        for s in summary.get("students") or []
    ]
    # pending placeholders for runnable too (replaced after start).
    pending_by_slug = {
        s["instance_slug"]: {
            **s,
            "status": "pending",
            "app_slug": app_slug,
        }
        for s in runnable
    }
    summary["students"] = list(summary["students"]) + list(pending_by_slug.values())
    save_run_state(summary, work_root=work_root)
    click.echo(f">>> Hold run_id={run_id} state → {state_path}")

    records = _run_bounded_pool(
        runnable,
        worker_count=worker_count,
        stagger_secs=stagger_secs,
        process_fn=process,
    )

    # Rebuild students list: keep prior skipped, replace pending with results.
    kept = [r for r in summary["students"] if r.get("status") == "skipped"]
    summary["students"] = kept + records
    summary["counts"] = _count_hold_statuses(summary["students"])
    summary["phase"] = "started"
    save_run_state(summary, work_root=work_root)

    running_n = summary["counts"].get("running", 0)
    failed_n = summary["counts"].get("start_failed", 0) + summary["counts"].get(
        "failed", 0
    )
    click.echo(
        f"\n>>> Start ramp done: running={running_n} start_failed={failed_n} "
        f"dry_run={summary['counts'].get('dry_run', 0)}"
    )

    stop_event = threading.Event()
    previous_handlers = {}

    def _on_signal(signum, _frame):
        clog.warning(f"Received signal {signum}; requesting bulk stop.")
        click.echo(f"\n!!! Signal {signum} — bulk-stopping hold run {run_id}…")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            previous_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, _on_signal)
        except (ValueError, OSError) as exc:
            # Not on main thread / unsupported — hold still works without signals.
            clog.debug(f"Could not install handler for {sig}: {exc}")

    try:
        if keep_running:
            summary["phase"] = "keep_running"
            summary["hold_end_reason"] = "keep_running"
            save_run_state(summary, work_root=work_root)
            click.echo(
                f"\n=== Hold start complete (apps left running) run_id={run_id} ===\n"
                f"  running={running_n}  start_failed={failed_n}\n"
                f"  Stop later with: nuvolos grade stop --run-id {run_id}\n"
                f"  State: {state_path}"
            )
            summary["finished_at"] = _utc_now_iso()
            save_run_state(summary, work_root=work_root)
            return summary

        if not dry_run and hold_duration_seconds > 0 and running_n > 0:
            summary["phase"] = "holding"
            save_run_state(summary, work_root=work_root)
            hold_evaluation_window(
                duration_seconds=hold_duration_seconds,
                state=summary,
                work_root=work_root,
                stop_event=stop_event,
            )
        elif dry_run:
            summary["hold_end_reason"] = "dry_run"
        else:
            summary["hold_end_reason"] = (
                "no_running_apps" if running_n == 0 else "no_hold"
            )

        summary["phase"] = "stopping"
        save_run_state(summary, work_root=work_root)
        if not dry_run:
            bulk_stop_students(
                org_slug=org_slug,
                space_slug=space_slug,
                app_slug=app_slug,
                students=summary["students"],
                dry_run=dry_run,
                parallel=worker_count,
                stagger_secs=stagger_secs,
            )
        summary["counts"] = _count_hold_statuses(summary["students"])
        summary["phase"] = "finished"
        summary["finished_at"] = _utc_now_iso()
        state_path = save_run_state(summary, work_root=work_root)
    finally:
        for sig, handler in previous_handlers.items():
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):
                pass

    clog.info(
        f"Hold run complete: running={summary['counts'].get('running')}, "
        f"stopped={summary['counts'].get('stopped')}, "
        f"start_failed={summary['counts'].get('start_failed')}, "
        f"stop_failed={summary['counts'].get('stop_failed')}."
    )
    click.echo(
        f"\n=== Grade hold run {run_id} complete ===\n"
        f"  running={summary['counts'].get('running')}  "
        f"stopped={summary['counts'].get('stopped')}  "
        f"start_failed={summary['counts'].get('start_failed')}  "
        f"stop_failed={summary['counts'].get('stop_failed')}\n"
        f"  State: {state_path}"
    )
    return summary


def stop_hold_run(
    *,
    run_id: str | None = None,
    state_path: str | Path | None = None,
    work_root: str | None = None,
    parallel: int = 5,
    stagger_secs: float = 0.0,
    dry_run: bool = False,
) -> dict:
    """Load persisted hold run state and bulk-stop remaining apps."""
    root = work_root or DEFAULT_GRADE_WORK_ROOT
    if state_path:
        state = load_run_state(run_id or "unknown", path=state_path)
    else:
        if not run_id:
            raise ClickException("--run-id is required unless --state-file is set")
        state = load_run_state(run_id, work_root=root)
    org_slug = state.get("org_slug")
    space_slug = state.get("space_slug")
    app_slug = state.get("app_slug")
    if not org_slug or not space_slug or not app_slug:
        raise ClickException(
            "Run state missing org_slug/space_slug/app_slug; cannot stop"
        )
    _validate_grade_environment(org_slug, space_slug)
    students = list(state.get("students") or [])
    if not students:
        raise ClickException("Run state has no students to stop")
    click.echo(
        f">>> Stopping hold run_id={state.get('run_id')} "
        f"({len(students)} student record(s)) app={app_slug}"
    )
    bulk_stop_students(
        org_slug=org_slug,
        space_slug=space_slug,
        app_slug=app_slug,
        students=students,
        dry_run=dry_run,
        parallel=parallel,
        stagger_secs=stagger_secs,
    )
    state["students"] = students
    state["counts"] = _count_hold_statuses(students)
    state["phase"] = "stopped_external"
    state["finished_at"] = _utc_now_iso()
    out = save_run_state(state, work_root=state.get("staging_root") or root)
    click.echo(
        f"=== Stop complete === stopped={state['counts'].get('stopped')} "
        f"stop_failed={state['counts'].get('stop_failed')} state={out}"
    )
    return state





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
    help=(
        "Destination for collected trees + nvcollect_manifest.json. "
        "Submission folders are renamed to student email when --org/--space given."
    ),
)
@click.option("--org", "-o", default=None, help="Organization slug (for email folder rename).")
@click.option("--space", "-s", default=None, help="Space slug (for email folder rename).")
def nv_grade_collect(assignment_name, assignment_folder, target_folder, org, space):
    """Collect submissions by calling nuvolos_collect.collect in-process."""
    check_api_key_configured()
    org_slug = org
    space_slug = space
    if not org_slug or not space_slug:
        try:
            context = json.loads(os.environ.get("NV_CONTEXT", "") or "{}")
        except json.JSONDecodeError:
            context = {}
        if isinstance(context, dict):
            org_slug = org_slug or context.get("org_slug") or context.get("org")
            space_slug = space_slug or context.get("space_slug") or context.get("space")
    collect_submissions(
        assignment_name,
        assignment_folder,
        target_folder,
        org_slug=org_slug,
        space_slug=space_slug,
    )
    if not (org_slug and space_slug):
        clog.warning(
            "Collect finished without org/space; submission folders kept as instance "
            "slugs. Pass --org/--space (or run from NV_CONTEXT) to rename to email."
        )
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
            s.get("email") or s.get("folder_name") or "",
            s.get("instance_name") or "",
            "yes" if s["found_in_space"] else "NO",
            s.get("target") or "",
        ]
        for s in students
    ]
    click.echo(
        tabulate(
            rows,
            headers=["instance_slug", "email", "name", "in_space", "target"],
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
    hidden=True,
    help=(
        "Deprecated. With --skip-collect only: optional path to an existing collect tree. "
        "Final grade artifacts always go to assignments-review handin/handback."
    ),
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
        "Shell command inside each student app (cwd=/files). "
        "Validation mode: required; waits for exit. "
        "Hold mode (--hold-duration/--keep-running): optional; launched detached. "
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
    default=None,
    required=False,
    hidden=True,
    type=click.Path(),
    help=(
        "Optional staging override (default /files/.nuvolos_grade). "
        "Durable output is always under assignments-review handin/handback."
    ),
)
@click.option(
    "--skip-collect",
    is_flag=True,
    help="Do not collect; use existing --manifest or --target-folder tree.",
)
@click.option(
    "--manifest",
    "-m",
    default=None,
    type=click.Path(exists=True),
    help="With --skip-collect: path to manifest file or prior results run dir.",
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
    help="Max concurrent student starts/checks (wave size in hold mode).",
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
        "After execute, pull output.log and publish into handin/handback "
        "(student-visible, read-only under handback)."
    ),
)
@click.option(
    "--instructor-instance",
    default=None,
    help="Instructor instance slug to receive logs (default: NV_CONTEXT instance or 'master').",
)
@click.option(
    "--hold-duration",
    default=None,
    help=(
        "Hold mode: keep apps RUNNING for this duration then bulk-stop. "
        "Examples: 30m, 1h, 1800. Enables concurrent evaluation window "
        "(no per-student stop-after-command)."
    ),
)
@click.option(
    "--keep-running",
    is_flag=True,
    help=(
        "Hold mode without timed stop: start apps and exit, leaving them running. "
        "Stop later with `nuvolos grade stop --run-id ...`."
    ),
)
@click.option(
    "--stagger-secs",
    type=float,
    default=0.0,
    show_default=True,
    help="Sleep between start requests inside a wave (rate-limit friendly).",
)
@click.option(
    "--from-instances",
    is_flag=True,
    help=(
        "Resolve students from space instance list (exclude master) instead of "
        "collect/manifest. Typical for hold-mode evaluation rosters."
    ),
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
    hold_duration,
    keep_running,
    stagger_secs,
    from_instances,
):
    """Validate submissions, or hold student apps for concurrent external evaluation.

    Default (validation): collect → start → run --command → pull logs → stop →
    publish handin/handback.

    Hold mode (--hold-duration / --keep-running): wave-start apps, optional
    detached --command, hold window, bulk stop. State under
    /files/.nuvolos_grade/<run_id>/run_state.json for `grade stop` recovery.
    """
    _validate_grade_environment(org, space)
    if grade_all:
        limit = None
    run_command = command or legacy_test_command
    hold_secs = _parse_duration_seconds(hold_duration) if hold_duration is not None else None
    hold_mode = hold_secs is not None or keep_running

    if hold_mode and hold_secs is not None and hold_secs < 0:
        raise ClickException("--hold-duration must be >= 0")

    if not hold_mode and not run_command:
        raise ClickException(
            "--command is required for validation mode "
            "(or pass --hold-duration / --keep-running)"
        )

    if from_instances:
        skip_collect = True
    elif not skip_collect:
        missing = [
            name
            for name, val in (
                ("--assignment-name", assignment_name),
                ("--assignment-folder", assignment_folder),
            )
            if not val
        ]
        if missing:
            raise ClickException(
                "Collect requires: "
                + ", ".join(missing)
                + " (or pass --skip-collect with --manifest, or --from-instances)"
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
        hold_duration_seconds=hold_secs if hold_mode else None,
        keep_running=keep_running,
        stagger_secs=stagger_secs,
        from_instances=from_instances,
    )

    mode = summary.get("mode") or "check"
    click.echo("\n" + "=" * 72)
    if mode == "hold":
        click.echo(f"GRADE HOLD SUMMARY  run_id={summary.get('run_id')}")
    else:
        click.echo(f"GRADE CHECK SUMMARY  run_id={summary.get('run_id')}")
    click.echo("=" * 72)
    click.echo(json.dumps(summary.get("counts") or {}, indent=2))
    if mode == "hold":
        click.echo(
            f"phase={summary.get('phase')!r} "
            f"hold_end_reason={summary.get('hold_end_reason')!r}"
        )
        state_hint = _run_state_path(
            summary.get("staging_root") or DEFAULT_GRADE_WORK_ROOT,
            summary.get("run_id") or "",
        )
        click.echo(f"state={state_hint}")
    click.echo("-" * 72)
    for rec in summary.get("students") or []:
        slug = rec.get("instance_slug") or "?"
        email = rec.get("email") or rec.get("folder_name") or ""
        status = rec.get("status")
        exit_code = (rec.get("execute") or {}).get("exit_code")
        err = rec.get("error") or rec.get("stop_error") or ""
        pub = rec.get("handin_publish") or {}
        click.echo(f"\n• {email or slug}")
        click.echo(f"    instance : {slug}")
        click.echo(
            f"    status   : {status}"
            + (f"  exit_code={exit_code}" if exit_code is not None else "")
        )
        if err:
            click.echo(f"    error    : {err}")
        if pub.get("handin_dir"):
            click.echo(f"    handin   : {pub.get('handin_dir')}")
        if pub.get("handback_dir"):
            click.echo(
                f"    handback : {pub.get('handback_dir')}  (student-visible, read-only)"
            )
        for fpath in pub.get("files") or []:
            click.echo(f"    file     : {fpath}")
        logs = rec.get("instructor_logs") or {}
        out_path = (logs.get("local_paths") or {}).get("output.log")
        if out_path:
            click.echo(f"    log      : {out_path}")
        # Re-print full log at the end so instructors can scroll one place.
        text = (logs.get("log_excerpts") or {}).get("output.log")
        truncated = (logs.get("log_truncated") or {}).get("output.log")
        if text:
            label = " (truncated)" if truncated else ""
            ban = f"----- output.log [{email or slug}]{label} -----"
            click.echo(ban)
            click.echo(text if text.endswith("\n") else text + "\n")
            click.echo("-" * len(ban))
    hb = summary.get("handback") or {}
    if hb:
        click.echo(
            f"\nhandback batch: status={hb.get('status')!r} error={hb.get('error')!r}"
        )
    click.echo("=" * 72 + "\n")

    failed = int(summary.get("counts", {}).get("failed") or 0)
    if mode == "hold":
        failed = int(summary.get("counts", {}).get("start_failed") or 0) + int(
            summary.get("counts", {}).get("stop_failed") or 0
        )
    if failed and not dry_run:
        raise ClickException(
            f"Grade run finished with {failed} failure(s). "
            + (
                f"Use `nuvolos grade stop --run-id {summary.get('run_id')}` if apps remain up."
                if mode == "hold"
                else "See per-student handin/handback output.log above."
            )
        )


@nv_grade.command("stop")
@click.option(
    "--run-id",
    default=None,
    help="Hold-mode run_id from a prior `grade check --hold-duration` / --keep-running.",
)
@click.option(
    "--state-file",
    type=click.Path(exists=True),
    default=None,
    help="Explicit path to run_state.json (alternative to --run-id).",
)
@click.option(
    "--results-dir",
    "-r",
    default=None,
    type=click.Path(),
    help=f"Staging root that contains <run_id>/ (default {DEFAULT_GRADE_WORK_ROOT}).",
)
@click.option(
    "--parallel",
    type=click.IntRange(min=1),
    default=5,
    show_default=True,
    help="Max concurrent stop requests.",
)
@click.option(
    "--stagger-secs",
    type=float,
    default=0.0,
    show_default=True,
    help="Sleep between stop requests.",
)
@click.option("--dry-run", is_flag=True, help="Plan only; do not stop apps.")
def nv_grade_stop(run_id, state_file, results_dir, parallel, stagger_secs, dry_run):
    """Bulk-stop apps from a prior hold-mode grade check (crash recovery)."""
    if not run_id and not state_file:
        raise ClickException("Provide --run-id or --state-file")
    state = stop_hold_run(
        run_id=run_id,
        state_path=state_file,
        work_root=results_dir,
        parallel=parallel,
        stagger_secs=stagger_secs,
        dry_run=dry_run,
    )
    click.echo(json.dumps(state.get("counts") or {}, indent=2))
    failed = int((state.get("counts") or {}).get("stop_failed") or 0)
    if failed and not dry_run:
        raise ClickException(f"Bulk stop finished with {failed} stop_failed student(s).")


