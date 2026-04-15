"""``radiant schema`` subcommand — list parameter definitions."""

from __future__ import annotations

import json

import click

from radiant.api._param_registry import build_parameter_set


@click.command("schema")
@click.option(
    "--format", "fmt", type=click.Choice(["text", "json"]),
    default="text", show_default=True,
    help="Output format.",
)
@click.option(
    "--stage", "stage_name", default=None,
    help="Filter to a specific stage prefix (e.g. optics, detector).",
)
def schema_cmd(fmt: str, stage_name: str | None) -> None:
    """List all parameter definitions.

    Example::

        radiant schema
        radiant schema --stage optics
        radiant schema --format json
    """
    ps = build_parameter_set()
    defs = ps._defs

    if stage_name is not None:
        prefix = stage_name if stage_name.endswith(".") else stage_name + "."
        defs = {k: v for k, v in defs.items() if k.startswith(prefix)}
        if not defs:
            click.echo(f"No parameters found for stage '{stage_name}'.")
            click.echo(
                "Available prefixes: "
                + ", ".join(sorted({k.split(".")[0] for k in ps._defs}))
            )
            return

    if fmt == "json":
        entries = []
        for name, pdef in sorted(defs.items()):
            entry: dict[str, object] = {
                "name": name,
                "description": pdef.description,
                "dtype": pdef.dtype.__name__,
                "canonical_unit": pdef.canonical_unit,
                "input_unit": pdef.input_unit,
                "default": pdef.default,
            }
            if pdef.bounds is not None:
                entry["bounds"] = list(pdef.bounds)
            entries.append(entry)
        click.echo(json.dumps(entries, indent=2))
    else:
        click.echo(
            f"{'Name':<45s}  {'Type':>5s}  {'Unit':>8s}  "
            f"{'Default':>10s}  Description"
        )
        click.echo("-" * 110)
        for name, pdef in sorted(defs.items()):
            default_str = str(pdef.default) if pdef.default is not None else "(required)"
            click.echo(
                f"{name:<45s}  {pdef.dtype.__name__:>5s}  "
                f"{pdef.input_unit:>8s}  {default_str:>10s}  "
                f"{pdef.description}"
            )
