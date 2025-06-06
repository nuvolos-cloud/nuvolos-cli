# Quickstart

You can launch the Nuvolos CLI with the `nuvolos` command.

## Prerequisites

If you are running the CLI on your own computer, you will need to configure your API key. You can do this with the `nuvolos config` command:

```
nuvolos config --api-key <YOUR_API_KEY>
```

## Debug Logging

You can enable detailed HTTP request and response logging by setting the `NUVOLOS_CLI_DEBUG` environment variable to `true`:

```bash
export NUVOLOS_CLI_DEBUG=true
```

When this variable is set, the CLI will print debug-level logs including API request URLs, headers, and responses.

## Using the CLI on the Nuvolos platform

**On the Nuvolos platform, you can use the CLI without any configuration.**

To list the applications available in the current instance you are working in, you can use the `nuvolos apps list` command:

```
nuvolos apps list
```

To launch an application, you can use the `nuvolos apps start` command:

```
nuvolos apps start -n <node_pool> APP
```
where `APP` is the application slug.
You can find the application slug in the output of the `nuvolos apps list` command.
The `-n` option can be used to set the node pool where the application should run. For further reference see [Launching scaled apps](launch_scaled_apps.md).
You can also add the `--wait` flag to the above command that makes the command wait for the launched application to be
in a `RUNNING` state before returning.

You can list all running apps with the `nuvolos apps running` command:

```
nuvolos apps running
```

You can stop an application with the `nuvolos apps stop` command:

```
nuvolos apps stop -a <app_slug>
```
Keep in mind, that the Nuvolos API has a hierarchical order in the `nuvolos apps stop` command. First it tries to
stop the application that has been launched by the current user, but if there is no application found, it will try
to stop a shared application in the same instance with the same `app_slug`.

You can execute custom commands in a Nuvolos application with the `nuvolos apps execute` command:
```
nuvolos apps execute -a <app_slug> COMMAND
```

## Using the CLI on your own computer

### Listing Nuvolos organizations

To list the Nuvolos organizations you have access to, you can use the `nuvolos orgs list` command:

```
nuvolos orgs list
```

### Listing Nuvolos spaces

To list the Nuvolos spaces you have access to in a chosen organization, you can use the `nuvolos spaces list` command:

```
nuvolos spaces list -o <org_slug>
```

where `<org_slug>` is the organization slug.

### Listing Nuvolos instances

To list the Nuvolos instances you have access to in a chosen space, you can use the `nuvolos instances list` command:

```
nuvolos instances list -o <org_slug> -s <space_slug>
```

where `<org_slug>` is the organization slug and `<space_slug>` is the space slug.

### Listing Nuvolos snapshots

To list the Nuvolos snapshots you have access to in a chosen instance, you can use the `nuvolos snapshots list` command:

```
nuvolos snapshots list -o <org_slug> -s <space_slug> -i <instance_slug>
```

where `<org_slug>` is the organization slug, `<space_slug>` is the space slug, and `<instance_slug>` is the instance slug.

### Listing Nuvolos applications

To list the Nuvolos applications you have access to in a chosen snapshot, you can use the `nuvolos apps list` command:

```
nuvolos apps list -o <org_slug> -s <space_slug> -i <instance_slug> -p <snapshot_slug>
```

where `<org_slug>` is the organization slug, `<space_slug>` is the space slug, `<instance_slug>` is the instance slug, and `<snapshot_slug>` is the snapshot slug.

**Note that the snapshot slug is optional, it defaults to the development (working) snapshot if omitted.**

### Launching a Nuvolos application

To launch a Nuvolos application in a chosen snapshot, you can use the `nuvolos apps start` command:

```
nuvolos apps start -o <org_slug> -s <space_slug> -i <instance_slug> -n <node_pool> APP
```

where `<org_slug>` is the organization slug, `<space_slug>` is the space slug, `<instance_slug>` is the instance slug, and `APP` is the application slug.
The `-n` option can be used to set the node pool where the application should run. For further reference see [Launching scaled apps](launch_scaled_apps.md).
You can also add the `--wait` flag to the above command that makes the command wait for the launched application to be
in a `RUNNING` state before returning.

**Note that you can only start Nuvolos applications in the development snapshot.**

### Stopping a Nuvolos application

To stop a Nuvolos application in a chosen snapshot, you can use the `nuvolos apps stop` command:

```
nuvolos apps stop -o <org_slug> -s <space_slug> -i <instance_slug> -a <app_slug>
```

where `<org_slug>` is the organization slug, `<space_slug>` is the space slug, `<instance_slug>` is the instance slug, and `<app_slug>` is the application slug.

Keep in mind, that the Nuvolos API has a hierarchical order in the `nuvolos apps stop` command. First it tries to
stop the application that has been launched by the current user, but if there is no application found, it will try
to stop a shared application in the same instance with the same `app_slug`.
### Executing commands in a Nuvolos application

To execute a command in a running Nuvolos application, you can use the `nuvolos apps execute` command:
```
nuvolos apps execute -o <org_slug> -s <space_slug> -i <instance_slug> -a <app_slug> COMMAND
```
where `<org_slug>` is the organization slug, `<space_slug>` is the space slug, `<instance_slug>` is the instance slug, 
`<app_slug>` is the application slug and `<command>` is the command to execute. For further details see [Execute commands](execute_commands.md).
