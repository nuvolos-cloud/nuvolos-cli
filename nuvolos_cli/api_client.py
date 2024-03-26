from click import ClickException
from datetime import datetime
from time import sleep

from humanize import naturalsize
from .logging import clog
from .config import get_api_config, from_variable
from .utils import exit_on_timeout

import nuvolos_client_api
from nuvolos_client_api.models import StartApp, ExecuteCommand
from nuvolos_client_api.models.application import Application
from pydantic import StrictStr


def _find_variables(tb, variables):
    to_find = list(variables)
    found = {}
    for var in to_find:
        if var in tb.tb_frame.f_locals:
            variables.remove(var)
            found[var] = tb.tb_frame.f_locals[var]
    if variables and tb.tb_next:
        found.update(_find_variables(tb.tb_next, variables))
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


class HumanizedApplication(Application):
    storage_used: StrictStr

    @classmethod
    def from_application(cls, app: Application):
        return cls(
            slug=app.slug,
            name=app.name,
            description=app.description,
            storage_used=naturalsize(app.storage_used, binary=False),
            shared=app.shared,
            exportable=app.exportable,
            status=app.status,
        )


def list_orgs():
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.OrganizationsV1Api(api_client)
        try:
            return api_instance.get_orgs()
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e, f"Exception when listing Nuvolos organizations: {e}"
            )


def list_spaces(org_slug: str):
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.SpacesV1Api(api_client)
        try:
            return api_instance.get_spaces(slug=org_slug)
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e, f"Exception when listing Nuvolos spaces for org [{org_slug}]: {e}"
            )


def list_instances(org_slug: str, space_slug: str):
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.InstancesV1Api(api_client)
        try:
            return api_instance.get_instances(org_slug=org_slug, space_slug=space_slug)
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e,
                f"Exception when listing Nuvolos instances for org [{org_slug}] and space [{space_slug}]: {e}",
            )


def list_snapshots(org_slug: str, space_slug: str, instance_slug: str):
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.SnapshotsV1Api(api_client)
        try:
            return api_instance.get_snapshots(
                org_slug=org_slug,
                space_slug=space_slug,
                instance_slug=instance_slug,
            )
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e,
                f"Exception when listing Nuvolos snapshots for org [{org_slug}], space [{space_slug}] and instance [{instance_slug}]: {e}",
            )


def list_apps(
    org_slug: str,
    space_slug: str,
    instance_slug: str,
    snapshot_slug: str,
):
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.AppsV1Api(api_client)
        try:
            return [
                HumanizedApplication.from_application(a)
                for a in api_instance.get_apps(
                    org_slug=org_slug,
                    space_slug=space_slug,
                    instance_slug=instance_slug,
                    snapshot_slug=snapshot_slug,
                )
            ]
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e,
                f"Exception when listing Nuvolos apps for org [{org_slug}], space [{space_slug}] and instance [{instance_slug}]: {e}",
            )


def list_all_running_apps():
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.WorkloadsV1Api(api_client)
        try:
            return api_instance.get_workloads()
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e, f"Exception when listing running Nuvolos apps: {e}"
            )


def list_all_running_workloads_for_app(
    org_slug: str, space_slug: str, instance_slug: str, app_slug: str
):
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.WorkloadsV1Api(api_client)
        try:
            return api_instance.get_workloads_for_app(
                org_slug=org_slug,
                space_slug=space_slug,
                instance_slug=instance_slug,
                app_slug=app_slug,
            )
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e,
                f"Exception when listing running workloads for Nuvolos app {app_slug}: {e}",
            )


def start_app(
    org_slug: str,
    space_slug: str,
    instance_slug: str,
    app_slug: str,
    node_pool: str = None,
):
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.WorkloadsV1Api(api_client)
        try:
            if node_pool is not None:
                res = api_instance.create_workload(
                    org_slug=org_slug,
                    space_slug=space_slug,
                    instance_slug=instance_slug,
                    app_slug=app_slug,
                    body=StartApp.from_dict({"node_pool": node_pool}),
                    _headers={"Content-Type": "application/json"},
                )
                clog.info(
                    f"App [{app_slug}] successfully started on node pool [{node_pool}]:\n{res}"
                )
            else:
                res = api_instance.create_workload(
                    org_slug=org_slug,
                    space_slug=space_slug,
                    instance_slug=instance_slug,
                    app_slug=app_slug,
                )
                clog.info(f"App [{app_slug}] successfully started:\n{res}")
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e,
                f"Exception when starting Nuvolos app [{app_slug}]: {e}",
            )


def wait_for_app_running(
    org_slug: str, space_slug: str, instance_slug: str, app_slug: str
):
    running = False
    start = datetime.utcnow()
    stopped_timeout_secs = 30
    starting_timeout_secs = int(from_variable("APP_START_TIMEOUT_SECS", 600))
    while not running:
        workloads = list_all_running_workloads_for_app(
            org_slug=org_slug,
            space_slug=space_slug,
            instance_slug=instance_slug,
            app_slug=app_slug,
        )
        if len(workloads) == 0:
            exit_on_timeout(
                start,
                timeout_secs=stopped_timeout_secs,
                err=f"No workload is available for app [{app_slug}] after {stopped_timeout_secs} seconds",
            )
            sleep(5)
        else:
            if workloads[0].status == "RUNNING":
                running = True
            else:
                exit_on_timeout(
                    start,
                    timeout_secs=starting_timeout_secs,
                    err=f"Application [{app_slug}] is still in STARTING state after {starting_timeout_secs} seconds",
                )
                sleep(5)
    clog.info(f"App [{app_slug}] is successfully started and running.")


def stop_app(org_slug: str, space_slug: str, instance_slug: str, app_slug: str):
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.WorkloadsV1Api(api_client)
        try:
            api_instance.delete_workload(
                org_slug=org_slug,
                space_slug=space_slug,
                instance_slug=instance_slug,
                app_slug=app_slug,
            )
            clog.info(f"App [{app_slug}] successfully stopped")
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e,
                f"Exception when stopping Nuvolos app [{app_slug}]: {e}",
            )


def execute_command_in_app(
    org_slug: str, space_slug: str, instance_slug: str, app_slug: str, command: str
):
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.WorkloadsV1Api(api_client)
        try:
            return api_instance.execute_command(
                org_slug=org_slug,
                space_slug=space_slug,
                instance_slug=instance_slug,
                app_slug=app_slug,
                body=ExecuteCommand.from_dict({"command": command}),
                _headers={"Content-Type": "application/json"},
            )
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e,
                f"Exception when running command {command} in Nuvolos app [{app_slug}]: {e}",
            )


def list_nodepools():
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.WorkloadsV1Api(api_client)
        try:
            return api_instance.get_nodepools()
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e,
                f"Exception when listing nodepools: {e}",
            )
