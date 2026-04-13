"""``radiant run`` subcommand — load config, run chain, print results."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import numpy as np

from radiant.api.session import RadiantSession
from radiant.io.config import ConfigError, load_config


def _parse_overrides(overrides: tuple[str, ...]) -> dict[str, str]:
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


def _coerce_value(raw: str) -> int | float | str:
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


@click.command()
@click.argument("config", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--set", "overrides", multiple=True,
    help="Parameter override in key=value format (repeatable).",
)
@click.option(
    "--wavelength-min", "wl_min", type=float, default=None,
    help="Override spectral grid minimum [um].",
)
@click.option(
    "--wavelength-max", "wl_max", type=float, default=None,
    help="Override spectral grid maximum [um].",
)
@click.option(
    "--wavelength-points", "wl_n", type=int, default=500,
    help="Number of wavelength grid points (default: 500).",
    show_default=True,
)
def run(
    config: str,
    overrides: tuple[str, ...],
    wl_min: float | None,
    wl_max: float | None,
    wl_n: int,
) -> None:
    """Run the RADIANT signal chain from a YAML config file.

    Example::

        radiant run examples/mwir_leo_minimal.yaml
        radiant run examples/mwir_leo_minimal.yaml --set optics.aperture_diameter_m=0.5
    """
    # Load config.
    try:
        params = RadiantSession.default_params()
        load_config(Path(config), params)
    except ConfigError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # Apply --set overrides.
    parsed = _parse_overrides(overrides)
    for key, raw_value in parsed.items():
        value = _coerce_value(raw_value)
        try:
            params.set(key, value)
        except KeyError:
            click.echo(
                f"Error: unknown parameter '{key}'. "
                "Check spelling or run 'radiant validate' for available parameters.",
                err=True,
            )
            sys.exit(1)

    # Resolve.
    try:
        params.resolve()
    except (ValueError, TypeError) as exc:
        click.echo(f"Error resolving parameters: {exc}", err=True)
        sys.exit(1)

    # Build wavelength grid.
    fmin = wl_min if wl_min is not None else params.get("spectral_integration.filter_min_um")
    fmax = wl_max if wl_max is not None else params.get("spectral_integration.filter_max_um")
    wl = np.linspace(fmin, fmax, wl_n)

    # Run chain.
    session = RadiantSession(wavelength_um=wl)
    result = session.run(params)

    # Print results.
    pe = result.frames["photoelectrons"].in_band_value
    click.echo(f"Signal:  {pe:.2f} e-")

    for nt in result.noise_terms:
        click.echo(f"  {nt.name:15s}  {nt.value_e:.4f} e- RMS")

    import math
    noise_total = math.sqrt(sum(n.value_e ** 2 for n in result.noise_terms))
    click.echo(f"Noise (RSS): {noise_total:.4f} e- RMS")

    snr = result.metrics.get("snr")
    if snr is not None:
        click.echo(f"SNR:     {snr:.2f}")
