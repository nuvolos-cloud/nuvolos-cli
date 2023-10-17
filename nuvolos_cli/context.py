from click import ClickException

from .api_client import NuvolosCliException
from .config import get_api_config
from .logging import clog

import nuvolos_client_api
from nuvolos_client_api.models.org import Org
from nuvolos_client_api.models.space import Space
from nuvolos_client_api.rest import ApiException


class NuvolosContext:
    _instance = None
    _current_org = None
    _current_space = None
    _current_instance = None
    _current_snapshot = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def set_current_org_slug(self, slug: str):
        config = get_api_config()
        with nuvolos_client_api.ApiClient(config) as api_client:
            api_instance = nuvolos_client_api.OrganizationsV1Api(api_client)
            try:
                self._current_org = api_instance.orgs_v1_org_slug_get(slug)
                self._current_space = None
                self._current_instance = None
                self._current_snapshot = None
            except ApiException as e:
                raise NuvolosCliException.from_api_exception(
                    e,
                    f"Exception when setting current organization by slug [{slug}]: {e}",
                )
        clog.debug(f"Current org set to [{self._current_org.slug}]")

    def set_current_org(self, org: Org):
        if org:
            self._current_org = org
            clog.debug(f"Current org set to [{org.slug}]")
        else:
            raise ClickException("No current organization provided.")

    def get_current_org(self):
        return self._current_org

    def set_current_space(self, space: Space):
        if not self._current_org:
            raise ClickException(
                "Current Nuvolos organization not set, please choose an organization first."
            )
        if not space:
            raise ClickException("No current space provided.")
        if space.oid != self._current_org.oid:
            raise ClickException(
                f"Space [{space.slug}] does not belong to current organization [{self._current_org.slug}]."
            )
        self._current_space = space
        self._current_instance = None
        self._current_snapshot = None
        clog.debug(f"Current space set to [{space.slug}]")
