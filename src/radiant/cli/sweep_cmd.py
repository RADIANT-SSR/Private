"""``radiant sweep`` subcommand — 1-D parameter sweep from CLI."""

from __future__ import annotations

import json
import sys

import click
import numpy as np

from radiant.cli._common import load_sensor, set_option


@click.command("sweep")
@click.argument("config", type=click.Path(exists=True, dir_okay=False))
@click.argument("param")
@click.option("--min", "v_min", type=float, required=True, help="Sweep minimum value.")
@click.option("--max", "v_max", type=float, required=True, help="Sweep maximum value.")
@click.option("--steps", type=int, default=10, show_default=True, help="Number of sweep points.")
@click.option("--metric", default="snr", show_default=True, help="Metric key to report.")
@click.option(
    "--output", "output_path", type=click.Path(), default=None,
    help="Save results to JSON or CSV (extension determines format).",
)
@click.option(
    "--plot", "plot_path", type=click.Path(), default=None,
    help="Save a plot to PNG (requires matplotlib).",
)
@set_option
def sweep_cmd(
    config: str,
    param: str,
    v_min: float,
    v_max: float,
    steps: int,
    metric: str,
    output_path: str | None,
    plot_path: str | None,
    overrides: tuple[str, ...],
) -> None:
    """Run a 1-D parameter sweep.

    Example::

        radiant sweep examples/mwir_leo_minimal.yaml optics.aperture_diameter_m \\
            --min 0.15 --max 0.60 --steps 10 --metric snr
    """
    sensor = load_sensor(config, overrides)
    values = np.linspace(v_min, v_max, steps)

    try:
        result = sensor.sweep(param, values, metric=metric)
    except (ValueError, KeyError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # Print table.
    click.echo(f"{'Value':>12s}  {metric:>12s}")
    click.echo("-" * 26)
    for v, m in zip(result.values, result.metric_values):
        click.echo(f"{v:12.6g}  {m:12.6g}")

    # Save output.
    if output_path is not None:
        if output_path.endswith(".csv"):
            lines = [f"value,{metric}"]
            for v, m in zip(result.values, result.metric_values):
                lines.append(f"{v},{m}")
            from pathlib import Path

            Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            data = {
                "param": param,
                "metric": metric,
                "values": result.values.tolist(),
                "metric_values": result.metric_values.tolist(),
            }
            from pathlib import Path

            Path(output_path).write_text(json.dumps(data, indent=2), encoding="utf-8")
        click.echo(f"Results written to {output_path}")

    # Save plot.
    if plot_path is not None:
        try:
            from radiant.api.plot import plot_sweep
        except ImportError:
            click.echo(
                "Error: matplotlib is required for --plot. "
                "Install with: pip install matplotlib",
                err=True,
            )
            sys.exit(1)
        fig = plot_sweep(result)
        fig.savefig(plot_path, dpi=150)
        click.echo(f"Plot saved to {plot_path}")
