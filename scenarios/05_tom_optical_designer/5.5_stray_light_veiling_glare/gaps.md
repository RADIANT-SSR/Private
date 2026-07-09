# Scenario 5.5 — Gaps and Friction

## Catalog gaps — status

The catalog listed five gaps for 5.5. Their real status today:

- **"No NIIRS output"** — STALE. `niirs` is in `result.metrics` (Gap 4);
  used throughout this scenario.
- **"No with/without toggle for individual effects"** — handled by scripting
  (run stray on vs off); not a framework gap.
- **"No stray-light PSF input (only scalar VGI and absolute irradiance)"** —
  REAL. Filed as Gap 60 (below).
- **"No MTF impact of stray light modeled"** — REAL. Folded into Gap 60.
- **"No FRED/Zemax stray-light PSF importer"** — REAL. Folded into Gap 60.

## Bug found — CU-062 (native veiling_glare mode is inert)

The `veiling_glare` stray-light mode computes its in-FOV irradiance with the
**pixel IFOV solid angle** (`omega_pixel = pitch²/focal²`) where the
**f-cone solid angle** (`π·D²/(4·focal²)`) is required. It therefore
under-reports stray by ~(D/pitch)²·π/4 ≈ 10⁷–10⁸ and reports zero impact for
any veiling-glare fraction — a Rule 16/17 silent-wrong-physics failure in a
physics stage. `optics/stage.py:990`. **Filed as CU-062** (Category C,
results-affecting). Demonstrated live in the scenario (Section 2). Workaround:
route VGI through the correct `absolute_irradiance` mode via
`stray_e = VGI · S_scene`.

## Gap filed to the registry (`docs/tracking/gaps.md`)

### Gap 60 — Stray light is a scalar noise pedestal only (no 2-D PSF, no MTF impact)
RADIANT models stray light as a spatially-uniform electron pedestal
(veiling-glare fraction or absolute irradiance) that adds shot noise. It
cannot ingest a 2-D stray-light PSF / PST map (FRED, Zemax), and it does not
model the veiling-glare **MTF / low-frequency contrast-modulation
reduction** — the spatial signature of stray light. The radiometric (noise)
hit is captured; the spatial (resolution/contrast-modulation) hit is not.
Pairs with Gap 58 (raster reader) for map ingestion.

## Friction / lessons

- **The natural stray-light knob is the broken one.** A user reaches for
  `veiling_glare_fraction` (it matches vendor VGI / FRED numbers) and gets a
  clean-optics answer. Until CU-062 lands, stray light must be entered as an
  absolute irradiance.
- **Veiling glare vs out-of-field stray are different magnitudes.** For this
  scene 3 % veiling glare is a ~4 % SNR nick, but 2.5 W/m² of out-of-field
  stray costs a full NIIRS level. The design driver is the absolute stray,
  not the VGI.
- **Contrast SNR degrades through noise, not signal.** A uniform pedestal
  cancels in the differential; anyone expecting stray light to wash out the
  contrast *signal* (as veiling-glare MTF would) will not see it in RADIANT
  (Gap 60).

## Catalog status

Scenario 5.5 — **DONE**. NIIRS gap stale (closed long ago); the stray-light
spatial-model gap is filed (Gap 60); the native-VGI-mode bug is CU'd
(CU-062) and demonstrated. This was the last non-MODTRAN scenario in the
execution plan.
