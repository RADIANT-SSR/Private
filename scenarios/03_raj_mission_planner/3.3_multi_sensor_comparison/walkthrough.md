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
| SNR | 1246 | **2449** | 527 |
| NIIRS | 4.86 | 4.58 | **4.94** |
| NEDT [mK] | 21.6 | **10.0** | 51.1 |
| GSD [m] | 9.0 | 19.2 | **3.4** |
| MTF@Nyquist | 0.25 | **0.46** | 0.00 |

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
