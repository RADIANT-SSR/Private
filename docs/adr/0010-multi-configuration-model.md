# ADR-0010: Multi-Configuration Model — CODE V Zoom Semantics, Materialized per Configuration

**Date:** 2026-07-25
**Status:** Accepted (owner-ratified 2026-07-25). Fully implemented: Phases 0–5 of
`docs/archive/Multi_Configuration_Plan.md` (complete, archived 2026-07-25) shipped the
API, the config-file section, the GUI, and the CLI.

## Context

A RADIANT session today models **one** sensor: a single `Sensor` wrapping one `ParameterSet`,
one wavelength grid, one element document, one set of injections. Every real trade the tool is
used for, however, is a *family* of closely related models:

- **band variants** — one telescope evaluated in MWIR and LWIR (the expressibility half of
  Gap 80, which records that RADIANT has no multi-band run concept);
- **geometry variants** — the same sensor at several slant ranges or view angles;
- **nominal vs. as-built** — one prescription with scalar as-built knobs (WFE, f/#,
  transmission, temperatures) perturbed.

In every case the two models differ in a handful of parameters and agree on the other several
hundred. The existing routes to express this are unsatisfactory:

1. **N separate YAML files** — the shared 95 % is duplicated N times, so a change to a shared
   parameter must be applied N times or the study silently drifts. `ComparisonDialog` (GT-3)
   and `compare_configs` (Gap 79) already compare N results, but they compare *files*: the
   comparison surface exists while the authoring surface does not.
2. **`_extends` / `_imports` file composition** — reserved in `io/config.py` and deliberately
   unimplemented (the loader raises; CU-050). This is a *file-composition* feature: it answers
   "how do documents inherit", not "how does one study hold N variants".
3. **A sweep** — `BatchRunner` varies parameters over labeled overrides, but a sweep is a
   transient batch of runs, not a persistent, named, editable, individually-inspectable set of
   models that the GUI displays and the user saves.

Constraints any design must satisfy:

- **Rule 6/7 (stage purity, immutable `ChainState`)** and the whole physics chain must be
  untouched — this capability is **results-neutral by construction**; any golden diff is a
  defect.
- **R-API (`CLAUDE.md` import table)** — the GUI is a view over the scripting API, one action
  ↔ one API call. Anything the GUI can express must be expressible from a script.
- **Rule 16 (validate before compute)** — every configuration's values must pass the same
  schema validation, bounds, enums, and consistency-group resolution as today's single sensor.
  No second resolution engine.
- **Rule 17 (no silent failures)** — a failing configuration must be named, never dropped or
  zero-filled.
- **One file = one study** — the persisted artifact must remain a single YAML document, and a
  document with no configurations must remain byte-for-byte today's format.

The owner's stated interaction model (2026-07-25) is **CODE V zoom configurations**, which
resolves the design question directly: parameters are shared by default; the user explicitly
promotes a parameter to carry one value per configuration.

## Decision

### D-A. Model — CODE V zoom-configuration semantics (plan D-1)

A **configuration set** is a shared base plus an explicitly configured table:

- A parameter is **shared** (one value across all configurations) by default.
- The user explicitly marks a parameter as **configured**. It then carries **one value per
  configuration** — **dense by construction**: a configured parameter has a value in *every*
  configuration. There are no sparse overlays, no per-configuration presence variance, no
  tombstones, and no inheritance chain to resolve.
- Everything not configured — tolerances, the optical element document, stage-output
  injections — stays shared.

### D-B. Single-store invariant (plan §3.1)

A dotpath is **either** in the base's explicit inputs **or** in the configured table — never
both, never neither-by-accident:

- `configure(dotpath)` *moves* it out of the base, seeding all $N$ values from its current
  shared value (or from its resolved default when the base never set it);
- `unconfigure(dotpath)` collapses it back to a single shared value and removes the column.

The invariant is enforced by the API, checked at load, and is what keeps the
consistency-group story unchanged: a group member that should be *derived* is simply absent
from both stores, exactly as today.

### D-C. Materialization via `Sensor.clone` — no core changes

Evaluation of configuration $i$ is defined as, and only as:

```
sensor_for(i) = base.clone()
                 .set_many({p: values[p][i] for p in configured})   # source = "config:<name>"
                 [with per-configuration wavelength_points when set]
```

Resolution, validation, bounds, enums, consistency groups, and defaults all run **per
configuration inside the existing `ParameterSet.resolve()`**. Nothing is bypassed and no
second resolution engine exists. An over-constrained group inside configuration $i$ raises the
existing actionable error, tagged with that configuration's name. Configured values carry
provenance `source="config:<name>"`, so `resolved()` / `explain()` name the owning
configuration with zero new provenance machinery.

Consequence: **`radiant.core` is not modified.** The capability is an `radiant.api`-layer
composition (`api/config_set.py`), a persistence section, and GUI state.

### D-D. One-file persistence via an ADR-0009 structured section (plan §3.3)

A configuration set persists as **one document**: today's shared parameters plus a
`configurations:` structured section, added to `_SECTION_KEYS` under the exact ADR-0009
mechanism that carries `optical_elements:`.

```yaml
configurations:
  names: [MWIR, LWIR]
  active: MWIR                  # GUI resume state
  baseline: MWIR                # delta reference
  wavelength_points:            # optional; omitted names use _radiant.wavelength_points
    LWIR: 300
  parameters:                   # dotpath → list aligned with `names` order
    spectral_integration.filter_min_um: [3.95, 8.0]
    spectral_integration.filter_max_um: [4.45, 12.0]
    detector.qe_value: [0.75, 0.62]
```

Binding rules: every `parameters` list length equals `len(names)` (dense — a mismatch is a
`ConfigError`, never padded); dotpaths validate against the schema at load with the existing
did-you-mean; a dotpath may not appear in both the shared body and `parameters` (D-B, checked
at load); values are input-unit scalars; `is_file_path` values relativize and resolve exactly
like shared values. **A file with no `configurations:` section is byte-for-byte today's
format** — backward compatibility is structural, not a migration. A section-bearing file
loaded through bare `Sensor.load` / `load_config` raises an actionable "load it with
`ConfigurationSet.load`" error via the existing opt-in machinery (Rule 17).

### D-E. Cardinality — $N \le 8$ (plan D-5)

A configuration set holds $1 \le N \le 8$ uniquely named configurations. The cap is a
product decision, not a technical limit: it bounds the always-on background evaluate-all pass
(8 configurations at roughly 0.22 s per run keeps a full pass under about 2 s), and it bounds
the side-by-side Performance surface to a width that renders honestly. A ninth configuration
is rejected with an actionable error. The degenerate case — one configuration, empty
configured table — is observably identical to today's bare `Sensor`.

> **Amendment (2026-09-01, owner-ratified):** cap raised $8 \to 12$ — scenario 9.4's
> nine-band OLI-2 study exceeded 8 on the first flagship use. See
> `docs/plans/Configuration_Set_Expansion_Plan.md` (Phase 1). The rationale above holds at
> 12 (background pass ≈ 2.6 s); "a ninth configuration" reads "a thirteenth" accordingly.

### D-F. Per-configuration wavelength grids are in v1 (plan §3.4, D-5)

The evaluation grid is already per-configuration for free: each materialized `Sensor` builds
its grid from **its own** resolved band, so configuring `filter_min_um` / `filter_max_um`
gives each configuration its own span with no new mechanism. What is currently
session-global is the **point count**. v1 adds an optional per-configuration
`wavelength_points`, which requires the **only** `Sensor` change this work makes: a supported
way to produce a clone with a different point count (`Sensor.with_wavelength_points(n) ->
Sensor`), since `_wl_points` is constructor-only today. That addition takes a
public-surface CHANGELOG entry and a lock-step `RADIANT_Scripting_API.md` update.

### D-G. `_extends` / `_imports` are explicitly out of scope (plan D-5)

Configurations are **not** file composition. The reserved `_extends` / `_imports` / `_vars`
keys (CU-050) remain unimplemented and the loader keeps raising on them. Configurations
compose *within* one document at the parameter level; `_extends` would compose *across*
documents at the file level. Implementing one does not implement or oblige the other, and the
config-format documentation states this explicitly so the two are never conflated.

### D-H. Ratified behavioral decisions (plan §8.1, D-6 … D-10)

These are recorded here verbatim in intent because each one is a behavior a future change
could silently reverse:

- **D-6 — Unconfigure keeps configuration #1's value.** When a parameter is un-configured,
  the *first* configuration's value always becomes the shared value. The GUI confirmation
  states this so it is never a silent physics change in the other configurations; a
  scripting-only `keep=<name>` override exists for deliberate alternatives.
- **D-7 — Per-configuration optical prescriptions are deferred to v1.1.** The
  `optical_elements` document stays shared across all configurations in v1. Scalar as-built
  knobs (WFE, f/#, transmission, temperatures) are ordinary configurable parameters and cover
  the near-term as-built workflow. A per-configuration element document is an additive later
  extension of the section format, gap-tracked at close-out.

  > **Superseded (2026-09-02, owner-ratified in live review):** v1.1 landed — a **row of
  > the shared document configures like a parameter** (dense: one complete entry per
  > member, written in place as `- configured: {member: entry, …}`; single io validation
  > authority; D-6 keep-first collapse; D-8 inline edit in the GUI with the red C). Row
  > identity is positional and the entry's `name` configures with the row — the owner
  > accepted the cross-member naming consequence. The "whole-document vs patching"
  > question this ADR left open is resolved in favor of neither: per-row configuration.
  > (A same-day replace-by-name override design was built first and superseded before
  > merge on live-review evidence.) Structure — row count and order — stays shared;
  > per-member addition/removal stays out of scope. See
  > `docs/plans/Configuration_Set_Expansion_Plan.md` §3a-bis (Gap 103).
- **D-8 — Inline edit is scoped to the displayed configuration.** Editing a configured
  parameter in a stage form or the parameter panel while configuration $X$ is displayed edits
  **$X$'s value only** (CODE V behavior). The per-parameter table is the all-$N$ editor.
  Editing a shared (unmarked) parameter edits the single shared value, as today — there is no
  hidden scope mode.
- **D-9 — Performance tabs show plain values only.** Metric × configuration cells carry value
  + unit, nothing else. Delta-vs-baseline and best-marks are **not** rendered in the GUI; they
  remain available through the scripting `compare` surface (`compare_configs`), and the
  `baseline` designation stays in the model for exactly that purpose.
- **D-10 — Naming: "Configurations".** GUI label "Configurations"; code `ConfigurationSet`;
  docs "configuration set". **Binding disambiguation convention**, enforced in every lock-step
  doc edit under this work: prose always says **"config file" / "YAML config"** for the
  on-disk artifact and reserves bare **"configuration"** for a member of a configuration set;
  existing doc text is amended where the two would otherwise collide in the same paragraph. If
  Phase 1–4 reviews find the convention breaking down in practice, renaming the members (for
  example to "variants") is a decision to reopen at this ADR's level, not a silent drift.

### D-I. Marking, display, and evaluation (plan D-2, D-3, D-4)

- Configuring is **explicit per parameter**; configured parameters carry a small red "C"
  badge in the parameter panel and per-stage forms, and a per-parameter table editor sets all
  $N$ values in one place.
- A **master configuration selector** picks the displayed configuration for stages 1–8; the
  Performance surface shows per-grouping tabs with all configurations side by side.
- **All configurations evaluate in the background, always** — displayed configuration first
  (so the visible views refresh at today's latency), remaining configurations following on the
  worker. Per-configuration failures surface tagged with the configuration name and never
  block the others.

## Rationale

The zoom-configuration model was chosen because it makes the *shared* case the default and the
*varying* case explicit and visible. That single property is what removes the failure mode all
alternatives carry — a parameter that differs between two models without anyone having said it
should. Density (one value per configuration, always) is what removes the resolution order
question entirely: there is nothing to resolve, so there is no precedence rule to document,
test, or get wrong. And materialization through `Sensor.clone` is what keeps the validation
authority singular: every configuration goes through the same `ParameterSet.resolve()` as
today's single sensor, so bounds, enums, consistency groups, defaults, and actionable errors
are inherited rather than re-implemented.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **A (chosen): shared base + dense configured table, materialized per configuration** | No `radiant.core` change; single validation path (`ParameterSet.resolve()` per materialized sensor); results-neutral by construction; degenerate 1-configuration case is exactly today's app; persists as one file with a back-compatible section; matches the owner's CODE V mental model | One new api module plus GUI state; configured/shared is a distinction users must learn (mitigated by the explicit "C" badge) |
| B: layered `ParameterSet` in `radiant.core` (base layer + per-configuration overlay layers) | Overlay resolution is general; sparse overlays expressible | Touches the `mypy --strict` core surface and the resolution engine that every golden result depends on — the one place results-neutrality cannot be asserted by construction; introduces a precedence order to specify and test; sparse overlays reintroduce the "differs and nobody said so" failure mode the model exists to prevent |
| C: $N$ independent `Sensor` objects held side by side | Trivial to implement; each configuration is fully independent | The shared 95 % is duplicated $N$ times, so shared edits must fan out or the study drifts — the exact defect the capability is meant to remove; nothing in the model records *which* parameters are intentionally different; no natural single-file persistence |
| D: `_extends` / `_imports` file composition (implement CU-050 instead) | Reuses a reserved, already-designed key; general file-level reuse | Solves document inheritance, not intra-study variants: $N$ files again, comparison across files rather than one editable study; no place for `active`/`baseline`/per-configuration ordering; a GUI would have to author and track $N$ documents. Adjacent and still valuable — but a different feature (D-G) |

## Consequences

- **Positive:** Band, geometry, and nominal-vs-as-built studies become expressible in one
  document and one session (Gap 80's expressibility half); the existing `compare_configs`
  surface gains a first-class producer; provenance names the owning configuration for free;
  the GUI's always-on evaluate loop generalizes to evaluate-all without a new execution model;
  single-configuration sessions are unchanged, which makes zero-regression a testable claim
  rather than an aspiration.
- **Negative:** A new public api surface (`ConfigurationSet`, `ConfigSetRunResult`,
  `ConfigSetError`, `Sensor.with_wavelength_points`) with Rule 20 lock-step docs and Rule 29
  CHANGELOG entries; a new persisted section with its own load-time validation; substantial
  GUI state work (scoped edits, badges, undo/redo scope, per-configuration columns).
- **Neutral:** `radiant.core`, the physics stages, `ChainState`, `ChainRunner`, the parameter
  schema, and the golden baselines are untouched — any golden diff in any phase of this work
  is a defect, not an expected change. Deferred to later versions and gap-tracked at close-out:
  per-configuration tolerance distributions, per-configuration stage-output injections,
  cross-configuration derived metrics (band ratios, dual-band contrast), sweeps of a whole set,
  and per-configuration optical element documents (D-7).

## References

- `docs/archive/Multi_Configuration_Plan.md` — the plan this ADR gated (§3 core model,
  §4 GUI vision, §5 phases, §8.1 decisions D-1…D-10); complete and archived 2026-07-25
- ADR-0009 (`0009-gui-config-object-editing-and-import.md`) — the structured-section
  persistence mechanism D-D extends, and the "authoring implies persistence parity" ruling
- `docs/architecture/RADIANT_Parameter_System.md` (resolution, provenance),
  `docs/architecture/RADIANT_Config_Format.md` §1.3–1.5 (reserved keys, sections),
  `docs/architecture/RADIANT_Scripting_API.md` (`Sensor` surface),
  `docs/architecture/RADIANT_GUI_Architecture.md` (contextual per-stage layout)
- `CLAUDE.md` Rules 6, 7, 16, 17, 19, 20, 29; import table (`gui` imports only `api` and `core`)
- `docs/tracking/Cleanup_Backlog.md` CU-050 (`_extends` reserved-but-unimplemented),
  CU-177 (file-path relativization helpers reused by the section)
- `docs/tracking/gaps.md` Gap 79 (`compare_configs`, FIXED), Gap 80 (multi-band run concept,
  re-dispositioned at close-out)
