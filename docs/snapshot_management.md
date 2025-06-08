# Snapshot Management

This document provides details on how to manage instance snapshots using the Nuvolos CLI.

## Creating Snapshots

The `nv snapshots create` command allows you to create a new snapshot for a specified instance.

### Usage

```bash
nuvolos snapshots create -n <snapshot-name> [options]
```

### Arguments

*   `-n, --name TEXT`: **Required**. The name of the snapshot to create.

### Options

*   `-o, --org TEXT`: The slug of the Nuvolos organization. If not provided, the CLI will attempt to use the organization from the current context or a configured default.
*   `-s, --space TEXT`: The slug of the Nuvolos space. If not provided, the CLI will attempt to use the space from the current context or a configured default.
*   `-i, --instance TEXT`: The slug of the Nuvolos instance. If not provided, the CLI will attempt to use the instance from the current context or a configured default.
*   `-d, --description TEXT`: An optional description for the snapshot.
*   `-e, --email`: Send an email notification when snapshot creation is complete.
*   `-w, --wait`: Wait until snapshot creation is complete before returning. The CLI will poll the task status.
*   `-f, --format TEXT`: Sets the output into the desired format. Available values: `tabulated` (default), `json`, `yaml`.
*   `--help`: Show this message and exit.

### Examples

1.  **Create a basic snapshot:**

    ```bash
    nuvolos snapshots create -o my-org -s my-space -i my-instance -n "my-first-snapshot"
    ```

2.  **Create a snapshot with a description and wait for completion:**

    ```bash
    nuvolos snapshots create -n "important-backup" -d "Backup before major changes" -w
    ```
    (Assuming org, space, and instance are set in the current context)

3.  **Create a snapshot and receive an email notification:**

    ```bash
    nuvolos snapshots create -n "nightly-backup" -e
    ```

## Deleting Snapshots

The `nv snapshots delete` command allows you to delete an existing snapshot.

### Usage

```bash
nuvolos snapshots delete -p <snapshot-slug> [options]
```

### Arguments

*   `-p, --snapshot TEXT`: **Required**. The slug of the snapshot to delete.

### Options

*   `-o, --org TEXT`: The slug of the Nuvolos organization.
*   `-s, --space TEXT`: The slug of the Nuvolos space.
*   `-i, --instance TEXT`: The slug of the Nuvolos instance.
*   `-w, --wait`: Wait until snapshot deletion is complete before returning.
*   `-f, --format TEXT`: Sets the output into the desired format. Available values: `tabulated` (default), `json`, `yaml`.
*   `--help`: Show this message and exit.

### Examples

1.  **Delete a snapshot:**

    ```bash
    nuvolos snapshots delete -o my-org -s my-space -i my-instance -p "my-old-snapshot"
    ```

2.  **Delete a snapshot and wait for the operation to complete:**

    ```bash
    nuvolos snapshots delete -p "snapshot-to-remove" -w
    ```
    (Assuming org, space, and instance are set in the current context)

---

For more information on managing contexts, please refer to the relevant CLI documentation.
