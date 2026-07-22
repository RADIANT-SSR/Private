# RADIANT — Coding Agent Instructions

This is the authoritative reference for all RADIANT coding agents. Read it fully before making any change. When in conflict with another document, this file governs agent behavior; `docs/architecture/RADIANT_Master_Architecture.md` governs architecture decisions.

---

## What Is This Codebase

RADIANT is a first-principles EO sensor performance modeling framework. It predicts SNR, NEDT, NIIRS, MTF, and detection range for space-based and airborne electro-optical sensors. The signal chain flows: geometry → source → atmosphere → optics → platform → spectral integration → detector → readout → performance metrics (geometry-first per ADR-0006).

**Primary reference documents** (read before touching related code):
- `docs/architecture/RADIANT_Master_Architecture.md` — non-negotiable constraints (15 rules)
- `docs/architecture/RADIANT_Conventions.md` — units, coordinate system, spectral variable
- `docs/architecture/RADIANT_Signal_Chain_Architecture.md` — stage protocol, ChainState
- `docs/architecture/RADIANT_Parameter_System.md` — parameter naming, types, resolution
- `docs/architecture/RADIANT_Testing_Validation.md` — what and how to test

---

## Non-Negotiable Rules

These rules are absolute. No exception without explicit approval from the project owner.

### 1. Python ≥ 3.11 — Type Hints Everywhere
Type hints are required on **every** function and method — not just public ones. `mypy --strict` must pass on `radiant.core` and `radiant.api`.

### 2. Units — Convert at Boundaries Only
- Internal canonical units: wavelength in **µm**, angles in **radians**, time in **seconds**, length in **meters**, radiance in **W/m²/sr/µm**, noise in **e- RMS**.
- Unit conversions happen exactly once: at `params.set()` (user input) or in file readers (MODTRAN: ×1e4 for W/cm² → W/m²).
- No unit conversion inside physics modules. A `* math.pi / 180` or `* 1e4` in a physics module is a red flag — verify it is computing physics, not converting units.

### 3. Coordinate System
Right-handed. +Z toward target (along boresight). +X cross-track. +Y along-track. Euler: ZYX (yaw → pitch → roll). Pixel indexing: `[row, col] = [y, x]`, 0-indexed. See `docs/architecture/RADIANT_Conventions.md` §1 for full details.

### 4. Dual-Path Spatial Architecture — PSF Path and MTF Product Path
RADIANT maintains two parallel spatial paths, both rooted in the same complex pupil function:

**PSF path** (spatial-domain metrics):
- Every spatial degradation enters as a convolution kernel on the `EffectivePSF`.
- EE_box, RER, FWHM, Strehl, LSF, and ERF are computed **only** from this PSF. Strehl is the degraded-PSF peak over the diffraction-limited `reference_psf` peak (same detector kernels on both, so detector effects cancel); the analytic Maréchal value survives only as the separate `strehl_marechal` diagnostic.
- EE_box is computed in `PlatformStage` from the fully degraded PSF (jitter, smear, turbulence included) and applied once in `SpectralIntegrationStage` (Rule 9).
- **NEVER** compute EE_box from one PSF and RER from another. All spatial-domain metrics derive from the same `EffectivePSF` object.

**MTF product path** (frequency-domain budget):
- Optical MTF is computed from the **autocorrelation of the complex pupil function** (equivalent to `|FT{PSF}|` by the Wiener-Khinchin theorem, but computed directly from the pupil).
- Each downstream contributor (detector aperture, jitter, smear, diffusion, IPC, turbulence) has an analytic or kernel-derived MTF.
- TDI mis-registration MTF is the one deliberate MTF-only term: it is a readout-timing effect with no spatial kernel, enters only the MTF product, and is excluded from the consistency comparison (`consistency_check._EXCLUDED_PREFIXES`).
- System MTF = product of all contributor MTFs: `MTF_sys(f) = Π_i MTF_i(f)`.
- MTF budgets, MTF-at-Nyquist, folded MTF, and GIQE/NIIRS consume this path.

**Consistency invariant**: Both paths originate from the same pupil. The FFT of the convolved `EffectivePSF` must agree with the MTF product; `performance/consistency_check.py` runs on every chain execution **in which the spatial (PSF/MTF) path is computed** with a default absolute tolerance of 2e-2 (worst measured full-chain discretization residual is ~1e-2 after the CU-003 area-integrated pixel kernel; the tolerance carries ~2× margin — see CU-003/CU-045) and logs a warning on failure. A failure means a degradation was added to one path but not the other. The spatial path (and hence this check) is skipped only when the analyst deselects the entire Spatial-MTF metric group *and* no enabled metric needs a spatial input — there is then no spatial computation to check (Gap 96 metric selection; owner-ratified 2026-07-18).

**What this rule forbids**:
- Computing EE from one PSF and MTF from a different PSF (the old single-path failure mode).
- Computing optical MTF by multiplying separate `MTF_diffraction × MTF_aberration` terms — aberrations interact with diffraction in the pupil and cannot be factored. The pupil autocorrelation handles this correctly as a single `MTF_optics` term.
- Allowing the two paths to diverge without a consistency check.

### 5. Emissivity of Optical Elements Is Always Derived — Never Independent
For any optical element, emissivity must be derived from Kirchhoff's law:
- Mirrors: `ε = 1 − R`
- Transmissive elements: `ε = 1 − T − R`

**Never** accept emissivity as an independent input parameter for an optical surface. A user who specifies both reflectance and emissivity for an optical element is over-specifying the system. Validate and derive; do not accept both.

This rule does **not** apply to scene targets and backgrounds, where emissivity is a legitimate independent parameter (it describes a material property, not an energy balance constraint).

### 6. Stages Are Pure Functions
- Stage signature: `run(self, state: ChainState, params: ParameterSet) -> ChainState`
- Stages **do not** mutate inputs. Use `state.with_frame(...)`, `state.with_noise(...)`, `state.with_mtf(...)`, `state.with_stage_output(...)`.
- Stages **do not** read files. File I/O happens before chain execution — spectral tables load into `SpectralDataStore`; file-derived objects (atmosphere model, optical element list) are built by the IO/API layer and injected via `ChainRunner.run(initial_stage_outputs=...)` (e.g. `stage_outputs["atmosphere_config"]["model"]`, built by `radiant.atmosphere.loaders.build_atmosphere_model`).
- Stages **do not** call other stages. All inter-stage data flows through `ChainState`.

### 7. ChainState Is Immutable
`ChainState` is a frozen dataclass. Never assign to its fields directly. Always use the `with_*` methods. Fields added by earlier stages are never removed or overwritten by later stages.

### 8. Spectral Integration Happens Exactly Once
Before `SpectralIntegrationStage`: spectral arrays (shape = N_wavelengths). After: per-pixel scalars (e-, DN). No other stage collapses spectral to scalar.

### 9. EE_box Applied Exactly Once
Computed in `PlatformStage` from the fully degraded PSF (`stage_outputs["platform"]["EE_box"]`). Applied in `SpectralIntegrationStage` only, only for point-source and sub-pixel target regimes, never to the background term in sub-pixel regime, never in extended-scene regime.

### 10. Regime Finalized in OpticsStage
- `SourceStage` tentative classification: `state.stage_outputs["source"]["regime_tentative"]`
- `OpticsStage` final classification: `state.stage_outputs["optics"]["regime"]`
- All downstream stages read `state.stage_outputs["optics"]["regime"]`. Never re-classify.

### 11. No Cross-Stage Imports in Physics Modules

```python
# FORBIDDEN in geometry, source, atmosphere, optics, platform,
# spectral_integration, detector, readout, performance:
from radiant.optics import psf        # cross-stage physics import — NO
from radiant.source import blackbody  # cross-stage — NO

# ALLOWED:
from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.spectral import SpectralData
```

`import-linter` enforces this in CI and will block PRs that violate it.

### 12. Every Parameter Has a ParameterDef in `_schema.py`
New parameters go in the owning stage's `_schema.py` (not `parameters.py` — that name is used internally by `radiant.core.parameters`). Required fields: `name` (dot-path), `dtype`, `canonical_unit`, `input_unit`, `default` or `None`. Naming: `namespace.parameter_name` — lowercase, underscores, no units in name. All tuneable quantities are parameters; nothing is hardcoded in physics modules.

### 13. Physical Constants From `constants.py`
```python
# CORRECT:
from radiant.core.constants import h, c, k_B
L = (2 * h * c**2 / lam_m**5) / (np.exp(h * c / (lam_m * k_B * T)) - 1)

# FORBIDDEN:
L = (2 * 6.626e-34 * (3e8)**2 / lam_m**5) / ...  # magic numbers
```

### 14. No `print()` in Library Code
Use the standard `logging` module. `print()` is permitted only in `cli/` entry points and examples.

### 15. Errors Are Actionable
All RADIANT-defined exceptions derive from `radiant.core.exceptions.RadiantError` (re-exported as `radiant.RadiantError`). Concrete subclasses live with the module that raises them — `ParameterBoundsError`, `ParameterEnumError`, `UnknownParameterError` (`core/parameters.py`), `KirchhoffViolationError` (`optics/element.py`), `ModtranUnavailableError` / `Tape7ParseError` (`atmosphere/modtran.py`), `ConfigError` (`io/config.py`), `ElementConfigError` (`io/element_config.py`), `OperationCancelledError` (`api/_progress.py`). They MAY co-inherit from a built-in exception (`ValueError`, `RuntimeError`) for back-compat with existing `except`/`pytest.raises` patterns; new RADIANT exception classes SHOULD inherit from `RadiantError` only.

```python
# CORRECT:
from radiant.core.parameters import ParameterBoundsError

raise ParameterBoundsError(
    what=f"sensor.detector.operating_temp = {T} K is out of bounds",
    why="HgCdTe operates at cryogenic temperature (1–300 K)",
    action="Set operating_temp to 77–120 K for HgCdTe detectors",
    context={"param": "sensor.detector.operating_temp", "value": T, "bounds": (1, 300)},
)

# FORBIDDEN:
raise ValueError("invalid temperature")
raise AssertionError("bad value")   # assert is for developer invariants only
```

User code that wants to distinguish "the framework rejected my input" from a generic Python bug catches `RadiantError`:

```python
from radiant import RadiantError, Sensor

try:
    result = Sensor(config).run()
except RadiantError as exc:
    # Every framework-defined error lands here.
    log.error("RADIANT rejected the run: %s", exc)
```

### 16. Validate Before Compute
Validate all user-controlled inputs before doing any physics computation. Use `ParameterSet` — never pass raw dicts from user input to physics functions. Physics-layer functions (`source/`, `atmosphere/`, `optics/`, `platform/`, `spectral_integration/`, `detector/`, `readout/`) must never return `NaN` or `inf` silently — raise an actionable error with context (per Rule 15). Metric-layer functions (`performance/snr.py`, `performance/nedt.py`, `performance/niirs.py`) may return result-typed failures with an explicit `failure_reason` field instead of raising — see Rule 17 carve-out.

### 17. No Silent Failures
No `except Exception: pass`. No `except Exception: return default_value`. No logging a warning and continuing when physics is undefined. No clipping values to valid ranges without at minimum a `UserWarning`.

**Exception (metric layer — see ADR-B):** computations under `radiant.performance/` (`snr.py`, `nedt.py`, `niirs.py`) may return result-typed failures with a structured `failure_reason` field instead of raising. The failure must be named and surfaced in the result object that callers already inspect; silent NaN propagation remains forbidden. Physics-layer modules (source through readout) keep the universal raise rule.

### 18. Test at Level 0 First
Write the Level 0 test that verifies the key equation **before** implementing the physics. Tests use known-good analytic values, not values computed by other RADIANT code. `pytest.approx` always uses explicit `rel=` or `abs=` tolerance — never the default.

### 19. One Computation, One Module
Each distinct physics calculation or metric (e.g., ground range, swath width, access rate, folded MTF) gets its own file. Do not bundle unrelated computations into a single module just because they share a stage or a prompt. A developer should be able to find a calculation by scanning file names, not by reading through a multi-purpose file.

**When this applies:**
- New standalone computations (pure functions with no shared mutable state)
- Metrics that could be tested, documented, or reused independently

**When bundling is acceptable:**
- Tightly coupled computations that share internal state or helper functions and would be meaningless apart (e.g., cavity T_sys and cavity eps_eff are one model, not two files)

### 20. Doc-and-Code Change in Lock-Step
Any change that modifies a public API name, parameter schema, error class, stage protocol, `ChainState` field, public method on `Sensor` / `ChainResult` / `SweepResult`, or an architectural rule MUST update the corresponding `docs/RADIANT_*.md` doc(s) in the same PR. Doc-only PRs are acceptable. Code-only PRs that cross a documented surface are not. Reviewers reject the PR rather than filing a follow-up.

The drift profile this prevents: a code-side change that silently obsoletes a doc claim, producing aspirational documentation that misleads future contributors and agents.

### 21. Every Finding Becomes a Tracked CU
When work uncovers a latent issue orthogonal to the current task — placeholder implementation, suppressed warning, dead helper, schema mismatch, doc claim that doesn't match code, golden-result tolerance bumped, hardcoded value that should be a parameter — it MUST be appended to `docs/tracking/Cleanup_Backlog.md` as a CU entry **before the current PR merges**. No silently-deferred debt; no "I'll log it later".

Required fields per CU entry:
- **CU number** (next available; never reuse)
- **Discovered**: originating task or commit + date
- **Status**: Open / Investigating / Stage-deferred (with gating stage and re-audit date)
- **File**: dotted path or `path:line`
- **Symptom**: what the reader can reproduce
- **Why it still matters**: physics or architectural consequence
- **Suggested fix**: one of (a) inline-fix-now, (b) stand-alone task, (c) delete-as-unused; with effort estimate and category (A/B/C/D)

### 22. CU Closure Is a Commit-Linked Event
A CU is closed only by moving its entry into the **Resolved** section of `docs/tracking/Cleanup_Backlog.md` with: resolution date, linked commit SHA, and a one-line resolution summary. Phantom closure (deleting an entry, marking ✓ without a commit, or moving to Resolved without the SHA) is forbidden.

Stage-deferral rule: if a CU is intentionally deferred behind unrelated stage work, the entry MUST record the gating stage(s) and a re-audit date. When a gating stage lands, the next PR touching that area re-audits the CU and either closes it or refreshes the deferral record (new gating stage + new re-audit date). A CU may not be silently carried across multiple stage landings without re-audit.

### 23. Every Artifact Has One Defined Home — and a Conforming Name
`docs/OPERATING_MODEL.md` §1 defines the closed folder taxonomy (architecture / adr / guides / theory / validation / tracking / plans / reports / archive) and §5 defines the binding naming conventions for every non-source file. Placement and naming are review-blocking: no project-management markdown inside a Python package, nothing new at `docs/` top level, no status or version words in filenames. When a placement question isn't answered by the Operating Model, the answer is added to it in the same PR.

### 24. Plans and Reports Have a Lifecycle
Every plan, audit, and report opens with a `Status:` header (Draft / Active / Complete / Superseded). The PR that completes a plan moves it to `docs/archive/` (HISTORICAL banner: date + completed-by) in that same PR — parallel to Rule 22's CU-closure protocol. Reports in `docs/reports/` are point-in-time records: immutable once complete, never moved, never edited; corrections are new documents. A "✅ COMPLETE" banner on a file still in the live tree is a violation.

### 25. One Registry Per Concern
Technical debt lives only in `docs/tracking/Cleanup_Backlog.md`; capability gaps only in `docs/tracking/gaps.md`. Creating a new tracking document requires folding and archiving the one it replaces in the same PR. Plans may reference registry entries but never re-enumerate them.

### 26. Generated Artifacts Are Regenerable, Committed Only With Cause
A binary or derived file may be committed only if it is (a) a golden baseline a test asserts against, or (b) a figure a committed document references. Every committed artifact names its generator (script + input) in a manifest or the referencing doc. When a baseline set is superseded, the old set is deleted in the same PR — git history is the archive. Everything else (results workbooks, ad-hoc plots) is regenerate-on-demand and gitignored.

### 27. One Canonical Version
When an implementation, plan, or baseline is superseded, the old version is deleted from the working tree, not retained alongside its replacement. A closed version may persist only with an explicit deferral record (gating condition + re-audit date), mirroring Rule 22's stage-deferral protocol.

### 28. Audit Protocol — Chartered In, Dispositioned Out
Chartered audits are owner-triggered with a written scope before work starts, live in exactly one `docs/reports/<topic>_<YYYY-MM>/` folder, and are immutable once complete. An audit is done only when every finding carries one of three dispositions: **CU'd** (Rule 21), **Planned** (`docs/plans/`, under Rule 24), or **Declined** (with one line of rationale). Lightweight hygiene checks against Rules 23–27 run at every phase close via the PR checklist. Full protocol: `docs/OPERATING_MODEL.md` §2.

### 29. Behavior-Affecting Changes Get a CHANGELOG Entry
The repo root `CHANGELOG.md` (Keep a Changelog format, `## [Unreleased]` section) records every user-observable change. A PR MUST add an entry under `[Unreleased]` in the same PR when it:
- (a) changes computed results — physics model, parameter default, or golden baseline (prefix the entry **Results-affecting:** and state direction and rough magnitude), or
- (b) adds, renames, deprecates, or removes a public surface — API method, parameter, metric, error class, or config field, or
- (c) adds or removes a capability tracked in `docs/tracking/gaps.md`.

Refactors, doc-only, test-only, and internal changes with no observable effect get no entry — the changelog is a user-facing record, not a commit log. The changelog entry complements, never replaces, the registry updates (Rules 21–22) and lock-step doc updates (Rule 20). Enforced via the PR-template checklist, the same mechanism as Rule 20. The changelog begins 2026-07-07; earlier history is git log plus the tracking registries, not retroactively reconstructed.

### 30. Code Runs on Windows and macOS
RADIANT is developed on macOS and must run unmodified on Windows. Every change — library, scripts, dev tools, tests — is written cross-platform:

- **Paths**: build paths with `pathlib.Path`; never concatenate path segments with `"/"` string operations; never hardcode absolute POSIX paths (`/tmp`, `/usr/...`, `/Users/...`) in code or defaults. A platform-dependent default (e.g. an external binary location) must fail with an actionable error (Rule 15) on the platform where it doesn't apply.
- **Encoding**: every text-mode `open()`, `Path.read_text()`, and `Path.write_text()` passes `encoding="utf-8"` explicitly. Windows' locale default is cp1252, which mis-decodes the `µ`/`°` characters this codebase uses (CU-149).
- **Newlines**: when a written text artifact's exact bytes matter (checksummed files, MODTRAN decks, golden text baselines), pass `newline="\n"` explicitly; otherwise accept platform newlines. Repo-side normalization is `.gitattributes`' job (CU-150).
- **APIs**: no POSIX-only stdlib modules (`fcntl`, `termios`, `pty`, `os.fork`, `signal`-based timeouts) in library code. Platform-specific code paths require an explicit `sys.platform` branch covering both platforms, and a reason.
- **Case**: never rely on filesystem case-insensitivity — two paths differing only in case are the same file on default macOS/Windows and different files on Linux CI.

New code that violates any of these is review-blocking even if it passes tests on the development machine — the tests only exercise the platform they run on.

---

## Agent Task Discipline

These rules govern how a coding agent handles a task. Violating them produces scope creep, architecture drift, or silent physics bugs.

- **One task per conversation.** Do only what the task specifies. Stop.
- **Read before writing.** Before writing any code, read the architecture document(s) listed in the task's "Read first:" section.
- **Do not implement unrequested features,** even obviously related ones. They get their own task.
- **Do not modify files outside the task's stated scope.**
- **Do not invent abstractions** not specified in the architecture documents.
- **Stop and ask if you encounter a contradiction** between the task and the architecture docs. Do not guess; do not resolve it silently.
- **Write tests as you go.** Do not batch tests at the end.
- **Run tests before declaring complete.** A task is not done until the tests pass.
- **Produce a structured report** when complete, following the category requirements below.

---

## Multi-Agent Git Hygiene

Multiple agents work this repo. Long-lived, shared workspaces — not branches — are
what create merge pain, files changing underfoot, and ambiguous `git status`.
These rules keep concurrent work clean. They are process rules, enforced by
convention and review (not CI).

- **One agent, one workspace. Never two agents in the same working directory at once.** This is the load-bearing rule — it is what prevents files appearing under you and registry files changing mid-edit. If work genuinely overlaps in time, isolate with a **git worktree** per agent (`git worktree add ../ssr-<task> -b <task-branch>`), each on its own branch sharing one repo/history.
  - **Editable-install caveat (worktrees):** `pip install -e .` writes a `.pth` that pins `import radiant` to whichever checkout was installed (normally the **main** tree). `pytest` handles this itself — `pythonpath = ["src"]` in `pyproject.toml` (rootdir-relative) makes a test run inside a worktree import *that worktree's* `src/`. But plain `python` (scenario runners, ad-hoc scripts) still resolves `radiant` from the editable install, so to exercise a worktree's **library** edits outside pytest, run with `PYTHONPATH=./src` (or `pip install -e .` from the worktree, which re-points the shared `.pth` and thus affects every checkout — avoid when other worktrees are live). Editing scenario/doc/registry files in a worktree needs none of this; only `src/radiant/` edits are affected.
- **One task = one short-lived branch = one merge.** Branch off `main`, do the task, commit, merge back to `main` in the same session, delete the branch. Branches live minutes-to-hours, not days. The reconciliation pain you are avoiding comes from branches that drift; merge fast and there is nothing to reconcile. Name branches by task (`gap96/metric-toggle`), never by agent.
- **Commit at the end of each task, not in a big batch.** Uncommitted work is what gets clobbered when another agent touches the tree. A task is not "done" until its work is committed.
- **Registries are the collision hot-spots** — `docs/tracking/gaps.md`, `docs/tracking/Cleanup_Backlog.md`, `CHANGELOG.md`. Edits to them must be **small, append-only, and committed immediately** (a new CU/Gap goes in and gets committed on its own, before the surrounding task work), so concurrent edits land in different sections and merge trivially. Never leave a half-edited registry uncommitted across other work.
- **Do not merge to `main` or push without explicit owner approval** (existing rule; restated here because a stale long-lived branch tempts a big catch-up merge). Keep the branch current with small merges instead of one large reconciliation.

---

## Validation Framework

Every task is assigned a category (A–D). The category determines what the completion report must include. The category is declared at the top of each task prompt.

### Category A — Pure Infrastructure
Structured report + self-review checklist.

### Category B — Core Abstractions
All of A, plus:
- **Dimensional audit:** verify every quantity has correct units at every interface
- **Failure modes:** document what breaks if inputs are at or beyond bounds
- **Serialization round-trip:** verify objects serialize and deserialize without loss

### Category C — Physics Implementation
All of B, plus:
- **Numerical truth anchors:** 3 independent sources (literature, analytic result, or trusted tool) that confirm the computed values
- **Assumptions:** explicit list of what is assumed (linearity, small-angle, etc.)
- **Fragility analysis:** what inputs cause this model to break down or become inaccurate
- **Cross-model consistency:** verify this module's output is consistent with adjacent stages (e.g., at-aperture radiance going into optics makes physical sense given the source)

### Category D — Integration and UX
All of C, plus:
- **Integration tests:** full chain tests confirming this change integrates correctly
- **Regression checks:** confirm no golden results changed unexpectedly; if they did, explain why

---

## Validation Section Specifications

When a category requires a validation section, use the exact format below. These are not optional fields — every required section must appear in the task report.

### 1. Numerical Truth Anchors (Category C — mandatory)

Every numerical implementation validated against at least THREE independent sources. For each anchor:

```
Truth Anchor N: [Name]
  Source: [citation, URL, or "hand calculation"]
  Expected: [value with units]
  Actual: [value with units]
  Absolute error: [value]
  Relative error: [value]
  Regime notes: [whether error grows in any parameter regime, and why]
```

If fewer than three anchors are available, explicitly document which are missing and why.

### 2. Dimensional Consistency Audit (Categories B and C — mandatory)

Trace units through every stage of the computation as a table:

```
Stage           | Input Units         | Output Units       | Conversion   | Check
----------------|---------------------|--------------------|--------------|-------
Input λ         | µm                  | µm                 | none         | ✓
Planck          | µm, K               | W/m²/sr/µm         | constants.hc | ✓
Integrate dλ    | W/m²/sr/µm, µm      | W/m²/sr            | trapz        | ✓
× Ω             | W/m²/sr, sr         | W/m²               | multiply     | ✓
× A_pixel       | W/m², m²            | W                  | multiply     | ✓
÷ E_photon      | W, J/photon         | photon/s           | divide       | ✓
× t_int         | photon/s, s         | photon             | multiply     | ✓
```

Every row must check. Any mismatch must be either resolved or explicitly justified.

### 3. Failure Mode Tests (Categories B and C — mandatory)

Test at the edges. Required coverage:

- **Edge-of-domain:** zero, very small (underflow risk), very large (overflow risk), negative
- **Extreme physical cases:** zero transmission, T → 0 K, T → 10000 K, λ → 0, λ → ∞, infinite range
- **Invalid inputs:** wrong types, grid mismatches, over-constrained consistency groups, negative where positive required
- **Conflicting parameters:** specifying both X and derived(X), mutually exclusive modes

Report each case with expected vs. actual behavior.

### 4. Assumptions (Category C — mandatory)

Every physics implementation makes assumptions. Name them explicitly:

```
Assumption: [What is assumed]
  Why valid: [Physics justification]
  What breaks: [What happens if this assumption is violated]
  Detected how: [Runtime check / documentation / silently wrong]
```

### 5. Fragility Analysis (Category C — mandatory)

```
What breaks this implementation?
  - Numerical instability zones
  - Invalid physics regimes
  - Cancellation errors (large - large ≈ small)
  - Overflow / underflow thresholds

Mitigations:
  - Input validation
  - Alternative formulations for extreme regimes
  - Explicit warnings or errors
  - Documentation
```

### 6. Traceability and Reproducibility (All categories)

```
Same inputs → identical outputs: [verified / not verified — explain]
Deterministic seed where applicable: [yes / no — justify]
Intermediate values inspectable: [yes (via result.inspect()) / no — explain]
```

### 7. Cross-Model Consistency (Category C — when multiple methods exist)

When there are multiple ways to compute the same thing, they must agree:

```
Model A: [description]
Model B: [description]
Tolerance: [e.g., < 1% or mathematical identity]
Result: max absolute difference = X, max relative = Y
```

### 8. Integration and Regression (Category D and end of each sub-phase)

```
Existing golden tests: [pass count / total]
  If any failed: [which values changed, by how much, and why]
New golden tests added: [yes / no]
Physics changes documented in CHANGELOG: [yes / no / N/A]
```

---

## Self-Review Checklist

Run this mentally before declaring any task complete.

### Physics
- Did I confuse units anywhere? (Verify the dimensional audit.)
- Did I implement the formula, or did I interpret it and implement my interpretation?
- Are signs correct? Is energy flowing in the right direction?
- Would a physicist raise an eyebrow at any intermediate output?

### Code
- Does the code actually do what the docstring says?
- Are tests testing real behavior, or just passing trivially?
- Is there any test that would still pass if I gutted the implementation?
- Any hidden state, globals, or side effects I missed?
- Would this run on Windows? (paths via pathlib, `encoding="utf-8"` on text I/O, no POSIX-only APIs — R30)

### Architecture
- Does this respect all 30 rules above?
- If I touched a documented surface (public API, schema, error class, stage protocol, ChainState field, architectural rule), did I update the matching `RADIANT_*.md` doc in this PR? (R20)
- If this change affects computed results or a public surface, did I add a `CHANGELOG.md` entry under `[Unreleased]`? (R29)
- Did I uncover any latent issue (placeholder, suppressed warning, dead helper, schema drift) that I left undocumented? If yes, file a CU before merge. (R21)
- If I closed a CU, does the Resolved entry have a linked commit SHA and resolution date? (R22)
- Did I invent any abstraction not in the architecture documents?
- Did I couple modules that should be independent?

### Scope
- Did I implement only what the task asked for?
- Any "while I was here" additions that should be separate tasks?

---

## Structured Report Template

Every task ends with a report in exactly this format. Omit sections not required by the task's category, but never omit required sections.

```
# Task Report: [Task Name]

## Category: [A / B / C / D]

## Files
Created:
  - path/to/file1
Modified:
  - path/to/file2
Tests added:
  - tests/path/test_file.py (N tests)

## Test Results
Total tests: N
Passing: N
Failing: 0
Coverage (this task): XX%
Coverage (overall): YY%

## Numerical Validation (Category C only)
### Truth Anchor 1: [Name]
  Source: ...
  Expected: ...
  Actual: ...
  Absolute error: ...
  Relative error: ...
  Regime notes: ...
### Truth Anchor 2: [Name]
  ...
### Truth Anchor 3: [Name]
  ...

## Dimensional Audit (Categories B, C)
[Table per spec above]
Issues: none / [describe]

## Failure Modes Tested
[List of edge cases with expected vs. actual behavior]

## Assumptions (Category C)
[List per spec above]

## Fragility Points (Category C)
[Known limitations with mitigations]

## Traceability
Same inputs → identical outputs: ...
Deterministic seed: ...
Intermediate values inspectable: ...

## Cross-Model Consistency (Category C, if applicable)
[Comparison results per spec above]

## Regression Status (Category D, or if existing code touched)
Existing golden tests: [pass / total]
Changes to golden values: none / [list with explanation]
New golden tests added: yes / no

## Self-Review
Physics: [notes]
Code: [notes]
Architecture: [notes]
Scope: [notes]

## Open Issues or Questions
[Anything unclear, any decisions that need human input]
```

---

## Package Layout

```
src/radiant/
├── core/           # Foundational abstractions — NO physics, NO sensor knowledge
│   ├── constants.py      # CODATA 2018 physical constants
│   ├── units.py          # Unit conversion registry
│   ├── parameters.py     # ParameterDef, ParameterSet, Tolerance, ConsistencyGroup
│   ├── spectral.py       # SpectralData, SpectralDataStore
│   ├── chain.py          # Stage Protocol, ChainState, ChainRunner
│   ├── radiometry.py     # RadiometricFrame, NoiseTerm
│   ├── geometry.py       # spherical-Earth helpers (slant range, incidence, Euler)
│   ├── viewing_triangle.py  # θ_o-referenced spherical-triangle solutions (ADR-0006)
│   └── regime.py         # RadiometricRegime enum
├── geometry/       # Stage 0: scene geometry — input modes, LOS, derived ranges (ADR-0006)
├── source/         # Stage 1: target + background spectral radiance
├── atmosphere/     # Stage 2: τ_atm, L_path, L_atm
├── optics/         # Stage 3: PSF, MTF, throughput, EE_box, regime final
├── platform/       # Stage 4: smear MTF, jitter MTF
├── spectral_integration/  # Stage 5: spectral → scalar (EE_box coupling)
├── detector/       # Stage 6: QE, noise terms, detector MTF
├── readout/        # Stage 7: TDI, ADC, gain, read noise
├── performance/    # Stage 8: SNR, NEDT, NIIRS, system MTF
├── data/           # SpectralLibrary — loads reference CSVs from repo-root data/ (emissivity, QE, solar)
├── io/             # I/O layer — YAML, MODTRAN, results
├── api/            # Public API — Sensor, SensorConfig, BatchRunner
├── cli/            # CLI — radiant run/validate/explain/gui
└── gui/            # Desktop GUI (PySide6) — view over the scripting API (optional `gui` extra)
```

(`plugins/` was removed 2026-07-06 — it was an empty two-file stub. The extension-point
design lives in `docs/architecture/RADIANT_Plugins.md` under a DEFERRED banner; the
package returns when that spec is implemented.)

---

## Import Rules (Strict — Enforced by `import-linter`)

| Module | May import from |
|--------|----------------|
| `core/` | stdlib, numpy, scipy ONLY |
| Physics stages (geometry through performance) | `radiant.core` ONLY |
| `data/` | `radiant.core` ONLY (+ stdlib, numpy, yaml) |
| `io/` | `radiant.core` + any physics stage (read-only for schema) |
| `api/` | `radiant.core` + all physics stages + `radiant.io` + `radiant.data` (pre-chain library resolution, Rule 6) |
| `cli/` | `radiant.api` + `radiant.io` + `radiant.gui` (lazy — the `radiant gui` subcommand) |
| `gui/` | `radiant.api` + `radiant.core` ONLY (+ PySide6, matplotlib, qtconsole, pyvista/pyvistaqt). No physics stage directly, no `io`/`cli`. The GUI is a view over the scripting API (one action ↔ one API call). |

---

## How to Find Things

| What you need | Where to look |
|--------------|--------------|
| Architecture overview | `docs/architecture/RADIANT_Master_Architecture.md` |
| Where files go | `docs/architecture/RADIANT_File_Tree.md` |
| All parameters | `docs/architecture/RADIANT_Parameter_System.md` |
| Subsystem design detail | `docs/architecture/RADIANT_<Subsystem>.md` |
| Where every document type lives | `docs/OPERATING_MODEL.md` |
| Work tracking (CUs, gaps) | `docs/tracking/Cleanup_Backlog.md`, `docs/tracking/gaps.md` |
| The code | `src/radiant/` |
| The tests | `src/radiant/<stage>/tests/` (unit), `tests/integration/` (full-chain + golden), `tests/` root (cross-cutting: exceptions, provenance, public API surface) |

---

## When Editing an Existing Stage

1. Read the stage's doc (e.g., `docs/architecture/RADIANT_Optics.md`) before changing anything.
2. Read the tests before changing the implementation. The tests define the contract.
3. Run the tests: `pytest src/radiant/<stage>/tests/ -v`
4. Do not add imports that violate the import rules. Check with `import-linter`.
5. Update `_schema.py` if adding or renaming parameters.
6. Do not change default values without reviewing all integration tests — defaults affect golden results.
7. Do not rename public API methods on `Sensor`, `ChainResult`, `SweepResult` without a deprecation warning.

---

## When Adding a New Stage

1. Create `src/radiant/<stage_name>/` directory.
2. Create `_schema.py` with all `ParameterDef` objects for this stage.
3. Create `stage.py` implementing the `Stage` protocol.
4. Create `tests/` with Level 0 tests for the key physics equations.
5. Register the stage in `api/session.py`'s `ChainRunner` stage list.
6. Add the stage to the document map in `docs/architecture/RADIANT_Master_Architecture.md`.

---

## Forbidden Actions

| Action | Why |
|--------|-----|
| `from radiant.optics import *` in a physics module | Violates import rules |
| `state.frames["name"] = frame` | Mutates frozen ChainState |
| Pass raw dict from user input to a physics function | Bypasses validation |
| Hardcode a physical constant anywhere except `constants.py` | Untracked magic number |
| Return `float("nan")` or `float("inf")` silently | Silent failure |
| `except Exception: continue` or `except Exception: pass` | Silent failure |
| `assert value > 0` for user input validation | Use `ParameterBoundsError` |
| `print()` in library code | Use logging |
| Compute EE_box from one PSF and RER from a different PSF | Violates Rule 4 (spatial-domain metrics must share one PSF) |
| Multiply separate `MTF_diffraction × MTF_aberration` for the optical term | Violates Rule 4 — use pupil autocorrelation for `MTF_optics` |
| Add a spatial degradation to only one path (PSF or MTF product) without the other | Violates Rule 4 consistency invariant |
| Accept emissivity as independent parameter for an optical element | Violates Rule 5 |
| Modify a test's `pytest.approx` tolerance to make a failing test pass | Fix the physics, not the test |
| Update a golden file without the review protocol in `RADIANT_Testing_Validation.md §5.3` | Breaks reproducibility |
| Implement anything not requested by the task | Scope creep |
| Land a doc-touching surface change without updating the matching `RADIANT_*.md` doc | Violates Rule 20 — produces aspirational-doc drift |
| Discover a latent issue in passing without filing a CU before PR merge | Violates Rule 21 — produces silent debt |
| Mark a CU resolved without a linked commit SHA and resolution date | Violates Rule 22 — phantom closure |
| Carry a stage-deferred CU across a gating-stage landing without re-audit | Violates Rule 22 — silent perpetual deferral |
| Add a normative claim to a `RADIANT_*.md` doc that no test, contract, or type check enforces | Produces aspirational drift (the failure mode that created the 16 Phase-4 audit findings) |
| Land a results-affecting or public-surface change without a `CHANGELOG.md` entry | Violates Rule 29 — untracked behavior change |
| Text-mode `open()`/`read_text()`/`write_text()` without `encoding="utf-8"` | Violates Rule 30 — cp1252 mojibake on Windows |
| Hardcode an absolute POSIX path or build paths by string concatenation | Violates Rule 30 — breaks on Windows |
| Import a POSIX-only stdlib module (`fcntl`, `termios`, `pty`, `os.fork`) in library code | Violates Rule 30 — breaks on Windows |

---

## Code Style

- **Formatter:** `ruff format`. Line length 100.
- **Linter:** `ruff check`. Zero warnings on `radiant.core` and `radiant.api`.
- **Type annotations:** Required on every function and method. `mypy --strict` must pass on `core/` and `api/`.
- **Docstrings:** All public functions and classes. One-line summary; Parameters/Returns section when non-obvious.
- **No `TODO`** in committed code without a linked GitHub issue number.

---

## Running Tests Locally

```bash
# Setup:
pip install -e ".[dev]"

# Fast tests (Level 0 + Level 1, no golden):
pytest src/ -v -m "not golden"

# Full suite:
pytest -v

# Coverage:
pytest --cov=radiant --cov-report=html

# Type check:
mypy --strict src/radiant/core src/radiant/api

# Import rules:
import-linter --config pyproject.toml

# Organization rules (placement + naming per docs/OPERATING_MODEL.md):
python scripts/check_org_rules.py

# Parameter-reference doc freshness (CU-099; also enforced by a pytest test):
python scripts/gen_param_reference.py --check

# Lint (src/ and tests/ — CU-089 widened the gate to cover tests/):
ruff check src/ tests/
```

All of these must pass before submitting a PR or declaring a task complete.
