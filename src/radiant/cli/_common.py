"""Shared CLI utilities — override parsing, config loading, Sensor creation."""

from __future__ import annotations

import sys

import click

from radiant.api.sensor import Sensor


def parse_overrides(overrides: tuple[str, ...]) -> dict[str, str]:
    """Parse ``--set key=value`` pairs into a dict.

    Raises
    ------
    click.BadParameter
        If any override is not in ``key=value`` format.
    """
    result: dict[str, str] = {}
    for item in overrides:
        if "=" not in item:
            raise click.BadParameter(
                f"Override must be key=value, got: '{item}'",
                param_hint="'--set'",
            )
        key, _, value = item.partition("=")
        result[key.strip()] = value.strip()
    return result


def coerce_value(raw: str) -> int | float | str:
    """Best-effort coercion of a CLI string to int, float, or str."""
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def load_sensor(
    config: str,
    overrides: tuple[str, ...] = (),
) -> Sensor:
    """Load a Sensor from a config path with optional --set overrides.

    Exits with code 1 on any load/override error.
    """
    sensor = Sensor.from_yaml(config)

    if overrides:
        try:
            parsed = parse_overrides(overrides)
        except click.BadParameter as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(1)

        for key, raw_value in parsed.items():
            value = coerce_value(raw_value)
            try:
                sensor.set(key, value)
            except KeyError:
                click.echo(
                    f"Error: unknown parameter '{key}'. "
                    "Check spelling or run 'radiant schema' for available parameters.",
                    err=True,
                )
                sys.exit(1)

    return sensor


# Standard Click options reused across commands.
set_option = click.option(
    "--set", "overrides", multiple=True,
    help="Parameter override in key=value format (repeatable).",
)
