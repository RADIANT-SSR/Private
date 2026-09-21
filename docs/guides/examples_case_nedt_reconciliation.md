# Case Study — Reconciling Predicted and Measured NEDT

**Scenario 7.1** · persona: Karen, test engineer · modality: script-led ·
scenario folder: `scenarios/07_karen_test_engineer/7.1_nedt_reconciliation/`

---

## The question

Karen has just finished TVAC testing an as-built MWIR sensor. She put a calibrated
blackbody in front of it at seven temperatures from 15 °C to 50 °C, took 500 frames at
each, and computed NEDT. At her primary test point, 25 °C, she measured
**127.0 mK ± 6.0 mK**.

She then configured RADIANT with the as-built parameters — the *measured* QE, the
*measured* dark current, the *measured* read noise, the *as-built* f-number, not the
nominal design values — and it predicted **74.17 mK**.

That is a 52.83 mK gap, and the prediction is the optimistic one. This is the
canonical test-engineer question and it has no comfortable answer: **does the model
match the measurement, and if not, what is the missing noise?** A gap that cannot be
attributed is a gap that will be re-argued at every design review until somebody
attributes it.

## The inputs, and why they are what they are

Everything arrives in one three-sheet workbook, `inputs/karen_nedt_lab_data.xlsx`,
which is Karen's lab notebook in vendor format. The script reads it with `openpyxl`
and converts at the boundary.

**System configuration** (sheet 1) — the optical bench as built:

| Quantity | Lab value | Canonical | Why it differs from nominal |
|---|---|---|---|
| Aperture diameter | 30.0 cm | 0.300 m | As designed. |
| Effective focal length | 121.5 cm | 1.215 m | Gives f/4.05, not the f/4.00 nominal — 1.25 % slow. |
| Optical transmission | 71.0 % | 0.710 | 73 % nominal; 2 points lost in the as-built coatings. |
| Optics temperature | 22.0 °C | 295.15 K | Lab ambient. The optics are *warm*. |
| Spectral band | 3500–5000 nm | 3.50–5.00 µm | MWIR cold filter at 77 K. |
| Blackbody emissivity | 0.995 | 0.995 | CI Systems SR-800R, ±0.02 °C stability. |
| Shroud | 22.0 °C, ε = 0.95 | 295.15 K | The TVAC chamber wall. |

**As-built detector** (sheet 2) — the FPA as measured, with the nominal value for
comparison:

| Quantity | As-built | Nominal | Deviation |
|---|---|---|---|
| Pixel pitch | 18 µm | 18 µm | — |
| Quantum efficiency | 68.0 % | 72.0 % | −4 points |
| Dark current | 135 e-/s | 100 e-/s | +35 % |
| Read noise (post-CDS) | 14.2 e- RMS | 12.0 e- RMS | +18 % |
| Full well | 500,000 e- | — | — |
| System gain / ADC | 12 e-/DN / 14 bit | — | — |
| Integration time | 0.5 ms | — | Lab test value; 8 ms in orbit. |
| IPC coupling | 1.5 % | — | — |
| ROIC glow | 5 e-/s | — | Measured, and **not modeled** — see below. |

**NEDT measurements** (sheet 3) — seven temperatures, 500 frames each, with the
measurement's own $\sigma$ so that the comparison carries error bars.

The single most consequential configuration choice is not in the workbook at all:

```python
"atmosphere": {
    "model": "exo",  # Vacuum — no atmospheric effects
},
```

The sensor is inside a TVAC chamber. There is no atmosphere. `exo` sets
$\tau_{atm} = 1$, $L_{path} = 0$ and $L_{atm,down} = 0$, so the only thermal sources in
the model are the blackbody, the shroud and the warm optics. Getting this wrong — by
leaving a default terrestrial column in place — would put an entire atmosphere between
a blackbody and a sensor sitting 30 cm apart on a bench, and no amount of gap analysis
downstream would recover from it.

## The physics being tested

$$\mathrm{NEDT} = \frac{\sigma_{total}}{\partial S/\partial T}$$

A noise in electrons over a responsivity in electrons per kelvin. Both halves have to
be right, and they fail in different ways: an error in $\sigma_{total}$ is a noise-model
error, an error in $\partial S/\partial T$ is a radiometry error. The decomposition
that follows is what separates them.

Each noise term carries its own share:

$$\mathrm{NEDT}_i = \frac{\sigma_i}{\partial S/\partial T},
\qquad
\mathrm{NEDT}_{total} = \sqrt{\textstyle\sum_i \mathrm{NEDT}_i^2}$$

## The scripted path

```bash
S=scenarios/07_karen_test_engineer/7.1_nedt_reconciliation
PYTHONPATH=src python $S/scripts/run_nedt_reconciliation.py
```

### Importing measured data

```python
INPUT_FILE = Path(__file__).parent.parent / "inputs" / "karen_nedt_lab_data.xlsx"
wb = openpyxl.load_workbook(INPUT_FILE)

ws_sys = wb["System Configuration"]
sys_specs: dict[str, object] = {}
for row in ws_sys.iter_rows(min_row=5, max_col=4, values_only=False):
    name, value = row[0].value, row[1].value
    if name and value is not None:
        try:
            sys_specs[name] = float(value)
        except (ValueError, TypeError):
            sys_specs[name] = value
```

Unremarkable code doing the essential thing: the lab's own workbook is the input, in
the lab's own units, and the conversion to canonical units happens exactly once, here
at the boundary, before anything touches the chain. The script prints the conversion
table so Karen can audit it — every row of it appears in the output below.

### Computing $\partial S/\partial T$ by finite difference

RADIANT does not expose its internal thermal derivative, so the script builds one:

```python
DELTA_T = 0.5  # K — finite difference step for dS/dT

result_center = Sensor.from_dict(make_config(T)).evaluate()
result_plus   = Sensor.from_dict(make_config(T + DELTA_T)).evaluate()
result_minus  = Sensor.from_dict(make_config(T - DELTA_T)).evaluate()

signal_e     = result_center.stage_outputs["readout"]["signal_e_final"]
signal_plus  = result_plus.stage_outputs["readout"]["signal_e_final"]
signal_minus = result_minus.stage_outputs["readout"]["signal_e_final"]
ds_dt = (signal_plus - signal_minus) / (2.0 * DELTA_T)  # e⁻/K
```

Three full chain evaluations per measurement temperature, twenty-one in all. A central
difference at $\delta T = 0.5$ K is accurate to better than 0.1 % against the analytic
Planck derivative over this range — the Planck function's curvature in the MWIR at
288–323 K is gentle enough that the second-order error term is negligible.

### The per-term decomposition and the gap

```python
noise_dict = {nt.name: nt.value_e for nt in result_center.noise_terms}
total_noise = math.sqrt(sum(v**2 for v in noise_dict.values()))
nedt_pred_mK = total_noise / ds_dt * 1000.0

nedt_per_term = {name: sigma / ds_dt * 1000.0 for name, sigma in noise_dict.items()}
```

and then the reconciliation itself, which is three lines of arithmetic and the whole
point of the exercise:

```python
sigma_meas = primary["meas_nedt_mK"] / 1000.0 * ds_dt   # measured NEDT → electrons
sigma_missing_sq = sigma_meas**2 - sigma_pred**2
sigma_missing = math.sqrt(sigma_missing_sq)
```

Run the measured NEDT *backwards* through the same $\partial S/\partial T$ to get the
noise the measurement implies, then subtract the model's noise in quadrature. What is
left is the unmodeled noise, in electrons, which is a far more actionable quantity
than a millikelvin discrepancy.

### Real output — the comparison

```text
=== Predicted vs. Measured NEDT ===
 BB T [°C] BB T [K] Meas [mK] Pred [mK]  Δ [mK] Signal [e⁻] dS/dT [e⁻/K] σ_total [e⁻]
  --------  -------  --------  --------  ------  ----------  -----------  -----------
      15.0   288.15     160.0     83.86   76.14      99,144       3758.9       315.21
      20.0   293.15     142.0     78.76   63.24     119,491       4392.9       345.98
      25.0   298.15     127.0     74.17   52.83     143,203       5105.7       378.70
      30.0   303.15     114.0     70.03   43.97     170,688       5903.0       413.40
      35.0   308.15     104.0     66.28   37.72     202,383       6790.9       450.11
      40.0   313.15      95.0     62.87   32.13     238,756       7775.2       488.84
      50.0   323.15      81.0     56.93   24.07     327,553      10056.9       572.51
```

### Real output — the noise budget at the primary test point

```text
=== NEDT Breakdown at Primary Test Point (25°C / 298.15 K) ===
  Signal:            143,203 e⁻
  dS/dT:              5105.7 e⁻/K
  Total noise:        378.70 e⁻ RMS

  Noise Term                   σ [e⁻ RMS]   NEDT_i [mK]   Fraction [%]
  -------------------------  ------------  ------------  -------------
  signal_shot                      378.42        74.117           99.9
  read_noise                        14.20         2.781            0.1
  quantization                       3.46         0.678            0.0
  dark_shot                          0.26         0.051            0.0
  background_shot                    0.00         0.000            0.0
  nearfield_shot                     0.00         0.000            0.0
  ...                          (ten further terms, all 0.00)
  ─────────────────────────  ────────────  ────────────  ─────────────
  RSS TOTAL                        378.70        74.173          100.0

  Measured NEDT:  127.0 mK
  Predicted NEDT: 74.17 mK
  Gap:            52.83 mK
```

### Real output — the gap analysis

```text
=== Gap Analysis ===
  σ_predicted:    378.70 e⁻ RMS
  σ_measured:     648.42 e⁻ RMS  (from NEDT = 127.0 mK)
  σ_missing:      526.34 e⁻ RMS  (RSS gap)
  NEDT_missing:   103.09 mK

  Noise Term      Current σ [e⁻] Required σ [e⁻] Increase [%]  Plausible?
  --------------  -------------- --------------- ------------  --------------------
  signal_shot             378.42          648.26         71.3  Unlikely alone
  read_noise               14.20          526.54       3608.0  Cannot explain alone
  quantization              3.46          526.36      15094.6  Cannot explain alone
  dark_shot                 0.26          526.34     202489.9  Cannot explain alone
  ...                          (twelve further terms, all "Cannot explain alone")
```

### Real output — sensitivity, and nominal versus as-built

```text
  Ranked by |sensitivity| (most impactful first):
    1. f-number (via focal length): 0.7428 mK per 1% change
    2. Optical transmission: 0.3714 mK per 1% change
    3. QE: 0.3714 mK per 1% change
    4. Integration time: 0.3714 mK per 1% change
    5. Read noise: 0.0010 mK per 1% change
    6. Dark current: 0.0000 mK per 1% change

=== Nominal vs. As-Built NEDT ===
  NEDT (nominal params):   70.19 mK
  NEDT (as-built params):  74.17 mK
  NEDT (measured):         127.0 mK

  Nominal → As-built degradation: 3.98 mK
  As-built → Measured gap:        52.83 mK
```

(The run takes 7.2 s and also writes `outputs/nedt_reconciliation_results.xlsx`.)

## What the numbers say

**Regime: extended.** The blackbody overfills the field of view — every pixel sees
blackbody radiance directly. The optics stage classifies the scene `extended`, and in
that regime the pixel is a single radiance field with no separable in-pixel background
term.

### The model is signal-shot-limited, and nothing else is close

99.9 % of the predicted noise is `signal_shot`. Read noise contributes 2.78 mK of the
74.17 mK, quantization 0.68 mK, dark shot 0.05 mK. On a 143,203 e- signal the
electronics are simply not in the conversation.

This is worth stating plainly because it forecloses an entire class of corrective
action. If the *model* is right, no better ROIC and no colder detector improves this
sensor: the remedy for a shot-limited system is more signal or less background — cold
optics, a tighter cold shield, spectral narrowing — not quieter electronics.

### The shroud background is *not* counted, and that is correct

An older vintage of this scenario carried a `background_shot` term of roughly 349 e-
from the 295 K shroud, about 46 % of the budget. It is now exactly zero, and the
reason is the extended regime: during a NEDT measurement the large-area blackbody
**fills the target pixel**. The shroud is not in that pixel. Adding its shot noise to
the target pixel's budget was a double count.

Removing it dropped the prediction from about 100 mK to 74 mK — and therefore
**widened** the gap against the 127 mK measurement. That is the right outcome and the
uncomfortable one. The old prediction was not closer to the measurement because it was
better; it was closer because a spurious term happened to push it that way. Anyone
reading an older baseline of this scenario should know that the smaller gap it reports
is not a better model.

### 526 e- of noise is missing, and no single modeled term can supply it

The reconciliation: $\sigma_{meas} = 0.127 \times 5105.7 = 648.42$ e- RMS against
$\sigma_{pred} = 378.70$ e- RMS, leaving
$\sqrt{648.42^2 - 378.70^2} = 526.34$ e- RMS unaccounted — **139 % of the predicted
noise**, worth 103.09 mK on its own.

The "what would it take" table is the script's most useful output and its verdict is
uniform: read noise would have to rise 3608 %, dark shot 202,490 %, quantization
15,095 %. Even signal shot — the one term large enough to be in the running — would
need to rise 71.3 %, which would require the collected signal to be 2.9 times what the
radiometry says it is. **No single modeled term explains the gap**, which is precisely
the finding that sends Karen to look outside the model.

Four candidates, in the order Karen should test them:

1. **Unmodeled mirror self-emission.** `nearfield_shot` is 0.00 e- and should not be.
   In scalar-transmission mode the lumped optical element is treated as refractive: by
   Kirchhoff, $T + R = 1$ so $\varepsilon = 1 - T - R = 0$, and a zero-emissivity
   element emits nothing. But these are **mirrors at 295 K in the MWIR**, and real
   mirrors with $\varepsilon = 1 - R$ emit. Capturing that requires the `key_elements`
   or `full_prescription` optical mode rather than a scalar throughput. This is the
   leading physical candidate and the one that would change the model's answer.
2. **The measurement is spatial, the prediction is temporal.** Karen computes NEDT as
   the $\sigma$ across a 100 × 100 pixel ROI. That statistic contains pixel-to-pixel
   responsivity and offset variation — PRNU and DSNU — which are *not* temporal noise.
   RADIANT's `prnu` and `dsnu` terms are both 0.00 e- here because the config does not
   enable them. A spatial $\sigma$ compared against a temporal $\sigma$ is not the same
   measurement, and on an uncorrected FPA the difference is easily this large.
3. **Unmodeled ROIC glow.** The workbook records 5 e-/s of ROIC glow. RADIANT's
   `glow_shot` term is always zero — the physics is not implemented. At 0.5 ms this is
   a small contributor, but it is a known-missing term rather than a negligible one.
4. **Blackbody calibration and chamber reflections.** The SR-800R's ±0.02 °C stability
   contributes roughly $0.02 \times 5106 = 102$ e- of apparent noise, and the
   $\varepsilon = 0.95$ shroud reflects 5 % of the blackbody's emission back toward the
   sensor.

### The as-built deviations explain almost nothing, and that is good news

Nominal 70.19 mK against as-built 74.17 mK: the QE loss, the 35 % higher dark current,
the 18 % higher read noise and the 1.25 % slower optics together cost **3.98 mK**, 7.5 %
of the 52.83 mK gap. The sensitivity table explains why. Only four parameters move NEDT
at all, and the largest — f-number — is worth 0.74 mK per 1 % change; read noise is
0.0010 mK per 1 % and dark current is 0.0000 mK per 1 %. In a shot-limited system,
NEDT $\propto 1/\sqrt{S}$ and $S \propto \tau/(f/\#)^2$, so f-number enters squared and
the electronics do not enter at all.

The message to Karen is therefore quite specific: **the sensor is performing close to
its as-built specification. The discrepancy is in the model's completeness and in the
test method, not in the hardware.** Chasing the 35 % dark-current excess would be
wasted effort.

### NEDT improves at higher blackbody temperature

From 15 °C to 50 °C, measured NEDT falls 160 → 81 mK and predicted 83.86 → 56.93 mK.
Both curves fall because $\partial S/\partial T$ grows faster than the noise does:
across that range $\partial S/\partial T$ rises 3759 → 10,057 e-/K (2.68×) while
$\sigma_{total}$ rises only 315 → 573 e- (1.82×), because shot noise grows as
$\sqrt{S}$. This is the Wien-side behavior of the Planck function in the MWIR, and
the fact that both the measurement and the model show it is a check that the
*responsivity* half of the NEDT ratio is right even though the *noise* half is not.

Note that the gap narrows with temperature too, 76.14 mK at 15 °C to 24.07 mK at 50 °C.
The missing noise is therefore not a fixed electron count — it scales with the scene.
That is itself a clue, and it points away from a constant additive term like ROIC glow
and toward something proportional to signal, which is what PRNU in a spatial-$\sigma$
measurement looks like.

## One caveat the run raises and the walkthrough does not

The three hottest test points — 35 °C, 40 °C and 50 °C, at all three finite-difference
perturbations — **exceed the 14-bit ADC full scale** at the as-built 12 e-/DN gain. The
run emits nine warnings of the form:

```text
UserWarning: ReadoutStage: ADC saturated — signal 2.73e+04 DN exceeds full scale
16383 DN (14-bit at 12 e-/DN). Signal clipped to 16383 DN. Increase
readout.gain_e_per_dn or readout.adc_bits, or reduce the signal (integration time,
aperture). (readout.adc_status = 'clipped')
```

The NEDT column is unaffected: the signal and $\partial S/\partial T$ the script reads
are electron-domain quantities, and the monotone $\partial S/\partial T$ progression in
the results table confirms the clip does not propagate into them. But a *real*
measurement at those three temperatures, on this ROIC at this gain, would have been
digitizer-limited — 327,553 e- is 27,296 DN against a 16,383 DN full scale — and the
comparison at 50 °C is therefore between a model of an unclipped sensor and a
measurement of a clipped one. The three lowest test points are clean. The scenario's
`walkthrough.md` does not mention this; the warning is the tool behaving correctly and
the omission is in the narrative, not the code.

## The takeaway

1. **The gap is real and it is 52.83 mK**, or equivalently 526 e- RMS of noise the
   model does not contain — 139 % of the noise it does.
2. **No modeled term can absorb it.** Every candidate would need an implausible
   increase; the reconciliation table makes that quantitative rather than rhetorical.
3. **The three leading explanations are all outside the current model**: warm-mirror
   self-emission that scalar transmission mode cannot produce, a spatial-versus-temporal
   mismatch in what "NEDT" means on each side of the comparison, and unmodeled ROIC
   glow.
4. **The hardware is fine.** As-built deviations cost 3.98 mK; the sensitivity analysis
   shows no ±1 % parameter perturbation could close the remaining gap.
5. **The honest prediction is the wider gap.** Removing a spurious shroud term made the
   model better and the agreement worse. Agreement achieved through a compensating
   error is not agreement.

Numbers in this chapter come from a re-run of the committed runner and reproduce the
scenario's `walkthrough.md` tables exactly — 74.17 mK predicted, 127.0 mK measured,
52.83 mK gap, 526.34 e- missing, 3.98 mK of as-built degradation, and every sensitivity
coefficient.

## The same study in the GUI

The scenario ships a GUI-openable baseline of the as-built sensor at the primary test
point, `inputs/7.1_nedt_reconciliation.gui.yaml`, with headline metrics snapshotted in
`.gui.expected.json`. Opening it puts the TVAC configuration in the window — `exo`
atmosphere, 298.15 K blackbody, warm shroud — where the Detector workspace's Noise tab
shows the same sixteen-term budget reproduced above and the Performance workspace
reports the 74.17 mK directly, so the prediction half of the reconciliation is a
single click rather than a script. The scenario's `gui_workflow.md` specifies what a
complete reconciliation workspace would add: a spreadsheet-import step that maps the
three sheets onto optics, detector and validation-target data with the unit
conversions highlighted; a nominal-versus-as-built table with deviations color-coded;
a **Lab / TVAC test mode** that recognizes the bench context and proposes
`atmosphere.model = "exo"` rather than leaving the analyst to know that; a progress
view over the seven temperatures × three runs; and the three comparison charts — NEDT
versus temperature with measurement error bars and the gap shaded, the noise-budget
breakdown, and the sensitivity ranking. The gap analysis itself has no built-in method
today; the script computes $\sigma_{missing}$ by hand, and a GUI would be doing the
same arithmetic behind the button.
