"""``radiant validate`` subcommand — check a config without running."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from radiant import RadiantError
from radiant.api.config_io import normalize_element_document
from radiant.api.config_set import ConfigurationSet
from radiant.api.session import RadiantSession
from radiant.cli._common import coerce_value, parse_overrides, set_option
from radiant.cli._study import SECTION_KEY, die, is_study, load_study
from radiant.io.config import ConfigError, load_config, unattached_section_error
from radiant.io.configured_elements import (
    configured_rows_need_a_configuration_set,
    has_configured_rows,
)
from radiant.io.element_config import ElementConfigError


@click.command()
@click.argument("config", type=click.Path(exists=False, dir_okay=False))
@set_option
def validate(config: str, overrides: tuple[str, ...]) -> None:
    """Validate a YAML config file without running the chain.

    Checks that the file parses, all parameter names are known, types
    are correct, and all required parameters are set.  Reports all
    errors at once (not fail-fast).

    A **study** config file (``configurations:``, ADR-0010) validates
    **every** configuration and reports one line each — no configuration's
    failure hides another's.

    Example::

        radiant validate examples/mwir_leo_minimal.yaml
        radiant validate study.yaml
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
    if has_configured_rows(sections.get("optical_elements")):
        # Configured rows carry one entry per configuration, so they are only
        # meaningful as part of a study — and there the study loader validates
        # them (density, entries, Kirchhoff) naming the row and the member.
        if not is_study(sections):
            click.echo(f"Error: {configured_rows_need_a_configuration_set(config_path)}", err=True)
            sys.exit(1)
    elif "optical_elements" in sections:
        try:
            normalize_element_document(sections["optical_elements"], base_dir=config_path.parent)
        except ElementConfigError as exc:
            errors.append(f"optical_elements: {exc}")

    # A study config file validates every configuration, not the shared body.
    if is_study(sections):
        if errors:
            click.echo("Validation failed:", err=True)
            for err in errors:
                click.echo(f"  - {err}", err=True)
            sys.exit(1)
        _validate_study(config_path, overrides)
        return

    # Sections this command cannot validate are reported, never silently
    # accepted (Rule 17).
    unattached = sorted(set(sections) - {"optical_elements", SECTION_KEY})
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


# ---------------------------------------------------------------------------
# Study config files (ADR-0010) — every configuration is validated
# ---------------------------------------------------------------------------


def _validate_study(config_path: Path, overrides: tuple[str, ...]) -> None:
    """Validate every configuration of a study config file, one line each.

    Resolution only — no physics runs (``ConfigurationSet.validate_all``). Each
    configuration reports independently, so one configuration's failure never
    hides another's, and the command exits non-zero when any of them failed.
    """
    cs = load_study(config_path)
    _apply_shared_overrides(cs, overrides)

    status = cs.validate_all()
    names = cs.names()
    failed = [name for name, err in status.items() if err is not None]
    width = max(len(name) for name in names)

    for name in names:
        error = status[name]
        if error is None:
            click.echo(f"  {name.ljust(width)}  ok      {_configuration_detail(cs, name)}")
        else:
            what = getattr(error, "what", None) or str(error)
            click.echo(f"  {name.ljust(width)}  ERROR   {what}")

    n_configured = len(cs.configured())
    tail = (
        f"{len(names)} configuration(s), {n_configured} configured parameter(s), "
        f"{len(failed)} failed."
    )
    if failed:
        click.echo(f"Study validation failed: {config_path} — {tail}", err=True)
        sys.exit(1)
    click.echo(f"Study OK: {config_path} — {tail}")


def _apply_shared_overrides(cs: ConfigurationSet, overrides: tuple[str, ...]) -> None:
    """Apply ``--set`` overrides to the study's **shared** base, or exit(1).

    A study's per-configuration values are not reachable from a single
    ``key=value`` pair — the flag would have to say *which* configuration — so
    a configured dot-path is refused with the route that does work, rather than
    guessing (Rule 17).
    """
    try:
        parsed = parse_overrides(overrides)
    except click.BadParameter as exc:
        die(str(exc))

    for key, raw_value in parsed.items():
        try:
            if cs.is_configured(key):
                die(
                    f"--set {key}=… cannot be applied to this study: {key!r} is a "
                    "configured parameter and carries one value per configuration, so a "
                    "single value has no unambiguous target. Edit the study's "
                    "`configurations.parameters` block, or set the values through "
                    "ConfigurationSet.set_value(s) in the scripting API."
                )
            cs.base.set(key, coerce_value(raw_value))
        except KeyError:
            die(f"unknown parameter: '{key}'")
        except RadiantError as exc:
            die(str(exc))


def _configuration_detail(cs: ConfigurationSet, name: str) -> str:
    """One resolved configuration's spectral grid, with units (project hard rule)."""
    sensor = cs.sensor_for(name)
    lo = sensor.get("spectral_integration.filter_min_um")
    hi = sensor.get("spectral_integration.filter_max_um")
    return f"band {lo:.3f}–{hi:.3f} µm, {sensor.wavelength_points} grid points"
