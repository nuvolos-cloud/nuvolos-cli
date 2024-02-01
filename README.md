<!-- [![PyPI version](https://img.shields.io/pypi/v/nuvolos-cli)](https://pypi.org/project/nuvolos-cli/)  -->
[![Docs](https://readthedocs.org/projects/nuvolos-cli/badge/)](https://nuvolos-cli.readthedocs.io/en/latest/)
<!-- [![Integration tests](https://github.com/nuvolos-cloud/nuvolos-cli/actions/workflows/integration-test.yaml/badge.svg)](https://github.com/nuvolos-cloud/nuvolos-cli/actions/workflows/integration-test.yaml) -->


```
 _   _                  _              ____ _     ___ 
| \ | |_   ___   _____ | | ___  ___   / ___| |   |_ _|
|  \| | | | \ \ / / _ \| |/ _ \/ __| | |   | |    | | 
| |\  | |_| |\ V / (_) | | (_) \__ \ | |___| |___ | | 
|_| \_|\__,_| \_/ \___/|_|\___/|___/  \____|_____|___|
                                                      
```

Nuvolos CLI is command-line interface (CLI) for the [Nuvolos](https://nuvolos.cloud) platform. It allows you to interact with the Nuvolos platform from your local terminal.

For installation and detailed usage, check out the [documentation](https://nuvolos-cli.readthedocs.io/en/latest/).

## Installation

You can install the latest stable version using pip with

```
pip install nuvolos-cli
```

## Using the CLI on the Nuvolos platform

**On the Nuvolos platform, you can use the CLI without any configuration.**

To list the applications available in the current instance you are working in, you can use the `nuvolos apps list` command:

```
nuvolos apps list
```

To launch an application, you can use the `nuvolos apps start` command:

```
nuvolos apps start -a <app_slug>
```
where `<app_slug>` is the application slug. 
You can find the application slug in the output of the `nuvolos apps list` command.

You can list all running apps with the `nuvolos apps command`:

```
nuvolos apps running
```

You can stop an application with the `nuvolos apps stop` command:

```
nuvolos apps stop -a <app_slug>
```

## Using the CLI on your own computer

### Prerequisites

If you are running the CLI on your own computer, you will need to configure your API key. You can do this with the `nuvolos config` command:

```
nuvolos config --api-key <YOUR_API_KEY>
```

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
nuvolos apps start -o <org_slug> -s <space_slug> -i <instance_slug> -a <app_slug> -n <node_pool>
```

where `<org_slug>` is the organization slug, `<space_slug>` is the space slug, `<instance_slug>` is the instance slug, and `<app_slug>` is the application slug.
The `-n` argument is an optional parameter to set the node pool where the application should run.

**Note that you can only start Nuvolos applications in the development snapshot.**

### Stopping a Nuvolos application

To stop a Nuvolos application in a chosen snapshot, you can use the `nuvolos apps stop` command:

```
nuvolos apps stop -o <org_slug> -s <space_slug> -i <instance_slug> -a <app_slug>
```

where `<org_slug>` is the organization slug, `<space_slug>` is the space slug, `<instance_slug>` is the instance slug, and `<app_slug>` is the application slug.

### Executing commands in a Nuvolos application

To execute a command in a running Nuvolos application, you can use the `nuvolos apps execute` command:
```
nuvolos apps execute -o <org_slug> -s <space_slug> -i <instance_slug> -a <app_slug> -c <command>
```
where `<org_slug>` is the organization slug, `<space_slug>` is the space slug, `<instance_slug>` is the instance slug, `<app_slug>` 
is the application slug and `<command>` is the command to execute.


