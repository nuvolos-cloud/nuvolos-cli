import pytest
from click.testing import CliRunner
from nuvolos_cli.interface import (
    nv_cli_config,
    nv_orgs_list,
    nv_spaces_list,
    nv_instances_list,
    nv_apps_list,
    nv_apps_start,
)


def test_nuvolos_cli_config_with_valid_api_key():
    runner = CliRunner()
    result = runner.invoke(nv_cli_config, ["--api-key", "valid_api_key"])
    assert result.exit_code == 0


def test_nuvolos_cli_config_without_api_key():
    runner = CliRunner()
    result = runner.invoke(nv_cli_config)
    assert result.exit_code != 0


def test_nuvolos_orgs_list_with_valid_format():
    runner = CliRunner()
    result = runner.invoke(nv_orgs_list, ["--format", "tabulated"])
    assert result.exit_code == 0


def test_nuvolos_orgs_list_with_invalid_format():
    runner = CliRunner()
    result = runner.invoke(nv_orgs_list, ["--format", "invalid_format"])
    assert result.exit_code != 0


def test_nuvolos_spaces_list_with_valid_org_slug():
    runner = CliRunner()
    result = runner.invoke(nv_spaces_list, ["--org", "valid_org_slug"])
    assert result.exit_code == 0


def test_nuvolos_spaces_list_without_org_slug():
    runner = CliRunner()
    result = runner.invoke(nv_spaces_list)
    assert result.exit_code != 0


def test_nuvolos_instances_list_with_valid_org_and_space_slug():
    runner = CliRunner()
    result = runner.invoke(
        nv_instances_list, ["--org", "valid_org_slug", "--space", "valid_space_slug"]
    )
    assert result.exit_code == 0


def test_nuvolos_instances_list_without_org_slug():
    runner = CliRunner()
    result = runner.invoke(nv_instances_list, ["--space", "valid_space_slug"])
    assert result.exit_code != 0


def test_nuvolos_instances_list_without_space_slug():
    runner = CliRunner()
    result = runner.invoke(nv_instances_list, ["--org", "valid_org_slug"])
    assert result.exit_code != 0


def test_nuvolos_apps_list_with_valid_org_space_and_instance_slug():
    runner = CliRunner()
    result = runner.invoke(
        nv_apps_list,
        [
            "--org",
            "valid_org_slug",
            "--space",
            "valid_space_slug",
            "--instance",
            "valid_instance_slug",
        ],
    )
    assert result.exit_code == 0


def test_nuvolos_apps_list_without_org_slug():
    runner = CliRunner()
    result = runner.invoke(
        nv_apps_list,
        ["--space", "valid_space_slug", "--instance", "valid_instance_slug"],
    )
    assert result.exit_code != 0


def test_nuvolos_apps_list_without_space_slug():
    runner = CliRunner()
    result = runner.invoke(
        nv_apps_list, ["--org", "valid_org_slug", "--instance", "valid_instance_slug"]
    )
    assert result.exit_code != 0


def test_nuvolos_apps_list_without_instance_slug():
    runner = CliRunner()
    result = runner.invoke(
        nv_apps_list, ["--org", "valid_org_slug", "--space", "valid_space_slug"]
    )
    assert result.exit_code != 0


def test_nuvolos_apps_start_with_valid_org_space_instance_and_app_slug():
    runner = CliRunner()
    result = runner.invoke(
        nv_apps_start,
        [
            "--org",
            "valid_org_slug",
            "--space",
            "valid_space_slug",
            "--instance",
            "valid_instance_slug",
            "--app",
            "valid_app_slug",
        ],
    )
    assert result.exit_code == 0


def test_nuvolos_apps_start_without_org_slug():
    runner = CliRunner()
    result = runner.invoke(
        nv_apps_start,
        [
            "--space",
            "valid_space_slug",
            "--instance",
            "valid_instance_slug",
            "--app",
            "valid_app_slug",
        ],
    )
    assert result.exit_code != 0


def test_nuvolos_apps_start_without_space_slug():
    runner = CliRunner()
    result = runner.invoke(
        nv_apps_start,
        [
            "--org",
            "valid_org_slug",
            "--instance",
            "valid_instance_slug",
            "--app",
            "valid_app_slug",
        ],
    )
    assert result.exit_code != 0


def test_nuvolos_apps_start_without_instance_slug():
    runner = CliRunner()
    result = runner.invoke(
        nv_apps_start,
        [
            "--org",
            "valid_org_slug",
            "--space",
            "valid_space_slug",
            "--app",
            "valid_app_slug",
        ],
    )
    assert result.exit_code != 0


def test_nuvolos_apps_start_without_app_slug():
    runner = CliRunner()
    result = runner.invoke(
        nv_apps_start,
        [
            "--org",
            "valid_org_slug",
            "--space",
            "valid_space_slug",
            "--instance",
            "valid_instance_slug",
        ],
    )
    assert result.exit_code != 0


class MyTestCase(unittest.TestCase):
    def test_something(self):
        self.assertEqual(True, False)  # add assertion here


if __name__ == "__main__":
    unittest.main()
