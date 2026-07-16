# ADR-0009: GUI Config-Object Editing and Data Import Go Through an API Facade, as Declarative Documents

**Date:** 2026-07-16
**Status:** Accepted (owner-ratified 2026-07-16, with FW-1 of the GUI Capability Expansion Plan
authorized to execute D3/D4 immediately)

## Context

GUI v1 is **`ParameterDef`-driven**: every input control is a `FieldRow` bound to a dot-path,
committed via `Sensor.set(dotpath, value, unit=…)` — one action, one API call. That pattern covers
scalars and enums completely, but the GUI Capability Audit
(`docs/reports/GUI_audit_071426/GUI_Capability_Audit.md` §12) identified ~a dozen P0/P1
capabilities that are **not flat parameters**:

- the **optical element train** (per-element kind / T_K / R / T spectral-or-scalar, cavity models) —
  `io/element_config.py::load_element_list()` parses an `optical_elements:` YAML section into
  `OpticalElement` objects, injected pre-chain as `stage_outputs["optics_config"]["element_list"]`;
- **Zernike / OPD wavefront screens** (`io/zemax_zernike.py` → `optics_config.wavefront_error`);
- **spectral curve imports** — detector QE, dark current, material emissivity/reflectance, measured
  curves (`io/qe_csv.py`, `io/dark_current_csv.py`, `io/aster_library.py`, …);
- **tabulated / MODTRAN atmospheres** (`atmosphere.tabulated_*_file`, `atmosphere.modtran.tape7_path`);
- **target / ship-class libraries** (`io/target_library.py`).

Verified constraints (2026-07-16) that any design must satisfy:

1. **The GUI cannot import `radiant.io`.** The import-linter contract "gui imports only api and
   core" (`pyproject.toml`) forbids `radiant.gui → radiant.io` — the loaders are unreachable from
   GUI code. This is deliberate: the GUI is a view over the scripting API.
2. **Two injection mechanisms already exist**, split by kind:
   - **File-path `ParameterDef`s** (`detector.qe_table_path`, `atmosphere.modtran.tape7_path`,
     `atmosphere.tabulated_*_file`, `source.target.*_path`): the *path* is the parameter; the
     session resolves and loads it pre-chain (Rule 6). These round-trip through `Sensor.save`/`load`
     natively.
   - **In-memory config objects** via the public `Sensor.set_stage_output(group, key, value)`
     (e.g. `("optics_config", "element_list", elements)`). These do **not** round-trip:
     `Sensor.from_yaml` does not parse an `optical_elements:` section, and `Sensor.save` does not
     write one — today even a script user must call `radiant.io.element_config.load_element_list()`
     and inject by hand.
3. **Rule 6** — stages never read files; all file I/O is pre-chain. **Rule 5** — emissivity of an
   optical element is Kirchhoff-derived, never an independent input (except declared ε on `LUMPED`
   pseudo-elements). **Rule 16** — validate before compute; no raw user dicts into physics.
4. **R-UNITS / import UX** (owner hard rules + scenario docs): every import shows units, auto-detected
   conversions are confirmed, never silent.

The question this ADR decides: **how does the GUI author, import, preview, and persist non-scalar
configuration** while honoring one-action-one-API-call, the import contract, and YAML parity?

## Decision

Five rulings, one pattern:

**D1 — File-path-first.** Wherever a file-path `ParameterDef` already exists, the GUI import control
is a file picker bound to that dot-path, committed with the ordinary `sensor.set(path_param, path)`.
No new mechanism, native YAML round-trip, provenance = the path itself. New file-backed capabilities
SHOULD be exposed as path parameters when the file is the natural unit of exchange (vendor CSV,
tape7) — this keeps the flat-parameter world as large as possible.

**D2 — Authored config objects are edited as declarative documents.** For configuration a user
*composes* in the GUI (the element train; later, filter stacks), the GUI edits a **declarative
dict/list document with the exact schema the existing io parser consumes** (the `optical_elements:`
section format). Commit serializes form state to that document and hands it to the API (D3), which
validates it **through the same io parser** and injects via `set_stage_output`. The GUI never
constructs physics objects (`OpticalElement`, `WavefrontError`) directly — the io parser remains the
single validation authority (Kirchhoff checks, bounds, Rule 16), and GUI-authored config is
YAML-loadable **by construction** because it *is* the YAML schema.

**D3 — A `radiant.api` config facade is the only bridge.** A small facade (new module
`radiant.api.config_io`, or methods on `Sensor` — exact surface decided in the FW phase) wraps the io
loaders for both directions:
- **preview-parse**: parse a chosen file / document and return a displayable summary (curve arrays,
  element table, detected units) *without* mutating the sensor — feeds the import-preview dialog;
- **commit**: validate the document via the io parser and inject (`set_stage_output`) — one API call.
This is forced by constraint 1 (gui cannot import io) and matches the existing api role ("pre-chain
library resolution", import table in `CLAUDE.md`). The api → io edge already exists and is legal.

**D4 — Authoring implies persistence parity.** *If the GUI can author it, `Sensor.save`/`load` must
carry it.* The FW phase extends the config round-trip so an authored `optical_elements:` section is
written by `Sensor.save` and re-injected by `Sensor.load` (closing the constraint-2 gap for element
trains). A GUI that builds state which silently vanishes on save/reopen is a defect. (This also fixes
the same gap for script users — the facade is not GUI-private.)

**D5 — One shared import-dialog contract.** Every importer (QE, dark, tape7, materials, libraries,
Zernike) uses one GUI pattern: *pick file → facade preview-parse → preview panel (plot/table, every
value unit-labeled, auto-detected unit conversions shown for explicit confirmation) → Apply = one API
call (D1 `set` or D3 commit) → the owning form shows a provenance badge (imported-from: path)*.
Parse failures surface as actionable `RadiantError` dialogs (what/why/action), never a silent
fallback. In the element editor specifically, ε renders as a **derived, read-only** field
(ε = 1 − R mirror / cavity-derived refractive), editable only on `LUMPED` rows (Rule 5).

## Rationale

The pattern keeps every v1 architectural invariant intact while unlocking the audit's [C]-class
items: the GUI stays a view (one action ↔ one API call), validation stays in exactly one place (the
io parsers), and GUI/YAML/script users all converge on the same declarative schema — no capability
becomes "GUI-only expressible."

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **A (chosen): api facade + declarative documents** | Honors import contract; single validation authority; YAML parity by construction; facade also serves script users | One new (small) api surface to build and document |
| B: let `gui` import `radiant.io` directly | No new api code | Breaks the ratified import contract and the "view over the API" principle; GUI-side orchestration of loaders duplicates session logic |
| C: GUI constructs domain objects via api re-exports (`OpticalElement` etc.) | Fewer layers at commit time | Bypasses loader validation (Rule 16 risk); GUI-built objects have no YAML representation → authored state can't persist; two construction paths drift |
| D: everything via temp-file YAML round-trips (write section → `load_element_list(tmp)`) | Reuses loaders unmodified | Fragile, opaque provenance; generalizes the very temp-file smell Gap 88 records; still needs an api wrapper to call the loader (constraint 1) |

## Consequences

- **Positive:** Unblocks audit items O-1 (element editor), A-4/A-8 (atmosphere imports), D-1/D-3
  (QE/dark curves), S-2/S-8/S-9/S-10 (source spectra/materials/libraries) with one reusable pattern;
  script users gain element-train persistence and one-call element authoring for free.
- **Negative:** One new public api surface (facade + save/load extension) — a Category B FW phase
  with Rule 20 doc updates (`RADIANT_Scripting_API.md`, `RADIANT_Config_Format.md`) and a Rule 29
  public-surface CHANGELOG entry. `Sensor.save` output grows a section (back-compatible: absent
  section = today's behavior).
- **Neutral:** `set_stage_output` remains public and unchanged (the facade builds on it). The
  import-preview dialog becomes a shared GUI component with per-importer content plugins.

## References

- `docs/reports/GUI_audit_071426/GUI_Capability_Audit.md` §12 (the reach-ability finding)
- `docs/plans/GUI_Capability_Expansion_Plan.md` (the plan this ADR gates)
- `docs/archive/GUI_Development_Plan.md` §4 ground rule 1 (one action ↔ one API call)
- `CLAUDE.md` import rules table; `pyproject.toml` import-linter contract "gui imports only api and core"
- `src/radiant/io/element_config.py` (the declarative `optical_elements:` schema — D2's document format)
- `docs/tracking/gaps.md` Gap 88 (temp-file serialize smell), GUI-1/GUI-7 (import backlog)
