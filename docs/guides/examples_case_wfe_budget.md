# Case Study — Allocating a Wavefront-Error Budget

**Scenario 5.1** · persona: Tom, optical designer · modality: script-led ·
scenario folder: `scenarios/05_tom_optical_designer/5.1_wfe_budget_allocation/`

---

## The question

Tom has a 40 cm Cassegrain on his screen in Zemax: f/10, 35 % linear central
obscuration, operating in the VNIR from 500 to 800 nm on a 500 km orbit. The design
closes. What he does not yet have is a **budget** — a defensible statement of how much
total wavefront error the telescope may accumulate, across design residual, assembly
tolerance and on-orbit thermal distortion, before the imagery stops being worth
flying.

Two versions of that question have to be answered separately, and conflating them is
the classic error:

1. **The trade.** How do Strehl, MTF at Nyquist, ensquared energy, RER and NIIRS move
   as total WFE RMS grows from 0 to 0.25 waves? This defines where the cliff is.
2. **The as-built.** Tom's current design has a *specific* Zernike decomposition —
   12 terms exported from Zemax. Where does that particular prescription sit against
   the budget, and does its *shape* matter, or only its RMS?

The second question is the one a scalar sweep cannot answer on its own, and the one
this scenario exists to demonstrate. A single RMS number is a summary statistic of a
pupil; two pupils with identical RMS and different modal content produce different
point-spread functions.

## The inputs, and why they are what they are

| Quantity | Value | Why |
|---|---|---|
| Aperture diameter | 40 cm ( = 0.400 m) | Tom's design. |
| Focal length | 400 cm ( = 4.000 m) | Holds f/10. |
| Central obscuration | 35 % linear | Cassegrain secondary plus its baffle. |
| Optical transmission | 75 % | Two-mirror train plus filter, lumped. |
| Optics temperature | 20 °C ( = 293.15 K) | Not load-bearing in the VNIR; the scene is solar-reflective. |
| WFE reference wavelength | 633 nm ( = 0.633 µm) | HeNe. Every interferometric measurement Tom will ever take is referenced here. |
| Spectral band | 500 – 800 nm ( = 0.500 – 0.800 µm) | The VNIR passband; band centre 650 nm. |
| Pixel pitch | 10.0 µm | The CCD. |
| Quantum efficiency | 85 % | Detector, band-average. |
| Dark current | 3.0 e-/s | Cooled CCD. |
| Read noise | 5.0 e- RMS | Detector. |
| Full well | 100 000 e- | Detector. |
| Integration time | 2.0 ms | A short VNIR dwell. |
| Orbit altitude | 500 km | Sets GSD 1.25 m at 2.5 µrad IFOV. |
| Target / background reflectance | 0.15 / 0.10 | A low-contrast land scene. |
| Solar zenith angle | 30 deg | A good-illumination reference case. |
| Atmosphere | `simple`, visibility 23 km, PWV 20 mm | Standard clear column. |

The derived numbers the script prints before it starts are the ones to hold onto:
**GSD 1.25 m, IFOV 2.5 µrad, Airy disk 15.9 µm (1.59 pixels), and $Q = 0.650$.**

$Q$ — the ratio of optical cutoff to detector sampling — is 0.650, which means this
system is **undersampled**. The pixel is larger than the Airy core. That single fact
determines the shape of everything below: the detector aperture MTF, not the optics,
is what limits MTF at Nyquist, and adding wavefront error eats into a budget the
detector has already spent most of.

**Tom's Zernike prescription** arrives as `inputs/tom_zernike_zemax.txt`, the Zemax
"Zernike Standard Coefficients" text export, in Noll indexing at the 633 nm reference:

| Index | Name | Coefficient [waves] |
|---|---|---:|
| Z4 | Defocus | 0.020 |
| Z5 | Astigmatism 0 | 0.015 |
| Z6 | Astigmatism 45 | 0.010 |
| Z7 | Coma Y | 0.025 |
| Z8 | Coma X | 0.018 |
| Z9 | Trefoil Y | 0.005 |
| Z10 | Trefoil X | 0.004 |
| Z11 | Spherical | 0.030 |
| Z12 | 2nd Astigmatism 0 | 0.003 |
| Z13 | 2nd Astigmatism 45 | 0.002 |
| Z14 | 2nd Coma Y | 0.002 |
| Z15 | 2nd Coma X | 0.001 |
| **RSS total** | | **0.0513** |

Spherical, coma-Y and defocus dominate. Because Noll-normalised coefficients *are*
per-mode RMS contributions, the total RMS is their root-sum-square — which is also
what makes the allocation below a clean RSS budget rather than a linear one.

## The scripted path

One script does the whole study:

```bash
S=scenarios/05_tom_optical_designer/5.1_wfe_budget_allocation
PYTHONPATH=src python $S/scripts/run_wfe_budget_trade.py
```

### Step 1 — Parse the Zemax export, and refuse to run on a mismatch

```python
zemax = load_zemax_zernike(ZEMAX_FILE)

# Cross-check: workbook sheet vs Zemax export must agree.
sheet_coeffs = {idx: coeff for idx, _, coeff in zernike_data}
if sheet_coeffs != zemax.zernike_coeffs:
    raise ValueError(
        "Workbook 'Zernike Coefficients' sheet disagrees with the Zemax "
        f"export: sheet={sheet_coeffs}, zemax={zemax.zernike_coeffs}"
    )
```

`radiant.io.zemax_zernike.load_zemax_zernike` handles the parts of a real Zemax
export that break naive parsers: UTF-16 and UTF-8 encodings, Noll-index validation,
and capture of the reference wavelength from the file's own header rather than from a
hard-coded assumption.

The cross-check against the workbook sheet is the more interesting line, and it is
worth stealing. Tom has the same twelve numbers in two places — the optical export
and the systems-engineering workbook. The script compares them and raises rather than
proceeding on whichever it happened to read second. Two sources of truth for one
quantity is a latent defect; making the script assert their agreement converts it
into a loud one.

### Step 2 — Express the allocation as an error budget

```python
WFE_ALLOCATION_WAVES = 1.0 / 14.0

wfe_budget = ErrorBudget(
    name="wfe",
    unit="waves @ 633 nm",
    contributors=tuple(
        BudgetContributor(name=f"Z{idx} {zern_names.get(idx, '')}".strip(), value=coeff)
        for idx, coeff in sorted(zemax.zernike_coeffs.items())
    ),
    allocation=WFE_ALLOCATION_WAVES,
)
```

The allocation is $\lambda/14 = 0.0714$ waves, the Maréchal criterion for
"diffraction-limited" (Strehl $\approx 0.80$). `radiant.api.ErrorBudget` does the RSS,
the margin, the per-contributor variance shares, and — the number Tom actually needs
— `remaining_allocation()`.

### Step 3 — Sweep the scalar RMS

```python
for wfe_rms in wfe_values:
    config["optics"] = {**base_config["optics"], "wfe_rms_waves": wfe_rms}
    sensor = Sensor.from_dict(config)
    r = sensor.evaluate()

    strehl = r.metrics.get("strehl", 0.0)
    mtf_nyq = r.metrics.get("mtf_at_nyquist", 0.0)
    ee_1x1 = r.metrics.get("ee_1x1", 0.0)
    rer = r.metrics.get("rer", 0.0)
    niirs = r.metrics.get("niirs", 0.0)
```

Thirteen sweep points from 0 to 0.25 waves. RADIANT expands the scalar RMS over a
fixed, deterministic equal-RMS low-order Zernike set (Noll Z4–Z11) to build the
aberrated pupil.

### Step 4 — Run the actual prescription, in Zernike mode

The scalar sweep is the *trade*. The as-built *truth* is a run of Tom's real
coefficients:

```python
wfe_zernike = zemax.to_wavefront_error()

config_zern["optics"] = {**base_config["optics"], "wfe_rms_waves": 0.0}
session_zern = RadiantSession(wavelength_um=wl_grid)
params_zern = session_zern.default_params()
load_config(config_zern, params_zern)
params_zern.resolve()
r_zern = session_zern.run(
    params_zern,
    extra_stage_outputs={"optics_config": {"wavefront_error": wfe_zernike}},
)

# Scalar-RMS run at exactly the same total RMS for a like-for-like pair.
config_scal["optics"] = {**base_config["optics"], "wfe_rms_waves": total_rms}
r_scal = Sensor.from_dict(config_scal).evaluate()
```

This is the architectural pattern for any file-derived object in RADIANT. Stages do
not read files; the IO layer builds the object and the API injects it into the chain
before execution, here through `RadiantSession.run(extra_stage_outputs=...)` into
`optics_config`. Note also that `wfe_rms_waves` is set to **0.0** on the Zernike run —
the scalar parameter and the injected prescription are two routes to the same pupil
phase, and stacking them would double-count the aberration.

The paired scalar run at exactly `total_rms` is what makes the comparison meaningful:
same RMS, different modal mix, everything else identical.

### Real output — the sweep

```
       WFE    Strehl     MTF@Nyq   EE(1x1)   EE(3x3)       RER       SNR     NIIRS
   [waves]      [--]        [--]      [--]      [--]      [--]      [--]      [--]
  --------  --------  ----------  --------  --------  --------  --------  --------
     0.000    1.0000      0.2546    0.4288    0.8833    0.6114     120.2      6.14
     0.020    0.9879      0.2488    0.4242    0.8805    0.6079     120.2      6.13
     0.040    0.9534      0.2327    0.4107    0.8720    0.5966     120.2      6.11
     0.060    0.9011      0.2101    0.3903    0.8581    0.5786     120.2      6.06
     0.071    0.8671      0.1968    0.3770    0.8484    0.5665     120.2      6.03
     0.080    0.8402      0.1862    0.3654    0.8394    0.5556     120.2      6.00
     0.100    0.7794      0.1663    0.3384    0.8167    0.5295     120.2      5.93
     0.120    0.7210      0.1530    0.3117    0.7912    0.5022     120.2      5.86
     0.140    0.6750      0.1450    0.2866    0.7640    0.4751     120.2      5.78
     0.160    0.6334      0.1383    0.2637    0.7367    0.4492     120.2      5.70
     0.180    0.5953      0.1296    0.2428    0.7101    0.4248     120.2      5.62
     0.200    0.5589      0.1178    0.2234    0.6852    0.4018     120.2      5.54
     0.250    0.4681      0.0863    0.1783    0.6300    0.3490     120.2      5.33
```

### Real output — the budget

```
=== WFE Error Budget (ErrorBudget, Gaps 23+28) ===
Error budget: wfe [waves @ 633 nm]
Contributor                           RMS    Share
Z11 Spherical                        0.03   34.2%
Z7 Coma Y                           0.025   23.7%
Z4 Defocus                           0.02   15.2%
Z8 Coma X                           0.018   12.3%
Z5 Astigmatism 0                    0.015    8.5%
Z6 Astigmatism 45                    0.01    3.8%
Z9 Trefoil Y                        0.005    0.9%
Z10 Trefoil X                       0.004    0.6%
Z12 2nd Astigmatism 0               0.003    0.3%
Z13 2nd Astigmatism 45              0.002    0.2%
Z14 2nd Coma Y                      0.002    0.2%
Z15 2nd Coma X                      0.001    0.0%
RSS total                         0.05131
Allocation                        0.07143
Margin (linear)                   0.02012  within budget
RSS headroom                      0.04969
```

### Real output — the prescription against its scalar twin

```
  Both runs: total WFE RMS = 0.0513 [waves at 633 nm]

  Metric                  Zernike (actual)   Scalar screen           Δ
  ----------------------  ----------------  --------------  ----------
  Strehl [--]                       0.9174          0.9256     -0.0082
  MTF@Nyquist [--]                  0.2246          0.2204     +0.0041
  EE(1x1) [--]                      0.3953          0.3999     -0.0046
  RER [--]                          0.5812          0.5872     -0.0060
  NIIRS [--]                          6.07            6.08     -0.0149
  SNR [--]                           120.2           120.2     +0.0000
```

(The run also prints a Maréchal reference table, a degradation table, a Strehl
comparison, a noise budget, and four figures. The whole thing takes 2.6 s.)

## What the numbers say

**Regime: extended.** The scene is a uniform land surface filling the pixel footprint
completely, so the optics stage classifies it `extended` and every downstream stage
reads that. In the extended regime there is no separable in-pixel background term —
which is why the noise budget below has no `background_shot` row.

### The budget closes, with real headroom

| Quantity | Value [waves at 633 nm] |
|---|---:|
| RSS total (Tom's 12 terms) | 0.0513 |
| Allocation ($\lambda/14$) | 0.0714 |
| Linear margin | +0.0201 |
| **RSS headroom** | **0.0497** |

The two margins are not the same number and the difference is not bookkeeping. The
**linear margin**, 0.0201 waves, is what is left if the next contributor adds
*arithmetically*. The **RSS headroom**, 0.0497 waves, is what is left if it adds *in
quadrature* — which is what independent error sources do:
$\sqrt{0.0714^2 - 0.0513^2} = 0.0497$. Tom can absorb an assembly-plus-thermal
contributor of nearly 0.05 waves RMS, two and a half times what the linear reading
would let him book. Quoting the linear margin to a mechanical engineer under-sells the
design by a factor of 2.5.

The variance-share column tells him where reduction effort pays: spherical alone is
34.2 % of the variance, coma-Y 23.7 %, defocus 15.2 %. The bottom six terms together
are under 2 %. Polishing trefoil is wasted money.

### Tom's design sits comfortably inside diffraction-limited territory

At his actual 0.0513-wave prescription, run in Zernike mode: **Strehl 0.9174**, MTF at
Nyquist 0.2246, RER 0.5812, and $\Delta$NIIRS of −0.07 against perfect optics. The
conventional diffraction-limited threshold is Strehl 0.80; he is well clear of it.

### Shape versus RMS — a smaller effect than it used to be, and worth understanding why

The prescription and its equal-RMS scalar twin now agree closely: $|\Delta|$ of 0.008
in Strehl, 0.004 in MTF at Nyquist, and 0.01 in NIIRS. That is the *expected* answer,
and it is expected because both pupils are now **low-order**. RADIANT's scalar
expansion is a deterministic equal-RMS spread over Noll Z4–Z11, so comparing it with
Tom's spherical-and-coma-dominated set is comparing two low-order pupils at one RMS.
Two such pupils should be near-twins at Strehl 0.92, and they are.

The signs are informative even so: Tom's actual mix sits *slightly below* the
equal-weight expansion in Strehl, EE and RER, and *slightly above* it in MTF at
Nyquist. Concentrating the variance in spherical and coma pulls a little more energy
out of the core than an even spread does, while leaving marginally more mid-frequency
contrast. The gap grows with WFE, and only the Zernike route reproduces
aberration-specific PSF structure — coma's asymmetric flare, spherical's rings — that
no single RMS number can encode. **Use the prescription whenever one exists.**

### SNR does not move, and that is the design insight

SNR is 120.2 at every one of the thirteen sweep points. Wavefront error redistributes
energy within the point-spread function; it does not remove photons from the aperture.
The noise budget is likewise constant:

| Noise term | σ [e- RMS] | Fraction |
|---|---:|---:|
| `signal_shot` | 120.3 | 99.8 % |
| `read_noise` | 5.0 | 0.2 % |
| `quantization` | 0.3 | < 0.1 % |
| `dark_shot` | 0.1 | < 0.1 % |
| **Total (RSS)** | **120.4** | |

Signal 14 468 e-, and $\sqrt{14\,468} = 120.3$: shot-limited, as a bright VNIR scene at
2 ms should be. NIIRS therefore changes with WFE almost entirely through the GIQE-5
RER term ($3.32 \log_{10}\mathrm{RER}$), with the SNR term held fixed. That is the
cleanest possible separation of a spatial effect from a radiometric one, and it means
every NIIRS movement in the sweep table above is attributable to image quality alone.

### Where the cliff is

| Degradation | First sweep point past it | Interpolated crossing |
|---|---|---|
| −0.25 NIIRS | 0.120 waves | ≈ 0.110 waves |
| −0.50 NIIRS | 0.180 waves | ≈ 0.175 waves |
| −1.00 NIIRS | not reached (−0.81 at 0.250) | — |

The script reports the first *sweep grid point* whose NIIRS has fallen past each
threshold; the scenario's `walkthrough.md` quotes the linear interpolation between
bracketing points. Both readings describe the same thirteen rows, and the difference
between them is sweep resolution, not disagreement.

The practical reading for Tom: the $\lambda/14$ allocation of 0.0714 waves costs him
0.11 NIIRS, which is nothing. He could relax the allocation to roughly 0.10 waves and
still be inside a quarter-NIIRS degradation. Whether he *should* is a separate
argument — Strehl at 0.10 waves is 0.78, just under the diffraction-limited line, and
"diffraction-limited" is a phrase that appears in requirements documents.

Note also that the spatial columns now **decouple**. From 0 to 0.25 waves, MTF at
Nyquist falls 66.1 % while RER falls only 42.9 %. A low-order aberration attacks
mid-frequency contrast harder than it attacks edge slope. A model that degraded every
spatial metric by one common factor could not produce that spread, and the fact that
RADIANT does is a check on the pupil-domain implementation: all five spatial metrics
come off the same `EffectivePSF`, so their *relative* behaviour is physics rather than
parameterisation.

## Two caveats the run itself raises

**Annular Zernikes are not implemented.** The very first line of output is a warning:

```
UserWarning: Obscuration ratio 0.35 > 0.30: standard Zernike polynomials are NOT
orthogonal on an annular pupil. Individual coefficient interpretations may be
misleading. Annular Zernikes (Mahajan 1981) are not implemented.
```

This is honest and it matters for the *interpretation* of individual coefficients, not
for the total. On a 35 %-obscured pupil the standard circular Zernike basis is no
longer orthogonal, so the variance shares in the budget table above are approximate
attributions rather than an exact decomposition. The RSS total and the resulting
pupil phase are unaffected; what is affected is the claim "spherical is 34.2 % of the
variance", which on an annulus mixes slightly with defocus and the higher spherical
terms. Tom should read the ranking as a priority ordering, not as an exact accounting.

**The Maréchal approximation is a reference, not the model.** The run prints a
side-by-side Maréchal-versus-RADIANT Strehl table. They diverge past about 0.1 waves —
at 0.25 waves, Maréchal gives 0.085 against RADIANT's 0.468. Two separate effects
produce that. Maréchal's $S = \exp[-(2\pi\,\mathrm{OPD_{rms}}/\lambda)^2]$ is a
small-aberration expansion that is simply invalid below Strehl $\approx 0.3$; and the
table's Maréchal column is evaluated at the 633 nm reference while RADIANT works at
the 650 nm band centre, where the same physical OPD is a smaller fraction of a wave.
RADIANT's reported Strehl is the degraded-PSF peak over the diffraction-limited
reference peak — a computed ratio, not a closed-form approximation — and it is the one
to quote.

## The takeaway

Tom's 40 cm Cassegrain carries 0.0513 waves RMS of design wavefront error against a
$\lambda/14$ (0.0714-wave) allocation. It closes with **0.0497 waves of RSS headroom**
for assembly and thermal contributors — the number to hand the mechanical team, not the
0.0201-wave linear margin. At that prescription the telescope delivers Strehl 0.9174,
MTF at Nyquist 0.2246 and a NIIRS cost of 0.07, which is negligible.

The budget's cliff is much further out than the allocation: a quarter-NIIRS
degradation does not arrive until roughly 0.11 waves. And the modal *shape* of the
error, at this RMS, is worth about 0.01 NIIRS — small, but the only way to know that
was to run the actual prescription rather than trust the scalar summary.

Numbers in this chapter come from a re-run of the committed runner and reproduce the
scenario's `walkthrough.md` tables exactly, to every printed digit.

One documentation defect surfaced in the re-run and is recorded rather than quietly
fixed: the script's closing "Limitations" block still describes the scalar sweep as
using "a random phase screen". It does not — the scalar expansion is now the
deterministic equal-RMS Z4–Z11 set, which is why the prescription and its twin agree
as closely as they do. The walkthrough's tables and discussion are current; the
runner's printed prose is one revision behind.

## The same study in the GUI

The scenario ships a GUI-openable baseline of this telescope,
`inputs/5.1_wfe_budget_allocation.gui.yaml`, with its headline metrics snapshotted in
`.gui.expected.json`. Opening it puts the 40 cm f/10 Cassegrain in the window with
`optics.wfe_rms_waves` as an editable field, so the sweep above can be walked by hand
one point at a time with the Performance workspace's Spatial/MTF group updating as you
go — which is a genuinely better way to build intuition for the Strehl-versus-MTF
decoupling than reading the table. The scenario's `gui_workflow.md` specifies what a
complete WFE workspace would add: a WFE input-mode selector (Scalar RMS / Zernike /
OPD map), an **Import from Zemax** button calling the same `load_zemax_zernike` the
script uses, a live table of the parsed Z4–Z15 terms with variance shares, and an
`ErrorBudget` panel showing allocation, linear margin and RSS headroom with a tooltip
explaining why the quadrature headroom exceeds the linear margin. Zernike mode is
functional through API-level injection today, as the script shows; what it lacks is a
configuration-surface route, so the GUI would perform the injection on the analyst's
behalf.
