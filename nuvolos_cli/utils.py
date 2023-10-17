import click
from functools import wraps
from pydantic import BaseModel
from tabulate import tabulate
import yaml

from .exception import NuvolosException


def print_model_tabulated(model: BaseModel, tablefmt="github"):
    click.echo(tabulate(model.dict(), tablefmt=tablefmt, headers="keys"))


def print_models_tabulated(models: [BaseModel], tablefmt="github"):
    click.echo(tabulate([m.dict() for m in models], tablefmt=tablefmt, headers="keys"))


def print_models_json(models: [BaseModel]):
    click.echo([m.json() for m in models])


def print_models_yaml(models: [BaseModel]):
    list_of_dicts = [m.dict() for m in models]
    click.echo(yaml.dump_all(list_of_dicts, sort_keys=True))


def format_response(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        res = f(*args, **kwargs)
        format_ = kwargs.get("format")
        if format_ == "tabulated":
            return print_models_tabulated(res)
        elif format_ == "json":
            return print_models_json(res)
        elif format_ == "yaml":
            return print_models_yaml(res)
        else:
            raise NuvolosException(f"{format_} is not a valid format option")

    return wrapper
