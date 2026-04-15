"""RADIANT CLI — Click entry point.

Usage::

    radiant run config.yaml [--set key=value ...]
    radiant validate config.yaml [--set key=value ...]
    radiant explain config.yaml param.name
    radiant sweep config.yaml param.name --min V --max V
    radiant tolerance config.yaml --trials N
    radiant compare config1.yaml config2.yaml
    radiant schema [--stage NAME]
    radiant template list|show|create
    radiant convert VALUE FROM_UNIT TO_UNIT
"""

import click

from radiant.cli.compare import compare
from radiant.cli.convert import convert_cmd
from radiant.cli.explain import explain
from radiant.cli.run import run
from radiant.cli.schema_cmd import schema_cmd
from radiant.cli.sweep_cmd import sweep_cmd
from radiant.cli.templates import template
from radiant.cli.tolerance_cmd import tolerance_cmd
from radiant.cli.validate import validate


@click.group()
@click.version_option(package_name="radiant")
def cli() -> None:
    """RADIANT — first-principles EO sensor performance modeling."""


cli.add_command(run)
cli.add_command(validate)
cli.add_command(compare)
cli.add_command(convert_cmd, "convert")
cli.add_command(explain)
cli.add_command(schema_cmd, "schema")
cli.add_command(sweep_cmd, "sweep")
cli.add_command(template)
cli.add_command(tolerance_cmd, "tolerance")
