# LFS Management

This document provides details on how to manage Large File Storage (LFS) shares attached to a Nuvolos space using the Nuvolos CLI.

## Listing LFS Shares

The `nuvolos lfs list` command lists the active LFS shares attached to a space.

### Usage

```bash
nuvolos lfs list [options]
```

### Optional Options

- `-o, --org TEXT`: Organization slug (required if not in context)
- `-s, --space TEXT`: Space slug (required if not in context)
- `-f, --format TEXT`: Output format. Available values: `tabulated` (default), `json`, `yaml`
- `--help`: Show this message and exit

### Example

```bash
nuvolos lfs list -o my_org -s my_space
```

## Cleaning Up an LFS Share

The `nuvolos lfs cleanup` command removes incomplete multipart uploads to an LFS share. Cleanup is an asynchronous operation; use `--wait` to block until completion, or monitor the returned task ID with `nuvolos tasks get`.

### Usage

```bash
nuvolos lfs cleanup --afsid <id> [options]
```

### Options

- `--afsid INTEGER`: **Required**. The id of the LFS share to clean up.
- `-o, --org TEXT`: Organization slug (required if not in context)
- `-s, --space TEXT`: Space slug (required if not in context)
- `-w, --wait`: Wait until the cleanup task completes before returning
- `-f, --format TEXT`: Output format. Available values: `tabulated` (default), `json`, `yaml`
- `--help`: Show this message and exit

### Example

```bash
nuvolos lfs cleanup -o my_org -s my_space --afsid 123 --wait
```
