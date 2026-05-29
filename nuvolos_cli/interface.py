import os
import json
import click
import click_log
from tabulate import tabulate

from .logging import clog
from .config import init_cli_config, check_api_key_configured, info
from .api_client import (
    list_orgs,
    list_spaces,
    list_instances,
    list_snapshots,
    list_apps,
    list_all_running_apps,
    start_app,
    stop_app,
    execute_command_in_app,
    list_all_running_workloads_for_app,
    list_nodepools,
    wait_for_app_running,
    create_snapshot,
    delete_snapshot,
    wait_for_task,
    get_task,
    create_instance,
    create_app,
    derive_app,
    list_images,
    create_image,
    update_image,
    list_image_families,
    create_image_family,
    list_image_links,
    list_sessions,
    get_session_logs,
    distribute_content,
    list_files,
    list_tables,
    get_schema_ddl,
    get_table_columns,
    get_table_ddl,
    rename_table,
    delete_table,
)
from .utils import (
    format_response,
    get_effective_snapshot_context,
    get_effective_instance_context,
    get_effective_space_context,
)


@click.group("nuvolos")
@click_log.simple_verbosity_option(clog)
@click.pass_context
def nuvolos(ctx):
    ctx.ensure_object(dict)
    if "NV_CONTEXT" in os.environ:
        ctx.obj = json.loads(os.environ["NV_CONTEXT"])


@nuvolos.command("config")
@click.option(
    "--api-key",
    type=str,
    help="The Nuvolos API key to use for authentication",
    required=True,
)
def nv_cli_config(**kwargs):
    """
    Initializes a new Nuvolos CLI configuration in the current directory.
    """
    init_cli_config(
        api_key=kwargs.get("api_key"),
    )


@nuvolos.group("orgs")
@click.pass_context
def nv_orgs(ctx):
    pass


@nv_orgs.command("list")
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_orgs_list(ctx, **kwargs):
    """
    Lists the Nuvolos organizations available to the current user.
    """
    check_api_key_configured()
    res = list_orgs()
    return res


@nuvolos.group("spaces")
@click.pass_context
def nv_spaces(ctx):
    pass


@nv_spaces.command("list")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization to use to list spaces",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_spaces_list(ctx, **kwargs):
    """
    Lists the Nuvolos organizations / spaces / instances / apps available to the current user.
    """
    check_api_key_configured()
    space_ctx = get_effective_space_context(ctx, **kwargs)
    return list_spaces(org_slug=space_ctx.get("org_slug"))


@nuvolos.group("instances")
@click.pass_context
def nv_instances(ctx):
    pass


@nv_instances.command("list")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization to use to list instances",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space to use to list instances",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_instances_list(ctx, **kwargs):
    """
    Lists the Nuvolos instances available to the current user.
    """
    check_api_key_configured()
    instance_ctx = get_effective_instance_context(ctx, **kwargs)
    return list_instances(
        org_slug=instance_ctx.get("org_slug"), space_slug=instance_ctx.get("space_slug")
    )


@nuvolos.group("snapshots")
@click.pass_context
def nv_snapshots(ctx):
    pass


@nv_snapshots.command("list")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization to use to list snapshots",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space to use to list snapshots",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance to use to list snapshots",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_snapshots_list(ctx, **kwargs):
    """
    Lists the Nuvolos snapshots available to the current user.
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
    return list_snapshots(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
    )


@nv_snapshots.command("create")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization to use to create a snapshot",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space to use to create a snapshot",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance to use to create a snapshot",
)
@click.option(
    "-n",
    "--name",
    type=str,
    required=True,
    help="The name of the snapshot to create",
)
@click.option(
    "-d",
    "--description",
    type=str,
    help="The description of the snapshot to create",
)
@click.option(
    "-e",
    "--email",
    is_flag=True,
    help="Send an email notification when snapshot creation is complete",
)
@click.option(
    "-w",
    "--wait",
    is_flag=True,
    help="Wait until snapshot creation is complete",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_snapshots_create(ctx, **kwargs):
    """
    Creates a new snapshot in the given instance.
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
    task = create_snapshot(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
        snapshot_name=kwargs.get("name"),
        snapshot_description=kwargs.get("description"),
        email_once_finished=kwargs.get("email", False),
    )

    if kwargs.get("wait") and task is not None and hasattr(task, "tkid"):
        clog.info(f"Waiting for snapshot creation task {task.tkid} to complete...")
        task = wait_for_task(tkid=task.tkid)

    return task


@nv_snapshots.command("delete")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization to use to delete a snapshot",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space to use to delete a snapshot",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance to use to delete a snapshot",
)
@click.option(
    "-p",
    "--snapshot",
    type=str,
    required=True,
    help="The slug of the snapshot to delete",
)
@click.option(
    "-w",
    "--wait",
    is_flag=True,
    help="Wait until snapshot deletion is complete",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_snapshots_delete(ctx, **kwargs):
    """
    Deletes a snapshot from the given instance.
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
    task = delete_snapshot(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
        snapshot_slug=kwargs.get("snapshot"),
    )

    if kwargs.get("wait") and task is not None and hasattr(task, "tkid"):
        clog.info(f"Waiting for snapshot deletion task {task.tkid} to complete...")
        task = wait_for_task(tkid=task.tkid)

    return task


@nuvolos.group("apps")
def nv_apps():
    pass


@nv_apps.command("list")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization to use to list applications",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space to use to list applications",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance to use to list applications",
)
@click.option(
    "-p",
    "--snapshot",
    type=str,
    default="development",
    help="The slug of the Nuvolos snapshot to use to list applications",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_apps_list(ctx, **kwargs):
    """
    Lists the Nuvolos applications available to the current user.
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
    return list_apps(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
        snapshot_slug=kwargs["snapshot"],
    )


@nv_apps.command("start")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization to use to start an application",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space to use to start an application",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance to use to start an application",
)
@click.argument("app")
@click.option(
    "-n",
    "--node-pool",
    type=str,
    help="The node pool to use to run the app",
)
@click.option(
    "-w",
    "--wait",
    is_flag=True,
    help="Waits until the started application is in a running state",
)
@click.pass_context
def nv_apps_start(ctx, app, **kwargs):
    """
    Starts the Nuvolos application with the APP application slug.
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
    start_app(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
        app_slug=app,
        node_pool=kwargs.get("node_pool", None),
    )
    if kwargs.get("wait"):
        wait_for_app_running(
            org_slug=snapshot_ctx.get("org_slug"),
            space_slug=snapshot_ctx.get("space_slug"),
            instance_slug=snapshot_ctx.get("instance_slug"),
            app_slug=app,
        )


@nv_apps.command("stop")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization to use to stop an application",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space to use to stop an application",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance to use to stop an application",
)
@click.option(
    "-a",
    "--app",
    type=str,
    help="The slug of the Nuvolos application to stop",
    required=True,
)
@click.pass_context
def nv_apps_stop(ctx, **kwargs):
    """
    Stops the Nuvolos application with the given application slug.
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
    stop_app(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
        app_slug=kwargs.get("app"),
    )


@nv_apps.command("running")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization to use to list running workloads for an application",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space to use to list running workloads for an application",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance to use to list running workloads for an application",
)
@click.option(
    "-a",
    "--app",
    type=str,
    help="The slug of the Nuvolos application to use to list running an workloads",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_apps_running(ctx, **kwargs):
    """
    Lists all running Nuvolos applications of the user. If the app is specified, lists all running workloads
    for the given application.
    """
    check_api_key_configured()
    app_slug = kwargs.get("app", None)
    if app_slug:
        snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
        res = list_all_running_workloads_for_app(
            org_slug=snapshot_ctx.get("org_slug"),
            space_slug=snapshot_ctx.get("space_slug"),
            instance_slug=snapshot_ctx.get("instance_slug"),
            app_slug=kwargs.get("app"),
        )
    else:
        res = list_all_running_apps()
    return res


@nv_apps.command("execute")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization to use to execute a command in an application",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space to use to execute a command in an application",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance to use to execute a command in an application",
)
@click.option(
    "-a",
    "--app",
    type=str,
    help="The slug of the Nuvolos application where the command is executed",
    required=True,
)
@click.argument("command")
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_apps_execute(ctx, command, **kwargs):
    """
    Executes COMMAND in a Nuvolos application.

    Example:
    nuvolos apps execute -a my_slug "python -c 'from time import sleep;sleep(10)'"
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
    res = execute_command_in_app(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
        app_slug=kwargs.get("app"),
        command=command,
    )
    return res


@nv_apps.command("nodepools")
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@format_response
def nv_apps_list_nodepools(**kwargs):
    """
    Lists all nodepools available for dedicated app launch.
    """
    check_api_key_configured()
    res = list_nodepools()

    return res


@nuvolos.group("tasks")
@click.pass_context
def nv_tasks(ctx):
    """Manages Nuvolos tasks."""
    pass


@nv_tasks.command("get")
@click.argument("tkid", type=int)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_task_get(ctx, tkid, **kwargs):
    """
    Retrieves the status and details of a specific task by its ID.
    """
    check_api_key_configured()
    task = get_task(tkid=tkid)
    return task


@nuvolos.command("info")
@click.pass_context
def nv_info(ctx):
    """
    Prints information about the Nuvolos CLI.
    """
    info(nuvolos_ctx=ctx.obj)


# --- Instances: create ---


@nv_instances.command("create")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space",
)
@click.option(
    "-n",
    "--name",
    type=str,
    required=True,
    help="The name of the instance to create",
)
@click.option(
    "--slug",
    type=str,
    help="The slug for the new instance (auto-generated from name if not provided)",
)
@click.option(
    "-d",
    "--description",
    type=str,
    help="The description of the instance to create",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_instances_create(ctx, **kwargs):
    """
    Creates a new instance in the specified space.
    """
    check_api_key_configured()
    instance_ctx = get_effective_instance_context(ctx, **kwargs)
    from slugify import slugify

    slug = kwargs.get("slug") or slugify(kwargs["name"], separator="_")
    res = create_instance(
        org_slug=instance_ctx.get("org_slug"),
        space_slug=instance_ctx.get("space_slug"),
        instance_name=kwargs["name"],
        instance_slug=slug,
        instance_description=kwargs.get("description"),
    )
    return res


# --- Apps: create, derive ---


@nv_apps.command("create")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance",
)
@click.option(
    "--imid",
    type=int,
    required=True,
    help="The image ID to use for the application",
)
@click.option(
    "-n",
    "--name",
    type=str,
    required=True,
    help="The long_id (display name) of the application",
)
@click.option(
    "-d",
    "--description",
    type=str,
    help="The description of the application",
)
@click.option(
    "--pars",
    type=str,
    help="JSON string of application parameters",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_apps_create(ctx, **kwargs):
    """
    Creates a new application in the development snapshot of the specified instance.
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
    res = create_app(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
        imid=kwargs["imid"],
        long_id=kwargs["name"],
        description=kwargs.get("description"),
        pars=kwargs.get("pars"),
    )
    return res


@nv_apps.command("derive")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance",
)
@click.option(
    "-a",
    "--app",
    type=str,
    required=True,
    help="The slug of the application to derive from",
)
@click.option(
    "-t",
    "--tag",
    type=str,
    help="The image tag for the derived image",
)
@click.option(
    "-e",
    "--email/--no-email",
    default=True,
    help="Send email once the derivation is finished (default: yes)",
)
@click.option(
    "-w",
    "--wait",
    is_flag=True,
    help="Wait until the derivation task is complete",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_apps_derive(ctx, **kwargs):
    """
    Creates a derived image from an existing Nuvolos application.
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
    task = derive_app(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
        app_slug=kwargs["app"],
        image_tag=kwargs.get("tag"),
        email_once_finished=kwargs.get("email", True),
    )

    if kwargs.get("wait") and task is not None and hasattr(task, "tkid"):
        clog.info(f"Waiting for derive task {task.tkid} to complete...")
        task = wait_for_task(tkid=task.tkid)

    return task


# --- Images ---


@nuvolos.group("images")
def nv_images():
    """Manages Nuvolos images."""
    pass


@nv_images.command("list")
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@format_response
def nv_images_list(**kwargs):
    """
    Lists all images accessible to the current user.
    """
    check_api_key_configured()
    return list_images()


@nv_images.command("create")
@click.option(
    "-n",
    "--name",
    type=str,
    required=True,
    help="Name of the image",
)
@click.option(
    "--docker-image-url",
    type=str,
    required=True,
    help="Docker image URL (e.g. registry/repo:tag)",
)
@click.option(
    "--description-md",
    type=str,
    required=True,
    help="Markdown description of the image",
)
@click.option(
    "--ifid",
    type=int,
    required=True,
    help="Image family ID to associate with",
)
@click.option(
    "-d",
    "--description",
    type=str,
    help="Short description of the image",
)
@click.option(
    "--public/--no-public",
    default=False,
    help="Whether the image is public",
)
@click.option(
    "--public-description",
    type=str,
    help="Public-facing description",
)
@click.option(
    "-o",
    "--org",
    type=str,
    help="Org slug to scope the image to (omit for global)",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="Space slug to scope the image to",
)
@click.option(
    "--app-type",
    type=str,
    help="Application type identifier",
)
@click.option(
    "--configuration",
    type=str,
    help="JSON string of configuration parameters",
)
@click.option(
    "--has-tables/--no-tables",
    default=None,
    help="Whether the image supports database tables",
)
@click.option(
    "--complexity",
    type=int,
    help="Complexity level of the image",
)
@click.option(
    "--tags",
    type=str,
    help="JSON string of tags",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@format_response
def nv_images_create(**kwargs):
    """
    Creates a new image record.
    """
    check_api_key_configured()
    configuration = None
    if kwargs.get("configuration"):
        configuration = json.loads(kwargs["configuration"])
    tags = None
    if kwargs.get("tags"):
        tags = json.loads(kwargs["tags"])
    res = create_image(
        name=kwargs["name"],
        docker_image_url=kwargs["docker_image_url"],
        description_md=kwargs["description_md"],
        ifid=kwargs["ifid"],
        description=kwargs.get("description"),
        public=kwargs.get("public", False),
        public_description=kwargs.get("public_description"),
        org_slug=kwargs.get("org"),
        space_slug=kwargs.get("space"),
        app_type=kwargs.get("app_type"),
        configuration=configuration,
        has_tables=kwargs.get("has_tables"),
        complexity=kwargs.get("complexity"),
        tags=tags,
    )
    return res


@nv_images.command("update")
@click.argument("imid", type=int)
@click.option(
    "-n",
    "--name",
    type=str,
    help="New name for the image",
)
@click.option(
    "--docker-image-url",
    type=str,
    help="New docker image URL",
)
@click.option(
    "-d",
    "--description",
    type=str,
    help="New short description",
)
@click.option(
    "--description-md",
    type=str,
    help="New markdown description",
)
@click.option(
    "--public/--no-public",
    default=None,
    help="Whether the image is public",
)
@click.option(
    "--public-description",
    type=str,
    help="New public-facing description",
)
@click.option(
    "--app-type",
    type=str,
    help="New application type identifier",
)
@click.option(
    "--configuration",
    type=str,
    help="JSON string of new configuration parameters",
)
@click.option(
    "--complexity",
    type=int,
    help="New complexity level",
)
@click.option(
    "--tags",
    type=str,
    help="JSON string of new tags",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@format_response
def nv_images_update(imid, **kwargs):
    """
    Updates an existing image record. Only provided fields are updated.
    """
    check_api_key_configured()
    configuration = None
    if kwargs.get("configuration"):
        configuration = json.loads(kwargs["configuration"])
    tags = None
    if kwargs.get("tags"):
        tags = json.loads(kwargs["tags"])
    res = update_image(
        imid=imid,
        name=kwargs.get("name"),
        docker_image_url=kwargs.get("docker_image_url"),
        description=kwargs.get("description"),
        description_md=kwargs.get("description_md"),
        public=kwargs.get("public"),
        public_description=kwargs.get("public_description"),
        app_type=kwargs.get("app_type"),
        configuration=configuration,
        complexity=kwargs.get("complexity"),
        tags=tags,
    )
    return res


# --- Image Families ---


@nuvolos.group("image-families")
def nv_image_families():
    """Manages Nuvolos image families."""
    pass


@nv_image_families.command("list")
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@format_response
def nv_image_families_list(**kwargs):
    """
    Lists all image families.
    """
    check_api_key_configured()
    return list_image_families()


@nv_image_families.command("create")
@click.option(
    "-n",
    "--name",
    type=str,
    required=True,
    help="Name of the image family",
)
@click.option(
    "--icon-url",
    type=str,
    required=True,
    help="URL of the icon for the image family",
)
@click.option(
    "-d",
    "--description",
    type=str,
    help="Description of the image family",
)
@click.option(
    "--groups",
    type=str,
    help="Comma-separated list of groups",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@format_response
def nv_image_families_create(**kwargs):
    """
    Creates a new image family. Priority is automatically set.
    """
    check_api_key_configured()
    groups = None
    if kwargs.get("groups"):
        groups = [g.strip() for g in kwargs["groups"].split(",")]
    res = create_image_family(
        name=kwargs["name"],
        icon_url=kwargs["icon_url"],
        description=kwargs.get("description"),
        groups=groups,
    )
    return res


# --- Image Links ---


@nuvolos.group("image-links")
def nv_image_links():
    """Manages Nuvolos image links."""
    pass


@nv_image_links.command("list")
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@format_response
def nv_image_links_list(**kwargs):
    """
    Lists all image links accessible to the current user.
    """
    check_api_key_configured()
    return list_image_links()


# --- Sessions ---


@nuvolos.group("sessions")
def nv_sessions():
    """Manages Nuvolos application sessions."""
    pass


@nv_sessions.command("list")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance",
)
@click.option(
    "-a",
    "--app",
    type=str,
    required=True,
    help="The slug of the Nuvolos application",
)
@click.option(
    "--page",
    type=int,
    help="Page number (default: 1)",
)
@click.option(
    "--per-page",
    type=int,
    help="Results per page (default: 100)",
)
@click.option(
    "--session-id",
    type=str,
    help="Filter by a specific session ID",
)
@click.option(
    "--sort",
    type=click.Choice(["asc", "desc"]),
    help="Sort order (default: desc)",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_sessions_list(ctx, **kwargs):
    """
    Lists sessions for a given application.
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
    return list_sessions(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
        app_slug=kwargs["app"],
        page=kwargs.get("page"),
        per_page=kwargs.get("per_page"),
        session_id=kwargs.get("session_id"),
        sort=kwargs.get("sort"),
    )


@nv_sessions.command("logs")
@click.option(
    "--session-id",
    type=str,
    required=True,
    help="The session ID to get logs for",
)
@click.option(
    "-c",
    "--container",
    type=str,
    required=True,
    help="The container name to get logs from",
)
@click.option(
    "--max-lines",
    type=int,
    help="Maximum number of log lines to return (default: 100)",
)
@click.option(
    "--from-start",
    type=str,
    help="ISO datetime to start reading logs from",
)
@click.option(
    "-f",
    "--format",
    type=click.Choice(["tabulated", "json"]),
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`",
)
@click.option(
    "--columns",
    type=str,
    help="Comma-separated list of columns to include (e.g. 'msg,ts')",
)
@click.pass_context
def nv_sessions_logs(ctx, **kwargs):
    """
    Retrieves logs for a specific session and container.
    """
    check_api_key_configured()
    result = get_session_logs(
        session_id=kwargs["session_id"],
        container_name=kwargs["container"],
        max_lines=kwargs.get("max_lines"),
        from_start=kwargs.get("from_start"),
    )

    selected_columns = None
    if kwargs.get("columns"):
        selected_columns = [
            c.strip() for c in kwargs["columns"].split(",") if c.strip()
        ]
        if not selected_columns:
            raise click.ClickException(
                "--columns must include at least one column name"
            )

    if result is None:
        if kwargs["format"] == "json":
            click.echo("[]")
        else:
            click.echo("No logs found.")
        return

    original_is_dict = isinstance(result, dict)
    structured_result = None
    if isinstance(result, dict):
        structured_result = [result]
    elif isinstance(result, list) and all(isinstance(entry, dict) for entry in result):
        structured_result = result

    if selected_columns:
        if structured_result is None:
            raise click.ClickException(
                "--columns is only supported for structured log entries"
            )
        available_columns = set().union(*(entry.keys() for entry in structured_result))
        missing_columns = [c for c in selected_columns if c not in available_columns]
        if missing_columns:
            raise click.ClickException(
                f"Unknown columns: {', '.join(missing_columns)}. Available columns: {', '.join(sorted(available_columns))}"
            )
        structured_result = [
            {column: entry.get(column, "") for column in selected_columns}
            for entry in structured_result
        ]

    if kwargs["format"] == "json":
        if structured_result is not None:
            if original_is_dict:
                click.echo(json.dumps(structured_result[0], indent=2))
            else:
                click.echo(json.dumps(structured_result, indent=2))
        else:
            click.echo(json.dumps(result, indent=2))
        return

    if structured_result is not None:
        if not structured_result:
            click.echo("No logs found.")
            return

        table_columns = selected_columns or list(structured_result[0].keys())
        rows = [
            [entry.get(column, "") for column in table_columns]
            for entry in structured_result
        ]
        click.echo(tabulate(rows, headers=table_columns, tablefmt="github"))
    else:
        click.echo(result)


# --- Distribution ---


@nuvolos.group("distribution")
def nv_distribution():
    """Distributes content from a snapshot to target instances."""
    pass


@nv_distribution.command("distribute")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the source Nuvolos organization",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the source Nuvolos space",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the source Nuvolos instance",
)
@click.option(
    "-p",
    "--snapshot",
    type=str,
    default="development",
    help="The slug of the source snapshot to distribute from (default: development)",
)
@click.option(
    "--targets",
    type=str,
    required=True,
    help="JSON array of target instances, each with org_slug, space_slug, instance_slug",
)
@click.option(
    "--apps",
    type=str,
    help="Comma-separated list of application slugs to distribute",
)
@click.option(
    "--files",
    type=str,
    help="Comma-separated list of file paths to distribute",
)
@click.option(
    "--tables",
    type=str,
    help="Comma-separated list of table names to distribute",
)
@click.option(
    "--auto-snapshot/--no-auto-snapshot",
    default=False,
    help="Create a snapshot of target instances before distributing (default: no)",
)
@click.option(
    "--notify/--no-notify",
    default=False,
    help="Notify target users when distribution is complete (default: no)",
)
@click.option(
    "--message",
    type=str,
    help="Custom email message to send with the notification",
)
@click.option(
    "-w",
    "--wait",
    is_flag=True,
    help="Wait until the distribution task is complete",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_distribution_distribute(ctx, **kwargs):
    """
    Distribute selected files, applications, and tables from a snapshot to target instances.
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)

    target_instances = json.loads(kwargs["targets"])

    source_applications = None
    if kwargs.get("apps"):
        source_applications = [a.strip() for a in kwargs["apps"].split(",")]

    source_files = None
    if kwargs.get("files"):
        source_files = [f.strip() for f in kwargs["files"].split(",")]

    source_tables = None
    if kwargs.get("tables"):
        source_tables = [t.strip() for t in kwargs["tables"].split(",")]

    task = distribute_content(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
        snapshot_slug=kwargs["snapshot"],
        target_instances=target_instances,
        source_applications=source_applications,
        source_files=source_files,
        source_tables=source_tables,
        auto_snapshot=kwargs.get("auto_snapshot", False),
        notify_target_users=kwargs.get("notify", False),
        custom_email_message=kwargs.get("message"),
    )

    if kwargs.get("wait") and task is not None and hasattr(task, "tkid"):
        clog.info(f"Waiting for distribution task {task.tkid} to complete...")
        task = wait_for_task(tkid=task.tkid)

    return task


# --- Files ---


@nuvolos.group("files")
def nv_files():
    """Manages files in snapshot areas."""
    pass


@nv_files.command("list")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance",
)
@click.option(
    "-p",
    "--snapshot",
    type=str,
    default="development",
    help="The slug of the Nuvolos snapshot to use",
)
@click.option(
    "-a",
    "--area",
    type=click.Choice(["files", "home"]),
    default="files",
    help="Area to list files from (default: files)",
)
@click.option(
    "--path",
    type=str,
    help="Optional path inside the selected area",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_files_list(ctx, **kwargs):
    """
    Lists files in the selected snapshot area.
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
    return list_files(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
        snapshot_slug=kwargs["snapshot"],
        area=kwargs["area"],
        local_path=kwargs.get("path"),
    )


# --- Tables ---


@nuvolos.group("tables")
def nv_tables():
    """Manages tables in snapshots."""
    pass


@nv_tables.command("list")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance",
)
@click.option(
    "-p",
    "--snapshot",
    type=str,
    default="development",
    help="The slug of the Nuvolos snapshot to use",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_tables_list(ctx, **kwargs):
    """
    Lists tables in the selected snapshot.
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
    return list_tables(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
        snapshot_slug=kwargs["snapshot"],
    )


@nv_tables.command("schema-ddl")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance",
)
@click.option(
    "-p",
    "--snapshot",
    type=str,
    default="development",
    help="The slug of the Nuvolos snapshot to use",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_tables_schema_ddl(ctx, **kwargs):
    """
    Returns the database schema DDL for the selected snapshot.
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
    return get_schema_ddl(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
        snapshot_slug=kwargs["snapshot"],
    )


@nv_tables.command("columns")
@click.argument("table")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance",
)
@click.option(
    "-p",
    "--snapshot",
    type=str,
    default="development",
    help="The slug of the Nuvolos snapshot to use",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_tables_columns(ctx, table, **kwargs):
    """
    Returns columns for TABLE in the selected snapshot.
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
    return get_table_columns(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
        snapshot_slug=kwargs["snapshot"],
        table_slug=table,
    )


@nv_tables.command("ddl")
@click.argument("table")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance",
)
@click.option(
    "-p",
    "--snapshot",
    type=str,
    default="development",
    help="The slug of the Nuvolos snapshot to use",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_tables_ddl(ctx, table, **kwargs):
    """
    Returns DDL for TABLE in the selected snapshot.
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
    return get_table_ddl(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
        snapshot_slug=kwargs["snapshot"],
        table_slug=table,
    )


@nv_tables.command("rename")
@click.argument("table")
@click.option(
    "--new-slug",
    type=str,
    help="New slug for the table",
)
@click.option(
    "--new-name",
    type=str,
    help="New display name for the table",
)
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance",
)
@click.option(
    "-p",
    "--snapshot",
    type=str,
    default="development",
    help="The slug of the Nuvolos snapshot to use",
)
@click.option(
    "-f",
    "--format",
    type=str,
    default="tabulated",
    help="Sets the output into the desired format. Available values: `tabulated`, `json`, `yaml`",
)
@click.pass_context
@format_response
def nv_tables_rename(ctx, table, **kwargs):
    """
    Renames TABLE in the selected snapshot.
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
    return rename_table(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
        snapshot_slug=kwargs["snapshot"],
        table_slug=table,
        new_slug=kwargs.get("new_slug"),
        new_name=kwargs.get("new_name"),
    )


@nv_tables.command("delete")
@click.argument("table")
@click.option(
    "-o",
    "--org",
    type=str,
    help="The slug of the Nuvolos organization",
)
@click.option(
    "-s",
    "--space",
    type=str,
    help="The slug of the Nuvolos space",
)
@click.option(
    "-i",
    "--instance",
    type=str,
    help="The slug of the Nuvolos instance",
)
@click.option(
    "-p",
    "--snapshot",
    type=str,
    default="development",
    help="The slug of the Nuvolos snapshot to use",
)
@click.pass_context
def nv_tables_delete(ctx, table, **kwargs):
    """
    Deletes TABLE from the selected snapshot.
    """
    check_api_key_configured()
    snapshot_ctx = get_effective_snapshot_context(ctx, **kwargs)
    delete_table(
        org_slug=snapshot_ctx.get("org_slug"),
        space_slug=snapshot_ctx.get("space_slug"),
        instance_slug=snapshot_ctx.get("instance_slug"),
        snapshot_slug=kwargs["snapshot"],
        table_slug=table,
    )
    click.echo(f"Table [{table}] deleted successfully")
