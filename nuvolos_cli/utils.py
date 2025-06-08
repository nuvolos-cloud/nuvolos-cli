import click
from click import ClickException
from datetime import datetime, timedelta
from copy import deepcopy
from functools import wraps
from pydantic import BaseModel
from tabulate import tabulate
from typing import List
import yaml

from .logging import clog


def print_model_tabulated(model: BaseModel, tablefmt="github"):
    click.echo(tabulate(model.dict(), tablefmt=tablefmt, headers="keys"))


def print_models_tabulated(models: List[BaseModel], tablefmt="github"):
    click.echo(tabulate([m.dict() for m in models], tablefmt=tablefmt, headers="keys"))


def print_models_json(models: List[BaseModel]):
    click.echo([m.json() for m in models])


def print_models_yaml(models: List[BaseModel]):
    list_of_dicts = [m.dict() for m in models]
    click.echo(yaml.dump_all(list_of_dicts, sort_keys=True))


def format_response(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        res = f(*args, **kwargs)
        if not isinstance(res, list):
            res = [res]
        format_ = kwargs.get("format")
        if format_ == "tabulated":
            return print_models_tabulated(res)
        elif format_ == "json":
            return print_models_json(res)
        elif format_ == "yaml":
            return print_models_yaml(res)
        else:
            raise click.ClickException(f"{format_} is not a valid format option")

    return wrapper


def get_effective_space_context(ctx, **kwargs):
    org_slug = kwargs.get("org", None)

    ret_ctx = deepcopy(ctx.obj)
    if org_slug:
        ret_ctx["org_slug"] = org_slug
    else:
        if not ret_ctx:
            raise ClickException("Please specify an org slug with the --org argument")

    ret_ctx = filter_context_dict(ret_ctx, ["org_slug"])
    clog.debug(f"Running with context: {ret_ctx}")
    return ret_ctx


def get_effective_instance_context(ctx, **kwargs):
    org_slug = kwargs.get("org", None)
    space_slug = kwargs.get("space", None)

    ret_ctx = deepcopy(ctx.obj)
    if org_slug:
        if not space_slug:
            raise ClickException(
                "Please specify a space slug with the --space argument"
            )
        else:
            ret_ctx["org_slug"] = org_slug
            ret_ctx["space_slug"] = space_slug
    elif space_slug:
        ret_ctx["space_slug"] = space_slug
    else:
        if not ret_ctx:
            raise ClickException(
                "Missing instance context. Please specify the context with the --org, --space arguments"
            )
    ret_ctx = filter_context_dict(ret_ctx, ["org_slug", "space_slug"])
    clog.debug(f"Running with context: {ret_ctx}")
    return ret_ctx


def get_effective_snapshot_context(ctx, **kwargs):
    org_slug = kwargs.get("org", None)
    space_slug = kwargs.get("space", None)
    instance_slug = kwargs.get("instance", None)

    ret_ctx = deepcopy(ctx.obj) if ctx.obj is not None else {}

    if org_slug:
        if not space_slug:
            raise ClickException(
                "Please specify a space slug with the --space argument"
            )
        elif not instance_slug:
            raise ClickException(
                "Please specify a instance slug with the --instance argument"
            )
        else:
            ret_ctx["org_slug"] = org_slug
            ret_ctx["space_slug"] = space_slug
            ret_ctx["instance_slug"] = instance_slug
    elif space_slug:
        if not instance_slug:
            raise ClickException(
                "Please specify a instance slug with the --instance argument"
            )
        else:
            ret_ctx["space_slug"] = space_slug
            ret_ctx["instance_slug"] = instance_slug
    elif instance_slug:
        ret_ctx["instance_slug"] = instance_slug
    else:
        if not ret_ctx:
            raise ClickException(
                "Missing application context. Please specify the context with the --org, --space, --instance arguments"
            )

    clog.debug(f"Running with context: {ret_ctx}")
    return ret_ctx


def filter_context_dict(d: dict, keep=[]):
    return {arg: value for arg, value in d.items() if arg in keep}


def mask_string(string: str, show: int = 4):
    return (len(string) - show) * "*" + string[-show:]


def mask_api_key_in_config(config: dict):
    if config.get("api_key"):
        config["api_key"] = mask_string(config["api_key"])
    return config


def exit_on_timeout(start_time: datetime, timeout_secs: int, err: str):
    difftime = datetime.utcnow() - start_time
    if difftime > timedelta(seconds=timeout_secs):
        raise ClickException(err)
