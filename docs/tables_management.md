# Tables Management

This document provides details on how to manage snapshot tables using the Nuvolos CLI.

## Listing Tables

The `nuvolos tables list` command displays all tables in a snapshot.

### Usage

```bash
nuvolos tables list [options]
```

### Optional Options

- `-o, --org TEXT`: Organization slug (required if not in context)
- `-s, --space TEXT`: Space slug (required if not in context)
- `-i, --instance TEXT`: Instance slug (required if not in context)
- `-p, --snapshot TEXT`: Snapshot slug (default: `development`)
- `-f, --format TEXT`: Output format. Available values: `tabulated` (default), `json`, `yaml`
- `--help`: Show this message and exit

### Example

```bash
nuvolos tables list -o my_org -s my_space -i my_instance -p my_snapshot
```

## Getting Schema DDL

The `nuvolos tables schema-ddl` command returns the complete database schema DDL for a snapshot.

### Usage

```bash
nuvolos tables schema-ddl [options]
```

### Optional Options

- `-o, --org TEXT`: Organization slug (required if not in context)
- `-s, --space TEXT`: Space slug (required if not in context)
- `-i, --instance TEXT`: Instance slug (required if not in context)
- `-p, --snapshot TEXT`: Snapshot slug (default: `development`)
- `-f, --format TEXT`: Output format. Available values: `tabulated` (default), `json`, `yaml`

### Example

```bash
nuvolos tables schema-ddl -o my_org -s my_space -i my_instance -p my_snapshot -f json
```

## Getting Table Columns

The `nuvolos tables columns` command returns all columns for a specified table.

### Usage

```bash
nuvolos tables columns TABLE [options]
```

### Arguments

- `TABLE`: **Required**. The slug of the table to inspect.

### Optional Options

- `-o, --org TEXT`: Organization slug (required if not in context)
- `-s, --space TEXT`: Space slug (required if not in context)
- `-i, --instance TEXT`: Instance slug (required if not in context)
- `-p, --snapshot TEXT`: Snapshot slug (default: `development`)
- `-f, --format TEXT`: Output format. Available values: `tabulated` (default), `json`, `yaml`

### Example

```bash
nuvolos tables columns experiment_results -o my_org -s my_space -i my_instance
```

## Getting Table DDL

The `nuvolos tables ddl` command returns the DDL for a specified table.

### Usage

```bash
nuvolos tables ddl TABLE [options]
```

### Arguments

- `TABLE`: **Required**. The slug of the table.

### Optional Options

- `-o, --org TEXT`: Organization slug (required if not in context)
- `-s, --space TEXT`: Space slug (required if not in context)
- `-i, --instance TEXT`: Instance slug (required if not in context)
- `-p, --snapshot TEXT`: Snapshot slug (default: `development`)
- `-f, --format TEXT`: Output format. Available values: `tabulated` (default), `json`, `yaml`

### Example

```bash
nuvolos tables ddl experiment_results -o my_org -s my_space -i my_instance -f json
```

## Renaming Tables

The `nuvolos tables rename` command updates a table's slug or display name.

### Usage

```bash
nuvolos tables rename TABLE [options]
```

### Arguments

- `TABLE`: **Required**. The slug of the table to rename.

### Optional Options

- `--new-slug TEXT`: New table slug
- `--new-name TEXT`: New table display name
- `-o, --org TEXT`: Organization slug (required if not in context)
- `-s, --space TEXT`: Space slug (required if not in context)
- `-i, --instance TEXT`: Instance slug (required if not in context)
- `-p, --snapshot TEXT`: Snapshot slug (default: `development`)
- `-f, --format TEXT`: Output format. Available values: `tabulated` (default), `json`, `yaml`

At least one of `--new-slug` or `--new-name` is required.

### Examples

1. **Rename table slug:**

   ```bash
   nuvolos tables rename experiment_results --new-slug experiment_results_archive \
     -o my_org -s my_space -i my_instance
   ```

2. **Update table display name:**

   ```bash
   nuvolos tables rename experiment_results --new-name "Experiment Results Archive" \
     -o my_org -s my_space -i my_instance
   ```

## Deleting Tables

The `nuvolos tables delete` command removes a table from a snapshot.

### Usage

```bash
nuvolos tables delete TABLE [options]
```

### Arguments

- `TABLE`: **Required**. The slug of the table to delete.

### Optional Options

- `-o, --org TEXT`: Organization slug (required if not in context)
- `-s, --space TEXT`: Space slug (required if not in context)
- `-i, --instance TEXT`: Instance slug (required if not in context)
- `-p, --snapshot TEXT`: Snapshot slug (default: `development`)

### Example

```bash
nuvolos tables delete experiment_results_archive -o my_org -s my_space -i my_instance
```
