# Atmosphere Models

*Persona: Sarah (systems engineer), Priya (radiometrist), Marcus (SDA analyst)*

The physics of RADIANT's two atmosphere model families — the closed-form **simple
parametric** model and the **library-backed** interpolated / tabulated / MODTRAN-import
models — organized by model rather than by change history. What each model computes, from
what first principles, and which measurement or test holds each claim in place.

This document is the *physics*. The measured accuracy of every model against the MODTRAN
run set lives in [`docs/validation/atmosphere_modtran_parity.md`](../validation/atmosphere_modtran_parity.md);
the architecture contract (`AtmosphericQuantities`, backend dispatch, guard structure)
lives in [`docs/architecture/RADIANT_Atmosphere.md`](../architecture/RADIANT_Atmosphere.md);
which model an operator should reach for lives in `docs/guides/atmosphere_selection.md`.
Atmospheric **turbulence** is a spatial effect and is documented with the rest of the MTF
cascade in [`docs/theory/spatial_model.md`](spatial_model.md) §7; it is not repeated here.

**Citation convention.** Every quantitative claim below carries its provenance in the form
*Record:* the CU entry (with resolution date) that measured it — *Enforced by:* the test
that pins it. A number whose only home is a CU record, with no committed test asserting it,
is marked **(record only)** so a reader knows its standing. Nothing in this document is a
normative claim without one of the two.

**Symbols.** $\lambda$ wavelength [µm]; $\zeta$ zenith angle at a path segment's **lower**
endpoint [rad]; $\theta_s$ solar zenith [rad]; $\Theta$ scattering angle [rad];
$h$ altitude above mean sea level [m]; $H_i$ species scale height [m]; $\tau$ transmittance
[–]; $\mathrm{OD}$ optical depth [–]; $m$ air mass [–]; $\sigma$ volume extinction
coefficient [km⁻¹]; $w$ precipitable water [cm]; $\omega_0$ single-scattering albedo [–];
$B(\lambda,T)$ Planck spectral radiance [W/m²/sr/µm]; $L$ radiance [W/m²/sr/µm];
$E$ irradiance [W/m²/µm]; $R_E = 6.371\times10^{6}$ m.

---

## 1. Two families, one contract

Every model in RADIANT delivers the same product bundle — a transmittance, an upwelling
path radiance, a downwelling emission term, and (for the composed topologies) the segment
products a path is assembled from. What differs is where the numbers come from:

| Family | Members | Physics origin | Geometry response |
|---|---|---|---|
| Closed-form parametric | `simple` | Beer-Lambert on four species, calibrated band-by-band against MODTRAN | Recomputed for every geometry |
| Library-backed | `interpolated`, `tabulated`, `modtran` (tape7 import) | Real MODTRAN 6 radiative transfer, stored and served | `interpolated` interpolates over declared axes; the other two are geometry-agnostic files |
| Identity | `exo` | $\tau \equiv 1$, $L \equiv 0$ — the cosmic vacuum | None (exact) |

The simple model is the only backend that can serve an arbitrary path topology
(down-looking, up-looking, level, grazing, twilight), because the segment evaluators are
built on its species model. The library families serve the topologies their runs actually
measured, and refuse the rest rather than approximating them.

---

## 2. The simple parametric model

### 2.1 Beer-Lambert structure

Transmittance along a path is the exponential of a slant optical depth built from four
species, each carried on its own exponential density profile:

$$\tau_{atm}(\lambda) \;=\; \exp\!\left[-\mathrm{OD}_{tot}(\lambda)\right],
\qquad
\mathrm{OD}_{tot}(\lambda) \;=\; \sum_{i} m_i \,\mathrm{OD}_{i,\mathrm{vert}}(\lambda)$$

with $i \in \{\text{mol}, \text{aer}, \text{h2o}, \text{gas}\}$ and $m_i$ the species air
mass of §2.7. The **vertical** column each species presents between two altitudes is the
analytic exponential integral

$$\mathrm{col}_i(h_{lo}, h_{hi}) \;=\; \int_{h_{lo}}^{h_{hi}} e^{-h/H_i}\,\mathrm{d}h
\;=\; H_i\left(e^{-h_{lo}/H_i} - e^{-h_{hi}/H_i}\right) \quad [\text{km}]$$

which is endpoint-symmetric, so one segment read in either direction presents one column —
the structural reason transmittance is single-valued (§2.12).

Scale heights: $H_{\text{mol}} = 8000$ m, $H_{\text{aer}} = 1200$ m, $H_{\text{h2o}} = 2000$ m.
The well-mixed-gas floor rides the molecular profile by construction (§2.5).

*Record:* module constants `H_MOL_M` / `H_AER_M` / `H_H2O_M`, `src/radiant/atmosphere/simple.py`.
*Enforced by:* `src/radiant/atmosphere/tests/test_simple.py`, and the segment↔evaluate
bit-identity test in `src/radiant/atmosphere/tests/test_segment_simple.py`.

### 2.2 Molecular (Rayleigh) scattering

The published Rayleigh constant is a **total vertical optical depth**, dimensionless — not
a per-km coefficient:

$$\tau_{R,\mathrm{vert}}(\lambda) \;=\; 0.0088\,\lambda_{\mu m}^{-4.09}$$

At $\lambda = 0.55$ µm this evaluates to $0.101484$, against the published
whole-atmosphere value $0.0973$–$0.10$ (Hansen & Travis 1974; Bucholtz 1995). The
sea-level volume extinction the slant integral needs is **derived** from it through the
exponential profile's own identity $\tau_{\mathrm{vert}} = \sigma_0 H$:

$$\sigma_{\text{mol}}(\lambda) \;=\; \frac{\tau_{R,\mathrm{vert}}(\lambda)}{H_{\text{mol}}}
\;=\; 0.012686\ \mathrm{km^{-1}} \ \text{at}\ 0.55\ \mu\mathrm{m}
\quad (\text{published} \approx 0.0116\ \mathrm{km^{-1}})$$

and is scaled along the path by $e^{-h/H_{\text{mol}}}$.

Deriving $\sigma_0$ rather than storing it independently is the fix for CU-253, in which
the published optical depth was consumed *as* the km⁻¹ coefficient — inflating every
VIS/NIR molecular optical depth by exactly the column depth, $\approx 8\times$.

*Record:* CU-253, resolved 2026-07-28 (commit `d169feb`).
*Enforced by:* `src/radiant/atmosphere/tests/test_simple.py` (Rayleigh anchors); the
derivation is structural — one constant, one division.

### 2.3 Aerosol (Mie) extinction

Aerosol extinction at the reference wavelength is fit from the Koschmieder visibility
relation, then carried spectrally by an Ångström power law:

$$\sigma_{\text{aer}}(0.55\ \mu\mathrm{m}) \;=\; \frac{3.912}{V_{km}}\ \ [\mathrm{km^{-1}}],
\qquad
\sigma_{\text{aer}}(\lambda) \;=\; \sigma_{\text{aer}}(0.55)\left(\frac{\lambda}{0.55}\right)^{-\alpha}$$

The constant $3.912 = -\ln(0.02)$ is the 2 % contrast threshold defining meteorological
visibility. Three canonical aerosol regimes:

| Regime | Ångström $\alpha$ | Aerosol SSA $\omega_{\text{aer}}$ |
|---|---:|---:|
| `rural` | 1.3 | 0.95 |
| `urban` | 1.5 | 0.85 |
| `maritime` | 0.7 | 0.99 |

The power law is a **scattering** model: good in VIS/SWIR, weak but usable through the
MWIR, and wrong in the LWIR where real IR aerosol extinction is absorption-dominated and
roughly flat. It is therefore clamped at the MWIR–LWIR boundary
$\lambda_{\text{clamp}} = 5.0$ µm — beyond it the extinction is frozen at its 5 µm value
rather than decaying unphysically toward zero, and the model warns once per run when the
clamp engages.

*Record:* CU-088, resolved 2026-07-12 (`AEROSOL_CLAMP_WAVELENGTH_UM`). Aerosol scale
height 1.2 km. *Enforced by:* `src/radiant/atmosphere/tests/test_simple.py` (clamp
behaviour and the once-per-run warning).

### 2.4 Water vapour — the curve of growth

Water vapour is **not** linear in Beer's law over a real band, because the strong lines
saturate long before the windows between them do. The calibrated model is a 15-region
curve of growth:

$$\mathrm{OD}_{\mathrm{h2o}}(\lambda) \;=\; k(\lambda)\,w_{\mathrm{eff}}^{\,b(\lambda)}$$

where $w_{\mathrm{eff}}$ [cm] is the path water amount — total precipitable water times
the traversed fraction of the $H_{\mathrm{h2o}} = 2$ km exponential column. The exponent
is fit region by region against the real MODTRAN 6 water ladder (runs D4 / A1 / D5,
H₂O ×0.5 / ×1 / ×2): **sub-linear $b \approx 0.2$–$0.8$** in the saturated absorption
bands, **super-linear $b \approx 1.3$–$1.75$** in the LWIR where the e-type continuum
dominates and the absorber's own pressure broadening compounds with amount.

This replaced a five-Lorentzian line fit whose far wings made the MWIR water response
$\approx 5\times$ too steep.

Standard-profile water columns (McClatchey et al. 1972, AFCRL-72-0497, carried into
MODTRAN MODELs 1–6) supply the default when the operator selects a climate profile and
leaves the water column at its schema default:

| Profile | PWV [cm] | Profile | PWV [cm] |
|---|---:|---|---:|
| `tropical` | 4.11 | `midlat_winter` | 0.85 |
| `midlat_summer` | 2.92 | `subarctic_summer` | 2.08 |
| `us_standard` | 1.40 | `subarctic_winter` | 0.42 |

*Record:* CU-161, resolved 2026-07-18 (commit `0aebdda`); profile coupling Gap 57.
Generator `scripts/fit_simple_atmosphere_gas_bands.py`.
*Enforced by:* `src/radiant/atmosphere/tests/test_simple.py::test_cu161_water_ladder_anchor`,
`src/radiant/atmosphere/tests/test_profile_pwv_coupling.py`.

### 2.5 The well-mixed-gas absorption floor

Each of the same 15 regions carries a **water-independent** vertical optical depth — the
CO₂ 4.3 µm and 15 µm bands, N₂O, the O₃ 9.6 µm band, and O₂ / CH₄ overtones — in excess
of what Rayleigh and aerosol already supply:

$$\mathrm{OD}_{\text{region}}(w) \;=\; \mathrm{floor\_od} \;+\; k\,w_{\mathrm{eff}}^{\,b}$$

The floor rides the molecular scale height (CU-161 defines it as a fraction of the
molecular column), and it enters the single-scattering albedo denominator as a **pure
absorber** (§2.9). Its absence is what made the pre-CU-161 model attribute the MWIR CO₂
floor to water and evaluate $\omega_0 \approx 1$ for space columns.

The calibrated table, exactly as shipped (`_CALIBRATED_GAS_REGIONS`):

| Region [µm] | `floor_od` | $k$ | $b$ | Region [µm] | `floor_od` | $k$ | $b$ |
|---|---:|---:|---:|---|---:|---:|---:|
| 0.30–0.45 | 0.0000 | 0.0000 | 1.000 | 3.10–3.50 | 0.1366 | 0.5824 | 0.457 |
| 0.45–0.70 | 0.0000 | 0.0025 | 0.874 | 3.50–5.00 | 0.4497 | 0.0944 | 0.808 |
| 0.70–1.30 | 0.0000 | 0.1245 | 0.434 | 5.00–7.50 | 1.3543 | 1.7850 | 0.530 |
| 1.30–1.50 | 0.0000 | 1.0933 | 0.327 | 7.50–8.00 | 0.9424 | 0.9210 | 0.673 |
| 1.50–1.75 | 0.0133 | 0.0282 | 0.645 | 8.00–10.00 | 0.2751 | 0.0877 | 1.268 |
| 1.75–2.05 | 0.0000 | 1.1186 | 0.216 | 10.00–12.00 | 0.0471 | 0.0602 | 1.750 |
| 2.05–2.40 | 0.0725 | 0.0320 | 0.843 | 12.00–14.29 | 0.5956 | 0.1398 | 1.583 |
| 2.40–3.10 | 0.7434 | 0.9666 | 0.560 | | | | |

Spectral shape *within* a region is flat: the model's contract is band-integrated
fidelity, not line structure. Wavelengths outside 0.30–14.29 µm clamp to the edge regions'
calibration.

*Record:* CU-161, resolved 2026-07-18.
*Enforced by:* `src/radiant/atmosphere/tests/test_gas_region_blend.py::test_interior_wavelengths_keep_exact_table_coefficients`
(the table is read back from the model, so a silent edit fails).

### 2.6 The region-edge smoothstep blend

The table is piecewise-constant, but it is **not** read as a step function. Across each of
the fourteen interior region edges the three coefficients
$c \in \{\mathrm{floor\_od},\,k,\,b\}$ are joined by a $C^1$ smoothstep ramp of half-width
$h_w = 0.02$ µm (full width 0.04 µm):

$$u(\lambda) \;=\; \mathrm{clip}\!\left(\frac{1}{2} + \frac{\lambda - \lambda_{\text{edge}}}{2 h_w},\;0,\;1\right),
\qquad
S(u) \;=\; u^2\,(3 - 2u),
\qquad
c(\lambda) \;=\; c_{lo} + (c_{hi} - c_{lo})\,S(u)$$

with $S(0) = 0$, $S(1) = 1$, $S'(0) = S'(1) = 0$ — the ramp meets the flat calibrated
regions with matching value *and* slope — and $S(\tfrac12) = \tfrac12$, so the edge itself
carries the exact arithmetic mean of the two regions. At the 0.70 µm edge, for instance,
$k$ evaluates to $(0.0025 + 0.1245)/2 = 0.0635$ exactly.

Outside the ramps nothing changes: a $\lambda$ at or beyond $h_w$ from every edge keeps
the bit-identical calibrated coefficient. Every region is wider than $2 h_w$ — the
narrowest is 0.20 µm at 1.30–1.50 µm, five times the full ramp width — so no two ramps
overlap, which is the invariant that stops a future refit from silently invalidating the
blend.

Read literally, the step table made $\tau(\lambda)$ jump at every edge and made a band-mean
$\tau$ that straddled an edge **sampling-grid-dependent**. Both effects, and the size of
the adopted blend, are in the parity document §2.7.

$h_w$ is a documented module constant, not a schema parameter (the `KOSCHMIEDER`
precedent): it is a numerical property of the calibration table, not a tuneable physical
quantity.

*Record:* CU-267, resolved 2026-08-01, owner-ratified.
*Enforced by:* `src/radiant/atmosphere/tests/test_gas_region_blend.py` — 40 Level-0 tests,
including `test_blend_ramps_never_overlap`, `test_edge_value_is_the_mean_of_the_two_regions`,
`test_coefficient_derivative_matches_analytic_smoothstep`, and the bit-exact hand anchor
`test_edge_midpoint_hand_value_at_0p70_um`.

### 2.7 Air mass — plane-parallel inside 80°, per-species spherical past it

The slant path length over the *absorbing* vertical extent of the segment is

$$L_{\text{slant}} \;=\; \frac{\Delta h_{\text{absorbing}}}{\cos\zeta},
\qquad
\Delta h_{\text{absorbing}} \;=\; \min\!\left(|h_{sen} - h_{tgt}|,\; h_{\text{atm,top}} - \min(h_{sen}, h_{tgt})\right)$$

so a ground site viewing a 700 km target traverses 100 km of air, not 700 km. The stored
air mass is therefore exactly $m = \sec\zeta$, and a wholly exo path returns $m = 1$ by the
`ExoAtmosphere` convention.

$\sec\zeta$ is the honest plane-parallel primitive and it is used unchanged for
$\zeta \le \texttt{SPHERICAL\_SWITCH\_RAD} = 80°$. Past 80° every column — the observer
column, the full ground-to-sensor column, the solar column, and any `ColumnSegmentSpec` —
hands over to the exact spherical slant integral, **per species**:

$$m_i \;=\; \frac{S_i\!\left(r_0;\, h_{lo} \to h_{hi};\, H_i\right)}{\mathrm{col}_i},
\qquad
r_0 \;=\; (R_E + h_{lo})\,\sin\zeta_{lo}$$

where $S_i$ is the density-weighted spherical column about the ray's perigee radius $r_0$
(`grazing_column.grazing_slant_column_km`, a graded-grid quadrature anchored analytically
against Chapman's grazing limit). The well-mixed-gas floor rides $m_{\text{mol}}$, because
CU-161 defines it as a fraction of the molecular column.

Three properties matter, and all three are measured rather than asserted:

- **It has to be per species.** Water vapour's 2 km profile hugs the tangent point far
  harder than the 8 km molecular one, so a single corrected scalar cannot serve both — at
  $\zeta = 89.4°$ the two diverge by $2.27\times$ in error.
- **The direction is toward more signal.** The spherical air mass is always the smaller
  one, so transmittance and SNR move **up** past 80° and never down.
- **It is a step, not a blend.** The size of that step, and why 80° rather than the 89.5°
  ceiling, are in the parity document §2.4.

The solar column's old 89.5° clamp retires with the hand-over: the spherical route has no
ceiling, so a twilight scene at $\theta_s = 89.9°$ now gets its own column.
`ZENITH_CEILING_RAD` (89.5°) still bounds the *observer* zenith, because that is the
column-air-mass validity ceiling for the plane-parallel form.

*Record:* CU-274, resolved 2026-07-29 (deleted the earlier geometric-chord branch);
CU-224 checklist item ex-CU-275, landed 2026-08-01 (extended the hand-over to the
down-looking and solar columns).
*Enforced by:* `src/radiant/atmosphere/tests/test_near_horizon_air_mass.py` (per-species
divergence, hand-over predicate, monotonicity, sign) and
`src/radiant/atmosphere/tests/test_near_horizon_handover.py` (zero drift inside the band,
step bound, all three call sites).

### 2.8 One linearisation convention — the slant column

Two calibrated terms — the water curve of growth and the gas floor — are *column* optical
depths, the integral of no local coefficient. Wherever the model needs a **local**
extinction (the single-scatter weights of §2.9, the level arm of §2.12), they must be
linearised: divided by a reference column to produce an equivalent per-km coefficient.

Because the curve of growth is sub-linear, that choice is not neutral. Linearising against
the vertical column instead of the slant one scales the effective water weight by
$m_{\mathrm{h2o}}^{\,b-1}$, and $\omega_0$ with it, wherever water absorbs.

**All three evaluators now linearise against the slant column** — the amount actually
traversed, which is what the linearisation is *of*. `column_segment_optical_depth`
publishes `slant_column_mol_km` / `_aer_km` / `_h2o_km` provenance under the same key names
the near-horizon branch already used, so the convention is inspectable (Rule 16).

Note the scope precisely: this is the convention for the **linearised local weights**. The
optical depth itself is still built as *vertical column × species air mass* (§2.7); the two
are consistent because $m_i$ is defined as the ratio of the slant to the vertical column.

At $\zeta = 0$ the air mass is exactly 1, so slant $\equiv$ vertical and every vertical
anchor is bit-identical across this change.

*Record:* CU-320, resolved 2026-08-02. Its own closure records two corrections to the
filed claim: the change is results-affecting for the up-looking/level *scattered* sky at
any $\zeta > 0$, not only past 80°; and against MODTRAN it is accuracy-**neutral** — the
win is cross-evaluator consistency (parity document §2.4).
*Enforced by:* `src/radiant/atmosphere/tests/test_segment_simple.py` (provenance keys),
`tests/integration/test_species_split_anchors.py` (the vertical K-ladder anchors, which
must not move).

### 2.9 Single-scatter solar path radiance

The scattered term on any column is the classic single-scatter source weighted by the
column's own emissivity-equivalent $1-\tau$:

$$L_{\text{path,scat}}(\lambda) \;=\; \frac{E_{\text{sun}}(\lambda)}{4\pi}\,\cos\theta_s\;\omega_0(\lambda)\;P(\Theta,\lambda)\;\bigl[1 - \tau_{atm}(\lambda)\bigr]$$

with $E_{\text{sun}}$ the top-of-atmosphere solar spectral irradiance and $4\pi$ the
full-sphere phase-function normalization.

**Single-scattering albedo.** Extinction-weighted, with the pure absorbers in the
denominator only:

$$\omega_0(\lambda) \;=\; \frac{\sigma_{\text{mol}} + \omega_{\text{aer}}\,\sigma_{\text{aer}}}
{\sigma_{\text{mol}} + \sigma_{\text{aer}} + \sigma_{\mathrm{h2o}} + \sigma_{\text{gas}}}$$

**Phase function.** Combined by *scattering* cross-section — a photon absorbed by water
does not contribute scattered radiance at all — and normalized so an isotropic scatterer
gives $P \equiv 1$:

$$P(\Theta,\lambda) \;=\; \frac{\sigma_{\text{mol}}\,P_R(\Theta) + \omega_{\text{aer}}\,\sigma_{\text{aer}}\,P_{HG}(\Theta)}
{\sigma_{\text{mol}} + \omega_{\text{aer}}\,\sigma_{\text{aer}}},$$

$$P_R(\Theta) = \tfrac{3}{4}\left(1 + \cos^2\Theta\right),
\qquad
P_{HG}(\Theta) = \frac{1 - g^2}{\left(1 + g^2 - 2g\cos\Theta\right)^{3/2}},
\qquad g = 0.7$$

**Where the species proportions are evaluated — the lower endpoint.** $\omega_0$ and
$P(\Theta)$ depend on the *relative* proportions of the four species, and those change with
altitude. All evaluators take them at the segment's **lower endpoint**: the densest air in
the path, the end the `L_toward_lower` product emerges from, and the choice the grazing and
level evaluators always made.

The retired alternative — the segment's arithmetic-mean altitude — put the weights, for
any column taller than $\approx 40$ km, above the altitude where the aerosol and water
coefficients underflow to zero in double precision. The consequence was not a small bias
but a silent model substitution: $\omega_0$ evaluated to exactly 1 (no absorption at all)
and the Henyey-Greenstein forward peak collapsed onto the isotropic-Rayleigh 1.5, so a tall
column scattered as if the atmosphere held no aerosol whatever `visibility_km` said. The
adoption measurement is in the parity document §2.3.

This term is **provisional below 3 µm**. Single scattering under-predicts the daytime
VIS/NIR sky, where multiple scattering dominates; a `UserWarning` fires when the evaluation
grid extends below `SCATTERED_SKY_PROVISIONAL_MAX_UM = 3.0` µm *and* a solar geometry with
the sun above the local horizon is supplied. A pure-thermal MWIR/LWIR call warns about
nothing, and neither does a night scene on a VIS grid.

*Record:* CU-260, folded into CU-224, adopted 2026-08-01; Gap 38 for the residual VIS
aerosol accuracy.
*Enforced by:* `tests/integration/test_species_split_anchors.py` (25 rung × band ratios,
the adoption criterion, and the thermal-control inertness),
`src/radiant/atmosphere/tests/test_sky_radiance.py` (the provisional-band warning).

### 2.10 Thermal path radiance — Kirchhoff emission at a height-resolved temperature

The thermal term on any column is a one-slab Kirchhoff graybody whose emissivity is
derived from the column's own transmittance (Rule 5 — never an independent input):

$$L_{\text{path,therm}}(\lambda) \;=\; \bigl[1 - \tau_{atm}(\lambda)\bigr]\,B\!\left(\lambda,\,T_{\text{eff}}(\lambda)\right)$$

It applies whether or not the sun is up — a night down-looking scene has scattered $\equiv 0$
and thermal $> 0$ — and it is computed by one module called from both directions
(`atmosphere/segment_thermal.py`).

**What $T_{\text{eff}}$ is.** It is the single temperature that makes this one-slab form
reproduce the **layered formal solution** of the segment's own non-isothermal air. Slice
the segment into $N$ sub-layers; layer $i$ has slant optical depth $\delta_i(\lambda)$ and
temperature $T_i$. Ordering the layers **from the end the radiation escapes**, the emergent
radiance is the discrete formal solution of the non-scattering LTE transfer equation:

$$L(\lambda) \;=\; \sum_i B(\lambda, T_i)\,\bigl(1 - e^{-\delta_i(\lambda)}\bigr)\,e^{-c_i(\lambda)},
\qquad
c_i(\lambda) = \sum_{j<i} \delta_j(\lambda)$$

The weights telescope exactly:

$$\sum_i \bigl(1 - e^{-\delta_i}\bigr) e^{-c_i} \;=\; 1 - e^{-\sum_i \delta_i} \;=\; 1 - \tau(\lambda)$$

so $L = (1-\tau)\,\langle B\rangle$ with $\langle B\rangle$ a convex combination of the
layer Planck functions, and

$$T_{\text{eff}}(\lambda) \;=\; B^{-1}\!\left(\langle B\rangle(\lambda)\right)$$

is guaranteed to lie between the coldest and warmest layer in the segment.

Three properties are structural, not fitted:

- **The total optical depth is untouched.** Only the altitude the emission is weighted at
  changes, so every $\tau$ in the model is bit-identical across this construction.
- **Isothermal is exact.** Every $T_i$ equal returns that temperature exactly, for every
  $\tau$, every direction and every layer count. A level arm is isothermal, so the level
  topologies keep a single exact graybody temperature.
- **Direction is geometry, not a fork.** `escape` names which endpoint the radiance leaves
  from. One model serves both directions: the down-looking `evaluate` term uses
  `escape="upper"` and the up-looking segment product `escape="lower"`. A direction-blind
  optical-depth-weighted mean temperature was measured against the same anchors and
  rejected — it degrades the MWIR everywhere, which is the measurement that forces escape
  into the model.

**Where the opacity sits in altitude.** The curve of growth fixes each species' *total*
column optical depth and says nothing about its vertical distribution, which is what the
weighting needs. That distribution is taken from first principles, with no fitted
coefficient:

- **Scattering species** (Rayleigh, aerosol) — extinction is proportional to number
  density, so the weighting profile is the species' own density scale height, unchanged.
- **Pressure-broadened absorbers** (the well-mixed-gas floor, water vapour) — a Lorentz
  line's absorption coefficient goes as number density *times* the collisional half-width,
  and the half-width goes as total pressure, so $\alpha \propto \rho_a\,p_{\text{air}}$ and
  the emission weighting rides the harmonic combination

$$H_{\text{emit}} \;=\; \left(\frac{1}{H_a} + \frac{1}{H_{\text{air}}}\right)^{-1}$$

  which takes the well-mixed floor from 8 km to **4 km** and water from 2 km to **1.6 km**.

The sub-layer count is a convergence-tested quadrature parameter, not a tuning knob:
`EMISSION_LAYERS_PER_SPECIES = 32`, whose discretisation error against a 512-per-species
reference is $\max|\Delta T_{\text{eff}}| = 0.016$ K over the whole anchor set — two orders
of magnitude below the model's own $\approx 4$ K accuracy against MODTRAN. Nothing in this
module therefore needs a `ParameterDef` (Rule 12).

**Vacuum limit.** A segment with no opacity has no emission to weight; the function falls
back to the temperature of its densest air so the value stays finite. The radiance it
multiplies is exactly zero there, so it is unobservable — it exists only so nothing returns
NaN (Rule 17).

*Record:* CU-321, resolved 2026-08-03 (owner-approved 2026-08-02), on top of CU-224
(resolved 2026-08-02), which added the thermal term to the down-looking direction at all —
before it, a pure-thermal LWIR down-looking scene had $L_{\text{path}} \equiv 0$ exactly.
*Enforced by:* `src/radiant/atmosphere/tests/test_emission_temperature.py` (the telescoping
identity, the isothermal and vacuum limits, the layer-count convergence),
`src/radiant/atmosphere/tests/test_downlooking_path_thermal.py` (the Planck form derived
from first principles, $\tau$ untouched, the up/down asymmetry), and
`tests/integration/test_emission_temperature_anchors.py` (the MODTRAN parity and
temperature-recovery scoreboards).

### 2.11 The hemispheric downwelling terms

Two products describe what falls on a *surface* — hemispheric irradiances, not directional
radiances, and consumed by the reflected-diffuse terms of the target and ground-background
arms.

**Thermal.** A target-anchored graybody on the **vertical** target → $h_{\text{atm,top}}$
column — the sky the target actually sees, so the sensor's altitude and viewing zenith
deliberately do not enter a hemispheric flux at the target:

$$E_{\text{sky,thermal}}(\lambda) \;=\; \left[1 - \tau_{\text{sky,vert}}(\lambda)^{D}\right]\,\pi\,B\!\left(\lambda,\,T(h_{tgt} + z_{em})\right),
\qquad
L_{\text{atm,down}}(\lambda) \;=\; \frac{E_{\text{sky,thermal}}(\lambda)}{\pi}$$

$T(\cdot)$ is the fixed-lapse ICAO standard-atmosphere lookup (6.5 K/km, floored at the
216.65 K tropopause above 11 km). The two constants are fit **jointly** to the real
up-looking MODTRAN H-runs: emission-height offset $z_{em} = 200$ m (downwelling is
dominated by near-surface air) and flux-diffusivity exponent $D = 1.1$ — below the textbook
Elsasser 1.66 because the curve-of-growth calibration to slant paths already absorbs part
of the hemispheric weighting.

Because $z_{em}$ and $D$ are fit jointly *through this one closed form*, a directional
path-radiance product cannot inherit the pair. That is why §2.10's height-resolved model
and this fitted graybody coexist deliberately: they are different products, not two
versions of one (Rule 27 does not apply). Re-fitting or retiring $z_{em}$ now that the
layered solution can compute what it approximates is a tracked refinement (CU-324).

**Scattered.** On the same vertical slab:

$$E_{\text{sky,scattered}}(\lambda) \;=\; E_{\text{TOA}}(\lambda)\,\cos\theta_s\;\omega_{0,\text{eff}}(\lambda,\ \text{aerosol})\;\bigl[1 - \tau_{\text{down,vert}}(\lambda)\bigr]$$

$\omega_{0,\text{eff}}$ is **not** the internal column $\omega_0$ of §2.9. It is a
MODTRAN-derived effective single-scattering albedo (`atmosphere/omega0_eff.py`): band-median
values per aerosol regime over VIS 0.4–0.7 / NIR 0.7–1.4 / SWIR 1.4–2.5 µm, edge-extended
outside, obtained by inverting *this closed form* against the real ground-level
diffuse-flux tables — so it absorbs MODTRAN's multiple-scatter contribution as an effective
parameter of this formula. Examples: rural 0.791 / 0.698 / 0.187; urban 0.423 / 0.430 /
0.263.

The two $\omega_0$ definitions coexist on purpose: the flux-fit table is not a valid
substitute inside the phase-function-weighted $L_{\text{path}}$ integral, and the internal
column $\omega_0$ over-predicted diffuse sky irradiance by $\approx 1.3\times$ (VIS rural)
to $\approx 5\times$ (SWIR urban).

*Record:* CU-155, resolved 2026-07-18 (commit `77d8ad2`), scope narrowed to this product by
CU-321 on 2026-08-02; Gap 38 (2026-07-20) for $\omega_{0,\text{eff}}$; CU-324 for the
$z_{em}$ refinement.
*Enforced by:* `tests/integration/test_modtran_real_runs.py` (the H2/H4 parity envelope and
the $\omega_{0,\text{eff}}$ re-derivation guard),
`src/radiant/atmosphere/tests/test_omega0_eff.py`,
`src/radiant/atmosphere/tests/test_e_sky_decomposition.py`.

### 2.12 Path topologies — segments, arms, and whole paths

Every non-trivial path is a **composition of path segments**: one piece of path between two
points, evaluated once, read from either end. Two spec types, because there are two
topologies and they are not variations of one form:

| Spec | Fields | Topology | Air mass |
|---|---|---|---|
| `ColumnSegmentSpec` | $h_{low}$, $h_{high}$ [m], $\zeta_{low}$ [rad] | **endpoint-minimum** — the path's lowest point is an endpoint | §2.7 |
| `LevelArmSpec` | altitude [m], length [m] | **interior-tangent** — the lowest point is in the middle | none at all |

One evaluated product, `SegmentQuantities`, carries **one** $\tau$ and **two** directional
radiances $L_{\text{toward upper}}$, $L_{\text{toward lower}}$. Transmittance is reciprocal,
so a segment has one $\tau$ no matter which way it is read; path radiance is not, because
the emitting and scattering layers are weighted by the transmittance of the material
*between* them and the receiver, and that weighting reverses with direction.

**The lower-endpoint convention.** Every column segment's zenith is keyed to its **lower**
endpoint. Two structural reasons: it is the one endpoint the two travel directions share,
so a single scalar describes the segment rather than the reading of it; and it is the angle
MODTRAN's Card 3 wants when $H_1 \le H_2$, so no convention translation sits between
RADIANT and its truth source.

**The level arm.** A level path cannot be served by the column machinery at all, and the
reason is structural rather than accuracy: a column's optical depth is
$\int e^{-h/H}\mathrm{d}h$ between two equal altitudes, which is **exactly zero**, and its
air mass is $\sec(\pi/2)$, which is undefined. The arm is instead

$$\tau(\lambda) \;=\; \exp\!\left[-\alpha(\lambda, h)\,L\right],
\qquad
L_{\text{path}}(\lambda) \;=\; \bigl[1 - \tau(\lambda)\bigr] B(\lambda, T_{\text{eff}}) \;+\; \text{single-scatter source}$$

with $\alpha$ the **local** extinction at the arm's altitude [km⁻¹] and $L$ the **true
spherical chord** between the endpoints [km] — not a flat-Earth range. No new calibration
is introduced: the water and gas terms are linearised exactly as §2.8 prescribes, against
a reference column independent of the arm's own length, which is what makes $\alpha$ a
property of altitude alone and $\tau$ a pure exponential in $L$.

The arm's one approximation is constant density. On a spherical Earth the chord dips below
its endpoints by the tangent-height depression

$$\Delta h \;\approx\; \frac{L^2}{8 R_E},
\qquad \text{mean sag over the chord} \;\approx\; \tfrac{2}{3}\Delta h$$

so the real path samples slightly *denser* air and the model **under-states** optical depth.
The horizon guard bounds the error: $\Delta h < 100$ m computes clean, up to 2 km warns,
beyond 2 km raises. On the 2 km water scale height that is a 3.4 % water-density error at
the clean edge, 6.8 % on the longest grid arm ($L = 100$ km), and a factor $\approx 1.9$ at
the raise threshold — which is why 2 km raises rather than warns.

$\tau(2L) = \tau(L)^2$ holds exactly for this arm, and it is precisely where a
correlated-$k$ band model disagrees: strong lines saturate first and flux keeps leaking
through the windows between them. That divergence is measured against the horizontal
MODTRAN grid in the parity document §2.6.

**The whole level path.** The sky behind a level target is *not* an arm composed with a
continuation joined at the target plane. A level ray is tangent at the chord **midpoint**,
so the sensor sits on its descending half, and the traversed column is, per species,

$$S_i \;=\; 2\,S\!\left(r_p;\, h_p \to h_{\text{arm}}\right) \;+\; S\!\left(r_p;\, h_{\text{arm}} \to h_{\text{top}}\right),
\qquad
r_p \;=\; \sqrt{r_{\text{arm}}^2 - (L/2)^2}$$

evaluated once by `atmosphere/level_whole_path.py`. Rooting a single ascending arc at the
sensor — the up-looking branch's shape — would drop the arm entirely, recovering only
83.0 % of the true traversed molecular column for a 100 km arm at 3 km and 75.1 % for a
150 km arm at 10 km. A zero-length arm reduces the whole-path evaluator **exactly** to the
grazing evaluator at $\zeta = \pi/2$, so the level and ascending sky topologies join
without a step. The 8 km-at-sea-level case is degenerate — its perigee sits 1.3 m *below*
the ellipsoid — so the integration floor is clamped at MSL and the model warns.

**Sky radiance along the LOS.** The radiance a receiver at $h_{\text{start}}$ sees looking
up along a ray of zenith $\zeta$ with nothing behind the atmosphere but cold space:

$$L_{\text{sky}}(h_{\text{start}}, \zeta) \;=\; \mathrm{SegmentQuantities}\!\left(\mathrm{ColumnSegmentSpec}(h_{\text{start}}, h_{\text{atm,top}}, \zeta)\right).L_{\text{toward lower}} \;+\; \tau_{\text{seg}} L_{\text{beyond}},
\qquad L_{\text{beyond}} \equiv 0$$

The 2.7 K cosmic background contributes $< 10^{-9}$ W/m²/sr/µm anywhere in the 0.3–14 µm
working range, so the composition is a no-op and the module is a thin, well-named wrapper
rather than a second physics implementation. **The ray starts at the sensor, not the
target**: a background behind a target cannot depend on where along the ray the target
sits, and splitting one column at the target plane swaps part of a warm ground-anchored
graybody for a cold target-anchored one — the segment model is not additive across a join.

**Composition rules.** For two adjoining segments $A$ (nearer the source) and $B$:

$$\tau(A \cup B) = \tau_A\,\tau_B,
\qquad
L(A \cup B) = L_A\,\tau_B + L_B$$

which, with the vacuum identities $\tau_V \equiv 1$, $L_V \equiv 0$, collapse an
exo-altitude target's path to the published fields with no arithmetic performed at all.

*Record:* ADR-0011 (path-segment contract, lower-endpoint convention, and the Phase-1
horizon-guard bands the sag table is read against); CU-254, resolved 2026-07-29
(sensor-rooted sky); CU-276, folded into CU-224, landed 2026-08-01 (the level whole path);
Gap 108 (`SkyBackground`), Gap 109 (topologies), Gap 95 (exo targets). The sag/water-error
table is **(record only)** — `RADIANT_Atmosphere.md` §4.2f; the guard thresholds it is read
against are enforced in `core/los_geometry.py`.
*Enforced by:* `src/radiant/atmosphere/tests/test_segments.py`,
`test_level_arm.py`, `test_level_whole_path.py` (the sag formula, the sensor-rooted-arc
column loss, the zero-arm grazing identity, the MSL clamp warning),
`test_sky_radiance.py`, `test_topology_dispatch.py`, `test_topology_exo.py`,
`tests/integration/test_exo_target_chain.py`.

### 2.13 Twilight — per-altitude illumination and the solar tangent transit

Whether a point is lit is decided per altitude rather than by a global $\theta_s < \pi/2$
bound, so solar zenith spans the closed $[0, \pi]$:

$$\text{sunlit}(h, \theta_s) \iff \theta_s \le \frac{\pi}{2}
\quad\text{or}\quad (R_E + h)\sin\theta_s \ge R_E
\iff h \ge R_E\left(\sec\delta - 1\right),\quad \delta = \theta_s - \frac{\pi}{2}$$

so a 60 km booster is sunlit at 5° solar depression while the ground beneath it (shadow
height $\approx 24$ km) is not. The assumption is a **sharp terminator** — opaque sphere,
point Sun, no refraction; the $\approx 200$ m penumbral blur and the $\approx 0.5°$ of
unmodelled refractive lift are documented, not smoothed.

For a **sunlit** target with $\theta_s > \pi/2$ the direct beam is a tangent transit, not
a descending column, so the solar transmittance is the two-arm decomposition

$$\tau_{\text{sun}} \;=\; \tau(\text{tangent} \to \text{target})\;\cdot\;\tau(\text{tangent} \to \text{TOA})$$

about the tangent radius $r_0 = (R_E + h_{tgt})\sin\theta_s$. For a **shadowed** target
$\tau_{\text{sun}}$ is exactly 0 and the scattered-sky solar component is already
identically zero; the thermal sky is untouched.

**This branch is provisional.** The twilight transit carries the largest optical depths
anywhere in RADIANT (30–70 air masses), where both the exponential-in-column transmittance
and the unmodelled refraction are at their worst. The twilight pair Q7/Q8 *was* delivered —
with Card-3 ANGLE hand-set to 93° / 96° and `LENN = 1`, and the hand edit verified against
the matrix by the Card-3 echo sweep — but both rows are `dev_only`: no library family and no
radiometric parity test consumes them, so the transit's **transmittance remains unanchored**
(parity document §1 and §3). Treat it as an order-of-magnitude bound.

Note also that RADIANT models the target as a horizontal Lambertian facet, so the direct
solar term is multiplied by $\cos\theta_s$ clamped at zero: for any $\theta_s > \pi/2$ the
direct term vanishes regardless of $\tau_{\text{sun}}$, because the beam arrives from below
the facet. $\tau_{\text{sun}}$ is still published correctly, because it is an inspectable
physical quantity (Rule 16) that a non-horizontal target model would consume.

*Record:* ADR-0011 decision 21 (GF-9); provisional status recorded in
`RADIANT_Atmosphere.md` §4.2e.
*Enforced by:* `src/radiant/atmosphere/tests/test_solar_shadow.py`,
`src/radiant/atmosphere/tests/test_solar_transit.py`,
`tests/integration/test_solar_illumination.py`.

---

## 3. The library-backed models

### 3.1 What a library family is

A family is a set of pre-computed MODTRAN states at discrete geometry points, plus a
declaration of which geometry fields are **interpolation axes**. Each stored node carries a
wavelength grid, a transmittance, a path radiance, a downwelling emission array, and the
full five-field run geometry it was rendered at.

Shipped families, with their axes and direction:

| Family | Direction | Axes | Coverage |
|---|---|---|---|
| `us_standard_zenith_fan` | down | `path_zenith_rad` | ground target, sensor 100 km, $\zeta$ 0–60° |
| `midlat_summer_ladders` | down | `sensor_altitude_m,target_altitude_m` | targets 0–29 km; sensor 35 km / 100 km / GEO; nadir |
| `midlat_summer_sensor_ladder` | down | `sensor_altitude_m` | ground target; sensor 3–100 km + GEO; nadir |
| `midlat_summer_boost_offnadir` | down | `sensor_altitude_m,target_altitude_m,path_zenith_rad` | targets 0–100 km; sensor 100 km / GEO; $\zeta$ 0–60° |
| `midlat_summer_upwelling_offnadir` | down | `sensor_altitude_m,path_zenith_rad` | ground target; sensor 10/100 km / GEO; $\zeta$ 0–60° |
| `midlat_summer_boost_ladder` | down | `sensor_altitude_m,target_altitude_m` | targets 0–100 km, 12 rungs; explicit-dir only |
| `midlat_summer_uplooking_ladder` | up | `target_altitude_m` | ground sensor, targets 0–20 km, vertical |
| `midlat_summer_uplooking_zenith_fan` | up | `target_altitude_m,path_zenith_rad` | ground sensor, targets 0–20 km, $\zeta$ 0–60° |
| `midlat_summer_uplooking_sensor_ladder` | up | `sensor_altitude_m` | observer 0–100 km, full column, fixed 48.2° |
| `midlat_summer_sst_column_fan` | up | `path_zenith_rad` | ground sensor, full column, $\zeta$ 0–78.5° (sec 1–5); explicit-dir only |
| `midlat_summer_sst_column_fan_site900m` | up | `path_zenith_rad` | 900 m site, full column, $\zeta$ 0–78.5° (sec 1–5); explicit-dir only |

Direction is a first-class property. An up-looking run measures one travel direction, so an
up-looking family stores its radiance under a **different NPZ key**
(`path_radiance_toward_lower`), carries a `los_direction` marker, and is served through a
different query entry point; the two entry points refuse each other's families rather than
reading the wrong product.

The two SST fans differ only in their rendered lower endpoint (0 m and 900 m) and are
**siblings, not one family with a sensor axis**: two rungs cannot be interpolated between,
the 900 m block has no 48.2° rung to make a rectangular grid with, and the 0 m fan had to
stay byte-identical. A site at any other elevation is served by `simple`.

*Record:* GF-10 (shipped 2026-07-26, batch-2 families 2026-08-02, the 900 m SST fan
2026-08-03); library provenance in
`src/radiant/data/tables/atmospheres/MANIFEST.md`.
*Enforced by:* `tests/integration/test_shipped_atmosphere_library.py`,
`tests/integration/test_batch2_atmosphere_families.py`,
`src/radiant/atmosphere/tests/test_interpolated_uplooking.py`.

### 3.2 Geometry interpolation in log-$\tau$

Transmittance is interpolated in **optical-depth** space, not in $\tau$:

$$\ln\tau_{\text{query}} \;=\; \mathrm{interp}\!\left(\text{axes};\ \ln\tau_{\text{nodes}}\right),
\qquad
\tau_{\text{query}} = \exp\!\left(\ln\tau_{\text{query}}\right)$$

Beer-Lambert gives $\tau = e^{-\mathrm{OD}}$ with OD linear in path length and absorber
amount, so linear interpolation of $\ln\tau$ preserves that linearity and linear
interpolation of $\tau$ does not.

Path radiance and downwelling emission interpolate **linearly**. They are additive
quantities with no Beer-Lambert exponential in path length, so log space would buy nothing
and would misbehave at zeros.

**No extrapolation.** A query outside the convex hull of the nodes always raises. The one
query served from outside the node span is not an exception but an application of the rule
— see §3.6.

### 3.3 Wavelength resampling in log-$\tau$, and why the two must commute

A chain runs on its own wavelength grid, which is normally not the stored one, so the
geometry-interpolated spectra must be resampled. That resample runs in the **same** log-$\tau$
space:

$$\tau(\lambda_{\text{query}}) \;=\; \exp\!\left[\mathrm{interp}_\lambda\!\left(\ln\tau_{\text{stored}}\right)\right]$$

Both operations are then linear in $\ln\tau$, so they **commute** and the answer no longer
depends on their order. Resampling linearly in $\tau$ instead returns the arithmetic mean of
the bracketing samples where the physics gives the geometric mean — and by AM–GM the
arithmetic mean is strictly larger, so the old convention was biased one way, upward.

The key equation the tests use as their truth anchor: for $\tau(\lambda) = e^{-a\lambda}$
the optical depth is *exactly* linear in $\lambda$, so a log-linear resample is exact at
every query wavelength and a cell midpoint must return $\sqrt{\tau_i \tau_{i+1}}$.

**The convention is universal across all three file-backed backends.** `tabulated` and
`modtran` each perform only one resample — no operation order to get wrong — but a
different *convention* meant the same stored MODTRAN column returned different numbers
depending on which backend served it. All three now carry every $\tau$-like array
(`transmittance`, $\tau_{up}$, $\tau_{sun}$, $\tau_{\text{full,up}}$) through the single
implementation in `atmosphere/log_tau_resample.py`. Scope, in both directions:

- **log-$\tau$**: transmittance only, in every backend.
- **linear**: $L_{\text{path}}$, $L_{\text{atm,down}}$, and every irradiance.

A query on the file's own grid short-circuits the log round trip and is **bit-identical**
to the stored array.

*Record:* CU-306, resolved 2026-08-01 (operation order); CU-316, resolved 2026-08-02
(cross-backend convention). Both owner-approved and results-affecting.
*Enforced by:* `src/radiant/atmosphere/tests/test_log_tau_resample.py` — the geometric-mean
key equation, the bit-identical native-grid no-op, per-backend midpoint identities, and the
three-backend agreement test.

### 3.4 Zenith axes interpolate in $\sec\zeta$

A zenith-angle axis is mapped $\zeta \mapsto \sec\zeta$ before interpolation. Combined with
§3.2 this is Beer-Lambert-**exact** between nodes: the path length along a zenith axis is
$\propto \sec\zeta$, so $\ln\tau$ linear in $\sec\zeta$ reproduces Beer at every query
angle. Linear-in-angle carried a measured in-band bias at fan midpoints (parity document
§2.10).

The transform is internal — user-facing coordinates, bounds and errors stay in radians.
Angles $\ge$ `_MAX_ZENITH_RAD` ($\approx 88.8°$) are **refused**, because $\sec\zeta$
diverges at the horizon.

Batch-2 gave the up-looking direction the same axis, sampled as a *uniform sec ladder*
rather than a uniform angle ladder: $\sec\zeta = 1.0 / 1.4999 / 2.0$ for the target fan and
$1/1.5/2/3/4/5$ for the full-column SST fan. Three sec rungs is the minimum that can
**test** linearity in sec rather than assume it. The 85°/88°/89.5° probes (M6–M8) were run
but are deliberately **not shipped as nodes**: at and past the 88.8° ceiling the mapping is
unvalidated, and a shipped node there would sit inside a hull the interpolator may traverse.
They serve as physics anchors instead (parity document §2.4).

*Record:* CU-160, resolved 2026-07-17 (commit `863e923`); GF-10 batch-2 sec ladder,
2026-08-02.
*Enforced by:* `src/radiant/atmosphere/tests/test_interpolated.py` (the
$\tau(\zeta) = \tau_{\text{vert}}^{\sec\zeta}$ Level-0 identity to $10^{-10}$),
`tests/integration/test_shipped_atmosphere_library.py` (holdout on the shipped fan),
`tests/integration/test_batch2_atmosphere_families.py` (M6–M8 excluded from every shipped
node set).

### 3.5 `TAU_FLOOR` — a lower clamp only

Stored transmittance is floored at `TAU_FLOOR` $= 10^{-30}$ (equivalently
$\mathrm{OD} \approx 69$) before the logarithm, so $\ln\tau$ is finite everywhere and an
opaque band resamples to that floor rather than to $-\infty$ or NaN. One definition, owned
by `atmosphere/log_tau_resample.py` and imported by every consumer.

The floor is deliberately **not** matched by a cap at 1.0. A $\tau > 1$ array is invalid
data, and capping it would convert a mis-scaled tape7 into a plausible-looking column —
exactly the silent-repair Rule 17 forbids. Instead it survives the resample and fails loud
downstream in `AtmosphericQuantities.__post_init__`. Negative $\tau$ raises inside the
resample itself.

*Record:* CU-316 resolution, 2026-08-02 (the deliberate departure is recorded there).
*Enforced by:* `src/radiant/atmosphere/tests/test_log_tau_resample.py::test_opaque_band_rides_the_floor`,
`::test_over_unity_is_not_capped`, `::test_negative_transmittance_raises`.

### 3.6 Vacuum-equivalence identities

Two identities let a family serve a query outside its node span *without* extrapolating,
because the intervening path is provably vacuum. Both are gated on the shared constant
`_VACUUM_EQUIVALENT_ALTITUDE_M` = 100 km = $h_{\text{atm,top}}$.

**Sensor axis.** MODTRAN's atmosphere ends at $h_{\text{atm,top}}$, so a sensor above a
node at or above the column top sees an *exactly identical* column — the added path has
zero extinction and zero emission. This is why the ladders duplicate their 100 km TOA state
at a 40 000 km node: an orbital sensor then falls inside the hull, and the duplication is a
physical identity, not an approximation. The same identity exempts such a query from the
non-axis geometry-mismatch warning.

**Target axis.** The mirror. A family whose measured target ceiling reaches
$h_{\text{atm,top}}$ integrated the *entire* column, so its top-of-column run **is** the
observer leg for any exo-altitude target; the query is clamped to the ceiling node and the
clamp is recorded in the segment provenance under `exo_target_vacuum_clamp`.

The guard asks the **family**, never a hard-coded name: `uplooking_target_ceiling_m` reads
the highest target altitude the family's own runs measure — from the `target_altitude_m`
axis hull when it carries one, from the recorded fixed value when it does not. A
**partial-column** family (ceiling below $h_{\text{atm,top}}$) is **refused**, with an
actionable error naming its measured ceiling and the families that do serve the scene:
composing its top rung with the vacuum identity would join a measured leg to an invented
one. The clamp is gated at $h_{\text{atm,top}}$ and nowhere else — a 50 km target through a
20 km ladder is 40 km of real atmosphere and still fails the hull check, unchanged.

*Record:* CU-224 checklist item ex-CU-308, landed 2026-08-02; CU-167 (non-axis warning),
resolved 2026-07-18 (commit `1d212e8`).
*Enforced by:* `tests/integration/test_uplooking_backend_dispatch.py` — the tripwire test
asserts every bundled up-looking family is either below the top *and* refuses an exo
target, or reaches it *and* satisfies the identity.

### 3.7 The hybrid up-looking composition

An up-looking run family is **one leg of data**, so an up-looking chain run on the
interpolated backend is a declared hybrid: the family serves the leg it measured, and a
`SimpleAtmosphere` companion — built pre-chain from the same `atmosphere.*` parameters a
`model = "simple"` run would use — serves the rest.

| Leg | Served by | Why |
|---|---|---|
| observer (sensor → target) | the up-looking run family | this *is* the rendered column, and it dominates a ground-to-air scene |
| illumination (solar column + sky above the target) | the `SimpleAtmosphere` companion | no rung of a sensor→target ladder is the column *above* the target, and the down-looking proxy query an up-looking family would need is refused by construction |
| sky at aperture (sensor → $h_{\text{atm,top}}$) | the `SimpleAtmosphere` companion | reading a partial ladder's top rung as "the sky" would be extrapolation past the hull |

Two independently-calibrated models in one answer is a real modelling compromise, so it is
never silent: a `UserWarning` is raised, an INFO record is logged, and
`stage_outputs["atmosphere"]["topology_provenance"]["backend_split"]` names which leg came
from which model. Where the two models must agree — $\tau_{\text{sun}}$, $E_{\text{TOA}}$,
and both $E_{\text{sky}}$ terms, all served by the companion alone — they are bit-identical.

**Owner-ratified 2026-08-01, conditionally.** The ratification is conditional on the
compromise staying *declared*: the warning, the INFO record and the `backend_split` marker
are part of what was ratified and must not be softened into silence. The measured
divergence between the two legs is in the parity document §2.11.

The one re-audit condition: the split exists because an up-looking family is one leg of
data. A family that is self-contained — carrying its own solar column and its own
sensor → $h_{\text{atm,top}}$ sky — or a scene whose target is a blackbody, where the
illumination terms vanish, makes the companion unnecessary *for that scene*, and the split
should be dropped there rather than declared.

A **level** path on an up-looking family is refused, not approximated: a level arm has zero
vertical extent and a local zenith of $\pi/2$ everywhere, so no rung of a column ladder is
that path and no interpolation between rungs produces it.

*Record:* CU-226 (chain wiring, landed 2026-07-30); CU-224 checklist item ex-CU-305,
owner-ratified 2026-08-01.
*Enforced by:* `tests/integration/test_uplooking_interpolated_chain.py`,
`src/radiant/atmosphere/tests/test_uplooking_backend_dispatch.py` (the warning, the INFO
record, and the provenance marker each have a test).

---

## 4. What the models do not represent

Recorded here because a physics document that omits its own boundaries is misleading. Each
item's tracking home is named; the *measured* consequences are in the parity document §3.

- **Line structure inside a calibrated region.** The simple model's spectral shape is flat
  within each of the 15 regions (CU-161); the 0.04 µm edge ramps remove the discontinuity,
  not the underlying flatness. This is now the named dominant residual of the thermal path
  radiance (CU-321 closure).
- **Multiple scattering.** The single-scatter source under-predicts the daytime VIS/NIR sky
  (Gap 38); the sub-3 µm provisional warning is what says so to an operator.
- **Refraction.** The geometry is unrefracted (ADR-0011 decision 5). It is the dominant
  geometric error inside the horizon guard's warn band, and the on/off calibration decks
  (Q5/Q6) are unrun.
- **Stratospheric structure.** The fixed-lapse ICAO profile is isothermal above the
  tropopause, so real stratospheric warming is not represented (CU-324).
- **Grazing-arc opacity distribution.** A grazing arc's air lies along the arc, not along
  the vertical between its endpoints; the emission weighting is approximate there, though
  the *total* optical depth is exact (CU-324).
- **O₃ emission altitude.** The well-mixed-gas floor lumps CO₂/N₂O/CH₄ with O₃, which peaks
  near 25 km, so 9.6 µm emission is placed too low (CU-324).
- **Polarization, 3D/heterogeneous atmospheres, time dependence, adjacency, aurora/airglow,
  cloud microphysics.** Out of scope for v1 (`RADIANT_Atmosphere.md` §11).

---

## References

- Hansen, J. E. and Travis, L. D. (1974). "Light scattering in planetary atmospheres."
  *Space Science Reviews* 16, 527–610. — Rayleigh whole-atmosphere optical depth.
- Bucholtz, A. (1995). "Rayleigh-scattering calculations for the terrestrial atmosphere."
  *Applied Optics* 34(15), 2765–2773.
- McClatchey, R. A. et al. (1972). *Optical Properties of the Atmosphere* (3rd ed.),
  AFCRL-72-0497. — standard-profile water columns.
- Henyey, L. G. and Greenstein, J. L. (1941). "Diffuse radiation in the galaxy."
  *Astrophysical Journal* 93, 70–83.
- Elsasser, W. M. (1942). *Heat Transfer by Infrared Radiation in the Atmosphere.*
  Harvard Meteorological Studies 6. — the diffusivity-factor context for $D$.
- Chapman, S. (1931). "The absorption and dissociative or ionizing effect of monochromatic
  radiation in an atmosphere on a rotating earth." *Proc. Phys. Soc.* 43, 26–45. — the
  grazing-limit anchor for the spherical slant column.
- `docs/theory/references.md` — the project-wide reference list.
