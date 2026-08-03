"""Height-resolved effective emission temperature of a path segment (CU-321).

One computation, one module (Rule 19): the single temperature ``T_eff(λ)``
that makes the one-slab Kirchhoff form ``(1 − τ)·B(λ, T_eff)`` reproduce the
**layered formal solution** of a segment whose air is not isothermal.

Why a single temperature is not enough
--------------------------------------
Until CU-321 every segment emitted at one temperature — the profile
temperature at its lower endpoint (CU-155).  That is exact for a level arm
and harmless for a few-km column, but it is badly wrong for a tall one,
because it is wrong in a *spectrally* structured way: an opaque channel of a
10 km column emits from wherever its own optical depth reaches unity as seen
from the observer, and a transparent channel emits from the whole column
weighted by absorber density.  Measured against the batch-2 MODTRAN pairs,
the one-temperature form over-stated the down-looking 3–5 µm path thermal by
2.0–2.4× on the tall columns (O3/O4/O5) while the same air read up-looking
sat at 1.0–1.5×.

The layered formal solution
---------------------------
Slice the segment into ``N`` sub-layers.  Layer ``i`` has slant optical depth
``δ_i(λ)`` and temperature ``T_i``.  Ordering the layers **from the end the
radiation escapes**, the emergent radiance is the textbook discrete formal
solution of the non-scattering LTE transfer equation::

    L(λ) = Σ_i  B(λ, T_i) · (1 − e^{−δ_i(λ)}) · e^{−c_i(λ)},
    c_i(λ) = Σ_{j<i} δ_j(λ)      (optical depth between layer i and the exit)

The weights telescope exactly::

    Σ_i (1 − e^{−δ_i}) e^{−c_i} = 1 − e^{−Σ δ_i} = 1 − τ(λ)

so ``L = (1 − τ)·⟨B⟩`` with ``⟨B⟩`` a convex combination of the layer Planck
functions, and

    T_eff(λ) = B⁻¹( ⟨B⟩(λ) )

is guaranteed to lie between the coldest and warmest layer temperature.  The
Kirchhoff structure of :mod:`radiant.atmosphere.segment_thermal` is therefore
untouched — emissivity is still ``1 − τ`` on the segment's own transmittance
(Rule 5) — and the **total** optical depth is untouched as well: this module
only redistributes the segment's existing opacity in altitude, it never
changes ``τ``.

Two limits are exact by construction:

* **isothermal** — every ``T_i`` equal returns that temperature exactly, for
  every ``τ``, every direction and every layer count.  A level arm is
  isothermal, so a level path keeps a single, exact graybody temperature;
* **vacuum** — a segment with no opacity has no emission to weight, and the
  function falls back to the temperature of its densest air (its lower
  endpoint, the pre-CU-321 convention) so the value stays finite and physical.
  The radiance it multiplies is exactly zero there, so it is unobservable; it
  exists only so nothing ever returns NaN (Rule 17).

Direction
---------
``escape`` names the end the radiance leaves from, and it is a *geometry*
input, not a direction-dependent model: one formula, evaluated twice for the
two directional products a segment carries.  It has to be there — the
measured MODTRAN direction asymmetry on one and the same column is a factor
1.5 in the MWIR, and no direction-blind weighting can reproduce it.  A
direction-blind optical-depth-weighted mean temperature was measured and
rejected (it degrades the MWIR against every anchor; see the CU-321 report).

Where the opacity sits in altitude
----------------------------------
The CU-161 curve-of-growth calibration fixes each species' **total** column
optical depth; it says nothing about the vertical distribution of that
opacity, which is what the weighting above needs.  This module takes the
distribution from first principles:

* **scattering species** (Rayleigh, aerosol) — the extinction coefficient is
  proportional to number density, so the weighting profile is the species'
  own density scale height, unchanged;
* **pressure-broadened absorbers** (the well-mixed-gas floor, water vapour) —
  a Lorentz line's absorption coefficient is proportional to number density
  *times* the collisional half-width, and the half-width is proportional to
  total pressure.  So ``α ∝ ρ_absorber · p_air``, i.e. the weighting profile
  is the harmonic combination
  :func:`pressure_broadened_scale_height_m` of the absorber's own scale
  height and air's.  For the well-mixed floor this halves 8 km to 4 km; for
  water it takes 2 km to 1.6 km.

No coefficient here is fitted.  Both scale-height rules are derived, and the
layer quadrature below is a convergence-tested numerical parameter, not a
tuning knob — so nothing in this module needs a ``ParameterDef`` (Rule 12,
the same standing as ``grazing_column.QUADRATURE_INTERVALS``).

Fragilities
-----------
* the ICAO fixed-lapse profile the caller supplies is isothermal above the
  tropopause, so real stratospheric warming is not represented;
* a grazing arc's air is distributed along the arc, not along the vertical
  between its endpoints; the vertical weighting used here is an approximation
  there (the *total* optical depth is still exact);
* the well-mixed-gas floor lumps CO₂/N₂O/CH₄ (well mixed) with O₃ (not), so
  the 9.6 µm ozone emission is placed too low.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.constants import hc_over_kB, two_hc2
from radiant.core.parameters import ParameterBoundsError

__all__ = [
    "EMISSION_LAYERS_PER_SPECIES",
    "EmissionSpecies",
    "emission_weighted_temperature",
    "pressure_broadened_scale_height_m",
    "segment_emission_temperature_K",
]

#: Sub-layers generated per distinct species scale height.  The layer edges are
#: the union of one equal-column grid per species, so every species is resolved
#: in its own column whatever the others do.  Convergence measured against a
#: 512-per-species reference over the whole O/K/N/H anchor set: max |ΔT_eff| =
#: 1.40 K at 4, 0.29 K at 8, 0.068 K at 16, **0.016 K at 32**, 0.0039 K at 64.
#: 32 is the first value whose discretisation error is two orders of magnitude
#: below the model's own ~4 K accuracy against MODTRAN.
EMISSION_LAYERS_PER_SPECIES: int = 32

#: Escape ends a segment's two directional radiance products emerge from.
EscapeEnd = Literal["upper", "lower"]


@dataclass(frozen=True)
class EmissionSpecies:
    """One absorbing/scattering species' contribution to a segment's opacity.

    Attributes
    ----------
    scale_height_m:
        Exponential scale height of the species' **absorption coefficient**
        [m], ``> 0`` — the profile the emission is distributed along.  For a
        pressure-broadened absorber this is *not* the density scale height;
        see :func:`pressure_broadened_scale_height_m`.
    optical_depth:
        The species' slant optical depth over the whole segment
        [dimensionless], one value per wavelength, ``≥ 0``.  Only its
        distribution in altitude is modelled here; the total is taken as
        given.
    """

    scale_height_m: float
    optical_depth: np.ndarray


def pressure_broadened_scale_height_m(
    absorber_scale_height_m: float,
    air_scale_height_m: float,
) -> float:
    """Scale height of a pressure-broadened absorption coefficient [m].

    A Lorentz line's absorption coefficient is ``α ∝ n_absorber · γ_L`` with
    the collisional half-width ``γ_L ∝ p_air``.  With both the absorber and
    the air on exponential profiles, ``α ∝ exp(−h/H_a)·exp(−h/H_air)``, whose
    scale height is the harmonic combination ``(1/H_a + 1/H_air)⁻¹``.  A
    well-mixed absorber (``H_a = H_air``) therefore emits on **half** the
    density scale height.

    Raises
    ------
    ParameterBoundsError
        If either scale height is not positive-finite.
    """
    for name, value in (
        ("absorber_scale_height_m", absorber_scale_height_m),
        ("air_scale_height_m", air_scale_height_m),
    ):
        if not math.isfinite(value) or value <= 0.0:
            raise ParameterBoundsError(
                what=f"pressure_broadened_scale_height_m: {name} = {value} m is not positive",
                why="An exponential profile needs a positive, finite scale height.",
                action=f"Pass a positive {name} (e.g. one of the SimpleAtmosphere H_* constants).",
                context={name: value},
            )
    return 1.0 / (1.0 / absorber_scale_height_m + 1.0 / air_scale_height_m)


def _layer_edges_m(
    h_low_m: float,
    h_high_m: float,
    scale_heights_m: Sequence[float],
    layers_per_species: int,
) -> np.ndarray:
    """Ascending sub-layer edges [m] resolving every species' own column.

    For each distinct scale height ``H`` the segment is cut into
    ``layers_per_species`` slabs of equal ``∫exp(−h/H) dh``; the union of
    those grids is the layer set.  A species whose column collapses (a very
    tall segment seen through a 1.2 km aerosol profile) is therefore still
    resolved where it matters, without forcing the others onto a grid tuned
    for it.
    """
    edges: list[float] = [h_low_m, h_high_m]
    for scale_height_m in sorted(set(scale_heights_m)):
        u_lo = -math.expm1(-h_low_m / scale_height_m)
        u_hi = -math.expm1(-h_high_m / scale_height_m)
        u = np.linspace(u_lo, u_hi, layers_per_species + 1)
        # log1p(-1) is -inf; clip one ulp below unity so a 100 km column on a
        # 1.2 km profile still yields a finite top edge (it is then clamped to
        # h_high_m by the clip below).
        u = np.clip(u, None, 1.0 - 1.0e-16)
        edges.extend((-scale_height_m * np.log1p(-u)).tolist())
    return np.unique(np.clip(np.asarray(edges, dtype=np.float64), h_low_m, h_high_m))


def emission_weighted_temperature(
    wavelength_um: np.ndarray,
    *,
    h_low_m: float,
    h_high_m: float,
    species: Sequence[EmissionSpecies],
    temperature_profile: Callable[[np.ndarray], np.ndarray],
    escape: EscapeEnd,
    layers_per_species: int = EMISSION_LAYERS_PER_SPECIES,
) -> np.ndarray:
    """Effective emission temperature ``T_eff(λ)`` of a segment [K].

    Parameters
    ----------
    wavelength_um:
        Wavelength grid [µm], strictly positive.
    h_low_m, h_high_m:
        Segment endpoints [m], ``h_low_m ≤ h_high_m``.  Equality is the level
        (isothermal) case and returns ``temperature_profile(h_low_m)``
        exactly, whatever the opacity.
    species:
        One :class:`EmissionSpecies` per contributing species.  Their optical
        depths sum to the segment's slant optical depth; this function never
        changes that sum.
    temperature_profile:
        ``T(h)`` [K] on an array of altitudes [m] — the caller's atmospheric
        profile.  Must return strictly positive temperatures.
    escape:
        ``"upper"`` for the radiance leaving at ``h_high_m`` (a down-looking
        observer above the segment), ``"lower"`` for the radiance leaving at
        ``h_low_m`` (an up-looking observer below it).
    layers_per_species:
        Quadrature resolution; see :data:`EMISSION_LAYERS_PER_SPECIES`.

    Returns
    -------
    np.ndarray
        ``T_eff`` [K], one per wavelength, bounded by the coldest and warmest
        layer temperature in the segment.  Never NaN or inf (Rule 17).

    Raises
    ------
    ParameterBoundsError
        On inverted endpoints, an empty species list, a shape mismatch, a
        negative optical depth, a non-positive scale height, a bad ``escape``
        value, a non-positive ``layers_per_species``, or a temperature profile
        that returns a non-positive or non-finite temperature.
    """
    lam = np.asarray(wavelength_um, dtype=np.float64)
    if escape not in ("upper", "lower"):
        raise ParameterBoundsError(
            what=f"emission_weighted_temperature: escape = {escape!r} is not a segment end",
            why="Radiance leaves a segment at one of its two endpoints.",
            action="Pass escape='upper' (down-looking observer) or 'lower' (up-looking).",
            context={"escape": escape},
        )
    if not math.isfinite(h_low_m) or not math.isfinite(h_high_m) or h_high_m < h_low_m:
        raise ParameterBoundsError(
            what=(
                f"emission_weighted_temperature: altitude pair (h_low_m = {h_low_m} m, "
                f"h_high_m = {h_high_m} m) is not a finite ordered interval"
            ),
            why="A segment runs from its lower endpoint upward.",
            action="Order the endpoints so h_low_m ≤ h_high_m.",
            context={"h_low_m": h_low_m, "h_high_m": h_high_m},
        )
    if layers_per_species < 1:
        raise ParameterBoundsError(
            what=(
                f"emission_weighted_temperature: layers_per_species = {layers_per_species} "
                "is below 1"
            ),
            why="The formal solution needs at least one sub-layer per species.",
            action=f"Use the module default ({EMISSION_LAYERS_PER_SPECIES}) or any integer ≥ 1.",
            context={"layers_per_species": layers_per_species},
        )
    if not species:
        raise ParameterBoundsError(
            what="emission_weighted_temperature: no species supplied",
            why="A segment's opacity is the sum over its species; an empty sum is not a segment.",
            action="Pass one EmissionSpecies per contributing species.",
            context={"n_species": 0},
        )
    for index, member in enumerate(species):
        od = np.asarray(member.optical_depth, dtype=np.float64)
        if od.shape != lam.shape:
            raise ParameterBoundsError(
                what=(
                    f"emission_weighted_temperature: species[{index}].optical_depth shape "
                    f"{od.shape} does not match wavelength_um shape {lam.shape}"
                ),
                why="Optical depth and wavelength are the same spectral vector.",
                action="Evaluate every species' optical depth on the chain wavelength grid.",
                context={"od_shape": od.shape, "lam_shape": lam.shape},
            )
        if not np.all(np.isfinite(od)) or float(od.min()) < 0.0:
            raise ParameterBoundsError(
                what=(
                    f"emission_weighted_temperature: species[{index}].optical_depth is not "
                    "finite and non-negative"
                ),
                why="A negative optical depth is an amplifying medium, not an atmosphere.",
                action="Fix the optical-depth computation that produced it.",
                context={"min": float(np.nanmin(od)), "max": float(np.nanmax(od))},
            )
        if not math.isfinite(member.scale_height_m) or member.scale_height_m <= 0.0:
            raise ParameterBoundsError(
                what=(
                    f"emission_weighted_temperature: species[{index}].scale_height_m = "
                    f"{member.scale_height_m} m is not positive"
                ),
                why="An exponential profile needs a positive scale height.",
                action="Pass the species' absorption-coefficient scale height in metres.",
                context={"scale_height_m": member.scale_height_m},
            )

    # --- Level (isothermal) segment: exact, no quadrature -------------------
    if h_high_m <= h_low_m:
        t_level = _validated_profile(temperature_profile, np.array([h_low_m], dtype=np.float64))
        return np.full_like(lam, float(t_level[0]))

    edges = _layer_edges_m(
        h_low_m, h_high_m, [member.scale_height_m for member in species], layers_per_species
    )
    if edges.size < 2:  # pragma: no cover - guarded by h_high_m > h_low_m above
        t_level = _validated_profile(temperature_profile, np.array([h_low_m], dtype=np.float64))
        return np.full_like(lam, float(t_level[0]))

    lower = edges[:-1]
    upper = edges[1:]
    layer_t = _validated_profile(temperature_profile, 0.5 * (lower + upper))

    # Per-layer optical depth: each species' total redistributed by its own
    # column fraction.  Normalising the fractions is what keeps Σ δ_i exactly
    # equal to the segment optical depth the caller already computed.
    layer_od = np.zeros((lower.size, lam.size), dtype=np.float64)
    for member in species:
        column = np.exp(-lower / member.scale_height_m) - np.exp(-upper / member.scale_height_m)
        total = float(column.sum())
        if total <= 0.0:
            # The species' column underflows over this segment (e.g. a 1.2 km
            # aerosol profile above 60 km): it carries no opacity to place.
            continue
        layer_od += (column / total)[:, None] * np.asarray(member.optical_depth, dtype=np.float64)[
            None, :
        ]

    # Vacuum fallback (below): the densest air in the segment, which is the
    # pre-CU-321 CU-155 convention and keeps the two continuous.
    t_vacuum = float(layer_t[0])

    # Order the layers from the escape end and accumulate the formal solution.
    if escape == "upper":
        layer_od = layer_od[::-1]
        layer_t = layer_t[::-1]
    cumulative = np.cumsum(layer_od, axis=0) - layer_od
    weight = -np.expm1(-layer_od) * np.exp(-cumulative)
    total_weight = weight.sum(axis=0)

    emitting = total_weight > 0.0
    if not np.any(emitting):
        return np.full_like(lam, t_vacuum)

    normalised = np.where(
        emitting[None, :], weight / np.where(emitting, total_weight, 1.0)[None, :], 0.0
    )
    b_layers = planck_spectral_radiance(lam[None, :], layer_t[:, None])
    b_eff = (normalised * b_layers).sum(axis=0)

    t_eff = _inverse_planck_K(lam, b_eff)
    if not np.all(emitting):
        t_eff = np.where(emitting, t_eff, t_vacuum)
    # ⟨B⟩ is a convex combination of the layer Planck functions, so T_eff is
    # bounded by the layer temperatures analytically; the clip only removes
    # round-off dust from the Planck inversion.
    return np.asarray(np.clip(t_eff, float(layer_t.min()), float(layer_t.max())), dtype=np.float64)


def segment_emission_temperature_K(
    wavelength_um: np.ndarray,
    *,
    h_low_m: float,
    h_high_m: float,
    od_slant_mol: np.ndarray,
    od_slant_aer: np.ndarray,
    od_slant_h2o: np.ndarray,
    od_slant_gas: np.ndarray,
    scale_height_mol_m: float,
    scale_height_aer_m: float,
    scale_height_h2o_m: float,
    temperature_profile: Callable[[np.ndarray], np.ndarray],
    escape: EscapeEnd,
    layers_per_species: int = EMISSION_LAYERS_PER_SPECIES,
) -> np.ndarray:
    """``T_eff(λ)`` [K] for a ``SimpleAtmosphere`` four-species segment.

    The adapter every call site uses, so the broadening rule lives in exactly
    one place: Rayleigh and aerosol keep their density scale heights (their
    extinction is proportional to number density), while the well-mixed-gas
    floor and water vapour are placed on the pressure-broadened profile
    :func:`pressure_broadened_scale_height_m` gives — 4 km and 1.6 km against
    the shipped 8 km / 2 km density profiles.

    ``od_slant_*`` are the four species' slant optical depths over the whole
    segment, exactly as the caller's optical-depth routine already computed
    them; their sum is left untouched.
    """
    return emission_weighted_temperature(
        wavelength_um,
        h_low_m=h_low_m,
        h_high_m=h_high_m,
        species=(
            EmissionSpecies(scale_height_mol_m, od_slant_mol),
            EmissionSpecies(scale_height_aer_m, od_slant_aer),
            EmissionSpecies(
                pressure_broadened_scale_height_m(scale_height_h2o_m, scale_height_mol_m),
                od_slant_h2o,
            ),
            EmissionSpecies(
                pressure_broadened_scale_height_m(scale_height_mol_m, scale_height_mol_m),
                od_slant_gas,
            ),
        ),
        temperature_profile=temperature_profile,
        escape=escape,
        layers_per_species=layers_per_species,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _validated_profile(
    temperature_profile: Callable[[np.ndarray], np.ndarray],
    altitudes_m: np.ndarray,
) -> np.ndarray:
    """Evaluate the caller's ``T(h)`` and refuse a non-physical answer."""
    values = np.atleast_1d(np.asarray(temperature_profile(altitudes_m), dtype=np.float64))
    bad_shape = values.shape != altitudes_m.shape
    if bad_shape or not np.all(np.isfinite(values)) or float(values.min()) <= 0.0:
        minimum = float(np.nanmin(values)) if values.size and not bad_shape else float("nan")
        raise ParameterBoundsError(
            what=(
                "emission_weighted_temperature: temperature_profile returned "
                f"shape {values.shape} / minimum {minimum} K"
            ),
            why=(
                "The Planck function is undefined at non-positive temperature, and the "
                "profile must answer one temperature per altitude."
            ),
            action="Return a strictly positive finite temperature for every altitude passed.",
            context={"n_altitudes": int(altitudes_m.size), "shape": values.shape},
        )
    return values


def _inverse_planck_K(lam_um: np.ndarray, radiance: np.ndarray) -> np.ndarray:
    """``T`` [K] such that ``B(λ, T) == radiance`` [W/m²/sr/µm].

    The analytic inverse of the Planck law used by
    :func:`radiant.core.blackbody.planck_spectral_radiance`, written with the
    same two constants so the pair round-trips:

        ``T = (hc/k_B) / (λ · ln(1 + 2hc²/(λ⁵ L)))``   (λ in m, L per m)
    """
    lam_m = lam_um * 1.0e-6
    l_per_m = radiance * 1.0e6
    with np.errstate(divide="ignore", over="ignore"):
        argument = two_hc2 / (lam_m**5 * l_per_m)
    return np.asarray(hc_over_kB / (lam_m * np.log1p(argument)), dtype=np.float64)
