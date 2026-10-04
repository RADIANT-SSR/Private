# Refractive Substrate Emission — Design Study

**Status:** Draft — **study complete, awaiting ratification of §7.** No implementation until §7 is ratified.

**Date:** 2026-10-04 (opened); 2026-10-04 (study completed)
**Category:** C (physics implementation) for the emission path; B for the material-library surface.
**Registry:** [[CU-394]] — this study is that CU's disposition. The study also opened [[CU-396]] (§7.3) and recommends one new Gap (§9.7).

**Owner ruling that opened it (2026-10-04), verbatim in substance:**

> The issue here is the detailed Kirchhoff. I'd like an approach where it is assumed
> that at the coating interface to the substrate, 1 = R + T. The absorption — and
> therefore the emissivity — is really given by the absorption coefficient of the
> substrate material. Optical coatings are very thin and their self-emission can be
> ignored for near-field. It's really substrates.

**Read first:**
- `docs/architecture/RADIANT_Optics.md` §5–§7 (element model, Kirchhoff derivation, étendue cone)
- `src/radiant/optics/cavity_model.py` (the existing per-surface cavity physics)
- Gap 127 (the ratified emission-model rules) and its archived plan
- `src/radiant/data/fpa.py` (`FPALibrary`) — the closest existing precedent for a bundled material/part library

**Companion artefacts produced by this study** (all under `docs/plans/substrate_data_proposed/`, proposed content — nothing is wired into the package):

| File | What it is |
|---|---|
| `<material>.yaml` × 8 | the proposed library entries: n(λ) source, α(λ) anchors, per-datum provenance |
| `sources/` | the exact retrieved source artefacts (refractiveindex.info YAMLs, CC0; Crystran material pages) with `MANIFEST.md` carrying URL, retrieval date and SHA-256 per Rule 26(c) |
| `tables/<material>.csv` | the generated n(λ), α(λ) tables — regenerable, gitignore candidates |
| `build_substrate_tables.py` | the Rule 26 generator-of-record for `tables/` |
| `n2_derivation.py` | the §7.3 derivation check — the algebraic reduction, the ε ≤ 1 bound, and the shipped-vs-correct ratio, independent of any material data |
| `grade_substrate_data.py` | the three-tier grading harness (§8) |
| `ge_alpha_temperature.py` | the α(λ,T) evidence for §7.2 |

These four scripts live under `docs/plans/`, which the merge battery's `ruff` scope does
not cover. They are nonetheless clean under `ruff check` and `ruff format` as committed —
verified by hand, not by a gate. Noted so a reader does not assume gate coverage; not
proposed as a gate widening (process-machinery moratorium).

---

## 1. What the ruling settles

The ruling is a statement about **where the absorption lives**, and the shipped model
already agrees with it. `cavity_model.py` enforces, per surface:

```
R + T = 1     (to _CAVITY_KIRCHHOFF_TOL)
```

with the comment *"coatings are lossless by model rule; all absorption, and hence all
emission, is bulk α·thickness. A deficit R + T < 1 would be coating absorption the
emissivity expression does not model — silently non-emitting — so it is rejected, not
tolerated."* A `KirchhoffViolationError` fires on any deficit.

So this study does **not** propose changing the *structure* of the emission physics. The
ruling confirms it and rejects the alternative that prompted CU-394 — lumping the whole
loss into an element-level $\varepsilon = 1 - T - R$, which would silently attribute
substrate absorption to the coatings and vice versa.

**What is actually missing is the substrate's material data.** The cavity needs `alpha`
[1/m] and `n_refr`, which are properties of germanium or silicon or ZnSe, not of the
instrument. An instrument datasheet quotes a band-averaged net transmission and a
surface count and cannot determine them. That is the whole of CU-394.

**What the study found in addition** (and did not expect): the cavity's *emissivity
expression* — not its structure — is wrong by a factor of $n^2/(1 + R_1 \cdot \mathrm{beer})$,
and the overflow is silently clipped. That is §7.3 and [[CU-396]].

## 2. The gap, stated precisely

| Input | Where it comes from today | Where it should come from |
|---|---|---|
| per-surface `R` / `T` | user, per element | user (coating spec) — unchanged |
| `thickness_m` | user, per element | user (element spec) — unchanged |
| `alpha` [1/m] | **user, per element** | **a substrate material, by name** |
| `n_refr` | **user, per element** | **a substrate material, by name** |

An analyst holding a lens drawing knows its material and thickness. They do not know
its bulk absorption coefficient at 4.2 µm, and should not have to.

## 3. Proposed shape (for ratification, not yet built)

A bundled **substrate material library**, structurally parallel to `FPALibrary`
(Gap 119) and the existing emissivity library under `data/tables/emissivity/`:

```yaml
optical_elements:
  - name: L1
    transfer_mode: REFRACTIVE
    substrate: germanium        # -> alpha(lambda), n(lambda) from the library
    thickness_m: 0.008
    R1: 0.010                   # coating, lossless: T1 = 1 - R1 derived
    R2: 0.010
    temperature_K: 250.0
```

Everything downstream is the existing cavity model, with the §7.3 `eps_eff` correction.

`substrate:` and the pair (`alpha`, `n_refr`) are **mutually exclusive** keys, rejected
as over-specification by the io parser (Rule 16) — see §9.3. That is the only new
validation rule the proposal adds.

## 4. Open questions for the study

1. **Which substrates ship?** Candidate v1 set: Ge, Si, ZnSe, ZnS (multispectral and
   standard), sapphire, CaF₂, BaF₂, fused silica. Each needs α(λ) and n(λ) over the
   bands RADIANT models, with provenance per Rule 26(c). → **answered, §7.1**
2. **Temperature dependence.** Ge's absorption is strongly temperature-dependent in the
   LWIR — free-carrier absorption rises steeply above ~250 K. A cryogenic Ge lens and a
   300 K Ge lens are not the same material. Does v1 carry α(λ, T), or α(λ) at a stated
   reference temperature with a documented limitation? → **answered, §7.2**
3. **The n² question.** `eps_eff = T2·n²·(1 − beer)/denom` carries the enhanced
   photon-density-of-states factor. For a high-index substrate with non-trivial
   absorption this can exceed 1 and is clipped. The study must establish the regime
   where the expression is valid and what should happen outside it — a clip is a silent
   failure in the Rule-17 sense and is the one place the current model may need work.
   → **answered, §7.3. The owner's concern was correct and understated.**
4. **Where the library lives.** `data/tables/substrates/`, consistent with
   `data/tables/fpa/`, and whether it is addressable from the GUI's element editor.
   → **answered, §7.4 / §9**
5. **Grading against reality.** A worked case with real material data — the study should
   reproduce a published cold-shield / warm-optics budget for a refractive MWIR head
   and compare. → **answered, §8**
6. **The GUI surface** (owner scope addition, 2026-10-04) — see §4a. → **answered, §9**

## 4a. The GUI surface

The owner put the GUI in scope for this study: *"part of our deep dive is figuring out
how to add it to the GUI."* An element whose emission is driven by a named material is
useless if the only way to name it is by hand-editing YAML.

The precedent to follow is the **FPA preset selector** (Gap 119,
`gui/widgets/fpa_part_selector.py`): a bundled library addressed by name, chosen from a
picker, with the resolved values visible and the provenance reachable. The element
editor (`gui/widgets/optical_element_editor.py`) is where this lands.

Questions the study must answer, not assume:

- **Where the picker lives.** A per-element control in the optical-element editor, or a
  material column in the element table? → **§9.1**
- **What the operator sees once a substrate is chosen.** → **§9.2**
- **What happens on a switch.** → **§9.3**
- **Display units.** → **§9.4**
- **The unavailable-material path.** → **§9.5**

**The GUI is specified by this study, not built by it.** Any GUI change goes through the
live-review loop before merge.

## 5. What the scenarios do meanwhile

10.2 and 10.4 model their refractive heads as Kirchhoff-equivalent reflective trains at
`R = τ^(1/N)`, which reproduces the net throughput exactly and emits at `ε = 1 − R` per
surface. Each runner documents the substitution. That stays until this study lands; the
numbers are defensible, the configs are not literal.

**The study strengthens this position.** Because the shipped `eps_eff` is high by up to
15.9× (§7.3), the fictitious-mirror substitution is currently *more* accurate than a
literal cavity configuration would have been. No scenario or golden baseline uses the
cavity path, so the §7.3 fix moves no committed number (§10.1).

## 6. Non-goals

- Changing the cavity emission expression's **structure**. The ruling endorses it, and
  the study confirms the structure (per-surface lossless coatings, bulk α·d absorption,
  Airy cavity denominator) is right. §7.3 corrects a *factor*, not the structure.
- Coating self-emission. Ruled out: coatings are thin enough that their self-emission is
  negligible for the near-field term.
- A general optical-materials database (dispersion for ray tracing, thermo-optic
  coefficients). This is a near-field emission study; it needs α and n and nothing else.

---

# 7. Decisions needed — recommendations with the numbers behind them

## 7.1 The v1 substrate set

**Recommendation: ship six, in two confidence tiers, and do not ship the other two.**

The decisive fact the study uncovered is that **n(λ) and α(λ) have completely different
data availability**, and the library's usefulness is set entirely by α:

- **n(λ) is a solved problem.** Critically-evaluated dispersion data exists for every
  candidate, is CC0 via the refractiveindex.info database, and reproduces each vendor's
  published index to $\le 0.003$ (§8, Tier 1). There is nothing to decide here.
- **α(λ) in the transparency window is the long pole, and the published data is spot
  values at laser lines, not spectra.** The tabulated $k(\lambda)$ that the
  refractiveindex.info database carries is a **null** in the window: Querry's ZnSe
  table, for example, reports $k = 0.0000000$ at every point from 2.0 µm to 14 µm —
  its detection floor corresponds to $\alpha \approx 1.6 \times 10^{-3}\ \mathrm{cm^{-1}}$,
  three times the true value. The $k$ data captures the two *absorption edges*
  (electronic, multiphonon), which is where a material should not be used; it says
  nothing about the window, which is where emission happens.

So α(λ) must be built by interpolation through published laser-line anchors. The number
of such anchors per material is the library's real quality metric:

| Material | window [µm] | published α anchors | span of anchors | α range [cm⁻¹] | grade spread | tier |
|---|---|---|---|---|---|---|
| ZnSe | 0.60–14 | **5** | 1.3–10.6 µm | 4e-4 … 5e-3 | ~2× (CVD lot) | **A** |
| CaF₂ | 0.40–10 | **6** | 2.7–10.6 µm | 7.8e-4 … 3.5 | ~2× | **A** |
| ZnS (multispectral) | 0.40–13 | **5** | 1.3–10.6 µm | 1e-4 … 0.2 | ~3× | **A** |
| Ge | 1.90–14 | **3** | 2.7–10.6 µm | 5e-3 … 0.027 | 2–5× (resistivity) | **B** |
| Si | 1.20–14 | **1** | 3.0 µm only | 0.01 (+4 modelled) | >10× (CZ vs FZ) | **B** |
| BaF₂ | 0.40–12 | **1** | 6.0 µm only | 3.2e-4 (+2 modelled) | unknown | **B** |
| sapphire | 0.40–5.0 | **1** | 2.4 µm only | 3e-4 (+2 modelled) | unknown | **C — do not ship** |
| fused silica | 0.40–2.5 | **1** | 1.0 µm only | 1e-5 (+1 modelled) | >100× (OH) | **C — do not ship** |

**Tier A (3 materials) — ship as measured data.** ZnSe, CaF₂ and multispectral ZnS have
five or six published anchors spanning the useful band. CaF₂'s set even resolves the
multiphonon edge explicitly (7.8e-4 cm⁻¹ at 2.7 µm → 3.5 cm⁻¹ at 10.6 µm, a 4500× rise),
which is exactly the kind of structure an analyst cannot guess.

**Tier B (3 materials) — ship, flagged, because an analyst cannot avoid them.** Ge is
*the* LWIR refractive substrate and Si *the* MWIR one; a substrate library without them
is not a substrate library, regardless of how thin the α data is. BaF₂ rides along as
the standard low-index LWIR corrector. All three carry per-anchor `basis:` fields
distinguishing published values from modelled shape, and their modelled portions are
labelled `source: estimated` in the YAML.

**Tier C (2 materials) — do not ship in v1.** Sapphire and fused silica have one anchor
each, outside any band where their self-emission matters. Fused silica is opaque past
~2.5 µm, so a 300 K silica element in its own passband emits a Planck radiance ~10⁻¹⁵ of
the scene — the *emission* reason to carry it does not exist, and carrying it would
imply a precision the data does not support. Sapphire's window closes at 5.5 µm and its
single anchor sits at 2.4 µm; a sapphire *dome* in a MWIR seeker is a real and important
case, which is precisely why it should wait for a sourced α(λ) rather than ship on a
modelled one. Both are listed as v2 candidates.

**Also recommended: drop "standard ZnS" from the candidate set.** The §4.1 list named
ZnS "multispectral and standard" as two entries. FLIR-grade ZnS differs from
multispectral ZnS by about 3× in α and ~0.001 in n; carrying two entries whose only
difference is an α level neither of which is spectrally resolved is false precision. The
proposal carries one `zinc_sulphide_ms` entry and records the grade spread in its
`grade_sensitivity` field.

**What the "grade spread" column means for the design.** Every tier-B spread exceeds the
whole magnitude of the emission term it computes. Optical Ge is specified by *resistivity*
(5–40 Ω·cm) precisely because resistivity sets the free-carrier contribution to α; CZ and
FZ silicon differ by >10× at 9 µm. A substrate library that serves one number per
wavelength per material is therefore serving a **class-typical** value, and the proposal
says so in each entry's `grade_note`. This is the same honesty posture the emissivity
library's manifest already takes (CU-080).

## 7.2 α(λ, T) — does germanium force a temperature axis?

**Recommendation: ship α(λ) at a stated reference temperature (293 K) with a declared
validity window and a hard `ParameterBoundsError` outside it. Do not build a temperature
axis in v1 — the data to build one from does not exist publicly.**

The question is not whether the effect is real. It is real. Evidence
(`ge_alpha_temperature.py`), from a physically decomposed model

$$\alpha_{\mathrm{Ge}}(\lambda, T) = \alpha_{\mathrm{mp}}(\lambda) \cdot f_{\mathrm{mp}}(T) + \alpha_{\mathrm{FC}}(\lambda, T)$$

anchored to the one measured point (0.027 cm⁻¹ at 10.6 µm, 293 K), with
$f_{\mathrm{mp}}(T) = [(1 + \bar{n}(T))/(1 + \bar{n}(300))]^N$ for an $N$-phonon sum
process on Ge's 301 cm⁻¹ (433 K) optical phonon, and $\alpha_{\mathrm{FC}}$ the Drude
free-carrier term over ionised donors plus the intrinsic pair density:

| T [K] | α_mp | α_FC | α_tot [cm⁻¹] | α/α(300 K) | FC share | radiance error from α(300 K) |
|---|---|---|---|---|---|---|
| 80 | 0.0088 | 0.0001 | 0.0089 | 0.33 | 1.3 % | +200 % |
| 180 | 0.0127 | 0.0005 | 0.0131 | 0.49 | 3.4 % | +105 % |
| 230 | 0.0168 | 0.0007 | 0.0175 | 0.65 | 3.9 % | +54 % |
| 273 | 0.0217 | 0.0010 | 0.0226 | 0.84 | 4.3 % | +19 % |
| 293 | 0.0244 | 0.0013 | 0.0257 | 0.95 | 5.2 % | +4.9 % |
| 300 | 0.0255 | 0.0016 | 0.0270 | 1.00 | 5.8 % | 0 |
| 320 | 0.0287 | 0.0029 | 0.0315 | 1.17 | 9.1 % | −14 % |
| 350 | 0.0341 | 0.0098 | 0.0439 | 1.63 | 22 % | −38 % |
| 400 | 0.0453 | 0.0717 | 0.1170 | 4.33 | 61 % | −76 % |

(radiance error = the error in $\varepsilon \cdot B(\lambda, T)$ for an 8 mm AR-coated Ge
element at 10.6 µm, from pinning α at its 300 K value.)

Three things the table settles, and one it overturns:

1. **The §4.2 premise is wrong about the mechanism.** Free-carrier absorption is **not**
   what makes Ge's room-temperature LWIR α what it is: it is 5.8 % of the 300 K total
   for 40 Ω·cm material. The 300 K value is **multiphonon lattice absorption**, and it
   is the multiphonon term's Bose-occupation scaling that produces most of the 80–350 K
   variation. The free-carrier runaway is real but starts above ~350 K (22 % of the
   total at 350 K, 61 % at 400 K), and it is a *resistivity-grade* effect at least as
   much as a temperature effect: at 400 K, α_FC is 0.126 cm⁻¹ for 1 Ω·cm material and
   0.072 cm⁻¹ for 40 Ω·cm.
2. **The T-dependence is robust, not a modelling artefact.** Varying the phonon order
   $N$ over 3–5 moves $\alpha_{\mathrm{mp}}(T)/\alpha_{\mathrm{mp}}(300)$ by about ±10 %;
   the effect itself (0.66× at 230 K, 1.17× at 320 K) survives.
3. **But the effect is second order next to §7.3.** A 300 K reference α costs +54 % /
   −38 % in emitted radiance over 230–350 K. The n² defect costs **+1586 %** for the
   same element. Fixing §7.3 and leaving α(λ) at one temperature is strictly better
   than the converse.

**What overturns the "build a temperature axis" option: there is no α(λ,T) data to build
it from.** The study searched the refractiveindex.info database (which carries Ge *n* at
nine temperatures, 100–550 K — and no $k$ anywhere in the window, at any temperature),
the Crystran material pages (one temperature), the Crossref index, arXiv and NTRS. The
asymmetry is itself the finding: *n(λ,T) is published and α(λ,T) is not*. A v1 temperature
axis would therefore be a **model** with one anchor, whose own uncertainty (phonon order
±10 %, resistivity grade 2–30× on the FC term) is of the same order as the correction it
applies. That is not data; it is a parameterisation masquerading as data.

**The limitation must not be silent, though.** Above ~350 K a 300 K reference α is wrong
by more than the term it computes, and 350 K is a physically real regime (a Ge window in
a hot airstream, a Ge element behind a laser). Serving a 300 K α there and saying nothing
is the same species of failure as the n² clip. So:

- each material entry carries `reference_temperature_K` and a
  `validity_temperature_K: [lo, hi]` pair;
- the loader raises a `ParameterBoundsError` (Rule 15, with `what / why / action /
  context`) when an element's `temperature_K` falls outside its substrate's validity
  window — **an error, not a warning**, because the model has no defensible answer there;
- the recommended Ge window is **[250, 330] K** (radiance error within +37 % / −20 %).
  Wide-gap materials (ZnSe, ZnS, CaF₂, BaF₂) get [77, 400] K: they have no free-carrier
  term in any EO operating range, and their multiphonon scaling is the same ~±35 % over
  that span. Si gets [200, 400] K — its 1.12 eV gap puts free-carrier absorption out of
  reach to well above 400 K.
- α(λ,T) returns as a **v2 item built as the decomposition model above, not as a table**,
  because a table cannot be sourced. Recorded as a §11 open item.

## 7.3 The n² question — the shipped model is wrong, and the clip was the symptom

**Recommendation: correct the expression. The owner's concern was right; if anything it
was understated.** This is [[CU-396]].

### 7.3.1 What the correct emissivity of an absorbing slab is

Take a plane-parallel slab, index $n$, thickness $d$, bulk absorption coefficient
$\alpha$, with lossless coatings $R_1 + T_1 = 1$ and $R_2 + T_2 = 1$ on its two faces.
Write $b = e^{-\alpha d}$ and $D = 1 - R_1 R_2 b^2$.

**Route 1 — Kirchhoff.** For a body in local thermodynamic equilibrium, the directional
spectral emissivity equals the directional spectral absorptivity,
$\varepsilon(\lambda, \hat{\mathbf{d}}) = A(\lambda, \hat{\mathbf{d}})$, where $A$ is the
fraction of a beam incident *from* $\hat{\mathbf{d}}$ that the slab absorbs. For emission
out of surface 2 — the downstream face, which is the only one RADIANT's near-field term
consumes — the matching absorption experiment is a beam entering through surface 2. The
standard incoherent (intensity-summing) slab gives

$$T_{\mathrm{sys}} = \frac{T_1 b T_2}{D}, \qquad R_{\mathrm{sys}} = R_1 + \frac{T_1^2 R_2 b^2}{D}$$

(exactly the shipped `T_sys` / `R_sys`), and the absorptance $1 - T_{\mathrm{sys}} -
R_{\mathrm{sys}}$ reduces algebraically to

$$A_1 = \frac{T_1 (1 - b)(1 + R_2 b)}{D}, \qquad\text{hence by symmetry}\qquad \boxed{\;\varepsilon_2 = A_2 = \frac{T_2 (1 - b)(1 + R_1 b)}{D}\;}$$

The reduction was verified numerically against the shipped `T_sys` / `R_sys` over 20 000
random $(R_1, R_2, b)$ triples: max residual **3.5 × 10⁻¹⁶**.

**Route 2 — volume emission, independently.** The equilibrium radiance *inside* a
dielectric of index $n$ is $n^2 B(\lambda,T)$ (photon density of states $\propto n^3$,
group velocity $\propto 1/n$). A ray reaching surface 2 has accumulated
$n^2 B (1 - b)$; the backward ray reflects off surface 1 and adds $n^2 B (1-b) R_1 b$;
the cavity sums to $1/D$. Escaping, radiance is **not** invariant across a refracting
interface — the invariant is $L/n^2$ — so $L_{\mathrm{out}} = T_2 L_{\mathrm{in}} / n^2$.
The $n^2$ cancels, giving $L_{\mathrm{out}} = T_2 (1-b)(1 + R_1 b) B / D$: the same
closed form, from entirely different physics.

**So the $n^2$ enhancement is real, and it is exactly cancelled by the $1/n^2$
radiance de-magnification at the escape interface.** The shipped expression kept the
first and dropped the second.

### 7.3.2 What that costs

$$\frac{\varepsilon_{\mathrm{shipped}}}{\varepsilon_{\mathrm{correct}}} = \frac{n^2}{1 + R_1 b}$$

Measured through the **shipped** `CavityModel` with the proposed material data, for an
AR-coated ($R_1 = R_2 = 0.01$) 8 mm element:

| material | λ [µm] | α [cm⁻¹] | A = 1−T_sys−R_sys | ε_shipped | ε_correct | ratio |
|---|---|---|---|---|---|---|
| germanium | 10.6 | 2.7e-2 | 0.02136 | **0.3388** | **0.02136** | **15.86** |
| silicon | 5.0 | 2.9e-2 | 0.02290 | 0.2651 | 0.02290 | 11.58 |
| ZnSe | 10.6 | 5.0e-4 | 0.00040 | 0.0023 | 0.00040 | 5.72 |
| ZnS-MS | 10.0 | 4.4e-2 | 0.03424 | 0.1642 | 0.03424 | 4.80 |
| CaF₂ | 5.0 | 2.4e-3 | 0.00188 | 0.0036 | 0.00188 | 1.94 |
| BaF₂ | 5.0 | 3.2e-4 | 0.00026 | 0.0005 | 0.00026 | 2.08 |

$\varepsilon_{\mathrm{correct}}$ equals the absorptance column to five decimals at every
row, as Kirchhoff requires. $\varepsilon_{\mathrm{shipped}}$ does not.

### 7.3.3 What should happen outside the valid regime: nothing, because there is no outside

This is the cleanest part of the answer. **The correct expression cannot exceed 1.** Over
200 000 random $(R_1, R_2, b)$ triples the maximum of
$T_2 (1-b)(1 + R_1 b)/D$ is 0.9985, approaching 1 only in the limit $R_2 \to 0$,
$b \to 0$ — a perfectly AR-coated face in front of an opaque substrate, which emits as a
blackbody behind a lossless window. For symmetric coatings it reduces to
$(1-R)(1-b)/(1-Rb)$, monotonically decreasing in $b$ from $1 - R$. There is no numerically
unstable zone, no cancellation, and no regime requiring a clip, a branch, or an
alternative formulation.

So the §4.3 question — "establish the regime where the expression is valid and what
should happen outside it" — resolves to: **the shipped expression is valid only at
$n = 1$ (where it also drops the $(1 + R_1 b)$ cavity-return term), and the clip is not a
guard against a numerical edge, it is the formula's own second-law violation being hidden.**
An $\varepsilon > 1$ means a passive element emits more radiance into vacuum than a
blackbody at its temperature. The right action is to delete both the $n^2$ and the clip,
not to decide what the clip should do.

### 7.3.4 Corroborating evidence that this was known and mis-resolved

- `docs/theory/radiometric_model_mixed_train.md` states **both** the $n^2$ expression
  (§1.1) and the self-consistency check `eps_eff,i ≈ A_total,i` "← must hold at each λ"
  (§"Kirchhoff self-consistency check"). These are mutually exclusive for $n > 1$. The
  corrected form satisfies the check identically.
- `docs/reports/phase3/prompt_3B1_report.md` §Open-Issues names the contradiction
  verbatim — *"The doc's Part 5 note that `eps_eff ≈ A_total` is only approximate (exact
  for n=1); for n > 1, eps_eff = n² × A_total. The doc could be clarified on this point"*
  — and resolves it in favour of the $n^2$. The same report's Truth Anchor 3 describes
  $\varepsilon = n^2 \times$ absorptance as *"the effective emissivity (thermal radiation
  emitted, normalized to incident flux)"*, which is the error in one line: emissivity is
  normalised to **blackbody emission**, not to incident flux.
- `src/radiant/optics/tests/test_element.py::test_cavity_nonzero_absorption`'s own
  docstring calls $1 - T_{\mathrm{sys}} - R_{\mathrm{sys}}$ the *"Kirchhoff emissivity"* —
  then never asserts `eps_eff` against it.

### 7.3.5 The steelman, and why it fails

Is there a configuration where the $n^2$ belongs? Yes — an **immersed** detector, in
optical contact with the substrate, sees $n^2$ more étendue. But that factor belongs to
$\Omega_{\mathrm{cone}}$, not to $\varepsilon$: RADIANT computes
$E_{\mathrm{FP},i} = \Omega_{\mathrm{cone}} \cdot \varepsilon_i \cdot B \cdot \prod \tau_j$
with $\Omega_{\mathrm{cone}}$ evaluated in vacuum from the working f/# (`etendue_cone.py`).
Putting an étendue factor inside an emissivity makes $\varepsilon$ exceed 1 and breaks the
Kirchhoff identity that the same module's validation check asserts. Even in the immersion
case the $n^2$ is in the wrong place.

**If the owner reads this and concludes the shipped model is right, the falsifiable claim
to attack is §7.3.1 Route 1**: that $\varepsilon_2 = 1 - T_{\mathrm{sys}} -
R_{\mathrm{sys}}$ for side-2 illumination. Everything else follows from it.

## 7.4 Where the library lives

**Recommendation: `src/radiant/data/tables/substrates/`, one YAML per material, loaded by
a new `SubstrateLibrary` in `radiant/data/substrate.py`, exactly parallel to
`FPALibrary`.** Confirmed as the right home for four reasons:

1. `OPERATING_MODEL.md` §6 already carves out `src/radiant/data/tables/` as the bundled
   reference-data tree that ships in the wheel and keeps its own `MANIFEST.md` beside the
   data (the carve-out `check_org_rules.py` implements).
2. The FPA preset format already solves the problems this data has: native-unit storage
   with conversion at apply time (Rule 2), per-value `source` / `basis` / `location`
   attribution, `basis: assumed` values carrying a justification note, and reference
   documents living repo-only under `docs/validation/` with hashes.
3. `data/` may import `radiant.core` only — which is all a substrate loader needs
   (`SpectralData`, the unit registry, `RadiantError`).
4. Resolution happens **pre-chain** in the API layer, like the FPA presets and the
   spectral libraries, so Rule 6 (stages do not read files) is untouched: the io/API
   layer resolves `substrate: germanium` into the `alpha` / `n_refr` `SpectralData` the
   `CavityModel` already takes, and the optics stage sees no change at all.

The per-material **reference documents** (the Crystran pages; the refractiveindex.info
YAMLs are themselves the primary artefact) go to a new
`docs/validation/substrate_datasheets/` with a `MANIFEST.md` carrying URL, retrieval date
and SHA-256 — the Rule 26(c) pattern Gap 119 established, repo-only, never in the wheel.

---

# 8. Grading against reality (§4.5)

`grade_substrate_data.py` runs three tiers, all against the **shipped** `CavityModel`.

## 8.1 Tier 1 — material-data grading, no free parameters

Push the proposed n(λ)/α(λ) through the shipped cavity model for an **uncoated** 3 mm
window (Fresnel $R = ((n-1)/(n+1))^2$ on both faces) and compare the resulting
$R_{\mathrm{sys}}$ against each vendor page's independently published two-surface
reflection loss. Nothing is fitted.

| material | λ [µm] | n published | n proposed | Δn | RL published [%] | RL model [%] | residual [pp] |
|---|---|---|---|---|---|---|---|
| germanium | 10.60 | 4.0021 | 4.0020 | −0.0001 | 53.0 | 52.65 | −0.35 |
| silicon | 5.00 | 3.4223 | 3.4195 | −0.0028 | 46.2 | 45.81 | −0.39 |
| ZnSe | 10.60 | 2.4028 | 2.4028 | −0.0000 | 29.1 | 29.05 | −0.05 |
| ZnS-MS | 10.00 | 2.20084 | 2.2007 | −0.0002 | 24.7 | 24.39 | −0.31 |
| sapphire | 1.06 | 1.75449 | 1.7546 | +0.0001 | 14.0 | 13.96 | −0.04 |
| CaF₂ | 5.00 | 1.39908 | 1.3990 | −0.0001 | 5.4 | 5.38 | −0.02 |
| BaF₂ | 5.00 | 1.45 | 1.4511 | +0.0011 | 6.5 | 6.55 | +0.05 |
| fused silica | 0.40 | 1.47012 | 1.4701 | +0.0000 | 7.0 | 6.99 | −0.01 |

All eight within **0.4 percentage points** of the published reflection loss; n within
0.003 everywhere, 0.0003 for six of eight. The small systematic negative residual on the
high-index rows is vendor rounding of a quantity quoted to two significant figures.

Tier 1 is the strongest grading available for this data product, because
$1 - T_{\mathrm{sys}} - R_{\mathrm{sys}}$ — the absorptance Tier 1 constrains — **is** the
emissivity (§7.3.1). Grading the throughput grades the emission.

## 8.2 Tier 2 — the emissivity table

Reproduced as the §7.3.2 table. `eps_correct` equals the absorptance identically;
`eps_shipped` is high by $n^2/(1 + R_1 b)$.

## 8.3 Tier 3 — a warm-optics / cold-shield budget

**On sourcing.** The study could not retrieve a single published end-to-end warm-optics
budget for a named refractive IR head with the tooling available (no WebSearch; Crossref,
arXiv and NTRS searched). Rather than cite one from memory, Tier 3 constructs the budget
from first principles using (a) the proposed material data, (b) the **shipped**
`etendue_cone_solid_angle_sr` ($\Omega = 2\pi(1 - \cos\theta)$, $\theta = \arctan(1/2N)$),
and (c) the published NETD class figures for cooled MWIR cameras, and states the
falsifiable claim. This is a weaker anchor than the task hoped for and is recorded as
such.

Configuration: Si 5 mm + Ge 5 mm + Si 5 mm triplet (LWIR cases: Ge 8 mm doublet), AR
$R = 0.01$ per surface, optics at 300 K, cold shield matched to the working f/#.

| case | optics/scene (shipped) | optics/scene (correct) | optics e⁻/frame shipped | correct | NETD error |
|---|---|---|---|---|---|
| MWIR 3–5 µm, f/2.5, 300 K scene | 0.329 | **0.027** | 5.28e5 | 4.38e4 | +13.9 % |
| MWIR 3–5 µm, f/2.5, 230 K cloud top | 8.55 | **0.708** | 5.28e5 | 4.38e4 | +135.7 % |
| LWIR 8–12 µm, f/2.0, Ge doublet, 300 K scene | 0.654 | **0.041** | 6.34e7 | 4.00e6 | +26.8 % |
| LWIR 8–12 µm, f/2.0, Ge doublet, 230 K cloud top | 2.86 | **0.180** | 6.34e7 | 4.00e6 | +81.6 % |
| LWIR space-looking, ZnS dome + Ge doublet, 50 K background | — | — | 8.81e7 | 9.21e6 | n/a (*) |

(*) no scene signal to normalise NETD against — the warm optics *are* the background.

**The reality check.** A well-designed AR-coated MWIR objective contributes a few percent
of a cold-shielded 300 K background — this is the standard design rule, and it is why
uncooled-optics MWIR and LWIR cameras work at all. The corrected model gives **2.7 %**
(MWIR) and **4.1 %** (LWIR). The shipped model gives 33 % and 65 %, and in the 230 K
cloud-top case says the warm optics outshine the scene **8.5 : 1** — a camera that cannot
image a cloud top. The corrected column also lands the MWIR shot-limited NETD at 22.4 mK,
inside the ≤ 20–25 mK band this camera class publishes; the shipped column gives 25.6 mK
for the same hardware.

**Where the defect is and is not results-affecting.** The benign-looking +13.9 % in row 1
is the honest headline for a 300 K-scene MWIR sensor: the scene flux dominates, so a 12×
error in a small term is a 14 % error in NETD. The defect becomes first-order exactly
where warm-optics self-emission is the design driver — cold scenes, LWIR, high-index
substrates, space-looking geometries — which is the class of problem RADIANT exists to
analyse.

---

# 9. The GUI surface — specification

Specification only; nothing is built. Any GUI change goes through the live-review loop.

## 9.1 Where the picker lives: a **Substrate column** in the element table, not a card

**Specification.** Add `_COL_SUBSTRATE` to `optical_element_editor.py`'s column set,
between `_COL_KIND` and `_COL_VALUE`, rendered as a `QComboBox` cell widget on
**REFRACTIVE rows only** and as an inert em-dash on REFLECTIVE / COLD_STOP rows.

Rationale, against the FPA-card alternative:

- The FPA selector is a **card** because an FPA preset is singular (one focal plane per
  sensor) and writes *many* dot-path parameters. A substrate is **per row** — a train has
  up to a dozen refractive elements with different materials — and writes *two* spectral
  quantities into one document entry. Per-row data belongs in the per-row table.
- The editor already carries two per-row combos (`_COL_TRANSFER`, `_COL_KIND`) with
  exactly this show/hide-by-mode behaviour, and the module docstring already frames a
  refractive row as having its own axis. A third combo is the established pattern, not a
  new one.
- The editor's **entry-faithful serialization** contract (CU-344) is what makes a column
  safe: a commit is the stored entry with only the table's cells overlaid, so a blank
  substrate cell writes nothing and the io parser's defaults keep applying.

**What the combo contains**, in order: `(no substrate — alpha/n given explicitly)`, then
the tier-A materials, then the tier-B materials under a separator labelled
`— flagged: class-typical alpha —`. Tier is a library field, so the combo reads it rather
than hard-coding a roster (the FPA picker's `available_fpa_parts()` precedent).

**A new API call is required.** `gui/` may import `radiant.api` + `radiant.core` only, so
the roster comes from a new `radiant.api.substrate.available_substrates()` returning a
tuple of `SubstrateInfo` (name, formula, window, tier, anchor count, citation URL) —
exactly the shape `available_fpa_parts()` has.

**Plus a details dialog**, reached from a per-row context-menu action
*Substrate details…* (the row context menu already exists for the Gap 103 configure
actions). It shows the material's window, reference temperature, validity window, the
per-anchor provenance table, and an **Open reference document** button with the FPA
selector's repo-PDF-then-citation-URL fallback.

## 9.2 What the operator sees once a substrate is chosen

Three surfaces, and the plan's §4a guess about one of them is **wrong**:

**(a) The ε column, already there, already correct.** `_COL_EPS` is read-only and filled
from `radiant.api.preview_optical_elements` (band-mean Kirchhoff ε). Choosing a substrate
makes a previously-0.000 refractive row show a real ε. That is the single most valuable
piece of feedback in the whole feature and it needs **no new widget** — it is why the
column exists.

**(b) A new α(λ) figure — NOT a curve on `plot_coating_spectra`.** The plan proposed
adding α to the existing per-element coating-spectra plot. That cannot work:
`plot_coating_spectra` hard-sets `ax.set_ylim(0.0, 1.05)` and labels its axis
"R / T / ε (dimensionless)", because every quantity it plots is a dimensionless fraction
in [0, 1]. α spans 10⁻⁵ to 10¹ cm⁻¹ — five decades on a different dimension. Putting it
on that axis renders every material except ZnS-MS as a flat line on zero.

**Specification:** a new `radiant.api.plot.plot_substrate_absorption(series, *, title)`
(Rule 19 — one computation, one module; it is a distinct figure, not a variant), with a
**log y-axis** in the operator's chosen α unit (§9.4), one curve per distinct substrate in
the train, and the published anchors overplotted as **markers** so the operator can see
which parts of the curve are measured and which are interpolated. That marker overlay is
the feature that makes §7.1's tier distinction visible rather than buried in a manifest.
It mounts on the Transmission tab beside the coating-spectra figure.

**(c) An inline note when a tier-B material is in the train**, routed through the
existing advisory-note channel, naming the grade spread: *"L2 substrate `silicon`: α(λ) is
class-typical CZ, one published anchor at 3.0 µm; CZ/FZ grade spread exceeds 10× at 9 µm.
Emission from this element is an order-of-magnitude estimate."* This is the
workflow-visible half of §7.1's honesty posture — a `grade_note` nobody reads is not a
disclosure.

## 9.3 Switch semantics: **mutual exclusion in the io parser, not a companion reset**

The plan proposed the companion-reset pattern (`architecture_switch.py`,
`edit_guard.apply_edit`). **That machinery does not apply here**, and the distinction is
load-bearing:

`edit_guard.apply_edit` withdraws **dot-path parameters** via `Sensor.reset(name)` then
`Sensor.set(dotpath, value)`. The optical element train is not a dot-path parameter — it
is the declarative element *document*, committed whole through the io parser under the
pseudo dot-path `optics_config.element_list`. There is no `Sensor.reset("L1.alpha")` to
call. Reaching for `companion_withdrawals` here would mean inventing dot-paths for
document keys.

**Specification instead:**

1. **At the document level**, `substrate` and the pair (`alpha`, `n_refr`) are mutually
   exclusive keys on one entry. The io parser's REFRACTIVE dispatch
   (`element_config.py:275`) raises `ElementConfigError` when an entry carries both —
   the same over-specification posture Rule 5 takes on emissivity and the cavity already
   takes on R-and-T per surface. **The io parser is the single validation authority**
   (the editor's own docstring says so); the GUI does not re-implement the rule.
2. **At the editor level**, choosing a substrate on a row **drops** that entry's `alpha`
   and `n_refr` keys and adds `substrate`, as one logical commit — the entry-faithful
   overlay already supports key removal. Choosing `(no substrate)` does the reverse:
   drops `substrate`, and leaves `alpha` / `n_refr` **blank** rather than back-filling
   them from the library. Back-filling would silently convert a library value into an
   explicit user value, which is the drift CU-344 was about.
3. **The operator is told**, in the same inline message band the editor already uses for
   pending drafts: *"L1: substrate `germanium` now supplies α(λ) and n(λ); the explicit
   values you had were withdrawn."* A withdrawal the operator cannot see is the failure
   mode the Gap 117 companion-reset work existed to fix.
4. **Switching between two substrates** is not a withdrawal at all — it rewrites one key.
   No message needed beyond the refreshed ε column and α figure.

## 9.4 Display units: canonical **1/m**, native and default-display **cm⁻¹**

**Specification:**

- **Canonical stays `1/m`.** `CavityModel.alpha` already consumes 1/m, Rule 2 makes
  metres the canonical length, and changing it would churn the one module that is right.
- **Register the pair** in `core/units.py`: `("1/m", "1/m"): 1.0` and
  `("1/cm", "1/m"): 100.0`. Neither exists today — the registry has no reciprocal-length
  dimension at all.
- **The library's YAML stores cm⁻¹**, the unit every source publishes, with conversion at
  apply time via `ParameterSet.set(..., unit=...)`. This is the FPA preset contract
  verbatim ("values are stored in the cited document's native unit").
- **The GUI defaults the α display unit to cm⁻¹**, with 1/m available, and entry and
  display symmetric — the GUI's hard display-unit rule.

**The precedent to cite in the ruling is Gap 135 / `A/cm2`.** The registry already made a
datasheet unit canonical over the SI form for current density, with the reasoning recorded
inline: *"the unit every HgCdTe datasheet and both predictive laws are published in… the
m2/cm2 choice is a silent 1e4 trap when an analyst converts by hand."* α is the identical
situation with a factor of 100. The recommendation above keeps the canonical SI (because
the consumer is already 1/m) while taking the datasheet unit everywhere a human reads or
types — which gets the Gap 135 benefit without the Rule 2 tension.

**Unit token spelling:** `1/cm`, not `cm^-1` or `cm-1`. The registry already uses the
`A/cm2`, `W/m2/um`, `1/s`, `%/hour` style — ASCII, slash-delimited, no caret (Rule 30: no
non-ASCII source literal). The GUI renders it as cm⁻¹ via the theme's display mapping, as
it already does for µm.

## 9.5 The unavailable-material path: an error that names the alternatives

**Specification:** the combo is a **closed list** — an operator cannot type a material
name, so the "unknown name" case cannot arise from the GUI. It can arise from YAML, and
there the `SubstrateLibrary` raises a `SubstrateError(RadiantError)` with the
`FPAPresetError` text shape: *what* (`Unknown substrate 'zinc_telluride'`), *why* (`only
substrates shipped in the library can be resolved by name`), *action* (`Choose one of:
germanium, silicon, …, or give alpha and n_refr explicitly`), *context* (`{"name": …,
"root": …}`). The GUI surfaces it through the shared `ActionableErrorDialog`, as a
rejected row edit already is.

**The important half of this question is the material that is wanted but absent** — and
the answer must not be a nearest-neighbour substitution. Three explicit paths, in the
error's `action` line and in the picker dialog's footer:

1. **Give `alpha` and `n_refr` explicitly** — the path that exists today and keeps
   working. The combo's `(no substrate — alpha/n given explicitly)` entry is a
   first-class choice, not a null state.
2. **Model it as a Kirchhoff-equivalent reflective train** — what scenarios 10.2 / 10.4
   do. Documented in the picker footer with a link to the guide, because an analyst
   holding only a net transmission has no other defensible option.
3. **File a Gap** for the material, with the data the library needs named (window, n
   source, α anchors). The picker footer says so; the §7.1 tier framework means a new
   material is an additive YAML, not a code change.

What it must **never** do is fall back to a similar material or to α = 0 (Rule 17).
Note that α = 0 is *already* what a simple refractive element gives (ε = 0 by Gap 127
rule 3), which is precisely why the unavailable path must be loud: the silent-fallback
behaviour is the default behaviour.

## 9.6 Live-review script

The feature's live review should walk: load a MWIR triplet config → set three refractive
rows to `(no substrate)`, observe ε = 0.000 on all three → set L1 to `germanium`, observe
the ε column populate and the α figure appear → open *Substrate details…*, open the
reference document → set L2 to `silicon` and read the tier-B advisory note → switch L1
from `germanium` to `zinc_selenide` and watch ε drop two decades → set L1's
`temperature_K` to 400 K and confirm the validity-window error fires with an actionable
message → switch L1 back to `(no substrate)` and confirm the α/n cells are blank, not
back-filled.

## 9.7 Recommended Gap

The GUI surface above is a capability, not a defect, so it belongs in `gaps.md` rather
than the cleanup backlog. **Recommend minting Gap 142 — "Substrate material library and
its element-editor surface"**, with §3 / §7.4 / §9 as its specification and this study as
its charter. Not minted by this study: the number must be reserved against `origin/main`
at implementation time, and §7 is not yet ratified.

---

# 10. If ratified: implementation shape and cost

## 10.1 The §7.3 fix is nearly free and should land first, independently

Blast radius, measured:

- **No committed test asserts a hard-coded non-zero cavity emissivity.** The two tests
  that assert `eps_eff` assert the α = 0 and d = 0 cases (both 0.0), which the corrected
  form also satisfies. `test_element_list.py:364` reads
  `cavity_lens.emissivity.values` rather than a literal, so it stays green by
  construction.
- **No golden config, integration fixture or scenario uses the cavity path** — 10.2 and
  10.4 use the fictitious-mirror substitution (§5). So the fix is results-affecting in
  principle and moves **zero committed number**.
- The change is: the `eps_eff` numerator in `cavity_model.py`, deleting the
  `np.clip(eps_vals, 0.0, 1.0)` in `element.py` (and keeping a `max(·, 0)` floor only if
  a reviewer wants defence against negative α, which `__post_init__` already rejects),
  the theory doc's §1.1 expression, and `prompt_3B1_report.md`'s correction — which,
  being a `docs/reports/` point-in-time record, is **immutable** (Rule 24), so the
  correction is a note in the theory doc, not an edit to the report.
- New Level 0 tests (Rule 18, written first): ε = A to 1e-12 for a spread of
  $(R_1, R_2, \alpha d, n)$; ε ≤ 1 over a dense sweep; the opaque limit ε → $1 - R_2$;
  independence from n at fixed α·d.
- A `CHANGELOG.md` entry under `[Unreleased]`, prefixed **Results-affecting:**, stating
  direction and magnitude (refractive cavity emissivity falls by $n^2/(1+R_1 b)$ —
  15.9× for Ge).

Recommended sequencing: **land §7.3 before the library.** The library's whole purpose is
to feed α and n into `eps_eff`; shipping it onto an expression that is 16× high would
make every new material immediately wrong, and would bake the error into the first
scenario that adopts a substrate.

## 10.2 The library, in dependency order

1. `core/units.py`: the `1/cm` ↔ `1/m` pair (§9.4). Trivially testable; nothing depends
   on it yet.
2. `data/substrate.py` + `data/tables/substrates/`: `SubstrateLibrary`, format version 1,
   `SubstrateError`, validity-window enforcement (§7.2), the eight-minus-two materials
   (§7.1), `MANIFEST.md`. Mirrors `data/fpa.py`; schema conformance of every shipped
   entry asserted by a test, as `test_fpa_presets.py` does.
3. `docs/validation/substrate_datasheets/` + manifest: the Rule 26(c) reference documents.
4. `io/element_config.py`: resolve `substrate:` into `alpha` / `n_refr`; reject the
   over-specified entry (§9.3.1).
5. `api/substrate.py`: `available_substrates()`, `SubstrateInfo` — the GUI's only door.
6. `api/plot.py`: `plot_substrate_absorption` (§9.2b).
7. GUI: the column, the details dialog, the figure, the advisory note (§9) — behind the
   live-review loop.

Steps 1–6 are a `src/` diff and pay the full gate battery; step 4 touches no `_schema.py`
but step 2's parameter surface may, in which case the full GUI suite runs regardless
(the CU-262/CU-309 rule).

---

# 11. Open items the study did not close

| Item | Why it is open | Disposition |
|---|---|---|
| α(λ,T) as a decomposition model | No published α(λ,T) data exists to validate against; the model's own uncertainty matches the correction (§7.2) | v2; revisit if a laser-calorimetry source surfaces |
| Primary (not manufacturer-secondary) α for Ge | Crystran attributes its α row to *"Manufacturers Published Data"*. The primary laser-calorimetry literature exists (e.g. the 10.6 µm Ge absorption measurements of the 1970s) but was not retrievable with the available tooling | record in the material YAML's `sources` note, as done; upgrade opportunistically |
| Sapphire and fused silica α(λ) | One anchor each; tier C (§7.1) | v2 candidates, explicitly not shipped |
| Birefringence | Sapphire's o and e rays differ by ~0.008 in n; format version 1 has no direction field | deferred with sapphire itself |
| `constants.py` has no `eps_0` / `m_e` | The α(λ,T) Drude term needs both. A physics module importing them from scipy would violate Rule 13 | only bites if α(λ,T) is implemented; note carried in `ge_alpha_temperature.py` |
| Off-normal path length | The theory doc's `beer_i = exp(-alpha_i d_i / cos(theta_r,i))` carries a refraction-angle path lengthening that `cavity_model.py` omits (it computes `exp(-alpha*d)` flat). At f/2 inside Ge the marginal internal ray is 3.5° off-normal, $\cos\theta = 0.998$ — negligible, but the doc and the code disagree | Findings-Log line, recorded 2026-10-04 |
| No retrievable published end-to-end warm-optics budget | §8.3 constructs its budget from first principles and states the falsifiable claim rather than citing from memory | recorded as a weaker-than-hoped anchor |

---

*Opened 2026-10-04 from [[CU-394]]; study completed 2026-10-04. Moves to `docs/archive/`
with a HISTORICAL banner in the PR that completes it (Rule 24) — which is the PR that
lands §10, not this one.*
