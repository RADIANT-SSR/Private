#!/usr/bin/env python
"""Render MODTRAN tape5 INPUT decks for every run in the run matrix.

Reads ``docs/plans/modtran_run_matrix.csv`` and, for each row, builds a
``ModtranConfig`` + ``AtmosphericGeometry`` from its columns and renders
the tape5 deck via ``radiant.atmosphere.modtran.render_tape5``.

This produces INPUT decks only. It does not run MODTRAN and it does
not fabricate tape7 OUTPUT — tape5 rendering is deterministic (pure
card-image formatting), but the radiative-transfer result is not;
synthesizing plausible-looking tape7 data would misrepresent RADIANT's
own physics as an independent reference and defeat the purpose of
``docs/archive/MODTRAN_Run_Matrix_Plan.md``. Running each deck through a
real MODTRAN binary remains a manual step.

Usage::

    python scripts/render_modtran_decks.py
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from radiant.atmosphere.modtran import (  # noqa: E402
    _IHAZE_MAP,
    ModtranConfig,
    render_tape5,
)
from radiant.atmosphere.protocol import AtmosphericGeometry  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MATRIX_CSV = _REPO_ROOT / "docs" / "plans" / "modtran_run_matrix.csv"
_OUTPUT_DIR = _REPO_ROOT / "modtran" / "decks"


def _row_to_config(row: dict[str, str]) -> ModtranConfig:
    if _IHAZE_MAP[row["aerosol"]] != int(row["ihaze"]):
        raise ValueError(
            f"{row['run_id']}: matrix aerosol={row['aerosol']!r} maps to IHAZE="
            f"{_IHAZE_MAP[row['aerosol']]}, but the row's ihaze column says "
            f"{row['ihaze']!r}. Fix the CSV before rendering."
        )
    vis_km = float(row["vis_km"]) if row["vis_km"].strip() else None
    hrange_str = row.get("hrange_km", "").strip()
    return ModtranConfig(
        atmosphere_profile=row["profile"],
        aerosol_model=row["aerosol"],
        h2o_scale=float(row["h2o_scale"]),
        o3_scale=float(row["o3_scale"]),
        visibility_km=vis_km,
        itype=int(row["itype"]),
        iemsct=int(row["iemsct"]),
        hrange_km=float(hrange_str) if hrange_str else 0.0,
        spectral_resolution_cm1=float(row["dv_cm1"]),
        v1_cm1=float(row["v1_cm1"]),
        v2_cm1=float(row["v2_cm1"]),
    )


def _row_to_geometry(row: dict[str, str]) -> AtmosphericGeometry:
    """Build the deck's geometry carrier from a run-matrix row.

    ITYPE=1 (horizontal) rows are the one case where the row's
    ``path_zenith_deg_radiant`` column (90°) is *not* passed through.
    ``AtmosphericGeometry`` deliberately refuses zenith angles past
    ``protocol.ZENITH_CEILING_RAD`` (89.5°) because that is where the
    column air-mass model stops meaning anything — and a level path's 90°
    is not a column zenith at all: it is an interior-tangent topology whose
    lowest point is mid-path (Geometry_Flexibility_Plan §8.3 addendum).
    ``render_tape5`` therefore writes the horizontal ANGLE = 90.000 itself
    for ITYPE=1 and never reads ``path_zenith_rad``, so the value carried
    here is inert for those rows.
    """
    zenith_str = row["path_zenith_deg_radiant"].strip()
    path_zenith_rad = math.radians(float(zenith_str)) if zenith_str else 0.0
    if int(row["itype"]) == 1:
        path_zenith_rad = 0.0
    return AtmosphericGeometry(
        sensor_altitude_m=float(row["h1_sensor_km"]) * 1000.0,
        target_altitude_m=float(row["h2_target_km"]) * 1000.0,
        path_zenith_rad=path_zenith_rad,
        solar_zenith_rad=math.radians(float(row["solar_zenith_deg"])),
        solar_azimuth_rad=math.radians(float(row["solar_azimuth_deg"])),
    )


def _rendered_card3_angle_deg(tape5: str) -> float:
    """Read ANGLE back from the rendered deck's Card 3 (H1, H2, ANGLE, ...).

    Parsed from the deck rather than recomputed here so the manifest
    reports what render_tape5 actually wrote (no drift between the
    renderer's CU-065 zenith→ANGLE conversion and this check).
    """
    return float(tape5.splitlines()[4].split()[2])


def _blank_zenith_caveat(row: dict[str, str]) -> str:
    """Explain a blank ``path_zenith_deg_radiant`` for the row that has one.

    Two different situations leave the column blank, and they need
    different instructions:

    * **IEMSCT=3** (Block E, solar-irradiance mode) — RADIANT's
      line-of-sight zenith concept does not apply to a ground-level
      irradiance calculation at all, so there is nothing to write.
    * **A path RADIANT cannot carry** (batch-2 Block Q twilight tangent
      transits) — the geometry is a real line of sight, but its
      lower-endpoint zenith exceeds ``protocol.ZENITH_CEILING_RAD``
      (89.5°), which ``AtmosphericGeometry`` refuses. The column is blank
      because the value is unrepresentable, not because it is meaningless,
      and the deck must be hand-edited from ``modtran_angle_at_h1_deg``
      before it is run.

    Both render Card-3 ANGLE as a 0 placeholder, so the manifest has to say
    which one it is.
    """
    if int(row["iemsct"]) == 3:
        return (
            "IEMSCT=3 irradiance mode: path_zenith_rad not "
            "physically meaningful here (ANGLE driven by solar "
            "geometry instead); rendered as 0"
        )
    return (
        "path_zenith_deg_radiant blank: this row's lower-endpoint zenith "
        "is past AtmosphericGeometry's 89.5 deg ceiling (a tangent/limb "
        "transit), so RADIANT cannot carry it; rendered as 0 — hand-set "
        "Card 3 ANGLE from modtran_angle_at_h1_deg before running"
    )


def _angle_caveat(row: dict[str, str], rendered_angle_deg: float) -> str:
    """Flag rows where the deck's ANGLE differs from the matrix's
    hand-worked H1-relative column.

    Since the CU-065 deck-side fix, render_tape5 converts RADIANT's
    lower-endpoint path zenith to MODTRAN's ANGLE-at-H1 convention
    (nadir-from-space renders 180), so every ITYPE=2 row now matches
    the matrix. A residual mismatch means this row's ANGLE is not
    derivable from path_zenith at all (Block E drives it from solar
    geometry instead) — hand-set it per the matrix before running.
    CU-065 residue: the convention is verified against the run
    matrix's own worked column, not yet the MODTRAN manual.
    """
    expected = float(row["modtran_angle_at_h1_deg"])
    if abs(expected - rendered_angle_deg) > 1e-6:
        return (
            f"deck ANGLE={rendered_angle_deg:g} deg; matrix wants "
            f"{expected:g} deg at H1 — this row's ANGLE is not derived "
            "from path_zenith (see other caveats); set it per the matrix "
            "before running"
        )
    return ""


def main() -> None:
    with _MATRIX_CSV.open() as f:
        rows = list(csv.DictReader(f))

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest_lines = [
        "# MODTRAN Deck Manifest",
        "",
        "> Generated by `scripts/render_modtran_decks.py` from "
        "`docs/plans/modtran_run_matrix.csv`. Regenerate on demand; do "
        "not hand-edit.",
        "",
        "These are rendered tape5 **input** decks only — no tape7 "
        "output is included or fabricated. Run each deck through a "
        "real MODTRAN binary to produce validation data; see "
        "`../README.md`.",
        "",
        "| run_id | block | profile | iemsct | itype | hrange_km | destination | caveats |",
        "|--------|-------|---------|--------|-------|-----------|-------------|---------|",
    ]

    for row in rows:
        run_id = row["run_id"]
        config = _row_to_config(row)
        geometry = _row_to_geometry(row)
        tape5 = render_tape5(config, geometry)
        (_OUTPUT_DIR / f"{run_id}.tp5").write_text(tape5, encoding="utf-8", newline="\n")

        rendered_angle_deg = _rendered_card3_angle_deg(tape5)
        caveats = []
        if not row["path_zenith_deg_radiant"].strip():
            caveats.append(_blank_zenith_caveat(row))
        support = row["deck_builder_support"].strip()
        if support != "current":
            caveats.append(
                f"deck_builder_support={support!r}: this row is NOT fully "
                "expressible by render_tape5 — the rendered deck needs a "
                "hand edit before it is run. See the row's notes column in "
                "docs/plans/modtran_run_matrix.csv"
            )
        angle_note = _angle_caveat(row, rendered_angle_deg)
        if angle_note:
            caveats.append(angle_note)
        caveat_text = "; ".join(caveats) if caveats else ""
        manifest_lines.append(
            f"| {run_id} | {row['block']} | {row['profile']} | "
            f"{row['iemsct']} | {row['itype']} | {config.hrange_km:g} | "
            f"{row['destination']} | {caveat_text} |"
        )

    (_OUTPUT_DIR / "MANIFEST.md").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    print(f"Rendered {len(rows)} tape5 decks to {_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
