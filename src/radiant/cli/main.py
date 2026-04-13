"""RADIANT CLI — Click entry point.

Usage::

    radiant run config.yaml [--set key=value ...]
    radiant validate config.yaml [--set key=value ...]
"""

import click

from radiant.cli.run import run
from radiant.cli.validate import validate


@click.group()
@click.version_option(package_name="radiant")
def cli() -> None:
    """RADIANT — first-principles EO sensor performance modeling."""


cli.add_command(run)
cli.add_command(validate)
