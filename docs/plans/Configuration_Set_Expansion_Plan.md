# Configuration Set Expansion Plan — 12-Member Cap + Per-Configuration Optical Elements

**Status:** Draft
**Owner trigger:** 2026-09-01 — "OLI is the perfect test case. What all needs to be updated?" after scenario 9.4's 8-band study hit both v1 limits on the first flagship use.
**Ratified inputs:** cap 8 → **12** (owner, 2026-09-01). **Open for ratification:** the override mechanism (§3a) and the GUI Elements-tab scope (§4a).
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
| Docs (Rule 20, same PR) | `RADIANT_Config_Format.md` §1.9 ("1–8" table row), `RADIANT_Scripting_API.md` §2.5c ("up to 8"), `RADIANT_GUI_Architecture.md` (selector-band capacity), `RADIANT_Physics_Inventory.md` (capability mention), ADR-0010 (dated amendment line on D-E: "2026-09-01 — cap raised to 12, owner-ratified; see this plan"), `docs/tracking/gaps.md` Gap 102 landed-row ("up to 8 named configurations") |
| CHANGELOG (Rule 29b) | Changed: public capacity of a configuration set, 8 → 12 |

Gate: full battery (touches `api/` + `io/` + `gui/`).

## 3. Phase 2 — per-configuration optical elements (Gap 103 v1.1) (effort M)

### 3a. The one open design decision — override mechanism

The `configurations:` section gains an `optical_elements:` sub-key mapping member name →
override. Three candidate semantics; **recommendation: replace-by-name**.

1. **Replace-by-name (recommended).** An override is a list of complete element entries;
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
| GUI | `gui/widgets/optical_element_editor.py` + host | see §4c — implementation and test matrix (scope decision §4a) |
| Tests | `io` section tests (round-trip, non-member key, unknown element name, bad entry, path resolution); `api/tests/test_config_set.py` (effective-document materialization, evaluate-all with per-member trains, save/load, coating-detail interplay); GUI test per §4 scope |
| Docs (Rule 20) | `RADIANT_Config_Format.md` §1.9 (sub-key spec + binding rules table row); `RADIANT_Scripting_API.md` §2.5c; `RADIANT_GUI_Architecture.md` Elements-tab row; **ADR-0010**: D-7 gains a dated supersession note pointing here (the ADR's "whole-document vs patching" open decision is resolved by §3a's ratification) |
| Registries | Gap 103 → RESOLVED at delivery (this plan is its PLANNED disposition today); CHANGELOG Added (Rule 29b/c) |

Gate: full battery.

## 4. GUI workstream — implementation, tests, and verification

The GUI is the primary interface, and configuration authoring is its most intricate
workflow — this section is the GUI's own implementation-and-verification plan, not a
footnote to the API work. Verification uses the repo's established three layers, at
every phase:

1. **Widget/window pytest** (`src/radiant/gui/tests/`, offscreen, in the merge gate) —
   drives the real `RADIANTMainWindow` on real study files;
2. **Headless real-GUI gate** (`scenarios/tools/verify_gui_open.py`) — opens each
   scenario's GUI baseline through the actual File → Open path and runs its console
   script in the real scripting window;
3. **Human walkthrough** (`GUI_EXERCISE_INDEX.md` + the scenario's `gui_workflow.md`) —
   the owner's click-path for the bespoke interactions no headless harness can judge
   (legibility, chip distinguishability, scroll feel).

### 4a. Elements-tab scope in a study (open decision)

What does the Elements tab show/edit once trains can differ per configuration?

- **v1.1 recommended scope:** the tab renders the **active configuration's effective
  train**; rows swapped in by an override carry an "overridden — <configuration>" badge.
  **Apply keeps editing the shared document only** (today's behavior, unchanged); authoring
  an override happens in YAML / scripting for now, and a follow-up gap tracks full override
  editing in the GUI. Cheap, honest, and the coating-detail pane (Gap 116) automatically
  shows the effective per-band filter.
- Alternative (larger): a per-configuration edit mode on the tab (scope selector shared vs
  this-configuration), mirroring ADR-0010 D-8 inline-edit semantics. Defer unless the
  YAML-first workflow proves painful.

### 4b. Phase 1 GUI — the 12-configuration authoring and reading workflow

Implementation: the §2 rows (accent palette ×12 both themes, manager-dialog limit,
selector-bar wrap note). Tests, all on a real 12-member study fixture:

| Workflow | Test (new or extended) |
|---|---|
| **Authoring to the cap in the GUI** — Edit → Configurations…: add, rename, reorder, duplicate up to 12; the 13th add refused with the actionable error, dialog intact | `test_configuration_manager.py` — extend the add-flow tests from 8 to 12; new 13th-refusal case |
| Selector band renders 12 tabs without pushing anything off-screen | `test_configuration_selector.py` — 12-tab variant of the CU-331 geometry test (bar stacked above strip, strip keeps full width, all 12 tabs reachable) |
| Every slot keeps a stable accent in both themes | existing `accent_tuple_covers_every_allowed_configuration` at 12 + a same-index-both-themes assertion |
| Performance matrix at 12 columns: frozen labels, linked scroll, full-width cards | parameterize the CU-332/333 test class (`TestFrozenLabelColumn`) up from 3 to 12 configurations |
| Switching among 12 tabs re-binds every panel without re-evaluating | extend the existing switch-stability test to the 12-member fixture |

Human pass: chip distinguishability check of the 12 accents in both themes (deliberately
a human judgment — §7 risk row).

### 4c. Phase 2 GUI — per-configuration trains, visible and trustworthy

Implementation (under the §4a ratified scope): effective-train rendering keyed to the
active configuration, override badge, re-render on configuration switch (the tab loads on
`bind_sensor`, and a selector switch re-binds every panel — the test pins this). Tests:

| Behavior | Test |
|---|---|
| Switching configurations swaps the overridden row (e.g. pan's filter) and shows the badge; shared rows unchanged | new `test_element_editor.py` / study-window case |
| Coating detail (Gap 116) follows the active configuration's effective element | extension of the Gap 116 test class onto a study with an override |
| Apply on the shared document while overrides exist preserves the overrides (no silent clobber) | `test_config_set.py` + a window-level case |
| A member's invalid override is that member's failure: named in `radiant validate` and attributed in Messages, never a modal for a non-displayed configuration | extend the Phase-4a failure-attribution tests |
| Evaluate-all runs every member with its own train (different filter ⇒ provably different SNR column) | window-level matrix assertion on a two-member override study |

### 4d. Phase 3 GUI — end-to-end acceptance on the real scenario

- **Headless end-to-end test (merge gate):** open `oli2_all_bands_study.yaml` — the real
  shipped file, not a fixture — in the offscreen window: 9 tabs; evaluate-all completes;
  9 matrix columns under frozen labels; Elements tab shows the active band's own filter;
  coating detail renders it; switching B4 → B8 swaps 36 µm/3.6 ms readouts for
  18 µm/1.8 ms and the filter row. One test, the whole demo.
- **Scenario harness:** add the study to the `verify_gui_open.py` sweep (it must route
  through the ConfigurationSet reader — the harness's first study file) and to
  `GUI_EXERCISE_INDEX.md`.
- **Owner walkthrough:** 9.4's `gui_workflow.md` rewritten as the demo script — the
  click-path you'd show someone to sell configuration sets. Your pass on it is the
  acceptance signature for the whole plan.

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
| Override mechanism (§3a) — replace-by-name recommended | **Open** — ratify before Phase 2 starts |
| GUI Elements-tab scope (§4a) — effective-train + badge, shared-only Apply recommended | **Open** — ratify before Phase 2 starts |
| GUI verification model — three layers per phase (§4b–4d), owner walkthrough as plan acceptance | Set by this revision (2026-09-01, owner-directed) |
