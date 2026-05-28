# Space Management

This document provides details on how to manage Nuvolos spaces using the Nuvolos CLI.

## Overview

Spaces are logical divisions within organizations in Nuvolos. Each space can have its own instances, applications, and settings. Spaces provide isolation and organization for collaborative environments.

## Listing Spaces

The `nuvolos spaces list` command allows you to view all spaces in a specified organization.

### Usage

```bash
nuvolos spaces list [options]
```

### Options

- `-o, --org TEXT`: Organization slug
- `-f, --format TEXT`: Output format. Available values: `tabulated` (default), `json`, `yaml`
- `--help`: Show help message and exit.

### Context Usage

If you have configured context, you may omit the org slug and it will be inferred from the context.

### Space Properties

Each space record includes:

- **slug**: URL-friendly identifier for the space
- **name**: Human-readable name
- **description**: Detailed description (optional, may be null)
- **type**: Type of space (e.g., "project", "team", "class")
- **role**: Your role within the space (e.g., "owner", "admin", "user")
- **visibility_type**: Whether the space is private or public
- **database_tables_enabled**: Whether this space supports database tables
- **video_library_enabled**: Whether this space supports a video library
- **archive_by_date**: Archival policy date (optional)
- **creation_timestamp**: When the space was created
- **last_modified_timestamp**: When the space was last modified
- **archival_timestamp**: When the space was archived (if applicable)

### Examples

```bash
# List spaces in an organization
nuvolos spaces list -o my_org

# List with JSON output
nuvolos spaces list -o my_org -f json

# List spaces (assuming org is in context)
nuvolos spaces list
```

## Next Steps

Once you have identified a space, you can:

1. Create instances: `nuvolos instances create -o my_org -s my_space -n "instance-name"`
2. List instances: `nuvolos instances list -o my_org -s my_space`
3. View applications: `nuvolos apps list -o my_org -s my_space -i my_instance`

## Related Commands

- [Organization Management](commands.md#organization-and-space-management) - List organizations
- [Instance Management](instance_management.md) - Create and manage instances in spaces
- [Application Management](app_management.md) - Create and manage applications
