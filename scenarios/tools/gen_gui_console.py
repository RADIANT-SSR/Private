"""Generate a scripting-window (console) script per scenario.

Each generated ``scripts/gui_console_<slug>.py`` is written for the GUI's
scripting window (arch: the window binds a live ``sensor``/``result``/``plot``
namespace). Paste it into the window after ``File -> Open YAML`` of the
scenario's ``inputs/<slug>.gui.yaml`` and it will:

* echo the headline metrics **with units** (house rule) and the resolved
  radiometric regime,
* run a small single-parameter sweep along the scenario's trade variable and
  bind ``plot`` to the resulting figure (the window pops it out), and
* mutate one parameter and re-evaluate, so the console's stale-banner /
  re-evaluate path gets exercised.

The script is also runnable standalone (``python gui_console_<slug>.py``) for
headless verification: if ``sensor`` is not already bound it loads the sibling
YAML itself.

Usage (from repo root)::

    python scenarios/tools/gen_gui_console.py          # all registered
    python scenarios/tools/gen_gui_console.py 1.1      # a subset by id
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _local_radiant import ensure_local_radiant  # noqa: E402

ensure_local_radiant()  # CU-338: this checkout's radiant, or refuse

from gui_baselines import REGISTRY, GuiScenario  # noqa: E402

# Display unit per metric key (house rule: every value carries a unit). "[-]"
# marks a dimensionless ratio / rating level.
_METRIC_UNIT: dict[str, str] = {
    "snr": "[-]",
    "contrast_snr": "[-]",
    "scnr": "[-]",
    "nedt_K": "K",
    "niirs": "[-]",
    "gsd_geometric_mean_m": "m",
    "gsd_cross_track_m": "m",
    "ground_range_m": "m",
    "rer": "[-]",
    "ee_3x3": "[-]",
    "mtf_at_nyquist": "[-]",
    "strehl": "[-]",
    "fwhm_x_m": "m",
    "well_margin_dB": "dB",
}


def _pick_sweep(scen: GuiScenario, sensor: object) -> tuple[str, str, str, float]:
    """Return (dotpath, label, unit, center_value) for the console sweep."""
    if scen.sweep is not None:
        dot, label, unit = scen.sweep
        return dot, label, unit, float(sensor.get(dot))  # type: ignore[attr-defined]
    for dot, label, unit in (
        ("optics.aperture_diameter_m", "Aperture diameter", "m"),
        ("spectral_integration.integration_time_s", "Integration time", "s"),
    ):
        try:
            val = sensor.get(dot)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            continue
        if isinstance(val, (int, float)) and val > 0:
            return dot, label, unit, float(val)
    raise RuntimeError(f"{scen.id}: no usable sweep axis; set GuiScenario.sweep")


_TEMPLATE = '''\
# GUI scripting-window script — Scenario {id}: {title}
#
# HOW TO USE
#   1. In the RADIANT GUI: File -> Open YAML -> inputs/{slug}.gui.yaml
#      (the baseline derived from the validated scenario runner).
#   2. Open the scripting window (Ctrl+Shift+P); it binds ``sensor``,
#      ``result``, ``plot`` and the ``Sensor`` class into the namespace.
#   3. Paste this script and Run. The figure pops out into its own window;
#      the parameter change marks the main view stale (click Refresh).
#
# NOTE: {notes_block}
#
# NB: the header is comments, not a docstring — the console is a REPL and would
# echo a bare """string""" back into the transcript. Also runs standalone
# (headless smoke test): python scripts/gui_console_{slug}.py

# --- bootstrap: use the live GUI ``sensor`` if present, else load the YAML ---
try:
    sensor  # bound by the GUI scripting window
except NameError:
    from pathlib import Path as _Path

    from radiant.api import Sensor

    sensor = Sensor.load(
        _Path(__file__).resolve().parent.parent / "inputs" / "{slug}.gui.yaml"
    )

import warnings

import matplotlib.pyplot as plt
import numpy as np

# --- 1) Baseline metrics (units explicit — house rule) ----------------------
# The chain re-warns on EVERY evaluate (e.g. "NIIRS extrapolated outside the
# GIQE-5 range"), and the message embeds the live SNR/GSD, so Python's own dedup
# can't collapse it — a 7-point sweep would print the same warning ~14×. Capture
# warnings here and surface each DISTINCT one once, as a concise note; the sweep
# and mutation below then run silently (the caveat is already stated).
with warnings.catch_warnings(record=True) as _caught:
    warnings.simplefilter("always")
    result = sensor.evaluate()
regime = result.stage_outputs["optics"]["regime"]
print("=== Scenario {id}: {title} ===")
print(f"Radiometric regime : {{regime}}")
{metric_prints}
for _note in dict.fromkeys(str(_w.message).split(":")[0].strip() for _w in _caught):
    print(f"note: {{_note}}")

# --- 2) Trade sweep along the scenario variable -----------------------------
# The scripting console is a REPL: it echoes the value of every *bare* top-level
# statement. A loose ``ax.plot(...)`` or ``sensor.set(...)`` (which returns the
# Sensor for chaining) would spam the transcript, so the sweep + plot live in a
# function (their calls run silently); only the final bare ``fig`` is left for
# the console to pop out into its own window.
def _sweep_and_plot():
    center = {center!r}  # current {sweep_label} [{sweep_unit}]
    axis = np.linspace(0.75 * center, 1.25 * center, 7)
    snr = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # the caveat was already surfaced once above
        for v in axis:
            sensor.set("{sweep_dot}", float(v))
            snr.append(sensor.evaluate().metrics["snr"])
    sensor.set("{sweep_dot}", center)  # restore the baseline
    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    ax.plot(axis, snr, "o-")
    ax.set_xlabel("{sweep_label} [{sweep_unit}]")
    ax.set_ylabel("SNR [-]")
    ax.set_title("Scenario {id}: SNR vs {sweep_label_lower}")
    ax.grid(alpha=0.3)
    return fig


fig = _sweep_and_plot()


# --- 3) Mutate one parameter + re-evaluate (exercises the stale banner) ------
def _mutation_demo():
    baseline = sensor.get("{sweep_dot}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # the caveat was already surfaced once above
        before = sensor.evaluate().metrics["snr"]
        sensor.set("{sweep_dot}", 1.10 * baseline)
        after = sensor.evaluate().metrics["snr"]
    sensor.set("{sweep_dot}", baseline)  # leave the config as opened
    print(f"+10% {sweep_label_lower}: SNR {{before:.2f}} -> {{after:.2f}} [-]")


_mutation_demo()

# A bare Figure on the last line: the scripting console routes it through its
# display hook and pops it out into its own window (MATLAB "see the plot").
# Under ``python <file>`` this is a harmless no-op.
fig
'''


def _metric_prints(scen: GuiScenario) -> str:
    lines = []
    for key in scen.metrics:
        unit = _METRIC_UNIT.get(key, "[-]")
        label = key.replace("_", " ")
        lines.append(
            f'print(f"{label:<18.18s} : {{result.metrics.get({key!r}):.4g}} {unit}")'
            if unit != "[-]"
            else f'print(f"{label:<18.18s} : {{result.metrics.get({key!r}):.4g}} {unit}")'
        )
    return "\n".join(lines)


def generate_one(scen: GuiScenario) -> Path:
    # Read the already-emitted baseline (fast) rather than re-importing the
    # runner (which, for unguarded runners, re-runs the whole analysis).
    from radiant.api import Sensor

    if not scen.yaml_path.is_file():
        raise FileNotFoundError(f"{scen.id}: run emit_gui_yaml.py first ({scen.yaml_path} missing)")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sensor = Sensor.load(scen.yaml_path)
        sweep_dot, sweep_label, sweep_unit, center = _pick_sweep(scen, sensor)
    notes_block = scen.notes or "baseline is the scenario's nominal operating point."
    text = _TEMPLATE.format(
        id=scen.id,
        title=scen.title,
        slug=scen.slug,
        notes_block=notes_block,
        metric_prints=_metric_prints(scen),
        sweep_dot=sweep_dot,
        sweep_label=sweep_label,
        sweep_label_lower=sweep_label.lower(),
        sweep_unit=sweep_unit,
        center=center,
    )
    scen.gui_script_path.parent.mkdir(parents=True, exist_ok=True)
    scen.gui_script_path.write_text(text, encoding="utf-8", newline="\n")
    return scen.gui_script_path


def main(argv: list[str]) -> int:
    wanted = set(argv[1:])
    scenarios = [s for s in REGISTRY if not wanted or s.id in wanted]
    repo = Path(__file__).resolve().parents[2]
    for scen in scenarios:
        try:
            path = generate_one(scen)
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] {scen.id:>4}  {type(exc).__name__}: {exc}")
            continue
        print(f"[ ok ] {scen.id:>4}  ->  {path.relative_to(repo)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
