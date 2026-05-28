# Image Links Management

This document provides details on how to manage Nuvolos image links using the Nuvolos CLI.

## Overview

Image links are records that control the availability and visibility of images across different scopes (global, organization, and space). Image links determine which users have access to specific images based on their organization and space roles.

## Listing Image Links

The `nuvolos image-links list` command allows you to view all image links accessible to the current user.

### Usage

```bash
nuvolos image-links list [options]
```

### Options

- `-f, --format TEXT`: Sets the output format. Available values: `tabulated` (default), `json`, `yaml`
- `--help`: Show help message and exit.

### Scope Rules

Image links are returned based on the following access rules:

- **Global links**: Records where both organization and space are NULL are accessible to all authenticated users
- **Organization-scoped links**: Records with a specific organization are accessible if you have an active organization role for that org
- **Space-scoped links**: Records with a specific space are accessible if you have an active space role for that space

### Examples

```bash
# List all accessible image links
nuvolos image-links list

# List image links as JSON (useful for processing)
nuvolos image-links list -f json

# List image links as YAML
nuvolos image-links list -f yaml
```

## Understanding Image Links

When you create an image (see [Image Management](image_management.md)), image link records are automatically created to define its availability:

- **Global images**: Created without organization or space scopes; accessible to everyone
- **Organization images**: Created with `--org` flag; accessible to members of that organization
- **Space images**: Created with both `--org` and `--space` flags; accessible to members of that space

Each image can have multiple image links for different scopes.

## Image Link Properties

Each image link record includes:

- **imid**: Image ID the link refers to
- **linkid**: Unique link identifier
- **org_slug**: Organization slug (NULL for global or space-scoped links)
- **space_slug**: Space slug (NULL for global or organization-scoped links)
- **priority**: Display priority within the scope
- **space_type**: Type of space (for filtering)
- **comment**: Optional descriptive comment

## Related Commands

- [Image Management](image_management.md) - Create and manage images
- [Image Families](image_families_management.md) - Organize images into families
