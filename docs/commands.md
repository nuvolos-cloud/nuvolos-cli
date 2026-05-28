# Command reference

Overview of all Nuvolos CLI commands

## Auto-generated Reference

::: mkdocs-click
    :module: nuvolos_cli.interface
    :command: nuvolos
    :prog_name: nuvolos

## Command Groups

The Nuvolos CLI is organized into the following command groups:

### Organization and Space Management
- `nuvolos orgs list` - List organizations
- `nuvolos spaces list` - List spaces in an organization

### Instance Management
- `nuvolos instances list` - List instances in a space
- `nuvolos instances create` - Create a new instance

See [Instance Management](instance_management.md) for detailed usage.

### Snapshot Management
- `nuvolos snapshots list` - List snapshots in an instance
- `nuvolos snapshots create` - Create a new snapshot
- `nuvolos snapshots delete` - Delete a snapshot

See [Snapshot Management](snapshot_management.md) for detailed usage.

### Application Management
- `nuvolos apps list` - List applications in a snapshot
- `nuvolos apps create` - Create a new application
- `nuvolos apps derive` - Derive an image from an application
- `nuvolos apps start` - Start an application
- `nuvolos apps stop` - Stop an application
- `nuvolos apps running` - List running applications or workloads
- `nuvolos apps execute` - Execute a command in an application
- `nuvolos apps nodepools` - List available node pools

See [Application Management](app_management.md) for detailed usage.

### Image Management
- `nuvolos images list` - List available images
- `nuvolos images create` - Create a new image
- `nuvolos images update` - Update an existing image

See [Image Management](image_management.md) for detailed usage.

### Image Families
- `nuvolos image-families list` - List image families
- `nuvolos image-families create` - Create a new image family

!!! danger "Permission Required"
    Creating image families requires the Image Manager role.
    To obtain this role, contact support@nuvolos.cloud.

See [Image Families Management](image_families_management.md) for detailed usage.

### Image Links
- `nuvolos image-links list` - List image links

See [Image Links Management](image_links_management.md) for detailed usage.

### Session Management
- `nuvolos sessions list` - List sessions for an application
- `nuvolos sessions logs` - Retrieve logs from a session (default markdown table output; supports `-f json` and `--columns`)

See [Session Management](session_management.md) for detailed usage.

### Task Management
- `nuvolos tasks get` - Get status of a task by ID

### Configuration and Info
- `nuvolos config` - Initialize CLI configuration
- `nuvolos info` - Display CLI information

