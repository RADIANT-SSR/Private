# GUI scripting-window script — Scenario 10.2: Air-to-air level IRST — horizontal arm, target kinematics
#
# HOW TO USE
#   1. In the RADIANT GUI: File -> Open YAML -> inputs/10.2_air_to_air_level_irst.gui.yaml
#      (the baseline derived from the validated scenario runner).
#   2. Open the scripting window (Ctrl+Shift+P); it binds ``sensor``,
#      ``result``, ``plot`` and the ``Sensor`` class into the namespace.
#   3. Paste this script and Run. The figure pops out into its own window;
#      the parameter change marks the main view stale (click Refresh).
#
# NOTE: scene_class air_to_air; los_direction level; Δh sag pill on the schematic.
#
# NB: the header is comments, not a docstring — the console is a REPL and would
# echo a bare """string""" back into the transcript. Also runs standalone
# (headless smoke test): python scripts/gui_console_10.2_air_to_air_level_irst.py

# --- bootstrap: use the live GUI ``sensor`` if present, else load the YAML ---
try:
    sensor  # bound by the GUI scripting window
except NameError:
    from pathlib import Path as _Path

    from radiant.api import Sensor

    sensor = Sensor.load(
        _Path(__file__).resolve().parent.parent / "inputs" / "10.2_air_to_air_level_irst.gui.yaml"
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
print("=== Scenario 10.2: Air-to-air level IRST — horizontal arm, target kinematics ===")
print(f"Radiometric regime : {regime}")
print(f"snr                : {result.metrics.get('snr'):.4g} [-]")
print(f"contrast snr       : {result.metrics.get('contrast_snr'):.4g} [-]")
print(f"detection range m  : {result.metrics.get('detection_range_m'):.4g} [-]")
for _note in dict.fromkeys(str(_w.message).split(":")[0].strip() for _w in _caught):
    print(f"note: {_note}")

# --- 2) Trade sweep along the scenario variable -----------------------------
# The scripting console is a REPL: it echoes the value of every *bare* top-level
# statement. A loose ``ax.plot(...)`` or ``sensor.set(...)`` (which returns the
# Sensor for chaining) would spam the transcript, so the sweep + plot live in a
# function (their calls run silently); only the final bare ``fig`` is left for
# the console to pop out into its own window.
def _sweep_and_plot():
    center = 50000.0  # current Level-arm slant range [km]
    axis = np.linspace(0.75 * center, 1.25 * center, 7)
    snr = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # the caveat was already surfaced once above
        for v in axis:
            sensor.set("geometry.target_range_m", float(v))
            snr.append(sensor.evaluate().metrics["snr"])
    sensor.set("geometry.target_range_m", center)  # restore the baseline
    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    ax.plot(axis, snr, "o-")
    ax.set_xlabel("Level-arm slant range [km]")
    ax.set_ylabel("SNR [-]")
    ax.set_title("Scenario 10.2: SNR vs level-arm slant range")
    ax.grid(alpha=0.3)
    return fig


fig = _sweep_and_plot()


# --- 3) Mutate one parameter + re-evaluate (exercises the stale banner) ------
def _mutation_demo():
    baseline = sensor.get("geometry.target_range_m")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # the caveat was already surfaced once above
        before = sensor.evaluate().metrics["snr"]
        sensor.set("geometry.target_range_m", 1.10 * baseline)
        after = sensor.evaluate().metrics["snr"]
    sensor.set("geometry.target_range_m", baseline)  # leave the config as opened
    print(f"+10% level-arm slant range: SNR {before:.2f} -> {after:.2f} [-]")


_mutation_demo()

# A bare Figure on the last line: the scripting console routes it through its
# display hook and pops it out into its own window (MATLAB "see the plot").
# Under ``python <file>`` this is a harmless no-op.
fig
