"""Behavioral tests for nuvolos grade (Client API–backed orchestration)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from nuvolos_client_api.models.instance import Instance
from nuvolos_client_api.models.space import Space
from nuvolos_client_api.models.space_instance_role import SpaceInstanceRole
from nuvolos_client_api.models.space_member import SpaceMember

from nuvolos_cli.grade import (
    _email_from_space_members,
    _space_members_by_instance_slug,
    expand_command_template,
    in_student_handin_path,
    resolve_students,
)
from nuvolos_cli.interface import nuvolos


TEACHING_CTX = {
    "org_slug": "org1",
    "space_slug": "space1",
    "instance_slug": "master",
}


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def teaching_env(monkeypatch):
    monkeypatch.setenv("NV_CONTEXT", json.dumps(TEACHING_CTX))
    monkeypatch.setenv("NUVOLOS_API_KEY", "test-key")


def _teaching_space():
    return Space(
        slug="space1",
        name="Course",
        type="TEACHING",
        visibility_type="PRIVATE",
        video_library_enabled=False,
    )


def _json_payload(output: str):
    start = output.find("[")
    assert start >= 0, output
    return json.loads(output[start:])


def test_grade_help_lists_commands(runner):
    result = runner.invoke(nuvolos, ["grade", "--help"])
    assert result.exit_code == 0, result.output
    assert "collect" in result.output
    assert "resolve-manifest" in result.output
    assert "check" in result.output


def test_grade_check_requires_command(runner, teaching_env):
    with (
        patch("nuvolos_cli.grade.check_api_key_configured", return_value="k"),
        patch("nuvolos_cli.grade.list_spaces", return_value=[_teaching_space()]),
    ):
        result = runner.invoke(
            nuvolos,
            [
                "grade",
                "check",
                "-o",
                "org1",
                "-s",
                "space1",
                "-a",
                "jupyter",
                "--skip-collect",
                "-m",
                ".",
            ],
        )
    assert result.exit_code != 0
    assert "--command is required" in result.output


def test_grade_check_requires_collect_args(runner, teaching_env):
    with (
        patch("nuvolos_cli.grade.check_api_key_configured", return_value="k"),
        patch("nuvolos_cli.grade.list_spaces", return_value=[_teaching_space()]),
    ):
        result = runner.invoke(
            nuvolos,
            [
                "grade",
                "check",
                "-o",
                "org1",
                "-s",
                "space1",
                "-a",
                "jupyter",
                "-c",
                "true",
            ],
        )
    assert result.exit_code != 0
    assert "Collect requires" in result.output


def test_grade_rejects_non_master_context(runner, monkeypatch):
    monkeypatch.setenv(
        "NV_CONTEXT",
        json.dumps(
            {
                "org_slug": "org1",
                "space_slug": "space1",
                "instance_slug": "student_a",
            }
        ),
    )
    monkeypatch.setenv("NUVOLOS_API_KEY", "test-key")
    with (
        patch("nuvolos_cli.grade.check_api_key_configured", return_value="k"),
        patch("nuvolos_cli.grade.list_spaces", return_value=[_teaching_space()]),
    ):
        result = runner.invoke(
            nuvolos,
            [
                "grade",
                "check",
                "-o",
                "org1",
                "-s",
                "space1",
                "-a",
                "jupyter",
                "-c",
                "true",
                "--skip-collect",
                "-m",
                ".",
            ],
        )
    assert result.exit_code != 0
    assert "master instance" in result.output


def test_expand_command_template_placeholders():
    out = expand_command_template(
        "python run.py --s {instance_slug} --i {instance} --t {target}",
        instance_slug="stu_1",
        target="/assignments/handin/hw1/submission",
    )
    assert out == (
        "python run.py --s stu_1 --i stu_1 --t /assignments/handin/hw1/submission"
    )


def test_in_student_handin_path_maps_master_src_to_in_app_mount():
    src = "/files/assignments-review/handin/stu_a/hw1/2026-01-01_00:00:00_abcd/submission"
    out = in_student_handin_path(src, "stu_a")
    assert out == "/assignments/handin/hw1/2026-01-01_00:00:00_abcd/submission"


def test_in_student_handin_path_none_for_unrelated_src():
    assert in_student_handin_path(None, "stu_a") is None
    assert in_student_handin_path("/files/other/stu_a/x", "stu_a") is None
    # Different student's slug in the path must not match.
    assert in_student_handin_path(
        "/files/assignments-review/handin/stu_b/hw1/submission", "stu_a"
    ) is None


def test_email_from_space_members_prefers_editor():
    members = [
        {"email": "viewer@ex.com", "role": "VIEWER"},
        {"email": "editor@ex.com", "role": "EDITOR"},
    ]
    assert _email_from_space_members(members) == "editor@ex.com"


def test_space_members_by_instance_slug_indexes_roles():
    members = [
        SpaceMember(
            name="Alice",
            email="alice@ex.com",
            active=True,
            space_role=None,
            instance_roles=[
                SpaceInstanceRole(instance_slug="stu_a", role="EDITOR"),
            ],
        ),
        SpaceMember(
            name="Bob",
            email="bob@ex.com",
            active=True,
            space_role="SPACE_ADMIN",
            instance_roles=[
                SpaceInstanceRole(instance_slug="stu_b", role="VIEWER"),
                SpaceInstanceRole(instance_slug="stu_a", role="VIEWER"),
            ],
        ),
    ]
    with patch("nuvolos_cli.grade.list_space_members", return_value=members):
        indexed = _space_members_by_instance_slug("org", "space")
    assert set(indexed) == {"stu_a", "stu_b"}
    assert {m["email"] for m in indexed["stu_a"]} == {"alice@ex.com", "bob@ex.com"}
    assert indexed["stu_b"][0]["email"] == "bob@ex.com"


def test_resolve_students_uses_instances_and_space_members():
    manifest = {
        "items": [
            {
                "src": "/files/assignments-review/handin/stu_a/a/ts/",
                "target": "/files/collected/stu_a/",
            },
            {
                "src": "/files/assignments-review/handin/missing/a/ts/",
                "target": "/files/collected/missing/",
            },
        ]
    }
    instances = [
        Instance(slug="stu_a", name="Not An Email"),
        Instance(slug="master", name="Master"),
    ]
    members = [
        SpaceMember(
            name="Alice Student",
            email="alice@ex.com",
            active=True,
            space_role=None,
            instance_roles=[SpaceInstanceRole(instance_slug="stu_a", role="EDITOR")],
        )
    ]
    with (
        patch("nuvolos_cli.grade.list_instances", return_value=instances),
        patch("nuvolos_cli.grade.list_space_members", return_value=members),
    ):
        students = resolve_students(manifest, "org1", "space1")

    assert len(students) == 2
    alice = students[0]
    assert alice["instance_slug"] == "stu_a"
    assert alice["found_in_space"] is True
    assert alice["email"] == "alice@ex.com"
    assert alice["instance_role"] == "EDITOR"
    assert alice["folder_name"] == "alice@ex.com"
    assert alice["in_app_target"] == "/assignments/handin/a/ts"

    missing = students[1]
    assert missing["instance_slug"] == "missing"
    assert missing["found_in_space"] is False
    assert missing["email"] is None


def test_resolve_manifest_cli_json(runner, teaching_env, tmp_path):
    manifest_path = tmp_path / "nvcollect_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "src": "/files/assignments-review/handin/stu_a/asg/ts/",
                        "target": str(tmp_path / "stu_a"),
                    }
                ]
            }
        )
    )
    instances = [Instance(slug="stu_a", name="alice@ex.com")]
    members = [
        SpaceMember(
            name="Alice",
            email="alice@ex.com",
            active=True,
            space_role=None,
            instance_roles=[SpaceInstanceRole(instance_slug="stu_a", role="EDITOR")],
        )
    ]
    with (
        patch("nuvolos_cli.grade.check_api_key_configured", return_value="k"),
        patch("nuvolos_cli.grade.list_spaces", return_value=[_teaching_space()]),
        patch("nuvolos_cli.grade.list_instances", return_value=instances),
        patch("nuvolos_cli.grade.list_space_members", return_value=members),
    ):
        result = runner.invoke(
            nuvolos,
            [
                "grade",
                "resolve-manifest",
                "-m",
                str(manifest_path),
                "-o",
                "org1",
                "-s",
                "space1",
                "-f",
                "json",
            ],
        )
    assert result.exit_code == 0, result.output
    payload = _json_payload(result.output)
    assert payload[0]["email"] == "alice@ex.com"
    assert payload[0]["instance_role"] == "EDITOR"
    assert payload[0]["found_in_space"] is True


def test_grade_check_dry_run_uses_client_lifecycle_plan(runner, teaching_env, tmp_path):
    manifest_path = tmp_path / "nvcollect_manifest.json"
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    manifest_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "src": "/files/assignments-review/handin/stu_a/asg/ts/",
                        "target": str(tmp_path / "stu_a"),
                    }
                ]
            }
        )
    )
    instances = [Instance(slug="stu_a", name="alice@ex.com")]

    def _fake_files_path(path):
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = results_dir / p
        return str(p)

    with (
        patch("nuvolos_cli.grade.check_api_key_configured", return_value="k"),
        patch("nuvolos_cli.grade.list_spaces", return_value=[_teaching_space()]),
        patch("nuvolos_cli.grade.list_instances", return_value=instances),
        patch("nuvolos_cli.grade.list_space_members", return_value=[]),
        patch("nuvolos_cli.grade._as_files_abs_path", side_effect=_fake_files_path),
        patch("nuvolos_cli.grade.DEFAULT_GRADE_WORK_ROOT", str(results_dir)),
        patch("nuvolos_cli.grade.start_app") as start,
        patch("nuvolos_cli.grade.execute_command_in_app") as execute,
        patch("nuvolos_cli.grade.stop_app") as stop,
    ):
        result = runner.invoke(
            nuvolos,
            [
                "grade",
                "check",
                "-o",
                "org1",
                "-s",
                "space1",
                "-a",
                "jupyterlab",
                "-c",
                "python -c 'print(1)'",
                "--skip-collect",
                "-m",
                str(manifest_path),
                "--dry-run",
                "--all",
                "-r",
                str(results_dir),
            ],
        )
    assert result.exit_code == 0, result.output
    assert "GRADE CHECK SUMMARY" in result.output
    assert "dry_run" in result.output
    start.assert_not_called()
    execute.assert_not_called()
    stop.assert_not_called()


def test_grade_collect_invokes_nuvolos_collect(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("NUVOLOS_API_KEY", "test-key")
    target = tmp_path / "out"
    target.mkdir()
    with (
        patch("nuvolos_cli.grade.check_api_key_configured", return_value="k"),
        patch("nuvolos_cli.grade.collect_submissions", return_value=0) as collect,
    ):
        result = runner.invoke(
            nuvolos,
            [
                "grade",
                "collect",
                "--assignment-name",
                "hw1",
                "--assignment-folder",
                "submission",
                "--target-folder",
                str(target),
                "-o",
                "org1",
                "-s",
                "space1",
            ],
        )
    assert result.exit_code == 0, result.output
    collect.assert_called_once()
    assert "Collect completed" in result.output


def test_wait_for_execute_completion_zero_disables_timeout(monkeypatch):
    """--exec-timeout 0 must poll indefinitely instead of failing instantly."""
    from nuvolos_cli import grade as grade_mod

    calls = {"n": 0}

    def fake_list_files(**kwargs):
        calls["n"] += 1
        # First call: not there yet. Second+: file present with stable size.
        if calls["n"] < 2:
            return []
        return [{"name": ".cmd_done", "size": 1}]

    monkeypatch.setattr(grade_mod, "list_files", fake_list_files)
    monkeypatch.setattr(grade_mod, "_parse_exit_code_from_listing", lambda **kw: 0)
    monkeypatch.setattr(grade_mod.time, "sleep", lambda _seconds: None)

    exit_code = grade_mod._wait_for_execute_completion(
        org_slug="org1",
        space_slug="space1",
        instance_slug="stu_1",
        done_file="/files/.nuvolos_grade/run/stu_1/.cmd_done",
        timeout_secs=0,
    )
    assert exit_code == 0
    assert calls["n"] >= 2


def test_wait_for_execute_completion_finite_timeout_raises(monkeypatch):
    from nuvolos_cli import grade as grade_mod
    from click import ClickException

    monkeypatch.setattr(grade_mod, "list_files", lambda **kwargs: [])
    monkeypatch.setattr(grade_mod.time, "sleep", lambda _seconds: None)
    # Force the deadline to already be in the past so the loop exits on the
    # first iteration instead of actually waiting real time in the test.
    times = iter([1000.0, 1000.0, 2000.0])
    monkeypatch.setattr(grade_mod.time, "time", lambda: next(times))

    with pytest.raises(ClickException, match="Timed out after 5s"):
        grade_mod._wait_for_execute_completion(
            org_slug="org1",
            space_slug="space1",
            instance_slug="stu_1",
            done_file="/files/.nuvolos_grade/run/stu_1/.cmd_done",
            timeout_secs=5,
        )


def test_started_app_registry_stop_all(monkeypatch):
    from nuvolos_cli import grade as grade_mod

    stops = []

    def fake_stop(**kwargs):
        stops.append(
            (
                kwargs["org_slug"],
                kwargs["space_slug"],
                kwargs["instance_slug"],
                kwargs["app_slug"],
            )
        )

    monkeypatch.setattr(grade_mod, "stop_app", fake_stop)
    registry = grade_mod._StartedAppRegistry()
    registry.add("org1", "space1", "stu_a", "bot")
    registry.add("org1", "space1", "stu_b", "bot")
    n = registry.stop_all()
    assert n == 2
    assert set(stops) == {
        ("org1", "space1", "stu_a", "bot"),
        ("org1", "space1", "stu_b", "bot"),
    }
    assert registry.snapshot() == []


def test_test_one_student_stops_app_on_abort(monkeypatch):
    """Ctrl+C mid-wait must still stop the student app (finally + registry)."""
    from nuvolos_cli import grade as grade_mod

    calls = []

    def fake_stop(**kwargs):
        calls.append(("stop", kwargs["instance_slug"], kwargs["app_slug"]))

    def fake_start(**kwargs):
        calls.append(("start", kwargs["instance_slug"], kwargs["app_slug"]))

    def fake_wait(**kwargs):
        calls.append(("wait", kwargs["instance_slug"], kwargs["app_slug"]))
        raise KeyboardInterrupt("simulated Ctrl+C")

    monkeypatch.setattr(grade_mod, "stop_app", fake_stop)
    monkeypatch.setattr(grade_mod, "start_app", fake_start)
    monkeypatch.setattr(grade_mod, "wait_for_app_running", fake_wait)
    monkeypatch.setattr(grade_mod, "list_apps", lambda **kw: [{"slug": "bot"}])
    # No pre-existing workload → pre-start cleanup is a no-op.
    monkeypatch.setattr(
        grade_mod, "list_all_running_workloads_for_app", lambda **kw: []
    )

    registry = grade_mod._StartedAppRegistry()
    grade_mod._set_active_registry(registry)
    try:
        with pytest.raises(KeyboardInterrupt):
            grade_mod.test_one_student(
                org_slug="org1",
                space_slug="space1",
                instance_slug="stu_a",
                app_slug="bot",
                command="python bot.py",
                run_id="run1",
                results_root="/files/.nuvolos_grade",
                student_folder="alice@ex.com",
                pull_logs=False,
            )
    finally:
        grade_mod._set_active_registry(None)

    stop_calls = [c for c in calls if c[0] == "stop"]
    assert stop_calls == [("stop", "stu_a", "bot")]
    assert ("start", "stu_a", "bot") in calls
    assert registry.snapshot() == []


def test_stop_app_if_running_skips_when_no_workload(monkeypatch):
    from nuvolos_cli import grade as grade_mod

    stops = []
    monkeypatch.setattr(
        grade_mod, "list_all_running_workloads_for_app", lambda **kw: []
    )
    monkeypatch.setattr(
        grade_mod, "stop_app", lambda **kw: stops.append(kw["instance_slug"])
    )
    assert (
        grade_mod._stop_app_if_running(
            org_slug="org1",
            space_slug="space1",
            instance_slug="stu_a",
            app_slug="bot",
            reason="test",
        )
        is False
    )
    assert stops == []


def test_stop_app_if_running_stops_when_workload_present(monkeypatch):
    from nuvolos_cli import grade as grade_mod

    stops = []
    monkeypatch.setattr(
        grade_mod,
        "list_all_running_workloads_for_app",
        lambda **kw: [{"status": "RUNNING"}],
    )
    monkeypatch.setattr(
        grade_mod, "stop_app", lambda **kw: stops.append(kw["instance_slug"])
    )
    assert (
        grade_mod._stop_app_if_running(
            org_slug="org1",
            space_slug="space1",
            instance_slug="stu_a",
            app_slug="bot",
            reason="test",
        )
        is True
    )
    assert stops == ["stu_a"]



def test_run_grade_check_aborts_stops_started_apps(monkeypatch, tmp_path):
    """Abort during a multi-student run must stop every app already started."""
    from click import ClickException
    from nuvolos_cli import grade as grade_mod

    manifest_path = tmp_path / "nvcollect_manifest.json"
    work = tmp_path / "work"
    work.mkdir()
    manifest_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "src": "/files/assignments-review/handin/stu_a/asg/ts/",
                        "target": str(tmp_path / "stu_a"),
                    },
                    {
                        "src": "/files/assignments-review/handin/stu_b/asg/ts/",
                        "target": str(tmp_path / "stu_b"),
                    },
                ]
            }
        )
    )

    stops = []
    starts = []

    def fake_stop(**kwargs):
        stops.append(kwargs["instance_slug"])

    def fake_start(**kwargs):
        starts.append(kwargs["instance_slug"])

    def fake_wait(**kwargs):
        # Abort once the first student app is up.
        if kwargs["instance_slug"] == "stu_a":
            raise KeyboardInterrupt("abort after first start")

    def fake_files_path(path):
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = work / p
        return str(p)

    monkeypatch.setattr(grade_mod, "stop_app", fake_stop)
    monkeypatch.setattr(grade_mod, "start_app", fake_start)
    monkeypatch.setattr(grade_mod, "wait_for_app_running", fake_wait)
    monkeypatch.setattr(grade_mod, "list_apps", lambda **kw: [{"slug": "bot"}])
    monkeypatch.setattr(
        grade_mod, "list_all_running_workloads_for_app", lambda **kw: []
    )
    monkeypatch.setattr(
        grade_mod,
        "list_instances",
        lambda **kw: [
            Instance(slug="stu_a", name="a@ex.com"),
            Instance(slug="stu_b", name="b@ex.com"),
        ],
    )
    monkeypatch.setattr(grade_mod, "list_space_members", lambda **kw: [])
    monkeypatch.setattr(grade_mod, "_as_files_abs_path", fake_files_path)
    monkeypatch.setattr(grade_mod, "DEFAULT_GRADE_WORK_ROOT", str(work))
    # Avoid signal handler install side effects in unit tests.
    monkeypatch.setattr(grade_mod, "_install_grade_abort_handlers", lambda reg: {})
    monkeypatch.setattr(grade_mod, "_restore_grade_abort_handlers", lambda prev: None)

    with pytest.raises(ClickException, match="Grade run aborted"):
        grade_mod.run_grade_check(
            org_slug="org1",
            space_slug="space1",
            app_slug="bot",
            command="python bot.py",
            skip_collect=True,
            manifest_path=str(manifest_path),
            pull_logs=False,
            continue_on_error=True,
        )

    assert "stu_a" in starts
    # pre-start cleanup + finally stop (and possibly orchestrator sweep)
    assert stops.count("stu_a") >= 1
    assert grade_mod._get_active_registry() is None


def test_wait_loop_raises_when_abort_requested(monkeypatch):
    from nuvolos_cli import grade as grade_mod

    registry = grade_mod._StartedAppRegistry()
    registry.request_abort()
    grade_mod._set_active_registry(registry)
    monkeypatch.setattr(grade_mod.time, "sleep", lambda _s: None)
    try:
        with pytest.raises(KeyboardInterrupt, match="grade aborted"):
            grade_mod._wait_for_files_area_path(
                org_slug="org1",
                space_slug="space1",
                instance_slug="stu_a",
                rel_path=".nuvolos_grade/x/.cmd_done",
                timeout_secs=30,
            )
    finally:
        grade_mod._set_active_registry(None)
