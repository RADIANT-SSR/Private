"""Study (configuration-set) helpers shared by ``radiant run`` and ``radiant validate``.

A **study** config file is one that carries the ``configurations:`` structured
section (ADR-0010): a shared parameter body plus up to eight named
configurations of the same modeling problem. The CLI's contract with it is
deliberately narrow (plan §3.5 — "CLI support is a thin follow-on"):

* ``radiant run study.yaml --configuration NAME`` evaluates **exactly one**
  named configuration — :meth:`ConfigurationSet.sensor_for` materializes it and
  the ordinary single-sensor run path takes over from there.
* ``radiant run study.yaml`` **without** the flag is an error naming every
  configuration in the file. Picking one implicitly would mean honoring the
  study's ``active`` designation, which is GUI display state, not a scripting
  default (ADR-0010 D-D) — a batch job's result would then depend on where the
  analyst last left the selector.
* ``radiant validate study.yaml`` validates **every** configuration
  (:meth:`ConfigurationSet.validate_all`) and reports one line each.

This module owns only the shared plumbing: study detection, the load, and the
two actionable errors that are worded identically wherever they surface.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, NoReturn

import click

from radiant import RadiantError
from radiant.api.config_set import ConfigurationSet
from radiant.io.config_set_section import SECTION_KEY

__all__ = [
    "SECTION_KEY",
    "die",
    "is_study",
    "load_study",
    "no_configuration_flag_error",
    "not_a_study_error",
]


def is_study(sections: Mapping[str, Any]) -> bool:
    """True when a loaded config file carried a ``configurations:`` section."""
    return SECTION_KEY in sections


def die(message: str) -> NoReturn:
    """Print an actionable error to stderr and exit with status 1."""
    click.echo(f"Error: {message}", err=True)
    raise SystemExit(1)


def load_study(path: Path) -> ConfigurationSet:
    """Load a study config file, or exit(1) with the loader's actionable message.

    Every section violation (dense-column mismatch, unknown dot-path, a
    dot-path in both stores, a bad configured value, …) already raises a
    ``ConfigError`` / ``ConfigSetError`` naming the file, the configuration, and
    the parameter — the CLI renders it rather than re-wording it.
    """
    try:
        return ConfigurationSet.load(path)
    except RadiantError as exc:
        die(str(exc))


def no_configuration_flag_error(path: str | Path, names: tuple[str, ...]) -> str:
    """Message for a study config file run without ``--configuration``."""
    listed = ", ".join(repr(n) for n in names)
    return (
        f"{path} is a study config file holding {len(names)} configuration(s): {listed}. "
        "`radiant run` evaluates exactly one of them, and which one is not inferred: "
        "the study's `active` configuration is GUI display state (ADR-0010 D-D), so "
        "honoring it here would make a batch result depend on where the selector was "
        f"last left. Re-run with --configuration NAME, e.g. --configuration {names[0]!r}, "
        "or use ConfigurationSet.evaluate_all() from the scripting API to evaluate the "
        "whole study."
    )


def not_a_study_error(path: str | Path, configuration: str) -> str:
    """Message for ``--configuration`` given against a plain (non-study) config file."""
    return (
        f"--configuration {configuration!r} was given, but {path} is a plain config file "
        f"with no '{SECTION_KEY}:' section — it models one sensor, which has no named "
        "configurations. Drop --configuration to run it, or point at a study config file "
        "written by ConfigurationSet.save()."
    )
