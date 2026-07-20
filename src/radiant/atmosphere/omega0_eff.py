"""MODTRAN-derived effective single-scattering albedo ω₀_eff(λ, aerosol).

Gap 38: the closed-form diffuse-sky irradiance

    E_sky_scattered(λ) = E_TOA(λ) · cos(θ_s) · ω₀ · (1 − τ_down,vert(λ))

needs an ω₀ with aerosol and spectral fidelity. The extinction-weighted
column ω₀ the simple model derives internally evaluates ≈ 1.000 for
space-sensor columns (only pure-scattering molecules survive at the
column mean altitude), over-predicting diffuse sky irradiance ~1.3×
(VIS, rural) to ~5× (SWIR), worst for urban aerosol.

The table below is the *empirically effective* ω₀: the value that makes
the closed form above reproduce the real MODTRAN 6 ground-level diffuse
flux, obtained by inverting the formula against the delivered flux
tables (E1/E3/E4 ``*_flux.csv`` DOWN column) with τ from the matching
transmittance runs (A1/D2/D3), band-median per aerosol regime. Because
it is fit through the single-scatter closed form, it absorbs the
multiple-scatter contribution MODTRAN includes — it is an effective
parameter of THIS formula, not a microphysical aerosol property.

Provenance: derived 2026-07-17 from the real MODTRAN 6 run set;
independently pinned (with a re-derivation guard against the staged
flux files) in ``tests/integration/test_modtran_real_runs.py``
(``OMEGA0_EFF``). The two tables must stay equal; a Level-0 test
asserts it.

Spectral form: piecewise-constant over the three reference bands —
VIS 0.4–0.7 µm, NIR 0.7–1.4 µm, SWIR 1.4–2.5 µm — with edge extension
(λ < 0.4 µm takes the VIS value; λ > 2.5 µm the SWIR value, where
scattered solar is radiometrically negligible anyway). Band-median
fitting supports no finer spectral claim; the steps at 0.7/1.4 µm are
a documented fragility, not physics.
"""

from __future__ import annotations

import numpy as np

from radiant.atmosphere.errors import AtmosphereValidationError

# aerosol -> (VIS, NIR, SWIR) band-median effective ω₀ [dimensionless].
# Bands: VIS 0.4–0.7 µm, NIR 0.7–1.4 µm, SWIR 1.4–2.5 µm.
OMEGA0_EFF_TABLE: dict[str, tuple[float, float, float]] = {
    "rural": (0.791, 0.698, 0.187),
    "maritime": (0.835, 0.758, 0.339),
    "urban": (0.423, 0.430, 0.263),
}

# Band edges [µm]: VIS below _VIS_NIR_EDGE_UM, NIR up to _NIR_SWIR_EDGE_UM,
# SWIR above (edge-extended beyond 2.5 µm).
_VIS_NIR_EDGE_UM: float = 0.7
_NIR_SWIR_EDGE_UM: float = 1.4


def omega0_eff(wavelength_um: np.ndarray, aerosol_type: str) -> np.ndarray:
    """Effective single-scattering albedo ω₀_eff(λ) for the diffuse-sky formula.

    Parameters
    ----------
    wavelength_um:
        Wavelength grid [µm].
    aerosol_type:
        One of ``rural``, ``maritime``, ``urban``.

    Returns
    -------
    ω₀_eff on the input grid [dimensionless, 0–1]: piecewise-constant
    band-median values (VIS/NIR/SWIR), edge-extended outside 0.4–2.5 µm.
    """
    if aerosol_type not in OMEGA0_EFF_TABLE:
        raise AtmosphereValidationError(
            f"omega0_eff: unknown aerosol_type '{aerosol_type}'. The "
            f"MODTRAN-derived ω₀_eff table covers {sorted(OMEGA0_EFF_TABLE)} "
            "(Gap 38). Set atmosphere.aerosol_type to one of these."
        )
    vis, nir, swir = OMEGA0_EFF_TABLE[aerosol_type]
    lam = np.asarray(wavelength_um, dtype=np.float64)
    return np.where(
        lam < _VIS_NIR_EDGE_UM,
        vis,
        np.where(lam < _NIR_SWIR_EDGE_UM, nir, swir),
    )
