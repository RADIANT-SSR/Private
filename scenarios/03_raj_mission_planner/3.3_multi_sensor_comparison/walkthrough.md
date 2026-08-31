# Scenario 3.3 — Multi-Sensor Comparison for Procurement


> **NIIRS applicability — engine update (CU-166).** Since this walkthrough was written, RADIANT added a metric-applicability gate: when one or more GIQE-5 inputs fall outside the calibration envelope — GSD 1.18–31.5 inch, RER 0.20–0.95, SNR 2–130 — the engine reports **NIIRS as N/A** by default instead of silently extrapolating. This configuration is outside that envelope, so the NIIRS values below are the **extrapolated** GIQE-5-form output: reproduce them with `performance.niirs.allow_extrapolated = true` and read them as a *relative trend, not a calibrated rating*. (The SNR/NEDT figures here predate later physics updates and are indicative; a full numeric refresh is tracked separately in the cleanup backlog. No IR-calibrated IIRS model yet — see `docs/tracking/gaps.md` Gap 100.)

**Persona:** Raj, mission planner evaluating three competing MWIR proposals.
**Question:** At a common operating point, how do the three sensors compare
on SNR / NIIRS / NEDT / MTF / GSD, which meet the requirements, and where
should each vendor invest to gain the most NIIRS?

Composition scenario — reuses the chain plus `giqe5_sensitivity` (Gap 20);
no new model.

---

## Inputs (vendor spec sheets → common form; non-RADIANT)

| File | Format | Represents |
|------|--------|-----------|
| `inputs/raj_sensor_proposals.xlsx` | Excel (`Proposals`, `Requirements`, `Operating` sheets) | Three vendors' specs transcribed to a common table, the procurement requirements, and the shared operating point |

`inputs/create_spreadsheet.py` regenerates it. **PDF spec-sheet parsing is
out of scope** (the catalog's flagged gap) — vendor numbers are captured in
the workbook, which is the RADIANT-facing input.

---

## Results (600 km, 300 K extended MWIR scene, 8 ms)

| Metric | Vendor A | Vendor B | Vendor C |
|--------|----------|----------|----------|
| SNR | 1160 | **2449** | 491 |
| NIIRS | 4.83 | 4.54 | **4.89** |
| NEDT [mK] | 23.7 | **11.4** | 56.0 |
| GSD [m] | 9.0 | 19.2 | **3.4** |
| MTF@Nyquist | 0.27 | **0.43** | 0.00 |

*Re-run 2026-08-30 after **CU-335** re-fitted the calibrated gas table's
VIS/NIR/SWIR rows against the post-CU-253 Rayleigh. The MWIR sensors here reach
only the λ⁻⁴ tail in the 2.40–5.00 µm floors, so every number in this document
is unchanged at its printed precision (the underlying SNR moves 1154.66 →
1154.63, three parts in 100 000). No table below was edited.*

*Prior vintage, 2026-08-02, pre-CU-321. Dominant mover: **CU-321** — the `(1−τ)·B` path
emission CU-224 added is now emitted at a height-resolved `T_eff(λ)` over the
600 km column instead of at its near-surface temperature, so it gives back part
of what CU-224 added on the two narrow-band vendors: A (3.7–4.8 µm) SNR
1272 → 1160 (−8.8 %) and NEDT 21.6 → 23.7 mK, C (3.7–4.8 µm) SNR 538 → 491
(−8.7 %) and NEDT 51.1 → 56.0 mK. Vendor B (3.0–5.0 µm) is unmoved to four
figures — the same band that CU-224 barely touched, for the same reason. GSD and
MTF@Nyquist are geometric and are bit-identical. **Verdicts unchanged:** C still
fails NEDT ≤ 50 mK (and now by a wider margin), B still wins SNR and NEDT, C
still wins GSD and NIIRS.*

**Compliance matrix (vs requirements):**

| Requirement | A | B | C |
|-------------|---|---|---|
| SNR ≥ 50 | ✓ | ✓ | ✓ |
| NIIRS ≥ 4.0 | ✓ | ✓ | ✓ |
| NEDT ≤ 50 mK | ✓ | ✓ | ✗ |
| GSD ≤ 1.5 m | ✗ | ✗ | ✗ |
| MTF@Nyq ≥ 0.25 | ✓ | ✓ | ✗ |
| **Total** | 4/5 | 4/5 | 2/5 |

- **No proposal is fully compliant — and the binding failure is GSD.** None
  of the three can reach 1.5 m GSD from 600 km with their proposed f/#: that
  needs a much longer focal length (≈f/30+ at these pitches), which trades
  against aperture and SNR. **The requirement is infeasible with the
  proposals as specified** — the actionable procurement finding. Raj should
  relax the GSD requirement, lower the orbit, or ask vendors for longer
  focal lengths.
- **Vendor B** leads SNR, NEDT, and MTF@Nyquist (fast f/3, large pixel,
  cold 77 K) but has the coarsest GSD. **Vendor C** leads NIIRS and GSD
  (small 10 µm pixel) but its pixel so oversamples the f/5 optics that
  MTF@Nyquist collapses to 0 (Q ≫ 2) and its warmer/lower-QE detector
  fails NEDT. **Vendor A** is the balanced middle — 4/5 compliant.
- **Vendor C's NEDT failure is real but close.** At 56.0 mK it misses the
  ≤ 50 mK requirement by 12 %. Its history is worth quoting to a vendor: the
  pre-CU-224 model read 62.7 mK (miss by 25 %), CU-224's path emission pulled it
  to 51.1 mK (miss by 2 %), and CU-321's colder, height-resolved emission
  temperature settled it at 56.0 mK. The verdict never changed (FAIL, 2/5), but
  the size of the fix a vendor would have to find did — quote 12 %, not 2 %.
- **Highest-leverage +10 % improvement (all vendors): GSD or RER**, each
  ≈ +0.14 NIIRS, versus only +0.07 for SNR — because NIIRS is logarithmic
  in SNR (already high) but responds strongly to resolution. Spending on
  optics (focal length / MTF), not on the detector, buys the most
  interpretability here.

---

## Physics / modeling notes (house rule)

- **Regime = EXTENDED**; the large absolute SNRs are whole-scene MWIR
  values at 300 K — appropriate for a relative comparison, not a
  detection-threshold number.
- **Vendor C's MTF@Nyquist = 0** is correct, not a bug: a 10 µm pixel
  behind f/5 MWIR optics has a Nyquist frequency far above the diffraction
  cutoff (Q ≫ 2), so there is no optical modulation at Nyquist. Its fine
  sampling helps GSD/NIIRS but wastes the pixel on unresolvable detail.
- **The radar chart normalises each axis to the best vendor** (NEDT and GSD
  inverted so outer = better), making the multi-metric trade visible at a
  glance.

---

## Truth anchors

The comparison composes validated pieces: the chain metrics (SNR/NIIRS/
NEDT/MTF/GSD, each with its own Level-0 tests) and `giqe5_sensitivity`
(Gap 20). The GSD infeasibility is a hand-checkable geometric fact:
`GSD = pitch · altitude / focal`, and `focal = f# · aperture` gives
0.75–1.75 m focal → 3.4–19 m GSD from 600 km.
