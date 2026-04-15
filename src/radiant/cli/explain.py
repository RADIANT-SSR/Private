"""``radiant explain`` subcommand — show parameter provenance."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from radiant.cli._common import load_sensor, set_option


@click.command()
@click.argument("config", type=click.Path(exists=True, dir_okay=False))
@click.argument("param")
@set_option
def explain(config: str, param: str, overrides: tuple[str, ...]) -> None:
    """Explain how a parameter got its value.

    Shows the value, unit, provenance, and derivation chain for the
    specified parameter.

    Example::

        radiant explain examples/mwir_leo_minimal.yaml optics.f_number
    """
    sensor = load_sensor(config, overrides)

    try:
        text = sensor.explain(param)
    except (KeyError, RuntimeError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if "is not resolved" in text:
        click.echo(f"Error: {text}", err=True)
        sys.exit(1)

    click.echo(text)
