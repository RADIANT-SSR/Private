"""n^2 validity study: compare the shipped eps_eff against the Kirchhoff absorptance.

Shipped (cavity_model.eps_eff):   T2 * n^2 * (1-b) / D
Kirchhoff (derived here):         A2 = T2 * (1-b) * (1 + R1*b) / D
where b = exp(-alpha*d), D = 1 - R1*R2*b^2.

A2 is the absorptance for illumination incident on surface 2, which by Kirchhoff's
law equals the directional emissivity out of surface 2.
"""

import numpy as np


def slab(R1: float, R2: float, b: float) -> tuple[float, float, float]:
    """Incoherent plane-parallel slab: (T_sys, R_sys, A) for side-1 illumination."""
    T1, T2 = 1.0 - R1, 1.0 - R2
    D = 1.0 - R1 * R2 * b * b
    T_sys = T1 * b * T2 / D
    R_sys = R1 + T1 * T1 * R2 * b * b / D
    return T_sys, R_sys, 1.0 - T_sys - R_sys


def closed_form_A1(R1: float, R2: float, b: float) -> float:
    """A1 = T1 (1-b)(1 + R2 b) / (1 - R1 R2 b^2) — algebraic reduction."""
    T1 = 1.0 - R1
    D = 1.0 - R1 * R2 * b * b
    return T1 * (1.0 - b) * (1.0 + R2 * b) / D


def eps_shipped(R1: float, R2: float, b: float, n: float) -> float:
    T2 = 1.0 - R2
    D = 1.0 - R1 * R2 * b * b
    return T2 * n * n * (1.0 - b) / D


def eps_kirchhoff_side2(R1: float, R2: float, b: float) -> float:
    """Emissivity out of surface 2 = absorptance for side-2 illumination."""
    T2 = 1.0 - R2
    D = 1.0 - R1 * R2 * b * b
    return T2 * (1.0 - b) * (1.0 + R1 * b) / D


print("=" * 78)
print("STEP 1 — verify the algebraic reduction A1 = T1(1-b)(1+R2 b)/D")
print("=" * 78)
rng = np.random.default_rng(7)
worst = 0.0
for _ in range(20000):
    R1, R2 = rng.uniform(0, 0.999, 2)
    b = rng.uniform(0, 1)
    _, _, a_num = slab(R1, R2, b)
    worst = max(worst, abs(a_num - closed_form_A1(R1, R2, b)))
print(f"max |1-T_sys-R_sys  -  closed form| over 20000 random (R1,R2,b) = {worst:.3e}")

print()
print("=" * 78)
print("STEP 2 — is the Kirchhoff emissivity ever > 1?  (it must not be)")
print("=" * 78)
mx = 0.0
arg = None
for _ in range(200000):
    R1, R2 = rng.uniform(0, 1, 2)
    b = rng.uniform(0, 1)
    e = eps_kirchhoff_side2(R1, R2, b)
    if e > mx:
        mx, arg = e, (R1, R2, b)
print(f"max eps_kirchhoff = {mx:.6f} at R1={arg[0]:.4f} R2={arg[1]:.4f} b={arg[2]:.4f}")
print("  -> bounded by 1 with equality only in the limit R2->0, b->0 (black substrate,")
print("     AR-perfect exit face). No clip is ever needed.")

print()
print("=" * 78)
print("STEP 3 — shipped vs correct for real substrates (AR coated, R1=R2=0.01)")
print("=" * 78)
# alpha [1/cm] at 10.6 um unless noted; thickness 8 mm
cases = [
    ("Ge      @10.6um", 4.0025, 0.027, 0.8),
    ("Si      @ 3.0um", 3.4320, 0.010, 0.8),
    ("ZnSe    @10.6um", 2.4028, 0.0005, 0.8),
    ("ZnS-MS  @10.6um", 2.2008, 0.2, 0.8),
    ("ZnS-MS  @ 3.8um", 2.2520, 0.0006, 0.8),
    ("sapphire@ 2.4um", 1.7430, 3.0e-4, 0.3),
    ("CaF2    @ 2.7um", 1.4140, 7.8e-4, 0.5),
    ("BaF2    @ 6.0um", 1.4580, 3.2e-4, 0.5),
    ("silica  @ 1.0um", 1.4504, 1.0e-5, 0.5),
]
R1 = R2 = 0.01
hdr = (
    f"{'case':<16} {'n':>7} {'a[1/cm]':>9} {'d[cm]':>6} "
    f"{'eps_ship':>10} {'eps_corr':>10} {'ratio':>7}"
)
print(hdr)
print("-" * len(hdr))
for name, n, a, d in cases:
    b = np.exp(-a * d)
    es = eps_shipped(R1, R2, b, n)
    ec = eps_kirchhoff_side2(R1, R2, b)
    print(f"{name:<16} {n:7.4f} {a:9.2e} {d:6.2f} {es:10.4f} {ec:10.4f} {es / ec:7.2f}")
print()
print("ratio -> n^2/(1+R1*b) exactly; for R1=0.01, b~1 that is n^2/1.01")
for name, n, a, d in cases:
    b = np.exp(-a * d)
    print(f"  {name:<16} n^2/(1+R1 b) = {n * n / (1 + R1 * b):7.3f}")

print()
print("=" * 78)
print("STEP 4 — where does the shipped expression exceed 1? (the clip regime)")
print("=" * 78)
print(f"{'material':<10} {'n':>7} {'alpha*d at eps_ship=1':>24} {'alpha*d at eps_corr=0.5':>26}")
for name, n, _a, _d in cases:
    T2 = 1 - R2
    # solve T2 n^2 (1-b)/D = 1 for b, with D ~ 1 - R1 R2 b^2 ~ 1
    # (1-b) = 1/(T2 n^2)  ->  b = 1 - 1/(T2 n^2)
    tgt = 1.0 - 1.0 / (T2 * n * n)
    ad_clip = -np.log(tgt) if 0 < tgt < 1 else float("nan")
    # eps_corr = 0.5: T2(1-b)(1+R1 b)/D = 0.5 -> solve numerically
    from scipy.optimize import brentq

    f = lambda x: eps_kirchhoff_side2(R1, R2, np.exp(-x)) - 0.5  # noqa: E731
    try:
        ad_half = brentq(f, 1e-9, 50)
    except Exception:  # noqa: BLE001
        ad_half = float("nan")
    print(f"{name.split()[0]:<10} {n:7.4f} {ad_clip:24.4f} {ad_half:26.4f}")
