"""Physical constants — CODATA 2018 exact values.

Source: NIST CODATA 2018 (https://physics.nist.gov/cuu/Constants/)
These are the 2019 SI redefinition exact values. After the 2019 SI
redefinition, h, c, k_B, and q are exact by definition.

This is the ONLY place physical constants are defined in RADIANT.
No module may hardcode physical constants. Import from here.

Usage:
    from radiant.core.constants import h, c, k_B
"""

import scipy.constants as _sc  # type: ignore[import-untyped]

# Speed of light in vacuum [m/s] — exact (SI definition)
# Value: 2.99792458e8 m/s
c: float = _sc.c

# Planck constant [J·s] — exact (SI redefinition 2019)
# Value: 6.62607015e-34 J·s
h: float = _sc.h

# Boltzmann constant [J/K] — exact (SI redefinition 2019)
# Value: 1.380649e-23 J/K
k_B: float = _sc.k

# Elementary charge [C] — exact (SI redefinition 2019)
# Value: 1.602176634e-19 C
q: float = _sc.e

# Stefan-Boltzmann constant [W/m²/K⁴] — derived: σ = 2π⁵k_B⁴/(15h³c²)
# Value: 5.670374419e-8 W/m²/K⁴
sigma_sb: float = _sc.sigma

# Nominal solar radius [m] — IAU 2015 Resolution B3 nominal value.
# https://www.iau.org/static/resolutions/IAU2015_English.pdf
R_sun_m: float = 6.957e8

# Astronomical unit [m] — IAU 2012 exact definition.
au_m: float = 1.495_978_707e11

# Nominal total solar irradiance at 1 AU [W/m²] — IAU 2015 Resolution B3
# nominal "solar irradiance" S_0. Used to calibrate the TOA solar
# spectrum constructed from a 5778 K blackbody.
S_solar_W_per_m2: float = 1361.0

# WGS-84 equatorial (semi-major axis) Earth radius [m] — exact by definition.
# https://earth-info.nga.mil/ (WGS-84 specification).  Used for spherical-Earth
# line-of-sight geometry (boundary converters, airmass, ray-sphere intersect).
# The `geometry` module elsewhere in core uses the US Standard 1976
# mean radius (6_371_000.0 m) for ground-incidence / slant-range calculations;
# the two values differ by ~0.1% and are used in separate geometric contexts.
R_EARTH_M: float = 6.378137e6

# Earth standard gravitational parameter GM [m³/s²] — WGS-84 / EGM value
# (G·M_earth). Used for circular-orbit kinematics (period, orbital velocity,
# ground-track speed) in radiant.core.orbit.
# https://earth-info.nga.mil/ (WGS-84 specification, GM).
mu_earth_m3_s2: float = 3.986_004_418e14

# Earth second zonal harmonic J2 [dimensionless] — WGS-84 value. Drives the
# secular nodal regression of LEO orbits (sun-synchronous condition,
# repeat-ground-track spacing) in radiant.core.repeat_ground_track.
J2_earth: float = 1.082_626_68e-3

# ---------------------------------------------------------------------------
# Derived convenience quantities
# ---------------------------------------------------------------------------

# h*c [J·m] — numerator factor in Planck spectral radiance
hc: float = h * c

# 2*h*c² [W·m²] — Planck spectral radiance numerator (first radiation constant)
two_hc2: float = 2.0 * h * c**2

# h*c/k_B [m·K] — second radiation constant c₂
hc_over_kB: float = h * c / k_B

# ---------------------------------------------------------------------------
# Backward-compatibility uppercase aliases (this file only).
# External code must use lowercase names per CLAUDE.md Rule 13.
# ---------------------------------------------------------------------------
C = c
H = h
K_B = k_B
Q = q
SIGMA_SB = sigma_sb
C1 = two_hc2
C2 = hc_over_kB
