# Distribution Management

This document provides details on how to distribute content between Nuvolos instances using the Nuvolos CLI.

## Overview

The distribution feature allows you to push files, applications, and database tables from a source snapshot to the development snapshot of one or more target instances. This is useful for sharing course materials, publishing analysis results, or synchronizing content across multiple instances.

## Distributing Content

The `nuvolos distribution distribute` command distributes selected content from a snapshot to target instances. Distribution is an asynchronous operation; use `--wait` to block until completion, or monitor the returned task ID with `nuvolos tasks get`.

### Usage

```bash
nuvolos distribution distribute --targets <json> [options]
```

### Arguments

- `--targets TEXT`: **Required**. JSON array of target instances. Each entry must have `org_slug`, `space_slug`, and `instance_slug`. Content distributes to the **development** snapshot of each target.

### Optional Options

- `-o, --org TEXT`: Organization slug of the source instance (required if not in context)
- `-s, --space TEXT`: Space slug of the source instance (required if not in context)
- `-i, --instance TEXT`: Instance slug of the source instance (required if not in context)
- `-p, --snapshot TEXT`: Snapshot slug to distribute from (default: `development`)
- `--apps TEXT`: Comma-separated application slugs to distribute
- `--files TEXT`: Comma-separated file OS paths to distribute (not slugs)
- `--tables TEXT`: Comma-separated table names to distribute (actual table names, not slugs)
- `--auto-snapshot`: Create a snapshot of each target instance before distributing (default: no)
- `--notify`: Notify target users by email when distribution completes (default: no)
- `--message TEXT`: Custom email message for the notification
- `-w, --wait`: Wait until the distribution task completes before returning
- `-f, --format TEXT`: Output format. Available values: `tabulated` (default), `json`, `yaml`
- `--help`: Show this message and exit

### Examples

1. **Distribute a single file to one target:**

   ```bash
   nuvolos distribution distribute \
     -o my_org -s my_space -i my_instance \
     --targets '[{"org_slug": "my_org", "space_slug": "target_space", "instance_slug": "target_instance"}]' \
     --files "/files/results/report.csv"
   ```

2. **Distribute multiple applications to multiple targets:**

   ```bash
   nuvolos distribution distribute \
     -o my_org -s my_space -i my_instance \
     --targets '[{"org_slug": "my_org", "space_slug": "class_space", "instance_slug": "student_001"}, {"org_slug": "my_org", "space_slug": "class_space", "instance_slug": "student_002"}]' \
     --apps "jupyter_lab,rstudio"
   ```

3. **Distribute with notification and wait for completion:**

   ```bash
   nuvolos distribution distribute \
     -o my_org -s my_space -i my_instance -p my_snapshot \
     --targets '[{"org_slug": "my_org", "space_slug": "target_space", "instance_slug": "target_instance"}]' \
     --files "/files/data/dataset.csv" \
     --tables "results,summary" \
     --notify --message "New dataset and results are available." --wait
   ```

4. **Distribute with auto-snapshot for safety:**

   ```bash
   nuvolos distribution distribute \
     -o my_org -s my_space -i my_instance \
     --targets '[{"org_slug": "my_org", "space_slug": "target_space", "instance_slug": "target_instance"}]' \
     --files "/files/config/settings.yaml" \
     --auto-snapshot --wait
   ```
