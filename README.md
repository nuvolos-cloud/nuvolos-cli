<!-- [![PyPI version](https://img.shields.io/pypi/v/nuvolos-cli)](https://pypi.org/project/nuvolos-cli/)  -->
[![Docs](https://readthedocs.org/projects/nuvolos-cli/badge/)](https://nuvolos-cli.readthedocs.io/en/latest/)
<!-- [![Integration tests](https://github.com/nuvolos-cloud/nuvolos-cli/actions/workflows/integration-test.yaml/badge.svg)](https://github.com/nuvolos-cloud/nuvolos-cli/actions/workflows/integration-test.yaml) -->


```
 _   _                  _              ____ _     ___ 
| \ | |_   ___   _____ | | ___  ___   / ___| |   |_ _|
|  \| | | | \ \ / / _ \| |/ _ \/ __| | |   | |    | | 
| |\  | |_| |\ V / (_) | | (_) \__ \ | |___| |___ | | 
|_| \_|\__,_| \_/ \___/|_|\___/|___/  \____|_____|___|
                                                      
```

Nuvolos CLI is command-line interface (CLI) for the [Nuvolos](https://nuvolos.cloud) platform. It allows you to interact with the Nuvolos platform from your local terminal.

For installation and detailed usage, check out the [documentation](https://nuvolos-cli.readthedocs.io/en/latest/).

## Installation

You can install the latest stable version using pip with

```
pip install nuvolos-cli
```

## Usage

You can invoke the Nuvolos CLI with the shell command `nuvolos`.

### Configuration

The Nuvolos CLI requires a configuration file to be present in your home directory. The configuration file is named `.nuvolos.yaml` and is automatically created when you run the `nuvolos` command for the first time. 

You can set your Nuvolos API key with the `config` command in the CLI:

```
nuvolos config --api-key <YOUR_API_KEY>
```