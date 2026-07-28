# GUI scripting-window script — Scenario 10.4: LEO→GEO exo SDA — θ_o = π, vacuum path
#
# HOW TO USE
#   1. In the RADIANT GUI: File -> Open YAML -> inputs/10.4_leo_to_geo_exo.gui.yaml
#      (the baseline derived from the validated scenario runner).
#   2. Open the scripting window (Ctrl+Shift+P); it binds ``sensor``,
#      ``result``, ``plot`` and the ``Sensor`` class into the namespace.
#   3. Paste this script and Run. The figure pops out into its own window;
#      the parameter change marks the main view stale (click Refresh).
#
# NOTE: scene_class space_to_space; wholly-vacuum up-looking path (τ = 1 exact).
#
# NB: the header is comments, not a docstring — the console is a REPL and would
# echo a bare """string""" back into the transcript. Also runs standalone
# (headless smoke test): python scripts/gui_console_10.4_leo_to_geo_exo.py

# --- bootstrap: use the live GUI ``sensor`` if present, else load the YAML ---
try:
    sensor  # bound by the GUI scripting window
except NameError:
    from pathlib import Path as _Path

    from radiant.api import Sensor

    sensor = Sensor.load(
        _Path(__file__).resolve().parent.parent / "inputs" / "10.4_leo_to_geo_exo.gui.yaml"
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
print("=== Scenario 10.4: LEO→GEO exo SDA — θ_o = π, vacuum path ===")
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
    center = 0.5  # current Integration time [ms]
    axis = np.linspace(0.75 * center, 1.25 * center, 7)
    snr = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # the caveat was already surfaced once above
        for v in axis:
            sensor.set("spectral_integration.integration_time_s", float(v))
            snr.append(sensor.evaluate().metrics["snr"])
    sensor.set("spectral_integration.integration_time_s", center)  # restore the baseline
    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    ax.plot(axis, snr, "o-")
    ax.set_xlabel("Integration time [ms]")
    ax.set_ylabel("SNR [-]")
    ax.set_title("Scenario 10.4: SNR vs integration time")
    ax.grid(alpha=0.3)
    return fig


fig = _sweep_and_plot()


# --- 3) Mutate one parameter + re-evaluate (exercises the stale banner) ------
def _mutation_demo():
    baseline = sensor.get("spectral_integration.integration_time_s")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # the caveat was already surfaced once above
        before = sensor.evaluate().metrics["snr"]
        sensor.set("spectral_integration.integration_time_s", 1.10 * baseline)
        after = sensor.evaluate().metrics["snr"]
    sensor.set("spectral_integration.integration_time_s", baseline)  # leave the config as opened
    print(f"+10% integration time: SNR {before:.2f} -> {after:.2f} [-]")


_mutation_demo()

# A bare Figure on the last line: the scripting console routes it through its
# display hook and pops it out into its own window (MATLAB "see the plot").
# Under ``python <file>`` this is a harmless no-op.
fig
