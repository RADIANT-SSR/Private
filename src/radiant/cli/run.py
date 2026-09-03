"""``radiant run`` subcommand — load config, run chain, print results."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import click
import numpy as np

from radiant import RadiantError
from radiant.api.sensor import Sensor
from radiant.api.session import RadiantSession
from radiant.cli._common import coerce_value, parse_overrides, set_option
from radiant.cli._study import (
    SECTION_KEY,
    die,
    is_study,
    load_study,
    no_configuration_flag_error,
    not_a_study_error,
)
from radiant.io.config import ConfigError, load_config, unattached_section_error
from radiant.io.configured_elements import (
    configured_rows_need_a_configuration_set,
    has_configured_rows,
)
from radiant.io.element_config import ElementConfigError, parse_element_entries
from radiant.io.results import ChainResult


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
    "--configuration",
    "configuration",
    metavar="NAME",
    default=None,
    help="Configuration of a study config file to evaluate (ADR-0010). Required for a "
    "study file; rejected for a plain config file.",
)
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
    configuration: str | None,
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
        radiant run study.yaml --configuration LWIR
    """
    # Load config. Structured sections (optical_elements, ADR-0009 / CU-153) are
    # taken via sections_out and injected pre-chain below — the same route
    # Sensor.from_yaml uses, so a Sensor.save'd element config runs from the CLI.
    sections: dict[str, object] = {}
    try:
        params = RadiantSession.default_params()
        load_config(Path(config), params, sections_out=sections)
    except ConfigError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # A study config file (`configurations:`, ADR-0010) runs one named
    # configuration and never its shared body alone (Rule 17).
    if is_study(sections):
        _run_study(
            config=config,
            configuration=configuration,
            overrides=overrides,
            wl_min=wl_min,
            wl_max=wl_max,
            wl_n=wl_n,
            output_path=output_path,
            provenance_path=provenance_path,
            fmt=fmt,
            quiet=quiet,
        )
        return
    if configuration is not None:
        die(not_a_study_error(config, configuration))
    if has_configured_rows(sections.get("optical_elements")):
        # Configured element rows belong to a study; without a `configurations:`
        # section they name configurations that do not exist (Rule 15/17).
        die(str(configured_rows_need_a_configuration_set(config)))

    # Any other section the CLI cannot act on is an error, never a silent drop.
    unattached = sorted(set(sections) - {"optical_elements", SECTION_KEY})
    if unattached:
        click.echo(f"Error: {unattached_section_error(unattached, config)}", err=True)
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

    # Parse any optical_elements section onto the run grid (Rule 6 pre-chain IO).
    extra_stage_outputs: dict[str, dict[str, object]] | None = None
    if "optical_elements" in sections:
        try:
            elements = parse_element_entries(
                sections["optical_elements"], wl, base_dir=Path(config).parent
            )
        except ElementConfigError as exc:
            click.echo(f"Error in optical_elements: {exc}", err=True)
            sys.exit(1)
        extra_stage_outputs = {"optics_config": {"element_list": elements}}

    # Run chain.
    session = RadiantSession(wavelength_um=wl)
    if extra_stage_outputs is not None:
        result = session.run(params, extra_stage_outputs=extra_stage_outputs)
    else:
        result = session.run(params)

    # -- Output --------------------------------------------------------

    _emit_result(result, config=config, configuration=None, fmt=fmt, quiet=quiet)
    _write_result_file(result, config=config, configuration=None, path=output_path, quiet=quiet)

    if provenance_path is not None:
        # CU-218: one flag, one schema. This path used to write
        # `ParameterSet.to_provenance_record` — three keys, resolved parameters
        # only — while the study path wrote the full run record, so a consumer of
        # `--provenance` had to sniff which shape it had been given. Both now emit
        # the run record, with `configuration: null` marking a plain (single
        # configuration) run. The run record is the richer of the two and the one
        # a materialized study can produce at all.
        prov: dict[str, object] = {"configuration": None}
        prov.update(result.to_provenance_record())
        Path(provenance_path).write_text(json.dumps(prov, indent=2), encoding="utf-8")
        if not quiet:
            click.echo(f"Provenance written to {provenance_path}")


# ---------------------------------------------------------------------------
# Study config files (ADR-0010) — one named configuration per invocation
# ---------------------------------------------------------------------------


def _explicitly_given(name: str) -> bool:
    """True when the caller supplied option *name* rather than taking its default.

    ``--wavelength-points`` carries a default (500) that the study path must be
    able to tell apart from an explicit ``--wavelength-points 500``: a study's
    configurations carry their own point counts, and silently overwriting them
    with the flag's default would evaluate the file on a grid it does not
    describe.
    """
    ctx = click.get_current_context(silent=True)
    if ctx is None:
        return False
    source = ctx.get_parameter_source(name)
    return source is not None and source.name != "DEFAULT"


def _run_study(
    *,
    config: str,
    configuration: str | None,
    overrides: tuple[str, ...],
    wl_min: float | None,
    wl_max: float | None,
    wl_n: int,
    output_path: str | None,
    provenance_path: str | None,
    fmt: str,
    quiet: bool,
) -> None:
    """Evaluate one named configuration of a study config file.

    Thin by construction: ``ConfigurationSet.load`` →
    :meth:`ConfigurationSet.sensor_for` → the ordinary ``Sensor.evaluate``
    path. Every validation, unit conversion, and actionable error is the api
    layer's, not the CLI's.
    """
    cs = load_study(Path(config))
    names = cs.names()
    if configuration is None:
        die(no_configuration_flag_error(config, names))

    if wl_min is not None or wl_max is not None:
        die(
            "--wavelength-min / --wavelength-max cannot be combined with --configuration: "
            "each configuration of a study spans its own resolved "
            "spectral_integration.filter_min_um … filter_max_um band (ADR-0010 D-F), so a "
            "single grid span imposed from the command line would contradict the file. "
            "Override the band itself, e.g. "
            "--set spectral_integration.filter_min_um=3.9, or edit the study."
        )

    try:
        sensor: Sensor = cs.sensor_for(configuration)
    except RadiantError as exc:
        die(str(exc))

    # The configuration's own point count is in force unless the caller asked
    # for a different one explicitly.
    if _explicitly_given("wl_n"):
        sensor = sensor.with_wavelength_points(wl_n)

    # --set overrides apply to the materialized configuration (they are the
    # last word, as on a plain config file); a configured parameter's value for
    # *this* configuration is what they override.
    for key, raw_value in parse_overrides(overrides).items():
        try:
            sensor.set(key, coerce_value(raw_value))
        except KeyError:
            die(
                f"unknown parameter '{key}'. Check spelling or run 'radiant schema' for "
                "available parameters."
            )
        except RadiantError as exc:
            die(str(exc))

    try:
        result = sensor.evaluate()
    except RadiantError as exc:
        die(f"configuration {configuration!r} failed to evaluate: {exc}")

    _emit_result(result, config=config, configuration=configuration, fmt=fmt, quiet=quiet)
    _write_result_file(
        result, config=config, configuration=configuration, path=output_path, quiet=quiet
    )

    if provenance_path is not None:
        # The run's own record, tagged with the configuration it came from.
        # Same shape as the plain path since CU-218 — only `configuration`
        # differs (a name here, null there).
        prov: dict[str, object] = {"configuration": configuration}
        prov.update(result.to_provenance_record())
        Path(provenance_path).write_text(json.dumps(prov, indent=2), encoding="utf-8")
        if not quiet:
            click.echo(f"Provenance written to {provenance_path}")


# ---------------------------------------------------------------------------
# Result rendering (shared by the plain and study paths)
# ---------------------------------------------------------------------------


def _emit_result(
    result: ChainResult,
    *,
    config: str,
    configuration: str | None,
    fmt: str,
    quiet: bool,
) -> None:
    """Render one run to stdout in the requested format.

    When *configuration* is given (a study run) every format carries it, so a
    saved or piped result can never be read as "the" result of the file: the
    text header gains a ``Configuration:`` line, the JSON object a
    ``configuration`` key, and the CSV a leading ``configuration`` column.
    """
    if fmt == "json":
        click.echo(json.dumps(_result_document(result, config, configuration), indent=2))
        return

    if fmt == "csv":
        if configuration is None:
            click.echo("metric,value")
            for name, val in sorted(result.metrics.items()):
                click.echo(f"{name},{val}")
        else:
            click.echo("configuration,metric,value")
            for name, val in sorted(result.metrics.items()):
                click.echo(f"{configuration},{name},{val}")
        return

    # Text format (default).
    if configuration is not None:
        click.echo(f"Configuration: {configuration}")
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


def _result_document(
    result: ChainResult,
    config: str,
    configuration: str | None,
    *,
    with_history: bool = False,
) -> dict[str, object]:
    """The JSON document for one run (stdout form, or the ``--output`` file form)."""
    data: dict[str, object] = {"config": config}
    if configuration is not None:
        data["configuration"] = configuration
    data["metrics"] = dict(result.metrics)
    data["noise_terms"] = [
        {"name": nt.name, "value_e_rms": nt.value_e} for nt in result.noise_terms
    ]
    if with_history:
        data["history"] = list(result.history)
    return data


def _write_result_file(
    result: ChainResult,
    *,
    config: str,
    configuration: str | None,
    path: str | None,
    quiet: bool,
) -> None:
    """Write the ``--output`` JSON file, when one was requested."""
    if path is None:
        return
    document = _result_document(result, config, configuration, with_history=True)
    Path(path).write_text(json.dumps(document, indent=2), encoding="utf-8")
    if not quiet:
        click.echo(f"Results written to {path}")
