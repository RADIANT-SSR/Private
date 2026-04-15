"""``radiant compare`` subcommand — side-by-side config comparison."""

from __future__ import annotations

import json
import sys

import click

from radiant.cli._common import load_sensor


@click.command()
@click.argument("config1", type=click.Path(exists=True, dir_okay=False))
@click.argument("config2", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--output", "output_path", type=click.Path(), default=None,
    help="Save comparison to JSON.",
)
def compare(config1: str, config2: str, output_path: str | None) -> None:
    """Compare two configurations side-by-side.

    Evaluates both configs and prints a metric diff table.

    Example::

        radiant compare config_a.yaml config_b.yaml
    """
    sensor1 = load_sensor(config1)
    sensor2 = load_sensor(config2)

    try:
        result1 = sensor1.evaluate()
        result2 = sensor2.evaluate()
    except (ValueError, TypeError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    all_metrics = sorted(
        set(result1.metrics.keys()) | set(result2.metrics.keys())
    )

    click.echo(
        f"{'Metric':>20s}  {'Config 1':>12s}  {'Config 2':>12s}  "
        f"{'Delta':>12s}  {'%Change':>10s}"
    )
    click.echo("-" * 70)

    comparison: dict[str, dict[str, float]] = {}
    for name in all_metrics:
        v1 = result1.metrics.get(name, float("nan"))
        v2 = result2.metrics.get(name, float("nan"))
        delta = v2 - v1
        pct = (delta / v1 * 100.0) if v1 != 0.0 else float("nan")
        click.echo(
            f"{name:>20s}  {v1:12.4f}  {v2:12.4f}  {delta:+12.4f}  {pct:+9.1f}%"
        )
        comparison[name] = {"config1": v1, "config2": v2, "delta": delta, "pct_change": pct}

    if output_path is not None:
        data = {
            "config1": config1,
            "config2": config2,
            "metrics": comparison,
        }
        from pathlib import Path

        Path(output_path).write_text(json.dumps(data, indent=2), encoding="utf-8")
        click.echo(f"\nComparison written to {output_path}")
