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
    from radiant.api.sensor import Sensor


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

    Requires the optional GUI extra::

        pip install "radiant[gui]"

    Examples::

        radiant gui
        radiant gui examples/mwir_leo_minimal.yaml
    """
    try:
        from radiant.gui import launch_gui
    except ImportError as exc:  # PySide6 (or another gui-extra dep) is missing.
        raise GuiUnavailableError(
            what="the RADIANT desktop GUI is not available",
            why=f"the optional 'gui' extra is not installed ({exc})",
            action='install it with: pip install "radiant[gui]"',
        ) from exc

    sensor = _load_sensor(config)
    sys.exit(launch_gui(sensor))


def _load_sensor(config: str | None) -> Sensor | None:
    """Load a :class:`Sensor` from *config*, or return ``None`` for no config.

    ``Sensor`` is imported lazily inside the body (not at module load) so the CLI
    stays importable and fast without touching the api layer until this command
    actually runs. Errors surface as their native :class:`RadiantError`
    subclasses.
    """
    if config is None:
        return None

    config_path = Path(config)
    if not config_path.exists():
        click.echo(f"Error: file not found: {config_path}", err=True)
        sys.exit(1)

    from radiant import Sensor

    return Sensor.from_yaml(str(config_path))
