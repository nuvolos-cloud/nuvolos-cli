# Instance Management

This document provides details on how to manage Nuvolos instances using the Nuvolos CLI.

## Overview

Instances in Nuvolos are containerized environments where users can run applications. Each instance belongs to a space, and each space belongs to an organization. Instances contain snapshots, and the development snapshot is where new applications are created.

## Listing Instances

The `nuvolos instances list` command allows you to view all instances in a specified space.

### Usage

```bash
nuvolos instances list [options]
```

### Options

- `-o, --org TEXT`: Organization slug
- `-s, --space TEXT`: Space slug
- `-f, --format TEXT`: Output format. Available values: `tabulated` (default), `json`, `yaml`
- `--help`: Show help message and exit.

### Context Usage

If you have configured context (via environment or config), you may omit these options and they will be inferred from the context.

### Examples

```bash
# List instances in a specific org and space
nuvolos instances list -o my_org -s my_space

# List instances with JSON output
nuvolos instances list -o my_org -s my_space -f json

# List instances (assuming org and space are in context)
nuvolos instances list
```

## Creating Instances

The `nuvolos instances create` command allows you to create a new instance in a specified space.

### Usage

```bash
nuvolos instances create [options]
```

### Required Options

- `-n, --name TEXT`: Name of the instance to create

### Optional Options

- `-o, --org TEXT`: Organization slug (required if not in context)
- `-s, --space TEXT`: Space slug (required if not in context)
- `--slug TEXT`: URL-friendly slug for the instance. If not provided, it will be auto-generated from the name.
- `-d, --description TEXT`: Description of the instance
- `-f, --format TEXT`: Output format (`tabulated`, `json`, `yaml`)

### Details

- The instance slug is used in URLs and API calls to identify the instance
- If no slug is provided, it will be automatically generated from the instance name using slugification (spaces → underscores, lowercase)
- The creation operation returns an instance object with all details including timestamps

### Examples

```bash
# Create a basic instance
nuvolos instances create \
  -o my_org \
  -s my_space \
  -n "Development Instance"

# Create an instance with custom slug and description
nuvolos instances create \
  -o my_org \
  -s my_space \
  -n "Production Instance" \
  --slug "prod_instance_001" \
  -d "Main production environment for customer-facing applications"

# Create an instance (assuming org and space are in context)
nuvolos instances create -n "Testing Instance"
```

## Instance Properties

An instance record includes:

- **slug**: URL-friendly identifier for the instance
- **name**: Human-readable name
- **description**: Detailed description (optional)
- **role**: Your role in the instance (e.g., "owner", "admin", "user")
- **creation_timestamp**: When the instance was created
- **archival_timestamp**: When the instance was archived (if applicable)
- **rearchive_after_timestamp**: When archived data will be re-archived (if applicable)

## Snapshots

Instances contain multiple snapshots. The **development** snapshot is where new applications are created and modified.

See [Snapshot Management](snapshot_management.md) for managing snapshots.

## Applications in Instances

Once you have an instance, you can:

1. View available images: `nuvolos images list`
2. Create applications from images: `nuvolos apps create`
3. Start applications: `nuvolos apps start`

See [Application Management](app_management.md) for more details.

## Related Commands

- [Space Management](space_management.md) - Manage spaces that contain instances
- [Application Management](app_management.md) - Create and manage applications
- [Snapshot Management](snapshot_management.md) - Create and manage snapshots
