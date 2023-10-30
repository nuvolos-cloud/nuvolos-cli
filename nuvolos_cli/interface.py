import click
import click_log
from click import ClickException

from .logging import clog
from .context import NuvolosContext
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
from .cli import NuvolosCli


@click.group("nuvolos")
@click_log.simple_verbosity_option(clog)
@click.pass_context
def nuvolos(ctx):
    """
    Nuvolos CLI is a command line interface for the Nuvolos platform.
    """
    if ctx.obj is None:
        ctx.obj = NuvolosContext()


@nuvolos.command("config")
@click.option(
    "--api-key",
    type=str,
    help="The Nuvolos API key to use for authentication",
)
@click.pass_context
def nv_cli_config(ctx, **kwargs):
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
def nv_list(**kwargs):
    """
    Lists the Nuvolos organizations / spaces / instances / apps available to the current user
    """
    check_api_key_configured()
    if kwargs.get("org"):
        if kwargs.get("space"):
            if kwargs.get("instance"):
                res = list_snapshots(
                    org_slug=kwargs.get("org"),
                    space_slug=kwargs.get("space"),
                    instance_slug=kwargs.get("instance"),
                )
            else:
                res = list_instances(
                    org_slug=kwargs.get("org"), space_slug=kwargs.get("space")
                )
        else:
            res = list_spaces(org_slug=kwargs.get("org"))
    else:
        res = list_orgs()
    return res


@nuvolos.group("apps")
@click.pass_context
def nv_apps(ctx, **kwargs):
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
@format_response
def nv_apps_list(**kwargs):
    """
    Lists the Nuvolos applications available to the current user
    """
    check_api_key_configured()
    if kwargs.get("org"):
        if kwargs.get("space"):
            if kwargs.get("instance"):
                res = list_apps(
                    kwargs.get("org"),
                    kwargs.get("space"),
                    kwargs.get("instance"),
                )
            else:
                raise ClickException(
                    "Please specify an instance slug with the --instance parameter"
                )
        else:
            raise ClickException(
                "Please specify a space slug with the --space parameter"
            )
    else:
        res = list_all_running_apps()

    return res


@nv_apps.command("start")
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
    "-a",
    "--app",
    type=int,
    help="The ID of the application to start",
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
    if kwargs.get("org"):
        if kwargs.get("space"):
            if kwargs.get("instance"):
                if kwargs.get("app"):
                    res = start_app(
                        kwargs.get("org"),
                        kwargs.get("space"),
                        kwargs.get("instance"),
                        kwargs.get("app"),
                        kwargs.get("node_pool"),
                    )
                else:
                    raise ClickException(
                        "Please specify an application ID with the --app parameter"
                    )
            else:
                raise ClickException(
                    "Please specify an instance slug with the --instance parameter"
                )
        else:
            raise ClickException(
                "Please specify a space slug with the --space parameter"
            )
    else:
        raise ClickException(
            "Please specify an organization slug with the --org parameter"
        )

    return res


@nv_apps.command("stop")
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
    "-a",
    "--app",
    type=int,
    help="The ID of the application to start",
)
def nv_stop_app(**kwargs):
    """
    Stops the Nuvolos application with the given ID
    """
    check_api_key_configured()
    if kwargs.get("org"):
        if kwargs.get("space"):
            if kwargs.get("instance"):
                if kwargs.get("app"):
                    res = stop_app(
                        kwargs.get("org"),
                        kwargs.get("space"),
                        kwargs.get("instance"),
                        kwargs.get("app"),
                    )
                else:
                    raise ClickException(
                        "Please specify an application ID with the --app parameter"
                    )
            else:
                raise ClickException(
                    "Please specify an instance slug with the --instance parameter"
                )
        else:
            raise ClickException(
                "Please specify a space slug with the --space parameter"
            )
    else:
        raise ClickException(
            "Please specify an organization slug with the --org parameter"
        )

    return res


@nuvolos.command("info")
def nv_info():
    """
    Prints information about the Nuvolos CLI
    """
    info()


@nuvolos.command("cli")
def nv_cli():
    """
    Enters the interactive Nuvolos CLI REPL
    """
    NuvolosCli().cmdloop()
