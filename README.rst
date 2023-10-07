.. _nuvolos-cli:

Nuvolos CLI
===========

Nuvolos CLI is command-line interface (CLI) for the `Nuvolos <https://nuvolos.cloud>`_ platform. It allows you to interact with the Nuvolos platform from your local terminal.

For installation and detailed usage, check out the `documentation <https://nuvolos-cli.readthedocs.io/en/latest/>`_.

Installation
------------

You can install the latest stable version using pip with

.. code-block:: console

    pip install nuvolos-cli

Usage
-----

You can invoke the Nuvolos CLI with the shell command ``nuvolos-cli``.

Configuration
-------------

The Nuvolos CLI requires a configuration file to be present in your home directory. The configuration file is named ``.nuvolos.yaml`` and is automatically created when you run the ``nuvolos-cli`` command for the first time. 

You can set your Nuvolos API key with the ``config`` command in the CLI:

.. code-block:: console

    (nuvolos-cli) config <YOUR_API_KEY>

Commands
--------

You can list of available commands with the ``?`` command:

.. code-block:: console

    (nuvolos-cli) ?
