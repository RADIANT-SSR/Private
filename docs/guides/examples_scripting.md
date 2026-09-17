# Scripting Examples

Six programs ship in `examples/scripts/`. Between them they cover the whole scripting
surface an analyst needs: load and evaluate, sweep, clone-and-diff, hand-rolled loops
with derived metrics, Monte Carlo tolerancing, and the multi-configuration study.
They are deliberately small — the largest is under sixty lines apart from the
configuration-set study — and each one is self-documenting, with its explanation in
the module docstring and in the output it prints.

Every output block below is the program's **actual** output, produced by running it
from the repository root:

```bash
PYTHONPATH=src python examples/scripts/<name>.py
```

Long tables are trimmed where the trim is marked; nothing is retyped or idealised.

All six run against `examples/mwir_leo_minimal.yaml`: a 0.30 m f/4 telescope at 8 km
altitude looking straight down at a 300 K, ε = 0.95 extended scene through a
mid-latitude-summer atmosphere, on an 18 µm-pitch focal plane with a 2 Me- well.
Because no target extent is given, the scene fills the pixel footprint and every one
of these examples runs in the **extended** radiometric regime. That single fact
explains most of what follows.

---

## 1. `basic_evaluation.py` — load, evaluate, read

**Demonstrates:** the three-line core of the API, plus the two result surfaces that
are not metrics — the noise budget and the stage history.

```python
from radiant.api.sensor import Sensor

CONFIG = Path(__file__).resolve().parent.parent / "mwir_leo_minimal.yaml"

sensor = Sensor.from_yaml(CONFIG)
result = sensor.evaluate()

for name, value in sorted(result.metrics.items()):
    print(f"  {name:20s} = {value:.6g}")

for nt in result.noise_terms:
    print(f"  {nt.name:25s}  {nt.value_e:.4f} e- RMS")

print(f"Stages executed: {' → '.join(result.history)}")
```

Output (metric list trimmed to the rows discussed):

```
=== RADIANT Basic Evaluation ===
Config: mwir_leo_minimal.yaml

  ee_1x1               = 0.414137
  ee_3x3               = 0.878017
  gsd_geometric_mean_m = 0.12
  mtf_at_nyquist       = 0.266771
  mtf_folded_at_nyquist = 0.53355
  nedt_K               = 0.024958
  niirs_extrapolated   = 1
  q_center             = 0.944444
  rer                  = 0.610069
  snr                  = 1124.03
  strehl               = 1
  well_margin_dB       = 3.98876
  ...                                   (35 metrics in total)

Noise budget:
  signal_shot                1124.0766 e- RMS
  background_shot            0.0000 e- RMS
  nearfield_shot             0.0000 e- RMS
  straylight_shot            0.0000 e- RMS
  dark_shot                  0.7071 e- RMS
  gr_noise                   0.0000 e- RMS
  johnson_noise              0.0000 e- RMS
  flicker_1f                 0.0000 e- RMS
  read_noise                 5.0000 e- RMS
  ktc_reset                  0.0000 e- RMS
  quantization               9.2376 e- RMS
  prnu                       0.0000 e- RMS
  dsnu                       0.0000 e- RMS
  clutter                    0.0000 e- RMS
  persistence_noise          0.0000 e- RMS
  glow_shot                  0.0000 e- RMS

Stages executed: geometry → source → atmosphere → optics → platform →
spectral_integration → detector → readout → calibration → performance
```

**What to notice.**

*The noise budget always has sixteen terms.* Twelve of them are exactly zero here
because this minimal config does not enable the physics that produces them — no
1/f corner, no PRNU or DSNU, no persistence, no clutter, no cold-shield glow. They
are printed anyway. A term that is zero because it was not configured and a term that
is zero because it is negligible look identical in a result object; they are
distinguished by the configuration, and printing the full taxonomy is what makes that
checkable.

*SNR is essentially the signal-shot term.* SNR = 1124.03 against a signal shot noise
of 1124.0766 e- RMS. In a shot-limited extended-source system the signal in electrons
is the square of the shot noise, so $\mathrm{SNR} = S/\sqrt{S} = \sqrt{S}$ — the SNR
and the shot-noise term in electrons are numerically the same to within the
contribution of everything else. Quadrature-summing the four non-zero terms gives
$\sqrt{1124.08^2 + 0.71^2 + 5.00^2 + 9.24^2} = 1124.13$ e- RMS, which is why the
5 e- RMS read noise and the 9.24 e- RMS quantization noise are visible in the budget
and invisible in the answer.

*The history is the architecture.* `result.history` is the ten stages in the order
they ran, geometry first. Nothing downstream re-decides what an earlier stage
concluded — the radiometric regime, for instance, is classified in the optics stage
and read unchanged by the six stages after it.

---

## 2. `aperture_sweep.py` — one axis, one metric, one figure

**Demonstrates:** `Sensor.sweep`, and the plotting helper that turns a `SweepResult`
into a figure.

```python
import numpy as np
from radiant.api.plot import plot_sweep
from radiant.api.sensor import Sensor

sensor = Sensor.from_yaml(CONFIG)

apertures = np.linspace(0.15, 0.60, 10)
result = sensor.sweep(
    "optics.aperture_diameter_m",
    apertures,
    metric="snr",
)

for d, snr in zip(result.values, result.metric_values, strict=True):
    print(f"{d:10.3f}  {snr:12.2f}")

fig = plot_sweep(result)
fig.savefig(OUTPUT, dpi=150)
```

Output (five saturation warnings elided — they are discussed below):

```
=== Aperture Sweep: SNR vs Aperture Diameter ===
     D (m)           SNR
------------------------
     0.150        561.94
     0.200        749.31
     0.250        936.67
     0.300       1124.03
     0.350       1311.38
     0.400       1414.17
     0.450       1414.17
     0.500       1414.17
     0.550       1414.17
     0.600       1414.17

Plot saved to: examples/scripts/aperture_sweep_snr.png
```

**What to notice.**

*The first five points are a straight line through the origin.* 561.94 / 0.150 m =
3746 per metre; 1311.38 / 0.350 m = 3747 per metre. For a shot-limited extended
source the collected signal scales as the collecting area, $S \propto D^2$, while the
dominant noise is its own square root, $\sqrt{S} \propto D$. So
$\mathrm{SNR} \propto D$ — linear in diameter, not quadratic. Doubling the aperture
doubles the SNR and costs four times the glass.

*The last five points are not physics.* From 0.40 m onward the answer is pinned at
1414.17 and the run emits a warning per point:

```
UserWarning: ReadoutStage: full well saturated — signal + dark + glow + near-field
+ stray = 2.246e+06 e- exceeds full_well_capacity_e = 2e+06 e- (fill fraction 1.12).
Signal clipped to 2e+06 e-. Downstream SNR/NEDT/NIIRS reflect the CLIPPED signal and
will not respond to scene/atmosphere changes.
```

1414.17 is $\sqrt{2 \times 10^{6}}$ — the shot-limited SNR of a pixel filled exactly
to its 2 Me- capacity, and therefore a constant independent of the scene. A trade
study that reads this plateau as "diminishing returns above 0.4 m" has drawn a
conclusion about an arithmetic clamp. The warning is the result; the number beside it
is not. The fix is a shorter integration time, a deeper well, or less throughput.

This is also the reason RADIANT raises rather than clips silently. A clipped chain
still produces a plausible-looking float, and a plausible-looking float in a
spreadsheet is indistinguishable from a real answer a week later.

---

## 3. `compare_configs.py` — clone, change, diff

**Demonstrates:** `Sensor.clone()` and `Sensor.set()`, and the fact that a
configuration change moves many metrics at once in directions that are not all the
same.

```python
baseline = Sensor.from_yaml(CONFIG)
baseline_result = baseline.evaluate()

modified = baseline.clone()
modified.set("optics.aperture_diameter_m", 0.45)
modified.set("spectral_integration.integration_time_s", 0.010)
modified_result = modified.evaluate()

all_metrics = sorted(set(baseline_result.metrics) | set(modified_result.metrics))
for name in all_metrics:
    v_base = baseline_result.metrics.get(name, float("nan"))
    v_mod = modified_result.metrics.get(name, float("nan"))
    delta = v_mod - v_base
    pct = (delta / v_base * 100.0) if v_base != 0.0 else float("nan")
    print(f"{name:>20s}  {v_base:12.4f}  {v_mod:12.4f}  {delta:+12.4f}  {pct:+9.1f}%")
```

Output (trimmed to the informative rows; the full table is 33 metrics):

```
=== Configuration Comparison ===

              Metric      Baseline      Modified         Delta     %Change
----------------------------------------------------------------------
       adc_margin_dB        4.4006        0.4119       -3.9888      -90.6%
        contrast_snr     1124.0273     4020.4751    +2896.4478     +257.7%
diffraction_limit_ground_m  0.1383        0.0922       -0.0461      -33.3%
              ee_1x1        0.4141        0.5444       +0.1302      +31.4%
              ee_3x3        0.8780        0.9199       +0.0419       +4.8%
   gsd_along_track_m        0.1200        0.1200       +0.0000       +0.0%
    mrt_at_nyquist_K        0.2105        0.1158       -0.0947      -45.0%
      mtf_at_nyquist        0.2668        0.3854       +0.1186      +44.5%
              nedt_K        0.0250        0.0198       -0.0051      -20.5%
            q_center        0.9444        0.6296       -0.3148      -33.3%
                 rer        0.6101        0.7065       +0.0964      +15.8%
                 snr     1124.0273     1414.1738     +290.1465      +25.8%
      well_margin_dB        3.9888        0.0000       -3.9888     -100.0%

Changes applied:
  optics.aperture_diameter_m: 0.30 → 0.45 m
  spectral_integration.integration_time_s: 0.005 → 0.010 s
```

**What to notice.**

*The spatial metrics are unambiguously better.* A 1.5× aperture shrinks the
diffraction limit at the ground from 0.1383 m to 0.0922 m — exactly 1/1.5 — pushes
$Q$ from 0.944 to 0.630 (deeper into detector-limited), lifts MTF at Nyquist from
0.2668 to 0.3854, RER from 0.6101 to 0.7065, and ensquared energy in the central
pixel from 0.4141 to 0.5444. GSD does not move at all, because GSD is pitch times
range over focal length and none of those changed. Sharper, not finer-sampled.

*The radiometric metrics are a trap.* SNR rises only 25.8 %, and `well_margin_dB`
falls to exactly 0.000. A 1.5× aperture and a 2× integration time together deliver
4.5× the electrons into a well that was already 63 % full, so the modified
configuration is clipped — and 1414.17 is once again $\sqrt{2\times10^{6}}$. The
+257.7 % on `contrast_snr` and the −20.5 % on NEDT are computed from a clipped
signal. `well_margin_dB` = 0.000 is the tell: zero headroom, by definition, is a full
well.

Read `well_margin_dB` and `adc_margin_dB` before reading anything in the radiometric
group. They are cheap and they are the honesty check on everything else.

*Units are in the names, not in the columns.* This script prints a bare numeric table
whose only unit information is what the metric names carry (`nedt_K`,
`gsd_along_track_m`, `well_margin_dB`). That is enough to read it, but it is thinner
than the rest of the repository's convention: compare the configuration-set study in
§6, which pulls each metric's unit from the metric registry and prints it in its own
column.

---

## 4. `custom_loop.py` — when the built-in sweep is not the shape you want

**Demonstrates:** that `clone()` + `set()` + `evaluate()` in a plain Python loop is a
first-class way to work, and that derived quantities the metric registry does not
define are yours to compute.

```python
base = Sensor.from_yaml(CONFIG)
t_int_values = [0.001, 0.002, 0.005, 0.010, 0.020, 0.050]

for t_int in t_int_values:
    s = base.clone()
    s.set("spectral_integration.integration_time_s", t_int)
    result = s.evaluate()

    snr = result.metrics["snr"]
    nedt_val = result.metrics.get("nedt")
    nedt = float(nedt_val) if nedt_val is not None else float("nan")

    # Time-normalized SNR: SNR / sqrt(t_int) — useful for comparing
    # detector performance independent of integration time.
    snr_norm = snr / math.sqrt(t_int)

    print(f"{t_int * 1000:12.1f}  {snr:10.2f}  {snr_norm:10.2f}  {nedt:10.6f}")
```

Output (three saturation warnings elided):

```
=== Custom Loop: Integration Time Analysis ===

  t_int (ms)         SNR      SNR/√t    NEDT (K)
----------------------------------------------
         1.0      502.59    15893.37         nan
         2.0      710.85    15895.11         nan
         5.0     1124.03    15896.15         nan
        10.0     1414.17    14141.74         nan
        20.0     1414.17     9999.71         nan
        50.0     1414.17     6324.37         nan

SNR/√t should be approximately constant if the system is
photon-noise-limited (shot noise ∝ √signal ∝ √t_int).
```

**What to notice.**

*The script's own hypothesis is confirmed, then broken, and the break is the point.*
For the first three rows $\mathrm{SNR}/\sqrt{t}$ is constant to four significant
figures — 15893, 15895, 15896 per $\sqrt{\mathrm{s}}$. Signal scales with integration
time, shot noise with its square root, so SNR scales as $\sqrt{t}$: this system is
photon-noise-limited. From 10 ms the ratio collapses (14142, 9999.7, 6324.4) because
the SNR column has stopped moving. The well fills at about 8 ms, and past that point
longer integration buys nothing but a clipped pixel. A constant
$\mathrm{SNR}/\sqrt{t}$ is a diagnostic for "photon-limited"; a *falling* one is a
diagnostic for "saturated or read-noise-limited", and telling those two apart is
exactly what this column is for.

*The NEDT column is a bug in the example, not in the chain.* The metric is registered
as `nedt_K`, carrying its unit in its name, and the script asks for `nedt`. `.get()`
returns `None`, the guard turns it into `nan`, and every row prints `nan`. The right
lookup is `result.metrics["nedt_K"]`, which returns 0.024958 K for the 5 ms row — the
same value `basic_evaluation.py` prints. The column header says `NEDT (K)`, so the
unit convention is intact; the key is not. Treat this as the cautionary example it
accidentally is: `result.metrics` is a plain mapping, `.get()` on a mis-remembered
key fails silently, and `result.metric_records()` is the surface that will tell you
the registered names and their units.

---

## 5. `tolerance_analysis.py` — Monte Carlo over manufacturing spread

**Demonstrates:** `set_tolerance`, `monte_carlo`, and the statistics and correlation
surface on the result — the answer to "which of my tolerances actually matters".

```python
sensor = Sensor.from_yaml(CONFIG)

sensor.set_tolerance("optics.aperture_diameter_m", "gaussian", std_fraction=0.02)
sensor.set_tolerance("optics.transmission_scalar", "gaussian", std_fraction=0.05)
sensor.set_tolerance("detector.qe_value",          "gaussian", std_fraction=0.03)

mc_result = sensor.monte_carlo(n_trials=50, seed=42)

for metric in mc_result.metric_names:
    print(f"{metric}:")
    print(f"  Mean:  {mc_result.mean(metric):.4f}")
    print(f"  Std:   {mc_result.std(metric):.4f}")
    print(f"  5th %%: {mc_result.percentile(metric, 5.0):.4f}")
    print(f"  95th %%: {mc_result.percentile(metric, 95.0):.4f}")

corr = mc_result.correlation("snr")
for param, r in sorted(corr.items(), key=lambda kv: abs(kv[1]), reverse=True):
    print(f"  {param:40s}  r = {r:+.4f}")
```

Output (per-metric blocks trimmed to four of the thirty-three):

```
=== Monte Carlo Tolerance Analysis ===
Trials: 50
Seed:   42

snr:
  Mean:  1119.8083
  Std:   38.5357
  5th %%: 1065.5523
  95th %%: 1170.0833

nedt_K:
  Mean:  0.0251
  Std:   0.0008
  5th %%: 0.0240
  95th %%: 0.0263

ee_1x1:
  Mean:  0.4142
  Std:   0.0073
  5th %%: 0.4049
  95th %%: 0.4268

well_margin_dB:
  Mean:  4.0640
  Std:   0.5916
  5th %%: 3.2912
  95th %%: 4.9168

Correlation with SNR:
  optics.transmission_scalar                r = +0.8184
  optics.aperture_diameter_m                r = +0.5109
  detector.qe_value                          r = +0.4983
```

**What to notice.**

*The correlations rank the tolerances, and the ranking is not the obvious one.*
Transmission dominates at $r$ = +0.82 despite being only a 5 % 1σ spread, because it
enters the signal linearly. Aperture is next at +0.51 even though signal goes as
$D^2$ — because its spread is only 2 %, so its contribution to the *variance* is
$2 \times 2\,\% = 4\,\%$ against transmission's 5 %. QE at 3 % lands at +0.50,
essentially tied with aperture. Read the correlations together with the spreads you
assigned: they measure the tolerance you set, not the sensitivity of the physics
alone. If tightening one tolerance is cheap, this table says which one to tighten.

*The metric means are not the nominal values.* Nominal SNR is 1124.03; the
Monte Carlo mean is 1119.81 with σ = 38.54. The shortfall is about 0.1 σ — sampling
noise at 50 trials, not a bias — but it is the kind of difference worth tracking: a
nonlinear response to symmetric input spread genuinely does move the mean, and with
only 50 samples you cannot yet tell which you are looking at. Raise `n_trials` before
reading anything into a sub-σ shift.

*The run is reproducible.* `seed=42` is echoed in the output, and the same seed gives
the same 50 draws and the same statistics on any machine.

*One cosmetic defect.* The `5th %%:` and `95th %%:` labels print a doubled percent
sign: the script uses printf-style `%%` escaping inside an f-string, where it has no
meaning. Harmless, and the numbers either side of it are correct.

---

## 6. `dual_band_configuration_set.py` — one telescope, three ways to operate it

**Demonstrates:** the multi-configuration API — `ConfigurationSet`, `configure()`,
`evaluate_all()`, `compare()`, `save()`/`load()` — and per-configuration warning
attribution. At 470 lines it is the largest example, and most of those lines are the
printed explanation rather than the modelling.

The study is a single 0.30 m f/4 telescope at 8 km altitude on one 18 µm-pitch focal
plane, operated three ways:

| Configuration | Band | Integration | QE | Well |
|---|---|---|---|---|
| `MWIR` | 3.5–5.0 µm | 5.0 ms | 0.70 | 2.0 Me- |
| `LWIR` | 8.0–12.0 µm | 0.5 ms | 0.55 | 6.0 Me- |
| `LWIR_long` | 8.0–12.0 µm | 2.0 ms | 0.55 | 6.0 Me- |

```python
from radiant.api import ConfigSetRunResult, ConfigurationSet, Sensor

base = Sensor.from_yaml(BASE_CONFIG, wavelength_points=300)
study = ConfigurationSet(base, names=["MWIR", "LWIR", "LWIR_long"])

study.configure("spectral_integration.filter_min_um",       [3.5,   8.0,    8.0])
study.configure("spectral_integration.filter_max_um",       [5.0,  12.0,   12.0])
study.configure("spectral_integration.integration_time_s",  [0.005, 0.0005, 0.002])
study.configure("detector.qe_value",                        [0.70,  0.55,   0.55])
study.configure("detector.dark_rate_e_per_s",               [1.0e5, 2.0e6,  2.0e6])
study.configure("readout.full_well_capacity_e",             [2.0e6, 6.0e6,  6.0e6])
study.configure("readout.gain_e_per_dn",                    [32.0,  92.0,   92.0])

study.baseline = "MWIR"   # deltas in compare() are measured against this
study.active   = "MWIR"   # evaluated first (this is the GUI's displayed one)

run = study.evaluate_all()
comparison = study.compare(run)
```

Seven parameters are configured; eleven stay shared — aperture, focal length,
altitude, pixel pitch, read noise, scene temperature, emissivity, and the atmosphere.
A change to any shared value moves all three configurations at once. That is the
whole point of the model: the study states what differs, not what is repeated.

Output (heavily trimmed — the program prints about 310 lines):

```
Summary (one line per configuration, evaluation order = active first):

  MWIR      *  ok   snr = 1124 [dimensionless]; nedt_K = 0.02496 [K]; gsd_geometric_mean_m = 0.12 [m]
  LWIR         ok   snr = 2248 [dimensionless]; nedt_K = 0.02761 [K]; gsd_geometric_mean_m = 0.12 [m]
  LWIR_long    ok   snr = 2448 [dimensionless]; nedt_K = 0.02536 [K]; gsd_geometric_mean_m = 0.12 [m]   (2 warnings)
  (* = baseline: 'MWIR'; 0 of 3 configuration(s) failed)

Warning attribution — each warning belongs to exactly one configuration:

  MWIR         no warnings
  LWIR         no warnings
  LWIR_long    2 warning(s): ...

Focus metrics (value [unit], then delta vs baseline):

metric                      unit                     MWIR                  LWIR             LWIR_long
-----------------------------------------------------------------------------------------------------
snr                         dimensionless         1123.79   2248.25 (+1.12e+03)   2447.71 (+1.32e+03)
nedt_K                      K                   0.0249632  0.0276141 (+0.00265)  0.0253638 (+0.000401)
gsd_geometric_mean_m        m                        0.12                  0.12                  0.12
diffraction_limit_ground_m  m                    0.138267     0.325333 (+0.187)     0.325333 (+0.187)
q_center                    dimensionless        0.944444       2.22222 (+1.28)       2.22222 (+1.28)
mtf_at_nyquist              dimensionless        0.266683  5.42079e-17 (-0.267)  5.42079e-17 (-0.267)
ee_1x1                      fraction             0.414038    0.135344 (-0.279)     0.135344 (-0.279)
well_margin_dB              dB                    3.98901        1.48629 (-2.5)    0.00579252 (-3.98)
```

and, later, the program's own reading of those numbers:

```
  MWIR         GSD =   0.12 m   diffraction blur = 0.1383 m   Q = 0.944 [dimensionless]
  LWIR         GSD =   0.12 m   diffraction blur = 0.3253 m   Q =  2.22 [dimensionless]
  LWIR_long    GSD =   0.12 m   diffraction blur = 0.3253 m   Q =  2.22 [dimensionless]

  MWIR         t_int =      5 ms   SNR =    1124   NEDT =  24.96 mK   well fill =  63.2 %
  LWIR         t_int =    0.5 ms   SNR =    2248   NEDT =  27.61 mK   well fill =  84.3 %
  LWIR_long    t_int =      2 ms   SNR =    2448   NEDT =  25.36 mK   well fill = 337.2 %

  LWIR       well 5.057e+06 e- of 6e+06 e-  (84.3 %) -> ok
  LWIR_long  well 2.023e+07 e- of 6e+06 e-  (337.2 %) -> clipped
```

**What to notice.**

*Same GSD, different imaging regime.* All three configurations sample the ground at
0.12 m, because GSD is set by pitch, focal length, and range — all shared. The
*optical* blur is not shared: diffraction scales with wavelength, so the LWIR spot on
the ground is 0.3253 m against the MWIR's 0.1383 m, a factor of 2.35 from the very
same 0.30 m aperture. $Q = \lambda F/\# / p$ therefore runs 0.944 in the MWIR
(undersampled, detector-limited, MTF at Nyquist a healthy 0.2667) and 2.22 in the
LWIR (oversampled, optics-limited, MTF at Nyquist 5.4 × 10⁻¹⁷ — numerically zero,
because diffraction cuts off *below* Nyquist). One telescope, one focal plane, two
genuinely different imaging regimes, chosen only by the band.

*A metric can diverge without being wrong.* Because MRT at Nyquist scales as
1/MTF, the LWIR configurations report `mrt_at_nyquist_K` of order $10^{15}$ K. That
is the metric correctly reporting "this system resolves nothing at Nyquist in this
band", not a temperature. Evaluate LWIR resolution below the optical cutoff instead.

*Aliasing behaves as the sampling theorem says it must.* The MWIR folded MTF at
Nyquist is 0.5334 = 2 × 0.2667, and the alias fraction is 0.5000: at Nyquist the
first sampling replica lands back on Nyquist, so exactly half the apparent contrast
there is folded-in above-Nyquist content. The LWIR folded value is 9.7 × 10⁻¹⁶ — zero
— and its alias fraction reads exactly 0. The optics cut off below Nyquist, so there
is nothing to alias. That zero is *reported*, not computed: the ratio is evaluated
only where the folded MTF exceeds 10⁻⁹ of its DC value, below which both terms are
round-off.

*The interesting sensitivity result is not the smaller NEDT.* The LWIR configuration
reaches 27.61 mK — within about 11 % of the MWIR's 24.96 mK — while integrating ten
times shorter, and still fills a three-times-deeper well to 84.3 %. At 300 K the
scene's spectral radiance peaks near 9.7 µm, and $dL/dT$ — which is what NEDT
actually measures — is far larger in absolute terms in the LWIR. The band is not
photon-starved; it is well-depth-limited. At equal integration time the LWIR
configuration would be decisively more sensitive, and it cannot use equal integration
time on this focal plane.

*`LWIR_long` demonstrates the trap it was built to demonstrate.* Four times the LWIR
integration time overfills a 6 Me- well to 337.2 %. Its SNR of 2448 is the highest in
the study and it collects the `*` best-value mark on several metrics, and it has won
nothing: its signal was clipped, so its SNR and NEDT no longer respond to the scene.
The two warnings that say so are attributed to `LWIR_long` alone — not re-raised into
the caller's warning filters, not attached to the study as a whole — so a noisy
configuration cannot be mistaken for a property of the run. Trade integration time
against well depth, not against SNR alone.

*The whole study is one file.* `study.save(path)` writes an ordinary RADIANT config
plus one `configurations:` section carrying the names, the baseline, the active
configuration, and the dense per-configuration value lists. A file without that
section is byte-for-byte today's format and still loads as the degenerate
one-configuration set. The script round-trips its own output and checks that the
names, the configured table, and the shared parameters all come back identical.

---

## What these six do not cover

Batch matrices over more than two axes, measured-data import and reconciliation,
Zernike wavefront import, and the flagship-mission validation comparisons all live in
the scenario suite rather than in `examples/scripts/`. `docs/guides/scenario_catalog.md`
indexes them, and later chapters of this volume work several of them end to end.
