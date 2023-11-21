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


@nuvolos.group("orgs")
@click.pass_context
def nv_orgs(ctx):
    pass


@nv_orgs.command("list")
@click.option(
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format",
)
@click.pass_context
@format_response
def nv_orgs_list(ctx, **kwargs):
    """
    Lists the Nuvolos organizations available to the current user
    """
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
    help="The organization to use to list spaces",
)
@click.option(
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format",
)
@click.pass_context
@format_response
def nv_spaces_list(ctx, **kwargs):
    """
    Lists the Nuvolos organizations / spaces / instances / apps available to the current user
    """
    check_api_key_configured()
    if kwargs.get("org") is not None or ctx.obj.get("org_slug"):
        return list_orgs(
            kwargs["org"] if kwargs.get("org") is not None else ctx.obj.get("org_slug"),
        )

    else:
        raise ClickException("Please specify an org slug with the --org argument")


@nuvolos.group("instances")
@click.pass_context
def nv_instances(ctx):
    pass


@nv_instances.command("list")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The organization to use to list instances",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The space to use to list instances",
)
@click.pass_context
@format_response
def nv_instances_list(ctx, **kwargs):
    """
    Lists the Nuvolos instances available to the current user
    """
    check_api_key_configured()
    if kwargs.get("org") is not None or ctx.obj.get("org_slug"):
        if kwargs.get("space") is not None or ctx.obj.get("space_slug"):
            return list_instances(
                kwargs["org"]
                if kwargs.get("org") is not None
                else ctx.obj.get("org_slug"),
                kwargs["space"]
                if kwargs.get("space") is not None
                else ctx.obj.get("space_slug"),
            )
        else:
            raise ClickException(
                "Please specify a space slug with the --space argument"
            )
    else:
        raise ClickException("Please specify an org slug with the --org argument")


@nuvolos.group("snapshots")
@click.pass_context
def nv_snapshots(ctx):
    pass


@nv_snapshots.command("list")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The organization to use to list snapshots",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The space to use to list snapshots",
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
@click.pass_context
@format_response
def nv_snapshots_list(ctx, **kwargs):
    """
    Lists the Nuvolos snapshots available to the current user
    """
    check_api_key_configured()
    if kwargs.get("org") is not None or ctx.obj.get("org_slug"):
        if kwargs.get("space") is not None or ctx.obj.get("space_slug"):
            if kwargs.get("instance") is not None or ctx.obj.get("instance_slug"):
                return list_snapshots(
                    kwargs["org"]
                    if kwargs.get("org") is not None
                    else ctx.obj.get("org_slug"),
                    kwargs["space"]
                    if kwargs.get("space") is not None
                    else ctx.obj.get("space_slug"),
                    kwargs["instance"]
                    if kwargs.get("instance") is not None
                    else ctx.obj.get("instance_slug"),
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
    if kwargs.get("org") is not None or ctx.obj.get("org_slug"):
        if kwargs.get("space") is not None or ctx.obj.get("space_slug"):
            if kwargs.get("instance") is not None or ctx.obj.get("instance_slug"):
                return list_apps(
                    kwargs["org"]
                    if kwargs.get("org") is not None
                    else ctx.obj.get("org_slug"),
                    kwargs["space"]
                    if kwargs.get("space") is not None
                    else ctx.obj.get("space_slug"),
                    kwargs["instance"]
                    if kwargs.get("instance") is not None
                    else ctx.obj.get("instance_slug"),
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
@click.pass_context
def nv_info(ctx):
    """
    Prints information about the Nuvolos CLI
    """
    info(nuvolos_ctx=ctx.obj)
