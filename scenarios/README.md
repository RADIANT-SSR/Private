# RADIANT Scenarios

Persona-driven test cases for exercising the RADIANT tool. Each folder
corresponds to a persona archetype; each subfolder is a self-contained
scenario with its own inputs, scripts, and outputs.

See `docs/expanded_scenarios.md` for full scenario descriptions and
recommended execution order.

## Folder Structure

```
scenarios/
  <persona>/
    <scenario>/
      inputs/     # YAML configs, CSV data, vendor specs
      scripts/    # Python scripts to run the scenario
      outputs/    # Results, plots, reports
      README.md   # Scenario description and instructions
```

## Personas

| Folder | Persona | Role |
|--------|---------|------|
| sarah_systems_engineer | Sarah | Systems engineer running trade studies |
| mike_detector_engineer | Mike | Detector engineer evaluating FPA options |
| raj_mission_planner | Raj | Mission planner optimizing orbits and coverage |
| lisa_analyst | Lisa | Intelligence analyst assessing detection capability |
| tom_optical_designer | Tom | Optical designer optimizing PSF and MTF |
| dr_chen_researcher | Dr. Chen | Researcher validating models against theory |
| karen_test_engineer | Karen | Test engineer reconciling predictions with measurements |

## Execution Order

Start with Tier 1 (no code changes needed), then progress through Tiers 2-4.
See `docs/expanded_scenarios.md` for the full priority table.
