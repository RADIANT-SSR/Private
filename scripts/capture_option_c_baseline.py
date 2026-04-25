"""Capture the pre-Option-C golden surface as a shadow-mode regression snapshot.

This is Stage 0 step 5 of the Option C Implementation Plan
([docs/Option_C_Implementation_Plan.md](../docs/Option_C_Implementation_Plan.md)).
It enumerates every YAML scenario under ``scenarios/`` (and, as a fallback,
``examples/`` templates, since the current repo keeps runnable YAML configs
there rather than under ``scenarios/``) that can be run through the existing
pipeline, executes the full chain, and captures:

- Captured-at git SHA
- The fixed wavelength grid
- For each scenario: status (ok|error), optional error message, placeholder
  ``classification`` + ``cell_ref`` fields, SNR, NEDT, MTF-at-Nyquist, and
  at-aperture radiance at each wavelength on the fixed grid.

The resulting YAML lands at ``tests/integration/snapshots/option_c_baseline.yaml``
and is the shadow-mode reference for Stage 3.

Per Stage 0 step 6, each entry carries a ``classification`` field, initially
populated by a conservative rule-based heuristic:

- LWIR-thermal-extended scenarios with sensor above the target-at-surface
  are tagged ``invariant`` (the existing pipeline handles these correctly).
- Sub-pixel terrestrial reflective / MWIR scenarios are tagged
  ``expected_to_change_at_stage_3`` (or ``_at_stage_6`` for MWIR) because
  Stage 3/6 unlocks new atmospheric propagation terms.
- Anything ambiguous is tagged ``unclassified`` for manual review.

Determinism: chain runs with ``params.resolve()`` and no RNG; repeated runs
give bit-identical results.

Per CLAUDE.md §1 (Python 3.11+), §14 (no print in library code): this is a
CLI entry point, so ``print`` is allowed. Uses only stdlib + radiant +
PyYAML (already a radiant dependency via ``radiant.io.config``).
"""

from __future__ import annotations

import math
import subprocess
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from radiant.api.session import RadiantSession
from radiant.io.config import load_config


REPO_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_DIR = REPO_ROOT / "scenarios"
EXAMPLES_DIR = REPO_ROOT / "examples"
SNAPSHOT_PATH = (
    REPO_ROOT / "tests" / "integration" / "snapshots" / "option_c_baseline.yaml"
)

# The fixed λ grid used for at-aperture radiance samples in the snapshot.
# Spans the full VNIR-LWIR range; each scenario evaluates only the subset of
# samples that fall inside its own filter band.
FIXED_GRID_UM: tuple[float, ...] = (
    0.5, 0.7, 1.0, 1.6, 2.2, 3.5, 4.0, 4.5, 8.0, 10.0, 12.0,
)


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    status: str           # "ok" | "error"
    error: str | None
    classification: str   # "invariant" | "expected_to_change_at_stage_3" |
                          # "expected_to_change_at_stage_4" |
                          # "expected_to_change_at_stage_6" |
                          # "expected_to_change_at_stage_6_and_stage_7" |
                          # "unclassified"
    cell_ref: str | None  # "Cell 28", "Cell 58", or None
    snr: float | None
    nedt_K: float | None
    mtf_at_nyquist: float | None
    L_aperture_W_m2_sr_um: list[float | None]


def _git_sha() -> str:
    """Return the current HEAD SHA (full)."""
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout.strip()


def _finite_or_none(x: Any) -> float | None:
    if x is None:
        return None
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return None
    return xf if math.isfinite(xf) else None


def _discover_yaml_scenarios() -> list[tuple[str, Path]]:
    """Find all YAML scenario files; skip non-runnable docs.

    Returns a list of (display_name, path) tuples. Display name is the
    path relative to the repo root. Order is deterministic (sorted).
    """
    found: list[tuple[str, Path]] = []
    # Primary location per the plan.
    for pat in ("*.yaml", "*.yml"):
        for p in sorted(SCENARIOS_DIR.rglob(pat)):
            found.append((str(p.relative_to(REPO_ROOT)), p))
    # Fallback: examples/ has the runnable YAMLs today (templates + minimal).
    # Explicit note in docs that these are captured here because scenarios/
    # holds walkthroughs, not YAML configs.
    for pat in ("*.yaml", "*.yml"):
        for p in sorted(EXAMPLES_DIR.rglob(pat)):
            found.append((str(p.relative_to(REPO_ROOT)), p))
    return found


def _infer_band_bounds(cfg: dict) -> tuple[float, float] | None:
    """Pull filter_min_um / filter_max_um out of a parsed YAML dict."""
    si = cfg.get("spectral_integration", {})
    lo = si.get("filter_min_um")
    hi = si.get("filter_max_um")
    if lo is None or hi is None:
        return None
    return float(lo), float(hi)


def _classify(cfg: dict, yaml_name: str) -> tuple[str, str | None]:
    """Classify a scenario + identify Cell 28 / Cell 58 anchor references.

    Conservative rules per Stage 0 step 6:

    - LWIR extended + sensor at or above surface + h_tgt not set (==0) →
      invariant (Cells 28, 58 and analogous LWIR thermal scenarios handled
      correctly by the current pipeline).
    - MWIR scenarios → ``expected_to_change_at_stage_6`` (E_sky
      decomposition lands at Stage 6).
    - VIS/NIR/SWIR scenarios → ``expected_to_change_at_stage_3`` (two-leg
      τ_sun/τ_up split + background aperture branch land at Stage 3).
    - Anything that doesn't match these buckets → unclassified.
    """
    bounds = _infer_band_bounds(cfg) or (0.0, 0.0)
    lo, hi = bounds
    center = 0.5 * (lo + hi) if hi > 0 else 0.0

    atm = cfg.get("atmosphere", {})
    atm_model = atm.get("model", "simple")

    # Band classification by center wavelength.
    if center == 0.0:
        band = "unknown"
    elif center < 1.0:
        band = "vis"
    elif center < 2.5:
        band = "nir"
    elif center < 3.0:
        band = "swir"
    elif center < 7.0:
        band = "mwir"
    else:
        band = "lwir"

    # Cell-reference nudge (informational; assembly-arm mapping is loose here).
    # Cell 28: terrestrial LWIR extended. Cell 58: space LWIR extended.
    name_lower = yaml_name.lower()
    if band == "lwir" and atm_model == "exo":
        cell_ref: str | None = "Cell 58"
        classification = "invariant"
    elif band == "lwir" and atm_model in ("simple", "modtran", "tabulated", "interpolated"):
        cell_ref = "Cell 28"
        classification = "invariant"
    elif band == "mwir":
        cell_ref = None
        classification = "expected_to_change_at_stage_6"
    elif band in ("vis", "nir", "swir"):
        cell_ref = None
        classification = "expected_to_change_at_stage_3"
    else:
        cell_ref = None
        classification = "unclassified"

    # Hint in the scenario name can override cell_ref.
    if "mwir_leo_minimal" in name_lower or "mwir_leo" in name_lower:
        # MWIR reflective+thermal mixed: remains classified by band rule above.
        pass
    if "mwir_ground_test" in name_lower:
        # Ground-test cell: MWIR band heuristic flags Stage-6 E_sky decomposition,
        # but this scenario is also a Stage-7 `no_atmosphere (ground_test)` sub-case.
        # Both stages will shift its values; classify it accordingly so reviewers
        # can attribute drift to the correct stage. (CU-004)
        classification = "expected_to_change_at_stage_6_and_stage_7"

    return classification, cell_ref


def _run_scenario(name: str, yaml_path: Path) -> ScenarioResult:
    """Execute the full chain on a single YAML and extract the metrics."""
    try:
        # Parse the YAML once (for band-based classification + grid sizing).
        with open(yaml_path, encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}

        bounds = _infer_band_bounds(cfg)
        if bounds is None:
            return ScenarioResult(
                name=name,
                status="error",
                error="YAML missing spectral_integration.filter_min_um/max_um",
                classification="unclassified",
                cell_ref=None,
                snr=None,
                nedt_K=None,
                mtf_at_nyquist=None,
                L_aperture_W_m2_sr_um=[None] * len(FIXED_GRID_UM),
            )

        lo, hi = bounds
        # 501 samples inside the band — matches the anchor tests.
        wl = np.linspace(lo, hi, 501)

        session = RadiantSession(wavelength_um=wl)
        params = session.default_params()
        load_config(yaml_path, params)
        params.resolve()

        result = session.run(params)

        # Extract metrics — each may be None for scenarios where the chain
        # does not produce the corresponding metric.
        snr = _finite_or_none(result.metrics.get("snr"))
        nedt = _finite_or_none(result.metrics.get("nedt_K"))
        mtf_ny = _finite_or_none(result.metrics.get("mtf_at_nyquist"))

        # L_aperture samples on the fixed grid — only those inside the band.
        L_samples: list[float | None] = []
        at_ap = result.frames.get("at_aperture")
        if at_ap is not None:
            L = np.asarray(at_ap.spectral_radiance, dtype=float)
            grid = np.asarray(result.wavelength_um, dtype=float)
            for lam in FIXED_GRID_UM:
                if lam < lo or lam > hi:
                    L_samples.append(None)
                else:
                    idx = int(np.argmin(np.abs(grid - lam)))
                    L_samples.append(_finite_or_none(L[idx]))
        else:
            L_samples = [None] * len(FIXED_GRID_UM)

        classification, cell_ref = _classify(cfg, name)

        return ScenarioResult(
            name=name,
            status="ok",
            error=None,
            classification=classification,
            cell_ref=cell_ref,
            snr=snr,
            nedt_K=nedt,
            mtf_at_nyquist=mtf_ny,
            L_aperture_W_m2_sr_um=L_samples,
        )
    except Exception as exc:  # noqa: BLE001 — per-scenario failure tolerated
        # Per task contract: failure entries must not crash the whole script.
        return ScenarioResult(
            name=name,
            status="error",
            error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
            classification="unclassified",
            cell_ref=None,
            snr=None,
            nedt_K=None,
            mtf_at_nyquist=None,
            L_aperture_W_m2_sr_um=[None] * len(FIXED_GRID_UM),
        )


def _result_to_yaml_dict(r: ScenarioResult) -> dict[str, Any]:
    return {
        "status": r.status,
        "error": r.error,
        "classification": r.classification,
        "cell_ref": r.cell_ref,
        "snr": r.snr,
        "nedt_K": r.nedt_K,
        "mtf_at_nyquist": r.mtf_at_nyquist,
        "L_aperture_W_m2_sr_um": r.L_aperture_W_m2_sr_um,
    }


def main() -> int:
    scenarios = _discover_yaml_scenarios()
    print(f"Discovered {len(scenarios)} YAML scenarios")

    scenario_entries: dict[str, dict[str, Any]] = {}
    ok_count = 0
    err_count = 0
    for name, path in scenarios:
        print(f"  Running {name} ...", end=" ", flush=True)
        r = _run_scenario(name, path)
        scenario_entries[name] = _result_to_yaml_dict(r)
        if r.status == "ok":
            ok_count += 1
            print(f"ok (class={r.classification}, cell={r.cell_ref})")
        else:
            err_count += 1
            short = (r.error or "").splitlines()[0] if r.error else ""
            print(f"ERROR: {short}")

    snapshot = {
        "schema_version": 1,
        "captured_at_sha": _git_sha(),
        "wavelength_grid_um": list(FIXED_GRID_UM),
        "scenarios": scenario_entries,
    }

    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SNAPSHOT_PATH, "w", encoding="utf-8") as fh:
        yaml.safe_dump(snapshot, fh, sort_keys=True, default_flow_style=False)

    print(
        f"\nWrote {SNAPSHOT_PATH.relative_to(REPO_ROOT)}: "
        f"{ok_count} ok, {err_count} error"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
