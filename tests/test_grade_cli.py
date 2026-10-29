"""Behavioral tests for nuvolos grade (Client API–backed orchestration)."""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
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




def test_wait_for_execute_completion_zero_disables_timeout(monkeypatch):
    """--exec-timeout 0 must poll indefinitely instead of failing instantly."""
    from nuvolos_cli import grade as grade_mod

    calls = {"n": 0}

    def fake_list_files(**kwargs):
        calls["n"] += 1
        # First call: not there yet. Second+: done file plus the exit sentinel,
        # which must be read from this same listing (no second request).
        if calls["n"] < 2:
            return []
        return [{"name": ".cmd_done", "size": 1}, {"name": ".cmd_exit.0"}]

    monkeypatch.setattr(grade_mod, "list_files", fake_list_files)
    monkeypatch.setattr(grade_mod.time, "sleep", lambda _seconds: None)

    exit_code = grade_mod._wait_for_execute_completion(
        org_slug="org1",
        space_slug="space1",
        instance_slug="stu_1",
        done_file="/files/.nuvolos_grade/run/stu_1/.cmd_done",
        timeout_secs=0,
    )
    assert exit_code == 0
    assert calls["n"] == 2


def test_wait_for_execute_completion_finite_timeout_raises(monkeypatch):
    from nuvolos_cli import grade as grade_mod
    from click import ClickException

    monkeypatch.setattr(grade_mod, "list_files", lambda **kwargs: [])
    monkeypatch.setattr(grade_mod.time, "sleep", lambda _seconds: None)
    # Virtual clock: every read advances time, so the 5s deadline is reached
    # after a few polls instead of waiting real time. Avoids pinning the test
    # to an exact number of time.time() reads.
    clock = {"t": 1000.0}

    def _tick():
        clock["t"] += 1.0
        return clock["t"]

    monkeypatch.setattr(grade_mod.time, "time", _tick)

    with pytest.raises(ClickException, match="Timed out after 5s"):
        grade_mod._wait_for_execute_completion(
            org_slug="org1",
            space_slug="space1",
            instance_slug="stu_1",
            done_file="/files/.nuvolos_grade/run/stu_1/.cmd_done",
            timeout_secs=5,
        )


def test_wait_for_execute_completion_tolerates_absent_work_dir(monkeypatch):
    """Production incident (2026-10-27, UZH Advanced Topics).

    The per-student work dir is created by `mkdir -p` inside the validation
    command itself, so the first listings target a path that cannot exist yet.
    Files V1 reports that as 404. The waiter must treat it as "not ready" and
    keep polling, not surface it as a failure.
    """
    from nuvolos_cli import grade as grade_mod

    class _NotFound(Exception):
        status = 404
        body = '{"code": "item_not_found"}'

    calls = {"n": 0}

    def fake_list_files(**kwargs):
        calls["n"] += 1
        if calls["n"] <= 3:
            raise _NotFound("File or folder does not exist")
        return [{"name": ".cmd_done", "size": 1}, {"name": ".cmd_exit.0"}]

    monkeypatch.setattr(grade_mod, "list_files", fake_list_files)
    monkeypatch.setattr(grade_mod.time, "sleep", lambda _seconds: None)

    exit_code = grade_mod._wait_for_execute_completion(
        org_slug="org1",
        space_slug="space1",
        instance_slug="stu_1",
        done_file="/files/.nuvolos_grade/run/stu_1/.cmd_done",
        timeout_secs=0,
    )
    assert exit_code == 0
    assert calls["n"] == 4


def test_wait_for_execute_completion_reports_nonzero_exit(monkeypatch):
    """A failing validation command must surface its real exit code."""
    from nuvolos_cli import grade as grade_mod

    monkeypatch.setattr(
        grade_mod,
        "list_files",
        lambda **kwargs: [
            {"name": ".cmd_done", "size": 1},
            {"name": ".cmd_exit.2"},
        ],
    )
    monkeypatch.setattr(grade_mod.time, "sleep", lambda _seconds: None)

    assert (
        grade_mod._wait_for_execute_completion(
            org_slug="org1",
            space_slug="space1",
            instance_slug="stu_1",
            done_file="/files/.nuvolos_grade/run/stu_1/.cmd_done",
            timeout_secs=0,
        )
        == 2
    )


def test_wait_for_execute_completion_missing_sentinel_is_failure(monkeypatch):
    """Done file without `.cmd_exit.<code>` must not be reported as success."""
    from nuvolos_cli import grade as grade_mod

    monkeypatch.setattr(
        grade_mod,
        "list_files",
        lambda **kwargs: [{"name": ".cmd_done", "size": 1}],
    )
    monkeypatch.setattr(grade_mod.time, "sleep", lambda _seconds: None)

    assert (
        grade_mod._wait_for_execute_completion(
            org_slug="org1",
            space_slug="space1",
            instance_slug="stu_1",
            done_file="/files/.nuvolos_grade/run/stu_1/.cmd_done",
            timeout_secs=0,
        )
        == 1
    )


def test_wrap_command_publishes_exit_sentinel_before_done_file():
    from nuvolos_cli.grade import _wrap_command_with_done_file

    command = _wrap_command_with_done_file(
        "true",
        done_file="/files/results/.cmd_done",
        output_log="/files/results/output.log",
    )
    assert command.index(': > "$work/.cmd_exit.$ec"') < command.index(
        'printf \'%s\' "$ec" > "$done_file"'
    )


def test_readiness_queue_backs_off_while_absent(monkeypatch):
    """Absent directories must widen the poll interval, present ones reset it."""
    from nuvolos_cli import grade as grade_mod

    queue = grade_mod._ReadinessQueue()
    key = queue._key("org1", "space1", "stu_1", "dir")
    now = [1000.0]
    monkeypatch.setattr(grade_mod.time, "time", lambda: now[0])

    queue._schedule_next(key, reset=False)
    first = queue._interval[key]
    queue._schedule_next(key, reset=False)
    second = queue._interval[key]
    assert second > first
    assert second <= grade_mod.READINESS_POLL_MAX_INTERVAL

    # Once the directory exists, polling returns to the fast cadence.
    queue._schedule_next(key, reset=True)
    assert queue._interval[key] == grade_mod.READINESS_POLL_MIN_INTERVAL


def test_is_not_found_error_detects_absence_shapes():
    """404 and legacy `item_not_found` payloads both mean "not there yet"."""
    from nuvolos_cli import grade as grade_mod

    class _Status(Exception):
        status = 404
        body = ""

    class _LegacyFiveHundred(Exception):
        status = 500
        body = '{"code": "item_not_found", "debug": "does not exist"}'

    class _RealFailure(Exception):
        status = 500
        body = '{"code": "space_rested"}'

    class _UrlOnlyMatch(Exception):
        status = 500
        body = ""

        def __str__(self):
            return "request failed: /files/item_not_found"

    class _AuthError(Exception):
        status = 403
        body = '{"code": "item_not_found"}'

    assert grade_mod._is_not_found_error(_Status("missing"))
    assert grade_mod._is_not_found_error(_LegacyFiveHundred("boom"))
    assert not grade_mod._is_not_found_error(_RealFailure("boom"))
    assert not grade_mod._is_not_found_error(_UrlOnlyMatch("boom"))
    assert not grade_mod._is_not_found_error(_AuthError("forbidden"))


def test_readiness_queue_shares_listing_with_waiters(monkeypatch):
    from nuvolos_cli import grade as grade_mod

    queue = grade_mod._ReadinessQueue()
    request_started = threading.Event()
    release_request = threading.Event()
    calls = []

    def fake_list_files(**kwargs):
        calls.append(kwargs)
        request_started.set()
        assert release_request.wait(timeout=2)
        return [{"name": "ready-a"}, {"name": "ready-b"}]

    monkeypatch.setattr(grade_mod, "list_files", fake_list_files)
    results = {}

    def wait_for(name):
        results[name] = queue.wait_for(
            org_slug="org1",
            space_slug="space1",
            instance_slug="stu_1",
            dir_rel="work",
            predicate=lambda entries: any(entry["name"] == name for entry in entries),
            timeout_secs=2,
            description=name,
        )

    first = threading.Thread(target=wait_for, args=("ready-a",))
    second = threading.Thread(target=wait_for, args=("ready-b",))
    first.start()
    assert request_started.wait(timeout=2)
    second.start()

    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        with queue._condition:
            if len(queue._waiters.get(("org1", "space1", "stu_1", "work"), {})) == 2:
                break
        threading.Event().wait(0.01)
    else:
        pytest.fail("second waiter did not register")

    release_request.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert results == {"ready-a": True, "ready-b": True}
    assert len(calls) == 1


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


def test_started_app_registry_retries_failed_stop(monkeypatch):
    from nuvolos_cli import grade as grade_mod

    attempts = []

    def fake_stop(**kwargs):
        attempts.append(kwargs["instance_slug"])
        if len(attempts) == 1:
            raise RuntimeError("temporary failure")

    monkeypatch.setattr(grade_mod, "stop_app", fake_stop)
    registry = grade_mod._StartedAppRegistry()
    registry.add("org1", "space1", "stu_a", "bot")

    assert registry.stop_all() == 0
    assert registry.snapshot() == [("org1", "space1", "stu_a", "bot")]
    assert registry.stop_all() == 1
    assert registry.snapshot() == []
    assert attempts == ["stu_a", "stu_a"]


def test_start_app_if_active_does_not_hold_lock_during_start(monkeypatch):
    """Abort must be able to set the event while start_app HTTP is in flight."""
    from nuvolos_cli import grade as grade_mod

    registry = grade_mod._StartedAppRegistry()
    started = threading.Event()
    release_start = threading.Event()
    abort_during_start = threading.Event()

    def fake_start(**kwargs):
        started.set()
        assert release_start.wait(5)
        # Simulate abort landing mid-start.
        assert abort_during_start.wait(5)

    monkeypatch.setattr(grade_mod, "start_app", fake_start)
    monkeypatch.setattr(grade_mod, "stop_app", lambda **kw: None)

    def worker():
        assert registry.start_app_if_active("org1", "space1", "stu_a", "bot") is False

    t = threading.Thread(target=worker)
    t.start()
    assert started.wait(5)
    # Must not block on the worker's start_app call.
    registry.request_abort()
    abort_during_start.set()
    release_start.set()
    t.join(5)
    assert not t.is_alive()
    assert registry.aborted


def test_abort_handlers_ignore_second_signal_and_restore():
    import signal as signal_mod

    from nuvolos_cli import grade as grade_mod

    registry = grade_mod._StartedAppRegistry()
    grade_mod._reset_run_abort_state()
    previous_int = signal_mod.getsignal(signal_mod.SIGINT)
    previous_term = signal_mod.getsignal(signal_mod.SIGTERM)
    previous = grade_mod._install_grade_abort_handlers(registry)
    try:
        handler = signal_mod.getsignal(signal_mod.SIGINT)
        assert callable(handler)
        with pytest.raises(KeyboardInterrupt, match="grade aborted"):
            handler(signal_mod.SIGINT, None)
        assert registry.aborted
        assert grade_mod._run_abort_event.is_set()
        assert signal_mod.getsignal(signal_mod.SIGINT) is signal_mod.SIG_IGN
        assert signal_mod.getsignal(signal_mod.SIGTERM) is signal_mod.SIG_IGN
    finally:
        grade_mod._restore_grade_abort_handlers(previous)
        grade_mod._reset_run_abort_state()
    assert signal_mod.getsignal(signal_mod.SIGINT) == previous_int
    assert signal_mod.getsignal(signal_mod.SIGTERM) == previous_term



def test_test_one_student_stops_app_on_abort(monkeypatch, tmp_path):
    """Ctrl+C mid-wait must still stop the student app (finally + registry)."""
    from nuvolos_cli import grade as grade_mod

    monkeypatch.setattr(grade_mod, "GRADE_QUEUE_ROOT", str(tmp_path))
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
    # No pre-existing workload → the job lock is free.
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


def test_test_one_student_waits_for_busy_app_then_runs(monkeypatch, tmp_path):
    """A workload owned by another job delays the start; it does not skip."""
    from nuvolos_cli import grade as grade_mod

    queue_root = tmp_path / "shared-queue"
    monkeypatch.setattr(grade_mod, "GRADE_QUEUE_ROOT", str(queue_root))
    calls = []
    probes = {"n": 0}

    def fake_workloads(**kwargs):
        # Busy for the first two polls, then the other job finishes.
        probes["n"] += 1
        return [{"status": "RUNNING"}] if probes["n"] <= 2 else []

    monkeypatch.setattr(
        grade_mod, "start_app", lambda **kw: calls.append(("start", kw["instance_slug"]))
    )
    monkeypatch.setattr(
        grade_mod, "stop_app", lambda **kw: calls.append(("stop", kw["instance_slug"]))
    )
    monkeypatch.setattr(grade_mod, "wait_for_app_running", lambda **kw: None)
    monkeypatch.setattr(grade_mod, "list_apps", lambda **kw: [{"slug": "bot"}])
    monkeypatch.setattr(grade_mod, "list_all_running_workloads_for_app", fake_workloads)
    monkeypatch.setattr(grade_mod, "execute_command_in_app", lambda **kw: {})
    monkeypatch.setattr(grade_mod, "_wait_for_execute_completion", lambda **kw: 0)
    monkeypatch.setattr(grade_mod, "_as_files_abs_path", lambda path: str(path))
    monkeypatch.setattr(grade_mod.time, "sleep", lambda _s: None)

    rec = grade_mod.test_one_student(
        org_slug="org1",
        space_slug="space1",
        instance_slug="stu_a",
        app_slug="bot",
        command="python bot.py",
        run_id="run1",
        results_root=str(tmp_path / "results"),
        student_folder="alice@ex.com",
        pull_logs=False,
    )

    assert rec["status"] == "executed"
    assert rec["queued"] is True
    # Waited out the foreign workload instead of starting a second one.
    assert probes["n"] == 3
    assert ("start", "stu_a") in calls
    assert (queue_root / grade_mod.GRADE_QUEUE_DIRNAME).is_dir()
    assert not (tmp_path / "results" / grade_mod.GRADE_QUEUE_DIRNAME).exists()


def test_test_one_student_fails_when_workload_state_is_unknown(
    monkeypatch, tmp_path
):
    from nuvolos_cli import grade as grade_mod

    starts = []

    def fail_lookup(**kwargs):
        raise RuntimeError("lookup failed")

    monkeypatch.setattr(grade_mod, "GRADE_QUEUE_ROOT", str(tmp_path))
    monkeypatch.setattr(grade_mod, "list_apps", lambda **kw: [{"slug": "bot"}])
    monkeypatch.setattr(grade_mod, "list_all_running_workloads_for_app", fail_lookup)
    monkeypatch.setattr(grade_mod, "start_app", lambda **kw: starts.append(True))

    record = grade_mod.test_one_student(
        org_slug="org1",
        space_slug="space1",
        instance_slug="stu_a",
        app_slug="bot",
        command="python bot.py",
        run_id="run1",
        results_root=str(tmp_path / "results"),
        student_folder="alice@ex.com",
        pull_logs=False,
    )

    assert record["status"] == "failed"
    assert "could not determine workload state" in record["error"]
    assert starts == []


def test_file_ticket_heartbeat_covers_workload_wait(monkeypatch, tmp_path):
    from nuvolos_cli import grade as grade_mod

    real_queue_class = grade_mod._FileTicketQueue
    queues = []
    ticket_survived_wait = []

    def make_queue(root):
        queue = real_queue_class(root, stale_after_secs=0.4)
        queues.append(queue)
        return queue

    def fake_workloads(**kwargs):
        threading.Event().wait(0.65)
        queue = queues[0]
        key = ("org1", "space1", "stu_a", "bot")
        ticket_survived_wait.append(
            bool(queue._live_tickets(queue._queue_dir(key)))
        )
        return []

    monkeypatch.setattr(grade_mod, "GRADE_QUEUE_ROOT", str(tmp_path / "queue"))
    monkeypatch.setattr(grade_mod, "_FileTicketQueue", make_queue)
    monkeypatch.setattr(grade_mod, "list_apps", lambda **kw: [{"slug": "bot"}])
    monkeypatch.setattr(grade_mod, "list_all_running_workloads_for_app", fake_workloads)
    monkeypatch.setattr(grade_mod, "start_app", lambda **kw: None)
    monkeypatch.setattr(grade_mod, "stop_app", lambda **kw: None)
    monkeypatch.setattr(grade_mod, "wait_for_app_running", lambda **kw: None)
    monkeypatch.setattr(grade_mod, "execute_command_in_app", lambda **kw: {})
    monkeypatch.setattr(grade_mod, "_wait_for_execute_completion", lambda **kw: 0)
    monkeypatch.setattr(grade_mod, "_as_files_abs_path", lambda path: str(path))

    record = grade_mod.test_one_student(
        org_slug="org1",
        space_slug="space1",
        instance_slug="stu_a",
        app_slug="bot",
        command="python bot.py",
        run_id="run1",
        results_root=str(tmp_path / "results"),
        student_folder="alice@ex.com",
        pull_logs=False,
    )

    assert record["status"] == "executed"
    assert ticket_survived_wait == [True]


def test_test_one_student_queue_timeout_reports_failure(monkeypatch, tmp_path):
    """An app held past --queue-timeout fails that student; never double-starts."""
    from nuvolos_cli import grade as grade_mod

    calls = []
    monkeypatch.setattr(grade_mod, "GRADE_QUEUE_ROOT", str(tmp_path))
    monkeypatch.setattr(
        grade_mod, "start_app", lambda **kw: calls.append("start")
    )
    monkeypatch.setattr(grade_mod, "stop_app", lambda **kw: calls.append("stop"))
    monkeypatch.setattr(grade_mod, "list_apps", lambda **kw: [{"slug": "bot"}])
    monkeypatch.setattr(
        grade_mod,
        "list_all_running_workloads_for_app",
        lambda **kw: [{"status": "RUNNING"}],
    )
    monkeypatch.setattr(grade_mod.time, "sleep", lambda _s: None)

    rec = grade_mod.test_one_student(
        org_slug="org1",
        space_slug="space1",
        instance_slug="stu_a",
        app_slug="bot",
        command="python bot.py",
        run_id="run1",
        results_root=str(tmp_path),
        student_folder="alice@ex.com",
        pull_logs=False,
        queue_timeout_secs=1,
    )

    assert rec["status"] == "failed"
    assert "timed out" in rec["error"]
    assert calls == []


def test_app_job_queue_serializes_in_fifo_order():
    """Second waiter runs only after the holder releases, in arrival order."""
    from nuvolos_cli import grade as grade_mod

    queue = grade_mod._AppJobQueue()
    key = ("org1", "space1", "stu_a", "bot")
    order: list[str] = []
    queued = threading.Event()

    assert queue.acquire(key) is True
    order.append("first-acquired")

    def second():
        queue.acquire(key, on_wait=lambda _ahead: queued.set())
        order.append("second-acquired")
        queue.release(key)

    waiter = threading.Thread(target=second)
    waiter.start()
    try:
        assert queued.wait(timeout=5)
        # Still blocked while the first holder owns the key.
        assert order == ["first-acquired"]
        order.append("first-released")
        queue.release(key)
    finally:
        waiter.join(timeout=5)

    assert order == ["first-acquired", "first-released", "second-acquired"]


def test_app_job_queue_timeout_releases_slot_for_next_waiter():
    """A waiter that times out must not strand the queue head."""
    from nuvolos_cli import grade as grade_mod

    queue = grade_mod._AppJobQueue()
    key = ("org1", "space1", "stu_a", "bot")

    assert queue.acquire(key) is True
    assert queue.acquire(key, timeout_secs=0.1) is False
    queue.release(key)
    assert queue.acquire(key, timeout_secs=0.1) is True
    queue.release(key)


def test_file_ticket_queue_orders_across_processes(tmp_path):
    """Ticket files give cross-process FIFO and self-heal stale entries."""
    from nuvolos_cli import grade as grade_mod

    key = ("org1", "space1", "stu_a", "bot")
    q = grade_mod._FileTicketQueue(tmp_path)

    first = q.take_ticket(key)
    second = q.take_ticket(key)
    assert q.position(key, first) == 0
    assert q.position(key, second) == 1

    q.release(first)
    assert q.position(key, second) == 0

    # A ticket from a crashed CLI is pruned instead of blocking the queue.
    reaper = grade_mod._FileTicketQueue(tmp_path, stale_after_secs=0)
    stale = reaper.take_ticket(key)
    assert reaper.position(key, second) == 0
    assert not stale.exists()
    q.release(second)


def test_file_ticket_queue_allocates_unique_order_under_concurrency(
    tmp_path, monkeypatch
):
    from nuvolos_cli import grade as grade_mod

    key = ("org1", "space1", "stu_a", "bot")
    queue = grade_mod._FileTicketQueue(tmp_path)
    original_live_tickets = queue._live_tickets

    def delayed_live_tickets(queue_dir):
        live = original_live_tickets(queue_dir)
        threading.Event().wait(0.05)
        return live

    monkeypatch.setattr(queue, "_live_tickets", delayed_live_tickets)
    workers = 8
    start = threading.Barrier(workers)

    def take_ticket(_):
        start.wait()
        return queue.take_ticket(key)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        tickets = list(executor.map(take_ticket, range(workers)))

    sequences = sorted(int(ticket.name.split("-", 1)[0]) for ticket in tickets)
    assert sequences == list(range(workers))


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
    monkeypatch.setattr(grade_mod, "GRADE_QUEUE_ROOT", str(tmp_path / "queue"))


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


def test_parallel_abort_stops_started_app_and_skips_late_start(monkeypatch, tmp_path):
    """Scripted pool: started apps are stopped; a worker released after cleanup does not start."""
    from concurrent.futures import CancelledError

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
                        "src": f"/files/assignments-review/handin/{slug}/asg/ts/",
                        "target": str(tmp_path / slug),
                    }
                    for slug in ("stu_a", "stu_b")
                ]
            }
        )
    )

    starts = []
    stops = []
    shutdowns = []

    class _InlineFuture:
        def __init__(self, fn):
            self._fn = fn
            self._done = False
            self._value = None
            self._error = None
            self._cancelled = False

        def cancel(self):
            if self._done:
                return False
            self._cancelled = True
            return True

        def result(self, timeout=None):
            if self._cancelled and not self._done:
                raise CancelledError()
            if not self._done:
                try:
                    self._value = self._fn()
                except BaseException as exc:
                    self._error = exc
                    self._done = True
                    raise
                self._done = True
            if self._error:
                raise self._error
            return self._value

    class _ScriptedPool:
        def __init__(self, max_workers):
            self.max_workers = max_workers
            self.futures = []

        def submit(self, fn, *args, **kwargs):
            fut = _InlineFuture(lambda: fn(*args, **kwargs))
            self.futures.append(fut)
            return fut

        def shutdown(self, wait=True, cancel_futures=False):
            shutdowns.append((wait, cancel_futures))
            if cancel_futures:
                for fut in self.futures:
                    fut.cancel()

    def fake_files_path(path):
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = work / p
        return str(p)

    def fake_wait(**kwargs):
        if kwargs["instance_slug"] == "stu_a":
            raise KeyboardInterrupt("abort after first start")

    monkeypatch.setattr(grade_mod, "_new_grade_pool", _ScriptedPool)
    monkeypatch.setattr(grade_mod, "start_app", lambda **kw: starts.append(kw["instance_slug"]))
    monkeypatch.setattr(grade_mod, "stop_app", lambda **kw: stops.append(kw["instance_slug"]))
    monkeypatch.setattr(grade_mod, "wait_for_app_running", fake_wait)
    monkeypatch.setattr(grade_mod, "list_apps", lambda **kwargs: [{"slug": "bot"}])
    monkeypatch.setattr(
        grade_mod, "list_all_running_workloads_for_app", lambda **kwargs: []
    )
    monkeypatch.setattr(
        grade_mod,
        "list_instances",
        lambda **kwargs: [
            Instance(slug="stu_a", name="a@ex.com"),
            Instance(slug="stu_b", name="b@ex.com"),
        ],
    )
    monkeypatch.setattr(grade_mod, "list_space_members", lambda **kwargs: [])
    monkeypatch.setattr(grade_mod, "_as_files_abs_path", fake_files_path)
    monkeypatch.setattr(grade_mod, "DEFAULT_GRADE_WORK_ROOT", str(work))
    monkeypatch.setattr(grade_mod, "GRADE_QUEUE_ROOT", str(tmp_path / "queue"))

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
            parallel=2,
        )

    assert starts == ["stu_a"]
    assert "stu_a" in stops
    assert "stu_b" not in starts
    assert shutdowns == [(False, True)]
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


def test_late_worker_does_not_start_after_globals_cleared(monkeypatch, tmp_path):
    """Abort cleanup may clear the global pointer; the captured registry still blocks start."""
    from nuvolos_cli import grade as grade_mod

    registry = grade_mod._StartedAppRegistry()
    grade_mod._set_active_registry(registry)
    monkeypatch.setattr(grade_mod, "GRADE_QUEUE_ROOT", str(tmp_path))
    starts = []

    def fake_get_active_registry():
        registry.request_abort()
        grade_mod._set_active_registry(None)
        grade_mod._run_abort_event.clear()
        return registry

    monkeypatch.setattr(grade_mod, "list_apps", lambda **kw: [{"slug": "bot"}])
    monkeypatch.setattr(grade_mod, "_get_active_registry", fake_get_active_registry)
    monkeypatch.setattr(grade_mod, "start_app", lambda **kw: starts.append(kw["instance_slug"]))
    monkeypatch.setattr(grade_mod, "stop_app", lambda **kw: None)

    with pytest.raises(KeyboardInterrupt, match="aborted before starting"):
        grade_mod.test_one_student(
            org_slug="org1",
            space_slug="space1",
            instance_slug="stu_b",
            app_slug="bot",
            command="python bot.py",
            run_id="run1",
            results_root="/files/.nuvolos_grade",
            pull_logs=False,
        )
    assert starts == []
    grade_mod._set_active_registry(None)
    grade_mod._reset_run_abort_state()


def test_resolve_students_filters_instance_and_survives_member_lookup_failure():
    from nuvolos_cli import grade as grade_mod

    manifest = {
        "items": [
            {"src": "/files/assignments-review/handin/stu_a/a/ts/", "target": "/tmp/a"},
            {"src": "/files/assignments-review/handin/stu_b/a/ts/", "target": "/tmp/b"},
        ]
    }
    instances = [
        Instance(slug="stu_a", name="alice@ex.com"),
        Instance(slug="stu_b", name="Not An Email"),
    ]
    with (
        patch("nuvolos_cli.grade.list_instances", return_value=instances),
        patch(
            "nuvolos_cli.grade.list_space_members",
            side_effect=RuntimeError("members down"),
        ),
    ):
        selected = grade_mod.resolve_students(
            manifest, "org1", "space1", instance_filter="stu_a"
        )
    assert [row["instance_slug"] for row in selected] == ["stu_a"]
    assert selected[0]["email"] == "alice@ex.com"
    assert selected[0]["instance_role"] is None


def test_read_manifest_rejects_missing_invalid_and_shapeless(tmp_path):
    from click import ClickException
    from nuvolos_cli import grade as grade_mod

    missing = tmp_path / "nope.json"
    with pytest.raises(ClickException, match="Manifest not found"):
        grade_mod.read_manifest(missing)

    bad = tmp_path / "nvcollect_manifest.json"
    bad.write_text("{")
    with pytest.raises(ClickException, match="Invalid manifest JSON"):
        grade_mod.read_manifest(bad)

    bad.write_text(json.dumps({"meta": {}}))
    with pytest.raises(ClickException, match="items"):
        grade_mod.read_manifest(bad)


def test_grade_check_missing_instance_and_skip_collect_errors(runner, teaching_env, tmp_path):
    manifest_path = tmp_path / "nvcollect_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "src": "/files/assignments-review/handin/missing/asg/ts/",
                        "target": str(tmp_path / "missing"),
                    }
                ]
            }
        )
    )
    with (
        patch("nuvolos_cli.grade.check_api_key_configured", return_value="k"),
        patch("nuvolos_cli.grade.list_spaces", return_value=[_teaching_space()]),
        patch("nuvolos_cli.grade.list_instances", return_value=[]),
        patch("nuvolos_cli.grade.list_space_members", return_value=[]),
        patch("nuvolos_cli.grade._as_files_abs_path", side_effect=lambda path: str(tmp_path / "work")),
    ):
        missing_manifest = runner.invoke(
            nuvolos,
            [
                "grade", "check", "-o", "org1", "-s", "space1", "-a", "bot",
                "-c", "true", "--skip-collect",
            ],
        )
        missing_instance = runner.invoke(
            nuvolos,
            [
                "grade", "check", "-o", "org1", "-s", "space1", "-a", "bot",
                "-c", "true", "--skip-collect", "-m", str(manifest_path),
            ],
        )
    assert missing_manifest.exit_code != 0
    assert "--manifest" in missing_manifest.output
    assert missing_instance.exit_code != 0
    assert "not found" in missing_instance.output


def test_grade_check_failed_student_exits_nonzero(runner, teaching_env, tmp_path):
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

    def fake_files_path(path):
        p = Path(path).expanduser()
        if str(p).startswith("/files"):
            p = tmp_path / "work" / p.name
        p.parent.mkdir(parents=True, exist_ok=True)
        return str(p)

    with (
        patch("nuvolos_cli.grade.check_api_key_configured", return_value="k"),
        patch("nuvolos_cli.grade.list_spaces", return_value=[_teaching_space()]),
        patch("nuvolos_cli.grade.list_instances", return_value=[Instance(slug="stu_a", name="a@ex.com")]),
        patch("nuvolos_cli.grade.list_space_members", return_value=[]),
        patch("nuvolos_cli.grade._as_files_abs_path", side_effect=fake_files_path),
        patch("nuvolos_cli.grade.list_apps", return_value=[]),
        patch("nuvolos_cli.grade.list_all_running_workloads_for_app", return_value=[]),
        patch("nuvolos_cli.grade.start_app") as start,
        patch("nuvolos_cli.grade.handback_collected_results", return_value={"status": "ok"}),
    ):
        result = runner.invoke(
            nuvolos,
            [
                "grade", "check", "-o", "org1", "-s", "space1", "-a", "bot",
                "-c", "true", "--skip-collect", "-m", str(manifest_path),
                "--continue-on-error",
            ],
        )
    assert result.exit_code != 0, result.output
    assert "failure" in result.output
    start.assert_not_called()
