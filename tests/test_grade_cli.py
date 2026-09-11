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
        "python run.py --s {instance_slug} --t {target} --i {instance}",
        instance_slug="stu_1",
        target="/files/collected/stu_1",
    )
    assert out == "python run.py --s stu_1 --t /files/collected/stu_1 --i stu_1"


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
