"""Behavioral tests for group-instance and member/invite CLI commands."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from nuvolos_client_api.models.instance_member import InstanceMember
from nuvolos_client_api.models.invitation_summary import InvitationSummary
from nuvolos_client_api.models.space_instance_role import SpaceInstanceRole
from nuvolos_client_api.models.space_invitation_summary import SpaceInvitationSummary
from nuvolos_client_api.models.space_member import SpaceMember
from nuvolos_client_api.models.task import Task
from nuvolos_client_api.rest import ApiException

from nuvolos_cli.api_client import (
    NuvolosCliException,
    create_group_instance,
    invite_instance_member,
    invite_space_member,
    list_instance_members,
    list_space_members,
)
from nuvolos_cli.interface import nuvolos


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def _api_key_ok():
    with patch("nuvolos_cli.interface.check_api_key_configured", return_value="test-key"):
        yield


def test_cli_help_lists_new_commands(runner):
    spaces = runner.invoke(nuvolos, ["spaces", "--help"])
    assert spaces.exit_code == 0
    assert "members" in spaces.output
    assert "invite" in spaces.output

    instances = runner.invoke(nuvolos, ["instances", "--help"])
    assert instances.exit_code == 0
    assert "members" in instances.output
    assert "invite" in instances.output
    assert "create" in instances.output


def test_instances_create_group_requires_editor_email(runner):
    result = runner.invoke(
        nuvolos,
        [
            "instances",
            "create",
            "-o",
            "org",
            "-s",
            "space",
            "-n",
            "Team",
            "--group",
        ],
    )
    assert result.exit_code != 0
    assert "--group requires at least one --editor-email" in result.output


def test_instances_create_editor_email_requires_group(runner):
    result = runner.invoke(
        nuvolos,
        [
            "instances",
            "create",
            "-o",
            "org",
            "-s",
            "space",
            "-n",
            "Team",
            "--editor-email",
            "a@example.com",
        ],
    )
    assert result.exit_code != 0
    assert "--editor-email requires --group" in result.output


def test_instances_create_wait_requires_group(runner):
    result = runner.invoke(
        nuvolos,
        [
            "instances",
            "create",
            "-o",
            "org",
            "-s",
            "space",
            "-n",
            "Solo",
            "--wait",
        ],
    )
    assert result.exit_code != 0
    assert "--wait requires --group" in result.output


def test_instances_create_group_calls_wrapper(runner):
    task = Task(tkid=42, operation="Create group instance")
    with patch(
        "nuvolos_cli.interface.create_group_instance", return_value=task
    ) as create:
        result = runner.invoke(
            nuvolos,
            [
                "instances",
                "create",
                "-o",
                "org1",
                "-s",
                "space1",
                "-n",
                "Team Alpha",
                "--slug",
                "team_alpha",
                "--group",
                "--editor-email",
                "alice@example.com",
                "--editor-email",
                "bob@example.com",
                "-d",
                "shared",
                "-f",
                "json",
            ],
        )
    assert result.exit_code == 0, result.output
    create.assert_called_once_with(
        org_slug="org1",
        space_slug="space1",
        instance_name="Team Alpha",
        instance_slug="team_alpha",
        editor_emails=["alice@example.com", "bob@example.com"],
        instance_description="shared",
    )
    assert '"tkid": 42' in result.output


def test_instances_members_json_output(runner):
    members = [
        InstanceMember(
            name="Alice",
            email="alice@example.com",
            active=True,
            role="EDITOR",
            role_source="instance",
        )
    ]
    with patch(
        "nuvolos_cli.interface.list_instance_members", return_value=members
    ) as listed:
        result = runner.invoke(
            nuvolos,
            [
                "instances",
                "members",
                "-o",
                "org1",
                "-s",
                "space1",
                "-i",
                "inst1",
                "-f",
                "json",
            ],
        )
    assert result.exit_code == 0, result.output
    listed.assert_called_once_with(
        org_slug="org1", space_slug="space1", instance_slug="inst1"
    )
    assert "alice@example.com" in result.output
    assert "EDITOR" in result.output


def test_instances_invite_calls_wrapper(runner):
    summary = InvitationSummary(
        email="student@example.com",
        role="VIEWER",
        status="PENDING",
        validity_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    with patch(
        "nuvolos_cli.interface.invite_instance_member", return_value=summary
    ) as invite:
        result = runner.invoke(
            nuvolos,
            [
                "instances",
                "invite",
                "-o",
                "org1",
                "-s",
                "space1",
                "-i",
                "inst1",
                "--email",
                "student@example.com",
                "--role",
                "viewer",
                "-f",
                "json",
            ],
        )
    assert result.exit_code == 0, result.output
    invite.assert_called_once_with(
        org_slug="org1",
        space_slug="space1",
        instance_slug="inst1",
        email="student@example.com",
        role="VIEWER",
    )
    assert "PENDING" in result.output


def test_spaces_members_json_output(runner):
    members = [
        SpaceMember(
            name="Admin",
            email="admin@example.com",
            active=True,
            space_role="SPACE_ADMIN",
            instance_roles=[
                SpaceInstanceRole(instance_slug="inst1", role="EDITOR")
            ],
        )
    ]
    with patch(
        "nuvolos_cli.interface.list_space_members", return_value=members
    ) as listed:
        result = runner.invoke(
            nuvolos,
            [
                "spaces",
                "members",
                "-o",
                "org1",
                "-s",
                "space1",
                "-f",
                "json",
            ],
        )
    assert result.exit_code == 0, result.output
    listed.assert_called_once_with(org_slug="org1", space_slug="space1")
    assert "SPACE_ADMIN" in result.output
    assert "inst1" in result.output


def test_spaces_invite_defaults_role(runner):
    summary = SpaceInvitationSummary(
        email="admin@example.com",
        role="SPACE_ADMIN",
        status="PENDING",
    )
    with patch(
        "nuvolos_cli.interface.invite_space_member", return_value=summary
    ) as invite:
        result = runner.invoke(
            nuvolos,
            [
                "spaces",
                "invite",
                "-o",
                "org1",
                "-s",
                "space1",
                "--email",
                "admin@example.com",
                "-f",
                "json",
            ],
        )
    assert result.exit_code == 0, result.output
    invite.assert_called_once_with(
        org_slug="org1",
        space_slug="space1",
        email="admin@example.com",
        role="SPACE_ADMIN",
    )


def test_wrapper_converts_api_exception():
    api_exc = ApiException(status=403, reason="Forbidden")
    api_exc.body = '{"code":"forbidden"}'
    api_exc.headers = {}

    class FakeInstancesApi:
        def create_group_instance(self, **kwargs):
            raise api_exc

        def get_instance_members(self, **kwargs):
            raise api_exc

        def invite_instance_member(self, **kwargs):
            raise api_exc

    class FakeSpacesApi:
        def get_space_members(self, **kwargs):
            raise api_exc

        def invite_space_member(self, **kwargs):
            raise api_exc

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with (
        patch("nuvolos_cli.api_client.get_api_config", return_value=object()),
        patch("nuvolos_cli.api_client.nuvolos_client_api.ApiClient", return_value=FakeClient()),
        patch(
            "nuvolos_cli.api_client.nuvolos_client_api.InstancesV1Api",
            return_value=FakeInstancesApi(),
        ),
        patch(
            "nuvolos_cli.api_client.nuvolos_client_api.SpacesV1Api",
            return_value=FakeSpacesApi(),
        ),
    ):
        with pytest.raises(NuvolosCliException) as exc:
            create_group_instance(
                "o",
                "s",
                "n",
                "slug",
                ["a@example.com"],
            )
        assert exc.value.status == 403

        with pytest.raises(NuvolosCliException):
            list_instance_members("o", "s", "i")
        with pytest.raises(NuvolosCliException):
            invite_instance_member("o", "s", "i", "a@example.com", "EDITOR")
        with pytest.raises(NuvolosCliException):
            list_space_members("o", "s")
        with pytest.raises(NuvolosCliException):
            invite_space_member("o", "s", "a@example.com")


def test_wrapper_create_group_instance_passes_model():
    captured = {}

    class FakeInstancesApi:
        def create_group_instance(self, **kwargs):
            captured.update(kwargs)
            return Task(tkid=7, operation="Create group instance")

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with (
        patch("nuvolos_cli.api_client.get_api_config", return_value=object()),
        patch("nuvolos_cli.api_client.nuvolos_client_api.ApiClient", return_value=FakeClient()),
        patch(
            "nuvolos_cli.api_client.nuvolos_client_api.InstancesV1Api",
            return_value=FakeInstancesApi(),
        ),
    ):
        result = create_group_instance(
            org_slug="org",
            space_slug="space",
            instance_name="Team",
            instance_slug="team",
            editor_emails=["a@example.com"],
            instance_description="desc",
        )

    assert result.tkid == 7
    body = captured["group_instance_create_request"]
    assert body.name == "Team"
    assert body.slug == "team"
    assert body.description == "desc"
    assert body.editor_emails == ["a@example.com"]
    assert captured["org_slug"] == "org"
    assert captured["space_slug"] == "space"
