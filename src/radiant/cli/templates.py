"""``radiant template`` subcommand — the bundled mission templates.

Serves the SAME template store the GUI welcome screen serves —
``radiant/data/templates/`` via :mod:`radiant.api.mission_templates`
discovery. The subcommand used to carry its own inline dict of four
minimal configs, disjoint from the bundled store (Rule 27 duality,
October sweep, owner-ratified 2026-09-12): the CLI and the GUI showed
different catalogs under one name. The inline dict is gone; its three
band classes the bundled store lacked (VNIR aerial, SWIR LEO, GEO LWIR)
graduated into the store as proper mission templates.

Names on the command line are the template file stems
(``leo_mapping_extended``), matching what ``create`` writes.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import click

from radiant.api.mission_templates import TemplateInfo, discover_templates


def _catalog() -> dict[str, TemplateInfo]:
    """The bundled templates keyed by file stem (CLI name)."""
    return {info.path.stem: info for info in discover_templates()}


def _fail_unknown(name: str, catalog: dict[str, TemplateInfo]) -> None:
    click.echo(f"Error: unknown template '{name}'.", err=True)
    click.echo(f"Available: {', '.join(sorted(catalog))}", err=True)
    sys.exit(1)


@click.group()
def template() -> None:
    """Manage sensor configuration templates."""


@template.command("list")
def template_list() -> None:
    """List the bundled mission templates (the GUI welcome-screen set)."""
    catalog = _catalog()
    if not catalog:
        click.echo(
            "No bundled templates found — the package data appears to be "
            "stripped from this installation.",
            err=True,
        )
        sys.exit(1)
    width = max(len(stem) for stem in catalog)
    click.echo(f"{'Name':<{width}s}  Description")
    click.echo("-" * (width + 50))
    for stem, info in sorted(catalog.items()):
        click.echo(f"{stem:<{width}s}  {info.blurb}  [{info.specs}]")


@template.command("show")
@click.argument("name")
def template_show(name: str) -> None:
    """Print a template configuration as YAML."""
    catalog = _catalog()
    if name not in catalog:
        _fail_unknown(name, catalog)
    click.echo(catalog[name].path.read_text(encoding="utf-8"))


@template.command("create")
@click.argument("name")
@click.option(
    "--output",
    "output_path",
    type=click.Path(),
    default=None,
    help="Output file path (default: <name>.yaml in current directory).",
)
def template_create(name: str, output_path: str | None) -> None:
    """Copy a template YAML to a file as a starting point."""
    catalog = _catalog()
    if name not in catalog:
        _fail_unknown(name, catalog)
    dest = Path(output_path) if output_path is not None else Path(f"{name}.yaml")
    shutil.copyfile(catalog[name].path, dest)
    click.echo(f"Template written to {dest}")
