"""XLSX workbook export (Tier-2 GT-4, owner decision D2 — openpyxl in the gui extra).

One workbook, three sheets built purely from public API surfaces:

- **Config** — every resolved parameter (dot-path, input value, input unit) via
  ``parameter_defs()`` + ``get_input()``; in a study, one value column per
  configuration (CU-374 F-22).
- **Metrics** — the last result's ``to_records()`` (name / value / unit / description);
  in a study, one value column per configuration from the retained evaluate-all pass.
- **Run** — the run stamp (CU-374 F-34/F-35).
- **Sweep** — the last sweep, when one exists: 1-D (param + metrics columns, mirroring
  ``SweepResult.to_csv``) or 2-D long form.

Every numeric cell keeps full precision (numbers, not formatted strings); units get
their own column (R-UNITS). Rule 30: openpyxl owns the file encoding.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from radiant.api.sweep import labeled_header, metric_units
from radiant.core.exceptions import RadiantError

if TYPE_CHECKING:
    from radiant.api import ChainResult
    from radiant.api.config_set import ConfigSetRunResult, ConfigurationSet
    from radiant.api.sensor import Sensor


def export_workbook(
    path: str | Path,
    sensor: Sensor,
    result: ChainResult | None,
    sweep: Any | None = None,
    *,
    stamp: Mapping[str, str] | None = None,
    config_set: ConfigurationSet | None = None,
    run: ConfigSetRunResult | None = None,
) -> Path:
    """Write the config/metrics/sweep workbook to *path* and return it.

    *stamp* (CU-374 F-34/F-35) adds a **Run** sheet of ``key / value`` rows — the
    run stamp every export carries, so the workbook says which run it describes
    and whether that run is stale.

    *config_set* and *run* (CU-374 F-22): in a **study** the Config sheet carries
    one value column per configuration, named as on screen (``parameter, unit,
    <name>, …``), and the Metrics sheet one value column per configuration from
    the retained evaluate-all pass (``name, unit, description, <name>, …``) — a
    configuration that failed shows an empty cell, never a zero. A plain session
    (or no set) writes the single-configuration layout it always did.
    """
    from openpyxl import Workbook

    book = Workbook()

    config_sheet = book.active
    config_sheet.title = "Config"
    names = tuple(config_set.names()) if config_set is not None and len(config_set) > 1 else ()
    if names and config_set is not None:
        columns: list[Sensor | None] = []
        for name in names:
            try:
                columns.append(config_set.sensor_for(name))
            except RadiantError:
                columns.append(None)  # an unresolvable configuration: empty cells
        config_sheet.append(["parameter", "unit", *names])
        for dotpath, pdef in sorted(sensor.parameter_defs().items()):
            config_sheet.append(
                [
                    dotpath,
                    pdef.input_unit or "",
                    *(_input_or_none(column, dotpath) for column in columns),
                ]
            )
    else:
        config_sheet.append(["parameter", "value", "unit"])
        for dotpath, pdef in sorted(sensor.parameter_defs().items()):
            config_sheet.append([dotpath, _input_or_none(sensor, dotpath), pdef.input_unit or ""])

    if names and run is not None and len(run.entries) > 1:
        metrics_sheet = book.create_sheet("Metrics")
        metrics_sheet.append(["name", "unit", "description", *run.names])
        per_config = {
            entry.name: {rec["name"]: rec for rec in entry.result.to_records()}
            for entry in run.entries
            if entry.result is not None
        }
        described: dict[str, dict[str, object]] = {}
        for records in per_config.values():
            for name, rec in records.items():
                described.setdefault(name, rec)
        for name in sorted(described):
            rec = described[name]
            metrics_sheet.append(
                [
                    name,
                    rec["unit"],
                    rec["description"],
                    *(
                        per_config.get(entry_name, {}).get(name, {}).get("value")
                        for entry_name in run.names
                    ),
                ]
            )
    elif result is not None:
        metrics_sheet = book.create_sheet("Metrics")
        metrics_sheet.append(["name", "value", "unit", "description"])
        for record in result.to_records():
            metrics_sheet.append(
                [record["name"], record["value"], record["unit"], record["description"]]
            )

    if sweep is not None:
        sweep_sheet = book.create_sheet("Sweep")
        if hasattr(sweep, "grid"):  # Sweep2DResult — long form
            sweep_sheet.append(
                [
                    labeled_header(sweep.param1_name, sweep.param1_unit),
                    labeled_header(sweep.param2_name, sweep.param2_unit),
                    labeled_header(sweep.metric_name, sweep.metric_unit),
                ]
            )
            for i, v1 in enumerate(sweep.values1):
                for j, v2 in enumerate(sweep.values2):
                    sweep_sheet.append([float(v1), float(v2), float(sweep.grid[i, j])])
        else:  # SweepResult
            extra = []
            if sweep.results:
                extra = sorted(
                    set().union(*(set(r.metrics) for r in sweep.results)) - {sweep.metric_name}
                )
            units = metric_units(sweep.results)
            sweep_sheet.append(
                [
                    labeled_header(sweep.param_name, sweep.param_unit),
                    labeled_header(sweep.metric_name, units.get(sweep.metric_name, "")),
                    *(labeled_header(name, units.get(name, "")) for name in extra),
                ]
            )
            for i, (v, m) in enumerate(zip(sweep.values, sweep.metric_values, strict=True)):
                extras = (
                    [float(sweep.results[i].metrics.get(name, float("nan"))) for name in extra]
                    if sweep.results
                    else []
                )
                sweep_sheet.append([float(v), float(m), *extras])

    if stamp:
        run_sheet = book.create_sheet("Run")
        run_sheet.append(["key", "value"])
        for key, value in stamp.items():
            run_sheet.append([key, value])
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    book.save(out)
    return out


def _input_or_none(sensor: Sensor | None, dotpath: str) -> object | None:
    """The resolved input value for *dotpath*, or ``None`` (an empty cell) when unset."""
    if sensor is None:
        return None
    try:
        return sensor.get_input(dotpath)
    except (KeyError, RadiantError):
        return None


__all__ = ["export_workbook"]
