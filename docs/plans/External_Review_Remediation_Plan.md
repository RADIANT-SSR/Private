# External Review Remediation Plan (2026-09-30)

**Status:** Active — opened 2026-09-30; **six of six code items landed 2026-09-30** (branch `review/2026-09-batch`). Open: CU-380's scenario sweep, CU-384, CU-387. Not archivable until those close (Rule 24).
**Charter:** owner direction 2026-09-30: "log all the gaps/CUs, formulate a plan
and then kick off the fix … I want these fixes done tonight so I can redeploy
tomorrow and test."
**Source report:** `docs/reports/external_review_2026-09/` (findings,
verification, dispositions — all immutable per Rule 24).
**Registry:** CU-380 … CU-387, Gap 132 … Gap 136, reserved on `origin/main` in
`a6c18028` per Rule 21.

---

## 1. Objective

Land the code-backed fixes for the seven confirmed external findings in one
batch, so the engine can be redeployed and re-tested against the reviewer's own
case. Two items are explicitly **not** built tonight because they need an owner
ruling or an ADR amendment; they are planned here and left Open.

---

## 2. Scope

### In scope tonight (code-backed, closable)

| CU | Finding | Size | Outcome |
|---|---|---|---|
| CU-386 | tests write a tracked file without encoding/newline | S | **CLOSED** — artifact untracked to `build/`, both keywords supplied |
| CU-385 | CLI stdout/stderr not UTF-8 (Rule 30) | S | **CLOSED** — 81 affected strings across 36 modules; `µ`/`°` were never the problem |
| CU-382 | rate-parameter ceilings justified by their default | S | **CLOSED** — three coupled ceilings raised, not one |
| CU-380 | warm-optics nearfield silently zero | M | **PARTIAL** — warning + examples landed; 5-scenario sweep deferred (reasons in the CU) |
| CU-381 | 1/f model — first-principles replacement | L | **CLOSED** — transfer-function integral; 21 Level-0 limits; Gap 137 spun out |
| CU-383 | stage cross-param validators unreachable from `validate` | M | **CLOSED** — 3 of 4 validators moved pre-chain; the 4th provably cannot |

### Planned, not built tonight

| CU | Why held |
|---|---|
| CU-384 | Needs an ADR-0010 amendment (dense-by-construction vs. conditional legality) and an owner ruling on the null-sentinel semantics. Rule 20 requires the ADR move in the same PR, so it is a task of its own. |
| CU-387 | Owner ruling requested. A chartered Rule 28 sweep over 51 scenario `gaps.md` files is larger than this whole batch, and the standing promotion rule it would add touches `scripts/check_org_rules.py` — permitted under the moratorium carve-out (CU-380 is the escaped defect), but not something to start the same night as the fixes it would have caught. |

### Out of scope

The five Gap entries (132–136) are capability additions, not defect repair.
Gap 133 in particular should land *with or after* CU-381, since it documents
the dispatch CU-381 rewrites.

The 34 extended-scene thermal scenarios that CU-380's warning will newly flag
are deferred to the chartered scenario sweep (recorded in CU-380, not implicit).

---

## 3. Execution order and rationale

Ordered so the tree is clean before anything else is measured, and so the
largest, riskiest change lands against an already-verified baseline.

1. **CU-386 first.** A `pytest` run currently rewrites a tracked file. Every
   subsequent verification in this plan reads `git status`, so this is fixed
   before it can confuse the rest of the night.
2. **CU-385.** Independent, small, no physics.
3. **CU-382.** Schema-only bound change; nothing downstream assumes a
   magnitude, and no default moves, so no result changes.
4. **CU-380.** Results-affecting. Lands the warning first, then the
   remediation of `examples/` + the 5 point-source scenarios, so the warning's
   own predicate is exercised by the files it is about to flag.
5. **CU-381.** The large one. Level-0 tests before implementation (Rule 18),
   against the analytic limits listed in §4.
6. **CU-383.** Last because it is additive and touches the most surfaces
   (`validate` path + CLI + study path) without changing physics.

**Branch:** one short-lived `review/2026-09-batch`, per-CU commits each
carrying its own `CU-Closes:` trailer (Rule 22), full gate battery once before
merge, single merge to `main`, branch deleted. Running the ~7-minute GUI suite
once per schema-touching commit would cost three runs for no added signal; the
battery is a merge gate, not a commit gate.

---

## 4. CU-381 design (the one with real physics content)

Replace the closed form with the measurement's noise transfer function:

$$\\sigma^2 = \\int_0^\\infty S(f)\\,\\lvert H_{\\text{box}}(f)\\rvert^2\\,\\lvert D_K(f)\\rvert^2\\,\\lvert H_{\\text{ref}}(f)\\rvert^2\\,df$$

- $S(f) = K_f/f$ above a white floor set by `detector.flicker_corner_hz` (new,
  load-bearing — the integral needs the floor; this is what scenario 2.2 Gap 1
  recommended independently).
- $H_{\\text{box}}(f) = t_{\\text{int}}\\,\\mathrm{sinc}(\\pi f t_{\\text{int}})$ — the
  per-frame boxcar integration. This is what finally makes $\\sigma_{1f}$ depend
  on integration time at all.
- $D_K(f)$ — Dirichlet kernel of the K-frame comb at spacing
  `readout.frame_period_s`. Carries the co-add correlation.
- $H_{\\text{ref}}(f)$ — the differencing high-pass: CDS (`readout.cds_enabled`)
  or the `counting_mode: up_down` reference phase. Unity when there is no
  reference.

### Acceptance limits (these are the Level-0 tests, written first)

| Limit | Expected | Replaces |
|---|---|---|
| $f \\to 0$ | $\\lvert H\\rvert^2 \\to (K\\,t_{\\text{int}})^2$ — correlated, ×K | checklist item (c), with no exponent chosen |
| white $S(f)$ | $\\int \\to K \\times$ per-frame — ×√K | confirms √K is kept where it is correct |
| $K = 1$ | collapses to the single boxcar | regression anchor |
| $K=1$, no corner, no reference | reproduces today's $\\sqrt{K_f \\ln(f_{hi}/f_{lo})}$ | free back-compat anchor |
| corner-capped, $K=1$ | matches scenario 2.2's measured corner-capped values | third independent anchor (Category C needs 3) |

### Decisions already made

- `flicker_f_low_hz` / `flicker_f_high_hz` are **kept as optional overrides**
  (unset ⇒ derived from timing), following `readout.frame_period_s`'s
  default-0.0-means-unset precedent. Not back-compat politeness: the DC
  divergence is physical for a bare un-referenced sum ($\\lvert D_K\\rvert^2 \\to K^2$
  while $S \\sim 1/f$), so a staring case must still state its observation
  window. The model should say that rather than hide it behind a 0.01 Hz
  default.
- `flicker_1f` **stays in `TEMPORAL_TERMS`**. Only the scaling dispatch
  changes. The correlation-aware pattern already exists at
  `readout/stage.py:222` for `clutter` and PRNU/DSNU.
- TDI keeps **×√N under analog TDI** — different physical pixels, independent
  1/f — and takes ×N only under digital TDI, where the same pixel is re-read.
  The co-add fix must not be applied blanket across axes.

### Known risk

`flicker_K` defaults to 0.0 and is set only by one GUI test and scenario 2.2's
script, so **no golden baseline moves**. The exposure is confined to users who
opted into the term — which is why this is a free correctness fix and also why
it went unnoticed for two releases.

---

## 5. Verification

Per-CU: the Level-0 tests named above, plus the originating reproduction in
`docs/reports/external_review_2026-09/reproduce.py` re-run to show the
before/after it was written to capture.

Pre-merge, the full battery (CLAUDE.md): `pytest -q`, `pytest scripts/`,
`mypy --strict src/radiant/core src/radiant/api`, `ruff check` and
`ruff format --check` over the six governed trees, `lint-imports`,
`check_org_rules.py`, `gen_param_reference.py --check`. The `_schema.py`
touches in CU-382 and CU-381 mean the full GUI suite runs — `pytest -q` covers
it via `testpaths`.

CHANGELOG: CU-380 and CU-381 are **Results-affecting:** entries with direction
and rough magnitude; CU-382/385/386 are public-surface or capability entries;
CU-383 is a public-surface entry.

---

## 6. Closure

This plan is complete when CU-380, 381, 382, 383, 385 and 386 are Resolved
with `CU-Closes:` trailers, and CU-384 and CU-387 carry a current deferral
record naming their gating condition. At that point the plan moves to
`docs/archive/` with a HISTORICAL banner in the same PR (Rule 24).

---

## 7. Outcome notes (added 2026-09-30, at the batch's close)

Where the plan was wrong, recorded so the next plan is better:

- **§4's acceptance limit "K = 1 reproduces today's closed form" was overstated.**
  With the boxcar weight it holds only in the narrowband limit `f·t_int ≪ 1`,
  which the shipped 1 MHz / 5 ms default badly violated — itself defect (b).
  The limit is still a valid anchor, with that condition stated.
- **§4 assumed `f_low`/`f_high` were kept for back-compatibility.** `f_low`
  survives for a *physical* reason instead (the DC divergence of an
  un-referenced sum is real), and `f_high` turned out to be physically
  unnecessary — the integration-time boxcar already provides the roll-off.
  Better than planned.
- **§3's "remediate `examples/`" assumed element trains.** The right fix was
  the opposite: a hand-computable anchor and a *minimal* config both
  legitimately exclude warm optics, so they state it explicitly and the golden
  stays bit-identical. The plan's assumption would have changed a golden for no
  gain.
- **CU-380's commit carried a premature `CU-Closes: 380` trailer.** The engine
  fix landed; the scenario sweep did not. Corrected in the registry entry,
  which is the authoritative record.
- **CU-380's verification was too narrow.** It ran the optics and golden suites
  but not `api`, and missed a test the example annotation broke. CU-383's
  commit fixed it. The merge battery would have caught it regardless — which is
  what the battery is for — but a per-CU suite selection by "which files did I
  touch" is exactly the unsound predictor CLAUDE.md warns about, and this is
  another instance of it.
- **Two new tests had to move out of stage test directories.** A stage test may
  not `import radiant`, because the top-level package reaches `api`/`io` and the
  physics-stages-import-only-core contract is machine-enforced. Both moved to
  `tests/integration/`.
