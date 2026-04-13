"""``radiant validate`` subcommand — check a config without running."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from radiant.api.session import RadiantSession
from radiant.io.config import ConfigError, load_config


@click.command()
@click.argument("config", type=click.Path(exists=False, dir_okay=False))
@click.option(
    "--set", "overrides", multiple=True,
    help="Parameter override in key=value format (repeatable).",
)
def validate(config: str, overrides: tuple[str, ...]) -> None:
    """Validate a YAML config file without running the chain.

    Checks that the file parses, all parameter names are known, types
    are correct, and all required parameters are set.

    Example::

        radiant validate examples/mwir_leo_minimal.yaml
    """
    config_path = Path(config)

    if not config_path.exists():
        click.echo(f"Error: file not found: {config_path}", err=True)
        sys.exit(1)

    # Load.
    try:
        params = RadiantSession.default_params()
        load_config(config_path, params)
    except ConfigError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # Apply overrides.
    from radiant.cli.run import _coerce_value, _parse_overrides

    try:
        parsed = _parse_overrides(overrides)
    except click.BadParameter as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    for key, raw_value in parsed.items():
        value = _coerce_value(raw_value)
        try:
            params.set(key, value)
        except KeyError:
            click.echo(f"Error: unknown parameter '{key}'.", err=True)
            sys.exit(1)

    # Resolve.
    try:
        params.resolve()
    except (ValueError, TypeError) as exc:
        click.echo(f"Validation failed: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Config OK: {config_path}")
    resolved = params.all_resolved()
    click.echo(f"  {len(resolved)} parameters resolved.")
