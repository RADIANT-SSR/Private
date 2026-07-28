# Scenario 10.4 — gaps encountered

Scenario: `scenarios/10_direction_general/10.4_leo_to_geo_exo`
Scene class: `space_to_space`, LOS direction `up` (LEO 500 km → GEO 35 786 km)
Recorded: 2026-07-28, branch `gf5/leo-to-geo`

The ADR-0011 direction-general geometry itself hit **no** gaps: the scene
resolves, the vacuum identities are exact, the horizon guard correctly stays
silent, the scene-class relevance map turns off exactly the right metrics, and
the Rule-4 dual-path consistency check passes with 86× margin. Everything below
is orthogonal to the geometry work.

Registry mirroring: these three items are reported to the orchestrator for
mirroring into `docs/tracking/gaps.md` (Gap numbers are minted there, not here —
Rule 25, one registry per concern). This file is the per-scenario record.

---

## G10.4-1 — Detection-range solver freezes total noise at the reference range

| Field | Value |
|---|---|
| **Found in** | Scenario 10.4 (Raj/SDA — LEO → GEO point-source detection range) |
| **Status** | WORKAROUND (quantified in the scenario; no code change made) |
| **Severity** | Medium — biases a shipped headline metric |
| **Description** | `performance/detection_path_aware.py` and `detection_beer_lambert.py` both take `noise_e` as a **scalar** frozen at the reference range, so the solved SNR-vs-range function is `S(R)/σ_ref`. Physically the target's own shot noise falls as the target dims, so `σ²(R) = S(R) + N₀²`. The frozen-noise model therefore under-reports the detection range wherever signal shot noise is a significant share of the noise power. |
| **Quantified here** | Signal shot noise is **51 %** of the noise power at the reference range. RADIANT reports `detection_range_m` = 78 138.9 km; the shot-noise-consistent closed form gives 90 015.3 km — RADIANT is **15.2 % conservative**. |
| **Not caused by this scenario's geometry** | The same scalar-noise contract is used by the down-looking Beer-Lambert arm, so every shipped point-source scenario carries the same bias. This scenario merely made it visible because the vacuum path removes every other confound. |
| **Workaround** | The runner prints both closed forms side by side (cross-check 4) and states which model RADIANT used, so the reported number is never mistaken for the shot-noise-consistent one. No code was changed. |
| **Impact** | `detection_range_m` only. SNR, NEDT, MTF, EE and every geometry output are unaffected. |
| **Fix location** | `src/radiant/performance/detection_generic.py` (callback contract), `detection_path_aware.py`, `detection_beer_lambert.py` — the noise argument would become a callable of range, or split into `signal_shot_scaling` + `fixed_noise_e²`. |
| **Effort** | Small–medium. The bisection is unchanged; the change is the SNR-vs-range closure plus a golden-baseline review (it *moves* every existing `detection_range_m` golden, so it is an owner decision, not an inline fix). |
| **Scenarios affected** | Every point-source scenario reporting `detection_range_m` (1.1, 4.1, 10.4, …). |
| **Rerun after fix** | 10.4 — cross-check 4(b) should then agree to solver tolerance instead of +15.2 %. |

---

## G10.4-2 — No inertial-velocity door for the sensor endpoint; the LOS rate uses ground-track speed

| Field | Value |
|---|---|
| **Found in** | Scenario 10.4 (LEO → GEO relative kinematics, Gap 111 doors) |
| **Status** | WORKAROUND |
| **Severity** | Medium for space targets; none for ground targets |
| **Description** | `radiant.geometry.los_rate` models the sensor's velocity as `v_g ê_⊥` where `v_g` is `geometry.ground_speed_m_s` — documented and derived (V6 `circular_orbit`) as the **sub-satellite ground-track** speed `v·R_E/a`. That is the correct scaling for the LOS rate to a *ground* target, where the off-boresight angle changes at `v_g/h`. For a **space** target the LOS rate depends on the platform's **inertial** velocity, and additionally on the target's own orbital motion, neither of which the platform-only (K0) path can express. |
| **Quantified here** | Setting `geometry.circular_orbit = True` on this scene (the framework's own platform-kinematics door) publishes `los_angular_rate_rad_s` = **200.1 µrad/s** against the correct **128.7 µrad/s** — **+55.5 %**. Two causes compound: ground-track speed 7 062.3 m/s is used where the inertial 7 616.6 m/s belongs, and the GEO target's own 3 074.9 m/s co-rotating motion (which *subtracts*) is absent. |
| **Workaround** | The scenario never uses `circular_orbit`. It computes both inertial speeds with `radiant.core.orbit.orbital_velocity_m_s`, enters the LEO inertial speed through `geometry.ground_speed_m_s` and the GEO inertial speed through the K2 triple (`target_speed_m_s`, `target_heading_rad = π/2`, `target_climb_rad = 0`), and cross-checks the result against the K1 direct-rate door. Both doors agree to 0.000e+00 %. |
| **Impact** | `los_angular_rate_rad_s`, and through it `platform.smear_width_m`, the smear MTF, EE_box, SNR and detection range — for **space-target scenes only**. Ground-target scenes are unaffected (the ground-track speed is the right quantity there). |
| **Fix location** | `src/radiant/geometry/_schema.py` (a sensor-velocity door distinct from ground-track speed), `src/radiant/geometry/modes.py::resolve_kinematics` / `resolve_los_rate`, `src/radiant/geometry/los_rate.py` (module docstring simplification 2 states the ground-track choice explicitly and is where the alternative belongs). |
| **Effort** | Medium — a new mode-entry parameter plus provenance-resolved agreement checking, in the ADR-0006 rule-2 pattern already used by K1/K2. |
| **Scenarios affected** | Any future `*_to_space` or `*_to_air` scene whose target moves. |
| **Rerun after fix** | 10.4 — `circular_orbit = True` should then publish 128.7 µrad/s directly, and the K1/K2 workaround becomes optional. |

---

## G10.4-3 — K2 heading frame is azimuthally degenerate for a radial line of sight (documentation)

| Field | Value |
|---|---|
| **Found in** | Scenario 10.4 (vertical up-look, θ_o = π exactly) |
| **Status** | OPEN — documentation only, no numerical consequence |
| **Severity** | Low |
| **Description** | `geometry.target_heading_rad` is measured in the target's local horizontal plane **from the azimuth of the sensor's ground point**. For a radial LOS (θ_o = 0 or π) the ground range is 0 m, so that azimuth reference does not exist. A user setting up a co-rotating LEO/GEO pair has no documented guidance for which heading to enter. |
| **Why it is harmless numerically** | The rate is ω = \|v_rel × û\| / R, which at θ_o = π reduces to `hypot(v_perp, v_par)/R` — invariant under rotation about the vertical. The scenario verified this: K2 with heading π/2 reproduces the hand kinematics exactly. |
| **Workaround** | The runner states the degeneracy and its harmlessness in its own output (section 8) and in `walkthrough.md` §5, and cross-checks K2 against the K1 direct-rate door. |
| **Impact** | User comprehension only. |
| **Fix location** | `src/radiant/geometry/los_rate.py` module docstring and the `TARGET_HEADING_RAD` `ParameterDef` description in `src/radiant/geometry/_schema.py` — one sentence naming the degenerate case and stating that any heading gives the same rate there. |
| **Effort** | Trivial (doc-only, Rule 20 lock-step with the parameter-reference regeneration). |
| **Scenarios affected** | Any radial-LOS scene with a moving target. |
| **Rerun after fix** | None required. |

---

## Explicitly NOT gaps (checked and clean)

- **Altitude ordering / extended θ_o domain** — `h_sensor < h_target` and
  θ_o = π are accepted and exact. This is the Phase-1 deliverable working.
- **Horizon guard** — correctly silent across the whole ζ_low sweep (0–60°):
  θ_o never approaches π/2 and the ray never grazes the limb.
- **Scene-class assertion** — `geometry.scene_class = "space_to_space"` is
  validated against the derivation and agrees; no false positive.
- **Scene-class metric relevance (G3)** — all ten ground-projection metrics are
  absent from `result.metrics`; the target-plane counterparts are present.
- **LOS-termination background** — `ColdSpaceBackground` with identically zero
  radiance, correctly selected without any scene-class branch.
- **Rule-4 dual-path consistency** — passed on both axes with 86× margin, and
  the nominal *and* heavily-smeared open-loop runs each raised zero
  `UserWarning`s.
- **Detection-range non-detection reporting** — short integration times report a
  result-typed failure with a `failure_reason`, not a silent NaN. Rule 17
  carve-out behaving as specified.
