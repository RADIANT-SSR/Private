# Refractive Substrate Emission — Design Study

**Status:** Draft — scoping study, opened on an owner ruling. No implementation until §7 is ratified.

**Date:** 2026-10-04
**Category:** C (physics implementation) for the emission path; B for the material-library surface.
**Registry:** [[CU-394]] — this study is that CU's disposition.

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

So this study does **not** propose changing the emission physics. The ruling confirms it
and rejects the alternative that prompted CU-394 — lumping the whole loss into an
element-level `ε = 1 − T − R`, which would silently attribute substrate absorption to
the coatings and vice versa.

**What is actually missing is the substrate's material data.** The cavity needs `alpha`
[1/m] and `n_refr`, which are properties of germanium or silicon or ZnSe, not of the
instrument. An instrument datasheet quotes a band-averaged net transmission and a
surface count and cannot determine them. That is the whole of CU-394.

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

Everything downstream is the existing cavity model, unchanged.

## 4. Open questions for the study

1. **Which substrates ship?** Candidate v1 set: Ge, Si, ZnSe, ZnS (multispectral and
   standard), sapphire, CaF₂, BaF₂, fused silica. Each needs α(λ) and n(λ) over the
   bands RADIANT models, with provenance per Rule 26(c).
2. **Temperature dependence.** Ge's absorption is strongly temperature-dependent in the
   LWIR — free-carrier absorption rises steeply above ~250 K. A cryogenic Ge lens and a
   300 K Ge lens are not the same material. Does v1 carry α(λ, T), or α(λ) at a stated
   reference temperature with a documented limitation?
3. **The n² question.** `eps_eff = T2·n²·(1 − beer)/denom` carries the enhanced
   photon-density-of-states factor. For a high-index substrate with non-trivial
   absorption this can exceed 1 and is clipped. The study must establish the regime
   where the expression is valid and what should happen outside it — a clip is a silent
   failure in the Rule-17 sense and is the one place the current model may need work.
4. **Where the library lives.** `data/tables/substrates/`, consistent with
   `data/tables/fpa/`, and whether it is addressable from the GUI's element editor.
5. **Grading against reality.** A worked case with real material data — the study should
   reproduce a published cold-shield / warm-optics budget for a refractive MWIR head
   and compare.
6. **The GUI surface** (owner scope addition, 2026-10-04) — see §4a.

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
  material column in the element table? The editor already handles per-row kinds
  (MIRROR / LENS) and transfer modes, so a substrate is a third axis on a refractive row.
- **What the operator sees once a substrate is chosen.** The resolved α(λ) and n(λ)
  curves are spectra, not scalars. The Optics workspace already plots coating spectra
  (`plot_coating_spectra`, per-element R / T / Kirchhoff ε) — the natural home is an
  additional curve there, so a user can see *why* their element emits.
- **What happens on a switch.** Changing a substrate changes α and n together. That is
  the companion-reset pattern (`gui/architecture_switch.py`, `edit_guard.apply_edit`) —
  the study should state whether a substrate switch withdraws any explicitly-set
  per-element `alpha`/`n_refr`, the same way an architecture switch withdraws
  counting-only parameters.
- **Display units.** α is quoted in the literature as cm⁻¹ far more often than m⁻¹, and
  the GUI's hard rule is that a value is shown in the unit the user chose, with entry
  and display symmetric. The unit registry needs the `1/cm` ↔ `1/m` pair, and the
  element editor needs to honour it.
- **The unavailable-material path.** What the GUI does when a user wants a substrate the
  library does not carry — the FPA selector's equivalent behaviour is the model, and the
  answer must not be a silent fallback (Rule 17).

**The GUI is specified by this study, not built by it.** Any GUI change goes through the
live-review loop before merge.

## 5. What the scenarios do meanwhile

10.2 and 10.4 model their refractive heads as Kirchhoff-equivalent reflective trains at
`R = τ^(1/N)`, which reproduces the net throughput exactly and emits at `ε = 1 − R` per
surface. Each runner documents the substitution. That stays until this study lands; the
numbers are defensible, the configs are not literal.

## 6. Non-goals

- Changing the cavity emission expression's **structure**. The ruling endorses it.
- Coating self-emission. Ruled out: coatings are thin enough that their self-emission is
  negligible for the near-field term.
- A general optical-materials database (dispersion for ray tracing, thermo-optic
  coefficients). This is a near-field emission study; it needs α and n and nothing else.

## 7. Decisions needed before implementation

- The v1 substrate set (§4.1).
- The α(λ, T) ruling (§4.2).
- The n²-validity and out-of-range behaviour ruling (§4.3).
- The GUI surface (§4a) — picker placement, switch semantics, and the α display unit.

---

*Opened 2026-10-04 from [[CU-394]]. Moves to `docs/archive/` with a HISTORICAL banner in
the PR that completes it (Rule 24).*
