# RADIANT Geometry Viewer — Implementation Handoff

> **Reference prototype:** `RADIANT Geometry Viewer.html` (open in any browser).
> The HTML prototype is the visual + interaction spec. This document explains the
> *intent* behind the design so the implementation team can make informed
> tradeoffs when porting to Python.

---

## 1. Purpose

The Geometry Viewer is one panel inside RADIANT — a spatial / spectral / radiometric
modeling tool for space-based remote sensing. This panel shows the **scenario
geometry** (relative positions and angles of sun, sensor, target) as an
**intentionally not-to-scale schematic**, optimized for understanding the angles
that drive radiometric calculations downstream.

It is **not** a flight visualizer or a Cesium-style globe. It is closer to a
CAD / engineering-drawing view: line-art forward, schematic, every element
labeled, every angle clickable.

---

## 2. Scope

### In scope (this panel)
- 3D schematic view with orbit / pan / zoom
- Sun, sensor, target glyphs
- Vectors:
  - Sun → target (always on)
  - Sensor → target (always on)
  - Sun → ground illumination point (only when target altitude > 0)
  - Sensor LOS extension from target → ground illumination point
- Click-to-reveal angle annotations:
  - **Target-frame:** θₛ, θᵥ, φₛ, φᵥ, Δφ, phase angle g (anchored at the target)
  - **Ground-frame:** θₛ_g, θᵥ_g, φₛ_g, φᵥ_g (anchored at the ground illumination
    point G_i — the radiometrically-relevant location when target altitude > 0)
- Target shape library: extended scene, plate, box, sphere, cylinder, cone,
  circle, ellipsoid, point source, custom mesh placeholder
- Target body-frame RPY (roll/pitch/yaw) with on-target triad gizmo for 3D shapes
- Right-side accordion side panel:
  - Live numeric readout of all angles
  - Sun position editor (date/time/lat/lon OR direct angles)
  - Sensor position editor (altitude, az/el OR ECI/orbit)
  - Target editor (shape, dimensions, altitude, lat/lon)
- Tweaks for visual variants (sensor glyph style, ground style, color theme)

### Out of scope (other panels / later phases)
- Real radiometric calculations (BRDF, atmospheric RT) — separate module
- Earth curvature toggle, view presets, hidden-line treatment, ruler ticks on
  vectors — phase 2 polish
- Real satellite mesh rendering — schematic on purpose
- Time-stepped orbit animation

---

## 3. Files in this prototype

| File | Role |
|---|---|
| `RADIANT Geometry Viewer.html` | Entry point. Loads React + Babel + the JSX modules. |
| `app.jsx` | Workspace chrome (left rail, dock tabs, status bar), state, side panel accordions. |
| `scene.jsx` | The 3D schematic — projection, vectors, angle arc rendering, click selection. |
| `shapes.jsx` | All target shape generators (vertices + edges per shape). |
| `geometry.js` | Pure math: `dirFromAzZen`, `computeAngles`, vector ops, RPY rotations. |
| `tweaks-panel.jsx` | Tweaks panel host (visual variant toggles). |

The math in `geometry.js` is the **canonical reference** for angle conventions.
Port it as-is.

---

## 4. Critical math conventions (already implemented)

- **Coordinate frame:** local tangent plane at the target nadir.
  +X = East, +Y = North, +Z = Up (zenith).
- **Azimuth:** measured clockwise from +Y (North), in degrees.
- **Zenith angle:** measured from +Z, in degrees.
- **Sun direction:** unit vector pointing *from target toward the sun*
  (collimated — parallel rays assumption).
- **Sensor direction:** unit vector pointing *from target toward the sensor*.
- **Phase angle g:** angle between sun direction and sensor direction (3D, not
  projected).
- **Ground illumination point G_i:** intersection of the sensor→target ray
  extended to z = 0. When target altitude is 0, G_i = target nadir = origin.
- **Target RPY:** intrinsic Tait-Bryan ZYX (yaw, then pitch, then roll), pivot
  at body geometric center.
- **Ground-frame angles when target altitude > 0:** numerically equal to
  target-frame angles for the sun (parallel rays). They are still drawn at G_i
  separately because they are conceptually different inputs to the radiometric
  kernels and the visual separation matters to the user.

---

## 5. Recommended Python stack

The prototype is platform-agnostic SVG. Any of:

- **PySide6 / PyQt6 + pyvista (VTK):** best for real 3D, GPU-accelerated.
  Recommended if performance matters.
- **PySide6 + Qt3D / QtQuick3D:** native Qt, no extra deps, slightly more code.
- **Dear PyGui:** lightest weight, but limited 3D primitives.
- **Web-based (Plotly Dash / Three.js via Pyodide):** if RADIANT itself is going
  web-based later.

Whatever you pick, **keep the schematic aesthetic** — line-art, no realistic
shading, intentional non-to-scale. Resist the urge to apply PBR materials.

---

## 6. Interaction model (port these exactly)

- **Orbit / pan / zoom:** standard mouse drag / shift-drag / wheel.
- **Click vector → reveal angles:** the clicked vector becomes "selected"
  (single selection). The corresponding angle arcs and labels appear. Clicking
  empty space deselects.
- **Click target body (3D shapes only) → reveal RPY triad:** the body-frame
  X′/Y′/Z′ axes appear at the target center, color-coded
  (pink=Roll, green=Pitch, purple=Yaw). The right panel auto-switches to the
  RPY accordion.
- **Click sun→ground vector or sensor LOS extension → ground-frame mini frame:**
  a faded mini Z′/N triad appears at G_i with θ and φ arcs in the corresponding
  vector color, plus an "incident" or "emergent" annotation.
- **Editing values in the side panel:** all angle readouts update live as you
  drag inputs. The 3D scene reflects changes immediately.

---

## 7. Visual conventions (port these exactly)

- **Color roles:** sun = amber, sensor = cyan, phase/azimuth = magenta,
  zenith = neutral, ground/projection = faded amber/cyan.
- **Stroke weights:** main vectors ≈ 1.6 px; arcs ≈ 0.9 px dashed; reference
  axes ≈ 0.7 px dashed.
- **Label boxes:** monospace 10 px, background-fill rectangle with a thin
  stroke in the same color as the arc.
- **The grid is a reference, not a measurement.** Use a faint two-tone grid
  on the ground plane.

---

## 8. Phase 2 polish (deferred)

In rough impact order, plan to add later:
1. Painter's-algorithm depth ordering so vectors don't punch through solids.
2. Hidden-line treatment (faded/dashed for occluded segments).
3. Curved-Earth toggle.
4. Ruler ticks along vectors (sense of distance without being to scale).
5. Hover-preview of angles before clicking.
6. View presets (top-down, principal-plane, iso, behind-sensor).
7. Mini compass / sun rose inset for orientation.
8. Persistent radiometric callout (always-on θₛ_g, θᵥ_g, Δφ, g card).

---

## 9. Suggested Claude Code prompt

When starting the implementation, paste this into Claude Code:

> I'm porting the geometry viewer panel of RADIANT (a remote-sensing modeling
> tool) from an HTML prototype to Python. The prototype is in
> `prototype/RADIANT Geometry Viewer.html` — open it in a browser; it is the
> visual and interaction spec. The handoff document
> `prototype/RADIANT_GEOMETRY_HANDOFF.md` explains scope, math conventions,
> and visual conventions.
>
> Target stack: **[fill in: PySide6 + pyvista, etc.]**
>
> Start by reading `prototype/geometry.js` and porting the math module
> (`dirFromAzZen`, `computeAngles`, RPY rotation, ground-illumination-point
> intersection) to `radiant/geometry/scene_math.py` with full type hints and
> docstrings citing the conventions in the handoff.
>
> Then scaffold the panel widget, dockable inside the existing RADIANT main
> window, with the right-side accordion side panel and an empty 3D viewport.
>
> Then implement the schematic 3D rendering: ground plane, axes, sun/sensor/
> target glyphs, vectors. Match the prototype's color palette and stroke
> conventions exactly.
>
> Then implement click selection and angle annotations (target-frame first,
> then ground-frame).
>
> Then implement the shape library and target RPY.
>
> Verify each step against the prototype before moving on.

---

## 10. Open questions for the team

- Final Python GUI stack decision?
- How does this panel get the live scenario state from the rest of RADIANT —
  shared model object, signals/slots, observable store?
- Coordinate frame in the rest of RADIANT — does it match the local-tangent
  ENU convention used here, or does it use ECEF / ECI? The math module should
  expose conversions if so.
- Target altitude — is "altitude above WGS84 ellipsoid" the convention, or
  altitude above local terrain DEM?
