# Files Management

This document provides details on how to list files from Nuvolos snapshot areas using the Nuvolos CLI.

## Listing Files

The `nuvolos files list` command allows you to view files in a snapshot area. You can list files from either the shared `files` area or your user `home` area, optionally filtered by path.

### Usage

```bash
nuvolos files list [options]
```

### Optional Options

- `-o, --org TEXT`: Organization slug (required if not in context)
- `-s, --space TEXT`: Space slug (required if not in context)
- `-i, --instance TEXT`: Instance slug (required if not in context)
- `-p, --snapshot TEXT`: Snapshot slug (default: `development`)
- `-a, --area [files|home]`: Area to list files from (default: `files`)
- `--path TEXT`: Optional path inside the selected area (default: root)
- `-f, --format TEXT`: Output format. Available values: `tabulated` (default), `json`, `yaml`
- `--help`: Show this message and exit

### Examples

1. **List the files area root:**

   ```bash
   nuvolos files list -o my_org -s my_space -i my_instance
   ```

2. **List a specific path in the files area:**

   ```bash
   nuvolos files list -o my_org -s my_space -i my_instance --path "datasets_2026"
   ```

3. **List home area in a different snapshot:**

   ```bash
   nuvolos files list -o my_org -s my_space -i my_instance -p archive_2026 -a home
   ```

4. **Output as JSON:**

   ```bash
   nuvolos files list -o my_org -s my_space -i my_instance -a home --path "notebooks" -f json
   ```
