# Application Management

This document provides details on how to manage Nuvolos applications using the Nuvolos CLI.

## Overview

Applications in Nuvolos are instantiations of container images within a specific snapshot of an instance. The CLI provides commands to list, create, start, stop, and manage applications.

## Listing Applications

The `nuvolos apps list` command allows you to view all applications in a specified snapshot.

### Usage

```bash
nuvolos apps list [options]
```

### Options

- `-o, --org TEXT`: Organization slug
- `-s, --space TEXT`: Space slug
- `-i, --instance TEXT`: Instance slug
- `-p, --snapshot TEXT`: Snapshot slug (default: "development")
- `-f, --format TEXT`: Output format. Available values: `tabulated` (default), `json`, `yaml`
- `--help`: Show help message and exit.

### Examples

```bash
# List applications in the development snapshot
nuvolos apps list -o my-org -s my-space -i my-instance

# List applications in a specific snapshot
nuvolos apps list -o my-org -s my-space -i my-instance -p my-snapshot

# List with JSON output
nuvolos apps list -o my-org -s my-space -i my-instance -f json
```

## Creating Applications

The `nuvolos apps create` command allows you to create a new application in the development snapshot of a specified instance.

### Usage

```bash
nuvolos apps create [options]
```

### Required Options

- `--imid INTEGER`: Image ID to use for the application
- `-n, --name TEXT`: Long display name for the application (used in the UI)

### Optional Options

- `-o, --org TEXT`: Organization slug (required if not in context)
- `-s, --space TEXT`: Space slug (required if not in context)
- `-i, --instance TEXT`: Instance slug (required if not in context)
- `-d, --description TEXT`: Description of the application
- `--pars TEXT`: JSON string of application parameters
- `-f, --format TEXT`: Output format (`tabulated`, `json`, `yaml`)

### Details

- Applications are created in the **development** snapshot by default
- The application slug is automatically generated and returned in the response
- Parameters are passed as a JSON string and are application-specific
- The image ID (imid) must correspond to an existing image that you have access to

### Examples

```bash
# Create a simple application from an image
nuvolos apps create \
  -o my-org \
  -s my-space \
  -i my-instance \
  --imid 42 \
  -n "Data Science Lab"

# Create an application with description and parameters
nuvolos apps create \
  -o my-org \
  -s my-space \
  -i my-instance \
  --imid 42 \
  -n "Jupyter Notebook" \
  -d "Jupyter Lab for data analysis" \
  --pars '{"theme": "dark", "notebook_dir": "/home/user/notebooks"}'

# Create an application (assuming context is set)
nuvolos apps create \
  --imid 10 \
  -n "RStudio Analysis"
```

## Deriving Applications

The `nuvolos apps derive` command creates a derived image from an existing application, capturing its current state as a new image.

### Usage

```bash
nuvolos apps derive [options]
```

### Required Options

- `-a, --app TEXT`: Slug of the application to derive from

### Optional Options

- `-o, --org TEXT`: Organization slug (required if not in context)
- `-s, --space TEXT`: Space slug (required if not in context)
- `-i, --instance TEXT`: Instance slug (required if not in context)
- `-t, --tag TEXT`: Image tag for the derived image
- `-e, --email / --no-email`: Send email when derivation is finished (default: yes)
- `-w, --wait`: Wait until the derivation task is complete
- `-f, --format TEXT`: Output format (`tabulated`, `json`, `yaml`)

### Details

- Deriving an application creates a new image based on the current state of the application
- This is useful for creating customized versions of applications with specific configurations or packages installed
- The operation is asynchronous and returns a task ID that can be monitored
- If `--wait` is specified, the CLI will poll the task status until completion
- Use `nuvolos tasks get TKID` to check task status anytime

### Examples

```bash
# Derive an application with default settings
nuvolos apps derive \
  -o my-org \
  -s my-space \
  -i my-instance \
  -a my-app-slug

# Derive with custom tag and email notification
nuvolos apps derive \
  -o my-org \
  -s my-space \
  -i my-instance \
  -a my-app-slug \
  -t "custom-v1.0" \
  -e

# Derive and wait for completion
nuvolos apps derive \
  -o my-org \
  -s my-space \
  -i my-instance \
  -a my-app-slug \
  -w

# Derive without email notification
nuvolos apps derive \
  -o my-org \
  -s my-space \
  -i my-instance \
  -a my-app-slug \
  --no-email
```

## Starting Applications

The `nuvolos apps start` command launches a Nuvolos application.

### Usage

```bash
nuvolos apps start APP [options]
```

### Arguments

- `APP`: The slug of the application to start

### Options

- `-o, --org TEXT`: Organization slug
- `-s, --space TEXT`: Space slug
- `-i, --instance TEXT`: Instance slug
- `-n, --node-pool TEXT`: Node pool to use for running the application
- `-w, --wait`: Wait until the application is running
- `-f, --format TEXT`: Output format
- `--help`: Show help message and exit.

### Examples

```bash
# Start an application
nuvolos apps start my-app-slug -o my-org -s my-space -i my-instance

# Start on a specific node pool
nuvolos apps start my-app-slug -o my-org -s my-space -i my-instance -n gpu-pool

# Start and wait for application to be ready
nuvolos apps start my-app-slug -o my-org -s my-space -i my-instance -w
```

## Stopping Applications

The `nuvolos apps stop` command stops a running Nuvolos application.

### Usage

```bash
nuvolos apps stop [options]
```

### Options

- `-o, --org TEXT`: Organization slug
- `-s, --space TEXT`: Space slug
- `-i, --instance TEXT`: Instance slug
- `-a, --app TEXT`: **Required**. Application slug to stop
- `-f, --format TEXT`: Output format

### Examples

```bash
# Stop an application
nuvolos apps stop -a my-app-slug -o my-org -s my-space -i my-instance
```

## Listing Running Applications

The `nuvolos apps running` command lists all running applications or workloads for a specific application.

### Usage

```bash
nuvolos apps running [options]
```

### Options

- `-o, --org TEXT`: Organization slug
- `-s, --space TEXT`: Space slug
- `-i, --instance TEXT`: Instance slug
- `-a, --app TEXT`: Application slug (optional; lists workloads for specific app if provided)
- `-f, --format TEXT`: Output format

### Examples

```bash
# List all running applications globally
nuvolos apps running

# List running workloads for a specific application
nuvolos apps running -o my-org -s my-space -i my-instance -a my-app-slug
```

## Executing Commands in Applications

The `nuvolos apps execute` command runs a command in a running application.

### Usage

```bash
nuvolos apps execute [options] COMMAND
```

### Arguments

- `COMMAND`: The command to execute in the application

### Options

- `-o, --org TEXT`: Organization slug
- `-s, --space TEXT`: Space slug
- `-i, --instance TEXT`: Instance slug
- `-a, --app TEXT`: **Required**. Application slug where command runs
- `-f, --format TEXT`: Output format

### Examples

```bash
# Execute a simple command
nuvolos apps execute -a my-app-slug -o my-org -s my-space -i my-instance "ls -la"

# Execute a Python command
nuvolos apps execute -a my-app-slug "python -c 'import numpy; print(numpy.__version__)'"

# Execute a longer running command
nuvolos apps execute -a my-app-slug "python training_script.py"
```

## Listing Node Pools

The `nuvolos apps nodepools` command shows all available node pools for launching applications.

### Usage

```bash
nuvolos apps nodepools [options]
```

### Options

- `-f, --format TEXT`: Output format

### Examples

```bash
# List available node pools
nuvolos apps nodepools

# List as JSON
nuvolos apps nodepools -f json
```

## Related Commands

- [Image Management](image_management.md) - View available images to create applications from
- [Session Management](session_management.md) - Monitor application sessions and logs
- [Snapshot Management](snapshot_management.md) - Manage instance snapshots
- [Tasks](commands.md#tasks) - Monitor long-running operations
