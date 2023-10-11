import os
import yaml
import pathlib

from .version import __version__
from .logging import clog

from .exception import (
    NuvolosException,
)
from .version import __version__

import nuvolos_client_api


def get_local_config_path():
    return pathlib.Path.cwd() / ".nuvolos" / "config.yaml"


def get_default_config_path():
    return pathlib.Path.home() / ".nuvolos" / "config.yaml"


class DictConfig(object):
    def __init__(self, path, default_generator=None):
        self.path = pathlib.Path(path)
        self.default_generator = default_generator

    def read(self):
        if not self.path.exists():
            if self.default_generator:
                self.write(self.default_generator())
        with self.path.open(mode="r") as f:
            d = yaml.safe_load(f)
            return d

    def write(self, d):
        if not self.path.parent.exists():
            pathlib.Path.mkdir(self.path.parent, parents=True)
        with self.path.open(mode="w") as f:
            return yaml.dump(d, f)


def from_variable(variable_name, default=None):
    val = os.environ.get(variable_name, default=default)
    if not host:
        if pathlib.Path(f"/secrets/{variable_name}").exists():
            with pathlib.Path(f"/secrets/{variable_name}").open(mode="r") as f:
                val = f.read()
    return val


def default_global_configs():
    return {
        "app_name": "nuvolos-cli",
        "nuvolos_cli_version": __version__,
        "api_key": from_variable("NUVOLOS_API_KEY"),
        "host": from_variable("NUVOLOS_API_HOST", "https://az-api.nuvolos.cloud")
    }


def get_global_dict_config():
    return DictConfig(get_default_config_path(), default_global_configs)


def get_local_dict_config():
    return DictConfig(
        pathlib.Path.cwd() / ".nuvolos" / "config.yaml", default_global_configs
    )


def get_config_path():
    if get_local_config_path().exists():
        return get_local_config_path()
    elif get_default_config_path().exists():
        return get_default_config_path()
    else:
        raise NuvolosException(
            "Nuvolos CLI is not configured, please set your API key with `nuvolos config --api-key`."
        )


def get_config():
    return get_local_dict_config()


def get_api_config():
    dc = get_config()
    config = dc.read()
    return nuvolos_client_api.Configuration(
        host=config["host"],
        api_key={"ApiKeyAuth": config["api_key"]},
        api_key_prefix={"ApiKeyAuth": "basic"},
    )


def init_cli_config(
    api_key: str = None,
):
    pdc = get_local_dict_config()
    project_settings = pdc.read()
    project_settings["nuvolos_cli_version"] = __version__
    project_settings["api_key"] = api_key
    pdc.write(project_settings)
    clog.info(f"Nuvolos CLI configuration written to [{pdc.path}].")

    if not get_default_config_path().exists():
        gdc = get_global_dict_config()
        global_settings = gdc.read()
        global_settings["nuvolos_cli_version"] = __version__
        global_settings["api_key"] = api_key
        gdc.write(global_settings)
        clog.info(f"Nuvolos CLI global configuration written to [{gdc.path}].")


def check_api_key_configured():
    api_key = os.environ.get("NUVOLOS_API_KEY")
    if api_key is None:
        gdc = get_global_dict_config()
        global_config = gdc.read()
        api_key = global_config.get("api_key")
        if api_key is None:
            ldc = get_local_dict_config()
            local_config = ldc.read()
            api_key = local_config.get("api_key")
            if api_key is None:
                raise NuvolosException(
                    "The Nuvolos API key must be set either as the NUVOLOS_API_KEY environment variable or with the `nuvolos configure --api-key` command."
                )
    return api_key


def info():
    clog.info(
        r"""
 _   _                  _              ____ _     ___ 
| \ | |_   ___   _____ | | ___  ___   / ___| |   |_ _|
|  \| | | | \ \ / / _ \| |/ _ \/ __| | |   | |    | | 
| |\  | |_| |\ V / (_) | | (_) \__ \ | |___| |___ | | 
|_| \_|\__,_| \_/ \___/|_|\___/|___/  \____|_____|___|
                                                      
"""
    )
    clog.info(f"Version: {__version__}")
    gc = get_config().read()
    clog.info(f"The Nuvolos CLI config ({get_config_path()}):\n{yaml.dump(gc)}")
