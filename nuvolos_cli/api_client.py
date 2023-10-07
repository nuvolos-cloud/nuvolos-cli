from .config import get_api_config
from .context import NuvolosContext
from .exception import NuvolosException

import nuvolos_client_api


def list(ctx: NuvolosContext):
    if ctx.current_org is None:
        pass


def list_orgs():
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.OrganizationsApi(api_client)
        try:
            return api_instance.orgs_v1_get()
        except nuvolos_client_api.ApiException as e:
            raise NuvolosException(f"Exception when listing Nuvolos organizations: {e}")


def list_spaces(org_slug: str):
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.SpacesApi(api_client)
        try:
            return api_instance.spaces_v1_org_slug_get(slug=org_slug)
        except nuvolos_client_api.ApiException as e:
            raise NuvolosException(
                f"Exception when listing Nuvolos spaces for org [{org_slug}]: {e}"
            )


def list_instances(org_slug: str, space_slug: str):
    pass


def list_snapshots(org_slug: str, space_slug: str, instance_slug: str):
    pass


def list_apps(org_slug: str, space_slug: str, instance_slug: str):
    pass


def list_all_running_apps():
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.WorkloadsApi(api_client)
        try:
            return api_instance.workloads_v1_get()
        except nuvolos_client_api.ApiException as e:
            raise NuvolosException(f"Exception when listing running Nuvolos apps: {e}")
