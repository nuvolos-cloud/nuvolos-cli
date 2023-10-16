from setuptools import setup
from setuptools.command.install import install


class PostInstallCommand(install):
    """Post-installation for installation mode."""

    def run(self):
        install.run(self)
        # Custom post-install commands could come here


def readme():
    with open("README.rst") as f:
        return f.read()


exec(open("nuvolos_cli/version.py").read())
setup(
    name="nuvolos-cli",
    version=__version__,
    description="Command-line interface for Nuvolos",
    long_description=readme(),
    url="https://github.com/nuvolos-cloud/nuvolos-cli",
    author="Alphacruncher",
    author_email="support@nuvolos.cloud",
    license="MIT",
    packages=["nuvolos_cli"],
    install_requires=[
        f"Nuvolos-Client-API=={__nuvolos_client_api_version__}",
        "click",
        "click-log",
        "pyyaml",
        "semver",
        "tabulate",
    ],
    zip_safe=False,
    entry_points={
        "console_scripts": [
            "nuvolos=nuvolos_cli.interface:nuvolos",
        ],
    },
    cmdclass={"install": PostInstallCommand},
    include_package_data=True,
    setup_requires=["pytest-runner"],
    tests_require=["pytest"],
)
