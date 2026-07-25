"""``radiant validate`` subcommand — check a config without running."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from radiant.api.config_io import normalize_element_document
from radiant.api.session import RadiantSession
from radiant.cli._common import coerce_value, parse_overrides, set_option
from radiant.io.config import ConfigError, load_config, unattached_section_error
from radiant.io.element_config import ElementConfigError


@click.command()
@click.argument("config", type=click.Path(exists=False, dir_okay=False))
@set_option
def validate(config: str, overrides: tuple[str, ...]) -> None:
    """Validate a YAML config file without running the chain.

    Checks that the file parses, all parameter names are known, types
    are correct, and all required parameters are set.  Reports all
    errors at once (not fail-fast).

    Example::

        radiant validate examples/mwir_leo_minimal.yaml
    """
    config_path = Path(config)
    errors: list[str] = []

    if not config_path.exists():
        click.echo(f"Error: file not found: {config_path}", err=True)
        sys.exit(1)

    # Load. Structured sections validate through the same facade Sensor uses
    # (native-grid structural + Kirchhoff checks, CU-153).
    sections: dict[str, object] = {}
    try:
        params = RadiantSession.default_params()
        load_config(config_path, params, sections_out=sections)
    except ConfigError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    if "optical_elements" in sections:
        try:
            normalize_element_document(sections["optical_elements"], base_dir=config_path.parent)
        except ElementConfigError as exc:
            errors.append(f"optical_elements: {exc}")
    # Sections this command cannot validate (today: `configurations:`, ADR-0010)
    # are reported, never silently accepted (Rule 17).
    unattached = sorted(set(sections) - {"optical_elements"})
    if unattached:
        click.echo(f"Error: {unattached_section_error(unattached, config_path)}", err=True)
        sys.exit(1)

    # Apply overrides — collect errors instead of exiting on first.
    try:
        parsed = parse_overrides(overrides)
    except click.BadParameter as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    for key, raw_value in parsed.items():
        value = coerce_value(raw_value)
        try:
            params.set(key, value)
        except KeyError:
            errors.append(f"Unknown parameter: '{key}'")

    # Resolve — collect resolve errors.
    try:
        params.resolve()
    except (ValueError, TypeError) as exc:
        errors.append(str(exc))

    if errors:
        click.echo("Validation failed:", err=True)
        for err in errors:
            click.echo(f"  - {err}", err=True)
        sys.exit(1)

    click.echo(f"Config OK: {config_path}")
    resolved = params.all_resolved()
    click.echo(f"  {len(resolved)} parameters resolved.")
