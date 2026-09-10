"""Optical (diffraction) spatial-frequency cutoff — the incoherent MTF band edge.

An incoherent, aberration-free circular pupil passes no spatial frequency above

    f_cutoff = 1 / (λ · F#)              [cycles/m on the focal plane]

where λ is the wavelength [m] and ``F# = focal_length / aperture_diameter``.
Above ``f_cutoff`` the pupil autocorrelation (Rule 4's ``MTF_optics``) is
identically zero, so every downstream MTF-product curve is zero there too.

The ``F#`` to pass is the **working** f-number of the **effective** pupil —
``stage_outputs["optics"]["f_number_eff"]``, which an undersized cold stop
reduces to (Gap 128) — not the primary's ``optics.f_number``. The cold stop is
the aperture stop, and the complex pupil the MTF product is built from already
uses it; a cutoff taken from the primary rim would not be the band edge of the
curve it describes. The two coincide at the default ``cold_stop_undersize_frac
= 0``.

Expressed on the chain's **angular** frequency axis — the axis every MTF overlay
and budget uses — an angular frequency ``f_ang`` [cycles/rad] images to
``f_ang / focal_length`` [cycles/m] on the focal plane, so

    f_cutoff [cycles/mrad] = f_cutoff [cycles/m] · focal_length_m / 1e3
                           = D / (λ · 1e3)

with the aperture diameter ``D = focal_length / F#`` [m] and λ in **m**. The
``/ 1e3`` is the rad → mrad step and nothing else (it is the same conversion
``PerformanceStage`` applies to the Nyquist frequency, kept identical on
purpose — the cycles/m ↔ cycles/mrad step is exactly where CU-234's error
lived).

This is the optics band edge, the companion of the detector sampling limit
``system_mtf.nyquist_freq``: together they bound the frequency band in which an
MTF curve carries information. Views use them to bound a plotted axis;
``performance/sampling_regime.py`` uses their ratio (Q) to classify the design.
"""

from __future__ import annotations

from radiant.performance.errors import PerformanceValidationError

__all__ = ["optics_cutoff_freq", "optics_cutoff_freq_cycles_per_mrad"]


def optics_cutoff_freq(wavelength_m: float, f_number: float) -> float:
    """Incoherent diffraction cutoff ``1 / (λ · F#)`` [cycles/m].

    Parameters
    ----------
    wavelength_m:
        Wavelength [m] (note: **metres**, not the µm the schema carries —
        convert at the call site, Rule 2).
    f_number:
        Working f-number of the effective pupil [dimensionless] —
        ``f_number_eff``, not the primary's ``optics.f_number`` (see the module
        docstring).

    Returns
    -------
    float
        Optical cutoff spatial frequency [cycles/m] on the focal plane.

    Raises
    ------
    PerformanceValidationError
        When λ or F# is not positive.
    """
    if wavelength_m <= 0.0:
        raise PerformanceValidationError(
            f"optics_cutoff_freq: wavelength_m must be positive, got {wavelength_m} m."
        )
    if f_number <= 0.0:
        raise PerformanceValidationError(
            f"optics_cutoff_freq: f_number must be positive, got {f_number}."
        )
    return 1.0 / (wavelength_m * f_number)


def optics_cutoff_freq_cycles_per_mrad(
    wavelength_m: float,
    f_number: float,
    focal_length_m: float,
) -> float:
    """The same cutoff on the chain's angular axis [cycles/mrad].

    ``f_cutoff [cycles/mrad] = focal_length_m / (λ · F# · 1e3)``, i.e. the
    focal-plane cutoff from :func:`optics_cutoff_freq` mapped through the focal
    length and then rad → mrad.

    Parameters
    ----------
    wavelength_m:
        Wavelength [m].
    f_number:
        Working f-number [dimensionless].
    focal_length_m:
        Effective focal length [m].

    Returns
    -------
    float
        Optical cutoff spatial frequency [cycles/mrad].

    Raises
    ------
    PerformanceValidationError
        When λ, F#, or the focal length is not positive.
    """
    if focal_length_m <= 0.0:
        raise PerformanceValidationError(
            "optics_cutoff_freq_cycles_per_mrad: focal_length_m must be positive "
            f"(the angular ↔ focal-plane mapping is through it), got {focal_length_m} m."
        )
    return optics_cutoff_freq(wavelength_m, f_number) * focal_length_m / 1e3
