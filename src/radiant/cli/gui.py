"""``radiant gui`` subcommand — launch the desktop GUI on an optional config.

The GUI lives behind the optional ``gui`` extra (PySide6 + friends). This command
imports :mod:`radiant.gui` **lazily** so the rest of the CLI works with a
core-only install; if the extra is missing it raises an actionable, RADIANT-typed
error naming the exact remedy (Rule 15).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

from radiant import RadiantError

if TYPE_CHECKING:
    from radiant.api.config_set import ConfigurationSet


class GuiUnavailableError(RadiantError):
    """The desktop GUI cannot start because its optional extra is not installed.

    Carries the structured ``what / why / action`` payload of the Rule 15
    actionable-error contract. Lives with the module that raises it (the CLI
    ``gui`` subcommand), because it must be raiseable even when
    :mod:`radiant.gui` itself fails to import.
    """

    def __init__(self, what: str, why: str, action: str) -> None:
        self.what = what
        self.why = why
        self.action = action
        super().__init__(f"{what} | Why: {why} | Action: {action}")


@click.command()
@click.argument("config", type=click.Path(exists=False, dir_okay=False), required=False)
def gui(config: str | None) -> None:
    """Launch the RADIANT desktop GUI, optionally on a YAML config file.

    The GUI ships with the base install (PySide6 is a core dependency); if the
    import fails the error names what is missing.

    Examples::

        radiant gui
        radiant gui examples/mwir_leo_minimal.yaml
    """
    try:
        from radiant.gui import launch_gui
    except ImportError as exc:  # PySide6 (or another gui-extra dep) is missing.
        raise GuiUnavailableError(
            what="the RADIANT desktop GUI is not available",
            why=f"a GUI dependency failed to import ({exc})",
            action='reinstall RADIANT (pip install -e ".[dev]" from a checkout, or the '
            "wheel) so PySide6 and its companions are present",
        ) from exc

    config_set = _load_config_set(config)
    sys.exit(launch_gui(config_set=config_set, path=config))


def _load_config_set(config: str | None) -> ConfigurationSet | None:
    """Load *config* as a :class:`ConfigurationSet`; ``None`` for no config.

    Every file goes through :meth:`ConfigurationSet.load` — the API decides the
    document kind (CU-342), exactly the one-reader dispatch the GUI's File → Open
    uses: a study file (``configurations:`` section) loads as the full set, a
    plain config as the degenerate one-configuration set. The api import is lazy
    (inside the body, not at module load) so the CLI stays importable and fast
    until this command actually runs. Errors surface as their native
    :class:`RadiantError` subclasses.
    """
    if config is None:
        # A bare `radiant gui` opens on the welcome screen (mission templates,
        # Blank config, worked examples, recent files — arch doc §4.4a), which is
        # what a window with no document shows. Handing it a blank Sensor instead
        # (the pre-welcome from-scratch flow of 2026-07-17) skipped that surface
        # until File → New (CU-373 F-44); the Blank card is the from-scratch path.
        return None

    config_path = Path(config)
    if not config_path.exists():
        click.echo(f"Error: file not found: {config_path}", err=True)
        sys.exit(1)

    from radiant.api.config_set import ConfigurationSet

    return ConfigurationSet.load(str(config_path))
