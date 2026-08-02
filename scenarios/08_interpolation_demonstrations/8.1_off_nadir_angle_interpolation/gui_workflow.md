# Scenario 8.1 — GUI Workflow Requirements

How an operator would use family interpolation in the GUI. (Per the
house rule that every scenario documents its GUI requirements. The GUI
is not yet built; this is a requirements capture.)

---

## Workflow in the GUI

1. **Enter a query geometry.** Off-nadir angle field; if it doesn't
   match an available MODTRAN run exactly, the GUI shows which family
   (if any) covers it and offers interpolation instead of silently
   picking the nearest point.
2. **Coverage indicator.** A small visual (like `fig1`) showing the
   query point relative to the family's covered range — in range
   (interpolate), out of range (refuse, suggest the nearest *available*
   family or the parametric fallback), or no matching family at all.
3. **A/B against nearest-neighbor**, exactly this scenario's
   comparison, available as a one-click "how much does interpolation
   matter here?" diagnostic — useful for an operator deciding whether
   it's worth the (small) extra complexity for a given query.

---

## MATLAB-like script/command window (standing GUI requirement)

```python
>>> from scripts.synth_modtran.family_interpolate import interpolate_family
>>> wl, tau, lp = interpolate_family("zenith_fan_us_standard", 37.5)
>>> tau[(wl >= 3.5) & (wl <= 5.0)].mean()
0.6952
```

Requirements this implies:
- **Family registry browsable from the window** (`FAMILIES` dict) so a
  user can discover what's interpolatable without reading source.
- **A single call that goes straight to a chain-ready tabulated-
  atmosphere config**, not just raw arrays — this scenario's script
  still hand-writes the CSV round-trip.

---

## GUI-specific gaps

- **No family auto-discovery.** Families are a hand-curated registry
  (deliberately, per the design rationale in `family_interpolate.py`)
  — the GUI would need the same registry, not a scan of the CSV.

## Interpolated-atmosphere availability

Switching **Atmosphere → Model** to `interpolated` works first try on this scene. The picker pre-selects **`us_standard_zenith_fan`** (profile `us_standard`, down-looking; covers ground targets only (target altitude fixed at 0 km), sensor at 100 km, LOS zenith 0-60 degrees); *Use this family* writes `atmosphere.interpolation_axes = 'path_zenith_rad'`. `Sensor.atmosphere_family_suggestion()` is the same answer from a script.
