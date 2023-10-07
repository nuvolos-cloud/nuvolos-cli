import click
import click_log
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
)
from .utils import print_model, print_models
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
@click.pass_context
def nv_list(ctx, **kwargs):
    """
    Lists the Nuvolos organizations / spaces / instances / apps available to the current user
    """
    check_api_key_configured()
    if kwargs.get("org"):
        if kwargs.get("space"):
            if kwargs.get("instance"):
                print_model(
                    list_snapshots(
                        kwargs.get("org"),
                        kwargs.get("space"),
                        kwargs.get("instance"),
                        kwargs.get("snapshot"),
                    )
                )
            else:
                print_models(list_instances(kwargs.get("org"), kwargs.get("space")))
        else:
            print_models(list_spaces(kwargs.get("org")))
    else:
        print_models(list_orgs())


@nuvolos.command("apps")
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
@click.pass_context
def nv_apps(ctx, **kwargs):
    """
    Lists the Nuvolos applications available to the current user
    """
    check_api_key_configured()
    if kwargs.get("org"):
        if kwargs.get("space"):
            if kwargs.get("instance"):
                print_models(
                    list_apps(
                        kwargs.get("org"),
                        kwargs.get("space"),
                        kwargs.get("instance"),
                    )
                )
            else:
                print_models(list_apps(kwargs.get("org"), kwargs.get("space")))
        else:
            print_models(list_apps(kwargs.get("org")))
    else:
        print_models(list_all_running_apps())


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
