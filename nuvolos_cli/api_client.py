from click import ClickException

from .config import get_api_config

import nuvolos_client_api


def _find_variables(tb, vars):
    """Find the values of variables in a traceback."""
    to_find = list(vars)
    found = {}
    for var in to_find:
        if var in tb.tb_frame.f_locals:
            vars.remove(var)
            found[var] = tb.tb_frame.f_locals[var]
    if vars and tb.tb_next:
        found.update(_find_variables(tb.tb_next, vars))
    return found


class NuvolosCliException(ClickException):
    def __init__(self, status, reason, body, headers, url=""):
        self.status = status
        self.reason = reason
        self.body = body
        self.headers = headers
        self.url = url
        self.message = (
            f"Nuvolos API Exception:\nURL:{url}\nHTTP {status}: {reason}\nBody: {body}"
        )
        super().__init__(self.message)

    @classmethod
    def from_api_exception(cls, e: nuvolos_client_api.ApiException, message=None):
        url = _find_variables(e.__traceback__, ["url"]).get("url", "")
        return cls(e.status, e.reason, e.body, e.headers, url)


def list_orgs():
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.OrganizationsV1Api(api_client)
        try:
            return api_instance.orgs_v1_get()
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e, f"Exception when listing Nuvolos organizations: {e}"
            )


def list_spaces(org_slug: str):
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.SpacesV1Api(api_client)
        try:
            return api_instance.spaces_v1_org_slug_get(slug=org_slug)
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e, f"Exception when listing Nuvolos spaces for org [{org_slug}]: {e}"
            )


def list_instances(org_slug: str, space_slug: str):
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.InstancesV1Api(api_client)
        try:
            return api_instance.instances_v1_org_org_slug_space_space_slug_get(
                org_slug=org_slug, space_slug=space_slug
            )
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e,
                f"Exception when listing Nuvolos instances for org [{org_slug}] and space [{space_slug}]: {e}",
            )


def list_snapshots(org_slug: str, space_slug: str, instance_slug: str):
    pass


def list_apps(org_slug: str, space_slug: str, instance_slug: str):
    pass


def list_all_running_apps():
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.WorkloadsV1Api(api_client)
        try:
            return api_instance.workloads_v1_get()
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e, f"Exception when listing running Nuvolos apps: {e}"
            )
