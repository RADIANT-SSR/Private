# Geometry & Sampling

*Persona: Sarah (systems engineer), Lisa (analyst)*

Spherical-Earth viewing geometry, orbit kinematics, ground sampling, smear kinematics,
solar geometry, and attitude conventions as implemented in RADIANT, which resolves the
scene geometry before any radiometry. Numeric anchors were re-derived from the literature
independently of the code and then checked against it. RADIANT uses the IUGG **mean Earth
radius $R = 6371.0$ km**, so the anchors below are quoted for that radius: an ~8 km radius
difference — the gap to the WGS-84 equatorial value — moves a 500 km/30° slant range by
~9 m and the orbit period by ~9 s, so always match radii before comparing numbers.

**Symbols and the code's naming.** Classical texts parameterize the viewing triangle by
the look angle at the satellite; RADIANT is **$\theta_o$-referenced**:

| Classical symbol | Meaning | RADIANT name |
|---|---|---|
| $\eta$ | look/off-nadir angle at the sensor | `eta` (`viewing_triangle.eta_from_theta_o`) |
| $\theta_o$ ($= \theta_i$ for a surface target) | LOS zenith angle at the **target** | `theta_o`, `path_zenith_rad` |
| $\varepsilon = \pi/2 - \theta_o$ | grazing/elevation angle | `elevation_angle_rad` |
| $\Lambda$ | Earth central angle | via ground range $R\Lambda$ |
| $R_s$ | slant range | `slant_range_m` |
| $h$ | sensor altitude | `geometry.sensor_altitude_m` |

---

## 1. The viewing triangle

**Equations.** Triangle Earth-center–sensor–target with sides $R$, $R+h$, $R_s$. Angle
closure $\Lambda = \theta_o - \eta$ and the law of sines give the load-bearing identity

$$\sin\theta_o = \frac{R+h}{R}\,\sin\eta$$

— note the **amplifying** factor $(R+h)/R$: incidence at the target always *exceeds* the
look angle on a sphere ($R/(R+h)$ belongs only in the $\varepsilon \to \eta$ direction).
Closed-form solution sets exist from any one of $\{\eta, \theta_o, \Lambda\}$ plus $h$;
the $\Lambda$-parameterized form uses the branch-safe
$\eta = \operatorname{atan2}(R\sin\Lambda,\ (R{+}h) - R\cos\Lambda)$.

**Assumptions & validity.** Spherical Earth, surface (or specified-altitude) target, no
refraction (refraction lifts apparent elevation up to ~0.5° at $\varepsilon \approx 0$).

**Pitfalls.** The flat-Earth intuition $\theta_o = \eta$ (wrong by 2.6° at
$h = 500$ km, $\eta = 30°$ and unbounded toward the limb); $\Lambda = \eta - \theta_o$
sign flips; degrees fed to radian trig.

**Numeric anchor.** $h = 500$ km, $\eta = 30°$:
$\theta_o = 32.6319°$, $\Lambda = 2.6319°$ (mean-R).

**In RADIANT.** `core/viewing_triangle.py` (`eta_from_theta_o`,
`slant_range_from_theta_o_m`, `ground_range_from_theta_o_m`,
`theta_o_from_ground_range_m`), `core/los_geometry.py::theta_o_from_eta`,
`core/geometry.py::incidence_angle_rad` · anchored by
`core/tests/test_viewing_triangle.py`, `test_los_geometry.py`, `test_geometry.py`.
**References.** [Wertz & Larson 1999].

---

## 2. Slant range

**Equation.** Direct form in the look angle:

$$R_s = (R+h)\cos\eta - \sqrt{R^2 - (R+h)^2\sin^2\eta}.$$

The **minus** root is the near (visible-surface) intersection; the plus root exits the
far side of the Earth. A negative discriminant means the LOS misses the Earth —
$\sin\eta > R/(R+h)$, beyond the limb; the boundary is
$\eta_{max} = \arcsin\!\frac{R}{R+h}$ with tangent-ray range $\sqrt{2Rh + h^2}$.

**Pitfalls.** Plus-root selection (returns ~11 Mm at nadir instead of $h$); silent NaN on
a beyond-horizon geometry instead of an actionable error; near $\eta_{max}$,
$dR_s/d\eta \to \infty$ — solvers should re-parameterize in $\Lambda$ or $\varepsilon$
there.

**Numeric anchors.** $h = 500$ km, $\eta = 30°$: $R_s = 585{,}110.5$ m (mean-R). Nadir:
$R_s = h$ exactly. $\eta_{max}(500\ \text{km}) = 68.01°$ (mean-R).

**In RADIANT.** `core/geometry.py::slant_range_spherical_m`,
`core/viewing_triangle.py::slant_range_from_theta_o_m` · anchored by
`core/tests/test_geometry.py` and the audit anchors in
`performance/tests/test_gsd.py::TestA4GeometryAnchors`.
**References.** [Wertz & Larson 1999].

---

## 3. Circular-orbit kinematics

**Equations.**

$$v = \sqrt{\frac{\mu}{R+h}},\qquad T = 2\pi\sqrt{\frac{(R+h)^3}{\mu}},\qquad v_g = v\,\frac{R}{R+h}.$$

The $R/(R+h)$ factor: satellite and nadir point share one angular rate $\omega$; linear
speed is $\omega$ times each circle's radius. It is a projection of angular motion, not a
velocity-vector projection.

**Assumptions & validity.** Two-body, circular, no $J_2$ (~0.1 % LEO period effect);
non-rotating Earth for $v_g$ — Earth rotation adds up to $\pm465\cos(\text{lat})$ m/s
(~6.6 % equatorial) to the true relative ground speed, unmodeled.

**Pitfalls.** $\sqrt{\mu/R}$ instead of $\sqrt{\mu/(R+h)}$ (3.8 % at 500 km); **orbital
$v$ where ground $v_g$ belongs** in smear/line-rate math — a +7.8 % error at 500 km that
looks plausible; $\mu$ in km³/s² mixed with meters.

**Numeric anchors** (mean-R): $v = 7616.6$ m/s, $T = 94.469$ min at $h = 500$ km.

**In RADIANT.** `core/orbit.py::orbital_velocity_m_s`, `orbital_period_s`,
`ground_track_speed_m_s`; repeat-track machinery in `core/repeat_ground_track.py` ·
anchored by `core/tests/test_orbit.py` (audit-pinned), `test_repeat_ground_track.py`.
**References.** [Vallado 2013].

---

## 4. GSD — nadir and off-nadir

**Equations.** $\mathrm{IFOV} = p/f$; nadir $\mathrm{GSD} = (p/f)\,h$. Off-nadir, the
beam width $\mathrm{IFOV}\cdot R_s$ (measured ⊥ to the LOS) projects onto the local
tangent plane; the LOS makes angle $\theta_o$ (**incidence at the target, not the look
angle $\eta$**) with the surface normal:

$$\mathrm{GSD}_{\text{in-plane}} = \frac{\mathrm{IFOV}\cdot R_s}{\cos\theta_o},\qquad \mathrm{GSD}_{\perp} = \mathrm{IFOV}\cdot R_s.$$

The $1/\cos\theta_o$ applies **only** in the tilt plane (the plane containing the LOS and
the local vertical); the orthogonal horizontal direction is itself ⊥ to the LOS and
projects length-preserving. In RADIANT's convention the LOS tilt is carried by
`geometry.path_zenith_rad` in the **along-track** plane, so `along_track_m` receives the
$1/\cos\theta_o$ elongation and `cross_track_m` the range-only factor. The formula is
exact on the sphere: differentiating the viewing triangle gives
$R\,d\Lambda/d\eta = R_s/\cos\theta_o$ identically.

**Pitfalls.** $\cos\eta$ for $\cos\theta_o$ (2.75 % at the anchor geometry, unbounded
toward the limb); $\cos$ vs $1/\cos$ (GSD must *grow* off-nadir); applying the obliquity
factor to both directions (a further ~19 % area error at the anchor); quoting one
off-nadir "GSD" without naming the direction.

**Numeric anchors** (mean-R, $p = 10$ µm, $f = 2$ m, $h = 500$ km): nadir 2.500000 m;
$\eta = 30°$: in-plane 3.473901 m — the wrong-angle value 3.378 m is explicitly rejected
by the anchor test.

**In RADIANT.** `performance/gsd.py::compute_gsd`, `compute_gsd_from_geometry` · anchored
by `performance/tests/test_gsd.py::TestA4GeometryAnchors` (includes the
$\cos\eta$-discriminator assertion). **References.** [Wertz & Larson 1999],
[Holst 2008].

---

## 5. Swath and access

**Equations.** Swath from the cross-track GSD and detector format:
$W = \mathrm{GSD}_{cross}\cdot N_{pix}$; area access rate $\dot A = W\,v_g$; ground range
from the central angle, $R\,\Lambda$. Wide-FOV swath uses the full spherical
mapping $\Lambda(\eta)$ — the flat-Earth $2h\tan\eta_{half}$ is 0.3 % low at ±15° and
diverges beyond ~30°.

**In RADIANT.** modules above · anchored by
`performance/tests/test_access_geometry.py`. **References.** [Wertz & Larson 1999].

---

## 6. Smear kinematics and TDI line-rate matching

**Equations.** Uncompensated nadir pushbroom: ground motion $v_g t_{int}$ maps to the
focal plane through the magnification $f/R_s$:

$$d_{img} = v_g\,t_{int}\,\frac{f}{R_s}\quad(= v_g t_{int} f/h\ \text{at nadir}).$$

TDI requires the line clock to match the image velocity:
$p\,f_{line} = v_{img} \iff t_{line} = \mathrm{GSD}/v_g$; residual per-stage mismatch
smear multiplies by $N$ stages. The MTF consequence of $d_{img}$ is the smear sinc of
the spatial chapter's *Platform kernels: jitter and smear*.

**Pitfalls.** Orbital $v$ for $v_g$ (+7.8 %); $f/R$ or $f/(R+h)$ for the magnification;
ground meters compared to focal-plane microns without $f/R_s$; conflating $t_{int}$ with
$t_{line}$ in TDI ($t_{int} = N\,t_{line}$; the matching condition constrains
$t_{line}$).

**Numeric anchor.** $h = 500$ km, $p = 10$ µm, $f = 2$ m, $t_{int} = 1$ ms:
$d_{img} \approx 2.8$ pixels — uncompensated millisecond integration is not viable; the
matched line time is ~354 µs.

**In RADIANT.** `platform/smear.py` (smear length from
`platform.ground_velocity_m_s`/`smear_length_um`), consistency group
`_GROUND_SPEED_GROUP` ties `ground_velocity_m_s` to the orbit value · anchored by
`platform/tests/test_smear.py`, `test_sampling.py`. **References.** [Holst 2008].

---

## 7. Solar geometry

**Equation.** Spherical law of cosines on the astronomical triangle:

$$\cos\theta_z = \sin\phi\sin\delta + \cos\phi\cos\delta\cos H$$

($\phi$ latitude, $\delta$ declination, $H$ hour angle from solar noon). Declination comes
from the day of year, and the hour angle from either the local solar time or the local
time of the ascending node.

**Pitfalls.** Clock time vs apparent solar time (equation of time, ±4° in $H$);
elevation returned where zenith is expected (downstream $\cos\theta_z$ irradiance factors
get sin/cos swapped); sign conventions on $\delta$ across hemispheres.

**Numeric anchor.** $\phi = 35°$N, $\delta = 23.44°$, $H = 15°$:
$\theta_z = 17.4256°$. Noon collapses to $\theta_z = \phi - \delta$ exactly.

**In RADIANT.** `core/solar_geometry.py::solar_zenith_angle_rad` · anchored by
`core/tests/test_solar_geometry.py` (audit-pinned). **References.** [Wertz & Larson 1999].

---

## 8. Attitude: Euler ZYX

**Equation.** Intrinsic z–y′–x″ (yaw $\psi$ → pitch $\theta$ → roll $\varphi$), active,
right-handed, column vectors:

$$\mathbf{R} = \mathbf{R}_z(\psi)\,\mathbf{R}_y(\theta)\,\mathbf{R}_x(\varphi),$$

gimbal lock at $\theta = \pm90°$. This matches `scipy Rotation.from_euler('ZYX', ...)`
exactly; extraction via $\theta = -\arcsin R_{31}$,
$\psi = \operatorname{atan2}(R_{21}, R_{11})$,
$\varphi = \operatorname{atan2}(R_{32}, R_{33})$.

**Pitfalls.** Intrinsic z-y′-x″ equals *extrinsic* x-y-z (same product) but not intrinsic
x-y′-z″; active/passive transposes; the $+\sin\theta$ corner of $\mathbf{R}_y$ sits
opposite to $\mathbf{R}_z$/$\mathbf{R}_x$.

**In RADIANT.** `core/geometry.py::euler_to_rotation_matrix`,
`rotation_matrix_to_euler` (convention pinned in `RADIANT_Conventions.md` §1 / CLAUDE.md
Rule 3) · anchored by `core/tests/test_geometry.py`.

---

## 9. Sampling on the ground

Focal-plane Nyquist $1/(2p)$ projects to ground Nyquist $1/(2\,\mathrm{GSD})$ —
direction-dependent off-nadir (use the direction's GSD from *GSD — nadir and off-nadir*
above). The optics-vs-sampling
budget ($Q = \lambda F_\#/p$, aliasing, folded MTF) lives in the spatial chapter's
*Sampling: Nyquist, Q, and folded MTF*; the geometry chapter's contribution is the GSD
that scales it to the ground.

---

## 10. Input modes and scene classes

**Input modes.** The scene is expressed in exactly one mode per family, and the mode is
detected by *provenance*: a parameter left at its default was not provided, so there is
no mode switch to set. The **viewing** family resolves to $\theta_o$: V0 direct range
(`geometry.target_range_m`; on a level path with no angle entered the range is the chord
that builds the triangle, $\varphi = 2\arcsin(d/2r)$, $\theta_o = \pi/2 + \varphi/2$),
V1 path zenith at the lower endpoint (`path_zenith_rad`), V2 off-boresight angle at the
sensor (`sensor_off_boresight_rad`, its reference axis nadir when the sensor is the upper
endpoint and zenith when it is the lower one), V3 ground range (`ground_range_m`,
direction-free: the surface arc fixes $\Lambda = \text{arc}/R$ whichever endpoint is
higher), V4 elevation above the horizontal at the lower endpoint (`elevation_angle_rad`,
signed: $\zeta_{low} = \pi/2 - \varepsilon$), and V6 circular orbit (ground speed and
period from the sensor altitude). Every entered viewing angle is referenced to the path's
**lower** endpoint — exactly what it always meant when the sensor was above the target;
when the sensor is the lower endpoint, $\theta_o = \pi - \zeta_{up}$ is derived and the
published mode label says so. The **solar** family resolves to $\theta_s, \Delta\phi$:
S0 night (thermal-only), S1 direct zenith, S2 elevation, S3 site and time (latitude, day
of year, local solar time or LTAN → declination and hour angle). The **LOS-rate** family
resolves to $\omega$: K0 platform-only $\omega = v_g/R_s$ (the default), K1 direct rate,
K2 target velocity $\omega = |\mathbf v_{rel,\perp}|/R_s$ with
$\mathbf v_{rel} = \mathbf v_{target} - \mathbf v_{sensor}$.

**Resolution rules.** Redundant entries for one canonical quantity must agree within 1 %
(1 µrad absolute floor for angles) or the stage raises, naming every entry and the value
it implies; every derived quantity is published with its mode label; no entries at all
gives the documented defaults (nadir view, 0.5 rad solar zenith by day) — never a silent
NaN.

**LOS direction and scene class.** Up, down or level follows from the two altitudes and
$\theta_o$ — never a user switch. The canonical $\theta_o$ lives on $[0, \pi)$:
below $\pi/2$ the sensor is above the target's horizon plane (every classic scene), above
it the sensor is below — the same Earth-centre / target / sensor triangle read from the
other vertex. The scene class is the observer × target band: **ground** ($h < 1$ km),
**air** ($1 \le h \le 100$ km) and **space** ($h > 100$ km, the atmosphere-top
convention), both boundaries closed from below. Physics never branches on the class — a
scene at 999 m and one at 1001 m compute identically — it drives defaults, metric
relevance, validation and the GUI composition only. `geometry.scene_class` is an optional
assertion cross-checked against the derivation: what it catches is a wrong-magnitude
altitude (600 m typed for 600 km), which pure derivation would render as a self-consistent
scene of the wrong class. The **horizon guard** refuses $|\theta_o - \pi/2| < 0.5°$
(refraction, unmodelled, dominates there) and computes between 0.5° and ~2° with a warning.
`geometry.site_elevation_m` is a *third* altitude — the terrain under the line of sight —
not an input mode; the Hufnagel-Valley surface term (atmosphere chapter) is its consumer,
and the terrain-bearing endpoint must sit at or above it.

**Pitfalls.** Entering the sensor's own zenith as V1 for an up-looking scene and expecting
it to be $\theta_o$ (V1 is the lower endpoint's zenith, so it *is* the sensor's there and
$\theta_o = \pi - \zeta$ follows); ground range typed where slant range was meant; two
doors set, one of them stale, which the 1 % rule reports rather than resolves.

**Numeric anchors.** V4 with $\varepsilon = -10°$ at the lower endpoint:
$\zeta_{low} = 100°$. A level chord $d = 200$ km at $r = R + 5$ km:
$\varphi = 2\arcsin(100/6376) = 1.7973°$, $\theta_o = 90.8987°$.

**In RADIANT.** `geometry/modes.py` (`resolve_viewing`, `resolve_solar`,
`resolve_kinematics`, `resolve_los_rate`, `viewing_direction`),
`geometry/scene_class.py`, `geometry/mode_manifest.py`, `core/viewing_triangle.py`
(symmetric solutions) · anchored by `geometry/tests/test_modes.py`,
`test_scene_class.py`, `test_mode_manifest.py`, `test_mode_guard.py`.
**References.** [Wertz & Larson 1999].
