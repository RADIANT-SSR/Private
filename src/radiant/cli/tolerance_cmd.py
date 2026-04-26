"""``radiant tolerance`` subcommand — Monte Carlo tolerance analysis."""

from __future__ import annotations

import json
import sys

import click

from radiant.cli._common import load_sensor, set_option


def _parse_tolerance_spec(spec: str) -> tuple[str, str, dict[str, float]]:
    """Parse a tolerance spec string.

    Format: ``"param_name distribution key=val key=val ..."``

    Example: ``"optics.aperture_diameter_m gaussian std_fraction=0.02"``

    Returns (param_name, distribution, params_dict).
    """
    parts = spec.split()
    if len(parts) < 3:
        raise click.BadParameter(
            f"Tolerance spec must be 'param distribution key=val ...', got: '{spec}'",
            param_hint="'--tolerance'",
        )
    param_name = parts[0]
    distribution = parts[1]
    params: dict[str, float] = {}
    for kv in parts[2:]:
        if "=" not in kv:
            raise click.BadParameter(
                f"Tolerance param must be key=value, got: '{kv}'",
                param_hint="'--tolerance'",
            )
        k, _, v = kv.partition("=")
        params[k] = float(v)
    return param_name, distribution, params


@click.command("tolerance")
@click.argument("config", type=click.Path(exists=True, dir_okay=False))
@click.option("--trials", type=int, default=100, show_default=True, help="Number of MC trials.")
@click.option("--seed", type=int, default=42, show_default=True, help="Random seed.")
@click.option(
    "--tolerance",
    "tolerances",
    multiple=True,
    help='Tolerance spec: "param distribution key=val ..." (repeatable).',
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(),
    default=None,
    help="Save results to JSON.",
)
@set_option
def tolerance_cmd(
    config: str,
    trials: int,
    seed: int,
    tolerances: tuple[str, ...],
    output_path: str | None,
    overrides: tuple[str, ...],
) -> None:
    """Run Monte Carlo tolerance analysis.

    Tolerances can be specified via --tolerance flags or in the config.

    Example::

        radiant tolerance examples/mwir_leo_minimal.yaml --trials 50 \\
            --tolerance "optics.aperture_diameter_m gaussian std_fraction=0.02" \\
            --tolerance "optics.transmission_scalar gaussian std_fraction=0.05"
    """
    sensor = load_sensor(config, overrides)

    # Apply tolerance specs from CLI.
    for spec in tolerances:
        try:
            param_name, distribution, params = _parse_tolerance_spec(spec)
        except click.BadParameter as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(1)
        sensor.set_tolerance(param_name, distribution, **params)

    try:
        mc_result = sensor.monte_carlo(n_trials=trials, seed=seed)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # Print summary.
    click.echo(f"Monte Carlo: {mc_result.n_trials} trials, seed={mc_result.seed}")
    click.echo()
    for metric in mc_result.metric_names:
        mean = mc_result.mean(metric)
        std = mc_result.std(metric)
        p5 = mc_result.percentile(metric, 5.0)
        p95 = mc_result.percentile(metric, 95.0)
        click.echo(f"{metric}:")
        click.echo(f"  Mean: {mean:.6g}  Std: {std:.6g}  [5th: {p5:.6g}, 95th: {p95:.6g}]")

    # Save output.
    if output_path is not None:
        data: dict[str, object] = {
            "n_trials": mc_result.n_trials,
            "seed": mc_result.seed,
            "metrics": {},
        }
        metrics_dict: dict[str, object] = {}
        for m in mc_result.metric_names:
            metrics_dict[m] = {
                "mean": mc_result.mean(m),
                "std": mc_result.std(m),
                "p5": mc_result.percentile(m, 5.0),
                "p95": mc_result.percentile(m, 95.0),
            }
        data["metrics"] = metrics_dict
        from pathlib import Path

        Path(output_path).write_text(json.dumps(data, indent=2), encoding="utf-8")
        click.echo(f"Results written to {output_path}")
