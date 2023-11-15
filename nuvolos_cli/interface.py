import os
import json
import click
import click_log
from click import ClickException

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
)
from .utils import format_response


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


@nuvolos.command("list")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The organization to use to list spaces",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The space to use to list instances",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The instance to use to list snapshots",
)
@click.option(
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format",
)
@format_response
@click.pass_context
def nv_list(ctx, **kwargs):
    """
    Lists the Nuvolos organizations / spaces / instances / apps available to the current user
    """
    check_api_key_configured()
    if kwargs.get("org", ctx.obj.get("org_slug")):
        if kwargs.get("space", ctx.obj.get("space_slug")):
            if kwargs.get("instance", ctx.obj.get("instance_slug")):
                res = list_snapshots(
                    org_slug=kwargs.get("org", ctx.obj.get("org_slug")),
                    space_slug=kwargs.get("space", ctx.obj.get("space_slug")),
                    instance_slug=kwargs.get("instance", ctx.obj.get("instance_slug")),
                )
            else:
                res = list_instances(
                    org_slug=kwargs.get("org", ctx.obj.get("org_slug")),
                    space_slug=kwargs.get("space", ctx.obj.get("space_slug")),
                )
        else:
            res = list_spaces(org_slug=kwargs.get("org", ctx.obj.get("org_slug")))
    else:
        res = list_orgs()
    return res


@nuvolos.group("apps")
def nv_apps():
    pass


@nv_apps.command("list")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The organization to use to list applications",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The space to use to list applications",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The instance to use to list applications",
)
@click.option(
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format",
)
@click.pass_context
@format_response
def nv_apps_list(ctx, **kwargs):
    """
    Lists the Nuvolos applications available to the current user
    """
    check_api_key_configured()
    if kwargs.get("org", ctx.obj.get("org_slug")):
        if kwargs.get("space", ctx.obj.get("space_slug")):
            if kwargs.get("instance", ctx.obj.get("instance_slug")):
                res = list_apps(
                    kwargs.get("org", ctx.obj.get("org_slug")),
                    kwargs.get("space", ctx.obj.get("space_slug")),
                    kwargs.get("instance", ctx.obj.get("instance_slug")),
                )
            else:
                raise ClickException(
                    "Please specify an instance slug with the --instance argument"
                )
        else:
            raise ClickException(
                "Please specify a space slug with the --space argument"
            )
    else:
        raise ClickException("Please specify an org slug with the --org argument")
    return res


@nv_apps.command("start")
@click.option(
    "-a",
    "--app",
    type=int,
    help="The ID of the application to start",
    required=True,
)
@click.option(
    "-n",
    "--node-pool",
    type=str,
    help="The node pool to use to run the app",
)
def nv_app_start(**kwargs):
    """
    Starts the Nuvolos application with the given ID
    """
    check_api_key_configured()
    res = start_app(
        aid=kwargs.get("app"),
        node_pool=kwargs.get("node_pool"),
    )
    return res


@nv_apps.command("stop")
@click.option(
    "-a",
    "--app",
    type=int,
    help="The ID of the application to start",
    required=True,
)
def nv_stop_app(**kwargs):
    """
    Stops the Nuvolos application with the given ID
    """
    check_api_key_configured()
    res = stop_app(
        aid=kwargs.get("app"),
    )

    return res


@nv_apps.command("running")
@click.option(
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format",
)
@format_response
def nv_stop_app(**kwargs):
    """
    Lists all running Nuvolos applications of the user
    """
    check_api_key_configured()
    res = list_all_running_apps()
    return res


@nuvolos.command("info")
def nv_info():
    """
    Prints information about the Nuvolos CLI
    """
    info()
