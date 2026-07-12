# RADIANT Reference Frames & Frame Conversion

**Date:** 2026-07-12
**Status:** Authoritative — written against shipped `src/radiant/core/quantity.py` and `core/radiometry.py` (2026-07-12 doc-reconciliation pass).
**Depends on:** RADIANT_Signal_Chain_Architecture.md (§3 ChainState, §5 backward propagation), RADIANT_Conventions.md
**Scope:** The reference-frame conversion machinery behind `ChainResult.signal_at()` / `noise_at()`: the `ReferenceFrame` enum, the `ChainQuantity` value object and its forward/backward `.to()`, the transfer-factor chain extracted from `stage_outputs`, how `NoiseTerm.origin_frame` drives conversion at query time, the two distinct frame collections (the query-position enum vs. the registered `RadiometricFrame` snapshots), and the saturated-well `1/gain` fallback. Signal_Chain §5 states the *contract* (what a user can ask, and the canonical frame list); this document is the *mechanism* (how the conversion is actually computed in code).

---

## 0. Why this document exists

Signal_Chain §5 answers *"what can I ask?"* — `result.noise_at("at_aperture")`,
`result.signal_at("dn")` — and gives the conceptual frame table. But the actual
conversion is non-obvious and lives in one file, `core/quantity.py`:

- the composite `post_optics → photoelectrons` factor is **extracted as a ratio**
  `signal_e / L_at_aperture_mean` rather than recomputed from
  `A_collect · Ω_pixel · QE · ∫(λ/hc)dλ · t_int`;
- the forward-factor walk tries a **composite key** when an adjacent single-hop
  factor is missing;
- the `post_readout → dn` step has a **saturated-well `1/gain` fallback** for the
  `signal_e_final == 0` case (Gap 73);
- and the **query-position enum is a different set** from the frame *names* that
  stages actually register in `state.frames`.

None of that is legible from Signal_Chain §5 alone. This document is the mechanism's
home. It also records where §5's frame table has drifted from the shipped enum
(§6, CU-091).

**Module map:**

| File | Owns |
|------|------|
| `core/quantity.py` | `ReferenceFrame` enum, `_FRAME_ORDER`, `FRAME_UNITS`, `_compute_transfer_factors`, `_get_forward_factor`, `ChainQuantity`, module-level `signal_at` / `noise_at` |
| `core/radiometry.py` | `RadiometricFrame` (the registered spectral/scalar snapshots), `NoiseTerm` (value + `origin_frame`) |

---

## 1. Two frame collections, deliberately distinct

RADIANT has **two** collections that both get called "frames," and conflating them
is the main source of confusion:

**(a) `ReferenceFrame` — the query-position enum** (`quantity.py`). Six ordered
positions used *only* by the forward/backward conversion machinery:

| Enum member | `.value` | `FRAME_UNITS` |
|-------------|----------|---------------|
| `AT_TARGET` | `"at_target"` | W/m²/sr/µm |
| `AT_APERTURE` | `"at_aperture"` | W/m²/sr/µm |
| `POST_OPTICS` | `"post_optics"` | W/m²/sr/µm |
| `PHOTOELECTRONS` | `"photoelectrons"` | e- |
| `POST_READOUT` | `"post_readout"` | e- |
| `DN` | `"dn"` | DN |

`_FRAME_ORDER` is exactly this top-to-bottom order; propagation direction is
decided by comparing the source and target indices in it.

**(b) Registered `RadiometricFrame` snapshots** (`state.frames`). Free-form-named
immutable spectral-or-scalar snapshots that stages actually write. As shipped, the
registered names are:

| Frame name | Registered by | Carries |
|------------|---------------|---------|
| `at_aperture_target` | AtmosphereStage | target-only-plus-path spectral radiance |
| `at_aperture` | AtmosphereStage | at-aperture spectral radiance |
| `at_aperture_background` | AtmosphereStage | background-plus-path spectral radiance |
| `post_optics` | OpticsStage | post-throughput spectral radiance |
| `photoelectrons` | SpectralIntegrationStage | `in_band_value` scalar [e-] |

SourceStage, DetectorStage, and ReadoutStage register **no** `RadiometricFrame`;
their contributions live in `stage_outputs`. The conversion machinery keys off the
enum plus `stage_outputs` plus the single `at_aperture` snapshot's radiance — **not**
off the arbitrary registered names. The one registered frame the machinery reads
directly is `photoelectrons` (the `signal_at` anchor, §4) and `at_aperture` (the
radiance denominator, §3).

---

## 2. `RadiometricFrame` and `NoiseTerm` — the value objects

Both are frozen, validated-at-construction dataclasses in `core/radiometry.py`.

**`RadiometricFrame`** holds `name`, `wavelength_um`, and *either* spectral arrays
(`spectral_radiance`, `spectral_irradiance`, `photon_rate`) *or* an `in_band_value`
scalar — the XOR is enforced in `__post_init__` (Rule 8: spectral integration
happens exactly once, so a frame is either pre- or post-integration, never both).
Spectral arrays must match the wavelength-grid shape; `in_band_value` must be
finite. Consequence (CU-049): pre-integration frames always carry
`in_band_value = None` — the scalar *at* such a frame exists only as a derived
quantity via backward propagation (§3–§4).

**`NoiseTerm`** holds `name`, `value_e` (σ in e- RMS, non-negative finite),
`origin_frame` (a non-empty string naming where the noise was generated),
`physical_basis` (provenance tag), and `contributes_to` (budget names). The
`origin_frame` string is what drives frame conversion at query time (§5); it must
be one of the `ReferenceFrame` `.value` strings for the conversion to resolve.

---

## 3. The transfer-factor chain (`_compute_transfer_factors`)

Forward factors convert left-frame → right-frame **by multiplication**. They are
extracted from `stage_outputs` (and the `at_aperture` frame) on every `.to()`
call — not cached in the state:

| Adjacent hop | Factor | Source |
|--------------|--------|--------|
| `at_target → at_aperture` | `mean(τ_atm)` | `stage_outputs["atmosphere"]["tau_atm"]` (band-averaged) |
| `at_aperture → post_optics` | `mean(τ_opt)` | `stage_outputs["optics"]["tau_opt"]` (band-averaged) |
| `at_aperture → photoelectrons` (composite) | `signal_e / L_at_aperture_mean` | `spectral_integration.signal_e` ÷ `mean(frames["at_aperture"].spectral_radiance)` |
| `post_optics → photoelectrons` | `signal_e / (L_at_aperture_mean · mean(τ_opt))` | derived from the composite above |
| `photoelectrons → post_readout` | `signal_e_final / signal_e` | `readout.signal_e_final` ÷ `detector.signal_e` |
| `post_readout → dn` | `signal_dn_final / signal_e_final` | `readout.signal_dn_final` ÷ `readout.signal_e_final` |

The **`at_aperture → photoelectrons` factor is deliberately a measured ratio**, not
a re-derivation. The forward physics is
`photoelectrons = L_at_aperture · τ_opt · A_collect · Ω_pixel · QE · (λ/hc) · Δλ · t_int`;
rather than recompute each term (and risk drifting from the forward pass), the code
takes `signal_e / mean(L_at_aperture)`, which *inherently* includes QE, fill
factor, area, solid angle, the photon-energy integral, and integration time because
`signal_e` was computed with all of them in the forward pass. The `post_optics`
variant divides out the optical transmittance so the two composite anchors stay
mutually consistent. These composite factors register only when `signal_e > 0` and
the `at_aperture` frame has a positive mean radiance.

### The saturated-well `1/gain` fallback (Gap 73)

The `post_readout → dn` step has two paths:

```
if signal_e_final > 0:      factor = signal_dn_final / signal_e_final   # normal
elif signal_e_final == 0:   factor = 1.0 / gain_e_per_dn                # saturated-well fallback
```

When the well saturates and `signal_e_final == 0` (e.g. a bright background
pedestal fills the well, Gap 73), the normal ratio is `0/0` and would leave `dn`
unreachable — `signal_at("dn")` would raise instead of returning `0`. The fallback
uses the linear conversion `1/gain`: off-chip binning and coadd scale DN and
electrons identically, so the ratio is exactly `1/gain` absent ADC clipping, and a
zero-electron signal never ADC-clips. This keeps `DN` reachable so `signal_at(DN)`
returns `0` rather than raising. `gain_e_per_dn` is
`stage_outputs["readout"]["gain_e_per_dn"]`.

### Walking multi-hop paths (`_get_forward_factor`)

To convert between non-adjacent frames, `_get_forward_factor` walks `_FRAME_ORDER`
from source index to target index, multiplying each adjacent factor. If an adjacent
single-hop key is missing, it looks for a **composite key** that spans from the
current frame to a downstream frame (the `at_aperture → photoelectrons` composite is
the one that exercises this, skipping `post_optics`). Backward conversion computes
the forward factor for the reverse direction and returns its reciprocal. If any
required factor (or composite) is missing, it returns `None`, and
`ChainQuantity.to()` raises `CoreValidationError` naming the available factors — a
missing factor is surfaced, never silently defaulted (Rule 17).

---

## 4. `ChainQuantity` and forward/backward propagation

`ChainQuantity` is a frozen `(value, frame, unit, name)` record. Its one method:

```python
def to(self, target_frame: ReferenceFrame, state: ChainState) -> ChainQuantity
```

recomputes the transfer factors from `state`, gets the cumulative forward (or
inverse) factor between `self.frame` and `target_frame`, and returns a new
`ChainQuantity` with `value × factor` and the target frame's `FRAME_UNITS`. A
same-frame `.to()` returns `self`. Forward propagation (e.g. electrons → DN)
multiplies; backward propagation (e.g. noise referred to the aperture) divides —
both handled by the sign of the index comparison in `_get_forward_factor`.

**`signal_at(state, target_frame)`** reads the `photoelectrons` frame's
`in_band_value` as the anchor, wraps it in a `ChainQuantity` at
`ReferenceFrame.PHOTOELECTRONS`, and propagates to the requested frame. Missing
`photoelectrons` frame (SpectralIntegrationStage not run) → `CoreValidationError`.

---

## 5. `noise_at` — origin-frame-driven conversion

```python
def noise_at(state, target_frame, term_name=None) -> ChainQuantity
```

- **Single term** (`term_name` given): finds the matching `NoiseTerm`, reads its
  `origin_frame` string, converts it to a `ReferenceFrame` enum, wraps `value_e` in
  a `ChainQuantity` at that origin, and propagates to `target_frame`. An unknown
  term name raises `CoreValidationError` listing the available names.
- **Total noise** (`term_name is None`): all noise terms must share a single
  `origin_frame` — a mixed-origin set raises `CoreValidationError` (RSS across
  different frames is physically meaningless without first converting each). It then
  RSS-combines all `value_e` and propagates the total from the shared origin to the
  target. No noise terms at all → `CoreValidationError`.

This is why `NoiseTerm.origin_frame` matters: it is the sole record of *where* each
noise was generated, and the conversion uses it to refer the noise to any queried
frame at query time (nothing is pre-stored per frame). The mixed-origin guard is
the reason DetectorStage/ReadoutStage register their terms at a consistent origin
frame.

---

## 6. Overlap with Signal_Chain §5, and known drift

Signal_Chain §5 is the **contract**: it defines the user-facing query API
(`signal_at` / `noise_at`), the backward-propagation concept, and the canonical
frame list. This document is the **mechanism**: the ratio-extraction of transfer
factors, the composite-key walk, the saturated-well fallback, and the enum-vs-
registered-frame distinction — all non-trivial, all in one file, none visible from
§5. That separation is why the machinery earns a dedicated doc rather than more
prose inside §5.

**Known drift (tracked as CU-091):** Signal_Chain §5's frame table lists seven
positions including an **`at_fpa`** frame (photons/s/pixel/µm) and names the
post-integration frame **`electrons`**. The shipped `ReferenceFrame` enum has
**six** members, has **no `at_fpa`**, and names the frame **`photoelectrons`**.
The §5 table also lists `at_target` as a registered position, but no `at_target`
`RadiometricFrame` is registered by any stage (AtmosphereStage registers
`at_aperture_target`); `AT_TARGET` is reachable only as an enum query position via
the `mean(τ_atm)` factor, not as a stored snapshot. These are documentation-side
mismatches, not code bugs — the shipped enum and machinery are internally
consistent. The reconciliation of §5's table with the shipped enum is CU-091.

---

## 7. How the rest of RADIANT consumes this

- **Public API:** `ChainResult.signal_at(frame)` and `noise_at(frame, term_name)`
  (`io/results.py`, exposed on the `Sensor` result) delegate to the `quantity.py`
  module functions. `ChainQuantity` carries value + unit + frame back to the user.
- **Backward radiometry:** `core/responsivity.py` uses the exported
  `spectral_integration.qe_curve` / `qe_scalar` so a "noise referred to the
  aperture in W/m²/sr/µm" query can include QE without a cross-stage detector
  import (Rule 11).
- **Provenance / inspection:** every registered `RadiometricFrame` remains
  inspectable after the run (`result.frames[...]`), and the transfer factors are
  recomputable from the immutable `stage_outputs` — the state *is* the audit record
  (Signal_Chain §1).

Nothing here is a chain stage; these are `core` value objects and pure query
helpers invoked by the API layer after the chain completes.
