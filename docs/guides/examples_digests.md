# Scenario Digest Compendium

The eight chapters before this one walk eight scenarios at full depth — the inputs,
the run, the figures, the physics argument, and the caveats. That depth costs roughly
fifteen pages apiece, and there are fifty-one scenarios in the repository. Covering
them all that way would produce a four-hundred-page volume in which the interesting
cases were buried.

The owner's ruling (Q3, 2026-09-16) was **total coverage at tiered depth**: every
scenario appears, eight at full depth, four in the flagship-validation chapter, and
the rest here as digests. A digest is one to two pages and answers five questions —
what was the mission, what went in, what came out, which radiometric regime was in
force, and what the analyst should take away — plus a pointer to the scenario folder
where the full narrative, the figures, and the gap list live.

## How to read a digest

Every digest carries the same six parts, in the same order:

- **Mission setup** — two or three sentences of context: who is asking, what they are
  looking at, from where.
- **Key inputs** — a compact table of the parameters that decide the answer, each with
  its unit. It is not the full configuration; the scenario folder holds that.
- **Headline results** — the numbers the scenario exists to produce, quoted from the
  committed `walkthrough.md` with their units. **No digest re-runs anything.** Where a
  walkthrough contradicts itself, or is missing a number a digest would want, the
  digest says so in one clause rather than papering over it.
- **Regime** — `extended`, `sub_pixel`, or `point_source`, named with one clause on
  why the scene classifies that way. Several scenarios never run the chain at all
  (pure geometry, pure sequence models); those say so.
- **Takeaway** — one or two sentences: the conclusion an engineer would carry into a
  design review.
- **Where to go deeper** — the scenario folder, and whether a GUI-openable baseline
  (`inputs/<slug>.gui.yaml`) ships with it. Where one does, the study can be opened
  through `File → Open YAML` and re-run in the GUI rather than from a script.

## A note on vintage

RADIANT's physics has moved under these scenarios repeatedly — the atmosphere model
alone has taken a dozen corrections since the first executions, each one re-baselining
the affected walkthroughs. The numbers below are the **committed walkthrough values at
their stated vintage**, not a fresh run. Most walkthroughs carry an italic refresh note
naming the cleanup unit responsible for the last movement and its size; where that
matters to the reading of a result, the digest repeats it. A number here that
disagrees with a run you do today means the scenario has been re-baselined since, and
the scenario's own `walkthrough.md` is the authority.

The scenarios are grouped by persona in catalog order. Persona 8 is not a persona at
all — it is a supplementary folder of tool demonstrations added outside the closed
thirty-five-scenario catalog, and it is included here for the same reason as
everything else: total coverage.

---

## Persona 1 — Sarah, Systems Engineer

Sarah sizes payloads for proposals. Her scenarios are aperture-and-altitude trades
where the answer has to be defensible to a customer, and the recurring theme is that
the sizing basis matters more than the sizing calculation.

### 1.2 — VNIR Pan Imager: GSD vs Aperture vs Altitude

**Mission setup.** A sun-synchronous panchromatic imager must hold a 0.5 m ground
sample distance while meeting an SNR spec. Holding GSD fixed as the orbit rises forces
a longer focal length, hence a higher f-number, hence less irradiance per pixel — so
aperture and altitude are coupled, and the SNR-spec contour runs diagonally across the
trade space. This is the first consumer of `radiant.core.solar_geometry`, which turns
the orbit's LTAN plus target latitude and date into the solar zenith angle.

**Key inputs.**

| Quantity | Value |
|---|---|
| Held GSD | 0.5 m (nadir) |
| Pixel pitch | 6.5 µm |
| Band | 450 – 700 nm (pan) |
| Aperture sweep | 20 – 80 cm |
| Altitude sweep | 400 – 600 km |
| Orbit / latitude | 10:30 LTAN sun-sync, 35 °N |
| SNR spec | 50 |
| Detector QE | Si CCD curve, digitized from a datasheet plot, band-averaged over 450–700 nm |

**Headline results.** At the 50 cm / 500 km reference design, winter SNR is **40.6**
(solar zenith 62.2°) against a summer 70.8 (zenith 22.7°) — a **43 % seasonal swing**,
and the winter case **fails** the SNR = 50 spec. The aperture ladder at 500 km reads
SNR 11.8 at 20 cm, 40.6 at 50 cm, 68.7 at 80 cm; the sampling parameter
$Q = \lambda\,(f/\#)/p$ runs 2.88, 1.15, 0.72 across the same three. Minimum aperture to
hold spec climbs **50 cm at 400 km → 75 cm at 600 km**. The 20 cm design is
diffraction-limited everywhere (diffraction ground spot 1.4–2.1 m against a 0.5 m
pixel); the 80 cm design is detector-limited; 50 cm straddles the crossover.

**Regime.** `extended` — the sunlit surface fills the pixel, so scene radiance *is* the
background, EE_box is not applied, and the point-source machinery is unused.

**Takeaway.** Size to the worst-case season, not the annual mean: a 50 cm aperture that
looks compliant on a mean-illumination chart misses spec every winter. And buying fine
GSD with a small aperture is wasted money — below about 50 cm the optics, not the
pixel, set the resolution.

**Where to go deeper.** `scenarios/01_sarah_systems_engineer/1.2_vnir_gsd_aperture_altitude/`.
A GUI baseline ships.

### 1.3 — Dual-Band MWIR/LWIR Wildfire Detection

**Mission setup.** Sarah must pick a band for a wildfire mission: a 5 m² hotspot at
~600 K against a 300 K conifer canopy, seen from a 10 km airborne platform. The vendor
offers MWIR (3.5–5.0 µm, 80 K) and LWIR (8–12 µm, 60 K) HgCdTe; the canopy emissivity
arrives as a JPL/NASA ASTER-library text file. The band decision is the deliverable.

**Key inputs.**

| Quantity | Value |
|---|---|
| Fire / background | 600 K hotspot, 5 m²; 300 K conifer canopy |
| Background emissivity | ASTER curve — ε = 0.9530 (MWIR), 0.9821 (LWIR) |
| Platform / optics | 10 km altitude, 2.5 cm f/2, 20 µm pixels |
| GSD / fill fraction | 4.0 m → 16 m² footprint; hotspot fills 0.31 |
| Fire-mode integration | 5 µs (MWIR), 25 µs (LWIR) |
| Scene clutter | 3 % of background (σ) |

**Headline results.** At 600 K: MWIR pixel signal 228,529 e⁻ against LWIR 2,962,748 e⁻;
contrast 220,998 e⁻ vs 1,217,206 e⁻; total noise 541.6 e⁻ RMS vs 52,411.7 e⁻ RMS, of
which clutter is 225.9 and 52,366.3 e⁻ RMS respectively. **SCNR including clutter:
408.0 (MWIR) vs 23.2 (LWIR)** — a 17× advantage. NEDT runs the other way, 229.9 mK
(MWIR) vs 165.4 mK (LWIR), both carrying the Gap 43 single-wavelength caveat. Over a
400–1200 K fire sweep, MWIR holds $P_d \approx 1$ throughout while **LWIR misses the
400 K smolder outright** (SCNR 1.1, $P_d = 0.000$ against a 4.75σ threshold). MWIR
saturates first, at ≈1200 K and ~98 % of the 4 Me⁻ well. Band-integrated radiance
contrast at 600 K is nearly equal — 373.6 W/m²/sr (MWIR) vs 382.0 W/m²/sr (LWIR).

**Regime.** `sub_pixel` — the 5 m² hotspot fills 31 % of the 16 m² pixel footprint, so
the regime override keeps the in-pixel background photons and the scene clutter in the
budget.

**Takeaway.** ΔL alone would call the two bands equivalent; the detector-level
comparison separates them by a factor of seventeen, because LWIR's 3 % clutter rides on
a background an order of magnitude brighter. **MWIR for fire detection, LWIR for
ambient-scene mapping** — NEDT is the wrong figure of merit for the former.

**Where to go deeper.** `scenarios/01_sarah_systems_engineer/1.3_dual_band_mwir_lwir/`.
A GUI baseline ships.

### 1.4 — TDI Pushbroom Optimization: Line Rate vs SNR

**Mission setup.** A VNIR panchromatic pushbroom imager on a 500 km sun-synchronous
orbit: ground velocity caps the per-line integration at ~0.2 ms, so time-delay
integration is what builds SNR. How many TDI stages, and where does the well stop the
gain? (The concept started MWIR; a 300 K thermal scene saturates at $N_{TDI}=1$, which
is why TDI is fundamentally a VNIR technology.)

**Key inputs.**

| Quantity | Value |
|---|---|
| Aperture / focal length | 25 cm / 250 cm (f/10) |
| Band | 500 – 850 nm |
| Pixel pitch / QE | 7.0 µm / 80 % |
| Read noise / FWC | 15 e⁻ RMS / 60,000 e⁻ |
| Ground velocity / line period | 6954.2 m/s / 0.2013 ms |
| GSD / Q | 1.40 m / 0.964 (undersampled) |
| TDI mode / misalignment | analog / 0.1 pixel per stage |
| $N_{TDI}$ sweep | 1 – 128 |

**Headline results.** Per-line signal 732 e⁻. SNR climbs 23.7 ($N=1$) → 107.2 ($N=16$)
→ 216.0 ($N=64$) and **plateaus at 244.5** once the signal clips at the 60,000 e⁻ well
— because there is no separable background photon term in an extended reflective
scene, the noise caps at $\sqrt{FWC} \approx 245$ e⁻ too, so SNR flattens rather than
falling. Saturation onset is $N_{TDI}=96$ (100 % fill); $N_{TDI}=64$ runs at 78.1 %.
NIIRS rises 4.62 → 6.21 over the same span (extrapolated GIQE-5 — the configuration is
outside the calibration envelope, CU-166). TDI misalignment MTF falls 0.9959 → 0.5508
from $N=1$ to $N=128$ as registration error accumulates as $\sqrt{N}$. A calibration
variant (Gap 120) re-runs the sweep with a one-point NUC and 2 % pre-correction PRNU:
the correlated floor caps SNR near **56** by $N_{TDI} \approx 16$–32, which **changes
the design answer qualitatively** from "96 stages, SNR 245."

*Internal inconsistency worth knowing:* the sweep table gives NIIRS 6.12 at
$N_{TDI}=64$, while the Physics Discussion quotes 6.05 for the same point and twice
names $N_{TDI}=64$ as the saturation onset the refreshed table puts at 96 — stale prose
against a refreshed table.

**Regime.** `extended` — a reflective ground scene fills the pixel, which is exactly
why the saturation behaviour is a plateau and not a cliff.

**Takeaway.** Thirty-two stages is the conservative sweet spot (NIIRS 5.89, 39 % well)
— but only if the calibration residual is ignored. With a realistic one-point NUC the
correlated floor, not the well, sets the answer, and stages past ~16–32 buy MTF loss
instead of SNR.

**Where to go deeper.** `scenarios/01_sarah_systems_engineer/1.4_tdi_pushbroom_optimization/`.
A GUI baseline ships.

### 1.5 — Obscured Aperture and Spider Vanes

**Mission setup.** Sarah is trading a Cassegrain telescope: how much do the central
obscuration and the struts supporting the secondary cost, against an ideal unobstructed
aperture, and how does the cost grow with strut width? This is the first consumer of
RADIANT's spider-vane pupil masking (`optics.n_spiders`, `optics.spider_width_m`,
`optics.spider_angle_deg`).

**Key inputs.**

| Quantity | Value |
|---|---|
| Aperture / f-number | 50 cm / f/12 |
| Central obscuration | ε = 0.30 (linear) |
| Spider arms | 4, 3 cm wide (baseline); swept 0 – 5 cm |
| Band / altitude | VNIR pan, 500 km |

**Headline results.** Three-configuration comparison: unobstructed SNR 75.1, EE_3×3
0.864, RER 0.582, MTF at Nyquist 0.228; obscured-only 71.5 / 0.763 / 0.517 / 0.207;
obscured plus four 3 cm spiders **66.8 / 0.657 / 0.485 / 0.221**. Going from the ideal
aperture to the full Cassegrain costs **11.1 % of SNR and 24 % of the 3×3 encircled
energy**. The strut-width sweep at ε = 0.30 takes SNR 71.5 → 63.5 and EE_3×3
0.763 → 0.607 across 0 → 5 cm; the 3 cm baseline costs ~14 % of the encircled energy
against strut-free supports. **Strehl is 1.000 in every row** — it is a wavefront-error
metric measured against a reference PSF carrying the same aperture geometry, so
obscuration and vanes are common-mode and cancel exactly.

**Regime.** `extended` — a sunlit surface fills the pixel; the spatial metrics, not the
regime, are the point here.

**Takeaway.** A designer judging this telescope by Strehl alone would miss the entire
obscuration and vane cost. EE and RER are the monotone degradation signals; MTF at
Nyquist is non-monotonic across the three apertures (0.228 → 0.207 → 0.221) because
thin high-contrast struts redistribute rather than uniformly suppress the modulation.

**Where to go deeper.** `scenarios/01_sarah_systems_engineer/1.5_obscured_aperture_spider_vanes/`.
A GUI baseline ships. (The walkthrough's aperture-comparison table carries a duplicated
header row — a Markdown artifact, not a second data set.)

### 1.6 — MWIR Point-Source Space Domain Awareness

**Mission setup.** A space-based MWIR sensor in a 700 km orbit must detect an
**unresolved** satellite at 729 km slant range. The target's angular extent is far below
one pixel IFOV, so it lands inside a single PSF: there is no surface filling a pixel,
and the right radiometric quantity is radiant intensity $I(\lambda)$ [W/sr/µm], not a
surface radiance times an area.

**Key inputs.**

| Quantity | Value |
|---|---|
| Aperture / f-number | 0.30 m / f/5 |
| Band / integration | 3.5 – 5.0 µm / 10 ms |
| Pixel pitch | 15 µm (InSb-class) |
| Target intensity | graybody: 290 K, 8 m² emitting area, ε = 0.85 |
| Range | `geometry.target_range_m` = 729,287 m (explicit) |

**Headline results.** Signal **20,939 e⁻**, **SNR 20.32**, **detection range (SNR = 6)
1346.7 km**, sampling $Q$ at band centre 1.42. Signal scales linearly with emitting
area, emissivity and intensity, and inverse-square with range — the point-source camera
equation. The blackbody point-intensity input reproduces an equivalent hand-built
intensity CSV exactly.

**Regime.** `point_source`, locked by `source.regime_override`. The chain reads range
from `geometry.target_range_m` explicitly rather than deriving it from altitude and
zenith, which is why the scenario sets it.

**Takeaway.** For an unresolved object, declare intensity. Setting a surface
temperature and emissivity with zero area does *not* define a point source — it raises
an actionable error steering the user toward area, which is the wrong direction. The
GUI does not yet expose the point-intensity inputs.

**Where to go deeper.** `scenarios/01_sarah_systems_engineer/1.6_mwir_point_source_sda/`.
**No GUI baseline ships** for this scenario — which is also why it was missed by one
physics-refresh sweep and carried a stale SNR for a month.

---

## Persona 2 — Mike, Detector Engineer

Mike evaluates focal planes. His scenarios are noise budgets, ROIC architecture trades,
and calibration floors — the questions where a vendor datasheet number and a fielded
system's behaviour diverge.

### 2.2 — 1/f Noise Corner Frequency in an LWIR Staring Array

**Mission setup.** A 640×512 LWIR HgCdTe staring array with a measured flicker
coefficient $K = 2.5\times10^{4}$ e⁻² and a corner frequency $f_c = 200$ Hz, operated at
30, 60 and 120 Hz. How much does 1/f noise cost in NEDT, and how should the flicker
band limits be set at each frame rate?

**Key inputs.**

| Quantity | Value |
|---|---|
| Optics | 15 cm Ge objective, f/2, 85 % transmission, 20 °C |
| Band | 8.0 – 10.0 µm |
| Detector | 24 µm HgCdTe, QE 55 %, dark 5×10⁵ e⁻/s, read 350 e⁻ RMS |
| FWC / integration | 20 Me⁻ / 100 µs (well-limited) |
| Flicker band | $f_{low}$ = frame rate, $f_{high} = 1/(2 t_{int})$ = 5000 Hz |
| Atmosphere | `exo` — short range, negligible path |

**Headline results.** $\sigma_{1/f} = \sqrt{K \ln(f_{high}/f_{low})}$ gives 357.6, 332.5
and 305.4 e⁻ RMS at 30, 60 and 120 Hz — a 4× frame-rate change moves it only 15 %,
because the dependence is logarithmic. NEDT with 1/f is **27.8 / 27.7 / 27.7 mK**
against 27.4 mK without: a **0.3–0.4 mK, ~1 % penalty**. The 60 Hz noise budget reads
`signal_shot` 2105.0 e⁻ RMS (92.5 % of variance), quantization 352.2, read 350.0,
flicker 332.5, dark 7.1, for an RSS total of 2188.2 e⁻ RMS. Sweeping $f_{low}$ from
1 Hz to 500 Hz moves NEDT only 28.00 → 27.55 mK. **RADIANT overestimates
$\sigma_{1/f}$ by 64–170 %** because it integrates $K/f$ across the full band instead of
capping at $f_c$ — capped values would be 217.8 / 173.5 / 113.0 e⁻ RMS. That is an open
gap, stated plainly in the walkthrough.

**Regime.** `extended` — the whole-FOV LWIR radiance field is one scene, so there is no
separate `background_shot` term (ADR-0002 Decision #13) and `signal_shot` carries it.

**Takeaway.** In a background-limited LWIR system 1/f noise is buried: the photon shot
noise from a 293 K background swamps it. Mike does not need to negotiate the flicker
spec. It would matter in read-noise-limited systems, below ~10 Hz frame rates, or with
$K > 10^6$ e⁻² — none of which apply here.

**Where to go deeper.** `scenarios/02_mike_detector_engineer/2.2_1f_noise_corner_frequency/`.
A GUI baseline ships.

### 2.3 — IPC Characterization: How Much MTF Loss Is Tolerable?

**Mission setup.** Five HgCdTe MWIR samples from one wafer lot, each with a different
inter-pixel capacitance — a parasitic coupling that leaks charge to the four nearest
neighbours after photon conversion. Mike has lab MTF and ensquared-energy measurements
on all five and needs to know how much IPC the system can tolerate.

**Key inputs.**

| Quantity | Value |
|---|---|
| Optics | 30 cm aperture, f/4, 72 % transmission |
| Detector | 18 µm pitch, QE 72 %, dark 50 e⁻/s |
| Geometry | 500 km LEO, nadir; 310 K ground scene, 295 K background |
| IPC sweep | 0 – 5 % per-neighbour coupling, 51 steps |
| Requirements | MTF at Nyquist ≥ 0.15, EE 1×1 ≥ 0.60, SNR ≥ 100 |

**Headline results.** Baseline (no IPC): MTF at Nyquist **0.2668**, SNR **782.84**,
EE 1×1 **0.4141**, GSD 7.50 m, $Q$ 0.944, NEDT 38.1 mK, NIIRS 4.82 (extrapolated,
CU-166), Strehl 1.000. **The binding constraint is EE 1×1, and it fails at baseline**
(0.4141 against a 0.60 requirement) before any IPC is applied; the MTF requirement is
met comfortably across the whole 0–5 % range. RADIANT's native IPC convolution now
tracks the analytic form $MTF_{IPC}(f_{Nyq}) = 1 - 4\alpha$ to within rounding — at
α = 5 %, native 0.2139 against analytic 0.2134, Δ 0.0005. Against the five lab samples,
the model predicts higher MTF at low IPC (Δ = +0.126 at 1.2 %, +0.092 at 1.8 %) and
slightly lower at the highest (Δ = −0.020 at 3.5 %), the gap narrowing monotonically
and crossing zero near 3 % coupling.

**Regime.** `extended` — the 310 K ground scene fills the pixel, so the background
temperature enters only the contrast-SNR calculation.

**Takeaway.** Engineers evaluating IPC reach for MTF; here the tighter requirement is
ensquared energy, and the vendor's typical IPC specification does not meet it. **IPC
does not affect SNR at all** — charge is redistributed, not destroyed — so the whole
cost is spatial.

**Where to go deeper.** `scenarios/02_mike_detector_engineer/2.3_ipc_impact_on_mtf/`.
A GUI baseline ships.

### 2.4 — Persistence Characterization: Bright-Source Recovery

**Mission setup.** After imaging a hot 800 K calibration source, how long does a
Type-II superlattice detector's persistence ghost linger, and what does it do to the
scene that follows? First consumer of the multi-frame model
`radiant.detector.persistence_sequence`.

**Key inputs.**

| Quantity | Value |
|---|---|
| Prior bright exposure | 150,000 e⁻ |
| Current scene | 20,000 e⁻ |
| Residual fraction $f$ (frame 1) | 1.5 % |
| Trap time constant τ | 50 ms |
| Frame period | 16.67 ms (60 Hz) |
| Gain (1 LSB) | 100 e⁻/DN |

**Headline results.** Residual decays as
$\text{residual}(n) = \text{prior} \cdot f \cdot e^{-(n-1)\Delta t/\tau}$: 2250 e⁻
(22.5 LSB) in frame 1, 828 e⁻ (8.3 LSB) at frame 4, 218 e⁻ (2.2 LSB) at frame 8, 11 e⁻
(0.1 LSB) at frame 17. **Frames to clear below 1 LSB: 11**, about 183 ms of dead time.
Persistence *shot* noise is small — 47.4 e⁻ RMS in frame 1 against 300 e⁻ read noise —
so scene SNR barely moves, 59.0 → 58.4 (−1 %).

**Regime.** No chain regime applies: this is a closed-form temporal sequence
calculation with no atmosphere, optics or chain radiometry in the loop.

**Takeaway.** **The bias is the problem, not the noise.** A 22-LSB ghost image of the
calibration source is false structure a detection algorithm will flag as real, and
unlike random noise it does not average away — the only remedies are waiting out the
eleven frames or subtracting a modelled ghost.

**Where to go deeper.** `scenarios/02_mike_detector_engineer/2.4_persistence_bright_source/`.
**No GUI baseline ships.**

### 2.5 — Well Capacity Optimization: Integration Time vs Dynamic Range

**Mission setup.** A MWIR HgCdTe FPA (640×512, 15 µm pitch, 2 Me⁻ well) in an f/2
ground-based surveillance system looks at a scene containing both 200 K cold sky and
1500 K jet exhaust. Mike needs one integration time that gives SNR ≥ 10 on the cold
target without saturating on the hot one.

**Key inputs.**

| Quantity | Value |
|---|---|
| Aperture / focal length | 20 cm / 40 cm (f/2) |
| Band | 3.5 – 5.0 µm |
| Detector | QE 72 %, dark 100 e⁻/s, read 20 e⁻ RMS, FWC 2.0 Me⁻ |
| ADC / gain | 14 bit / 130 e⁻/DN |
| Sweep | 50 log-spaced $t_{int}$, 1 µs – 50 ms × 10 scene temperatures (200 – 1500 K) |
| Requirements | SNR ≥ 10 at 200 K; ≤ 70 % fill on hot targets; 90 % absolute limit |

**Headline results.** SNR ≥ 10 on the 200 K target requires **$t_{int} \geq 103.2$ µs**
(565 e⁻, SNR 11.6). At that integration the hottest scene staying under 90 % well fill
is **400 K**; at 1 ms it has fallen to 300 K, barely above ambient. **1000 K and 1500 K
saturate even at 1 µs.** The 200–1500 K dynamic range is therefore physically
impossible in a single integration — a 1500 K blackbody radiates ~389× more in-band
power than a 200 K one. The 1 ms noise budget at 200 K reads `signal_shot` 74.0 e⁻ RMS
(75.2 % of variance), quantization 37.5 (19.3 %), read 20.0 (5.5 %), RSS 85.3 e⁻ RMS;
at 400 K `signal_shot` is 1414.2 e⁻ RMS and 99.9 % of the variance.

**Regime.** `extended` — one radiance field, so no separate `background_shot` term. The
walkthrough flags `nearfield_shot = 0` as a known scalar-mode limitation: warm-optics
self-emission is not modelled, which under-predicts cold-target noise.

**Takeaway.** The requirement is not achievable and the tool says so cleanly. The cold
end is where ROIC choices show up — a quarter of the 200 K noise variance is
quantization plus read noise — while at 400 K the electronics are irrelevant. This
scenario's dead end is what motivates 2.6.

**Where to go deeper.** `scenarios/02_mike_detector_engineer/2.5_well_capacity_optimization/`.
A GUI baseline ships.

### 2.6 — DROIC vs Analog ROIC: Single-Frame HDR

**Mission setup.** Scenario 2.5 ended at a physical wall. A vendor offers a
Senseeker-class digital-pixel ROIC for the same MWIR HgCdTe FPA: in-pixel 16-bit
counters with 4.5 ke⁻ charge-subtraction packets and analog residue readout. What does
that buy at the 1 ms cold-target working point?

**Key inputs.**

| Quantity | Analog | DROIC |
|---|---|---|
| Well / effective well | 2.0 Me⁻ | $2^{16} \times 4500$ = 294.9 Me⁻ |
| Dead-time ceiling (5 MHz × 1 ms × 4500 e⁻) | — | 22.5 Me⁻ |
| Governing bound at 1 ms | charge well | dead time |
| ADC | 14 bit at 130 e⁻/DN | 14-bit residue, 0.275 e⁻/DN |
| Read / counting-chain noise | 20 e⁻ RMS | 20 e⁻ RMS |

Shared: 20 cm f/2 optics, 3.5–5.0 µm, QE 72 %, 15 µm pitch, 1.0 ms integration.

**Headline results.** At 400 K the analog chain **clips** (733.0 % nominal fill,
SNR 1413.6 clipped, NEDT 34.56 mK on a clipped signal) while the DROIC delivers
**SNR 3828.9 at 65.2 % fill and NEDT 12.76 mK** — a 2.7× better NEDT where the analog
part has stopped measuring. In the unsaturated 200–300 K overlap the two are
equivalent: SNR agrees within 0.8 %, NEDT within 0.3 mK, with the DROIC's residue
quantization floor (0.079 e⁻ RMS) actually below the analog ADC's (37.5 e⁻ RMS).
Dynamic range at the matched 200 K point goes **76.3 dB → 97.4 dB (+21.1 dB)**. Above
~450 K the DROIC clips too, with `saturation_mechanism = "dead_time"`.

**Regime.** `extended` — an unresolved-scene radiometric comparison; the interest is
entirely in the readout architecture.

**Takeaway.** **The dead-time ceiling, not the counter, is the DROIC's real limit** —
22.5 Me⁻ is 7.6 % of the 294.9 Me⁻ counter capacity. The 2.5 requirement is still not
met end to end, but the wall moved from 300 K to 400 K; covering 1500 K needs a faster
comparator ($f_{max} \gtrsim 90$ MHz), a larger packet, or up/down mode.

**Where to go deeper.** `scenarios/02_mike_detector_engineer/2.6_droic_vs_analog_hdr/`.
**No GUI baseline ships.**

### 2.7 (calibration-limited NEDT) — Two-Point NUC Floor in an LWIR Starer

*Two distinct scenario folders in persona 02 both carry the number 2.7. They are
disambiguated here by folder name; the collision is tracked as **CU-362**.*

**Mission setup.** The datasheet NEDT of Mike's LWIR staring camera (~25 mK) comes from
the temporal noise budget. Every such system he has fielded is limited instead by the
residual fixed-pattern noise the two-point NUC leaves behind. The Gap 120 calibration
model lets him model the calibration process itself — cal-point placement, detector
nonlinearity, correction decay, and the blackbody source's own uncertainty.

**Key inputs.**

| Quantity | Value |
|---|---|
| Optics / band | 10 cm f/1.5, 8 – 12 µm, 85 % transmission |
| Detector | 12 µm pitch, QE 65 %, dark 5×10⁵ e⁻/s at 60 K, read 350 e⁻ RMS, 20 Me⁻ well |
| Integration | 120 µs (~50 % fill at 300 K) |
| Scheme / cal points | two-point NUC at 290 / 310 K |
| Nonlinearity dispersion (1σ) | 1.0 % of full scale |
| Pre-cal PRNU / DSNU (1σ) | 2.0 % / 300 e⁻ |
| Drift | gain 0.005 %/hour; offset 720 e⁻/hour |
| Cal source | ε = 0.98, ΔT(1σ) = 0.5 K, Δε(1σ) = 0.005 |

**Headline results.** The achieved NEDT is **exactly the temporal floor at the two cal
points** (26.13 mK at 290 K, 25.06 mK at 310 K, cal floor 0.00 mK) and degrades
parabolically outside the span: 30.73 mK at 280 K, 28.84 at 320 K, 46.97 at 330 K,
**79.86 mK at 340 K** — 3.3× the datasheet number. Uncalibrated (raw 2 % PRNU) the same
sweep reads 1086–1570 mK. Drift at 340 K takes NEDT 79.86 → 88.90 → 175.47 → 475.49 mK
at 0, 6, 24 and 72 hours since calibration. Separately, at 300 K the cal-source
uncertainty produces a **bias** of 0.955 % of radiance, or **591.5 mK at scene
temperature**, reported beside the 26.02 mK precision figure and never RSS'd into it.

**Regime.** `extended` LWIR imaging, with `detector.noise_regime = "imaging"`. The
calibration residual is added *after* readout scaling (ADR-0012), so correlated errors
do not average down.

**Takeaway.** Cal-point placement is now a design trade the tool can answer, and a
temperature-retrieval product carries two numbers, not one: a ±26 mK spread around a
possible 0.59 K offset. The old "FPN calibrated away" assumption flatters the design
everywhere outside the cal span.

**Where to go deeper.** `scenarios/02_mike_detector_engineer/2.7_calibration_limited_nedt/`.
**No GUI baseline ships**, though a `gui_workflow.md` walks the same study through the
Calibration screen.

### 2.7 (up/down background subtraction) — In-Pixel Pedestal Removal

*The second folder numbered 2.7; see the CU-362 note above.*

**Mission setup.** Mike's DROIC vendor offers an up/down counting mode: the in-pixel
counter increments during the scene phase and decrements during a reference phase,
subtracting the background pedestal before readout. The driving case is a dim
point-source target over a bright common background, where plain up-counting spends the
counter range on the pedestal. What does up/down buy, and what does it cost?

**Key inputs.**

| Quantity | Value |
|---|---|
| Aperture / focal length | 15 cm / 30 cm (f/2) |
| Band | 3.5 – 5.0 µm |
| Target | 500 K, ε = 0.9, 0.001 m² at 10 km |
| Background (swept) | 250 – 330 K, ε = 0.95 |
| Platform / atmosphere | 8 km altitude, mid-latitude summer |
| Integration (up = down phase) | 50 ms |
| Counter | 14 bit × 2000 e⁻/count |
| `up` bound / `up_down` signed bound | 32.77 Me⁻ / 16.38 Me⁻ |
| Counting-chain noise per phase | 5 e⁻ RMS |

**Headline results.** Target charge over the up phase is ≈4.86 Me⁻ (29.6 % of signed
capacity); the pedestal grows 15.9 Me⁻ (250 K) → 88.9 Me⁻ (330 K). Plain `up` counting
saturates at ~290 K background (113.6 % fill, usable SNR collapsing to 67.6 and then
0.0); **`up_down` fill is background-independent at 29.6 % across the whole sweep**,
with SNR 802.2 → 359.2 over 250 → 330 K. At 250 K, where both modes are clean, the
up/down penalty is visible: **802.2 vs 1066.0, a ratio of 0.75** — between 1 and
$1/\sqrt{2} = 0.707$, because the target's own shot noise (2203 e⁻ RMS) does not double,
only the background terms do (`reference_shot` = 3984 e⁻ RMS at 250 K). At 290 K the
comparison inverts to an 8.6× usable-SNR advantage.

**Regime.** A dim target over a bright common background, with the in-pixel background
term explicitly retained — the noise budget carries `reference_shot`, a ×√2 counting
read, and `packet_reset` over both phases.

**Takeaway.** Up/down moves the wall from the pedestal to the differential, at an
honest √2-class reference penalty. Any model that cancels the mean without paying the
reference noise overstates the mode by up to √2 — which is exactly why the noise budget
names both phases.

**Where to go deeper.** `scenarios/02_mike_detector_engineer/2.7_updown_background_subtraction/`.
**No GUI baseline ships.**

### 2.8 — Real-Part Quick Start: GeoSnap-18 by Name

**Mission setup.** Every prior scenario began with Mike transcribing datasheet values
by hand. For a MWIR airborne study he wants the part he is actually being offered — a
Teledyne GeoSnap-18 — modelled from the FPA preset library that ships with RADIANT
(Gap 119): one `fpa:` line, every value carrying its datasheet citation.

**Key inputs.**

| Input | Value | Who supplies it |
|---|---|---|
| FPA part | `geosnap-18` (12 parameters) | library preset |
| Target temperature | 300 K | Mike |
| Sensor altitude | 8000 m | Mike |
| Aperture / focal length | 0.30 m / 1.20 m (f/4) | Mike |
| Band / integration | 3.5 – 5.0 µm / 5 ms | Mike |
| Dark rate | 5.0×10⁴ e⁻/s | Mike (explicit, by design) |

The preset supplies 18 µm pitch, 2048 cross-track pixels, 100 % fill factor, QE 85 %,
110 K detector temperature, `analog_well` architecture, a 2.6 Me⁻ well, 400 e⁻ RMS ROIC
noise, a 14-bit ADC at a derived full-scale-matched 158.7 e⁻/DN, and an 85 Hz frame
period.

**Headline results.** **SNR 1177.9**, readout architecture `analog_well`. The 400 e⁻ RMS
preset entry is the vendor's ROIC-only noise for the large well; the measured 13.2 µm
science device shows 360 e⁻ RMS *system* read noise (Bowens et al. 2024), so the preset
is honest to within 10 %. Quantization at the matched gain is $158.7/\sqrt{12} \approx
45.8$ e⁻ RMS, small against 400 e⁻ read noise, and the full well digitizes
warning-free. *The digest has only this one headline metric because the walkthrough
reports only one* — no NEDT or spatial metric is quoted.

**Regime.** `extended` — a 300 K scene fills the pixel and the chain is
background-shot dominated; the binding capacity is the 2.6 Me⁻ charge well.

**Takeaway.** The preset library is a provenance mechanism as much as a convenience:
every value traces `fpa:geosnap-18/<source>`, the cited PDFs live under
`docs/validation/fpa_datasheets/` with SHA-256 manifest rows, and `FPALibrary` refuses
any preset whose attribution is incomplete. The deliberately-absent dark current is the
model being honest — dark is a function of cutoff and temperature that this custom-cutoff
part's datasheet does not fix.

**Where to go deeper.** `scenarios/02_mike_detector_engineer/2.8_fpa_part_library/`.
**No GUI baseline ships.**

---

## Persona 3 — Raj, Mission Planner

Raj turns sensor performance into collection decisions. His scenarios ask where the
go/no-go line sits — in weather, in look angle, in vendor selection — and they
repeatedly find that the intuitive driver is not the binding one.

### 3.2 — Weather Sensitivity: How Bad Can It Get?

**Mission setup.** A baselined MWIR reconnaissance sensor on a 500 km sun-synchronous
orbit needs a weather go/no-go threshold. At what visibility does performance drop
below the NIIRS ≥ 4.0 requirement, and how much does precipitable water vapour cost?

**Key inputs.**

| Quantity | Value |
|---|---|
| Aperture / focal length | 30 cm / 120 cm (f/4) |
| Band / target | 3.5 – 5.0 µm; 300 K target, 290 K background |
| Detector | 18 µm pitch, QE 70 %, dark 150 e⁻/s, read 18 e⁻ RMS, 500 ke⁻ well |
| Integration / GSD | 1.0 ms / 7.5 m |
| Visibility sweep | 2 – 100 km (25 points) at PWV 1.4 cm |
| PWV sweep | 0.5 – 5.0 cm (15 points) at visibility 23 km |
| Requirement / goal | NIIRS ≥ 4.0 / ≥ 5.0 |

**Headline results.** Across the **entire** 2–100 km visibility range, band-mean τ moves
0.4738 → 0.5580 and NIIRS moves **4.47 → 4.49**. Across the full 0.5–5.0 cm PWV range, τ
moves 0.5932 → 0.4398 and NIIRS falls just **0.04** (SNR 508.7 → 481.3). All eight named
weather conditions from Arctic dry to heavy haze are **GO**; the whole 36-cell
visibility × PWV grid spans 4.45–4.50 NIIRS. **No condition meets the NIIRS ≥ 5.0 goal**
— the best case reaches 4.50. The baseline noise budget is 99.8 % `signal_shot`
(502.0 e⁻ RMS of a 502.4 e⁻ RMS total, signal 252,041 e⁻). A real-MODTRAN cross-check
validates both axes: measured visibility response 23 → 5 km gives τ 0.555 → 0.511
against the model's 0.552 → 0.526, and the PWV slope matches at −0.038 vs −0.039 per cm.

**Regime.** `extended` — one MWIR radiance field, so `signal_shot` carries the whole
scene.

**Takeaway.** **GSD, not weather, caps NIIRS.** The GIQE-5 GSD term carries a −3.32
coefficient against SNR's +1.559, and at 7.5 m GSD the penalty is −8.20 before SNR is
considered; reaching NIIRS 5.0 needs GSD ≤ ~5.4 m, i.e. a ~1.7 m focal length rather
than 1.2 m. MWIR is robust to aerosol because extinction scales as $\lambda^{-1.3}$,
making 4.2 µm scattering ~13× weaker than at 0.55 µm, and robust to water because the
MWIR H₂O bands are already saturated.

**Where to go deeper.** `scenarios/03_raj_mission_planner/3.2_weather_sensitivity/`.
A GUI baseline ships.

### 3.3 — Multi-Sensor Comparison for Procurement

**Mission setup.** Three vendors have bid MWIR sensors. At a common operating point —
600 km, a 300 K extended scene, 8 ms — how do they compare on SNR, NIIRS, NEDT, MTF and
GSD; which meet the requirements; and where should each vendor invest to gain the most
interpretability? A composition scenario: the chain plus `giqe5_sensitivity`, no new
model.

**Key inputs.** Three vendor spec columns transcribed to a common workbook (PDF
spec-sheet parsing is explicitly out of scope). Vendor A: 3.7–4.8 µm, balanced. Vendor
B: 3.0–5.0 µm, fast f/3, large pixel, 77 K. Vendor C: 3.7–4.8 µm, 10 µm pixel behind
f/5, warmer and lower-QE. Requirements: SNR ≥ 50, NIIRS ≥ 4.0, NEDT ≤ 50 mK, GSD ≤ 1.5 m,
MTF at Nyquist ≥ 0.25.

**Headline results.**

| Metric | Vendor A | Vendor B | Vendor C |
|---|---|---|---|
| SNR | 1160 | **2449** | 491 |
| NIIRS | 4.83 | 4.54 | **4.89** |
| NEDT [mK] | 23.7 | **11.4** | 56.0 |
| GSD [m] | 9.0 | 19.2 | **3.4** |
| MTF at Nyquist | 0.27 | **0.43** | 0.00 |

Compliance: A 4/5, B 4/5, C 2/5. **No proposal is fully compliant, and the binding
failure is GSD** — none reaches 1.5 m from 600 km at the proposed f-numbers, which
would need ≈f/30 or more at these pitches. Vendor C's MTF at Nyquist of 0.00 is correct,
not a bug: a 10 µm pixel behind f/5 MWIR optics puts Nyquist far above the diffraction
cutoff ($Q \gg 2$). A +10 % improvement in GSD or RER is worth ≈+0.14 NIIRS for every
vendor, against only +0.07 for SNR.

**Regime.** `extended` — the large absolute SNRs are whole-scene 300 K MWIR values,
appropriate for a relative comparison and not as detection thresholds.

**Takeaway.** The actionable procurement finding is that **the GSD requirement is
infeasible as written**: relax it, lower the orbit, or ask for longer focal lengths.
And because NIIRS is logarithmic in SNR but strongly responsive to resolution, vendor
investment belongs in the optics, not the detector.

**Where to go deeper.** `scenarios/03_raj_mission_planner/3.3_multi_sensor_comparison/`.
A GUI baseline ships.

### 3.4 — Off-Nadir Performance Degradation

**Mission setup.** A VNIR panchromatic pushbroom on a 600 km sun-synchronous orbit.
"Can I still get useful imagery at 45° off-nadir?" The trade is image quality against
access area: how much NIIRS and GSD are surrendered to reach a target 527 km from the
nadir track.

**Key inputs.**

| Quantity | Value |
|---|---|
| Aperture / focal length | 35 cm / 350 cm (f/10) TMA |
| Obscuration / WFE | 20 % / 0.05 waves RMS at 633 nm |
| Band / pitch / QE | 450 – 900 nm / 8 µm / 80 % |
| Integration / altitude | 0.5 ms / 600 km, 10:30 LTAN, solar zenith 30° |
| Nadir GSD / $Q$ | 1.37 m / 0.844 (slightly undersampled) |
| Sweep | path zenith 0 – 45° in 5° steps |

**Headline results.** Over 0 → 45°: slant range 600.0 → 814.8 km, air mass 1.0000 →
1.3580, ground range 0 → **527.2 km**, band-mean τ 0.6594 → 0.5581 (−15.9 %). Cross-track
GSD grows 1.37 → **1.86 m (+36 %)** while along-track grows 1.37 → **2.63 m (+92 %)** —
the ground sample becomes rectangular. **SNR *rises*, 59.8 → 71.6 (+19.8 %)**, because
the growing path radiance adds more photons than the transmission loss removes — the
atmospheric-veiling effect. NIIRS falls 5.43 → 4.86, a **−0.57 penalty**, smaller than
the −0.69 the geometric-mean GSD term alone would give because the rising SNR partly
offsets it. Nadir diagnostics: NEDT 64.0 mK, Strehl 0.9065, RER 0.5372, EE 1×1 0.3634,
folded MTF at Nyquist 0.4544 with a 0.5000 alias fraction. RADIANT's `gsd_cross_track_m`
and `gsd_along_track_m` now reproduce the scenario's independent spherical-Earth
calculation on **both** axes to double-precision round-off (worst residual
1.4 × 10⁻¹³ %).

*Internal inconsistencies worth knowing:* the "Access vs Quality Trade" table carries
an older NIIRS vintage (5.35 / 5.14 / 4.78 at 0 / 30 / 45°) than the sweep table above
it (5.43 / 5.22 / 4.86); the gap-closure list quotes NIIRS 5.32 and well margin 27.6 dB
against the metrics table's 26.9 dB; and one refresh note says "the NIIRS penalty at 45°
is still −0.90" where the refreshed table reads −0.57. The digest quotes the sweep
table, which is the most recently refreshed.

**Regime.** `extended` — one reflective radiance field, hence no separate
`background_shot` term.

**Takeaway.** SNR going *up* off-nadir is real but misleading for detection work:
*contrast* SNR falls, because veiling washes out the target-background difference. The
honest cost of a 527 km access radius is −0.57 NIIRS, driven almost entirely by the
along/cross GSD asymmetry.

**Where to go deeper.** `scenarios/03_raj_mission_planner/3.4_off_nadir_agility/`.
A GUI baseline ships.

### 3.5 — Nighttime MWIR Imaging Feasibility

**Mission setup.** Can an airborne sensor image a warm building complex (295 K) against
terrain (288 K) **at night**, and how does MWIR compare with LWIR for a 7 K thermal
scene? The scenario exercises the first-class extended contrast reference (ADR-0005),
the NEDT and MRT-at-Nyquist metrics, and an analytic solar-versus-thermal comparison.

**Key inputs.**

| Quantity | Value |
|---|---|
| Scene | 295 K target against 288 K terrain (ΔT = 7 K) |
| Platform | 3 km AGL airborne, tropical atmosphere |
| Water column | 4.1 cm precipitable water — **set explicitly**, not implied by the profile |
| Bands | MWIR 3.5 – 5.0 µm and LWIR 8 – 12 µm |
| Optics / pitch | f/4, 30 µm pixels |
| Integration / well | 0.2 ms / 1×10⁷ e⁻ — sized so neither band saturates |
| Terrain envelope | NOAA LST strip, 287.6 – 288.6 K |

**Headline results.** MWIR: SNR 375.7, contrast SNR 38.1, NEDT 72.5 mK (ΔT/NEDT = 97×),
MRT at Nyquist 0.399 K. LWIR: SNR 2773.3, contrast SNR 101.0, NEDT 21.6 mK
(ΔT/NEDT = 324×), MRT 0.350 K. **Both bands detect the 7 K contrast with wide margin**;
LWIR wins on every figure, as the ~10 µm Planck peak of a 290 K scene implies. On solar
independence, band-integrated thermal against a daytime reflected-solar upper bound:
MWIR 1.379 vs 0.305 W/m²/sr (**×5**), LWIR 32.60 vs 0.0331 W/m²/sr (**×986**). Across
the terrain envelope MWIR contrast SNR stays ≥ 34 (34.6 at the hottest background, 40.4
at the coolest) and LWIR spans 89.3 – 108.8.

**Regime.** `extended` thermal self-emission, with `source.contrast_reference` set to
the 288 K terrain so `contrast_snr` is a true two-pixel differential with combined
target-plus-reference noise.

**Takeaway.** **Verdict: yes.** And the night case is the *stronger* one for MWIR: by
day the ×5 thermal-to-solar margin means roughly 20 % reflected-solar contamination —
the glint problem — while at night that term is exactly zero. A real-MODTRAN check
notes the parametric model is 2.2× too absorbing in MWIR and 0.81× too transparent in
LWIR on this tropical column, both pushing the same way, so the quoted MWIR-versus-LWIR
margin overstates LWIR's advantage.

**Where to go deeper.** `scenarios/03_raj_mission_planner/3.5_nighttime_mwir_feasibility/`.
A GUI baseline ships.

---

## Persona 4 — Lisa, Detection/Targeting Analyst

Lisa produces collection guidance. Her scenarios ask at what range, at what hour, and
under what countermeasure a target is actually findable — and two of the four turn on
contrast rather than sensitivity.

### 4.2 — Maritime Ship Classification (Johnson DRI)

**Mission setup.** With an airborne MWIR sensor on a 5 km UAV, at what range can each
ship class be Detected, Recognized and Identified? First consumer of
`radiant.performance.johnson_criteria`, which turns the Johnson resolved-cycle criteria
(1 / 4 / 6.4 cycles across the target) into ranges.

**Key inputs.**

| Quantity | Value |
|---|---|
| IFOV | 12.5 µrad (15 µm pitch / 1.2 m focal length) |
| Platform altitude | 5 km |
| Critical dimension | $\sqrt{L \cdot H}$, the 2-D-target convention |
| N50 cycles | 1 (detection), 4 (recognition), 6.4 (identification) |
| Geometric horizon | $\sqrt{2 R_E h}$ = 252 km |

**Headline results.** Identification resolution range by class: small boat (3.5 m
critical dimension) **22 km**, patrol craft (13.4 m) **84 km**, corvette (30.0 m)
**188 km**, frigate (44.2 m) 276 km, destroyer (52.8 m) 330 km, container ship (94.9 m)
593 km. The binding limit is resolution for the first three and the **252 km horizon**
for the last three. The small boat is resolution-limited at every task — detection
139 km, recognition 35 km, identification 22 km. For detection, every class except the
small boat is horizon-limited.

**Regime.** No chain run at all: DRI ranges are pure geometry (target size, IFOV, N50).
The signal chain would enter only through a contrast/MTF extension.

**Takeaway.** **The fleet splits at the frigate**: above ~44 m critical dimension,
line-of-sight is the wall and resolution is ample; below it, closing range is the only
option. Small, fast craft are the hard maritime ISR problem, and this quantifies why.
The model is contrast-blind and therefore the optimistic bound — a low-contrast target
at dusk identifies at shorter range, and reliable (>90 %) identification needs ~1.5× the
N50 cycles, shrinking every range by about a third.

**Where to go deeper.** `scenarios/04_lisa_analyst/4.2_maritime_ship_classification/`.
**No GUI baseline ships.**

### 4.3 — Camouflage Effectiveness Analysis

**Mission setup.** Lisa evaluates three thermal camouflage nets against an airborne
LWIR FLIR at 3 km. A hot vehicle (engine deck ~380 K, oxidized steel) sits in scrub
(305 K, ε = 0.96); the nets drape it and re-emit at their own near-ambient 310 K. Their
emissivity spectra arrive in three different vendor forms — a dense measured CSV, a
spectrally shaped curve, and a three-point quote sheet.

**Key inputs.**

| Quantity | Value |
|---|---|
| Sensor / band | airborne LWIR FLIR at 3 km, 8 – 12 µm |
| Bare vehicle | oxidized steel, ASTER library, ε ≈ 0.80 |
| Net A | broadband metalized weave, mean ε ≈ 0.60 |
| Net B | spectrally shaped — low 8–10 µm, high 10–12 µm |
| Net C | ε ≈ 0.93, given at only three wavelengths (8.0 / 10.5 / 14.0 µm) |
| Net surface temperature | 310 K |

**Headline results.**

| Option | Contrast [e⁻] | SCNR | Well fill [%] | Signature reduction |
|---|---:|---:|---:|---:|
| Bare vehicle | +1,851,019 | 1283.5 | 32.3 | — |
| Net A (ε ≈ 0.60) | −509,543 | 353.3 | 12.6 | 72.5 % |
| Net B (shaped) | −273,017 | 189.3 | 14.6 | 85.3 % |
| **Net C (ε ≈ 0.93)** | **+82,721** | **57.4** | 17.6 | **95.5 %** |

Sub-band SCNR shows Net B's shaping directly: 232.1 in 8–10 µm against 41.5 in
10–12 µm, so a half-band sensor would rank the nets differently than the full FLIR.
Detection range is **edge-limited at 17.1 km for every option** — the 80° zenith sweep
cap, not SCNR.

**Regime.** `extended` — a draped net fills the pixel. Because the extended regime
carries no separate scene-background photon term, the differential is formed explicitly
from two runs: $SCNR = |S_{option} - S_{scrub}| / \text{noise}_{scrub}$. Spectral
emissivity enters through the tabulated-radiance path
(`source.target.user_radiance_path`) because the chain has no spectral target-emissivity
input (Gap 47).

**Takeaway.** **Camouflage is radiance matching, not emission lowering.** The intuitive
low-ε choice over-corrects: Net A at ε = 0.60 reads distinctly *cold* (−510 k e⁻), a
large negative contrast an $|contrast|$ detector sees just as well as a hot one. Net C,
whose high flat emissivity sits near the scrub's 0.96, cuts the signature 95.5 %. And no
net defeats detection at 3 km — they reduce signature, which is the operational metric.

**Where to go deeper.** `scenarios/04_lisa_analyst/4.3_camouflage_effectiveness/`.
A GUI baseline ships.

### 4.4 — Time-of-Day (Diurnal) Thermal Detectability

**Mission setup.** Over a 24-hour cycle, when is a painted-metal vehicle detectable
against its soil background in the LWIR, and when does it wash out? The physics is
thermal crossover: twice a day the two surfaces radiate equally, contrast collapses, and
the target vanishes regardless of detector sensitivity. The diurnal temperature profile
is input data; no new framework model is involved.

**Key inputs.**

| Quantity | Value |
|---|---|
| Sensor / band / altitude | LWIR, 8 – 12 µm, 3 km AGL |
| Target | painted metal, ε = 0.92, low thermal inertia (large early swing) |
| Background | soil, ε = 0.95, higher inertia (smaller lagged swing) |
| Profile | measured 24-hour CSV, sampled every 0.5 h |
| Integration time | 0.1 ms — 8 ms saturates the well (>99 %) and destroys the contrast |
| Detectability threshold | \|contrast SNR\| ≥ 10 |

**Headline results.** Contrast SNR runs −98.3 at 00:00 (ΔT = −4.06 K, cold target),
+18.5 at 06:00, **+140.6 at 12:00** (ΔT = +10.06 K), +17.8 at 18:00, −66.0 at 21:00.
Physical-temperature crossovers (ΔT = 0) fall at **04:12 and 19:48**; **radiance**
crossovers (contrast = 0) at **05:12 and 18:48** — offset by about an hour. Washout
windows (|contrast SNR| < 10) are ≈05:30–06:00 and ≈18:30–19:00, roughly 30 minutes
each. **Median NEDT across the day is 36.7 mK, essentially constant.**

**Regime.** `extended` for each pixel run; the differential is built at the scenario
level as $(S_t - S_b)/\sqrt{N_t^2 + N_b^2}$, because the chain's own `contrast_e` is
populated only in the sub-pixel regime (Gap 52).

**Takeaway.** **The washout is a scene effect, not a sensor effect** — the detector is
exactly as sensitive at crossover as at noon; there is simply nothing to detect. And
because the target is *less* emissive than the background, it must run a few kelvin
warmer to match it, so the radiance crossover is offset from the temperature crossover
by ~1 hour. An analyst planning around the temperature crossover mis-times the washout
by that hour. A real-MODTRAN check moves the crossings by only ≈±10 minutes.

**Where to go deeper.** `scenarios/04_lisa_analyst/4.4_time_of_day_analysis/`.
A GUI baseline ships.

### 4.5 — Microbolometer UAV Altitude Trade (NETD-Specified)

**Mission setup.** An uncooled microbolometer is specified only by its NETD — the way
uncooled detectors are actually quoted. How high can the UAV fly and still detect a
small warm ground target? Second consumer of the D*/NEP/NETD converter set
(`radiant.performance.detectivity`, `.nep_electrons`, `.nep_netd`).

**Key inputs.**

| Quantity | Value |
|---|---|
| Vendor NETD | 50 mK |
| Optics | f/1, 486 µrad IFOV |
| Target | 1 m, ΔT = 4 K against background |
| Frame time | 16 ms (the bolometer thermal time constant) |
| Detection floor | 4 × NETD = 200 mK (recognition-grade) |
| Altitude sweep | 1 – 11 km |

**Headline results.** Converter outputs: $dP/dT = 1.515 \times 10^{-10}$ W/K,
$NEP = 7.576 \times 10^{-12}$ W, $D^* = 1.254 \times 10^{9}$ Jones — the textbook order
of magnitude for an uncooled microbolometer, about 100× below a cooled photon detector.
The altitude trade: at 1 km, GSD 0.49 m, fill fraction 1.000, τ 0.921, apparent
ΔT 3682 mK; at 5 km, 2.43 m / 0.170 / 0.748 / 508 mK; at 7 km, 3.40 m / 0.087 / 0.715 /
**248 mK (detect)**; at 9 km, 4.37 m / 0.052 / 0.695 / **145 mK (no detect)**. The target
goes sub-pixel at **2.1 km**, and the **detection ceiling is 7.5 km** — 1 km lower than
this walkthrough previously reported, because the refreshed atmosphere is more absorbing
on long slant paths. Across 1–11 km the fill fraction falls ×28.6 while τ falls only
×1.34, so dilution outweighs attenuation about 21:1 in the 38× total contrast collapse.

**Regime.** Sub-pixel dilution applied as an apparent-contrast threshold
($ff \cdot \Delta T \cdot \tau$ against $4 \times$ NETD), not a chain `contrast_snr`.
**A false saturation warning fires** (Gap 101): the chain checks a photoelectron count
against a charge well, but a bolometer measures resistance change over its thermal
frame. The SNR the baseline reports is a photon-FPA quantity with no bolometric meaning;
the scenario's actual metric is independent of the well and ADC path.

**Takeaway.** The ceiling is set by resolution, not sky clarity, so the fix is a longer
focal length or a closer approach. An operator flying to the previously-published 8.5 km
ceiling would have been 1 km above the detection limit.

**Where to go deeper.** `scenarios/04_lisa_analyst/4.5_altitude_trade_uav/`.
A GUI baseline ships.

---

## Persona 5 — Tom, Optical Designer

Tom owns the optics and the spatial budget. His scenarios are sampling,
chromaticism, line-of-sight stability and stray-light trades, and each one finds
that the metric a designer reaches for first — MTF at Nyquist, veiling glare,
Strehl — is not the one that binds.

### 5.2 — Pixel Pitch and the Sampling Parameter Q

**Mission setup.** The optics are fixed: a 30 cm f/4 Ritchey-Chrétien working
3.5–5.0 µm from a 500 km orbit. Six vendors offer detectors from 8 to 30 µm pitch,
each pitch carrying its own well, dark current, QE and read noise — small pixels
quiet and shallow, large ones deep and noisy. Which pitch balances resolution
against sensitivity while meeting every requirement?

**Key inputs.**

| Quantity | Value |
|---|---|
| Aperture / f-number | 30 cm / f/4 |
| Band / geometry | 3.5 – 5.0 µm / 500 km LEO, nadir |
| Airy disk at 4.25 µm | 41.6 µm ($2.44\,\lambda\,f/\#$) |
| Pitch candidates | 8, 12, 15, 18, 24, 30 µm, each with matched vendor specs |
| Matched-spec span | QE 70 → 68 %, dark 15 → 120 e⁻/s, FWC 40 ke⁻ → 2.5 Me⁻, read 8 → 28 e⁻ RMS |
| Requirements | GSD < 10 m, MTF at Nyquist ≥ 0.10, EE 1×1 ≥ 0.30, SNR ≥ 100 |

**Headline results.** Across 8 → 30 µm: $Q = \lambda\,(f/\#)/p$ runs 2.12 → 0.57,
GSD 3.3 → 12.5 m, SNR 199.8 → 1268.8, MTF at Nyquist 0.000 → 0.409, EE 1×1
0.146 → 0.572, NEDT 149.7 → 23.6 mK. **Two candidates pass everything — 15 µm and
18 µm** — and an SNR/GSD figure of merit picks **18 µm** (94.3 against 15 µm's
80.0) at $Q$ = 0.94, SNR 706.9, GSD 7.5 m, NEDT 42.3 mK. The 8 µm pixel fails both
spatial requirements; 12 µm now fails EE 1×1 at 0.269 against the 0.30 floor,
having passed before CU-188's cell-area-overlap EE_box lowered every EE 1×1 by
11–13 %; 24 and 30 µm fail GSD. **MTF at Nyquist of exactly 0.000 at 8 µm is
physical, not a defect** — Nyquist at 62.5 cy/mm sits above the ~59 cy/mm
diffraction cutoff, so there is genuinely no modulation there to measure.

**Regime.** `extended` — the 310 K ground scene fills every candidate pixel, so the
trade is collection area against sampling with no EE_box coupling.

**Takeaway.** Signal scales as $p^2$, so oversampling is expensive: 18 → 8 µm
throws away 5× the signal to buy resolution the f/4 optics cannot deliver. The
binding *upper* limit on pitch is GSD and the binding *lower* one is ensquared
energy — MTF at Nyquist, the metric a designer reaches for first, is comfortable
across the entire compliant range. And each pitch must carry its own vendor specs:
sweeping pitch alone would give the wrong answer.

**Where to go deeper.** `scenarios/05_tom_optical_designer/5.2_pixel_pitch_optimization/`.
A GUI baseline ships. (The refresh notes call this "an 8–12 µm scene" where the band
is 3.5–5.0 µm — boilerplate carried from an LWIR sibling; the movement they quote is
this scenario's own.)

### 5.3 — Monochromatic vs Polychromatic PSF

**Mission setup.** With the 18 µm pitch chosen in 5.2, is the spatial analysis that
chose it even accurate? Diffraction scales linearly with wavelength, so across a
3.5–5.0 µm band — a 43 % span — the Airy diameter grows 34.2 → 48.8 µm. Does a
monochromatic PSF at band centre give the right spatial metrics, or is a
flux-weighted polychromatic PSF required?

**Key inputs.**

| Quantity | Value |
|---|---|
| Optics / pitch | f/4, 18 µm (the 5.2 selection) |
| Band | 3.5 – 5.0 µm |
| Per-λ probes | 3.5, 4.0, 4.25, 4.5, 5.0 µm in ±50 nm narrow bands |
| PSF model | `optics.psf_n_wavelengths` = 1 (mono), 5, 11, 21 |
| Weighting | in-band **photon** spectral flux of the 300 K scene |

**Headline results.** The per-wavelength ladder is monotone in both directions:
MTF at Nyquist 0.328 → 0.210, EE 1×1 0.478 → 0.358, FWHM 19.5 → 23.6 µm and
SNR 88 → 244 across 3.5 → 5.0 µm — tighter PSF and fewer photons at the short end.
Full-band, mono (N=1) gives MTF at Nyquist 0.267, EE 1×1 0.414, EE 3×3 0.878, RER
0.610, FWHM 21.3 µm; poly (N=11) gives 0.248, 0.396, 0.871, 0.596, 21.1 µm. The
chromaticism error is therefore **+7.6 % on MTF at Nyquist and +4.7 % on EE 1×1**,
+2.3 % on RER, and negligible on EE 3×3 (+0.8 %), FWHM (+0.8 %) and SNR (+0.0 %).
N=11 converges to within 0.3 % of N=21. The 18 µm pixel still passes every 5.2
requirement under polychromatic analysis, with EE 1×1 clearing its floor by 31 %
rather than 47 %. *(Takeaway 6 of the walkthrough quotes the poly values as
0.246/0.394 where its own table reads 0.248/0.396, and calls the EE 3×3 error 0.9 %
against the table's 0.8 % — stale prose against a refreshed table.)*

**Regime.** `extended`. SNR is identical across every PSF model, because in the
extended regime SNR depends on total signal and noise, not PSF shape.

**Takeaway.** **Monochromatic analysis always overstates, never understates**, and
by a knowable amount: band centre is sharper than the flux-weighted average, and a
thermal source's in-band photon flux is biased toward the long-wavelength end.
The error concentrates entirely in the single-pixel metrics — EE 1×1 and MTF at
Nyquist — which is exactly where point-source detection sensitivity lives.

**Where to go deeper.** `scenarios/05_tom_optical_designer/5.3_mono_vs_poly_psf/`.
A GUI baseline ships.

### 5.4 — Jitter Tolerance: Deriving the Pointing Requirement

**Mission setup.** A 50 cm f/10 VNIR panchromatic imager on a 500 km sun-synchronous
orbit, GSD 0.80 m. The 5.0 m focal length that buys the fine GSD also amplifies
angular jitter onto the focal plane: how much line-of-sight wander can the
spacecraft allow? The sweep is 51 *full-chain* evaluations, not an analytic
approximation — the jitter kernel convolves into the `EffectivePSF` and
`PerformanceStage` reads RER and NIIRS back off it.

**Key inputs.**

| Quantity | Value |
|---|---|
| Aperture / focal length | 50 cm / 500 cm (f/10) |
| Obscuration / WFE | 30 % / 0.05 waves RMS |
| Band / pitch / QE | 450 – 700 nm / 8 µm / 85 % |
| Integration / FWC | 0.5 ms / 100,000 e⁻ |
| GSD / $Q$ / IFOV | 0.80 m / 0.72 (undersampled) / 1.6 µrad |
| Jitter sweep | 0 – 5.0 µrad, 51 points |
| Thresholds | ΔNIIRS = −0.5, ΔNIIRS = −1.0, absolute NIIRS = 6.0 |

**Headline results.** Baseline signal 2109 e⁻ (2.1 % well), noise 46.2 e⁻ RMS of
which `signal_shot` is 98.6 %, and — from the CU-355-refreshed sweep — zero-jitter
MTF at Nyquist 0.2186, RER 0.5724, NIIRS 6.03. **SNR is exactly 45.6 at all 51
sweep points, spread 0.0000**: jitter blurs the image without removing a photon, so
NIIRS degrades entirely through the RER term. Focal-plane blur is
$\sigma_{fp} = \text{jitter} \times f$, so 1 µrad is 5 µm = 0.625 pixels. Jitter MTF
at Nyquist falls 1.0000 → 0.1455 (1 µrad) → 0.0072 (1.6 µrad, one full IFOV); RER
0.5724 → 0.4013 → 0.1193 at 5 µrad; NIIRS 6.03 → 5.52 → 3.77. The budget lines are
**1.0 µrad for ΔNIIRS = −0.5, 1.8 µrad for −1.0, and 0.2 µrad for the absolute
NIIRS = 6.0 floor**. Past ~2.6 µrad RER drops below 0.20 and the NIIRS tail is
extrapolated GIQE-5 output (CU-178).

*Internal inconsistencies worth knowing:* the "Baseline Results" box (MTF 0.2330,
RER 0.5483, NIIRS 5.97) and a paragraph asserting "the NIIRS = 6.0 floor is no longer
reachable at any jitter" are the pre-CU-355 vintage, contradicting the refreshed sweep
and threshold tables above them. The digest quotes the refreshed tables.

**Regime.** `extended` — a reflective ground scene fills the pixel, which is why SNR
is jitter-invariant. For point-source detection jitter *would* cost per-pixel SNR;
GIQE-5 assumes extended targets.

**Takeaway.** How the requirement is *written* changes the answer by 5×: an
absolute NIIRS ≥ 6.0 spec consumes essentially the whole jitter budget at 0.2 µrad,
while a relative ΔNIIRS ≤ 0.5 allows 1.0 µrad. And the Gaussian-PSF shortcut used in
the first version of this study overestimated the budget by ~20 %, because the real
Airy-plus-IPC PSF has wider tails than a Gaussian.

**Where to go deeper.** `scenarios/05_tom_optical_designer/5.4_jitter_induced_blur/`.
A GUI baseline ships.

### 5.5 — Stray Light and Veiling Glare

**Mission setup.** Tom's FRED stray-light analysis returns three things: a 3 %
veiling-glare index, 2.5 W/m² of out-of-field stray irradiance, and a 2-D stray PSF
RADIANT cannot ingest. What do the first two cost in contrast, SNR and NIIRS, and
how much veiling glare can the design tolerate? The scene is a daytime VNIR pan
rooftop (ρ = 0.30) against vegetation (ρ = 0.15) from 7 km.

**Key inputs.**

| Quantity | Value |
|---|---|
| Optics / band | 15 cm f/6 / 0.5 – 0.8 µm |
| Platform / illumination | airborne 7 km, solar zenith 30° |
| Target / background reflectance | 0.30 / 0.15 |
| Stray mode 1 | `veiling_glare`, VGI = 3 % |
| Stray mode 2 | `absolute_irradiance`, 2.5 W/m² out-of-field |
| Well | 3.0 × 10⁵ e⁻ (target pixel saturates) |
| Budget | ΔNIIRS ≤ 0.2 **and** contrast SNR ≥ 50 |

**Headline results.** Clean: SNR 546.7, contrast SNR 217.4, NIIRS 11.052. **3 %
veiling glare** adds 2.92 × 10⁴ stray e⁻ → SNR 522.0, contrast SNR 208.6, ΔNIIRS
**−0.031**. **The 2.5 W/m² out-of-field term** adds 5.52 × 10⁶ stray e⁻ — several
times the signal itself — taking SNR to 124.3, contrast SNR to 49.4 and ΔNIIRS to
**−1.003**, a full NIIRS level. Tolerance: VGI can rise to **~10 %** before either
budget clause breaks. The scenario also found and fixed the `veiling_glare` mode:
it had scaled in-FOV irradiance by the *pixel IFOV* solid angle instead of the
*f-cone*, under-reporting stray by ~10⁷–10⁸ so that any VGI produced ~zero stray
(CU-062). Fixed, the mode reproduces the identity $stray_e = VGI \cdot signal_e$ to
the digit — 9.729 × 10⁴ e⁻ at VGI 10 %. *(The absolute NIIRS values of ~11 sit far
above the rating scale's 9-point ceiling — unflagged GIQE-5 extrapolation on a fine-GSD
airborne pan scene; only the ΔNIIRS column is meaningful.)*

**Regime.** `extended`. Stray light is a **pedestal, not a signal**: it is common to
target and background, cancels exactly in the target−background contrast, and
degrades contrast SNR purely through the shot noise it adds.

**Takeaway.** The number the optical designer worries about is the cheap one. Three
percent of veiling glare costs 0.03 NIIRS; the out-of-field irradiance costs a
full level, and that is the term the baffle design must control. What the scalar
model does *not* capture is the spatial half — there is no veiling-glare MTF and no
2-D PSF/PST importer, so the radiometric hit is modelled and the contrast-modulation
hit is not.

**Where to go deeper.** `scenarios/05_tom_optical_designer/5.5_stray_light_veiling_glare/`.
A GUI baseline ships.

---

## Persona 6 — Dr. Chen, Researcher

Dr. Chen validates. Every one of her scenarios checks RADIANT against something
outside it — real MODTRAN output, a hand-integrated Planck calculation, ROC theory,
a retrieval Jacobian — and reports the residual whether or not it flatters the tool.

### 6.2 — Atmospheric Model Intercomparison

**Mission setup.** How far does RADIANT's parametric `SimpleAtmosphere`
(Beer-Lambert with tuned band fits) diverge from real MODTRAN 6 across the six
standard atmosphere profiles at one fixed geometry — and what does that divergence do
to SNR? The reference is the delivered MODTRAN 6 A-block, not a synthetic stand-in;
the script falls back to synthetic tape7 with a loud banner when the gitignored real
set is not staged, so a bare clone still runs.

**Key inputs.**

| Quantity | Value |
|---|---|
| Profiles | us_standard, tropical, midlat summer/winter, subarctic summer/winter |
| Geometry | nadir, 100 km sensor (the A-block matrix, not the catalog's 10°/500 km) |
| Band | 3.5 – 5.0 µm |
| Scene | 300 K target against 288 K background |
| Reference | real MODTRAN 6 `A1–A6.tp7`, imported via `atmosphere.model = "modtran"` |
| Comparison | identical sensor config run twice per profile, isolating the atmosphere term |

**Headline results.** Band-mean τ residuals (MODTRAN − Simple, relative to MODTRAN)
span a **uniform −4.7 % to −9.8 %** across all six profiles — Simple is
systematically slightly *too transparent*, and the offset no longer varies with
climate. SNR residuals run **−6.6 % to −16.6 %** and now track the τ residuals
(tropical worst on both, subarctic_winter best on both), with real-MODTRAN SNR nearly
profile-independent at 567–579. The τ table is the CU-161 acceptance evidence: the
first real-data run in 2026-07 found residuals spanning **−43 % to +62 %**, and the
gas-band recalibration that finding triggered collapsed them **6×** to the band
above.

**Regime.** `extended` thermal contrast in the MWIR — both target and background are
attenuated by the same column, so the SNR-relevant quantity is the contrast radiance
difference rather than absolute τ.

**Takeaway.** **SNR is now more sensitive to atmosphere-model choice than raw
transmittance is**, which reverses this scenario's own earlier conclusion. An
atmosphere model contributes two separable things: attenuation, which largely cancels
in a contrast ratio, and its own path emission, which does not. Judging a model by τ
alone understates its effect on a thermal SNR prediction. (libRadtran remains absent
— fabricating plausible numbers would defeat the purpose of an intercomparison the
same way a fake MODTRAN would.)

**Where to go deeper.** `scenarios/06_dr_chen_researcher/6.2_atmospheric_intercomparison/`.
A GUI baseline ships.

### 6.3 — Noise Model Verification Against Hand Calculation

**Mission setup.** Dr. Chen is writing a paper comparing RADIANT against analytic
noise models. She needs every noise term checked against a hand calculation built
from CODATA constants alone — sharing nothing with RADIANT but the constants and the
solar irradiance table.

**Key inputs.**

| Quantity | Value |
|---|---|
| Optics | 30 cm f/4, 70 % transmission, 293 K |
| Detector | 18 µm pitch, QE 70 %, dark 100 e⁻/s, read 20 e⁻ RMS, FWC 2 Me⁻, 14-bit at 1 e⁻/DN |
| Scene / band / integration | 300 K, ε = 0.95 / 3.5 – 5.0 µm / 5 ms |
| Platform / atmosphere | 8 km airborne / `exo` (vacuum) |
| Entry path | raw vendor units through `Sensor.set(..., unit=...)`, cross-checked to 1e-12 |

**Headline results.** **Every noise term agrees to 0.00 %**: `signal_shot` 1280.68,
`dark_shot` 0.71, `read_noise` 20.00, `quantization` 0.29 e⁻ RMS, RSS total 1280.83
e⁻ RMS, SNR 1280.52. The underlying signals match to better than 0.01 % — 1,506,203
thermal + 133,931 solar = 1,640,135 e⁻ by hand against RADIANT's 1,640,136. That
exactness required two upgrades to the *hand* model, not the code: a photon-weighted
spectral integral (the band-centre $E_{photon}$ shortcut reads ~5.5 % low for a 300 K
source in this band) and the Kirchhoff reflected-solar term (ρ = 1 − ε = 0.05 of the
TOA solar spectrum, ~9 % of the in-band signal). `background_shot` and
`nearfield_shot` are both 0 by design. **NEDT is the one disagreement: 21.79 mK
reported against 23.92 mK exact, 8.9 % apart** — registry Gap 43, because the stage
uses the single-wavelength Planck-factor form and its SNR numerator includes the
reflected-solar signal, which does not vary with target temperature. *(The
performance table reports MTF at Nyquist 0.2668 where the MTF budget's own system row
reads 0.2688.)*

**Regime.** `extended` — the 300 K target fills the pixel IFOV, so there is no
separate scene-background photon stream (ADR-0002 Decision #13) and the background
inputs define only the contrast scene.

**Takeaway.** A 0.00 % agreement across all terms simultaneously pins the Planck
integral, the solar coupling, the Kirchhoff reflectance, the pixel étendue, the QE
and transmission application and the shot-noise square root in one check. The two
hand-model upgrades are the lesson: **a thermal-only textbook formula verifies a
nighttime scene**, and a band-centre photon energy is a 5.5 % error on any
wide-band thermal source.

**Where to go deeper.** `scenarios/06_dr_chen_researcher/6.3_noise_model_verification/`.
A GUI baseline ships.

### 6.4 — Synthetic Scene Generation for Algorithm Testing

**Mission setup.** Dr. Chen is developing an LWIR target-detection algorithm and
needs raw material to test it against: pixel-level signal and noise for a multi-target
scene, a simulated noisy 1-D strip, an SNR map, and a ROC curve per target. First
consumer of `radiant.performance.roc`.

**Key inputs.**

| Quantity | Value |
|---|---|
| Sensor | 5 cm aperture, f/20, 25 µm pitch (25 µrad IFOV), 0.5 ms |
| Band / background | LWIR 8 – 12 µm / uniform 290 K |
| Targets | five, 10 – 200 km range, 15 – 40 K hotter than background |
| Reference target | 305 K, 3 m, ε = 0.93 |
| Fill fraction | $ff = (\text{size}/\text{GSD})^2$, capped at 1 |
| Detection model | equal-variance Gaussian, $P_d = Q(Q^{-1}(P_{fa}) - SNR)$ |

**Headline results.** Background pixel 4.972 × 10⁵ e⁻ with σ = 713 e⁻,
shot-noise-limited. **All five nominal targets are trivially detected** — contrast
SNR 487.3 (10 km) down to 51.2 (200 km, the only sub-pixel one at $ff$ = 0.36), every
$P_d$ = 1.000 at $P_{fa}$ = 10⁻⁴. A ROC of those five is uninformative, so the
detection science lives in the range sweep, where $ff \propto 1/R^2$ walks the
reference target down: contrast SNR 51.2 (200 km) → 8.2 (500 km) → 3.2 (800 km) →
0.51 (2000 km). **Reliable detection ($P_d \geq 0.9$) holds to ≈ 535 km and the
50/50 range is ≈ 700 km.** The informative gap is at 800 km, where AUC is still 0.988
— good *separation* — but $P_d$ at $P_{fa}$ = 10⁻⁴ is only 0.302.

**Regime.** `extended` for every chain run, with the scene assembled analytically
from it. In the extended regime the per-pixel signal is **geometrically**
range-independent — radiance × a fixed pixel solid angle — but not atmospherically
so: the nominal table shows the filled-pixel target signal falling 31 % over
10 → 200 km through transmittance alone, and the sweep's analytic $ff$ dilution
holds the atmospheric factors at each target's own range rather than claiming an
identity.

**Takeaway.** **The gap between AUC and a strict-$P_{fa}$ $P_d$ is the whole design
trade.** At 800 km the target is well separated from the background by any
integrated measure, and a detector held to one false alarm in ten thousand still
finds it only one time in three. The near targets being "too easy" is the physical
answer, not a modelling artefact, and the scenario moves the analysis rather than
tuning the scene.

**Where to go deeper.** `scenarios/06_dr_chen_researcher/6.4_synthetic_scene_generation/`.
A GUI baseline ships.

### 6.5 — Emissivity Sensitivity for Temperature Retrieval

**Mission setup.** An LWIR radiometer measures radiance and the analyst inverts it
for surface temperature — but the inversion needs an *assumed* emissivity. How badly
does an error in that assumption bias the retrieved temperature, and how does the
bias compare with the sensor's own NEDT? First consumer of
`radiant.performance.temperature_retrieval`.

**Key inputs.**

| Quantity | Value |
|---|---|
| True scene | T = 300 K, ε = 0.95 |
| Band | LWIR 8 – 12 µm |
| System NEDT | 50 mK |
| Assumed-ε sweep | 0.90 – 1.00 |
| Method | band-averaged Planck; Brent root-find inversion plus the analytic Jacobian |

**Headline results.** The Jacobian at the operating point gives
$\partial L/\partial\varepsilon$ = 38.50 W/m²/sr and $\partial L/\partial T$ = 0.598
W/m²/sr/K, hence **$dT/d\varepsilon = -64.4$ K per unit ε, or −0.64 K per 0.01 ε**.
The exact inversion tracks it: assumed ε = 0.90 retrieves 303.34 K (**+3.34 K**),
ε = 0.94 gives +0.65 K, ε = 0.96 gives −0.64 K, ε = 1.00 gives **−3.11 K**. A lower
assumed ε over-estimates T, because the surface must be hotter to emit the same
radiance. **The NEDT-equivalent emissivity uncertainty is ±0.0008 (0.08 %)**: to keep
the retrieval bias below the sensor's own 50 mK, emissivity must be known to better
than a tenth of a percent. Over a realistic ±0.05 uncertainty the bias reaches 3.3 K
— **67× the NEDT floor**.

**Regime.** No chain regime applies — this is a band-radiance inversion with its
Jacobian, run against a declared NEDT rather than through the signal chain.

**Takeaway.** **Emissivity knowledge, not detector NEDT, limits absolute LWIR
thermometry.** Buying a lower-NEDT detector does nothing for temperature accuracy
until ε is pinned down — and because the retrieval error is a *bias*, not noise,
frame averaging (which beats down NEDT) does not touch it.

**Where to go deeper.** `scenarios/06_dr_chen_researcher/6.5_spectral_emissivity_sensitivity/`.
**No GUI baseline ships** — the only scenario in personas 5–7 without one.

---

## Persona 7 — Karen, Test Engineer

Karen measures what the model predicts. Her scenarios are bench comparisons — a
blackbody calibration, a slanted-edge MTF, a cold-stop background, a TVAC
temperature sweep — and the interesting result is always the residual, and what it
turns out to be made of.

### 7.2 — Radiometric Calibration Verification

**Mission setup.** Karen ran a NIST-traceable blackbody calibration at five set
points from 280 to 360 K, recording 100-frame mean DN at each. She needs RADIANT's
as-built prediction beside the measurement **in DN**, the unit her data system
actually records, plus responsivity, a linearity check and per-point uncertainty —
with the lab ambient and the instrument's own self-emission modelled, because that is
what a calibration's offset term physically is.

**Key inputs.**

| Quantity | Value |
|---|---|
| Optics | 15 cm / 30 cm (f/2.0), τ = 0.72 net |
| Modelled train | 3 × R = 0.98 mirror + AR cold window ⇒ emitting ε ≈ 0.045, not the workbook's ε = 28 % |
| Optics temperature | 20 °C (bench ambient) |
| Detector | 15 µm pitch, QE 75 %, dark 5 × 10⁴ e⁻/s, read 30 e⁻ RMS, 2 Me⁻ well |
| Band / integration / gain | 3.7 – 4.9 µm / 0.25 ms / 125 e⁻/DN, 14 bit |
| Set points | 280, 300, 320, 340, 360 K (5 – 60 % well) |

**Headline results.** Predicted DN runs 742.1 → 9615.1 against measured 795.5 →
9815.0, residuals **−6.72 % at the cold end narrowing to −2.04 % at the hot end**.
Fitting `measured = a·predicted + b` decomposes that entirely into two physical
knobs: **a = 1.0162** (real responsivity +1.62 % against the as-built gain spec) and
**b = +43.6 DN** of instrument offset. Percent residuals are largest at the cold end
not because the model is worse there but because a fixed offset is a larger fraction
of a small signal. Responsivity $dDN/dT$ rises 42.47 → 198.15 DN/K over the sweep as
the Planck derivative steepens; radiance responsivity is 1059 DN/(W/m²/sr). Linearity
holds to **0.107 % of full scale**. Calibration uncertainty on 100-frame means is
5.9 mK (280 K) and 4.4 mK (360 K). Separately, RADIANT models **73.8 DN of
warm-optics near-field** from first principles — which now *exceeds* the 43.6 DN
fitted residual, itself informative.

**Regime.** `extended` — the blackbody fills the aperture, so the scene-background
photon term is skipped and the lab-ambient parameters feed only the contrast scene.
The instrument terms that genuinely move the offset, near-field and dark, are both
modelled.

**Takeaway.** **Raw residuals of −2 to −7 % are not a model failure; they are an
uncalibrated instrument.** Two coefficients absorb them completely, which is the
entire point of the exercise. That the modelled near-field now exceeds the fitted
offset says either the bench train is better coated than the assumed R = 0.98 or its
barrel is colder than 20 °C — a testable statement, which is where 7.4 picks up.

**Where to go deeper.** `scenarios/07_karen_test_engineer/7.2_radiometric_calibration/`.
A GUI baseline ships.

### 7.3 — MTF Measurement vs Prediction

**Mission setup.** Karen measured system MTF with a slanted-edge target (ISO 12233)
at 650 nm. She has as-built WFE from interferometry (0.07 waves RMS at 633 nm) and
knows the detector sits 5 µm from best focus. Overlay the prediction, decompose the
budget, compute the residual, and find out what the residual is made of.

**Key inputs.**

| Quantity | Value |
|---|---|
| Optics | 20 cm Cassegrain, f/3.0, 25 % obscuration, 82 % transmission |
| Band / test wavelength | 550 – 750 nm / 650 nm collimator |
| Detector | 10 µm pitch, 100 % fill, IPC 1.0 % |
| As-built WFE / defocus | 0.07 waves RMS at 633 nm / 5 µm |
| Sampling | $f_{Nyq}$ 50.0 cy/mm against a 512.8 cy/mm cutoff; $Q$ = 0.195 |
| Atmosphere | `exo` (bench) |

**Headline results.** **Measured MTF at Nyquist 0.4441 against RADIANT's 0.4361**,
with a **residual RMS of 0.0215** across all 50 measured points — slanted-edge
measurement-noise level. The analytic four-term composition reads 0.5339 with a
0.0606 RMS residual, so **RADIANT now beats the analytic model**. The budget at
Nyquist: optics (diffraction + obscuration + WFE + defocus-Z4, from one pupil)
0.6699, pixel aperture 0.6364, IPC 0.9602, everything else unity, system product
0.4392 against the PSF path's 0.4361. Defocus is negligible: 5 µm costs 0.9 % of MTF
at Nyquist, and even 15 µm only 7.4 %. Two residual explainers were tested on a grid
and **both rejected** — electronics blur (1 µm ⇒ RMS 0.0292) and TIS surface
roughness (5 nm ⇒ 0.0248) each make the fit *worse*, bounding them below those
values. Other metrics: Strehl 0.9494, RER 0.7818, FWHM 10.15 µm.

**Regime.** A bench measurement, not a scene: GSD, NIIRS and NEDT are all reported
N/A (altitude = 0, no thermal scene in the VNIR), and the noise budget is dark 0.32,
read 8.00, quantization 2.31 e⁻ with essentially no photon flux.

**Takeaway.** **This scenario's own diagnosis drove a model change.** At the 2026-08
vintage the residual was 0.0917 RMS and the walkthrough diagnosed it as the *shape
ambiguity of scalar WFE* — a white-noise phase screen dumps aberrated energy into a
compact halo and drops low frequencies toward the Strehl plateau, where a real
optic's smooth aberrations hold them near 1. CU-355 replaced the screen with a
deterministic low-order Zernike expansion and the residual fell **4.3×**. The
secondary lesson is the rejection workflow itself: a hypothesis that does not reduce
the residual is reported as rejected, not quietly fitted. And at $Q$ = 0.195 the pixel
sinc, not the optics, is the dominant contributor — improving WFE buys almost nothing.

**Where to go deeper.** `scenarios/07_karen_test_engineer/7.3_mtf_measurement_vs_prediction/`.
A GUI baseline ships.

### 7.4 — Cold-Stop Undersizing Sweep

**Mission setup.** In a TVAC campaign on an MWIR imager, the cold stop *is* the
aperture stop: a ~77 K cryogenic aperture deliberately built a little smaller than
the primary so that alignment and thermal tolerances can never let the focal plane see
past it to warm structure. Undersizing buys that certainty and pays in photons. How
much margin can the camera afford, does it help the background, and what do six
shuttered-background lab readings mean?

**Key inputs.**

| Quantity | Value |
|---|---|
| Optics | 25 cm / 1.0 m (f/4.0), net τ = 0.68 |
| Modelled train | 3 × R = 0.98 mirror (ε = 0.02 each) + AR cold window (ε = 0) ⇒ ε_emit 0.06, not 0.32 |
| Detector | dark 499,376 e⁻/s (from 80 fA/pixel), read 25 e⁻ RMS |
| Band / integration | 3.70 – 4.80 µm / 8 ms |
| Sweep | undersizing $u$ = 0 → 10 % |
| Requirement | shuttered background < 40,000 e⁻ |

**Headline results.** One effective pupil drives everything:
$D_{eff} = (1-u)D$, and from it $A_{collect}$, $N_{eff}$, the complex pupil (hence
PSF *and* MTF, Rule 4) and the étendue cone $\Omega_{cone}$. At $u$ = 0: signal
2,994,945 e⁻, near-field 106,631 e⁻, SNR 1699.3, NEDT 17.00 mK, MTF at Nyquist
0.3017. Over 0 → 10 %: **$A_{collect}$ −19.0 %, $\Omega_{cone}$ −18.8 %, near-field
−18.8 %, signal −19.0 %, SNR −10.0 %, MTF at Nyquist −11.6 %** — about 1 % of SNR and
1.2 % of resolution per 1 % of pupil diameter. The 40,000 e⁻ requirement **fails at
both ends** (106,631 → 86,561 e⁻). Karen's six lab readings, 35,500 → 55,750 e⁻, all
sit *below* the model, inverting to an implied per-mirror reflectance of R ≈
0.990–0.993 against the assumed 0.98.

**Regime.** `extended` — the blackbody fills the FOV, so `background_e` = 0 by design
and the only background terms are warm-optics near-field and dark. The bench runs as
`exo` with a placeholder `sensor_altitude_m` (registry Gap 42).

**Takeaway.** **Undersizing is not a background-control knob.** Signal and near-field
fall together because both come from the same effective pupil — the physics the
deleted `optics.nearfield_fraction` "leakage" knob concealed by letting a cold stop
attenuate in-cone emission it cannot touch. The levers that actually scale the
near-field are optics temperature and coating emissivity. And the 57 % spread across
cold-stop *positions* is what the new rules cannot explain and should not fit: with a
true aperture stop, position cannot move the background, so a monotone rise says the
stop has stopped being the aperture stop — a finding for the mechanical team, recorded
as an accepted Gap 128 limitation.

**Where to go deeper.** `scenarios/07_karen_test_engineer/7.4_cold_stop_sweep/`.
A GUI baseline ships.

### 7.5 — Performance at Temperature Extremes

**Mission setup.** A TVAC sweep of the FPA operating temperature from 70 to 95 K,
imaging the 300 K chamber shroud. Karen measured dark current at each point — it goes
*super-Arrhenius* above ~85 K — and QE at three. She needs SNR and NEDT versus
temperature, the noise budget as dark grows, the QE(T)-versus-dark split, and an
operating point with margin against the acceptance spec.

**Key inputs.**

| Quantity | Value |
|---|---|
| Optics | f/2.0, net τ = 0.74; train modelled as 3 × R = 0.98 + AR cold window (ε_emit 0.06) |
| Scene | 300 K chamber shroud, fills the aperture |
| Sweep | FPA temperature 70 – 95 K, measured $J(T)$ driving `detector.dark_rate_e_per_s` |
| QE | interpolated from three measured points; every run repeated with QE frozen at 77 K |
| Integration | 0.6 ms |
| Spec | SNR ≥ 750 **and** NEDT ≤ 35 mK |

**Headline results.** The measured dark curve matches an Arrhenius fit
($E_a$ = 0.240 eV) exactly through 82 K and then diverges catastrophically:
**+10 % at 85 K, +90 % at 88 K, +201.8 % at 90 K, +735.8 % at 95 K** (395,723,319
against a fitted 47,345,161 e⁻/s). Across the sweep SNR falls 814.7 → 674.6 and NEDT
rises 34.01 → 41.07 mK, driven by dark shot noise climbing **0.9 → 466.5 e⁻ RMS**
from negligible to the second-largest term. Over 70 → 95 K **QE falls 9 % while dark
current rises 294,612×**, and NEDT with QE(T) versus QE frozen differs by only a few
percent. Spec holds through **82 K** (NEDT 34.88 mK, 0.1 mK of margin); 85 K fails on
NEDT. The correctly-modelled warm-optics near-field (Gap 128 raised it 7,496 →
31,840 e⁻) costs ~6 K of the compliant range the ε = 1 − τ fallacy had appeared to
buy. *(Key Results recommends operating at 79 K with a 3 K guard band; the next-steps
list says 85 K, the first temperature the same table fails on.)*

**Regime.** `extended` — the 300 K shroud fills the aperture, so the background
photon term is skipped and the budget is signal-shot + dark-shot + read + near-field
+ quantization.

**Takeaway.** **Extrapolating a cold-side activation energy is the failure mode this
test exists to catch**: the Arrhenius line would call 95 K eight times better than it
is, because above the knee a different physical mechanism (defect-assisted tunneling)
dominates and no single $E_a$ fits both regimes. The guard band protects against
cooler drift *and* against the NEDT slope steepening from ~0.25 mK/K near the
compliance edge to ~1.4 mK/K past 92 K.

**Where to go deeper.** `scenarios/07_karen_test_engineer/7.5_environmental_temp_extremes/`.
A GUI baseline ships.

---

## Persona 8 — Interpolation Demonstrations (a tool demonstration, not a persona)

Folder 08 sits deliberately outside the closed thirty-five-scenario catalog. It has no
persona and no mission owner — it exists to demonstrate the per-family MODTRAN
atmosphere interpolator (`scripts/synth_modtran/family_interpolate.py`) with runnable
examples, and it follows the same scenario-trio convention as everything else.

### 8.1 — Off-Nadir Angle Interpolation

**Mission setup.** A customer requirement lands at 37.5° off-nadir, which is not one of
the MODTRAN run matrix's zenith-fan points (0°, 30°, 45°, 60°, all `us_standard`,
100 km sensor, nadir target). Does interpolating between the two bracketing runs
actually beat grabbing the nearest one?

**Key inputs.**

| Quantity | Value |
|---|---|
| Family | `zenith_fan_us_standard` — real MODTRAN 6 runs A1/B1/B2/B3 |
| Query | 37.5° path zenith |
| Bracketing runs | B1 at 30°, B2 at 45° |
| Method | linear in $\log \tau$, on the **airmass** axis $\sec\theta$ (CU-160) |
| Band | 3.5 – 5.0 µm |

**Headline results.** A holdout test predicts the real 45° run from its 30° and 60°
neighbours and compares against ground truth (in-band τ = 0.4988): interpolating in
$\log\tau$ **linear in angle** gives 0.4785, a **−4.07 %** error; **linear in airmass**
gives 0.4983, **−0.10 %**; nearest-neighbour (30°) gives 0.5329, **+6.84 %**. At the
actual 37.5° query, interpolated τ is 0.5185 with chain SNR 552.1, against
nearest-neighbour τ 0.4988 and SNR 541.6 — a nearest-neighbour error of **−3.8 % in
transmittance and −1.9 % in SNR**.

**Regime.** Not a regime study — one atmosphere-data-source comparison fed through an
identical chain config evaluated at the true 37.5° geometry, isolating the data-source
effect.

**Takeaway.** The method beats nearest-neighbour by about 1.7× against real ground
truth, and the residual that remained had a knowable cause with a 40× fix: optical depth
scales with airmass, not angle. The axis correction was a coordinate transform, not new
data, and it now governs the shipped atmosphere library too.

**Where to go deeper.** `scenarios/08_interpolation_demonstrations/8.1_off_nadir_angle_interpolation/`.
A GUI baseline ships.

### 8.2 — Target-Altitude Interpolation

**Mission setup.** A stratospheric-sensor mission needs atmosphere data for a target at
15 km — not one of the altitude ladder's points (0, 1, 5, 10, 20, 29 km, all
`midlat_summer`, 35 km sensor, nadir). Same method as 8.1, a different axis type, to
show the tool generalizes.

**Key inputs.**

| Quantity | Value |
|---|---|
| Family | `altitude_ladder_stratospheric` — **synthetic** tape7 data |
| Query | 15 km target altitude |
| Ladder spacing | 1, 4, 5, 10, 9 km gaps — deliberately non-uniform |
| Band | 8 – 12 µm |

**Headline results.** The ladder reads in-band τ 0.5774 (0 km), 0.7039 (1 km), 0.8822
(5 km), 0.9151 (10 km), **0.9291 interpolated at 15 km**, 0.9447 (20 km), 0.9790
(29 km). Nearest-neighbour selection (20 km) is **+1.7 % in transmittance** and **+0.7 %
in full-chain SNR** — the SNR error is smaller because the extended-scene
target/background contrast partially cancels atmosphere effects common to both terms.
*The walkthrough is explicit that the +0.7 % SNR figure was carried forward, not
re-measured, in the last refresh sweep: the runner's chain half needs a generated
synthetic MODTRAN set that is absent on a clean checkout.*

**Regime.** `extended`. Reproducing the scenario requires
`python scripts/generate_synthetic_tape7.py` first; the runner now names that
prerequisite rather than failing with a bare `FileNotFoundError`.

**Takeaway.** The 15 km query lands in the ladder's widest gap, which is exactly where
nearest-neighbour is weakest and interpolation earns its keep. The method does not care
whether the free axis is an angle or an altitude — it only needs monotone behaviour in
optical depth along that axis. Note the recurring friction: full-well saturation
silently zeroed the atmosphere effect on the first attempt, the third scenario to hit
that failure mode.

**Where to go deeper.** `scenarios/08_interpolation_demonstrations/8.2_target_altitude_interpolation/`.
A GUI baseline ships (it uses an inline builder and does not need the synthetic set).

### 8.3 — Boost-Phase Target-Altitude Sweep (skeleton)

**Mission setup.** A space-based MWIR sensor in a 500 km orbit tracks a booster
continuously from launch to burnout. As the booster climbs, the absorbing column between
it and the sensor shortens. Can one config sweep `geometry.target_altitude_m` from 0 to
300 km against the shipped interpolated library and produce physically sensible τ and
SNR?

**Key inputs.**

| Quantity | Value |
|---|---|
| Sensor / band | 500 km LEO, nadir; 3 – 5 µm |
| Target | 900 K plume, 4 m² |
| Atmosphere | `interpolated`, `midlat_summer_ladders` (real MODTRAN, 5 cm⁻¹ FWHM slit) |
| Interpolation axes | `sensor_altitude_m,target_altitude_m` |
| Sweep | target altitude 0 – 300 km |

**Headline results.** Three regimes. **Interpolated (0–29 km):** τ_up rises 0.4143 →
0.9425 and SNR 304.33 → 485.23. **Pending (29–100 km):** above the ladder's 29 km
ceiling but below the 100 km atmosphere top, so the interpolator refuses the query and
the script marks the rungs **PENDING** rather than inventing numbers — this band is the
acceptance driver for the MODTRAN boost-ladder expansion. **Vacuum (≥ 100 km):**
τ_up ≡ 1.0000 by the Gap 95 exo-altitude leg, with SNR 590.18 (100 km) → 1183.67
(300 km).

**Regime.** `sub_pixel`, locked by `source.regime_override`. A 4 m² plume at LEO slant
range subtends ≈4 µrad against a ~16.7 µrad IFOV — 0.22× the PSF FWHM, too large for the
point-source approximation and far too small to fill a pixel.

**Takeaway.** SNR keeps rising across the vacuum leg even with τ pinned at 1, and the
scenario separates the two causes explicitly so the climb is not misread as residual
absorption: the slant range is *closing*, from 400 km to 200 km, so the plume's fill
fraction grows. The engineering lesson is in the friction note — for a sweep, check the
saturation envelope at **both** ends, because here the brightest case is the last rung,
not the first.

**Where to go deeper.** `scenarios/08_interpolation_demonstrations/8.3_boost_phase_target_altitude_sweep/`.
**No GUI baseline ships.**

---

## Direction-General Scenarios (folder 10)

Folder 10 is not a persona either. It is the acceptance suite for ADR-0011 and the
Geometry-Flexibility work: one scenario per cell of the observer × target matrix that
RADIANT could not previously *express*, because `core/viewing_triangle.py` rejected a
sensor below its target and the canonical target-side path zenith $\theta_o$ was
bounded to $[0, \pi/2)$. Each scenario is a Category-D validation with independent
cross-checks, and each reports the dual-path consistency residual explicitly. The
fourth member of the folder, 10.2, is covered at full depth as a case study.

### 10.1 — Ground-to-Air MWIR Detection

**Mission setup.** A range test engineer has a ground-based MWIR search-and-track
camera on a tripod at a sea-level desert range; the trial target is a small turbojet
UAS cruising at 10 km, at night. The test plan sweeps the camera from straight up down
to 30° elevation and asks the ordinary questions: what does pointing elevation cost,
how far can the target be held, and does any of it agree with MODTRAN?

**Key inputs.**

| Quantity | Value |
|---|---|
| Optics | 100 mm / 200 mm (f/2.0), τ = 0.75 |
| Modelled train | 3 × R = 0.98 mirror + AR cold window ⇒ emitting ε = 0.06, not the datasheet's 25 % |
| Detector | 15 µm pitch, QE 75 %, dark 5 × 10⁴ e⁻/s, read 250 e⁻ RMS, 11 Me⁻ well |
| Band / integration | 3.0 – 5.0 µm / 0.5 ms |
| Target | 550 K nozzle, ε = 0.90, 2.827 × 10⁻³ m² at 10 km |
| Atmosphere / illumination | `simple`, midlat summer, 23 km visibility, rural aerosol / night |
| Sweep | sensor-side zenith $\zeta_{low}$ = 0 → 60° (elevation 90 → 30°) |

**Headline results.** At the nominal 60°-elevation point: slant range 11,543.99 m,
band-mean τ 0.4520, signal 8.062 × 10⁴ e⁻ against a sky background of 1.507 × 10⁵ e⁻,
**SNR 144.64, NEDT 610.8 mK**. Over the whole sweep (90° → 30° elevation) τ falls
0.4995 → 0.2668, signal falls **7.21×** and SNR 204.52 → 29.24. The extra factor over
the 3.98× inverse-square loss is air mass; meanwhile **up-path radiance rises 64.1 %**
(0.4388 → 0.7203 W/m²/sr), which is Kirchhoff, not a sign error — the same extra
absorbing column is an extra emitting one. Detection range (SNR = 5), walked with the
full chain along the real ray, runs **66.88 km at the zenith down to 44.20 km at 60°**.
RADIANT's own `detection_range_m` metric is deliberately **absent**, with a named
result-typed failure: the continuation past a 10 km target is still inside the
atmosphere and the metric layer has no altitude-resolved extinction profile to
integrate. *(The Gap-128 retune paragraph in §2 reports post-retune values of SNR
142.23 and NEDT 621.2 mK that the sweep table below it does not carry.)*

**Regime.** `point_source` — the nozzle's angular extent is 0.0602 of the PSF FWHM,
inside the ≤ 0.10 bound RADIANT enforces, and EE_box (0.5941) is applied once to the
target term only. Eleven ground-projection metrics are off by scene class, and GSD
stays absent even when the group is force-enabled: the ground-plane cosine projection
is undefined at an incidence angle of 150°.

**Takeaway.** The MODTRAN anchor is reported as a **characterisation, not an
agreement claim**: τ is systematically too transparent in the MWIR (+29.5 % on a 1 km
column, converging to +9.3 % by 20 km) and up-path radiance is too low (−45.3 % at the
scenario's own geometry), both pushing the same way, so **the quoted SNR should be
read as ≈ 40–50 % optimistic in absolute terms with the trends reliable** — which is
all a pointing-elevation trade needs.

**Where to go deeper.** `scenarios/10_direction_general/10.1_ground_to_air_mwir_detection/`.
A GUI baseline ships.

### 10.3 — Ground-to-Space SST in the Visible Band

**Mission setup.** A space-surveillance site runs a 1 m visible tracking telescope on
a small LEO object at 700 km during the terminator window: the sun is 12° below the
*site's* horizon, so the sky at the telescope is dark while the object overhead is
still in full sunlight. Before ADR-0011 the scene was doubly inexpressible — the
sensor had to be above the target, and the sun was hard-bounded above the horizon.

**Key inputs.**

| Quantity | Value |
|---|---|
| Site / telescope | 900 m MSL / 1.000 m aperture, f/10, 60 % transmission |
| Band / detector | 400 – 900 nm / 15 µm pitch, QE 80 %, read 5 e⁻ RMS, 400 ke⁻ well |
| Exposure | 5 ms (set by tracking accuracy, not the well) |
| Target | 700 km, ρ = 0.25, $A_{proj}$ = 1.00 m², solar phase 35° |
| Target door | `source.target.user_intensity_path` — a measured $I(\lambda)$ CSV |
| Pointing / sun | $\zeta_{low}$ = 20° / solar depression 12°, relative azimuth 45° |
| Turbulence / visibility | HV-5/7 $C_n^2$ profile / 100 km |

**Headline results.** At the nominal tasking: band-mean $\tau_{up}$ 0.7652, Fried
parameter **$r_0$ = 19.820 cm**, **EE_box 0.12075**, signal 49,220 e⁻, **SNR 221.78**,
detection range (SNR = 3) 24,678 km. The measurement is decisively
**seeing-limited**: seeing FWHM 3.214 µrad (0.663″) against diffraction's 0.793 µrad,
a ratio of 4.05, and turbulence takes MTF at Nyquist from 0.46250 to **0.00862** while
RER falls 0.7704 → 0.3317. Across the pass ($\zeta_{low}$ 0 → 75°) SNR falls 6.6×,
with transmittance contributing only 1.56× and $r_0$ shrinking as
$\sec\zeta^{-3/5}$ — since CU-253 corrected the Rayleigh term, **seeing plus
inverse-square, not extinction, is most of the decay**. Four anchors: the closed-form
point-source identity reproduces the chain signal to 0.000 %, the apparent magnitude
lands at 5.54 mag (inside the 4–8 naked-eye-satellite band), transmittance
reciprocity holds to 1.1 × 10⁻¹⁶, and **published astronomical extinction FAILS** —
0.261 mag/airmass against a published 0.12–0.20 band. *(Two stale figures ride along:
the deliberate-non-anchor paragraph still calls that failure 1.4× the published top
where the refreshed anchor reads 1.3×, and the closing to-do list quotes a daylight
sky pedestal of 3.2774 W/m²/sr/µm where §9 computes 3.8794.)*

**Regime.** `point_source`, entered through the intensity door because RADIANT has no
reflective point-source door: the reflective path multiplies by
$\max(\cos\theta_s, 0)$, identically zero in exactly the terminator window this
scenario exists to model. That door also *strips* the sun, so $\tau_{sun}$ never
multiplies the target term and the analyst owns the illumination gate.

**Takeaway.** **The 1 m aperture buys photons, not resolution** — doubling $D$ would
leave the long-exposure blur diameter unchanged and only double $D/r_0$. The seeing
itself should be read as optimistic by roughly 2×: the Hufnagel-Valley ground term is
conventionally above *ground* level but the model evaluates it against MSL, so a
900 m site silently loses its own boundary layer. And the extinction anchor's failure
is instructive rather than fatal: the MODTRAN-scored comparison on the same band
*improved* while this one worsened, which localises the residual to aerosol
attribution rather than the gas fit.

**Where to go deeper.** `scenarios/10_direction_general/10.3_ground_to_space_sst_visible/`.
A GUI baseline ships.

### 10.4 — LEO-to-GEO Space-to-Space SDA

**Mission setup.** A 500 km LEO host carries a 35 cm MWIR staring telescope pointed
*up* at the geostationary belt. Three numbers size the tasking plan: can it detect a
reference GEO communications bus in eclipse and at what single-frame SNR, how far past
GEO does that capability extend, and does the relative angular rate force rate-tracking
or permit a stare? The physics was never the blocker — both endpoints sit above
`h_atm_top`, so the path is vacuum by construction — only the altitude-ordering gate
was.

**Key inputs.**

| Quantity | Value |
|---|---|
| Telescope | 350 mm / 2100 mm (f/6.0), 25 % obscuration, 60 % transmission, 0.05 waves WFE |
| Detector | 18 µm pitch (8.571 µrad IFOV), QE 75 %, dark 1000 e⁻/s, read 25 e⁻ RMS, 100 ke⁻ well |
| Band / integration | 3.5 – 5.0 µm / 500 ms rate-tracked stare |
| Geometry | 500 km LEO → 35,786 km GEO, $\zeta_{low}$ = 0°, night (eclipse) |
| Target | 280 K grey body, ε = 0.85, 20 m² projected area |
| Rate-track residual | 1 % of the open-loop LOS rate |

**Headline results.** EE_box 0.245670, in-pixel signal 1295.78 e⁻, total noise 49.233
e⁻ RMS, **SNR 26.32**, **detection range (SNR = 5) 94,438 km** — 2.67× the LEO→GEO
range, so the belt sits comfortably inside the single-frame horizon. Background shot
noise is **exactly zero**: the up-looking LOS exits into deep space and selects
`ColdSpaceBackground`. The kinematics are the design driver: LEO 1108.508 µrad/s
against GEO 72.940 µrad/s gives an open-loop LOS rate of **128.709 µrad/s**, which
drags the point source across **7.5 pixels** in a 500 ms inertially-fixed stare,
collapsing EE_box to 0.0597 and SNR to 8.29. **Open-loop SNR peaks at 250 ms and then
falls** — past that the smear kernel grows faster than $\sqrt t$ — while the
rate-tracked curve keeps rising as $\sqrt t$ because the scene is background-free.
Every vacuum transport identity is checked bitwise, not toleranced. *(The §4.3 prose
and cross-check 3 both still carry pre-CU-355 numbers — an open-loop collapse of
"0.223 → 0.054, SNR 24.5 → 7.6", and a hand-vs-chain signal of 1177.2 e⁻ against the
refreshed 1295.78 e⁻.)*

**Regime.** `point_source`, finalized in `OpticsStage`. A 20 m² bus at 35,286 km
subtends 0.1267 µrad — 68× smaller than the detector IFOV and far inside the 14.8 µrad
diffraction core — so all the flux lands in one PSF and the in-pixel signal follows
inverse-square, which is what makes a detection range meaningful at all. The reported
NEDT of 1005 mK is *not* a figure of merit here: it is a radiance-contrast sensitivity
defined against a scene that fills the pixel, and this target fills 0.02 % of one.

**Takeaway.** **The tracking loop, not the aperture or the signature, is the design
driver.** A 1 % rate residual holds smear to 0.075 px and the full 500 ms is usable; an
untracked stare throws away two-thirds of the SNR and has an optimum three times
shorter. The scenario also retired a framework defect found here and in 10.2
independently: the detection-range solver froze the noise at the reference range, and
since signal shot noise carries 51 % of the noise power here, that made $R_{det}$
conservative by 15.2 % and dependent on where the chain was evaluated (CU-263).

**Where to go deeper.** `scenarios/10_direction_general/10.4_leo_to_geo_exo/`.
A GUI baseline ships.
