# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for **RADIANT** — a first-principles EO sensor performance modeling framework.

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [0000](0000-template.md) | Template | — |
| [0001](0001-scope-and-constraints.md) | Scope and Top-Level Constraints | Accepted |
| [0002](0002-option-c-source-atmosphere-split.md) | Option C — Source/Atmosphere Split | Accepted |
| [0003](0003-t6-tabulated-at-source.md) | T6 Tabulated Radiance at Source | Proposed |
| [0004](0004-t7-intensity-at-source.md) | T7 Intensity at Source | Accepted |
| [0005](0005-extended-target-background-contrast.md) | Extended Target-vs-Background Contrast | Accepted |
| [0006](0006-geometry-stage.md) | Geometry Is Stage 0 of the Chain | Accepted |
| [0007](0007-3d-viewer-visual-direction.md) | 3D Geometry Viewer — Visual Direction and Scene-Library Lift | Proposed |
| [0008](0008-target-extent-to-geometry-and-scenario-type.md) | Target Spatial Extent Belongs to Geometry; Declared Scenario Type | Accepted |
| [ADR-A](ADR-A-fidelity-preset.md) | Drop FidelityPreset | Accepted |
| [ADR-B](ADR-B-metric-soft-fail.md) | Metric-Layer Soft Failures | Accepted |
| [ADR-C](ADR-C-public-api-surface.md) | Public API Surface | Accepted |
| [ADR-D](ADR-D-parameter-naming.md) | Parameter Naming | Accepted |

## Numbering scheme

Two ID schemes coexist for historical reasons: the numeric `000N-` series and the lettered `ADR-A…D` series (created by the 2026-04 architecture audit). **Both are frozen** — existing ADRs keep their IDs because they are cross-referenced throughout the specs. **New ADRs continue the numeric series from `0005-`** using `NNNN-<kebab-slug>.md` (see `docs/OPERATING_MODEL.md` §5).

## Process

- Each significant architecture decision gets its own numbered ADR
- ADRs are append-only — never edit an accepted ADR; supersede it with a new one
- Use [0000-template.md](0000-template.md) as the starting point for new ADRs
