# RADIANT — Scenario Testing Instructions

This document defines how to build, execute, and validate RADIANT
scenarios. Every agent working on scenarios must follow these rules.

---

## What Is a Scenario?

A scenario is a persona-driven test case that exercises RADIANT the way
a real user would. Each scenario:

- Is owned by a **persona** (Sarah, Mike, Raj, Lisa, Tom, Dr. Chen, Karen)
- Poses a **specific engineering question** the persona needs answered
- Uses **realistic inputs** in vendor/user-native formats (not RADIANT-
  internal format)
- Runs the **full RADIANT signal chain** via Python scripts
- Produces **quantitative results** with units on every number
- Documents **gaps** — anything RADIANT can't do natively that the
  scenario needs

Scenarios are NOT unit tests. They are end-to-end acceptance tests that
prove RADIANT works for real use cases.

---

## Folder Structure

Every scenario lives under `scenarios/<persona>/<scenario>/` and must
contain:

```
scenarios/
  <NN>_<persona_name>/
    <N.M>_<scenario_slug>/
      inputs/          # Vendor-format data: Excel, CSV, YAML, vendor specs
      scripts/         # Python scripts that run the scenario
      outputs/         # Generated results: Excel, PNG plots, reports
      walkthrough.md   # Narrative explanation of the scenario and physics
      gui_workflow.md  # How this would work in a future GUI
      gaps.md          # (if any) Per-scenario gap log
```

### Naming Convention

- Persona folders: `NN_firstname_role` (e.g., `01_sarah_systems_engineer`)
- Scenario folders: `N.M_short_description` (e.g., `1.4_tdi_pushbroom_optimization`)
- Script files: `run_<description>.py` for main scripts,
  `create_spreadsheet.py` for input generators

---

## Rules for Building Scenarios

### Rule 1: Inputs Are NOT in RADIANT Format

Do not assume inputs arrive in RADIANT-compliant format. Use the formats
a real user would have:

- Vendor datasheets (Excel with vendor units: mm, %, km, ms)
- Lab measurements (CSV with column headers in native units)
- Design tool exports (Zemax, Code V conventions)
- Mission planning spreadsheets

The script converts from vendor units to RADIANT canonical units:
- Wavelength: **µm**
- Angles: **radians**
- Length: **meters**
- Time: **seconds**
- Radiance: **W/m²/sr/µm**

Every conversion must be explicit in the script with a comment:

```python
# Convert vendor units → RADIANT canonical
aperture_m = row["Entrance Pupil Diameter [mm]"] / 1000  # mm → m
qe = row["QE [%]"] / 100                                 # % → fraction
t_int_s = row["Integration Time [ms]"] / 1000            # ms → s
altitude_m = row["Orbit Altitude [km]"] * 1000            # km → m
```

### Rule 2: Every Numerical Output Must Have Units

**HARD RULE.** Every number printed, tabled, or plotted must include
its unit. No exceptions.

```python
# CORRECT:
print(f"SNR: {snr:.1f}")                          # SNR is dimensionless — OK
print(f"GSD: {gsd_m:.2f} m")                       # unit attached
print(f"NEDT: {nedt_K * 1000:.1f} mK")             # converted and labeled
print(f"Transmission: {tau:.4f} (band-mean)")       # dimensionless with context

# WRONG:
print(f"GSD: {gsd_m:.2f}")          # no unit
print(f"Temperature: {temp}")        # no unit, no format
```

Plot axes must include units in labels:

```python
ax.set_xlabel("Pixel Pitch [µm]")
ax.set_ylabel("SNR [dimensionless]")
ax.set_ylabel("NEDT [mK]")
```

### Rule 3: Scripts Must Explain the Physics

The script output should help the user understand what RADIANT is doing
and why the results make physical sense. Include:

1. **Regime identification**: What radiometric regime is active and why
   (extended scene, point source, sub-pixel)?
2. **Unused parameters**: If a parameter doesn't affect the result,
   explain why (e.g., "Background temperature does not enter extended-
   scene SNR — only contrast SNR uses it")
3. **Non-obvious physics**: When results are counterintuitive, explain
   the mechanism (e.g., "SNR increases with off-nadir angle because
   path radiance adds more photons than transmission loss removes")
4. **Validation cross-checks**: Compare RADIANT results against hand
   calculations or analytical formulas where possible

### Rule 4: Write a walkthrough.md After Finishing

After the scenario scripts run and produce results, create
`walkthrough.md` in the scenario root. This is a narrative document
that:

1. **States the problem**: What does the persona need to know?
2. **Describes the system**: Sensor configuration table with all
   parameters, values, units, and notes
3. **Explains the approach**: How RADIANT is used to answer the question
   — which parameters are swept, what chain stages are involved
4. **Shows key results**: Tables and figures with full context.
   Reference the output files in `outputs/`
5. **Discusses the physics**: Why do the results look the way they do?
   What drives the trends? Where are the crossover points?
6. **Identifies gaps**: What couldn't RADIANT do natively? What required
   workarounds?
7. **States what the persona would do next**: What follow-on analyses
   would they want?

**Reference format**: See
`scenarios/02_mike_detector_engineer/2.3_ipc_impact_on_mtf/walkthrough.md`

### Rule 5: Write a gui_workflow.md for Every Scenario

**HARD RULE.** Every completed scenario must include `gui_workflow.md`.
This documents how the same analysis would work in a future GUI.

Structure:

1. **Persona context**: One sentence on who and what they need
2. **Numbered steps**: Import → Configure → Run → Visualize → Analyze → Export
3. **Per step**: Action (menu path), GUI components (what user sees/clicks),
   unit conversion highlights
4. **Interactive features**: Hover tooltips, draggable thresholds,
   click-to-drill-down, linked views
5. **Script window commands**: Python commands that replicate each GUI
   action (for power users who prefer scripting)
6. **GUI requirements table**: What the GUI must support, with priority
   and gap references

**Reference format**: See
`scenarios/05_tom_optical_designer/5.2_pixel_pitch_optimization/gui_workflow.md`

### Rule 6: Log Gaps in TWO Places

Any issue, gap, or blocker discovered during scenario development goes in:

1. **Per-scenario `gaps.md`**: In the scenario folder, with description,
   severity, and workaround
2. **Master `docs/tracking/gaps.md`**: The canonical gap registry, using the
   structured table format:

```markdown
## Gap N: <Short title>

| Field | Value |
|-------|-------|
| **Found in** | Scenario X.Y (Persona — description) |
| **Status** | OPEN / WORKAROUND / FIXED |
| **Description** | What the gap is and why it matters |
| **Workaround** | How the scenario script works around it (if any) |
| **Impact** | Which metrics or results are affected |
| **Fix location** | Which module/file needs to change |
| **Effort** | Estimated scope (small / medium / large) |
| **Scenarios blocked** | List of other scenarios affected |
| **Rerun after fix** | Which scenario to rerun to verify the fix |
```

---

## Scenario Execution Order

Scenarios are tiered by the number of code changes needed. Work through
them in order — earlier scenarios build capabilities that unlock later
ones. See `docs/guides/scenario_catalog.md` for the full priority table.

| Tier | Description | Code Changes |
|------|-------------|-------------|
| 1 | Executable today with scripting only | None |
| 2 | Need 1-2 metric additions | `performance/` only |
| 3 | Need input parsers / format converters | `io/` only |
| 4 | Need signal chain enhancements | Physics stages |

---

## Running a Scenario

### First-Time Setup

```bash
# From the repo root:
pip install -e ".[dev]"
```

### Execute a Scenario Script

```bash
cd scenarios/<persona>/<scenario>
python scripts/run_<description>.py
```

Scripts should:
- Print progress to stdout with section headers
- Write results to `outputs/` (Excel, PNG, CSV)
- Print a summary table at the end
- Exit cleanly (no interactive prompts)

### Verify Results

After running, check:
1. Output files exist in `outputs/`
2. Numbers have units (in script output, plots, and tables)
3. Physics makes sense (monotonicity, scaling laws, conservation)
4. Compare against walkthrough.md reference tables if they exist

---

## Batch Scenario Regression Testing

At every development checkpoint (end of Phase 3A, 3B, 3C, etc.),
run ALL scenario scripts as a regression gate:

```bash
# Run all scenarios and check for errors
for script in scenarios/*/scripts/run_*.py; do
    echo "=== Running: $script ==="
    python "$script" || echo "FAILED: $script"
done
```

Compare results against previous outputs:
- Nadir cases should be unchanged when new features default to zero
- Off-nadir, smear, Zernike results should only change when those
  features are explicitly configured
- Any unexpected change must be documented with an explanation

---

## Scenario Completion Checklist

Before declaring a scenario complete, verify:

- [ ] `inputs/` contains vendor-format data (not RADIANT-internal)
- [ ] `scripts/` contain runnable Python scripts
- [ ] `outputs/` contain generated results (Excel, plots)
- [ ] Script prints units on every numerical output
- [ ] Script explains regime, unused params, and non-obvious physics
- [ ] `walkthrough.md` exists with full narrative
- [ ] `gui_workflow.md` exists with step-by-step GUI workflow
- [ ] Gaps (if any) logged in per-scenario `gaps.md` AND `docs/tracking/gaps.md`
- [ ] Script runs cleanly from a fresh checkout (no hardcoded paths)
- [ ] Results are physically reasonable (sanity-checked)

---

## Reference Scenarios

These are the gold-standard examples for scenario format:

| Document | Reference |
|----------|-----------|
| Walkthrough | `scenarios/02_mike_detector_engineer/2.3_ipc_impact_on_mtf/walkthrough.md` |
| GUI workflow | `scenarios/05_tom_optical_designer/5.2_pixel_pitch_optimization/gui_workflow.md` |
| Per-scenario gaps | `scenarios/02_mike_detector_engineer/2.3_ipc_impact_on_mtf/gaps.md` |
| Master gap registry | `docs/tracking/gaps.md` |
| Scenario descriptions | `docs/guides/scenario_catalog.md` |
| Off-nadir walkthrough | `scenarios/03_raj_mission_planner/3.4_off_nadir_agility/walkthrough.md` |
