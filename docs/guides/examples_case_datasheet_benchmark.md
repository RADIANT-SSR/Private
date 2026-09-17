# Case Study — Benchmarking Against a Published Datasheet

**Scenario 6.1** · persona: Dr. Chen, researcher validating a model against the
literature · modality: script-led · scenario folder:
`scenarios/06_dr_chen_researcher/6.1_published_snr_benchmark/`

---

## The question

Dr. Chen has a published cooled-LWIR HgCdTe focal-plane datasheet on her desk. It
quotes two numbers and the conditions they were measured under: a specific
detectivity $D^* = 2.00 \times 10^{11}$ Jones and a NETD of 25.0 mK, at f/2, against
a 300 K scene, over 8–12 µm, on a 30 µm pixel. She wants to know whether RADIANT,
configured to those same conditions, reproduces them.

This is not a trade study. There is no sweep, no aperture axis, no design decision at
the end of it. It is the question a researcher asks before she is willing to publish
anything *else* the tool says: **does the noise model land on a number somebody else
measured?**

The obstacle is that the datasheet and the chain speak different languages. A
datasheet quotes **optical-power** figures of merit — watts of noise-equivalent
power, and the detectivity derived from them. RADIANT's chain computes noise in
**electrons RMS**, because that is where the physics lives: shot noise is the square
root of a collected charge, read noise is a ROIC property in electrons, dark shot is
a rate times a time. Getting from one to the other is a unit bridge, and it is the
bridge this scenario was written to exercise.

## The inputs, and why they are what they are

Everything below is transcribed from `inputs/chen_lwir_datasheet.xlsx` (sheet
`Datasheet`) into the run script as module constants, so that the run is
self-contained and reproducible without the workbook. `inputs/create_spreadsheet.py`
regenerates the workbook from the same values.

| Quantity | Value | Why |
|---|---|---|
| Published $D^*$ | $2.00 \times 10^{11}$ Jones | The figure under test. "Jones" is cm·Hz$^{1/2}$/W. |
| Published NETD | 25.0 mK | The second figure under test. |
| Spectral band | 8.0 – 12.0 µm | The datasheet's stated LWIR passband. |
| Pixel pitch | 30 µm × 30 µm | Sets the detector area $A_d = 9.00 \times 10^{-6}$ cm². |
| f-number | 2.0 | The datasheet's reference cold-stop f/#; realised as a 0.05 m aperture at 0.10 m focal length. |
| Scene temperature | 300 K, ε = 0.98 | The reference scene the NETD is quoted against. |
| Integration time | 30 µs | The datasheet's reference dwell. It is short *because* the LWIR flux is intense. |
| Quantum efficiency | 0.75 | Datasheet, band-average. |
| Dark rate | $1.0 \times 10^{5}$ e-/s at 77 K | Datasheet, at the cryogenic set point. |
| Read noise | 60 e- RMS | Datasheet ROIC. |
| Full well | $1.0 \times 10^{7}$ e- | Datasheet ROIC. |
| Optical transmission | 0.85 | Scalar lump — this benchmark is not a coated-train study. |
| Atmosphere | `simple`, `us_standard`, nadir from 1000 m | A short, nearly transparent column; the benchmark is about the detector, not the air. |
| Tolerance | ±15 % | Dr. Chen's declared pass band, set before the run. |

Two entries carry more weight than they look. The **30 µs integration time** is the
whole reason this configuration is plausible: an 8–12 µm staring array pointed at a
room-temperature scene collects charge extraordinarily fast, and 30 µs is what keeps
the well from filling. LWIR staring FPAs are integration-time-limited, and the
datasheet's reference conditions quietly encode that.

The **±15 % tolerance is declared in advance**, in the script, as `TOLERANCE_PCT`. A
benchmark whose tolerance is chosen after the residual is known is not a benchmark.

## The converter bridge

Three relations link the two languages. All three ship as RADIANT functions with
their own Level-0 tests, and this scenario was the first consumer of them:

$$\mathrm{NEP} = \sigma_e \cdot \frac{hc}{\eta\,\lambda\,t_{int}}
\qquad
D^* = \frac{\sqrt{A_d\,\Delta f}}{\mathrm{NEP}}
\qquad
\Delta f = \frac{1}{2\,t_{int}}$$

The first converts a noise in electrons to a noise-equivalent optical power in watts:
divide by the quantum efficiency to get from electrons to absorbed photons, multiply
by the photon energy $hc/\lambda$ to get joules, divide by the integration time to
get watts. The second is the definition of specific detectivity — detector area and
noise bandwidth normalised out, so that arrays of different size and frame rate can
be compared.

The third is the one worth pausing on. $\Delta f = 1/(2 t_{int})$ is the **equivalent
noise bandwidth of an integrating detector**: a device that accumulates charge for
$t_{int}$ and then reads it out is, to a noise calculation, a filter of that
bandwidth. It is a convention, not a measurement, and it is what makes a per-frame
electron count commensurable with a per-$\sqrt{\text{Hz}}$ detectivity. At the
datasheet's 30 µs it gives $\Delta f = 16.7$ kHz.

## The scripted path

One script does the whole study:

```bash
PYTHONPATH=src python \
  scenarios/06_dr_chen_researcher/6.1_published_snr_benchmark/scripts/run_datasheet_benchmark.py
```

### The sensor, built in code rather than loaded from YAML

Because every parameter is a datasheet figure, the script constructs the sensor
directly instead of maintaining a parallel config file:

```python
def build_sensor() -> Sensor:
    """LWIR FPA configured to the datasheet reference conditions."""
    aperture = 0.05
    focal = aperture * FNUM  # f/# = focal / aperture
    s = Sensor()
    s.set("source.scene_type", "extended")
    s.set("source.target.temperature", SCENE_TEMP_K, unit="K")
    s.set("source.target.emissivity", 0.98)
    s.set("optics.aperture_diameter_m", aperture)
    s.set("optics.focal_length_m", focal)
    s.set("optics.transmission_scalar", TRANSMISSION)
    s.set("detector.pixel_pitch_x_um", PITCH_UM)
    s.set("detector.qe_value", QE)
    s.set("detector.dark_rate_e_per_s", DARK_E_PER_S)
    s.set("spectral_integration.filter_min_um", BAND[0])
    s.set("spectral_integration.filter_max_um", BAND[1])
    s.set("spectral_integration.integration_time_s", T_INT_S)
    s.set("readout.read_noise_e_rms", READ_NOISE_E)
    s.set("readout.full_well_capacity_e", FULL_WELL_E)
    return s
```

Note the f-number: it is not a settable input. RADIANT derives it from aperture and
focal length, so the script inverts the datasheet's f/2 into a focal length and lets
the chain re-derive it. That is the general pattern for any derived quantity in
RADIANT — you specify the independent inputs and the tool computes the rest.

### The two directions of the bridge

The script crosses the bridge twice, in opposite directions, and that is the whole
design of the benchmark. First it takes the **datasheet's** $D^*$ *down* to an
electron count, so that Dr. Chen can see what total noise the published figure
implies:

```python
nep_spec = nep_from_dstar(DSTAR_SPEC, AREA_CM2, DELTA_F_HZ)
sigma_e_spec = noise_electrons_from_nep(nep_spec, QE, LAMBDA_C_UM, T_INT_S)
```

Then it runs the chain and takes the **chain's** noise *up* to a detectivity:

```python
r = build_sensor().evaluate()
signal_e = r.stage_outputs["spectral_integration"]["signal_e"]
snr = r.metrics["snr"]
noise_e = signal_e / snr

nep_chain = nep_from_noise_electrons(noise_e, QE, LAMBDA_C_UM, T_INT_S)
dstar_chain = dstar_from_nep(nep_chain, AREA_CM2, DELTA_F_HZ)
nedt_chain_mk = r.metrics["nedt_K"] * 1e3
```

Two details are worth copying into your own benchmark scripts. The total noise is
recovered as `signal_e / snr` rather than by quadrature-summing the sixteen noise
terms by hand — the chain already did that sum, and re-doing it is an opportunity to
disagree with it. And NETD is read straight out of `result.metrics["nedt_K"]`, which
is the chain's band-integrated $\partial S/\partial T$ value, not a single-wavelength
approximation.

### Real output

```
==========================================================================
SCENARIO 6.1 — PUBLISHED-DATASHEET BENCHMARK (D*/NETD)
==========================================================================
Datasheet: cooled LWIR HgCdTe, D* = 2.00e+11 Jones, NETD = 25 mK @ f/2, 300 K,
8–12 µm, 30 µm pixel.
Pixel area 9.00e-06 cm², noise bandwidth Δf = 1/(2·t_int) = 16.7 kHz.

--------------------------------------------------------------------------
DATASHEET D* → NEP → equivalent noise electrons (converter chain)
--------------------------------------------------------------------------
  NEP(D*)               = 1.936e-12 W
  σ_e equivalent        = 2,193 e⁻ (total noise the D* implies)

--------------------------------------------------------------------------
CHAIN RESULT → D* / NETD (via the converters)
--------------------------------------------------------------------------
  Signal                = 6.335e+06 e⁻   (well 63%)
  Total noise σ_e       = 2,518 e⁻   (√signal = 2,517 → BLIP)
  NEP(chain)            = 2.223e-12 W
  D*(chain)             = 1.742e+11 Jones
  NETD(chain)           = 24.62 mK

--------------------------------------------------------------------------
BENCHMARK (tolerance ±15%)
--------------------------------------------------------------------------
Metric           Datasheet         Chain    Residual   Verdict
D* [Jones]        2.00e+11      1.74e+11      -12.9%      PASS
NETD [mK]             25.0          24.6       -1.5%      PASS

Wrote fig1_datasheet_benchmark.png
```

(One interpretive paragraph is trimmed from the block above; it is quoted in full in
the next section. The run takes 0.83 s.)

## The comparison

| Metric | Datasheet | Chain | Residual | Verdict (±15 %) |
|---|---|---|---|---|
| $D^*$ [Jones] | $2.00 \times 10^{11}$ | $1.74 \times 10^{11}$ | **−12.9 %** | PASS |
| NETD [mK] | 25.0 | 24.6 | **−1.5 %** | PASS |

Both pass. But they pass by very different margins — 1.5 % on NETD against 12.9 % on
$D^*$ — and the asymmetry is the interesting part of the result, not a blemish on it.

**The chain is background-limited, and that is why $D^*$ comes out low.** The run
reports a signal of $6.335 \times 10^{6}$ e- and a total noise of 2518 e- RMS, against
$\sqrt{6.335 \times 10^{6}} = 2517$ e-. The two agree to one part in 2500: every other
noise term in the budget — the 60 e- read noise, the 3 e- of dark shot over 30 µs —
is invisible in quadrature against photon shot noise. The system is **BLIP**,
background-limited in performance.

A datasheet's peak $D^*$ is a near-intrinsic figure: it characterises the *detector*,
measured under conditions chosen to expose the detector's own noise floor. A real
system staring at a 300 K scene through an f/2 cold stop is not in that condition —
it is drowning in scene photons — so its *system* detectivity is necessarily lower
than the detector's intrinsic one. The −12.9 % residual is that effect. It is in the
expected direction, and a residual of the *opposite* sign would have been the alarming
result, because it would mean the chain had found less noise than the physics of the
scene allows.

The script's own summary of this, printed verbatim with the table:

> Interpretation: the chain is photon-shot- (BLIP-) limited (σ_e ≈ √signal), so its
> system D* reflects the background-limited detectivity at these conditions.
> Agreement within tolerance validates RADIANT's noise model against the published
> figure; a residual would flag a background-flux or QE mismatch versus the datasheet
> reference.

**The electron-domain cross-check makes the same point in the other units.** The
datasheet's $D^*$, converted down, implies 2193 e- of total noise; the chain finds
2518 e-. That is 14.8 % more noise, which is the same statement as the −12.9 %
detectivity residual seen from the other side of the reciprocal. Dr. Chen gets to
check the bridge's arithmetic against itself without leaving the output block.

**NETD agrees far better because NETD is a ratio in which the background cancels.**
$\mathrm{NEDT} = \sigma_{total} / (\partial S/\partial T)$. In the BLIP limit the
numerator is $\sqrt{S}$ and the denominator is proportional to $S$ times the Planck
derivative's logarithmic slope, so the background flux largely divides out and what
survives is the thermal contrast of the scene and the band. The datasheet and the
chain are describing the same physics there, and they agree to 1.5 %.

**Regime: extended.** The 300 K scene fills the pixel footprint completely, so
RADIANT classifies the scene `extended` in the optics stage and every downstream
stage reads that classification. In the extended regime there is no separable
background term inside the target pixel — the pixel sees one radiance field — which
is why the noise budget here is signal shot plus electronics and nothing else. The
well fills to 63 % in 30 µs, confirming that the datasheet's short dwell is a
saturation constraint rather than a stylistic choice.

## Truth anchors behind the converters

The benchmark above tests the *model*. The converters it runs through were tested
first, on their own, in `src/radiant/performance/tests/test_noise_spec_converters.py`
(13 Level-0 tests), before this scenario was allowed to consume them:

| Anchor | Setup | Expected |
|---|---|---|
| $D^*$ definition | $A_d = 1 \times 10^{-4}$ cm², $\Delta f = 1$ Hz, $D^* = 1 \times 10^{10}$ Jones | NEP $= 1 \times 10^{-12}$ W (hand calculation) |
| NEP ↔ $\sigma_e$ | $\mathrm{NEP} = \sigma_e hc/(\eta \lambda t_{int})$, both directions | Exact round-trip |
| NEP ↔ NETD | NEP $1 \times 10^{-12}$ W, $\partial P/\partial T = 1 \times 10^{-11}$ W/K | NETD $= 0.1$ K |
| Full loop | $D^* \to \mathrm{NEP} \to \mathrm{NETD} \to \mathrm{NEP} \to D^*$ | Closes |

That ordering is the point. A unit bridge that has not been closed against a hand
calculation is not evidence about the model — it is a second, untested model sitting
between you and the answer.

## The takeaway

RADIANT reproduces a published cooled-LWIR FPA's NETD to 1.5 % and its $D^*$ to
12.9 %, both inside a ±15 % tolerance declared before the run, with the $D^*$ residual
explained in the right direction by the system's background-limited operating point.
For a researcher, the usable conclusion is narrower and more valuable than "the tool
works": **the electron-domain noise model, propagated from component specifications
plus scene photon shot noise, lands on published optical-power figures of merit** —
and when it does not, the converters give you the residual in whichever of the two
unit systems makes the diagnosis obvious.

The verification-of-numbers reflex here is worth keeping. The run was re-executed for
this chapter and reproduces the scenario's committed `walkthrough.md` table digit for
digit: $\sigma_e = 2518$ e-, $D^* = 1.742 \times 10^{11}$ Jones, NETD $= 24.62$ mK,
residuals −12.9 % and −1.5 %.

## The same study in the GUI

The scenario ships a GUI-openable baseline of this configuration,
`inputs/6.1_published_snr_benchmark.gui.yaml`, with its headline metrics snapshotted
in the neighbouring `.gui.expected.json`. Opening it puts the same LWIR FPA in the
window, where the Detector workspace's Noise tab shows the sixteen-term budget the
`signal_e / snr` shortcut above summarises, and the Performance workspace reports the
NETD directly. The scenario's `gui_workflow.md` specifies what a full benchmark
workflow would add on top: a datasheet-import step, a side-by-side benchmark panel
with the tolerance band shaded and a PASS/FAIL verdict — the content of
`outputs/fig1_datasheet_benchmark.png` — and a one-call "chain → $D^*$/NETD" helper
callable from the GUI's scripting window, so that the converter chain is available
interactively rather than only in a script. The converter functions themselves are
already importable there.
