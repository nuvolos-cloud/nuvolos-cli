# Session Management

This document provides details on how to manage and monitor Nuvolos application sessions using the Nuvolos CLI.

## Overview

Sessions represent individual user interactions with running Nuvolos applications. Each session tracks resource usage, timing information, and associated logs. The CLI provides commands to list sessions and retrieve their logs.

## Listing Sessions

The `nuvolos sessions list` command allows you to view all sessions for a specific application.

### Usage

```bash
nuvolos sessions list [options]
```

### Required Options

- `-a, --app TEXT`: Application slug

### Optional Options

- `-o, --org TEXT`: Organization slug (required if not in context)
- `-s, --space TEXT`: Space slug (required if not in context)
- `-i, --instance TEXT`: Instance slug (required if not in context)
- `--page INTEGER`: Page number for pagination (default: 1)
- `--per-page INTEGER`: Results per page (default: 100)
- `--session-id TEXT`: Filter by a specific session ID
- `--sort TEXT`: Sort order (`asc` or `desc`; default: `desc`)
- `-f, --format TEXT`: Output format (`tabulated`, `json`, `yaml`)

### Session Information

Each session record includes:

- **session_id**: Unique identifier for the session
- **start_time**: When the user connected to the application
- **stop_time**: When the user disconnected (null if still active)
- **start_uid**: User ID who started the session
- **start_uid_full_name**: Full name of the user
- **stop_uid**: User ID who stopped the session (if applicable)
- **runtime_seconds**: Total session duration
- **ncu**: Number of compute units used
- **ncu_hours_used**: Normalized compute unit hours
- **credits_spent**: Credit usage
- **node_pool**: Which node pool the session ran on
- **active_resource**: Current resource type
- **logging_containers**: List of containers with available logs
- **can_read_logs**: Whether you can read logs for this session

### Examples

```bash
# List all sessions for an application
nuvolos sessions list -o my-org -s my-space -i my-instance -a my-app

# List sessions with specific sorting
nuvolos sessions list -o my-org -s my-space -i my-instance -a my-app --sort asc

# List specific session by ID
nuvolos sessions list \
  -o my-org -s my-space -i my-instance \
  -a my-app \
  --session-id abc123def456

# List sessions with pagination
nuvolos sessions list \
  -o my-org -s my-space -i my-instance \
  -a my-app \
  --page 2 --per-page 50

# List as JSON for processing
nuvolos sessions list \
  -o my-org -s my-space -i my-instance \
  -a my-app \
  -f json

# List sessions with context (if configured)
nuvolos sessions list -a my-app
```

## Retrieving Session Logs

The `nuvolos sessions logs` command allows you to retrieve logs from a specific session and container.

### Usage

```bash
nuvolos sessions logs [options]
```

### Required Options

- `--session-id TEXT`: The session ID to get logs for
- `-c, --container TEXT`: Container name to get logs from

### Optional Options

- `--max-lines INTEGER`: Maximum number of log lines to return (default: 100)
- `--from-start TEXT`: ISO datetime to start reading logs from (e.g., `2025-05-26T10:30:00Z`)
- `-f, --format TEXT`: Output format (`tabulated` or `json`; default: `tabulated`)
- `--columns TEXT`: Comma-separated list of columns to include in output (e.g., `msg,ts`)

### Details

- Container names can be found in the session record's `logging_containers` field
- The `from-start` parameter accepts ISO 8601 format timestamps
- Log lines are returned in reverse chronological order by default (most recent first)
- Default output is a markdown-style table suitable for terminal viewing
- Use `-f json` to get the raw JSON payload format
- `--columns` can be combined with either output format to project specific fields
- The maximum lines limit helps prevent overwhelming output for long-running sessions

### Examples

```bash
# Get recent logs from a session
nuvolos sessions logs \
  --session-id abc123def456 \
  -c jupyter

# Get logs as JSON
nuvolos sessions logs \
  --session-id abc123def456 \
  -c main-app \
  -f json

# Show only selected columns in table output
nuvolos sessions logs \
  --session-id abc123def456 \
  -c main-app \
  --columns "msg,ts"

# Get more log lines
nuvolos sessions logs \
  --session-id abc123def456 \
  -c main-app \
  --max-lines 500

# Get logs from a specific time onwards
nuvolos sessions logs \
  --session-id abc123def456 \
  -c worker \
  --from-start "2025-05-26T14:00:00Z"

# Get logs from multiple common containers
# (run separately for each container)
nuvolos sessions logs --session-id abc123def456 -c app
nuvolos sessions logs --session-id abc123def456 -c sidecar
nuvolos sessions logs --session-id abc123def456 -c init
```

## Understanding Session Logs

Session logs help you debug application behavior and monitor performance:

- **Application container**: Main application logs (e.g., `jupyter`, `rstudio`, `app`)
- **Sidecar containers**: Supporting services (monitoring, networking, etc.)
- **Init containers**: Setup and initialization logs

The availability of logs depends on:
- Whether the container is configured to produce logs
- Whether log persistence is enabled
- Your permissions for the space/instance
- Whether the session is still active or archived

## Related Commands

- [Application Management](app_management.md) - Start, stop, and manage applications
- [Task Management](commands.md#tasks) - Monitor asynchronous operations like derivation
- [Snapshot Management](snapshot_management.md) - Manage instance snapshots
