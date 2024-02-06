import os
import json
import click
import click_log

from .logging import clog
from .config import init_cli_config, check_api_key_configured, info
from .api_client import (
    list_orgs,
    list_spaces,
    list_instances,
    list_snapshots,
    list_apps,
    list_all_running_apps,
    start_app,
    stop_app,
    execute_command_in_app,
    list_all_running_workloads_for_app,
    list_nodepools,
)
from .utils import (
    format_response,
    get_effective_snapshot_context,
    get_effective_instance_context,
    get_effective_space_context,
)


@click.group("nuvolos")
@click_log.simple_verbosity_option(clog)
@click.pass_context
def nuvolos(ctx):
    ctx.ensure_object(dict)
    if "NV_CONTEXT" in os.environ:
        ctx.obj = json.loads(os.environ["NV_CONTEXT"])


@nuvolos.command("config")
@click.option(
    "--api-key",
    type=str,
    help="The Nuvolos API key to use for authentication",
    required=True,
)
def nv_cli_config(**kwargs):
    """
    Initializes a new Nuvolos CLI configuration in the current directory.
    """
    init_cli_config(
        api_key=kwargs.get("api_key"),
    )


@nuvolos.group("orgs")
@click.pass_context
def nv_orgs(ctx):
    pass


@nv_orgs.command("list")
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_orgs_list(ctx, **kwargs):
    """
    Lists the Nuvolos organizations available to the current user
    """
    check_api_key_configured()
    res = list_orgs()
    return res


@nuvolos.group("spaces")
@click.pass_context
def nv_spaces(ctx):
    pass


@nv_spaces.command("list")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization to use to list spaces",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_spaces_list(ctx, **kwargs):
    """
    Lists the Nuvolos organizations / spaces / instances / apps available to the current user
    """
    check_api_key_configured()
    space_ctx = get_effective_space_context(ctx, **kwargs)
    return list_spaces(org_slug=space_ctx.get("org_slug"))


@nuvolos.group("instances")
@click.pass_context
def nv_instances(ctx):
    pass


@nv_instances.command("list")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization to use to list instances",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space to use to list instances",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_instances_list(ctx, **kwargs):
    """
    Lists the Nuvolos instances available to the current user
    """
    check_api_key_configured()
    instance_ctx = get_effective_instance_context(ctx, **kwargs)
    return list_instances(
        org_slug=instance_ctx.get("org_slug"), space_slug=instance_ctx.get("space_slug")
    )


@nuvolos.group("snapshots")
@click.pass_context
def nv_snapshots(ctx):
    pass


@nv_snapshots.command("list")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization to use to list snapshots",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space to use to list snapshots",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance to use to list snapshots",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_snapshots_list(ctx, **kwargs):
    """
    Lists the Nuvolos snapshots available to the current user
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
    return list_snapshots(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
    )


@nuvolos.group("apps")
def nv_apps():
    pass


@nv_apps.command("list")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization to use to list applications",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space to use to list applications",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance to use to list applications",
)
@click.option(
    "-p",
    "--snapshot",
    type=str,
    default="development",
    help="The slug of the Nuvolos snapshot to use to list applications",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_apps_list(ctx, **kwargs):
    """
    Lists the Nuvolos applications available to the current user
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
    return list_apps(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
        snapshot_slug=kwargs["snapshot"],
    )


@nv_apps.command("start")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization to use to start an application",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space to use to start an application",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance to use to start an application",
)
@click.argument("app")
@click.option(
    "-n",
    "--node-pool",
    type=str,
    help="The node pool to use to run the app",
)
@click.pass_context
def nv_apps_start(ctx, app, **kwargs):
    """
    Starts the Nuvolos application with the APP application slug
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
    res = start_app(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
        app_slug=app,
        node_pool=kwargs.get("node_pool", None),
    )
    return res


@nv_apps.command("stop")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization to use to stop an application",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space to use to stop an application",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance to use to stop an application",
)
@click.option(
    "-a",
    "--app",
    type=str,
    help="The slug of the Nuvolos application to stop",
    required=True,
)
@click.pass_context
def nv_apps_stop(ctx, **kwargs):
    """
    Stops the Nuvolos application with the given application slug
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
    res = stop_app(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
        app_slug=kwargs.get("app"),
    )

    return res


@nv_apps.command("running")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization to use to list running workloads for an application",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space to use to list running workloads for an application",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance to use to list running workloads for an application",
)
@click.option(
    "-a",
    "--app",
    type=str,
    help="The slug of the Nuvolos application to use to list running an workloads",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_apps_running(ctx, **kwargs):
    """
    Lists all running Nuvolos applications of the user. If the app is specified, lists all running workloads
    for the given application.
    """
    check_api_key_configured()
    app_slug = kwargs.get("app", None)
    if app_slug:
        snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
        res = list_all_running_workloads_for_app(
            org_slug=snapshot_ctx.get("org_slug"),
            space_slug=snapshot_ctx.get("space_slug"),
            instance_slug=snapshot_ctx.get("instance_slug"),
            app_slug=kwargs.get("app"),
        )
    else:
        res = list_all_running_apps()
    return res


@nv_apps.command("execute")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization to use to execute a command in an application",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space to use to execute a command in an application",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance to use to execute a command in an application",
)
@click.option(
    "-a",
    "--app",
    type=str,
    help="The slug of the Nuvolos application where the command is executed",
    required=True,
)
@click.argument("command")
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_apps_execute(ctx, command, **kwargs):
    """
    Executes COMMAND in a Nuvolos application.

    Example: 
    nuvolos apps execute -a my_slug "python -c 'from time import sleep;sleep(10)'"
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
    res = execute_command_in_app(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
        app_slug=kwargs.get("app"),
        command=command,
    )
    return res


@nv_apps.command("nodepools")
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@format_response
def nv_apps_list_nodepools(**kwargs):
    check_api_key_configured()
    res = list_nodepools()

    return res


@nuvolos.command("info")
@click.pass_context
def nv_info(ctx):
    """
    Prints information about the Nuvolos CLI
    """
    info(nuvolos_ctx=ctx.obj)
