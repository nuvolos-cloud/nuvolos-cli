from click import ClickException
from datetime import datetime
import json
from time import sleep

from humanize import naturalsize
from slugify import slugify
from .logging import clog
from .config import get_api_config, from_variable
from .utils import exit_on_timeout

import nuvolos_client_api
from nuvolos_client_api.models import (
    StartApp,
    ExecuteCommand,
    Task1,
    AppCreate,
    DeriveApp,
    ImageCreate,
    ImageFamilyCreate,
    ImageUpdate,
    InstanceCreateRequest,
)
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
            aoid=app.aoid,
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


def create_snapshot(
    org_slug: str,
    space_slug: str,
    instance_slug: str,
    snapshot_name: str,
    snapshot_description: str = None,
    email_once_finished: bool = False,
):
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.InstancesV1Api(api_client)
        try:
            return api_instance.create_snapshot(
                org_slug=org_slug,
                space_slug=space_slug,
                instance_slug=instance_slug,
                body=nuvolos_client_api.SnapshotCreateRequest.from_dict(
                    {
                        "name": snapshot_name,
                        "slug": slugify(snapshot_name, separator="_"),
                        "description": snapshot_description,
                        "email_once_finished": email_once_finished,
                    }
                ),
                _headers={"Content-Type": "application/json"},
            )
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e,
                f"Exception when creating Nuvolos snapshot for org [{org_slug}], space [{space_slug}] and instance [{instance_slug}]: {e}",
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


def delete_snapshot(
    org_slug: str, space_slug: str, instance_slug: str, snapshot_slug: str
):
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.SnapshotsV1Api(api_client)
        try:
            return api_instance.delete_snapshot(
                org_slug=org_slug,
                space_slug=space_slug,
                instance_slug=instance_slug,
                snapshot_slug=snapshot_slug,
            )
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e,
                f"Exception when deleting Nuvolos snapshot [{snapshot_slug}] for org [{org_slug}], space [{space_slug}] and instance [{instance_slug}]: {e}",
            )


def get_task(tkid: int) -> Task1:
    """
    Retrieves the status and details of a specific task by its ID.

    Args:
        tkid: The ID of the task to retrieve

    Returns:
        The task object with status information
    """
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.TasksV1Api(api_client)
        try:
            return api_instance.get_task(tkid=tkid)
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e, f"Exception when getting task status for task [{tkid}]: {e}"
            )


def wait_for_task(tkid: int, timeout_secs: int = None):
    """
    Waits for a task to complete, periodically checking its status.

    Args:
        tkid: The ID of the task to wait for
        timeout_secs: Maximum time to wait in seconds before timing out (defaults to APP_TASK_TIMEOUT_SECS or 600)

    Returns:
        The completed task object
    """
    if timeout_secs is None:
        timeout_secs = int(from_variable("APP_TASK_TIMEOUT_SECS", 600))

    start = datetime.utcnow()
    task = get_task(tkid)

    # Use status rather than numeric codes
    while task.status in ["CREATED", "QUEUED", "RUNNING"]:
        exit_on_timeout(
            start,
            timeout_secs=timeout_secs,
            err=f"Task [{tkid}] is still in progress (status={task.status}) after {timeout_secs} seconds",
        )
        sleep(5)
        task = get_task(tkid)

    if task.status == "COMPLETED":
        clog.info(f"Task [{tkid}] completed successfully")
        return task
    elif task.status == "FAILED":
        error_msg = f"Task [{tkid}] failed with error: {task.error}"
        clog.error(error_msg)
        raise NuvolosCliException(500, "Task failed", error_msg, {}, "")
    elif task.status == "CANCELLED":
        error_msg = f"Task [{tkid}] was cancelled"
        clog.error(error_msg)
        raise NuvolosCliException(500, "Task cancelled", error_msg, {}, "")
    else:
        error_msg = f"Task [{tkid}] ended with unexpected status: {task.status}"
        clog.error(error_msg)
        raise NuvolosCliException(500, "Unexpected task status", error_msg, {}, "")


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


def create_instance(
    org_slug: str,
    space_slug: str,
    instance_name: str,
    instance_slug: str,
    instance_description: str = None,
):
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.InstancesV1Api(api_client)
        try:
            return api_instance.create_instance(
                org_slug=org_slug,
                space_slug=space_slug,
                instance_create_request=InstanceCreateRequest.from_dict(
                    {
                        "name": instance_name,
                        "slug": instance_slug,
                        "description": instance_description,
                    }
                ),
                _headers={"Content-Type": "application/json"},
            )
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e,
                f"Exception when creating instance [{instance_name}] in org [{org_slug}], space [{space_slug}]: {e}",
            )


def create_app(
    org_slug: str,
    space_slug: str,
    instance_slug: str,
    imid: int,
    long_id: str,
    description: str = None,
    pars: str = None,
):
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.AppsV1Api(api_client)
        body = {"imid": imid, "long_id": long_id}
        if description is not None:
            body["description"] = description
        if pars is not None:
            body["pars"] = pars
        try:
            return api_instance.create_app(
                org_slug=org_slug,
                space_slug=space_slug,
                instance_slug=instance_slug,
                app_create=AppCreate.from_dict(body),
                _headers={"Content-Type": "application/json"},
            )
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e,
                f"Exception when creating app in org [{org_slug}], space [{space_slug}], instance [{instance_slug}]: {e}",
            )


def derive_app(
    org_slug: str,
    space_slug: str,
    instance_slug: str,
    app_slug: str,
    image_tag: str = None,
    email_once_finished: bool = True,
):
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.AppsV1Api(api_client)
        body = {"email_once_finished": email_once_finished}
        if image_tag is not None:
            body["image_tag"] = image_tag
        try:
            return api_instance.derive_app(
                org_slug=org_slug,
                space_slug=space_slug,
                instance_slug=instance_slug,
                app_slug=app_slug,
                derive_app=DeriveApp.from_dict(body),
                _headers={"Content-Type": "application/json"},
            )
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e,
                f"Exception when deriving app [{app_slug}] in org [{org_slug}], space [{space_slug}], instance [{instance_slug}]: {e}",
            )


def list_images():
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.ImagesV1Api(api_client)
        try:
            return api_instance.get_images()
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e, f"Exception when listing images: {e}"
            )


def create_image(
    name: str,
    docker_image_url: str,
    description_md: str,
    ifid: int,
    description: str = None,
    public: bool = False,
    public_description: str = None,
    org_slug: str = None,
    space_slug: str = None,
    app_type: str = None,
    configuration: dict = None,
    has_tables: bool = None,
    complexity: int = None,
    tags: dict = None,
):
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.ImagesV1Api(api_client)
        body = {
            "name": name,
            "docker_image_url": docker_image_url,
            "description_md": description_md,
            "ifid": ifid,
            "public": public,
        }
        if description is not None:
            body["description"] = description
        if public_description is not None:
            body["public_description"] = public_description
        if org_slug is not None:
            body["org_slug"] = org_slug
        if space_slug is not None:
            body["space_slug"] = space_slug
        if app_type is not None:
            body["app_type"] = app_type
        if configuration is not None:
            body["configuration"] = configuration
        if has_tables is not None:
            body["has_tables"] = has_tables
        if complexity is not None:
            body["complexity"] = complexity
        if tags is not None:
            body["tags"] = tags
        try:
            return api_instance.create_image(
                image_create=ImageCreate.from_dict(body),
                _headers={"Content-Type": "application/json"},
            )
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e, f"Exception when creating image [{name}]: {e}"
            )


def update_image(
    imid: int,
    name: str = None,
    docker_image_url: str = None,
    description: str = None,
    description_md: str = None,
    public: bool = None,
    public_description: str = None,
    app_type: str = None,
    configuration: dict = None,
    complexity: int = None,
    tags: dict = None,
):
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.ImagesV1Api(api_client)
        body = {}
        if name is not None:
            body["name"] = name
        if docker_image_url is not None:
            body["docker_image_url"] = docker_image_url
        if description is not None:
            body["description"] = description
        if description_md is not None:
            body["description_md"] = description_md
        if public is not None:
            body["public"] = public
        if public_description is not None:
            body["public_description"] = public_description
        if app_type is not None:
            body["app_type"] = app_type
        if configuration is not None:
            body["configuration"] = configuration
        if complexity is not None:
            body["complexity"] = complexity
        if tags is not None:
            body["tags"] = tags
        try:
            return api_instance.update_image(
                imid=imid,
                image_update=ImageUpdate.from_dict(body),
                _headers={"Content-Type": "application/json"},
            )
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e, f"Exception when updating image [{imid}]: {e}"
            )


def list_image_families():
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.ImageFamiliesV1Api(api_client)
        try:
            response = api_instance.get_image_families_without_preload_content()
            raw_payload = response.data.decode("utf-8") if response.data else "[]"
            families = json.loads(raw_payload)

            # Some backend records may contain null entries inside groups,
            # while the generated client expects every item to be a string.
            sanitized_families = []
            for family in families:
                groups = family.get("groups")
                if isinstance(groups, list):
                    family["groups"] = [group for group in groups if group is not None]
                sanitized_families.append(
                    nuvolos_client_api.ImageFamily.from_dict(family)
                )

            return sanitized_families
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e, f"Exception when listing image families: {e}"
            )


def create_image_family(
    name: str,
    icon_url: str,
    description: str = None,
    groups: list = None,
):
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.ImageFamiliesV1Api(api_client)
        body = {"name": name, "icon_url": icon_url}
        if description is not None:
            body["description"] = description
        if groups is not None:
            body["groups"] = groups
        try:
            return api_instance.create_image_family(
                image_family_create=ImageFamilyCreate.from_dict(body),
                _headers={"Content-Type": "application/json"},
            )
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e, f"Exception when creating image family [{name}]: {e}"
            )


def list_image_links():
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.ImageLinksV1Api(api_client)
        try:
            return api_instance.get_image_links()
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e, f"Exception when listing image links: {e}"
            )


def list_sessions(
    org_slug: str,
    space_slug: str,
    instance_slug: str,
    app_slug: str,
    page: int = None,
    per_page: int = None,
    session_id: str = None,
    sort: str = None,
):
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.SessionsV1Api(api_client)
        kwargs = {
            "org_slug": org_slug,
            "space_slug": space_slug,
            "instance_slug": instance_slug,
            "app_slug": app_slug,
        }
        if page is not None:
            kwargs["page"] = page
        if per_page is not None:
            kwargs["per_page"] = per_page
        if session_id is not None:
            kwargs["session_id"] = session_id
        if sort is not None:
            kwargs["sort"] = sort
        try:
            return api_instance.get_sessions(**kwargs)
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e,
                f"Exception when listing sessions for app [{app_slug}]: {e}",
            )


def get_session_logs(
    session_id: str,
    container_name: str,
    max_lines: int = None,
    from_start: str = None,
):
    config = get_api_config()
    with nuvolos_client_api.ApiClient(config) as api_client:
        api_instance = nuvolos_client_api.SessionsV1Api(api_client)
        kwargs = {
            "session_id": session_id,
            "container_name": container_name,
        }
        if max_lines is not None:
            kwargs["max_lines"] = max_lines
        if from_start is not None:
            kwargs["from_start"] = from_start
        try:
            response = api_instance.get_session_logs_without_preload_content(**kwargs)
            raw_payload = response.data.decode("utf-8") if response.data else "[]"
            if not raw_payload.strip():
                return []
            try:
                return json.loads(raw_payload)
            except json.JSONDecodeError:
                return raw_payload
        except nuvolos_client_api.ApiException as e:
            raise NuvolosCliException.from_api_exception(
                e,
                f"Exception when getting session logs for session [{session_id}], container [{container_name}]: {e}",
            )
