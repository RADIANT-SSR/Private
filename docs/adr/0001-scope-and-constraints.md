# ADR-0001: RADIANT Scope and Top-Level Constraints

**Date:** 2026-04-06  
**Status:** Accepted

## Context

Before architecture can be defined, the scope of physics, use cases, and integration requirements must be bounded. This ADR captures the top-level framing decisions made during initial scoping.

## Decision

RADIANT is a first-principles radiometric, spectral, and spatial performance modeling framework with the following scope:

### Use Cases (v1)
- **Primary:** Sensor design trades and performance prediction
- **Not in scope:** Image quality assessment of collected imagery, active sensors (LIDAR, SAR)

### Spectral Coverage
- Full UV through LWIR
- Single spectral band in v1; architecture must not preclude multispectral/hyperspectral extension
- **Implication:** Radiometric chain must handle three distinct source regimes:
  - UV/VIS/SWIR: reflected solar dominant
  - MWIR (~3–5 µm): mixed thermal emission + reflected solar (both must be modeled)
  - LWIR: Planck thermal emission dominant
  - The MWIR crossover regime requires simultaneous treatment of both source terms — this is not optional

### Observer/Target Geometry
- Observers may be space-based, airborne, or ground-based
- Targets may be space-based, airborne, or ground-based
- All geometry combinations must be supported — 9 total pairings
- Slant range, look angle, and atmospheric path length must be computed correctly for each combination

### Atmospheric Model
- Full spectral atmosphere: transmittance + path radiance + thermal emission from atmosphere
- Tool must accept inputs ranging from simple (single bulk transmittance) to complex (full spectral MODTRAN output)
- Simple atmospheres are a degenerate case of the full model — NOT a separate code path
- MODTRAN output ingestion is a v1 requirement; interface format TBD

### Image Quality Metrics
- NIIRS is a hard requirement — both regimes:
  - EO-NIIRS via GIQE (4.0 and/or 5.0) for VIS/SWIR
  - IIRS (Infrared Interpretability Rating Scale) for MWIR/LWIR
- Additional metrics: SNR, NEDT, MTF, detection range
- Metrics are computed from the full physics chain — not empirically fitted

### Spatial Model
- Both geometric optics and wave optics required
- Tool auto-selects appropriate regime based on f/# and wavelength; user override allowed
- Optics detail (aberrations, WFE, Zernike decomposition) deferred to a subsequent ADR

### Polarization
- Not in scope for v1

### Users
- Primary users are analysts running design trade studies
- API must support interactive use; GUI is not a v1 requirement
- Architecture must not prohibit future pipeline/automated use

### Integration
- MODTRAN output ingestion required in v1
- No other specific tool integrations required in v1
- Architecture must not prohibit future integration with other tools (DIRSIG, etc.)

## Rationale

These decisions establish the physics fidelity floor and the key architectural branch points before any implementation choices are made. Flexibility (spectral range, geometry, atmosphere complexity) is a primary design goal and must be reflected in the core data model — it cannot be bolted on later.

## Consequences

- **Positive:** Scope is explicit; deferred items are identified, not forgotten
- **Negative:** UV-to-LWIR coverage with correct MWIR crossover treatment adds significant complexity to the source and atmosphere models
- **Neutral:** Single-band v1 simplifies spectral integration loops but the spectral axis must still be a first-class dimension in the data model

## References

- GIQE 4.0 / GIQE 5.0 (NGA)
- IIRS (Infrared Interpretability Rating Scale)
- MODTRAN (Spectral Sciences Inc. / Air Force Research Laboratory)
