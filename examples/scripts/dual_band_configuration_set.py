#!/usr/bin/env python3
"""Dual-band configuration-set study — MWIR vs LWIR on one telescope.

Usage::

    python examples/scripts/dual_band_configuration_set.py

What this demonstrates
----------------------
The multi-configuration API (:class:`radiant.api.ConfigurationSet`, ADR-0010):
**one** modeling problem carrying several named configurations of itself, all
evaluated in one pass and compared side by side. The interaction model is CODE V
zoom configurations — a parameter is *shared* (one value for every
configuration) until you explicitly ``configure()`` it, at which point it
carries one value per configuration, densely, never sparsely.

The study is a single 0.30 m f/4 telescope at 8 km altitude looking straight
down at a 300 K, ε = 0.95 extended scene through a mid-latitude-summer
atmosphere (the shared base is ``examples/mwir_leo_minimal.yaml``), read out on
one 18 µm-pitch FPA, operated in three ways:

===============  =============================================================
``MWIR``         3.5–5.0 µm, 5.0 ms integration, QE 0.70, 2.0 Me- well
``LWIR``         8.0–12.0 µm, 0.5 ms integration, QE 0.55, 6.0 Me- well
``LWIR_long``    identical to ``LWIR`` but integrated 4× longer (2.0 ms) —
                 a deliberately over-integrated design that saturates the well
===============  =============================================================

Only the parameters that actually differ between the three are configured;
aperture, focal length, altitude, scene temperature, emissivity, pixel pitch,
read noise, and the atmosphere are shared, so a change to any of them moves all
three configurations at once. That is the point of the model: the study states
what differs, not what is repeated.

Along the way the script exercises the Phase-3 orchestration surface:

* ``evaluate_all()`` — every configuration evaluated in one pass, the active
  configuration first, per-configuration failures recorded rather than raised.
* per-configuration **warning attribution** — the saturation warnings raised by
  ``LWIR_long`` are attached to ``LWIR_long`` and to nothing else.
* ``ConfigSetRunResult.summary()`` — one triage line per configuration.
* ``ConfigurationSet.compare()`` — the aligned metric × configuration matrix,
  with deltas measured against the set's designated baseline.
* ``save()`` / ``load()`` — the whole study is one YAML file and survives a
  round trip (demonstrated here into a temporary directory).

Physics notes this script prints and explains
---------------------------------------------
* **Regime.** No target extent is specified, so every configuration classifies
  as EXTENDED (the scene fills the pixel footprint). This is decided once, in
  ``OpticsStage`` (architecture Rule 10), per configuration.
* **Same GSD, different blur.** GSD is set by pitch, focal length, and range —
  all shared — so all three configurations see 0.12 m ground sample. The
  *optical* blur is not shared: diffraction scales with λ, so the LWIR
  configurations are ~2.4× blurrier at identical sampling.
* **The sampling regime flips between bands.** Q = λ·f/# / pitch is 0.94 in the
  MWIR (undersampled — detector-limited, aliasing possible) and 2.22 in the
  LWIR (oversampled — optics-limited). One telescope, one FPA, two different
  imaging regimes purely from the band.
* **Saturation is a per-configuration property.** ``LWIR_long`` clips; its
  reported SNR reflects a clipped signal and must not be read as a better
  design. The chain says so out loud, and the warning is attributed to that
  configuration alone.

Why a module docstring and not a companion walkthrough
------------------------------------------------------
``examples/`` in this repository carries no walkthrough-markdown convention —
its scripts are self-documenting, with the explanation in the module docstring
and in the printed output (contrast ``scenarios/``, which does use walkthroughs).
This script follows the ``examples/`` convention.

Units
-----
Every number this script prints carries its unit, in the printed output as well
as in the tables (project hard rule). Metric units come from the RADIANT metric
registry via ``ChainResult.metric_records()`` — they are never spelled out by
hand here.
"""

from __future__ import annotations

import logging
import sys
import tempfile
from pathlib import Path

from radiant.api import ConfigSetRunResult, ConfigurationSet, Sensor

BASE_CONFIG = Path(__file__).resolve().parent.parent / "mwir_leo_minimal.yaml"

# Coarse enough to run in a few seconds, fine enough that band-integrated
# radiometry is converged to well under a percent.
WAVELENGTH_POINTS = 300

# Metrics worth walking through one by one for this particular study. The full
# union-of-metrics matrix is printed too; this is the guided tour.
FOCUS_METRICS = (
    "snr",
    "nedt_K",
    "gsd_geometric_mean_m",
    "diffraction_limit_ground_m",
    "q_center",
    "mtf_at_nyquist",
    "ee_1x1",
    "well_margin_dB",
)


def build_study() -> ConfigurationSet:
    """Build the three-configuration dual-band study.

    The base sensor is the shared state; ``configure()`` moves a parameter out
    of it and gives it one value per configuration (ADR-0010 single-store
    invariant — a parameter is shared *or* configured, never both).
    """
    base = Sensor.from_yaml(BASE_CONFIG, wavelength_points=WAVELENGTH_POINTS)
    study = ConfigurationSet(base, names=["MWIR", "LWIR", "LWIR_long"])

    # --- band definition -------------------------------------------------
    study.configure("spectral_integration.filter_min_um", [3.5, 8.0, 8.0])
    study.configure("spectral_integration.filter_max_um", [5.0, 12.0, 12.0])

    # --- what the band forces on the rest of the design ------------------
    # LWIR photon flux from a 300 K scene is ~an order of magnitude higher than
    # MWIR, so the LWIR configurations integrate far shorter into a deeper well.
    study.configure("spectral_integration.integration_time_s", [0.005, 0.0005, 0.002])
    study.configure("detector.qe_value", [0.70, 0.55, 0.55])
    study.configure("detector.dark_rate_e_per_s", [1.0e5, 2.0e6, 2.0e6])
    study.configure("readout.full_well_capacity_e", [2.0e6, 6.0e6, 6.0e6])
    # Gain matched to well / 2^16 in each configuration, so the ADC spans the
    # well it is actually digitizing rather than a shared compromise value.
    study.configure("readout.gain_e_per_dn", [32.0, 92.0, 92.0])

    study.baseline = "MWIR"  # deltas in compare() are measured against this
    study.active = "MWIR"  # evaluated first (this is the GUI's displayed one)
    return study


def print_study_definition(study: ConfigurationSet) -> None:
    """Show what is shared and what is configured, with units."""
    print("=" * 78)
    print("Dual-band configuration-set study — MWIR vs LWIR on one telescope")
    print("=" * 78)
    print()
    print(f"Base config file : {BASE_CONFIG.name}")
    print(f"Spectral grid    : {WAVELENGTH_POINTS} points per configuration")
    print(f"Configurations   : {', '.join(study.names())}")
    print(f"Baseline         : {study.baseline!r}   (delta reference)")
    print(f"Active           : {study.active!r}   (evaluated first)")
    print()

    print("Configured parameters (one value per configuration, in input units)")
    print("-" * 78)
    header = f"{'parameter':<44}{'unit':<10}" + "".join(f"{n:>12}" for n in study.names())
    print(header)
    for dotpath, values in sorted(study.configured().items()):
        unit = study.base.parameter_def(dotpath).input_unit or "-"
        cells = "".join(f"{v:>12.6g}" for v in values)
        print(f"{dotpath:<44}{unit:<10}{cells}")
    print()

    # Read the base's explicit inputs directly: once the band-defining
    # parameters are configured they have LEFT the base, so the base on its own
    # is deliberately un-resolvable — asking it to resolve would be a category
    # error. Only a materialized configuration resolves.
    shared = dict(study.base.inputs())
    print(f"Shared parameters ({len(shared)} — one value for ALL configurations)")
    print("-" * 78)
    for dotpath in sorted(shared):
        pdef = study.base.parameter_def(dotpath)
        print(f"  {dotpath:<42}{shared[dotpath]!s:>14}  {pdef.input_unit or '-'}")
    print()
    print("  unit '-' means the schema declares no unit string: the quantity is")
    print("  dimensionless (qe_value, transmission, adc_bits, emissivity) or")
    print("  names its unit in the parameter itself (…_e = electrons,")
    print("  …_um = micrometres, …_e_per_dn = electrons per digital number).")
    print()
    print("  A change to any shared parameter above moves all three")
    print("  configurations together — that is the whole point of the model.")
    print()


def print_run_summary(study: ConfigurationSet, run: ConfigSetRunResult) -> None:
    """Print the triage summary and the per-configuration warnings."""
    print("=" * 78)
    print("evaluate_all() — one pass over every configuration")
    print("=" * 78)
    print()
    print("Summary (one line per configuration, evaluation order = active first):")
    print()
    for line in run.summary().splitlines():
        print(f"  {line}")
    print()

    warnings_by_config = run.warnings
    print("Warning attribution — each warning belongs to exactly one configuration:")
    print()
    if not warnings_by_config:
        print("  (none — every configuration ran clean)")
    for name in study.names():
        messages = warnings_by_config.get(name, ())
        if not messages:
            print(f"  {name:<12} no warnings")
            continue
        print(f"  {name:<12} {len(messages)} warning(s):")
        for message in messages:
            print(f"      - {message}")
    print()
    print("  The warnings above were raised inside the chain while that ONE")
    print("  configuration evaluated. They are recorded on the result (and")
    print("  logged), never re-raised into the caller's warning filters, so a")
    print("  noisy configuration cannot be mistaken for a property of the study.")
    print()


def print_comparison(study: ConfigurationSet, run: ConfigSetRunResult) -> None:
    """Print the focused walk-through and then the full comparison matrix."""
    comparison = study.compare(run)
    baseline = comparison.labels[comparison.baseline_index]

    print("=" * 78)
    print(f"compare() — metric x configuration, deltas vs baseline {baseline!r}")
    print("=" * 78)
    print()
    print("Focus metrics (value [unit], then delta vs baseline):")
    print()
    name_w = max(len(m) for m in FOCUS_METRICS) + 2
    header = f"{'metric':<{name_w}}{'unit':<16}" + "".join(
        f"{label:>26}" for label in comparison.labels
    )
    print(header)
    print("-" * len(header))
    for metric in FOCUS_METRICS:
        row = comparison.row(metric)
        cells = ""
        for value, delta in zip(row.values, row.deltas, strict=True):
            if value is None:
                # Rule 17: a metric this configuration did not compute is shown
                # absent. It is never zero-filled — zero is a physical answer.
                cells += f"{'— (not computed)':>26}"
            elif delta is None or delta == 0.0:
                cells += f"{value:>26.6g}"
            else:
                cells += f"{value:>14.6g} ({delta:+.3g})".rjust(26)
        print(f"{metric:<{name_w}}{row.unit:<16}{cells}")
    print()
    print("  '*' in the full table below marks the best value for that metric")
    print("  (higher-is-better by default; NEDT / GSD / FWHM lower-is-better).")
    print("  Read those marks with the warnings in hand: they are a mechanical")
    print("  comparison of numbers, so a saturated configuration whose signal")
    print("  was clipped can still collect a '*' on SNR and NEDT. It has not")
    print("  won anything — see section 5 below.")
    print()
    print("Full union-of-metrics matrix (every metric any configuration computed):")
    print()
    for line in comparison.to_table().splitlines():
        print(f"  {line}")
    print()


def print_physics_discussion(study: ConfigurationSet, run: ConfigSetRunResult) -> None:
    """Explain regime, the non-obvious results, and the irrelevant parameters."""
    results = {name: run.result_for(name) for name in study.names()}

    print("=" * 78)
    print("Reading the results — regime, non-obvious behavior, unused parameters")
    print("=" * 78)
    print()

    print("1. Radiometric regime (decided once, in OpticsStage — Rule 10)")
    print("-" * 78)
    for name, result in results.items():
        regime = result.stage_outputs["optics"]["regime"]
        print(f"  {name:<12} {getattr(regime, 'value', regime)}")
    print()
    print("  No target extent is given, so the 300 K scene fills the pixel")
    print("  footprint in every configuration: all three are EXTENDED. In this")
    print("  regime the target signal is a radiance integrated over the pixel")
    print("  solid angle, so the ensquared-energy fraction EE_box is NOT applied")
    print("  to the signal (architecture Rule 9) — it is reported as a spatial")
    print("  metric (ee_1x1, ee_3x3) but does not scale the electrons.")
    print()

    print("2. Parameters that carry no weight in THIS study")
    print("-" * 78)
    print("  - Point-source / sub-pixel inputs (target area, radiant intensity,")
    print("    sub-pixel fill fraction) are unused: the regime is EXTENDED, so")
    print("    the chain never enters the point-source branch.")
    print("  - EE_box is computed but not applied to the signal (Rule 9, above);")
    print("    ee_1x1 and ee_3x3 below are therefore diagnostics here, not")
    print("    throughput factors.")
    print("  - Platform jitter / smear are at their defaults and identical in")
    print("    all three configurations, so they cancel out of every delta in")
    print("    the comparison above — they are shared, not configured.")
    print("  - detector.dark_rate_e_per_s IS configured and matters: it fills")
    print("    the well alongside the signal (see well_margin_dB), but at these")
    print("    integration times it is not the dominant noise term.")
    print()

    print("3. Same telescope, same GSD, different imaging regime")
    print("-" * 78)
    for name, result in results.items():
        m = result.metrics
        print(
            f"  {name:<12} GSD = {m['gsd_geometric_mean_m']:>6.4g} m   "
            f"diffraction blur = {m['diffraction_limit_ground_m']:>6.4g} m   "
            f"Q = {m['q_center']:>5.3g} [dimensionless]"
        )
    print()
    print("  GSD comes from pixel pitch, focal length, and slant range — all")
    print("  shared — so it is identical in all three: 0.12 m. The diffraction")
    print("  blur is NOT shared: it scales with wavelength, so the LWIR spot on")
    print("  the ground is ~2.4x wider from the very same 0.30 m aperture.")
    print()
    print("  Q = lambda x f/# / pitch < 1 (MWIR) means detector-limited and")
    print("  undersampled: the optics pass more detail than the 18 um pixels can")
    print("  sample, and MTF at Nyquist stays high. Q > 2 (LWIR) means")
    print("  optics-limited and oversampled: diffraction cuts the MTF off BELOW")
    print("  Nyquist, so mtf_at_nyquist collapses toward zero. One FPA, one")
    print("  telescope, two genuinely different imaging regimes — chosen only by")
    print("  the band. That is the result this whole study exists to show.")
    print()
    print("  Consequence to read carefully: mrt_at_nyquist_K in the full matrix")
    print("  scales as 1/MTF, so for the LWIR configurations (MTF -> 0 at")
    print("  Nyquist) it diverges to an absurd number of kelvin. That is the")
    print("  metric reporting 'this system resolves nothing at Nyquist in this")
    print("  band', not a physical temperature — evaluate LWIR resolution at a")
    print("  frequency below the optical cutoff instead.")
    print()
    print("  Known defect (CU-209): mtf_folded_at_nyquist and")
    print("  alias_fraction_at_nyquist fold at f_Nyquist rather than at the")
    print("  sampling frequency 2 x f_Nyquist, so those two rows do not follow")
    print("  the picture above (an oversampled band should show no aliasing).")
    print("  Ignore them in this study until that CU closes.")
    print()

    print("4. Sensitivity: comparable NEDT, ten times less integration time")
    print("-" * 78)
    for name, result in results.items():
        m = result.metrics
        t_int = study.configured()["spectral_integration.integration_time_s"][
            study.names().index(name)
        ]
        print(
            f"  {name:<12} t_int = {t_int * 1e3:>6.4g} ms   "
            f"SNR = {m['snr']:>7.4g} [dimensionless]   "
            f"NEDT = {m['nedt_K'] * 1e3:>6.4g} mK   "
            f"well fill = {result.well_status().fill_fraction * 100:>5.1f} %"
        )
    print()
    print("  Read those rows together, not column by column. The LWIR")
    print("  configuration reaches an NEDT within ~15 % of the MWIR one while")
    print("  integrating TEN TIMES shorter — and it still fills a well three")
    print("  times deeper to 59 %. That is the non-obvious result: at 300 K the")
    print("  scene's spectral radiance peaks near 9.7 um, and dL/dT (the")
    print("  radiance change per kelvin, which is what NEDT actually measures)")
    print("  is far larger in absolute terms in the LWIR. The band is not")
    print("  photon-starved, it is well-depth-limited.")
    print()
    print("  So the honest comparison is not 'which NEDT number is smaller'. At")
    print("  equal integration time the LWIR configuration would be decisively")
    print("  more sensitive; it cannot use equal integration time on this FPA")
    print("  because the well saturates first — which is exactly what the")
    print("  LWIR_long configuration below demonstrates. The MWIR's real")
    print("  advantage is the opposite one: higher *fractional* contrast per")
    print("  kelvin, which is why MWIR wins for hot targets, not 300 K scenes.")
    print()

    print("5. Why LWIR_long is not the better design its SNR suggests")
    print("-" * 78)
    long_status = results["LWIR_long"].well_status()
    lwir_status = results["LWIR"].well_status()
    print(
        f"  LWIR       well {lwir_status.total_well_e:.4g} e- of "
        f"{lwir_status.full_well_capacity_e:.4g} e-  "
        f"({lwir_status.fill_fraction * 100:.1f} %) -> {lwir_status.status}"
    )
    print(
        f"  LWIR_long  well {long_status.total_well_e:.4g} e- of "
        f"{long_status.full_well_capacity_e:.4g} e-  "
        f"({long_status.fill_fraction * 100:.1f} %) -> {long_status.status}"
    )
    print()
    if long_status.is_saturated:
        print("  LWIR_long saturates: 4x the integration time overfills a well")
        print("  that LWIR already fills to ~59 %. The chain clips the signal and")
        print("  says so (see the warnings above, attributed to LWIR_long alone).")
        print("  Its reported SNR and NEDT are computed from the CLIPPED signal,")
        print("  so they no longer respond to the scene at all — a saturated")
        print("  design reads as insensitive, not as high-performing. Trade")
        print("  integration time against well depth, not against SNR alone.")
    print()


def demonstrate_persistence(study: ConfigurationSet) -> None:
    """Save the whole study to one YAML file, reload it, and prove it round-trips."""
    print("=" * 78)
    print("Persistence — one study, one file")
    print("=" * 78)
    print()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "dual_band_study.yaml"
        study.save(path)
        size_bytes = path.stat().st_size
        reloaded = ConfigurationSet.load(path)

        print(f"  saved to    : {path.name}  ({size_bytes} bytes)")
        print(f"  names       : {reloaded.names()}  (order preserved)")
        print(f"  baseline    : {reloaded.baseline!r}")
        print(f"  active      : {reloaded.active!r}")
        print(f"  configured  : {len(reloaded.configured())} parameter(s)")
        print()

        same_names = reloaded.names() == study.names()
        same_table = dict(reloaded.configured()) == dict(study.configured())
        same_shared = dict(reloaded.base.inputs()) == dict(study.base.inputs())
        print(f"  names identical             : {same_names}")
        print(f"  configured table identical  : {same_table}")
        print(f"  shared parameters identical : {same_shared}")
        print()
        print("  The file is an ordinary RADIANT config file plus one")
        print("  'configurations:' section. A file without that section is")
        print("  byte-for-byte today's format and still loads as the degenerate")
        print("  one-configuration set.")
        print()
        # Show the section itself — it is short, and it is the whole study.
        section_lines = study.to_yaml().splitlines()
        start = next(i for i, ln in enumerate(section_lines) if ln.startswith("configurations:"))
        print("  configurations: section as written")
        print("  " + "-" * 60)
        for line in section_lines[start:]:
            print(f"  {line}")
        print()


def main() -> None:
    # evaluate_all() re-emits every warning it captured through `logging`, so
    # nothing is lost even if a caller ignores ConfigRun.warnings. Routing the
    # log to stdout here keeps those lines in order with the printed report
    # instead of racing it on stderr; they are the same warnings the
    # attribution section below reproduces per configuration.
    logging.basicConfig(
        level=logging.WARNING,
        format="[log] %(message)s",
        stream=sys.stdout,
    )

    study = build_study()
    print_study_definition(study)

    run = study.evaluate_all()
    print_run_summary(study, run)
    print_comparison(study, run)
    print_physics_discussion(study, run)
    demonstrate_persistence(study)

    print("=" * 78)
    print("Done. Configurations evaluated:", len(run.entries), "| failed:", run.n_failed)
    print("=" * 78)


if __name__ == "__main__":
    main()
