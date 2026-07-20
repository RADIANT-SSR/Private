"""``radiant convert`` subcommand — unit conversion utility."""

from __future__ import annotations

import sys

import click

from radiant.api.units import convert, input_units, targets_for


@click.command()
@click.argument("value", type=float)
@click.argument("from_unit")
@click.argument("to_unit")
def convert_cmd(value: float, from_unit: str, to_unit: str) -> None:
    """Convert a value between RADIANT-supported units.

    Example::

        radiant convert 18 um m
        radiant convert 45 deg rad
        radiant convert 5 ms s
    """
    try:
        result = convert(value, from_unit, to_unit)
    except KeyError:
        click.echo(f"Error: no conversion from '{from_unit}' to '{to_unit}'.", err=True)
        # List available conversions for the from_unit.
        targets = targets_for(from_unit)
        if targets:
            click.echo(f"  '{from_unit}' can convert to: {', '.join(targets)}", err=True)
        else:
            # Show all available from-units.
            click.echo(f"  Available units: {', '.join(input_units())}", err=True)
        sys.exit(1)

    click.echo(f"{value} {from_unit} = {result:g} {to_unit}")
