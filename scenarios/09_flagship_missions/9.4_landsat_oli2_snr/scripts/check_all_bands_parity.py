"""Scenario 9.4 acceptance check: all-bands study vs. the nine per-band standalones.

`oli2_all_bands_study.yaml` holds all nine Landsat 9 OLI-2 bands as one
configuration set (ADR-0010 + Gap 103 v1.1): one shared instrument, a configured
`band_filter` element row carrying each band's own synthesized interference strip,
and configured scalars for the values the bands genuinely differ in. The nine
`oli2_b0N_snr_ltyp.yaml` files are the same nine models written out one per file.

Why parity is expected to machine precision, not merely to plotting accuracy:
`ConfigurationSet.sensor_for(name)` materializes a configuration by cloning the
shared base, applying that configuration's configured values, and attaching its
effective optical-element document. If the study's shared body plus band N's
configured values reproduce standalone N's document field for field — same band
edges, so the same spectral grid span at the same (default, 500) point count;
same filter CSV; same QE, dark rate, pitch, and integration time — then the two
runs drive *identical* parameter sets through *identical* stages. Identical
inputs to a deterministic chain give bit-comparable outputs, so the acceptance
bar is rel < 1e-9 (floating-point re-association headroom), not a physics
tolerance. A band that misses the bar is not a rounding artifact: it means the
study and the standalone are describing different sensors, and the study is what
gets fixed.

Regime: extended source in every band (`source.scene_type: extended`, uniform
scene fills the pixel — the regime OLI's per-detector uniform-scene SNR is
defined in). EE_box is therefore not applied (Rule 9) and the spatial path runs
at platform defaults; the claim under test here is radiometric only.

Usage (from the repo root, so `radiant` resolves to this checkout — CU-338):

    PYTHONPATH=./src python \\
      scenarios/09_flagship_missions/9.4_landsat_oli2_snr/scripts/check_all_bands_parity.py

Exit status: 0 when every band satisfies rel < 1e-9, 1 otherwise.
"""

from __future__ import annotations

import sys
from pathlib import Path

from radiant.api import ConfigurationSet, Sensor

#: Acceptance bar (Configuration_Set_Expansion_Plan.md §5, criterion 3).
REL_TOLERANCE: float = 1e-9

SCENARIO_DIR: Path = Path(__file__).resolve().parent.parent
STUDY_PATH: Path = SCENARIO_DIR / "oli2_all_bands_study.yaml"

#: Configuration name -> its per-band standalone config file.
STANDALONE_BY_CONFIG: dict[str, str] = {
    "B1_CA": "oli2_b01_snr_ltyp.yaml",
    "B2_Blue": "oli2_b02_snr_ltyp.yaml",
    "B3_Green": "oli2_b03_snr_ltyp.yaml",
    "B4_Red": "oli2_b04_snr_ltyp.yaml",
    "B5_NIR": "oli2_b05_snr_ltyp.yaml",
    "B6_SWIR1": "oli2_b06_snr_ltyp.yaml",
    "B7_SWIR2": "oli2_b07_snr_ltyp.yaml",
    "B8_Pan": "oli2_b08_snr_ltyp.yaml",
    "B9_Cirrus": "oli2_b09_snr_ltyp.yaml",
}


def _relative_difference(study: float, standalone: float) -> float:
    """|study - standalone| / |standalone| [-], with a 0-vs-0 guard."""
    if standalone == 0.0:
        return 0.0 if study == 0.0 else float("inf")
    return abs(study - standalone) / abs(standalone)


def main() -> int:
    """Evaluate both sides, print the comparison table, return the exit status."""
    print("Scenario 9.4 — Landsat 9 OLI-2 all-bands study vs. per-band standalones")
    print(f"Study: {STUDY_PATH.name}")
    print(
        "Regime: extended (uniform scene fills the pixel) in every band — "
        "EE_box not applied (Rule 9); the claim under test is radiometric."
    )
    print(
        "Parity is exact-by-construction: the study materializes each band into the "
        "same effective document its standalone file states, so both sides drive an "
        f"identical chain. Acceptance bar: rel < {REL_TOLERANCE:.0e} [-]."
    )
    print()

    config_set = ConfigurationSet.load(STUDY_PATH)
    run = config_set.evaluate_all()

    study_snr: dict[str, float] = {}
    for entry in run.entries:
        if entry.error is not None:
            print(f"  {entry.name}: study configuration FAILED to evaluate: {entry.error}")
            return 1
        assert entry.result is not None  # entry.ok implies a result (ConfigRun contract)
        study_snr[entry.name] = entry.result.snr()

    header = (
        f"{'Band':<10} {'study SNR [-]':>16} {'standalone SNR [-]':>20} "
        f"{'rel diff [-]':>14}  {'verdict':<7}"
    )
    print(header)
    print("-" * len(header))

    failures: list[str] = []
    for name in config_set.names():
        standalone_file = SCENARIO_DIR / STANDALONE_BY_CONFIG[name]
        standalone = Sensor.from_yaml(standalone_file).evaluate().snr()
        study = study_snr[name]
        rel = _relative_difference(study, standalone)
        passed = rel < REL_TOLERANCE
        if not passed:
            failures.append(name)
        print(
            f"{name:<10} {study:>16.9f} {standalone:>20.9f} "
            f"{rel:>14.2e}  {'PASS' if passed else 'FAIL':<7}"
        )

    print()
    if failures:
        print(
            f"FAIL — {len(failures)} of {len(study_snr)} bands miss rel < "
            f"{REL_TOLERANCE:.0e} [-]: {', '.join(failures)}."
        )
        print(
            "  A miss means the study's effective document for that band differs from "
            "its standalone — check the configured scalars (band edges, radiance path, "
            "QE, dark rate, pitch, integration time), the configured filter row's entry, "
            "and the spectral grid point count. Fix the study, never the standalone and "
            "never this tolerance."
        )
        return 1

    print(
        f"PASS — all {len(study_snr)} bands reproduce their standalone to "
        f"rel < {REL_TOLERANCE:.0e} [-]."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
