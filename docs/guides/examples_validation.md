# Flagship-Mission Validation

Everything before this chapter shows RADIANT *being used*. This chapter asks the
prior question: **when RADIANT prints a number, is the number right?**

The honest answer has three parts, and they carry different weights.

1. **Four flight instruments.** Sentinel-2 MSI, Landsat 8/9 TIRS, Aqua MODIS, and
   Landsat 9 OLI-2 all publish performance figures — per-band SNR at a stated
   reference radiance, or per-band NEdT at a stated scene temperature — together with
   enough instrument description to build the model that should reproduce them.
   Scenarios 9.1–9.4 do exactly that. This is the strongest evidence the model has,
   because the comparison is against hardware in orbit rather than against another
   model.
2. **A MODTRAN 6 run set.** The atmosphere backends are measured against 130 delivered
   tape7 runs spanning six profiles, five geometry classes, and the full 0.3–14 µm
   span. That is a model-to-model comparison — MODTRAN is not the sky — but MODTRAN is
   the community reference, and the parity record states the residuals rather than
   claiming agreement.
3. **A hand calculation.** One MWIR case is worked from CODATA constants to SNR by
   hand, step by step, and asserted by an integration test to a relative tolerance of
   $10^{-4}$. It validates the arithmetic of the chain, not its physics choices, and
   it is the anchor everything else is ultimately checked against.

The chapter closes with what none of that covers, which is a longer list than the
first three sections might suggest.

## How to read a flagship comparison

Every one of the four flagship scenarios is built the same way, and the construction
is what makes the comparison meaningful:

- **The anchor is quoted at-aperture.** Published SNR requirements are stated *at* a
  reference radiance $L_{\text{ref}}$ or $L_{\text{typ}}$ in W/m²/sr/µm; published
  NEdT is measured against an onboard blackbody. So each scenario drives the chain
  with that radiance (or that blackbody) through a **vacuum path**
  (`atmosphere.model: exo`). The atmosphere and the scene model are deliberately taken
  out of the loop. What is under test is the aperture-to-electrons radiometry: solid
  angle, collecting area, throughput, quantum efficiency, integration time, and the
  noise stack.
- **Every instrument input carries a provenance class.** The four source-data
  dossiers maintained with the validation records (Sentinel-2 MSI, Landsat TIRS,
  MODIS TEB, Landsat OLI-2) tag each number as
  *published*, *model value*, or *assumption*, with the citation. Aperture and focal
  length are published; band-average quantum efficiency usually is not.
- **The assumption envelope is declared before the run.** Where an input is an
  assumption, the dossier states a range as well as a central value, and the
  comparison reports the SNR envelope that range produces. A prediction band, not a
  point, is what an assumption-carrying model is entitled to claim.
- **The verdict vocabulary is fixed.** **CONSISTENT** means the published value is
  reachable inside the declared envelope, or the residual maps onto a plausible value
  of a named unpublished parameter. **INCONCLUSIVE** means the residual is explainable
  but the explanation is not yet sourced. There is no "PASS".
- **The implied-parameter inversion is the diagnostic.** In the shot-noise limit
  $\mathrm{SNR} \propto \sqrt{\eta\,\tau\,t_{int}\,N_{TDI}}$, so a measured SNR can be
  inverted for the throughput product it implies. A residual that implies a physically
  plausible $\eta\tau$ is a modelling assumption being wrong in a known direction; one
  that implies an impossible $\eta\tau$ would be a defect.

**Provenance of the numbers below.** Every table in §§1–4 is quoted from the
scenario's committed `walkthrough.md`. Because the four scenarios run in under a
second each on a vacuum path with no fenced data, they were re-run while this chapter
was written (2026-09-17): all four reproduce their committed tables. Two numbers of
extra precision have moved since the walkthroughs were written and are flagged where
they appear. Envelope and implied-throughput columns that the walkthroughs summarise
in prose are quoted from a fresh run of `scripts/run_external_validation.py`, which is
the script the dossiers are executable through, and are labelled as such.

---

## 1. Sentinel-2 MSI — per-band SNR at the reference radiance

### Mission context

Copernicus Sentinel-2 carries the MultiSpectral Instrument: a 150 mm-pupil
three-mirror-anastigmat pushbroom imager in a 786 km sun-synchronous orbit, imaging
13 bands from 443 nm to 2190 nm at 10 m, 20 m, and 60 m ground sample distance across
a 290 km swath. It is the most heavily used optical Earth-observation instrument in
civil service, and ESA publishes both its **radiometric requirement** and its
**on-orbit measured performance** band by band.

### The published anchor

ESA's SentiWiki mission pages ([S2-SW], `https://sentiwiki.copernicus.eu/web/s2-mission`)
give, in Table 3, each band's reference radiance $L_{\text{ref}}$ [W/m²/sr/µm] and the
SNR required at it; Table 4 gives the SNR measured on Sentinel-2C. Five bands are
modelled — four VNIR silicon bands and one SWIR MCT band:

| Band | λ centre [nm] | FWHM [nm] | $L_{\text{ref}}$ [W/m²/sr/µm] | SNR required [-] | SNR measured, S2C [-] |
|---|---:|---:|---:|---:|---:|
| B2 | 492.7 | 64 | 128.00 | 154 | 162 |
| B3 | 559.8 | 35 | 128.00 | 168 | — |
| B4 | 664.6 | 30 | 108.00 | 142 | 175 |
| B8 | 832.8 | 118 | 103.00 | 174 | — |
| B11 | 1613.7 | 88 | 4.00 | 100 | 133 |

Source: the Sentinel-2 MSI source-data dossier, which carries the full
instrument table with per-row confidence classes.

### How the scenario models it

Each band is one config file in
`scenarios/09_flagship_missions/9.1_sentinel2_msi_snr/`. The scene is a flat two-point
user-radiance spectrum equal to that band's $L_{\text{ref}}$ (`data/s2_msi_*_lref.csv`),
propagated through `atmosphere.model: exo`. The regime is **extended** — a uniform
scene fills the pixel footprint, so the ensquared-energy factor is unity and never
applied (Rule 9). TDI is modelled as a 2-line charge sum, which is what the published
"1 TDI stage for 2 lines" means radiometrically: signal doubles, one read. The line
time follows from GSD and ground-track speed, $\approx 1.50$ ms for the 10 m bands.
B11 differs in pixel pitch (15 µm) and in its QE assumption; nothing else changes
between the five files.

### The comparison

RADIANT central prediction against both published figures (walkthrough table, verbatim,
with the ratios computed from it):

| Band | RADIANT SNR [-] | ESA required [-] | RADIANT / required [-] | S2C measured [-] | RADIANT / measured [-] |
|---|---:|---:|---:|---:|---:|
| B2 | 253 | ≥ 154 | 1.64 | 162 | 1.56 |
| B3 | 208 | ≥ 168 | 1.24 | — | — |
| B4 | 193 | ≥ 142 | 1.36 | 175 | 1.10 |
| B8 | 337 | ≥ 174 | 1.94 | — | — |
| B11 | 331 | ≥ 100 | 3.31 | 133 | 2.49 |

The assumption envelope and the shot-limit inversion, from
`scripts/run_external_validation.py` (run 2026-09-17):

| Band | Envelope, SNR [-] | Collected signal [e-] | Implied $\eta\tau$ from measured [-] |
|---|---|---:|---:|
| B2 | 188.0 – 308.6 | 65 615 | 0.153 |
| B3 | 157.2 – 251.5 | 44 847 | — |
| B4 | 145.0 – 232.6 | 38 506 | 0.341 |
| B8 | 253.7 – 430.2 | 115 183 | — |
| B11 | 263.6 – 375.3 | 110 810 | 0.091 |

### What the residuals mean

Every band clears its requirement, several by a wide margin, and the prediction sits
*above* the measured value wherever a measured value exists. That direction is
expected and is the honest reading of the model: RADIANT is computing a photon-limited
SNR with generous throughput assumptions, and it models no pixel-response
non-uniformity, no detector striping, no calibration-transfer noise, and no
quantisation of the on-ground processing chain — all of which are present in the flight
number.

Of the three bands with a measured anchor, only **B4** has its measurement inside the
declared envelope (175 sits comfortably in 145.0 – 232.6). B2's 162 and B11's 133 fall
*below* their envelopes, and the dossier resolves both by inversion rather than by
widening the envelope after the fact:

- **B2** implies $\eta\tau = 0.153$. At a band-average transmission near 0.6 that is a
  blue-end quantum efficiency of roughly 0.20 — low against the 0.50 assumed, but
  entirely ordinary for a front-illuminated silicon CMOS detector at 493 nm. The
  scenario's verdict is CONSISTENT with the QE assumption named as the responsible
  input.
- **B11** implies $\eta\tau = 0.091$, which no plausible MCT quantum efficiency
  reaches. The unpublished parameter here is the SWIR integration time: the SWIR focal
  plane runs on its own timing, and a substantially shorter dwell than the 20 m-band
  line time would close the gap on its own. Because no source for that dwell was
  found, the scenario records B11 as **INCONCLUSIVE pending a sourced SWIR $t_{int}$**,
  not as agreement.

That distinction — CONSISTENT for the four bands whose residual maps onto a plausible
value of a named parameter, INCONCLUSIVE for the one that does not — is the whole
discipline of this chapter in one table.

---

## 2. Landsat 8 TIRS — thermal NEdT

### Mission context

The Thermal Infrared Sensor on Landsat 8 and 9 is the canonical spaceborne LWIR
noise-equivalent-temperature-difference benchmark: an f/1.64 four-element refractive
telescope (178 mm focal length) at 705 km, imaging two thermal bands onto three
640 × 512 GaAs QWIP sensor chip assemblies at roughly 39 K, with an onboard variable-
temperature blackbody for calibration. Its on-orbit NEdT was measured by the
instrument team against that blackbody and published.

### The published anchor

[Montanaro 2014b] — Montanaro, Levy & Markham, *On-Orbit Radiometric Performance of
the Landsat 8 Thermal Infrared Sensor*, Remote Sensing 6(12) — Table 2:

| Band | Scene T [K] | NEdT spec [K] | NEdT measured [K] |
|---|---:|---:|---:|
| B10 (10.6–11.2 µm) | 300 | 0.400 | 0.049 |
| B11 (11.5–12.5 µm) | 300 | 0.400 | 0.052 |

Provenance and the full instrument table, including the [Reuter 2015] optical
prescription and the [Jhabvala 2011] focal-plane parameters: the Landsat TIRS
source-data dossier.

### How the scenario models it

A 300 K unit-emissivity blackbody through a vacuum path — the same view the published
measurement is taken against. The optics are the published prescription (f/1.64,
178 mm, total transmission 0.49); the detector is the published 25 µm QWIP with the
as-flown 3.49 ms integration time, $4 \times 10^{7}$ e-/s dark rate, and 260 e- RMS read
noise.

One input is not published in a usable form and is the scenario's one inversion. The
published conversion efficiency $CE = g\eta = 0.8$ %, taken literally, does not fill
the well anywhere near the published saturation temperatures. Inverting instead on
those saturation points — full well at 400 K for B10 and 370 K for B11 — gives
$CE_{\text{eff}} = 1.64 \times 10^{-2}$ (B10, $\times 2.05$ the published value) and
$1.36 \times 10^{-2}$ (B11, $\times 1.70$). The two CE values bracket the answer, and the
scenario reports the bracket rather than picking one silently.

### The comparison

Walkthrough table, verbatim:

| Band | RADIANT NEdT, this config [mK] | Bracket [mK] | Spec [mK] | Measured [mK] |
|---|---:|---|---:|---:|
| B10 | 58 | 58 – 124 | ≤ 400 | 49 |
| B11 | 52 | 52 – 89 | ≤ 400 | 52 |

The 2026-09-17 re-run reproduces these to the digit the walkthrough rounds to: 58.07 mK
(B10) and 52.02 mK (B11), against collected signals of $1.62 \times 10^{6}$ e- and
$2.90 \times 10^{6}$ e- respectively. The saturation-CE and raw-CE brackets at three
scene temperatures, from the same run of `scripts/run_external_validation.py`:

| Band | Scene T [K] | Raw-CE prediction [mK] | Saturation-CE prediction [mK] | Measured [mK] | Well fill [-] |
|---|---:|---|---|---:|---:|
| B10 | 270 | 102.5 – 153.1 | 63.6 – 84.3 | 57 | 0.23 |
| B10 | 300 | 90.3 – 124.1 | 58.0 – 71.3 | 49 | 0.35 |
| B10 | 320 | 85.7 – 112.6 | 56.0 – 66.3 | 45 | 0.46 |
| B11 | 270 | 76.3 – 103.4 | 55.0 – 68.6 | 60 | 0.32 |
| B11 | 300 | 70.8 – 89.4 | 52.0 – 61.1 | 52 | 0.49 |
| B11 | 320 | 68.9 – 83.9 | 51.0 – 58.3 | 51 | 0.62 |

(The inner width of each bracket is the read-noise envelope: 260 e- RMS for the ROIC
typical value, up to 1033 e- RMS when the 1000 e- electronics spec ceiling is RSS'd in.)

### What the residuals mean

**B11's prediction lands on the flight value exactly**: 52 mK predicted, 52 mK
measured, at the same 300 K scene. B10 predicts 58 mK against 49 mK measured, an
18 % over-prediction of the noise — the model is *conservative*, which is the safe
direction for a noise floor and the direction the missing conversion-efficiency detail
would push.

Both bands sit at roughly one-eighth of the 400 mK specification, which is the more
important structural check: a model that could not distinguish a 400 mK requirement
from a 50 mK instrument would be useless for the trade studies the rest of this volume
performs.

The scenario also cross-checks the raw signal against the instrument team's own
published radiometric budget ([Jhabvala 2011]) and agrees within about 25 %. The
remaining difference is the physically correct one: the published budget is dominated
by calibration-**stability** terms — blackbody and optics temperature knowledge — which
are not detector noise and are deliberately absent from a detector-noise floor.
Verdict: CONSISTENT.

---

## 3. Aqua MODIS — thermal emissive bands

### Mission context

MODIS is a 705 km whiskbroom scanner with a 17.78 cm aperture, a double-sided scan
mirror completing a 1.4771 s revolution, 1354 frames per Earth scan, and separate
focal planes at roughly 83 K for the short- and long-wave infrared. Aqua MODIS has a
twenty-year on-orbit calibration record, which makes it the best-characterised thermal
emissive band set in existence.

### The published anchors

Two independent anchors, which is why this scenario validates two different claims.

NASA's MODIS specification pages ([SPEC]) publish each thermal band's **typical scene
radiance** $L_{\text{typ}}$ — itself the 300 K band-averaged Planck radiance — and its
NEdT specification; [XIONG-2023] Table 5 publishes the Aqua measured NEdT:

| Band | λ range [µm] | $L_{\text{typ}}$ [W/m²/sr/µm] | NEdT spec [mK] | NEdT measured [mK] |
|---|---|---:|---:|---:|
| 20 | 3.660 – 3.840 | 0.45 | 50 | 20 |
| 29 | 8.400 – 8.700 | 9.58 | 50 | 20 |
| 31 | 10.780 – 11.280 | 9.55 | 50 | 20 |
| 32 | 11.770 – 12.270 | 8.94 | 50 | 30 |

Provenance: the MODIS TEB source-data dossier.

### How the scenario models it

A 300 K blackbody through a vacuum path, with the published effective focal lengths
(380.9 mm short-wave / 282.1 mm long-wave), the published detector sizes (540 µm and
400 µm), and the frame-derived integration times (323.3 µs; band 29 is four
on-board-averaged 73.3 µs samples). Optical transmission (0.40) and quantum efficiency
(0.70) are assumptions carrying envelopes; detector noise is the *named unknown* the
scenario exists to bound.

### Claim 1 — the spectral chain against four published Planck anchors

Published $L_{\text{typ}}$ against RADIANT's 300 K band-averaged Planck radiance
(2026-09-17 run of `scripts/run_external_validation.py`):

| Band | Published [W/m²/sr/µm] | RADIANT [W/m²/sr/µm] | Difference [%] |
|---|---:|---:|---:|
| 20 | 0.45 | 0.450 | −0.0 |
| 29 | 9.58 | 9.583 | +0.0 |
| 31 | 9.55 | 9.555 | +0.1 |
| 32 | 8.94 | 8.946 | +0.1 |

Four independent bands spanning 3.7 µm to 12 µm agree to 0.1 % or better — which is
the printed precision of the published column. This is the cleanest validation in the
chapter, because it is a direct comparison against published numbers with **no**
assumption class involved: the Planck integral, the band edges, and the spectral grid
are all that participate.

### Claim 2 — the NEdT floor, and why it is a bound

| Band | RADIANT photon/read floor [mK] | Spec [mK] | Measured [mK] | Implied detector noise $\sigma_{det}$ [e-] |
|---|---|---:|---:|---:|
| 20 | 8.10 – 10.56 | 50 | 20 | $7.4 \times 10^{3}$ |
| 29 | 2.12 – 2.73 | 50 | 20 | $2.4 \times 10^{5}$ |
| 31 | 1.76 – 2.27 | 50 | 20 | $4.4 \times 10^{5}$ |
| 32 | 1.89 – 2.44 | 50 | 30 | $6.2 \times 10^{5}$ |

The band-20 chain value at the scenario's central assumptions is ≈ 10 mK, reproduced
on re-run as 10.27 mK. The floors for bands 29, 31, and 32 are computed pre-readout by
`scripts/run_external_validation.py`, because those bands well-clip in the full chain
at 300 K — a modelling limitation recorded in the scenario's own `gaps.md`, not a
physical statement about MODIS.

The required ordering holds in every band: **floor < measured < spec**. That is the
signature of a detector-noise-limited instrument, and it is exactly what MODIS is —
photoconductive HgCdTe with generation-recombination and 1/f noise in the short-wave
bands, photovoltaic crosstalk in the long-wave ones. The measured 20–30 mK sits 10–40×
above the photon floor.

The floor is therefore a **bound, not a prediction**, and the chapter says so rather
than claiming a 2 mK model matches a 20 mK instrument. The useful output is the last
column: the implied detector noise a detector model would have to reproduce to close
the gap. That column is a specification for future work, written in the units the work
would be done in.

---

## 4. Landsat 9 OLI-2 — nine-band SNR with a modelled coating train

### Mission context

The Operational Land Imager 2 is a 135 mm four-mirror off-axis anastigmat pushbroom
imager at 705 km, covering nine reflective bands from the 443 nm coastal-aerosol band
to the 2.2 µm SWIR, with silicon PIN detectors for the VNIR and HgCdTe for the SWIR on
a single 210 K focal plane, digitised to 14 bits. Requirements are published per band
at a typical radiance $L_{\text{typ}}$, and on-orbit SNR has been characterised for
both OLI and OLI-2.

### The published anchor

Requirements from [Irons 2012] (*The next Landsat satellite: The Landsat Data
Continuity Mission*, Remote Sensing of Environment 122); Landsat 8 measured values
from [Morfitt 2015], recalled at ±15 % and flagged as such in the scenario's own gap
list. Provenance: the Landsat OLI-2 source-data dossier.

### How the scenario models it

This scenario is the one that exercises the most machinery, and it is worth reading
for that reason alone even where the validation verdict is unsurprising.

The optical train is **not** a lumped `transmission_scalar`. It is six
`optical_elements` rows: four protected-silver mirrors carrying a reflectance curve
with $\varepsilon = 1 - R$ derived per Kirchhoff (Rule 5), an anti-reflection-coated
focal-plane window, and the band's interference filter. Every curve is **synthetic** —
no per-surface curves are published for OLI — generated by
`scripts/gen_oli2_coatings.py` from vendor-typical anchors with the filter 50 % points
pinned to the published band edges. The end-to-end band-average throughput this
produces, for the red band, is $0.975^4 \times 0.985 \times 0.90 \approx 0.80$.

All nine bands live in **one** configuration set (`oli2_all_bands_study.yaml`). The
shared instrument is stated once; what is configured is the band filter (as a
configured element row — one complete element entry per configuration), the
$L_{\text{typ}}$ spectrum, the band edges, the quantum efficiency, the dark rate, and
— for the panchromatic band alone — an 18 µm pitch and a 1.8 ms line time against
36 µm and 3.6 ms for the 30 m bands.

### The comparison

Walkthrough table, verbatim:

| Band | RADIANT SNR [-] | Required [-] | L8 measured [-] (recalled ±15 %) | Prediction / measured [-] |
|---|---:|---:|---:|---:|
| B1 Coastal aerosol | 177 | ≥ 130 | ~230 | 0.77 |
| B2 Blue | 496 | ≥ 130 | ~360 | 1.38 |
| B3 Green | 472 | ≥ 100 | ~300 | 1.57 |
| B4 Red | 341 | ≥ 90 | ~225 | 1.51 |
| B5 NIR | 238 | ≥ 90 | ~200 | 1.19 |
| B6 SWIR1 | 328 | ≥ 100 | ~265 | 1.24 |
| B7 SWIR2 | 367 | ≥ 100 | ~180 | 2.04 |
| B8 Pan | 227 | ≥ 80 | ~145 | 1.56 |
| B9 Cirrus | 139 | ≥ 50 | ~165 | 0.84 |

Collected signals run from $3.95 \times 10^{4}$ e- (B9) to $2.82 \times 10^{5}$ e- (B2).
Every band is shot-noise dominated: the 200 e- RMS read noise contributes ≤ 6 % of the
total noise, and dark charge stays under 180 e- per frame even in the SWIR.

### What the residuals mean

**Verdict: CONSISTENT.** Every prediction clears its requirement, and every
prediction-to-flight ratio lands in the 0.8 – 2.0× envelope that scenario 9.1
established for assumption-class $\eta\tau$ — with B7 at 2.04 sitting on the boundary.

The two bands that land *below* flight are the informative ones. B1 (16 nm wide) and
B9 (21 nm wide) are the two narrow bands, where the band-edge roll-off of the
synthetic super-Gaussian filter eats a larger fraction of the in-band integral than it
does in a wide band, and where the assumed quantum efficiency (0.70 at 443 nm; 0.80 for
1.37 µm MCT) was deliberately set conservative. The flight instrument evidently does
better than the synthetic coating model. The recalled measured values themselves carry
±15 %, which covers a good part of both gaps.

### The structural check — configuration set against standalone files

The nine per-band standalone config files remain in the folder as cross-checks, and
`scripts/check_all_bands_parity.py` asserts that the configuration set reproduces each
one. Walkthrough table, verbatim:

| Band | Study SNR [-] | Standalone SNR [-] | Relative difference [-] |
|---|---:|---:|---:|
| B1_CA | 176.566166598 | 176.566166598 | 0.00e+00 |
| B2_Blue | 496.146430356 | 496.146430356 | 0.00e+00 |
| B3_Green | 472.394526650 | 472.394526650 | 0.00e+00 |
| B4_Red | 340.629354646 | 340.629354646 | 0.00e+00 |
| B5_NIR | 237.635101135 | 237.635101135 | 0.00e+00 |
| B6_SWIR1 | 327.616523306 | 327.616523306 | 0.00e+00 |
| B7_SWIR2 | 367.385730198 | 367.385730198 | 0.00e+00 |
| B8_Pan | 226.565673500 | 226.565673500 | 0.00e+00 |
| B9_Cirrus | 138.894479928 | 138.894479928 | 0.00e+00 |

The re-run on 2026-09-17 reproduces the study-versus-standalone verdict exactly — all
nine bands bit-identical, every relative difference 0.00e+00, against an acceptance bar
of $10^{-9}$. Two of the *absolute* values have moved in their sixth significant figure
since the walkthrough was written (B6_SWIR1 327.616523306 → 327.616524064, a relative
move of $2 \times 10^{-9}$; B7_SWIR2 367.385730198 → 367.387242489, a relative move of
$4.1 \times 10^{-6}$), which is a re-baselining of the two SWIR bands somewhere upstream,
far below the precision of any published comparison in the table above. The committed
walkthrough is quoted as it stands; the drift is recorded in the findings log.

This is not a physics result — the equality is expected *by construction*, because
materialising configuration N reproduces standalone N's effective document field for
field, so both sides drive the same deterministic chain. It is a regression guard on
the configuration-set machinery, and it is the kind of check that catches a
configured-row bug the physics tests would not. It has caught one already: the study
once shared a single composite filter element whose union carried both strips'
roll-off across the 1 nm B1/B2 seam, giving ≤ 0.5 % differences in those two bands.
Per-band filter entries removed the artifact.

---

## 5. What the four flagships share

Read together, the four comparisons establish a narrower claim than "RADIANT is
validated", and it is worth stating the narrow claim precisely:

- **Extended-scene radiometry, aperture to electrons, is right to within the
  assumption envelope of the unpublished instrument parameters.** Four instruments,
  twenty bands, spanning 443 nm to 12.3 µm, silicon and MCT and QWIP, pushbroom and
  whiskbroom, SNR and NEdT.
- **The Planck integral and the band-averaging are right to 0.1 %** against four
  independently published radiance anchors (§3, claim 1).
- **The noise stack is right to roughly 20 % or better where the instrument is
  photon-and-read-limited** (§2: 52 mK against 52 mK, 58 mK against 49 mK) and
  correctly identifies itself as a *bound* where the instrument is detector-limited
  (§3, claim 2).
- **The direction of every residual is explained**, and the explanations are all of
  one kind: RADIANT computes an idealised photon-limited performance, so it
  over-predicts flight SNR wherever the flight instrument carries non-uniformity,
  striping, or calibration-transfer noise that the model does not represent.

Every one of these comparisons runs on a **vacuum path**. None of them validates the
atmosphere, the scene model, the spatial path, or the calibration model. That is what
the next two sections and §8 are for.

---

## 6. Atmosphere — parity against a MODTRAN 6 run set

The atmosphere backends are measured against an owner-run MODTRAN 6 run matrix rather
than against field radiometry. The full record — every table, every test that pins it,
and a seventeen-entry limitations register — is the MODTRAN-parity validation
record. This section quotes its headline numbers; it does not replace it.

**The run set.** 132 authored rows, of which **130 tape7 runs are delivered**, plus
four ground-level flux sidecars = 134 artifacts. They span seventeen blocks: the six
standard profiles at nadir, a zenith fan at 30°/45°/60°, partial columns, a
visibility and water-vapour ladder, sky-irradiance runs, airborne and space sensor
geometries, thermal downwelling at the 48.2° diffusivity angle, a 5 × 5 horizontal-path
grid from 5 km to 100 km range, and near-horizon probes out to 89.5°. Two rows — the
refraction on/off calibration pair — remain unrun.

**Thermal path radiance.** Band-mean model/MODTRAN ratios, before and after the
escape-resolved emission-temperature model landed:

| Anchor | Geometry | MWIR 3–5 µm, before → after [-] | LWIR 8–12 µm, before → after [-] |
|---|---|---|---|
| O3 | ground ↔ 10 km, zenith 48.2°, down | 2.013 → 1.141 | 1.326 → 1.055 |
| O5 | ground ↔ 100 km, zenith 48.2°, down | 2.422 → 1.217 | 1.430 → 1.093 |
| K1 | ground ↔ 1 km, nadir, up | 0.379 → 0.358 | 0.530 → 0.515 |
| H5 | ground ↔ 100 km, zenith 48.2°, up | 1.041 → 0.721 | 1.263 → 1.074 |

Aggregate over the fourteen enforced anchors, LWIR: RMS $|\ln r|$ **0.3342 → 0.2611**,
a 22 % improvement. The tall down-looking columns went from over-reading the MWIR by a
factor of two to within about 20 %.

**Effective emission temperature.** Because MODTRAN reports τ and thermal path
radiance separately, its own effective emission temperature is recoverable exactly,
which isolates the temperature error from the opacity error:

| Metric | Band | One-temperature [K] | Height-resolved [K] |
|---|---|---:|---:|
| $\max \lvert \Delta T \rvert$ over the anchor set | MWIR | 25.2 | 10.4 |
| $\max \lvert \Delta T \rvert$ over the anchor set | LWIR | 23.2 | 9.5 |
| RMS $\lvert \Delta T \rvert$ | MWIR | 9.5 | 4.3 |
| RMS $\lvert \Delta T \rvert$ | LWIR | 10.4 | 3.2 |

**Transmittance.** The gas and water calibration was fitted on one profile (US
standard); the five non-calibration profiles — tropical, mid-latitude summer and
winter, subarctic summer and winter — hold band-mean τ within **± 0.012** of MODTRAN in
the water-relevant windows. Up-looking partial columns converge to within 2 % in the
LWIR by 10–20 km, and are systematically too transparent for shallow columns (at 1 km,
model 0.889 against MODTRAN 0.781 in the 8–12 µm band) because the calibration was
fitted to full columns. Constant-altitude horizontal arms hold to **± 3.5 %** in the
LWIR across the 3–15 km altitude sweep.

**Where the simple backend stops working.** The analytic arm's exponential law
$\tau(2L) = \tau(L)^2$ is exactly where a correlated-$k$ band model disagrees, and the
disagreement is monotone with range. Down the 3 km row of the horizontal grid,
model/MODTRAN:

| Range | 5 km | 10 km | 25 km | 50 km | 100 km |
|---|---:|---:|---:|---:|---:|
| LWIR 8–12 µm [-] | 1.03 | 1.01 | 0.95 | 0.87 | 0.82 |
| MWIR 3–5 µm [-] | 1.09 | 0.88 | 0.43 | 0.11 | 0.01 |

This is the documented reason long-range MWIR horizontal work needs the MODTRAN or
interpolated backend rather than the `simple` one — and it is a good example of the
register's general posture: the number is published, with its trend, rather than the
regime being quietly excluded.

**The limitations register names its own dominant residual.** The largest known
atmosphere error is the *region-flat spectral shape* of the calibrated opacity model:
there is no line structure inside the seventeen calibrated regions, which under-reads
up-looking MWIR thermal radiance by 25–40 % on columns deeper than 5 km. Alongside it:
the visible and near-infrared sky is a provisional single-scatter model that
under-predicts the daytime visible sky by roughly 2× near the horizon (and warns at
runtime below 3 µm); refraction is unmodelled, worth about 0.5° of lift near the
horizon; and the visible band's opacity is right in total but mis-attributed between
gas and aerosol, which matters to any product that separates the two.

---

## 7. MWIR single-wavelength ground truth

The oldest anchor in the codebase is also the simplest: one MWIR case worked by hand
from CODATA 2018 constants to an SNR, with every intermediate value written down.
The single-wave ground-truth record is the full derivation;
`examples/ground_truth_mwir.yaml` is the configuration, and
`tests/integration/test_ground_truth_mwir.py` asserts the chain against it.

The configuration is deliberately stripped of everything that could hide an error: a
300 K, $\varepsilon = 1.0$ target at 4.0 µm on a three-point grid
[3.999, 4.000, 4.001] µm, a vacuum atmosphere, a 0.30 m aperture at f/5, 0.75 optical
transmission, a 15 µm pixel, 0.70 quantum efficiency, **zero** dark current, 5.0 ms
integration, 30 e- RMS read noise, unity gain, 16-bit conversion.

The chain, step by step:

| Step | Quantity | Hand value | Unit |
|---|---|---:|---|
| 1 | Planck radiance $B(4.0\ \mu m, 300\ K)$ | 7.2197642257e-01 | W/m²/sr/µm |
| 2 | At-aperture radiance (vacuum) | 7.2197642257e-01 | W/m²/sr/µm |
| 3 | After optics, $\times\,0.75$ | 5.4148231693e-01 | W/m²/sr/µm |
| 4 | Collecting area $\tfrac{\pi}{4}D^2$ | 7.0685834706e-02 | m² |
| 5 | Pixel solid angle $p^2/f^2$ | 1.0000e-10 | sr |
| 6 | Photon rate | 7.7073e+07 | photon/s/pixel/µm |
| 7 | Electron rate, $\times\,\eta$ | 5.3951e+07 | e-/s/pixel/µm |
| 8 | Signal over the band, $\times\,t_{int}$ | 539.508 | e- |
| 9 | Shot noise $\sqrt{S}$ | 23.23 | e- RMS |
| 10–12 | Dark / read / quantisation noise | 0.0 / 30.0 / 0.2887 | e- RMS |
| 13 | Total noise (RSS) | 37.94 | e- RMS |
| 14 | **SNR** | **14.22** | – |

The chain reproduces step 8 as 539.50846835 e- against the constant-radiance hand value
539.50809863 e-, a relative difference of $6.9 \times 10^{-7}$. That single number is
the entire error budget: it is the trapezoid rule capturing the curvature of the Planck
function across a 0.002 µm band, and it is three orders of magnitude inside the test's
$10^{-4}$ tolerance. Every other step is exact to float64 — the constants are CODATA
2018 exact values, the vacuum atmosphere is the identity, and the geometry is two
closed-form expressions.

What this anchor validates is the **arithmetic and unit handling** of the radiometric
core: solid angle, collecting area, the photon-energy conversion $\lambda/hc$, the
spectral integral, and the noise RSS. What it does not validate is any *modelling
choice* — there is no atmosphere, no background, no spatial path, no real detector
physics in it. It is the floor of the validation stack, not its ceiling.

---

## 8. What validation does **not** yet cover

> RADIANT's validated core is **extended-scene, vacuum-path radiometry from aperture
> to electrons, plus the photon-and-read noise stack**: four flight instruments,
> twenty bands, 443 nm to 12.3 µm, agreeing within the declared envelopes of their
> unpublished parameters, on top of a hand-calculated arithmetic anchor good to
> $7 \times 10^{-7}$. Outside that core, the evidence thins in five specific ways, and
> none of them is closed by the chapter above. **First, nothing here validates the
> spatial path against measurement.** No flight or laboratory MTF, ensquared-energy,
> or NIIRS figure is anchored anywhere in the repository; the PSF/MTF dual-path
> consistency check (Rule 4) proves the two paths agree with *each other* to 2e-2,
> which is an internal-consistency guarantee and not an external one, and the one
> scenario that compares predicted against "measured" MTF uses a synthetic
> measurement. **Second, the atmosphere is validated against MODTRAN, not against the
> sky.** It is a model-to-model comparison over one owner-run deck set, its residuals
> are large where the register says they are large — 25–40 % on deep up-looking MWIR
> columns, a factor of two on the near-horizon daytime visible sky, an order of
> magnitude on 100 km MWIR horizontal arms — and no geometry outside the delivered run
> matrix is measured at all. **Third, the flagship comparisons deliberately bypass the
> atmosphere and the scene model**: all four run `atmosphere.model: exo` against a
> stated at-aperture radiance, so there is no end-to-end validated case in which a
> scene model, an atmosphere, and a sensor model are simultaneously under test against
> a published number. **Fourth, the point-source and sub-pixel regimes have no external
> anchor.** Every flagship is extended-scene; detection range, the Johnson criteria,
> and the ensquared-energy coupling that governs sub-pixel targets are exercised by
> scenarios but validated against no published instrument. **Fifth, the detector and
> calibration models are datasheet-anchored, not measurement-anchored**: 1/f and
> generation-recombination noise, inter-pixel capacitance, persistence, well
> saturation, and the whole post-NUC calibration residual model rest on vendor
> datasheet values and internal consistency, and §3 above quantifies exactly how much
> that matters — MODIS's measured NEdT sits 10–40× above the photon floor RADIANT can
> currently compute, and the detector-noise term that accounts for the difference is
> named as an unknown rather than modelled. A reader deciding whether to trust a
> RADIANT number should ask which of those five categories it falls in before asking
> how many digits it printed.

Three further boundaries are worth stating in the same spirit, because they are
properties of the *evidence*, not of the model:

- **Recalled and assumption-class inputs are present in every flagship.** Landsat 8's
  measured OLI SNRs are recalled at ±15 %. Quantum efficiencies, optical
  transmissions, and one integration time are assumptions with envelopes rather than
  citations. A comparison that agrees inside such an envelope is a consistency test,
  not a calibration.
- **The comparisons are single-point, not distributional.** Each band is compared at
  one scene radiance or one scene temperature (TIRS at three temperatures is the
  exception). Nothing here tests how the residual behaves across the full dynamic
  range of any instrument.
- **Scenario numbers carry a vintage.** RADIANT's physics has been corrected
  repeatedly, each correction re-baselining affected walkthroughs. The four flagship
  walkthroughs were re-run for this chapter and reproduce; the rest of the volume
  quotes committed values at their stated vintage, and the scenario's own
  `walkthrough.md` is always the authority.

None of this argues against using the tool. It argues for reading the validation
register before quoting a number outside the validated core — and, where a decision
turns on a number outside it, for adding the anchor that would bring it inside.
