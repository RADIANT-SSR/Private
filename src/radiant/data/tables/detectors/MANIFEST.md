# Detector QE Library — Manifest

**Status:** representative / illustrative curves — **not** traceable vendor data.

These CSVs supply quantum-efficiency curves `QE(λ)` for the GUI/library material
dropdown and the example configs. Each is a **representative** response for the
named material system (typical band edges and peak-QE shape), **not** a specific
vendor part's measured datasheet. Provenance for the underlying numbers is
**undocumented** (no committed generator or citation) — this manifest records that
gap honestly (CU-080) so a user comparing against a real datasheet knows these are
illustrative, not measured, curves.

| File | Material system | Nominal spectral span | Notes |
|------|-----------------|-----------------------|-------|
| `silicon.csv` | Si (visible/NIR) | 0.3–1.15 µm | Peaks in the visible, cuts off near the Si band gap (~1.1 µm) |
| `ingaas.csv` | InGaAs (SWIR) | 0.8–1.8 µm | Standard SWIR photodiode response |
| `inp_ingaasp.csv` | InP/InGaAsP | 0.8–1.8 µm | Telecom-band III-V response |
| `hgcdte_mwir.csv` | HgCdTe (MWIR cutoff) | 1–6 µm | Representative MWIR MCT |
| `hgcdte_lwir.csv` | HgCdTe (LWIR cutoff) | 3–14 µm | Representative LWIR MCT |
| `type2_sls.csv` | Type-II strained-layer superlattice | 2.5–13 µm | Representative T2SL response |

**Format:** `wavelength_um, qe` — wavelength in µm (ascending), QE as a dimensionless
fraction in [0, 1].

## Known limitations (CU-080)

- **No citations.** The curves are not tied to a published datasheet or model; a
  side-by-side comparison against a specific vendor part will show unexplained
  deviations. Treat them as shape-representative defaults, not measured references.
- **Replace-or-cite.** To make a curve traceable, replace it with cited vendor/model
  data and add its `source_citation` here (matching the `data/emissivity/manifest.yaml`
  convention), or keep it explicitly labelled illustrative.
