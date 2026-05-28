# Image Families Management

This document provides details on how to manage Nuvolos image families using the Nuvolos CLI.

## Overview

An image family represents a Nuvolos application type — for example, JupyterLab — and appears as a tile in the Nuvolos App gallery. It groups all versioned images of that application (e.g., JupyterLab 4.5.6) together under a single entry. Each image belongs to exactly one family, and families automatically manage priority ordering.

!!! danger "Permission Required"
    Creating image families requires the Image Manager role.
    If you need this role, contact support@nuvolos.cloud.

## Listing Image Families

The `nuvolos image-families list` command allows you to view all available image families.

### Usage

```bash
nuvolos image-families list [options]
```

### Options

- `-f, --format TEXT`: Sets the output format. Available values: `tabulated` (default), `json`, `yaml`
- `--help`: Show help message and exit.

### Examples

```bash
# List all image families
nuvolos image-families list

# List image families as JSON
nuvolos image-families list -f json

# List image families as YAML
nuvolos image-families list -f yaml
```

## Creating Image Families

The `nuvolos image-families create` command allows you to create a new image family.

!!! danger "Permission Required"
    Only users with the Image Manager role can create image families.
    To obtain this role, contact support@nuvolos.cloud.

### Usage

```bash
nuvolos image-families create [options]
```

### Required Options

- `-n, --name TEXT`: Name of the image family
- `--icon-url TEXT`: URL of the icon representing the image family

### Optional Options

- `-d, --description TEXT`: Description of the image family
- `--groups TEXT`: Comma-separated list of group identifiers
- `-f, --format TEXT`: Output format (`tabulated`, `json`, `yaml`)

### Details

- The priority for a new image family is automatically set to one more than the highest existing priority
- Icons should be accessible via a public URL for proper display in the Nuvolos UI
- Groups can be used to organize and categorize related image families

### Examples

```bash
# Create a simple image family
nuvolos image-families create \
  -n "Data Science" \
  --icon-url "https://example.com/icons/data-science.png"

# Create an image family with description and groups
nuvolos image-families create \
  -n "Development Tools" \
  --icon-url "https://example.com/icons/dev-tools.png" \
  -d "IDEs and development environments" \
  --groups "ide,editor,development"

# Create an image family with multiple groups
nuvolos image-families create \
  -n "Analytics Platforms" \
  --icon-url "https://example.com/icons/analytics.png" \
  -d "Analytics and visualization tools" \
  --groups "analytics,visualization,business_intelligence"
```

## Related Commands

- [Image Management](image_management.md) - Create and manage images
- [Image Links](image_links_management.md) - Manage image availability scoping
