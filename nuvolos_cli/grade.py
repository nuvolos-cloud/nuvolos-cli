"""Instructor assignment testing (NC-3322) — base structure.

Option A: ``nuvolos grade check`` calls ``nuvolos_collect.collect``
in-process, then runs start → wait → execute → stop per student instance via
existing ``api_client`` (API-key auth).

Deferred (not in this module yet):
- GPU ``--node-pool`` keep-warm sequencing
- Credit ``billing_mode`` / course-test billing
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import click
from click import ClickException
from tabulate import tabulate

from .api_client import (
    execute_command_in_app,
    list_apps,
    list_instances,
    start_app,
    stop_app,
    wait_for_app_running,
)
from .config import check_api_key_configured
from .logging import clog
from .utils import _model_to_dict

MANIFEST_FILENAME = "nvcollect_manifest.json"


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
    instances = list_instances(org_slug=org_slug, space_slug=space_slug)
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
        students.append(
            {
                "index": idx,
                "instance_slug": slug,
                "src": item.get("src"),
                "target": item.get("target"),
                "instance_name": (meta or {}).get("name"),
                "found_in_space": meta is not None,
            }
        )

    if instance_filter and not students:
        raise ClickException(
            f"No manifest item matched --instance {instance_filter!r}"
        )

    if limit is not None:
        students = students[: max(0, limit)]
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


def test_one_student(
    *,
    org_slug: str,
    space_slug: str,
    instance_slug: str,
    app_slug: str,
    command: str,
    dry_run: bool = False,
    skip_app_preflight: bool = False,
) -> dict:
    """Start → wait RUNNING → execute → stop for one student instance."""
    record = {
        "instance_slug": instance_slug,
        "app_slug": app_slug,
        "command": command,
        "status": "pending",
        "started_at": _utc_now_iso(),
        "execute": None,
        "error": None,
        "stopped": None,
    }

    if dry_run:
        record["status"] = "dry_run"
        record["finished_at"] = _utc_now_iso()
        clog.info(
            f"[dry-run] would start/execute/stop app={app_slug} "
            f"on {org_slug}/{space_slug}/{instance_slug}: {command!r}"
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
            record["status"] = "failed"
            record["error"] = (
                f"App slug '{app_slug}' not found on instance '{instance_slug}'. "
                f"Available: {sorted(app_slugs)}"
            )
            record["finished_at"] = _utc_now_iso()
            return record

    started = False
    try:
        clog.info(f"Starting app [{app_slug}] on instance [{instance_slug}]...")
        # GPU node_pool deferred; credit billing_mode deferred
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
        clog.info(f"Executing test command on [{instance_slug}]...")
        exec_result = execute_command_in_app(
            org_slug=org_slug,
            space_slug=space_slug,
            instance_slug=instance_slug,
            app_slug=app_slug,
            command=command,
        )
        record["execute"] = _serialize_execute_result(exec_result)
        record["status"] = "executed"
    except Exception as exc:
        record["status"] = "failed"
        record["error"] = str(exc)
        clog.error(f"Student [{instance_slug}] failed: {exc}")
    finally:
        if started:
            try:
                clog.info(
                    f"Stopping app [{app_slug}] on instance [{instance_slug}]..."
                )
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
    return record


def run_grade_check(
    *,
    org_slug: str,
    space_slug: str,
    app_slug: str,
    test_command: str,
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
) -> dict:
    """Orchestrator: optional collect → resolve → lifecycle batch."""

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
        # dry-run with collect: try existing manifest if present, else empty plan
        try:
            manifest = read_manifest(manifest_source)
        except ClickException:
            clog.warning(
                "No existing manifest for dry-run without prior collect; "
                "student list empty until a real collect runs."
            )
            manifest = {"meta": {}, "items": []}

    students = resolve_students(
        manifest,
        org_slug,
        space_slug,
        instance_filter=instance_filter,
        limit=limit,
    )

    results_path = Path(results_dir).expanduser().resolve()
    results_path.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    summary = {
        "run_id": run_id,
        "started_at": _utc_now_iso(),
        "org_slug": org_slug,
        "space_slug": space_slug,
        "app_slug": app_slug,
        "test_command_template": test_command,
        "target_folder": target_folder,
        "assignment_name": assignment_name,
        "assignment_folder": assignment_folder,
        "skip_collect": skip_collect,
        "instance_filter": instance_filter,
        "dry_run": dry_run,
        "deferred": {
            "gpu_node_pool": "not implemented in base structure",
            "credit_billing_mode": "not implemented in base structure",
        },
        "counts": {
            "total": len(students),
            "ok": 0,
            "failed": 0,
            "skipped": 0,
            "dry_run": 0,
        },
        "students": [],
    }

    for student in students:
        slug = student["instance_slug"]
        if not student["found_in_space"]:
            msg = (
                f"Instance '{slug}' not found in org={org_slug} space={space_slug} "
                "(or API key lacks access)."
            )
            if skip_missing_instances or continue_on_error:
                clog.warning(msg + " Skipping.")
                rec = {
                    **student,
                    "status": "skipped",
                    "error": msg,
                    "finished_at": _utc_now_iso(),
                }
                summary["students"].append(rec)
                summary["counts"]["skipped"] += 1
                continue
            raise ClickException(msg)

        command = expand_command_template(
            test_command,
            instance_slug=slug,
            target=str(student.get("target") or ""),
        )
        rec = test_one_student(
            org_slug=org_slug,
            space_slug=space_slug,
            instance_slug=slug,
            app_slug=app_slug,
            command=command,
            dry_run=dry_run,
        )
        rec["src"] = student.get("src")
        rec["target"] = student.get("target")
        rec["instance_name"] = student.get("instance_name")
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
            if not continue_on_error and not dry_run:
                break

        if not dry_run:
            time.sleep(1)

    summary["finished_at"] = _utc_now_iso()
    out_file = results_path / f"grade_run_{run_id}.json"
    with out_file.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, default=str)
    summary["results_file"] = str(out_file)
    clog.info(f"Wrote grade run summary to {out_file}")
    return summary


# ---------------------------------------------------------------------------
# Click commands
# ---------------------------------------------------------------------------


@click.group("grade")
def nv_grade():
    """Student assignment testing / grading (instructor).

    Uses the same API key as other nuvolos commands
    (``nuvolos config --api-key`` / ``NUVOLOS_API_KEY``).

    Primary flow (Option A): collect via nuvolos_collect, then test each
    student instance with apps start/execute/stop.
    """


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
    """Collect submissions by calling nuvolos_collect.collect in-process.

    Requires /files/assignments-review/handin (instructor Nuvolos app mount).
    """
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
    check_api_key_configured()
    manifest_data = read_manifest(manifest)
    students = resolve_students(
        manifest_data, org, space, instance_filter=instance
    )
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
    "--test-command",
    "-c",
    required=True,
    help=(
        "Command for apps execute. "
        "Placeholders: {instance_slug}, {instance}, {target}."
    ),
)
@click.option(
    "--results-dir",
    "-r",
    required=True,
    type=click.Path(),
    help="Directory for grade_run_*.json summaries.",
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
    help="Continue to the next student after a failure.",
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
def nv_grade_check(
    assignment_name,
    assignment_folder,
    target_folder,
    org,
    space,
    instance,
    app_slug,
    test_command,
    results_dir,
    skip_collect,
    manifest,
    dry_run,
    continue_on_error,
    skip_missing_instances,
    limit,
):
    """Collect (Option A) then test each student instance.

    Base lifecycle per student: start → wait RUNNING → execute → stop.
    Auth: existing API key only.

    Deferred: GPU --node-pool, credit billing_mode.
    """
    check_api_key_configured()

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
                "Option A collect requires: "
                + ", ".join(missing)
                + " (or pass --skip-collect with --manifest)"
            )

    summary = run_grade_check(
        org_slug=org,
        space_slug=space,
        app_slug=app_slug,
        test_command=test_command,
        results_dir=results_dir,
        target_folder=target_folder,
        assignment_name=assignment_name,
        assignment_folder=assignment_folder,
        skip_collect=skip_collect,
        manifest_path=manifest,
        instance_filter=instance,
        dry_run=dry_run,
        continue_on_error=continue_on_error,
        skip_missing_instances=skip_missing_instances,
        limit=limit,
    )

    click.echo(json.dumps(summary["counts"], indent=2))
    click.echo(f"results_file: {summary.get('results_file')}")

    if summary["counts"]["failed"] and not dry_run:
        raise ClickException(
            f"Grade run finished with {summary['counts']['failed']} failure(s). "
            f"See {summary.get('results_file')}"
        )
