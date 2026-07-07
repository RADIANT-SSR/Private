# Changelog

All notable changes to RADIANT are recorded here, per CLAUDE.md Rule 29.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Newest entries
at the top of `[Unreleased]`; on release, `[Unreleased]` rolls into a dated
version heading. Categories: **Added** / **Changed** / **Deprecated** /
**Removed** / **Fixed**. Entries that change computed numbers (physics models,
parameter defaults, golden baselines) are prefixed **Results-affecting:** and
state the direction and rough magnitude of the change.

What gets an entry (Rule 29): changes to computed results, public API surface
(methods, parameters, metrics, error classes, config fields), and capability
additions or removals. What does not: refactors, doc-only, test-only, and
internal changes with no observable effect.

This changelog begins 2026-07-07. Earlier history lives in `git log`,
`docs/tracking/gaps.md`, and `docs/tracking/Cleanup_Backlog.md` and is not
retroactively reconstructed.

## [Unreleased]

### Added
- `optics.scalar_emissivity` parameter (default 0.0): declared effective
  emissivity of the lumped train in scalar transmission mode, enabling
  warm-optics nearfield emission from the simplest input mode (Gap 37).
  **Results-affecting only when set nonzero** — it adds nearfield background
  and shot noise (lower SNR, higher NEDT) for warm-optics MWIR/LWIR
  configurations; the default preserves all existing results (`ε = 0`,
  nearfield dark). `OpticalElement` gains a `declared_emissivity` field,
  legal only on `kind=LUMPED` pseudo-elements; `KirchhoffViolationError`
  on physical surfaces or when `ε + τ + R > 1`.
