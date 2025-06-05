import os
import yaml
import pathlib

from click import ClickException

from .logging import clog
from .utils import mask_api_key_in_config
from .version import __version__

import nuvolos_client_api


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
    if not val:
        if pathlib.Path(f"/secrets/{variable_name}").exists():
            with pathlib.Path(f"/secrets/{variable_name}").open(mode="r") as f:
                val = f.read()
    return val


def default_global_configs():
    return {
        "nuvolos_cli_version": __version__,
        "api_key": from_variable("NUVOLOS_API_KEY"),
        "host": from_variable("NUVOLOS_API_HOST", "https://api.nuvolos.cloud"),
    }


def get_global_dict_config():
    return DictConfig(get_default_config_path(), default_global_configs)


def get_config():
    if not get_default_config_path().exists():
        return default_global_configs()
    else:
        dc = get_global_dict_config().read()
        api_key = from_variable("NUVOLOS_API_KEY")
        if api_key:
            # Prioritize the environment variable
            dc["api_key"] = api_key
        host = from_variable("NUVOLOS_API_HOST")
        if host:
            dc["host"] = host

        if dc["api_key"] is None:
            raise ClickException(
                "Nuvolos CLI is not configured, please set your API key with `nuvolos config --api-key`."
            )
        return dc


def get_api_config():
    config = get_config()
    return nuvolos_client_api.Configuration(
        host=config["host"],
        api_key={"ApiKeyAuth": config["api_key"]},
        api_key_prefix={"ApiKeyAuth": "basic"},
        debug=os.getenv("NUVOLOS_CLI_DEBUG", "false").lower() in ("true", "1", "yes"),
    )


def init_cli_config(
    api_key: str = None,
):
    if not get_default_config_path().exists():
        gdc = get_global_dict_config()
        global_settings = gdc.read()
        global_settings["nuvolos_cli_version"] = __version__
        global_settings["api_key"] = api_key
        gdc.write(global_settings)
        clog.info(f"Nuvolos CLI global configuration written to [{gdc.path}].")


def check_api_key_configured():
    api_key = from_variable("NUVOLOS_API_KEY")
    if api_key is None:
        if not get_default_config_path().exists():
            raise ClickException(
                "The Nuvolos API key must be set either as the NUVOLOS_API_KEY environment variable or with the `nuvolos config --api-key` command."
            )
        gdc = get_global_dict_config().read()
        api_key = gdc["api_key"]
        if api_key is None:
            raise ClickException(
                "The Nuvolos API key must be set either as the NUVOLOS_API_KEY environment variable or with the `nuvolos config --api-key` command."
            )
    return api_key


def info(nuvolos_ctx=None):
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
    gc = mask_api_key_in_config(get_config())
    if nuvolos_ctx:
        clog.info(
            f"""\nThe Nuvolos CLI context:
Organization slug:\t{nuvolos_ctx['org_slug']}
Space slug:\t\t{nuvolos_ctx['space_slug']}
Instance slug:\t\t{nuvolos_ctx['instance_slug']}"""
        )
    clog.info(
        f"\nThe Nuvolos CLI config ({get_default_config_path() if get_default_config_path().exists() else ''}):\n{yaml.dump(gc)}"
    )
