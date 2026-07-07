# Cleanup Backlog — Phase 2 Plan

**Status:** Draft — written 2026-04-24
**Scope:** Open items in `docs/Cleanup_Backlog.md` after Phase 1 (mypy/ruff/import-linter) closed out CU-001/002/010/015.
**Governing docs:** `CLAUDE.md` (Rule 4 / 11 / 17 / 19, regression gate, one-task-per-commit), `docs/architecture/RADIANT_Master_Architecture.md`.
**Sequencing rule:** any item flagged "Stage-deferred" stays where it is — those will close as a side-effect of the Option C plan landing the relevant stage. Do **not** pre-emptively pick them up here; doing so would either revert Cell 28/58 invariants or duplicate work that the stage author owns.

---

## Triage Summary

| ID | Title | Category | Risk | Owner / Trigger | Action |
|----|-------|----------|------|------------------|--------|
| CU-003 | MTF tolerance miss on `swir_aerial_gas.yaml` | C (physics) | M | independent | **Pick up — Track A** |
| CU-004 | `mwir_ground_test.yaml` ambiguous classification | A (bookkeeping) | L | independent | **Pick up — Track B** |
| CU-005 | `theta_o_from_eta` unwired | A (decision) | L | Stage 7 | Defer — revisit after Option C Stage 7 |
| CU-006 | `LineOfSightGeometry` field-order footgun | B (refactor) | L | independent | **Pick up — Track C (do first)** |
| CU-007 | MWIR-mixed `UserWarning` suppressed in `_inferrer` | C (physics) | M | Stage 3 / 6 | Defer — Option C Stage 6 |
| CU-008 | `GroundBackground` placeholder grey, not spectral | C (physics) | M | Stage 3 | Defer — Option C Stage 3 (background subsystem) |
| CU-009 | LOS uses Kármán default, no observer geometry | C (physics) | M | Stage 5 | Defer — Option C Stage 5 |
| CU-011 | MODTRAN `evaluate()` aliases two-leg τ | C (physics) | H | Stage 6 | Defer — Option C Stage 6 |
| CU-012 | Shadow-mode classification injection unwired | A (test wiring) | L | Stage 6 | Defer — Option C Stage 6 fixture work |
| CU-013 | Shadow-mode `rtol=1e-6` may be too tight | A (tuning) | L | Stage 6 | Defer — Option C Stage 6 calibration |
| CU-014 | Stage-4 ground-bg assembly is thermal-only | C (physics) | H | Stage 6 | Defer — Option C Stage 6 (re-baselines anchors) |

**Independently actionable now:** CU-003, CU-004, CU-006.
Recommended order: **CU-006 → CU-004 → CU-003** (cheapest first; CU-003 last because it may flush a real physics drift).

---

## Execution Principles (carried over from Phase 1)

- One backlog item per commit. Do not bundle.
- Regression gate is mandatory at every commit:
  ```
  pytest src/ -q                       # 2360 expected pass
  pytest tests/integration/ -q         # 381 expected pass
  mypy --strict src/radiant/core src/radiant/api
  ruff check src/
  lint-imports --config pyproject.toml
  ```
- **Stop and ask** before proceeding if any of:
  - A fix would change physics behavior (especially for CU-003).
  - A golden / snapshot result drifts unexpectedly.
  - The change exceeds 50 lines.
  - A type or import error turns out to mask a real bug.
- Commit message format: `chore(debt): CU-### — <one-line summary>`. Body cites which CU is closed and which `Cleanup_Backlog.md` line moved.

---

## Track C — CU-006: `LineOfSightGeometry` keyword-only construction

**Why first:** smallest, lowest-risk, prevents a real footgun before Stage 5 inferrer expansion. Category B (no physics change).

### Pre-reads
- `src/radiant/core/los_geometry.py` (the dataclass + the unwired converter from CU-005 lives here too — do **not** touch it in this commit)
- All call sites: `grep -rn "LineOfSightGeometry(" src/ tests/`
- `docs/architecture/RADIANT_Master_Architecture.md` Rule 12 (parameter system) for keyword discipline

### Steps
1. Add `kw_only=True` to the dataclass decorator: `@dataclass(frozen=True, kw_only=True)`.
2. Re-order field declarations to match the plan's textual order `(h_tgt, h_atm_top=1e5, theta_o, theta_s, delta_phi)` now that positional ordering is no longer load-bearing. Confirm `theta_o` has no default (or pick one explicitly — defer to current implementation if it has none).
3. Convert any positional call sites to keyword form. Test files in `core/tests/` are the most likely callers.
4. Run targeted tests first: `pytest src/radiant/core/tests/ -v -k los_geometry`.
5. Full regression gate.
6. Move CU-006 from "Open" to "Resolved" in `docs/Cleanup_Backlog.md` with commit hash.

### Stop triggers
- Any non-test production call site uses positional construction → escalate; that call site needs review before flipping to kw-only.
- A test fails because it relied on positional argument order — fix the test (the test is exposing the very bug we're closing).

### Validation expectations
- Dimensional audit: N/A (no physics).
- Failure mode: pass a wrong-order dict literal → expect a `TypeError` at construction (this is the whole point).
- Self-review checklist: confirm `Architecture: ✓` (rule 12 keyword discipline reinforced).

---

## Track B — CU-004: `mwir_ground_test.yaml` snapshot reclassification

**Why second:** independent of code changes, but requires a small judgement call on schema (single enum vs list).

### Pre-reads
- `tests/integration/snapshots/option_c_baseline.yaml` — find the `mwir_ground_test` entry and its current `classification`
- The schema definition for that YAML (search for the enum / validator). Likely `tests/integration/conftest.py` or a sibling `_schema.py`.
- The Option C plan section that defines the classification taxonomy

### Decision required (raise to user before coding)
Two paths, pick one explicitly:

**Path A — single enum, expand the vocabulary**
Add a new value `expected_to_change_at_stage_6_and_stage_7` (or similar). Reclassify the cell. Lowest churn but couples the taxonomy to compound cases.

**Path B — list of classifications**
Promote the field from `str` to `list[str]`. Update the validator and any downstream consumers (shadow-mode comparison, baseline-snapshot reader). More flexible long-term, more touch points.

**Recommend asking** before coding — this is a snapshot-schema decision, not a mechanical fix.

### Steps (after decision)
1. Implement the chosen schema path with its validator update.
2. Reclassify `mwir_ground_test`.
3. If Path B: update every consumer in `tests/integration/` and any stage that reads `option_c_classification`.
4. Run `pytest tests/integration/ -q` plus any unit test for the snapshot loader.
5. Full regression gate.
6. Move CU-004 to Resolved with the chosen path documented.

### Stop triggers
- More than 3 consumers of the classification field would need to change for Path B → reconsider Path A.
- Any other scenario in the snapshot also has a compound classification — handle them all in this commit (still one CU, one logical change).

### Validation expectations
- No physics change. Category A.
- Confirm shadow-mode comparison still skips/compares correctly for the reclassified cell — exact behavior depends on the chosen path.

---

## Track A — CU-003: MTF tolerance miss on `swir_aerial_gas.yaml`

**Why last:** highest investigation cost; a real PSF-↔-MTF-product divergence is exactly the failure mode CLAUDE.md Rule 4 is written to catch. Either the tolerance is loose because the scenario hits a numerical edge (legitimate), or one path is missing a degradation (real bug).

### Pre-reads
- `docs/architecture/RADIANT_Master_Architecture.md` Rule 4 in full
- `docs/architecture/RADIANT_Optics.md` (PSF path + MTF product path)
- `src/radiant/optics/psf/effective.py` and the consistency check that emits the warning
- `examples/swir_aerial_gas.yaml` (or wherever the scenario actually lives — task author confirmed the path is uncertain)
- `scripts/capture_option_c_baseline.py` (the script that surfaced this)

### Investigation phase (no code changes)
1. Locate the scenario YAML (`grep -rn "swir_aerial_gas" .`) and confirm the actual file path.
2. Reproduce: run the consistency check standalone on this scenario at `standard` fidelity, capture `max_err_x`, `max_err_y`, and the per-frequency MTF residual.
3. Identify which spatial degradation differs between paths. Suspects, in order of likelihood:
   - **Jitter MTF**: PSF path applies a Gaussian kernel; MTF product applies the analytic MTF. Off-by-σ or radians-vs-arcsec bug?
   - **Smear**: the rectangular smear function is sometimes implemented as a sinc on the MTF side and a boxcar convolution on the PSF side — verify they FT-match.
   - **Diffraction normalization**: pupil-autocorrelation normalization vs. PSF central pixel.
   - **Sampling / aliasing**: high-frequency content folded differently between paths.
4. Quantify the residual: is it monotonic in frequency (a missing low-freq term), or peaked near Nyquist (an aliasing/sampling issue)?

### Branch on findings (raise to user before coding)
- **Finding A:** missing or mis-applied degradation in one path → real bug. Open as a stand-alone task with Category C scope. Do **not** silently widen the tolerance.
- **Finding B:** numerical edge (e.g., very small Q, very fast f/#, near-nyquist aliasing inherent to the sampling grid) → tolerance widening is justified for this scenario only. Document why in a per-scenario tolerance override and a comment in `RADIANT_Optics.md`.
- **Finding C:** scenario YAML has an inconsistent input (e.g., a jitter spec that the PSF path interprets differently from the MTF path) → fix the scenario YAML, not the consistency check.

### Steps (after the decision)
1. Implement the chosen branch.
2. Re-run the consistency check on the scenario; capture before/after residuals.
3. Run the full pytest src/ + integration suite. Watch for any other scenario that drifts (especially golden snapshots).
4. **If goldens drift:** stop — follow `RADIANT_Testing_Validation.md §5.3` golden-update protocol; do not silently update.
5. Move CU-003 to Resolved with the residual numbers and the chosen branch documented.

### Stop triggers
- Any other scenario's MTF residual changes by > 1e-6 — that is a Rule-4 regression and must be reported.
- The fix touches `optics/` production code by > 50 lines — escalate to a stand-alone task.
- The fix would silently update a golden value — stop, follow the protocol.

### Validation expectations (Category C — full)
- **Numerical truth anchors:** at least three. For an optical-MTF fix:
  1. Closed-form Airy MTF at the same `Q = λ·F#·f_s` for diffraction-only.
  2. Hand-computed jitter MTF: `exp(-2π² σ² f²)` at one frequency.
  3. Smear MTF: `sinc(π · v_smear · t_int · f)` at one frequency.
- **Dimensional audit:** trace one frequency through both paths; both must end in cycles/(detector pitch) consistently.
- **Failure modes:** zero jitter, infinite jitter, Q → 0, Q → 1, on-axis vs corner field point.
- **Cross-model consistency:** the explicit purpose of the consistency check; report the post-fix `max_err` and confirm it crosses below 1e-6.

---

## Stage-Deferred Items (do not pick up standalone)

Each of these is a known issue waiting on a specific Option C stage. Deferring them is intentional — picking them up here would either:
- duplicate Stage 6's own scope (CU-007, CU-011, CU-014),
- revert pinned cell invariants that the stage author plans to re-baseline (CU-014, parts of CU-013),
- or fix one symptom without fixing the underlying parameter surface (CU-008, CU-009, CU-005).

When the relevant stage lands:
- Stage 3 (atmosphere/backgrounds): close CU-008.
- Stage 5 (partial-column atmosphere + observer geometry): close CU-009.
- Stage 6 (spectral integration / E_sky decomposition / MWIR-mixed / two-leg τ): close CU-007, CU-011, CU-012, CU-013, CU-014.
- Stage 7 (sensor descriptor): close CU-005 (or remove the unwired converter if still unused).

Each closure follows the same protocol as the Track A/B/C items above: one commit, regression gate, backlog row moved to Resolved.

---

## Phase 2 Completion Criteria

Phase 2 is **complete** when:
- CU-006, CU-004, CU-003 are in the Resolved section of `docs/Cleanup_Backlog.md`, each with a commit hash.
- Or each has been explicitly converted to a stand-alone task (with a separate task prompt) because it exceeded the 50-line / physics-change scope and a Track-A/B/C commit could not close it.
- Open section of `Cleanup_Backlog.md` contains only stage-deferred items (CU-005 / 007 / 008 / 009 / 011 / 012 / 013 / 014).
- Regression gate green at the final commit.
