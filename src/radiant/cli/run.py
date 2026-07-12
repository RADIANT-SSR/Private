"""``radiant run`` subcommand — load config, run chain, print results."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import click
import numpy as np

from radiant.api.session import RadiantSession
from radiant.cli._common import coerce_value, parse_overrides, set_option
from radiant.io.config import ConfigError, load_config


def _parse_overrides(overrides: tuple[str, ...]) -> dict[str, str]:
    """Parse ``--set key=value`` pairs into a dict.

    Raises
    ------
    click.BadParameter
        If any override is not in ``key=value`` format.

    .. deprecated:: Use :func:`radiant.cli._common.parse_overrides` instead.
    """
    return parse_overrides(overrides)


def _coerce_value(raw: str) -> int | float | str:
    """Best-effort coercion of a CLI string to int, float, or str.

    .. deprecated:: Use :func:`radiant.cli._common.coerce_value` instead.
    """
    return coerce_value(raw)


@click.command()
@click.argument("config", type=click.Path(exists=True, dir_okay=False))
@set_option
@click.option(
    "--wavelength-min",
    "wl_min",
    type=float,
    default=None,
    help="Override spectral grid minimum [um].",
)
@click.option(
    "--wavelength-max",
    "wl_max",
    type=float,
    default=None,
    help="Override spectral grid maximum [um].",
)
@click.option(
    "--wavelength-points",
    "wl_n",
    type=int,
    default=500,
    help="Number of wavelength grid points (default: 500).",
    show_default=True,
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(),
    default=None,
    help="Write results to a JSON file.",
)
@click.option(
    "--provenance",
    "provenance_path",
    type=click.Path(),
    default=None,
    help="Write provenance record to a JSON file.",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json", "csv"]),
    default="text",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--quiet",
    is_flag=True,
    default=False,
    help="Suppress all output except the final metric summary.",
)
def run(
    config: str,
    overrides: tuple[str, ...],
    wl_min: float | None,
    wl_max: float | None,
    wl_n: int,
    output_path: str | None,
    provenance_path: str | None,
    fmt: str,
    quiet: bool,
) -> None:
    """Run the RADIANT signal chain from a YAML config file.

    Example::

        radiant run examples/mwir_leo_minimal.yaml
        radiant run examples/mwir_leo_minimal.yaml --set optics.aperture_diameter_m=0.5
        radiant run examples/mwir_leo_minimal.yaml --output result.json
    """
    # Load config.
    try:
        params = RadiantSession.default_params()
        load_config(Path(config), params)
    except ConfigError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # Apply --set overrides.
    parsed = parse_overrides(overrides)
    for key, raw_value in parsed.items():
        value = coerce_value(raw_value)
        try:
            params.set(key, value)
        except KeyError:
            click.echo(
                f"Error: unknown parameter '{key}'. "
                "Check spelling or run 'radiant schema' for available parameters.",
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

    # -- Output --------------------------------------------------------

    if fmt == "json":
        data = {
            "config": config,
            "metrics": dict(result.metrics),
            "noise_terms": [
                {"name": nt.name, "value_e_rms": nt.value_e} for nt in result.noise_terms
            ],
        }
        click.echo(json.dumps(data, indent=2))
    elif fmt == "csv":
        click.echo("metric,value")
        for name, val in sorted(result.metrics.items()):
            click.echo(f"{name},{val}")
    else:
        # Text format (default).
        if not quiet:
            pe = result.frames["photoelectrons"].in_band_value
            click.echo(f"Signal:  {pe:.2f} e-")

            for nt in result.noise_terms:
                click.echo(f"  {nt.name:15s}  {nt.value_e:.4f} e- RMS")

            noise_total = math.sqrt(sum(n.value_e**2 for n in result.noise_terms))
            click.echo(f"Noise (RSS): {noise_total:.4f} e- RMS")

        snr = result.metrics.get("snr")
        if snr is not None:
            click.echo(f"SNR:     {snr:.2f}")

        if quiet:
            for name, val in sorted(result.metrics.items()):
                if name != "snr":
                    click.echo(f"{name}: {val:.6g}")

    # -- File outputs --------------------------------------------------

    if output_path is not None:
        data = {
            "config": config,
            "metrics": dict(result.metrics),
            "noise_terms": [
                {"name": nt.name, "value_e_rms": nt.value_e} for nt in result.noise_terms
            ],
            "history": list(result.history),
        }
        Path(output_path).write_text(json.dumps(data, indent=2), encoding="utf-8")
        if not quiet:
            click.echo(f"Results written to {output_path}")

    if provenance_path is not None:
        from radiant import __version__ as _radiant_version

        prov = params.to_provenance_record(radiant_version=_radiant_version)
        Path(provenance_path).write_text(json.dumps(prov, indent=2), encoding="utf-8")
        if not quiet:
            click.echo(f"Provenance written to {provenance_path}")
