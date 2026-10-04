#!/usr/bin/env python3
"""Generator for the PROPOSED substrate material library (Rule 26 generator-of-record).

Status: proposed content for `docs/plans/Refractive_Substrate_Emission_Plan.md`.
NOT wired into `radiant.data`. Nothing imports this; it is run by hand.

What it does
------------
1. Evaluates n(lambda) for each candidate substrate from the dispersion formula or
   critically-evaluated table named in that material's YAML `sources` block (all
   retrieved from the refractiveindex.info database, CC0 / public domain).
2. Builds alpha(lambda) in the transparency window by log-log interpolation through
   published laser-line anchor values (Crystran material pages, which cite the
   primary literature per material). Anchors beyond the published set are marked
   `source: estimated` in the material YAML and are shape-only.
3. Writes one CSV per material on a shared grid, and prints a provenance table.

Run from the repo root:
    python docs/plans/substrate_data_proposed/build_substrate_tables.py
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
OUT = HERE / "tables"


# ----------------------------------------------------------------------------
# Dispersion formula evaluators (refractiveindex.info conventions)
# ----------------------------------------------------------------------------
def sellmeier_1(lam: np.ndarray, c: list[float]) -> np.ndarray:
    """formula 1: n^2 - 1 = c0 + sum_i c_{2i-1} lam^2 / (lam^2 - c_{2i}^2)."""
    n2 = 1.0 + c[0]
    for i in range(1, len(c), 2):
        n2 = n2 + c[i] * lam**2 / (lam**2 - c[i + 1] ** 2)
    return np.sqrt(n2)


def sellmeier_2(lam: np.ndarray, c: list[float]) -> np.ndarray:
    """formula 2: n^2 - 1 = c0 + sum_i c_{2i-1} lam^2 / (lam^2 - c_{2i})."""
    n2 = 1.0 + c[0]
    for i in range(1, len(c), 2):
        n2 = n2 + c[i] * lam**2 / (lam**2 - c[i + 1])
    return np.sqrt(n2)


def formula_4(lam: np.ndarray, c: list[float]) -> np.ndarray:
    """formula 4 (Klein-style modified Sellmeier), first two resonance groups."""
    n2 = np.full_like(lam, c[0])
    n2 = n2 + c[1] * lam ** c[2] / (lam**2 - c[3] ** c[4])
    n2 = n2 + c[5] * lam ** c[6] / (lam**2 - c[7] ** c[8])
    return np.sqrt(n2)


FORMULAS = {"sellmeier_1": sellmeier_1, "sellmeier_2": sellmeier_2, "formula_4": formula_4}


def read_ri_table(path: Path) -> np.ndarray:
    """Read the `tabulated n` block out of a retrieved refractiveindex.info YAML."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    for block in doc["DATA"]:
        if block["type"].strip() == "tabulated n":
            return np.array(
                [[float(x) for x in ln.split()] for ln in block["data"].split("\n") if ln.strip()],
                dtype=float,
            )
    raise ValueError(f"{path}: no 'tabulated n' block")


def eval_n(spec: dict[str, Any], lam: np.ndarray, base: Path) -> np.ndarray:
    """Evaluate n(lambda) from a YAML n_refr block."""
    if spec["kind"] == "formula":
        return FORMULAS[spec["formula"]](lam, [float(x) for x in spec["coefficients"]])
    pts = read_ri_table(base / spec["source_file"])
    # Linear in lambda: the critically-evaluated tables are dense enough that
    # interpolation error is below their own 4th-decimal precision.
    return np.interp(lam, pts[:, 0], pts[:, 1])


def eval_alpha(spec: dict[str, Any], lam: np.ndarray) -> np.ndarray:
    """Evaluate alpha(lambda) [1/cm] by log10-log10 interpolation through anchors.

    Outside the anchor span the value is held at the nearest anchor and the
    material YAML's `window_um` records where that is legitimate; the caller
    (and the study) treats anything outside `window_um` as not covered.
    """
    pts = np.array([[a["lambda_um"], a["alpha_cm_inv"]] for a in spec["anchors"]], dtype=float)
    pts = pts[np.argsort(pts[:, 0])]
    lx, ly = np.log10(pts[:, 0]), np.log10(np.maximum(pts[:, 1], 1e-12))
    return 10.0 ** np.interp(np.log10(lam), lx, ly)


# ----------------------------------------------------------------------------
def main() -> None:
    OUT.mkdir(exist_ok=True)
    # 0.4-14 um, the span RADIANT models. 0.02 um steps below 2 um (where
    # dispersion is steep), 0.05 um above.
    lam = np.unique(
        np.concatenate([np.arange(0.40, 2.0001, 0.02), np.arange(2.0, 14.0001, 0.05)]).round(4)
    )

    rows: list[tuple[str, ...]] = []
    for path in sorted(HERE.glob("*.yaml")):
        mat = yaml.safe_load(path.read_text(encoding="utf-8"))
        lo, hi = mat["window_um"]
        mask = (lam >= lo) & (lam <= hi)
        sub = lam[mask]
        n = eval_n(mat["n_refr"], sub, HERE)
        a = eval_alpha(mat["alpha"], sub)
        out = OUT / f"{mat['name']}.csv"
        with out.open("w", encoding="utf-8", newline="\n") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(["wavelength_um", "n_refr", "alpha_cm_inv"])
            for li, ni, ai in zip(sub, n, a, strict=True):
                w.writerow([f"{li:.4f}", f"{ni:.5f}", f"{ai:.6g}"])
        na = len(mat["alpha"]["anchors"])
        rows.append(
            (
                mat["name"],
                f"{lo:.2f}-{hi:.1f}",
                f"{n.min():.3f}-{n.max():.3f}",
                f"{a.min():.2e}-{a.max():.2e}",
                str(na),
                mat["alpha"]["grade_sensitivity"],
            )
        )

    hdr = ("material", "window[um]", "n range", "alpha range [1/cm]", "a-anchors", "grade spread")
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(hdr)]
    line = "  ".join(h.ljust(w) for h, w in zip(hdr, widths, strict=True))
    print(line)
    print("-" * len(line))
    for r in rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)))
    print(f"\n{len(rows)} materials written to {OUT.relative_to(HERE.parents[2])}/")
    print(f"grid: {lam[0]:.2f}-{lam[-1]:.2f} um, {len(lam)} points (per-material window applied)")


if __name__ == "__main__":
    main()
