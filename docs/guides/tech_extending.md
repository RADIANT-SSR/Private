# Extending RADIANT

This chapter is the practical walkthrough the three preceding specifications support: how
to add a stage, how to add a parameter, what the import rules permit, and where the
plugin system stands.

Everything here assumes the constraints of Part 1 and Part 3. An extension that violates
one of them is not an extension — it is a fork in disguise.

---

## 1. Adding a parameter

Every user-facing quantity is defined exactly once, as a `ParameterDef` in the owning
stage's `_schema.py`. Nothing tuneable is hardcoded in a physics module; a magic number in
a physics file is a bug, not a shortcut.

### The steps

1. **Pick the owning stage.** The namespace is the stage that consumes the parameter —
   `optics.*` lives in `src/radiant/optics/_schema.py`, `detector.*` in
   `src/radiant/detector/_schema.py`. Do not put a parameter in a stage that merely
   forwards it.
2. **Write the `ParameterDef`** and add it to that module's `ALL_PARAMETERS` tuple. The
   central registry (`radiant.api._param_registry.build_parameter_set`) collects every
   stage's tuple, so there is nothing else to register.
3. **Read it in the stage** via `params.get("namespace.name")` — never from a raw dict,
   never from a module-level constant.
4. **Write the Level 0 test first**, against a known-good analytic value, before the
   implementation exists.
5. **Regenerate the parameter reference** (`python scripts/gen_param_reference.py`) — the
   generated chapter of this volume is freshness-gated, so a new parameter with a stale
   reference fails the check.
6. **Update the matching architecture document** in the same change. The parameter schema
   is a documented surface.

Note that the schema surface reaches further than it looks: the GUI builds its editors
from `Sensor.parameter_defs()`, so adding one parameter can move a GUI test even though no
GUI file was touched.

### The fields

```python
from radiant.core.parameters import ParameterDef

APERTURE_DIAMETER_M = ParameterDef(
    name="optics.aperture_diameter_m",
    description="Clear entrance-pupil diameter of the primary [m].",
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=None,                 # None means required
    bounds=(1e-4, 20.0),          # in input_unit
    group="fnumber",              # consistency group membership
    tags=frozenset({"optics", "aperture"}),
)
```

| Field | Meaning |
|-------|---------|
| `name` | Dot-path, `namespace.parameter_name`, lowercase with underscores |
| `description` | One sentence; it is what the Parameter Reference and the GUI tooltip print |
| `dtype` | `float`, `int`, `str`, or `bool` — nothing else |
| `canonical_unit` | The internal storage unit (µm, rad, s, m, …) |
| `input_unit` | The unit the user enters and the YAML carries |
| `default` | In `input_unit`. `None` means **required** |
| `bounds` | `(lo, hi)` in `input_unit`; numeric dtypes only |
| `enum_values` | Closed set of legal strings; `str` dtype only |
| `group` | Consistency-group name, if the parameter is derivable from others |
| `tags` | Free-form labels for filtering and grouping |
| `default_justification` | Why this default and not another — required discipline for a non-obvious default |
| `deprecated_aliases` | Former names; they resolve with a `DeprecationWarning` |
| `required_unless` | Dot-path of a parameter that supersedes this one, letting a required parameter stay unset (e.g. `detector.qe_value` is required *unless* `detector.qe_table_path` is set) |
| `is_file_path` | The value names a data file: serialization stores it relative to the YAML's directory so configs stay portable. Not for system paths such as a MODTRAN binary |

`ParameterDef` validates itself on construction: a non-scalar dtype, `enum_values` on a
non-string, `bounds` on a non-numeric, a self-alias, or `required_unless` on a parameter
that has a default all raise immediately.

### Naming

Lowercase with underscores, no units *inside* the name but a unit **suffix** where one
applies (`_m`, `_um`, `_rad`, `_s`, `_K`, `_e_rms`). The suffix names the canonical stored
unit, which is not always the entry unit — `geometry.solar_zenith_rad` is entered in
degrees through `set(..., unit="deg")`.

### Consistency groups

When a new parameter is derivable from existing ones, declare the relation instead of
recomputing it at the call site. A group names its members, its constraint, a derivation
per member, and a tolerance:

```python
from radiant.core.parameters import ConsistencyGroup

_FNUMBER_GROUP = ConsistencyGroup(
    name="fnumber",
    parameters=("optics.aperture_diameter_m", "optics.focal_length_m", "optics.f_number"),
    constraint="f_number = focal_length_m / aperture_diameter_m",
    derivations={
        "optics.f_number": lambda kv: (
            kv["optics.focal_length_m"] / kv["optics.aperture_diameter_m"]
        ),
        # … one entry per member
    },
    tolerance=1e-3,
)
```

Supply any two members and the third is derived with provenance `DERIVED` and a
`derived_from` record. Supply all three inconsistently and resolution raises rather than
silently preferring one. Groups are registered in
`radiant.api._param_registry.build_parameter_set`.

The `ground_speed` group is worth studying as the other archetype: it is an *identity*
group linking `platform.ground_velocity_m_s` and `geometry.ground_speed_m_s`, two names
for one physical quantity. Setting either derives the other, so smear and access rate can
never read two different velocities.

---

## 2. Adding a stage

A new stage is a substantial change — it extends the chain protocol — but the mechanics
are small.

1. **Create `src/radiant/<stage_name>/`.**
2. **Create `_schema.py`** with every `ParameterDef` the stage owns, collected in
   `ALL_PARAMETERS`, and add it to `radiant.api._param_registry`.
3. **Create `stage.py`** implementing the `Stage` protocol:

   ```python
   from radiant.core.chain import ChainState
   from radiant.core.parameters import ParameterSet


   class MyStage:
       """One-line description of what this stage computes."""

       @property
       def name(self) -> str:
           return "my_stage"

       def run(self, state: ChainState, params: ParameterSet) -> ChainState:
           value = params.get("my_stage.some_parameter")
           ...
           return state.with_stage_output("my_stage", "result", value)
   ```

   `name` is a read-only property, and `run` returns a **new** state — never the one it
   was handed.

4. **Create `tests/`** with Level 0 tests for the key physics equations, written against
   known-good analytic values — not against values another part of RADIANT computed.
5. **Register the stage** in the `ChainRunner` list in `radiant/api/session.py`, at the
   position the physics requires.
6. **Add the stage to the document map** in `RADIANT_Master_Architecture.md` and write its
   subsystem document.

### What the stage may and may not do

| Allowed | Forbidden |
|---------|-----------|
| Read parameters via `params.get(...)` | Mutating `state` or `params` |
| Read earlier stages' `state.stage_outputs[...]` | Importing another physics stage |
| Return `state.with_frame / with_noise / with_mtf / with_stage_output` | Reading or writing any file |
| Raise an actionable `RadiantError` subclass | Calling another stage's `run` |
| Log through the `logging` module | `print()` |
| — | Returning `NaN` / `inf` silently, or holding state between runs |

A stage needing a file-derived object does not open the file: the API layer builds the
object before the chain and injects it through
`ChainRunner.run(initial_stage_outputs=...)`. `atmosphere_config.model` and
`optics_config.element_list` are the shipped examples, and
`Sensor.set_stage_output(group, key, value)` is the user-facing door to the same
mechanism.

### If the stage has a spatial effect

Both spatial paths must move together. A new degradation needs a convolution kernel on
the `EffectivePSF` **and** a corresponding term in the MTF product — or an explicit,
documented reason why it is one of the deliberate MTF-only terms, like TDI
mis-registration. Adding it to only one path is caught by the consistency check on every
run, which is exactly what that check exists for.

---

## 3. Import rules

Module boundaries are machine-enforced by `import-linter`, and a violating change is
blocked before it merges. The contracts:

| Module | May import from |
|--------|-----------------|
| `core/` | stdlib, numpy, scipy only — no `radiant.*` imports at all |
| Physics stages (`geometry` … `performance`) | `radiant.core` only |
| `data/` | `radiant.core` only, plus stdlib, numpy, yaml |
| `io/` | `radiant.core` plus any physics stage (read-only, for schema) |
| `api/` | `radiant.core`, all physics stages, `radiant.io`, `radiant.data` |
| `cli/` | `radiant.api`, `radiant.io`, and `radiant.gui` (lazily, for `radiant gui`) |
| `gui/` | `radiant.api` and `radiant.core` only — no physics stage, no `io`, no `cli` |

```python
# FORBIDDEN inside a physics stage:
from radiant.optics import psf         # cross-stage physics import
from radiant.source import blackbody   # cross-stage

# ALLOWED:
from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.spectral import SpectralData
```

Two consequences worth internalizing:

- **Stages communicate only through `ChainState`.** If a stage seems to need another
  stage's function, the function belongs in `core` or the value belongs in `stage_outputs`.
- **The GUI is a view over the scripting API**, one action to one API call. When the GUI
  needs something a physics stage knows, the bridge is an `api/` module — the pattern
  `radiant.api.geometry_modes` and `radiant.api.metric_groups` follow.

Verify locally with:

```bash
lint-imports --config pyproject.toml
```

---

## 4. Adding a metric

Each distinct metric gets its own module under `radiant/performance/`, with its own error
class and its own Level 0 test. Bundling unrelated computations into one file because they
share a stage is the thing this rule exists to prevent — a developer should find a
calculation by scanning file names.

Bundling is acceptable only for computations that share internal state or helpers and
would be meaningless apart (a cavity's $T_\text{sys}$ and $\varepsilon_\text{eff}$ are one
model, not two files).

A metric must also register its unit and description, so that `metric_records()` can
return it with units; a metric key with no registry entry raises rather than reporting a
bare number.

The metric layer carries one deliberate exception to the no-silent-failure rule: a
computation under `radiant.performance/` may return a result-typed failure with a named
`failure_reason` field instead of raising, because "this metric is undefined for this
scene" is a reportable outcome rather than a rejected input. The failure must appear in
the result object callers already inspect. Silent `NaN` propagation remains forbidden, and
physics-layer modules keep the universal raise rule.

---

## 5. Testing an extension

The test hierarchy is specified in full in the preceding chapter. In short:

- **Level 0** — the physics equation against a known-good analytic or literature value.
  Write it *before* the implementation. Never compare against a number another part of
  RADIANT produced.
- **Level 1** — module behavior, including the failure modes: zero, negative, very large,
  very small, wrong type, conflicting inputs.
- **Level 2** — full-chain integration and golden results.

`pytest.approx` always carries an explicit `rel=` or `abs=` tolerance; the default is never
acceptable. Loosening a tolerance to make a failing test pass is a change to the test, not
a fix to the physics — golden results have their own review protocol precisely so that
baseline changes are deliberate and explained.

---

## 6. Plugins — deferred

`docs/architecture/RADIANT_Plugins.md` specifies a formal extension-point system: abstract
base classes for source, atmosphere, metric, detector, and file-format plugins, discovered
at run time through `pyproject.toml` entry points, so that an organization with a
proprietary atmosphere model or a custom metric can extend RADIANT without forking it.

**That design is deferred and not implemented.** The `src/radiant/plugins/` package does
not exist — an empty stub was removed rather than left to mislead — and none of the ABCs
or registration
machinery described in that document is importable. The specification is preserved as the
v2 design, not as a description of current behavior. Do not write code against those
symbols.

Until it lands, the supported extension routes are the ones in this chapter: a new stage,
a new parameter, a new metric module — contributed into the tree, under the same rules as
any other change.
