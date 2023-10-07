from nuvolos_client_api.models.org_client_api import OrgClientAPI
from .logging import clog
from .exception import NuvolosException
from .config import get_api_config

import nuvolos_client_api
from nuvolos_client_api.models.org_client_api import OrgClientAPI
from nuvolos_client_api.models.org_space_limitied import OrgSpaceLimitied
from nuvolos_client_api.rest import ApiException
from .logging import clog
from .exception import NuvolosException


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
            api_instance = nuvolos_client_api.OrganizationsApi(api_client)
            try:
                self._current_org = api_instance.orgs_v1_org_slug_get(slug)
                self._current_space = None
                self._current_instance = None
                self._current_snapshot = None
            except ApiException as e:
                raise NuvolosException(
                    f"Exception when setting current organization by slug [{slug}]: {e}"
                )
        clog.debug(f"Current org set to [{self._current_org.slug}]")

    def set_current_org(self, org: OrgClientAPI):
        if org:
            self._current_org = org
            clog.debug(f"Current org set to [{org.slug}]")
        else:
            raise NuvolosException("No current organization provided.")

    def get_current_org(self):
        return self._current_org

    def set_current_space(self, space: OrgSpaceLimitied):
        if not self._current_org:
            raise NuvolosException(
                "Current Nuvolos organization not set, please choose an organization first."
            )
        if not space:
            raise NuvolosException("No current space provided.")
        if space.oid != self._current_org.oid:
            raise NuvolosException(
                f"Space [{space.slug}] does not belong to current organization [{self._current_org.slug}]."
            )
        self._current_space = space
        self._current_instance = None
        self._current_snapshot = None
        clog.debug(f"Current space set to [{space.slug}]")
