# Configuration Set Expansion Plan — 12-Member Cap + Per-Configuration Optical Elements

**Status:** Active
**Owner trigger:** 2026-09-01 — "OLI is the perfect test case. What all needs to be updated?" after scenario 9.4's 8-band study hit both v1 limits on the first flagship use.
**Ratified inputs:** cap 8 → **12** (owner, 2026-09-01); override mechanism = **replace-by-name** (§3a, owner, 2026-09-02); GUI editing scope = **full per-configuration Elements-tab editing** (§4a, owner, 2026-09-02). No decisions remain open.
**Delivers:** Gap 103 (per-configuration prescriptions, DEFERRED → PLANNED with this document); the ADR-0010 D-E cap amendment; scenario 9.4 as the acceptance showcase — all nine OLI-2 bands in one study file.

---

## 1. Why now, and why these two together

ADR-0010 v1 shipped two deliberate simplifications: at most 8 configurations (D-E) and one
shared `optical_elements` document (D-7). Scenario 9.4 — the first flagship study — hit both
in one afternoon: nine bands need nine configurations, and the pan band's filter overlaps
green/red so no shared composite can carry it (Gap 103's recorded re-audit instance,
2026-08-29). The two limits fail together on any real multi-band instrument, so they lift
together, with the OLI study as the acceptance case for both.

Results-neutrality by construction: neither change touches `radiant.core` or any physics
stage. Existing configs and studies load unchanged; every new behavior is opt-in via new
section content.

## 2. Phase 1 — raise the cap to 12 (effort S)

One semantic constant, mirrored in one io default, displayed in two GUI surfaces, asserted
in three test files, documented in four docs.

| Surface | File | Change |
|---|---|---|
| The constant | `api/config_set.py` | `MAX_CONFIGS: ClassVar[int] = 8` → `12`; the add-configuration error's what/why text follows automatically |
| io mirror | `io/config_set_section.py` | `_DEFAULT_MAX_CONFIGURATIONS = 8` → `12` (the api layer passes `MAX_CONFIGS` in; the default exists for bare section loads — keep the two synced, one comment cross-references the other) |
| Accent palette | `gui/themes/tokens.py` | `config_accents` grows 8 → 12 entries in **both** themes; same index = same hue across themes (identity across theme toggle). Four new hues per theme, chosen against the panel surfaces and checked for pairwise distinguishability (including for the common CVD axes — the dataviz palette method, applied to chips) |
| Selector band | `gui/widgets/configuration_bar.py` | comment currently notes the accent tuple "not reachable while MAX_CONFIGS is 8" — reword; verify wrap behavior at 12 tabs (CU-331's stacked band is the layout that must absorb it; watch item §7) |
| Manager dialog | `gui/widgets/configuration_manager_dialog.py` | the add-row limit and its explanatory text |
| Tests | `api/tests/test_config_set.py` (cap boundary: 12 accepted, 13th refused with the actionable error); `gui/tests/test_configuration_selector.py` (`accent_tuple_covers_every_allowed_configuration` — asserts palette length ≥ MAX_CONFIGS, must pass at 12); `gui/tests/test_configuration_manager.py` (limit text) |
| Docs (Rule 20, same PR) | `RADIANT_Config_Format.md` §1.9 ("1–8" table row), `RADIANT_Scripting_API.md` §2.5c ("up to 8"), `RADIANT_GUI_Architecture.md` (selector-band capacity), ~~`RADIANT_Physics_Inventory.md` (capability mention)~~ (verified 2026-09-02: that doc carries no configuration-set mention — no edit; the stale capability claims lived in `docs/guides/` instead and were fixed), `gui/workers.py` + `docs/guides/{configuration,scripting,trade_studies}.md` (stale "eight"/"ninth" claims), ADR-0010 (dated amendment line on D-E: "2026-09-01 — cap raised to 12, owner-ratified; see this plan"), `docs/tracking/gaps.md` Gap 102 landed-row ("up to 8 named configurations") |
| CHANGELOG (Rule 29b) | Changed: public capacity of a configuration set, 8 → 12 |

Gate: full battery (touches `api/` + `io/` + `gui/`).

## 3. Phase 2 — per-configuration optical elements (Gap 103 v1.1) (effort M)

### 3a. Override mechanism — ratified: replace-by-name (owner, 2026-09-02)

The `configurations:` section gains an `optical_elements:` sub-key mapping member name →
override. Three candidate semantics were weighed; **replace-by-name is ratified**.

1. **Replace-by-name (ratified).** An override is a list of complete element entries;
   each entry **replaces** the shared-document entry with the same `name`. A name with no
   shared-document match is an error (no silent adds; adding/removing elements per
   configuration is a different feature, deliberately excluded). The shared train is stated
   once; a configuration states only what differs — the ADR-0010 "the study states what
   differs" philosophy. Every override entry is a *complete* entry re-validated by the io
   parser (single validation authority, Kirchhoff included); there is no field-level merge,
   so no patch-resolution semantics.
2. Whole-document replacement — simplest matching rules, but the OLI study would restate
   five shared elements nine times; repetition is the failure mode the model exists to
   prevent. Not recommended.
3. Field-level patching — most compact, but reintroduces exactly the sparse-overlay
   resolution ADR-0010 D-A rejected. Not recommended.

```yaml
optical_elements:                     # shared train — stated once
  - {name: M1, ...}                   # ×4 mirrors, window
  - {name: band_filter, transmittance: data/filter_b01.csv, ...}

configurations:
  names: [B1_CA, B2_Blue, ..., B8_Pan, B9_Cirrus]
  optical_elements:                   # NEW sub-key (this phase)
    B2_Blue:
      - {name: band_filter, transmittance: data/filter_b02.csv, ...}
    # ... one single-entry override per band; B1 uses the shared default
```

### 3b. Touched surfaces

| Surface | File | Change |
|---|---|---|
| Section schema | `io/config_set_section.py` | parse + validate the sub-key: keys must be member names; each override entry validated through `parse_element_entries` (fail at load, named configuration in the error); replace-target name must exist in the shared document; `is_file_path` values relativize on save / resolve on load (CU-177 parity with configured values) |
| Materialization | `api/config_set.py` | store overrides; `sensor_for(i)` builds the *effective* document (shared entries, overridden ones swapped by name) and attaches via the existing `Sensor.set_optical_elements` — no new attachment path, Rule 6 unchanged; new API pair `set_element_override(name, entries)` / `clear_element_override(name)` + accessor; `save`/`load` round-trip; `validate()` covers every member's effective document |
| Single-store analog | `api/config_set.py` | invariant: an element name is overridden in a configuration **or** inherited — never both ambiguously; enforced by construction (dict keyed by member → list keyed by element name, dense entries) |
| CLI | none structural | `radiant run --configuration` and `radiant validate` already route through `ConfigurationSet`; validate's per-member lines gain element errors for the member that owns them |
| GUI | `gui/widgets/optical_element_editor.py` + host | see §4a — full per-configuration editing (ratified scope) |
| Tests | `io` section tests (round-trip, non-member key, unknown element name, bad entry, path resolution); `api/tests/test_config_set.py` (effective-document materialization, evaluate-all with per-member trains, save/load, coating-detail interplay); GUI tests per §4c matrix |
| Docs (Rule 20) | `RADIANT_Config_Format.md` §1.9 (sub-key spec + binding rules table row); `RADIANT_Scripting_API.md` §2.5c; `RADIANT_GUI_Architecture.md` Elements-tab row; **ADR-0010**: D-7 gains a dated supersession note pointing here (the ADR's "whole-document vs patching" open decision is resolved by §3a's ratification) |
| Registries | Gap 103 → RESOLVED at delivery (this plan is its PLANNED disposition today); CHANGELOG Added (Rule 29b/c) |

Gate: full battery.

## 4. GUI editing scope — ratified: full per-configuration editing

### 4a. Ratified scope (owner, 2026-09-02)

The Elements tab gains a **scope control** — *Shared document* vs *This configuration* —
mirroring ADR-0010 D-8 inline-edit semantics. In both scopes the tab renders the **active
configuration's effective train**; rows swapped in by an override carry an
"overridden — <configuration>" badge, and the coating-detail pane (Gap 116) shows the
effective per-band element for the active configuration.

- **Shared scope:** Apply edits the shared `optical_elements` document — today's behavior,
  unchanged. Overrides are never touched from this scope.
- **This-configuration scope:** Apply **diffs** the edited effective train against the
  shared document and stores exactly the changed entries as replace-by-name overrides for
  the active configuration (§3a semantics — complete entries, re-validated by the io
  parser). An entry edited back to equality with its shared counterpart drops its
  override. Diff-based Apply keeps the persisted YAML minimal — the study states only what
  differs. Element addition/removal remains excluded in both scopes (§7 watch item).

The lighter v1.1 alternative (badge-only rendering, shared-only Apply, YAML-first override
authoring) was considered and superseded by this ratification.

### 4b. Phase-1 GUI test matrix

| Test | File | Asserts |
|---|---|---|
| Accent coverage | `gui/tests/test_configuration_selector.py` | accent tuple length ≥ `MAX_CONFIGS` (12) in **both** themes; same index = same hue across theme toggle |
| Chip distinguishability | same | the 12 accents are pairwise distinct strings in each theme (perceptual/CVD spacing is validated at design time per §7, not asserted numerically) |
| Selector band at 12 | `gui/tests/test_configuration_selector.py` | a 12-member set renders 12 tabs; CU-331 stacked band absorbs them (no crash, all tabs reachable) |
| Manager dialog cap | `gui/tests/test_configuration_manager.py` | add-row enabled at 11, disabled/refused at 12 with explanatory text quoting the cap |
| Cap boundary (api) | `api/tests/test_config_set.py` | 12th accepted; 13th raises the actionable error naming 12 |

### 4c. Phase-2 GUI test matrix

| Test | Asserts |
|---|---|
| Scope control default | tab opens in Shared scope; single-configuration (non-study) files show no scope control |
| Effective-train render | switching active configuration re-renders the effective train; overridden rows carry the badge, inherited rows do not |
| Shared Apply untouched | Apply in Shared scope edits the shared document only; existing overrides survive verbatim |
| Diff-based Apply | in This-configuration scope, editing one element and applying stores exactly one replace-by-name override for the active member |
| Override drop on equality | editing an overridden entry back to shared equality and applying clears that override |
| Validation routing | an invalid override edit surfaces the io parser's error naming the configuration; nothing is stored |
| Coating-detail pane | shows the effective (overridden) element for the active configuration |
| Round-trip | GUI-authored overrides save/load identically via `io/config_set_section.py` (CU-177 path relativization included) |

## 5. Phase 3 — the OLI showcase (acceptance case; effort S once 1+2 land)

- `9.4`: replace `oli2_30m_bands_study.yaml` with `oli2_all_bands_study.yaml` — **all nine
  bands, one file**: shared four-mirror train + window; a shared default `band_filter`;
  eight single-entry overrides giving every band its own synthesized strip (pan included —
  its 18 µm pitch and 1.8 ms integration are ordinary configured scalars). The composite
  butcher-block element and its Gap-103-workaround narrative retire from the study
  (Rule 27: the superseded study file is deleted; the composite CSV stays — the per-band
  standalones don't use it either, but the generator and walkthrough keep documenting it
  as the D-7-era artifact until the walkthrough rewrite lands, which drops it).
- Acceptance criteria: (1) `radiant validate` — 9/9 OK; (2) evaluate-all in one pass, 9
  Performance columns readable under CU-331/332/333 behavior; (3) each configuration's SNR
  matches its standalone per-band file to `rel < 1e-9` (identical filters now — the ≤0.5%
  B1/B2 composite-seam artifact disappears and its walkthrough paragraph is rewritten);
  (4) coating-detail pane shows the per-band filter for the active configuration.
- Docs: 9.4 walkthrough + gui_workflow rewrite (the "filter trick" section becomes the
  per-configuration-elements showcase), 09 README row, CHANGELOG, Gap 103 closure record.

## 6. Sequencing and gates

Phase 1 and Phase 2 are independent PRs (1 does not block 2, but the showcase needs both).
Each phase: one branch, full battery (api/io/gui surfaces), lock-step docs in the same PR,
merge, push. Phase 3 is scenario + docs (scenario gates). Estimated: Phase 1 ≈ half a day;
Phase 2 ≈ 1–2 days including tests; Phase 3 ≈ half a day.

## 7. Risks and watch items

- **12 distinguishable accent chips** — hue spacing tightens; validate pairwise contrast in
  both themes and under CVD simulation before landing; if 12 legible hues prove unreachable,
  fall back to hue+shape (chip glyph variation) rather than shrinking the cap.
- **Selector-band width at 12 tabs** — CU-331's stacked band owns the full window width;
  12 named tabs at laptop width may still overflow. If they do, that is a new, honest
  defect (scroll or overflow affordance on the bar), filed then, not pre-built now.
- **Override semantics creep** — replace-by-name deliberately excludes per-configuration
  element *addition/removal* (different trains, not different coatings). If a real scenario
  needs structurally different trains per configuration, that is a new gap with its own
  design conversation, not an extension smuggled into this one.
- **Matrix at 9+ columns** — CU-332/333 made wide matrices scrollable and frozen-labelled;
  12-configuration studies will exercise them harder. No pre-emptive work; watch.

## 8. Decision log

| Decision | State |
|---|---|
| Cap value = 12 | **Ratified** (owner, 2026-09-01) |
| Override mechanism (§3a) = replace-by-name | **Ratified** (owner, 2026-09-02) |
| GUI editing scope (§4a) = full per-configuration editing — scope control, diff-based override Apply | **Ratified** (owner, 2026-09-02; supersedes the v1.1 badge-only recommendation) |
