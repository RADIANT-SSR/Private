# Scenario 3.5 — Nighttime MWIR Imaging Feasibility

**Persona:** Raj, mission planner.
**Question:** Can the airborne MWIR sensor image a warm building complex
(295 K) against terrain (288 K) at **night**, and how does MWIR compare to
LWIR for this 7 K thermal scene?

Exercises the first-class extended contrast reference (ADR-0005), the NEDT
and MRT-at-Nyquist metrics, and an analytic solar-vs-thermal comparison.

---

## Inputs (non-RADIANT)

| File | Format | Represents |
|------|--------|-----------|
| `inputs/raj_scene.xlsx` | Excel workbook | Thermal scene (target/terrain T, ε), tropical-atmosphere column, dual-band airborne sensor config |
| `inputs/noaa_lst_strip.csv` | CSV | Stand-in for the NOAA land-surface-temperature **GeoTIFF** Raj has — RADIANT can't read rasters (see gaps.md). A 1-D terrain-temperature strip used for the background envelope. |

`inputs/create_spreadsheet.py` regenerates both; the scene/sensor values are
transcribed into the run script.

---

## Method

- **Detectability (chain).** Extended thermal self-emission
  (`is_hot_target`). The target-vs-terrain differential uses the first-class
  contrast reference (ADR-0005): `source.contrast_reference` = the 288 K
  terrain, so `contrast_snr` is the true two-pixel differential with combined
  target+reference noise. *Validated:* with the sensor sized below full well,
  the metric reproduces an explicit two-run differencing to the digit
  (MWIR 26.2 = 26.2, LWIR 133.7 = 133.7).
- **Solar independence (analytic, `core.blackbody`).** Band-integrated
  thermal emitted radiance `ε·∫B(λ,T)dλ` vs the reflected-solar radiance a
  Lambertian surface would add in full daylight (`ρ·E_sun_band/π`, sun at
  zenith, τ=1 — an optimistic upper bound).
- **Background envelope.** The NOAA LST strip's min/mean/max terrain
  temperatures re-drive the contrast to confirm the verdict is robust.

**Config note (matters for correctness):** integration time (0.2 ms) and
full well (1×10⁷ e-) are sized so *neither band saturates*. The
contrast-reference noise model is exact only below full well — above it the
metric drifts (a CU, filed).

---

## Results

### 1. Detectability — MWIR vs LWIR

| Band | SNR | Contrast SNR | NEDT (mK) | ΔT/NEDT | MRT@Nyq (K) |
|------|-----|--------------|-----------|---------|-------------|
| MWIR | 166.9 | 26.2 | 159.5 | 44× | 0.932 |
| LWIR | 2290.1 | 133.7 | 26.9 | 261× | 0.399 |

- Both bands detect the 7 K contrast with **wide margin** — ΔT is 44×
  (MWIR) to 261× (LWIR) the NEDT, and the smallest resolvable ΔT at Nyquist
  (MRT) is well under 1 K ≪ 7 K.
- **LWIR wins on every figure.** Near a 290 K scene the Planck peak sits at
  ~10 µm, so LWIR collects far more thermal photons — lower NEDT, higher
  contrast SNR. MWIR is viable; LWIR is the stronger band in this
  temperature regime.

### 2. Solar independence

| Band | Thermal (W/m²/sr) | Reflected solar, daytime UB (W/m²/sr) | Thermal / solar |
|------|-------------------|----------------------------------------|-----------------|
| MWIR | 1.379 | 3.05×10⁻¹ | ×5 |
| LWIR | 32.60 | 3.31×10⁻² | ×986 |

- In **LWIR** reflected sunlight is ×986 below the surface's own emission —
  negligible day or night.
- In **MWIR** the margin is only **×5**: even at the optimistic upper bound,
  daytime MWIR carries **~20 % reflected-solar contamination** — the
  well-known MWIR solar-glint problem. This makes the nighttime case
  **stronger**: at night that term is exactly zero, so MWIR loses a daytime
  contamination source and sees pure thermal self-emission.
- A reflective (VNIR/SWIR) sensor sees **nothing** at night; both thermal
  bands image the same scene they saw by day. That is the precise sense in
  which thermal imaging is solar-independent.

### 3. Background-temperature envelope

Terrain LST over the scene: 287.6–288.6 K. Across the whole envelope the
MWIR contrast SNR stays ≥ 24 (worst case at the hottest background, where
ΔT is smallest) — far above the confident-detection threshold (SNR ≈ 6,
Rose criterion). The verdict is robust to background variation across the
map.

**Verdict: YES.** Nighttime imaging is feasible; MWIR detects the 7 K scene
with wide margin and is fully solar-independent; LWIR is the stronger band.

---

## Physics / modeling notes (house rule)

- **Tropical atmosphere is set by two parameters, not one.** Selecting
  `standard_atmosphere = "tropical"` only raises the downwelling *emission*
  temperature (sea-level 299.65 vs 288.15 K); it does **not** set the
  profile's humidity. The tropical water column (`precipitable_water_cm = 4.1`)
  is set explicitly — without it the run would use the US-standard 1.4 cm and
  overstate transmission. Filed as a gap.
- **Reflected solar is the only solar term** for opaque surfaces (ρ = 1−ε);
  there is no transmitted-solar path. The comparison is an upper bound
  (zenith sun, τ=1), so the true daytime contamination is smaller still.
- **MRT-at-Nyquist is finite here by design.** With 30 µm pixels at f/4 the
  system is detector-limited (Nyquist below the diffraction cutoff) in both
  bands, so the Nyquist MTF is non-zero and MRT is well-defined. At finer
  pitch (Q→1) the Nyquist MTF → 0 and MRT diverges — physically correct
  (nothing resolves at a frequency the optics cannot pass).

---

## Real-MODTRAN validation note (added 2026-07-17)

Run F1 of the real MODTRAN 6 set (2026-07-17) is this scenario's exact
atmosphere geometry — 3 km airborne sensor, nadir, tropical — making
3.5 the only scenario with a geometry-exact real anchor. Band-mean
total transmittance:

| Band | Real F1 τ [-] | Simple τ [-] | real/simple |
|---|---|---|---|
| MWIR 3.5–5.0 µm | 0.529 | 0.240 | **2.20×** (simple too absorbing — CU-161 water over-response on the 4.1 cm column) |
| LWIR 8–12 µm | 0.539 | 0.665 | **0.81×** (simple too transparent — missing e-type H₂O continuum, CU-155/CU-161 addendum) |

Consequences for this walkthrough's conclusions (first-order, scaling
contrast SNR by the τ ratio; path-radiance/noise terms shift it
somewhat):

- **MWIR contrast SNR ≈ 26 modeled → ≈ 58 with the real atmosphere; LWIR
  ≈ 134 → ≈ 108.** The night-MWIR feasibility verdict *strengthens* —
  the real tropical atmosphere is twice as kind to the MWIR as the
  parametric model claimed.
- **The MWIR-vs-LWIR comparison narrows from ~5:1 to ~2:1.** The
  qualitative ordering (LWIR still ahead for a 7 K scene) survives, but
  the margin this walkthrough quotes overstates LWIR's advantage —
  both of the parametric model's water errors (MWIR too absorbing,
  LWIR too transparent) pushed the same direction in the ratio.
- Directionally consistent with scenario 6.2 (tropical is the simple
  model's worst profile) — but measured here at the scenario's own
  3 km column rather than the full column.

Numbers not re-baselined (parametric-workflow demonstration); this
note records the accuracy context. Anchor: `modtran/real_runs/F1.tp7`.

## Truth anchors

- **Contrast-reference metric = two-run differencing** to the digit when
  un-saturated (MWIR 26.16, LWIR 133.68) — the ADR-0005 combined-noise model
  reproduces an independent hand computation.
- **LWIR NEDT < MWIR NEDT near 290 K** — consistent with the Planck peak at
  ~10 µm; LWIR photon flux from a 290 K surface exceeds MWIR by ~an order of
  magnitude, matching the SNR ratio (2290 vs 167).
- **Solar/thermal ratios** match the textbook crossover: the MWIR
  emitted-vs-reflected crossover for terrestrial temperatures sits inside
  3–5 µm, so a 295 K surface in-band is emission-dominated but only modestly
  (×5), while LWIR is overwhelmingly emission-dominated (×986).
