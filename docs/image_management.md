# Image Management

This document provides details on how to manage Nuvolos images using the Nuvolos CLI.

## Overview

An image in Nuvolos represents a specific version of a Nuvolos application — for example, JupyterLab 4.5.6. Images are containerized and can be instantiated as applications within instances. The CLI provides commands to list, create, and update images.

!!! danger "Permission Required"
    Creating images requires the Image Manager role.
    If you need this role, contact support@nuvolos.cloud.

## Listing Images

The `nuvolos images list` command allows you to view all images accessible to your user.

### Usage

```bash
nuvolos images list [options]
```

### Options

- `-f, --format TEXT`: Sets the output format. Available values: `tabulated` (default), `json`, `yaml`
- `--help`: Show help message and exit.

### Examples

```bash
# List all images in tabulated format
nuvolos images list

# List all images as JSON
nuvolos images list -f json
```

## Creating Images

The `nuvolos images create` command allows you to create a new image record.

!!! danger "Permission Required"
    Only users with the Image Manager role can create images.
    To obtain this role, contact support@nuvolos.cloud.

### Usage

```bash
nuvolos images create [options]
```

### Required Options

- `-n, --name TEXT`: Name of the image
- `--docker-image-url TEXT`: Docker image URL (e.g., `registry/repo:tag`)
- `--description-md TEXT`: Markdown description of the image
- `--ifid INTEGER`: Image family ID to associate with

### Optional Options

- `-d, --description TEXT`: Short description of the image
- `--public / --no-public`: Whether the image is public (default: false)
- `--public-description TEXT`: Public-facing description for the image
- `-o, --org TEXT`: Organization slug to scope the image to (omit for global access)
- `-s, --space TEXT`: Space slug to scope the image to (requires org if specified)
- `--app-type TEXT`: Application type identifier (e.g., "jupyter", "rstudio")
- `--configuration TEXT`: JSON string of configuration parameters
- `--has-tables / --no-tables`: Whether the image supports database tables
- `--complexity INTEGER`: Complexity level of the image (for UI sorting/filtering)
- `--tags TEXT`: JSON string of tags for categorization
- `-f, --format TEXT`: Output format (`tabulated`, `json`, `yaml`)

### Examples

```bash
# Create a simple global image
nuvolos images create \
  -n "My Python App" \
  --docker-image-url "registry.example.com/my-python-app:v1.0" \
  --description-md "A Python application for data science" \
  --ifid 1

# Create an org-scoped image with configuration
nuvolos images create \
  -n "Jupyter Lab" \
  --docker-image-url "registry.example.com/jupyter:latest" \
  --description-md "Jupyter Lab environment" \
  --ifid 2 \
  -o my_org \
  --app-type jupyter \
  --configuration '{"cpu": "2", "memory": "4G"}' \
  --complexity 3

# Create a space-scoped image with metadata
nuvolos images create \
  -n "R Studio" \
  --docker-image-url "registry.example.com/rstudio:latest" \
  --description-md "RStudio server environment" \
  --ifid 3 \
  -o my_org \
  -s my_space \
  --app-type rstudio \
  --tags '{"type": "ide", "language": "r"}' \
  --public \
  --public-description "Free RStudio environment"
```

## Updating Images

The `nuvolos images update` command allows you to modify an existing image record. Only provided fields are updated; others remain unchanged.

!!! danger "Permission Required"
    Only users with the Image Manager role can update images.
    To obtain this role, contact support@nuvolos.cloud.

### Usage

```bash
nuvolos images update IMID [options]
```

### Arguments

- `IMID`: The image ID to update (integer)

### Optional Options

- `-n, --name TEXT`: New name for the image
- `--docker-image-url TEXT`: New docker image URL
- `-d, --description TEXT`: New short description
- `--description-md TEXT`: New markdown description
- `--public-description TEXT`: New public-facing description
- `--app-type TEXT`: New application type identifier
- `--configuration TEXT`: JSON string of new configuration parameters
- `--complexity INTEGER`: New complexity level
- `--tags TEXT`: JSON string of new tags
- `-f, --format TEXT`: Output format (`tabulated`, `json`, `yaml`)

### Examples

```bash
# Update the name and description
nuvolos images update 42 \
  -n "Updated Python App" \
  -d "An improved version"

# Update to public with new description
nuvolos images update 42 \
  --public \
  --public-description "Now available to all users"

# Update configuration and tags
nuvolos images update 42 \
  --configuration '{"cpu": "4", "memory": "8G"}' \
  --tags '{"type": "premium", "language": "python"}'
```

## Image Families

An image family represents a Nuvolos application type — for example, JupyterLab — and groups all versioned images of that application together. See [image_families_management.md](image_families_management.md) for managing image families.

## Related Commands

- [Instance Management](instance_management.md) - Create instances to run applications
- [Application Management](app_management.md) - Create and manage applications from images
