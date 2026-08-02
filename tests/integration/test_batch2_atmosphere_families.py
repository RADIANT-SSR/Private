"""Integration: the batch-2 MODTRAN delivery — new families, CU-181, ex-CU-223.

The batch-2 run set (``docs/plans/modtran_run_matrix.csv`` rows M1–Q8, delivered
2026-08-02, 35 of the 37 authored rows — Q5/Q6 gated on a real refraction
switch) is ingested by ``scripts/build_atmosphere_library.py`` into four new
families plus an altitude-resolved ``atm_emission_down`` on the pre-existing
down-looking ones.  This module owns the ingestion contract:

1. **ex-CU-223 — the deck-geometry convention.**  Every batch-2 row's delivered
   Card-3 echo must match the run matrix, and every family builder must key its
   nodes to the matrix's ``path_zenith_deg_radiant`` — the **lower-endpoint**
   zenith — never to a sensor-referenced ``los.theta_o``.  The two differ by
   180° for a down-looking row, which is precisely the trap CU-223 filed.
2. **The new families load and query**, node-exact and off-node, with the
   zenith axis interpolating in ``sec(ζ)`` space (CU-160).
3. **CU-181 — the downwelling is altitude-resolved**, and the measured decay is
   pinned against the entry's own analytic table.

Pinned values are band means of the slit-degraded (5 cm⁻¹ FWHM) library
content, measured 2026-08-02 from the delivered tape7s.  Both sides are pinned
(the value and, where a ratio is the physics, the ratio), so an unexplained
improvement fails too and forces this record to be updated.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np
import pytest

from radiant.atmosphere.errors import AtmosphereValidationError
from radiant.atmosphere.interpolated import (
    UPLOOKING_RADIANCE_KEY,
    GeometryPoint,
    InterpolatedAtmosphere,
)
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.spectral import SpectralData

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_RUNS = _REPO_ROOT / "modtran" / "real_runs"
_MATRIX_CSV = _REPO_ROOT / "docs" / "plans" / "modtran_run_matrix.csv"
_LIB = _REPO_ROOT / "src" / "radiant" / "data" / "tables" / "atmospheres"

#: Card-3 echo line index in a delivered MODTRAN 6 tape7 (0-based), as used by
#: ``tests/integration/test_uplooking_horizontal_anchors.py``.
_CARD3_ECHO_LINE = 5

#: The batch-2 block letters and the number of rows delivered for each.
_BATCH2_BLOCKS = {"M": 8, "N": 10, "O": 5, "P": 6, "Q": 6}
_BATCH2_DELIVERED = sum(_BATCH2_BLOCKS.values())  # 35 (Q5/Q6 not run)

_DEG = math.pi / 180.0


def _matrix_rows() -> dict[str, dict[str, str]]:
    with _MATRIX_CSV.open(encoding="utf-8") as handle:
        return {row["run_id"]: row for row in csv.DictReader(handle)}


def _is_batch2(run_id: str) -> bool:
    return run_id[0] in _BATCH2_BLOCKS and run_id[1:].isdigit()


def _card3_echo(run: str) -> list[float]:
    """``[H1, H2, ANGLE, RANGE, ...]`` [km, km, deg, km] from a tape7 echo."""
    line = (_REAL_RUNS / f"{run}.tp7").read_text(encoding="utf-8").splitlines()[_CARD3_ECHO_LINE]
    return [float(token) for token in line.split()]


def _band_mean(wl: np.ndarray, values: np.ndarray, lo: float, hi: float) -> float:
    band = (wl >= lo) & (wl <= hi)
    return float(np.trapezoid(values[band], wl[band]) / (hi - lo))


def _uplooking_family(subdir: str, axes: list[str]) -> InterpolatedAtmosphere:
    """Load a shipped up-looking family the way ``loaders._build_interpolated`` does."""
    points: list[GeometryPoint] = []
    for npz_file in sorted((_LIB / subdir).glob("*.npz")):
        with np.load(npz_file, allow_pickle=True) as data:
            coords = data["geometry"].item()
            wl = np.asarray(data["wavelength_um"], dtype=np.float64)
            tau = np.asarray(data["transmittance"], dtype=np.float64)
            l_down = np.asarray(data[UPLOOKING_RADIANCE_KEY], dtype=np.float64)
        points.append(
            GeometryPoint(
                coordinates=coords,
                transmittance=SpectralData(
                    name="tau", wavelength_um=wl.copy(), values=tau, unit="", source=str(npz_file)
                ),
                path_radiance=SpectralData(
                    name="L_toward_lower",
                    wavelength_um=wl.copy(),
                    values=l_down,
                    unit="W/m²/sr/µm",
                    source=str(npz_file),
                ),
                atm_emission_down=SpectralData(
                    name="unused",
                    wavelength_um=wl.copy(),
                    values=np.zeros_like(wl),
                    unit="W/m²/sr/µm",
                    source=str(npz_file),
                ),
            )
        )
    return InterpolatedAtmosphere(points, axes=axes, family_direction="up")


def _node_geometries(subdir: str) -> list[dict[str, float]]:
    out: list[dict[str, float]] = []
    for npz_file in sorted((_LIB / subdir).glob("*.npz")):
        with np.load(npz_file, allow_pickle=True) as data:
            out.append(dict(data["geometry"].item()))
    return out


# ---------------------------------------------------------------------------
# 1. ex-CU-223 — the lower-endpoint deck-geometry convention, on ingestion
# ---------------------------------------------------------------------------


@pytest.mark.level2
def test_every_batch2_row_was_delivered_or_is_a_recorded_gap() -> None:
    """35 of 37 batch-2 rows landed; every undelivered row is a *recorded* gap.

    Two recorded shapes exist: the Q5/Q6 refraction pair (not runnable
    without a ray-bending switch, ``deck_builder_support`` says so) and
    owner-ratified FUTURE RUN rows authored after the delivery (P7/P8, the
    CU-181 closure's 60/80 km downwelling rungs), which carry the literal
    ``FUTURE RUN`` marker in their notes column. Anything else missing is a
    delivery regression.
    """
    rows = _matrix_rows()
    authored = sorted(rid for rid in rows if _is_batch2(rid))
    delivered = [rid for rid in authored if (_REAL_RUNS / f"{rid}.tp7").exists()]
    missing = sorted(set(authored) - set(delivered))
    assert len(delivered) == _BATCH2_DELIVERED, f"batch-2 delivery changed: {len(delivered)} runs"
    for run_id in missing:
        recorded = (
            rows[run_id]["deck_builder_support"] == "refraction_toggle"
            or "FUTURE RUN" in rows[run_id]["notes"]
        )
        assert recorded, f"unrecorded missing batch-2 row: {run_id}"


@pytest.mark.level2
def test_batch2_card3_echoes_match_the_matrix_on_the_lower_endpoint_convention() -> None:
    """ex-CU-223 ingestion check, on all 35 delivered rows.

    The matrix carries two zenith columns and they are NOT the same number:

    * ``path_zenith_deg_radiant`` — the **lower-endpoint** zenith, the value
      RADIANT records as a family node's ``path_zenith_rad``;
    * ``modtran_angle_at_h1_deg`` — Card-3 ANGLE, measured at H1, which for a
      **down-looking** row (the O block) is ``180° − path_zenith_deg_radiant``
      and for an up-looking one (M/N/P) is the lower-endpoint zenith unchanged.

    Feeding ``los.theta_o`` straight into the deck — CU-223's defect — would
    have produced the up-looking number on the down-looking rows.  This asserts
    the delivered echoes carry the *converted* value where conversion applies,
    so the ingestion is reading real lower-endpoint geometry.
    """
    rows = _matrix_rows()
    checked = 0
    down_looking = 0
    for run_id, row in rows.items():
        if not _is_batch2(run_id) or not (_REAL_RUNS / f"{run_id}.tp7").exists():
            continue
        echo = _card3_echo(run_id)
        assert echo[0] == pytest.approx(float(row["h1_sensor_km"]), abs=1e-6), run_id
        assert echo[1] == pytest.approx(float(row["h2_target_km"]), abs=1e-6), run_id
        assert echo[2] == pytest.approx(float(row["modtran_angle_at_h1_deg"]), abs=1e-6), run_id

        zenith_str = row["path_zenith_deg_radiant"].strip()
        if zenith_str and int(row["itype"]) != 1:
            lower_endpoint_deg = float(zenith_str)
            if float(row["h1_sensor_km"]) > float(row["h2_target_km"]):
                # Down-looking: the sensor is the path's UPPER endpoint.
                assert echo[2] == pytest.approx(180.0 - lower_endpoint_deg, abs=1e-6), run_id
                assert echo[2] != pytest.approx(lower_endpoint_deg, abs=1e-3), run_id
                down_looking += 1
            else:
                # Up-looking: the sensor IS the lower endpoint — no conversion.
                assert echo[2] == pytest.approx(lower_endpoint_deg, abs=1e-6), run_id
        checked += 1
    assert checked == _BATCH2_DELIVERED, f"only {checked} batch-2 echoes compared"
    assert down_looking == 5, "the O block is the batch-2 down-looking set (5 rows)"


@pytest.mark.level2
def test_staged_itype1_rows_all_reproduce_their_delivered_range() -> None:
    """The Q1–Q4 horizontal probes join the L grid's ITYPE=1 Card-3 contract.

    ``test_uplooking_horizontal_anchors.py`` pins the L block by name; this
    sweeps **every** staged ITYPE=1 row, so a new horizontal row cannot land
    without its RANGE being compared against the matrix.
    """
    rows = _matrix_rows()
    checked = 0
    for run_id, row in rows.items():
        if int(row["itype"]) != 1 or not (_REAL_RUNS / f"{run_id}.tp7").exists():
            continue
        echo = _card3_echo(run_id)
        assert echo[0] == pytest.approx(float(row["h1_sensor_km"]), abs=1e-6), run_id
        assert echo[1] == pytest.approx(float(row["h2_target_km"]), abs=1e-6), run_id
        assert echo[2] == pytest.approx(90.0, abs=1e-6), run_id
        assert echo[3] == pytest.approx(float(row["hrange_km"]), abs=1e-6), run_id
        checked += 1
    assert checked >= 29, f"only {checked} ITYPE=1 rows compared — staged set shrank?"


@pytest.mark.level2
@pytest.mark.parametrize(
    ("family_map", "subdir"),
    [
        ("UPLOOKING_ZENITH_FAN", "midlat_summer_uplooking_zenith_fan"),
        ("SST_COLUMN_FAN", "midlat_summer_sst_column_fan"),
        ("UPLOOKING_SENSOR_LADDER", "midlat_summer_uplooking_sensor_ladder"),
        ("UPWELLING_OFFNADIR", "midlat_summer_upwelling_offnadir"),
    ],
)
def test_family_builders_key_their_nodes_to_the_matrix_lower_endpoint_zenith(
    family_map: str, subdir: str
) -> None:
    """ex-CU-223's ingestion residue: node geometry comes from the matrix.

    For every run the builder places in a family, the recorded NPZ
    ``path_zenith_rad`` must equal the matrix's ``path_zenith_deg_radiant`` —
    the lower-endpoint zenith — and NOT the Card-3 ANGLE the deck carries.  On
    the O block those two differ by 180°, so this cannot pass by coincidence.
    """
    from scripts import build_atmosphere_library as builder

    rows = _matrix_rows()
    mapping = getattr(builder, family_map)
    checked = 0
    for run, spec in mapping.items():
        if run not in rows:
            continue  # K/H/A/I/J runs from batch 1 are pinned by their own families
        row = rows[run]
        zenith_deg = spec[-1] if isinstance(spec, tuple) else 48.2
        if family_map == "UPLOOKING_SENSOR_LADDER":
            zenith_deg = builder.UPLOOKING_SENSOR_LADDER_ZENITH_DEG
        elif family_map == "SST_COLUMN_FAN":
            zenith_deg = spec
        matrix_zenith = float(row["path_zenith_deg_radiant"])
        assert zenith_deg == pytest.approx(matrix_zenith, abs=1e-6), (
            f"{run}: builder zenith {zenith_deg}° != matrix lower-endpoint {matrix_zenith}°"
        )
        if float(row["h1_sensor_km"]) > float(row["h2_target_km"]):
            card3 = float(row["modtran_angle_at_h1_deg"])
            assert zenith_deg == pytest.approx(180.0 - card3, abs=1e-6), run
        checked += 1
    assert checked >= 1

    # And the shipped NPZ files really carry those coordinates.
    recorded = {round(g["path_zenith_rad"] / _DEG, 4) for g in _node_geometries(subdir)}
    assert recorded, subdir
    assert max(recorded) <= 90.0, f"{subdir}: a node zenith exceeds 90° (sensor-referenced?)"


# ---------------------------------------------------------------------------
# 2. The new families load and query
# ---------------------------------------------------------------------------


class TestUplookingZenithFan:
    """N block + K block: targets 0-20 km × lower-endpoint zenith 0/48.2/60°."""

    _SUBDIR = "midlat_summer_uplooking_zenith_fan"
    _AXES = ["target_altitude_m", "path_zenith_rad"]

    @pytest.mark.level2
    def test_grid_is_rectangular_and_complete(self) -> None:
        geoms = _node_geometries(self._SUBDIR)
        targets = sorted({g["target_altitude_m"] for g in geoms})
        zeniths = sorted({round(g["path_zenith_rad"], 9) for g in geoms})
        assert targets == [0.0, 1000.0, 3000.0, 5000.0, 10_000.0, 20_000.0]
        assert len(zeniths) == 3
        assert [round(z / _DEG, 3) for z in zeniths] == [0.0, 48.2, 60.0]
        assert len(geoms) == len(targets) * len(zeniths) == 18
        assert all(g["sensor_altitude_m"] == 0.0 for g in geoms)

    @pytest.mark.level2
    def test_zenith_axis_is_a_uniform_sec_ladder(self) -> None:
        """sec ζ = 1.0 / 1.4999 / 2.0 — the CU-160 interpolation coordinate."""
        zeniths = sorted({round(g["path_zenith_rad"], 9) for g in _node_geometries(self._SUBDIR)})
        secs = [1.0 / math.cos(z) for z in zeniths]
        assert secs == pytest.approx([1.0, 1.4999, 2.0], abs=1e-3)

    @pytest.mark.level2
    def test_node_query_reproduces_the_stored_column(self) -> None:
        family = _uplooking_family(self._SUBDIR, self._AXES)
        with np.load(_LIB / self._SUBDIR / "t010_z48.2.npz", allow_pickle=True) as data:
            stored_tau = np.asarray(data["transmittance"], dtype=np.float64)
        product = family.uplooking_column_product(
            family.wavelength_um,
            LineOfSightGeometry(theta_o=math.pi - 48.2 * _DEG, h_tgt=10_000.0, h_sensor=0.0),
        )
        np.testing.assert_allclose(product.tau, stored_tau, rtol=1e-6, atol=1e-9)

    @pytest.mark.level2
    def test_the_off_vertical_query_the_k_ladder_refused_is_now_served(self) -> None:
        """GF-10's deferral closes: 48.2° and 60° up-looking are real nodes now."""
        family = _uplooking_family(self._SUBDIR, self._AXES)
        vertical = family.uplooking_column_product(
            family.wavelength_um,
            LineOfSightGeometry(theta_o=math.pi, h_tgt=10_000.0, h_sensor=0.0),
        )
        slant = family.uplooking_column_product(
            family.wavelength_um,
            LineOfSightGeometry(theta_o=math.pi - 60.0 * _DEG, h_tgt=10_000.0, h_sensor=0.0),
        )
        wl = family.wavelength_um
        tau_vert = _band_mean(wl, vertical.tau, 8.0, 12.0)
        tau_slant = _band_mean(wl, slant.tau, 8.0, 12.0)
        # Twice the air mass ⇒ strictly less transmittance, and more downwelling.
        assert tau_slant < tau_vert
        assert _band_mean(wl, slant.L_toward_lower, 8.0, 12.0) > _band_mean(
            wl, vertical.L_toward_lower, 8.0, 12.0
        )

    @pytest.mark.level2
    def test_off_node_zenith_interpolates_linearly_in_sec_space(self) -> None:
        """CU-160 by construction: the sec midpoint is the log-τ midpoint.

        ζ chosen so sec ζ is exactly halfway between the 48.2° and 60° nodes;
        log-τ linear in sec then makes the answer the geometric mean of the two
        node transmittances, to interpolator round-off.  A linear-in-angle
        interpolator would land elsewhere — this is the discriminating test.
        """
        family = _uplooking_family(self._SUBDIR, self._AXES)
        sec_lo, sec_hi = 1.0 / math.cos(48.2 * _DEG), 1.0 / math.cos(60.0 * _DEG)
        zeta_mid = math.acos(1.0 / (0.5 * (sec_lo + sec_hi)))
        wl = family.wavelength_um

        def tau_at(zeta_rad: float) -> np.ndarray:
            return family.uplooking_column_product(
                wl, LineOfSightGeometry(theta_o=math.pi - zeta_rad, h_tgt=5_000.0, h_sensor=0.0)
            ).tau

        mid = tau_at(zeta_mid)
        expected = np.sqrt(np.clip(tau_at(48.2 * _DEG), 1e-30, 1.0) * tau_at(60.0 * _DEG))
        np.testing.assert_allclose(mid, expected, rtol=1e-5, atol=1e-9)
        # The angle midpoint is a *different* zenith, so the two schemes differ.
        assert math.degrees(zeta_mid) == pytest.approx(55.1535, abs=1e-3)
        # The *angle* midpoint of 48.2° and 60° is 54.1° — a full degree away,
        # which is what makes this a discriminating test rather than a tautology.
        assert math.degrees(zeta_mid) - 54.1 == pytest.approx(1.0535, abs=1e-3)

    @pytest.mark.level2
    def test_beyond_the_zenith_hull_is_refused_not_extrapolated(self) -> None:
        family = _uplooking_family(self._SUBDIR, self._AXES)
        with pytest.raises(AtmosphereValidationError, match="outside the available range"):
            family.uplooking_column_product(
                family.wavelength_um,
                LineOfSightGeometry(theta_o=math.pi - 75.0 * _DEG, h_tgt=5_000.0, h_sensor=0.0),
            )


class TestSstColumnFan:
    """M block + H5: ground observer → the 100 km atmosphere top, sec 1…5."""

    _SUBDIR = "midlat_summer_sst_column_fan"
    _AXES = ["path_zenith_rad"]

    @pytest.mark.level2
    def test_the_sec_ladder_is_uniform_and_stops_at_sec_5(self) -> None:
        zeniths = sorted({round(g["path_zenith_rad"], 9) for g in _node_geometries(self._SUBDIR)})
        secs = [1.0 / math.cos(z) for z in zeniths]
        assert secs == pytest.approx([1.0, 1.5, 2.0, 3.0, 4.0, 5.0], abs=2e-3)

    @pytest.mark.level2
    def test_the_dev_only_near_horizon_rungs_are_not_shipped(self) -> None:
        """M6–M8 (85/88/89.5°) are physics anchors, not library nodes.

        Past the 88.8° airmass ceiling the sec-space mapping is unvalidated, so
        shipping them would put an unvalidated coordinate inside a hull the
        interpolator is allowed to traverse.
        """
        zeniths = [g["path_zenith_rad"] / _DEG for g in _node_geometries(self._SUBDIR)]
        assert max(zeniths) == pytest.approx(78.463, abs=1e-3)
        rows = _matrix_rows()
        for run in ("M6", "M7", "M8"):
            assert rows[run]["destination"] == "dev_only", run

    @pytest.mark.level2
    def test_full_column_transmittance_falls_monotonically_with_air_mass(self) -> None:
        family = _uplooking_family(self._SUBDIR, self._AXES)
        wl = family.wavelength_um
        previous = 1.0
        for zenith_deg in (0.0, 48.2, 60.0, 70.529, 75.522, 78.463):
            product = family.uplooking_column_product(
                wl,
                LineOfSightGeometry(
                    theta_o=math.pi - zenith_deg * _DEG, h_tgt=100_000.0, h_sensor=0.0
                ),
            )
            tau = _band_mean(wl, product.tau, 8.0, 12.0)
            assert tau < previous, zenith_deg
            previous = tau
        # sec 5 through the whole column: an opaque LWIR sky, but not zero.
        assert 0.0 < previous < 0.2

    @pytest.mark.level2
    def test_the_sec_1_node_is_the_m1_run_band_mean(self) -> None:
        """Node-exact against the delivered M1 tape7 (slit-degraded ≲0.003)."""
        family = _uplooking_family(self._SUBDIR, self._AXES)
        product = family.uplooking_column_product(
            family.wavelength_um,
            LineOfSightGeometry(theta_o=math.pi, h_tgt=100_000.0, h_sensor=0.0),
        )
        wl = family.wavelength_um
        assert _band_mean(wl, product.tau, 8.0, 12.0) == pytest.approx(0.582553, abs=5e-3)
        assert _band_mean(wl, product.tau, 3.5, 4.1) == pytest.approx(0.779188, abs=5e-3)


class TestUplookingSensorLadder:
    """P block + H5: an elevated observer's full column at the 48.2° angle."""

    _SUBDIR = "midlat_summer_uplooking_sensor_ladder"
    _AXES = ["sensor_altitude_m"]

    @pytest.mark.level2
    def test_rungs_are_the_p_block_plus_the_zero_length_top(self) -> None:
        geoms = _node_geometries(self._SUBDIR)
        sensors = sorted(g["sensor_altitude_m"] / 1000.0 for g in geoms)
        assert sensors == [0.0, 1.0, 5.0, 10.0, 20.0, 29.0, 50.0, 100.0]
        assert all(g["target_altitude_m"] == 100_000.0 for g in geoms)
        assert all(g["path_zenith_rad"] == pytest.approx(48.2 * _DEG, abs=1e-9) for g in geoms)

    @pytest.mark.level2
    def test_the_column_thins_with_observer_altitude_and_closes_at_the_top(self) -> None:
        family = _uplooking_family(self._SUBDIR, self._AXES)
        wl = family.wavelength_um
        previous = 0.0
        for sensor_km in (0.0, 1.0, 5.0, 10.0, 20.0, 29.0, 50.0):
            product = family.uplooking_column_product(
                wl,
                LineOfSightGeometry(
                    theta_o=math.pi - 48.2 * _DEG,
                    h_tgt=100_000.0,
                    h_sensor=sensor_km * 1000.0,
                ),
            )
            tau = _band_mean(wl, product.tau, 8.0, 12.0)
            assert tau > previous, sensor_km
            previous = tau
        assert previous > 0.99
        # The top rung is the zero-length identity. It is asserted on the stored
        # node, not through a query: an observer AT the target altitude is a
        # LEVEL line of sight, which uplooking_column_product refuses (and the
        # horizon guard rejects long before that) — the node exists to close the
        # hull for queries approaching it, not to be queried itself.
        with np.load(_LIB / self._SUBDIR / "s100.npz", allow_pickle=True) as data:
            assert np.all(np.asarray(data["transmittance"]) == 1.0)
            assert np.all(np.asarray(data[UPLOOKING_RADIANCE_KEY]) == 0.0)

    @pytest.mark.level2
    def test_an_off_angle_query_is_refused_because_the_ladder_has_no_zenith_axis(self) -> None:
        """The generalised fixed-zenith refusal: this family is a 48.2° ladder."""
        family = _uplooking_family(self._SUBDIR, self._AXES)
        with pytest.raises(AtmosphereValidationError) as excinfo:
            family.uplooking_column_product(
                family.wavelength_um,
                LineOfSightGeometry(theta_o=math.pi, h_tgt=100_000.0, h_sensor=10_000.0),
            )
        message = str(excinfo.value)
        assert "48.2000" in message
        assert "midlat_summer_sst_column_fan" in message
        assert "VERTICAL" not in message  # this one is NOT a vertical ladder


class TestUpwellingOffnadir:
    """O block + J1/A3/I5: down-looking ground-target grid (sensor × zenith)."""

    _SUBDIR = "midlat_summer_upwelling_offnadir"

    @pytest.mark.level2
    def test_grid_is_rectangular_over_sensor_and_zenith(self) -> None:
        geoms = _node_geometries(self._SUBDIR)
        sensors = sorted({g["sensor_altitude_m"] / 1000.0 for g in geoms})
        zeniths = sorted({round(g["path_zenith_rad"] / _DEG, 3) for g in geoms})
        assert sensors == [10.0, 100.0, 40_000.0]
        assert zeniths == [0.0, 48.2, 60.0]
        assert len(geoms) == 9
        assert all(g["target_altitude_m"] == 0.0 for g in geoms)

    @pytest.mark.level2
    def test_the_zenith_is_the_ground_endpoint_value_not_the_deck_angle(self) -> None:
        """Every recorded zenith is ≤ 90°; the decks carry 180° − that."""
        for geom in _node_geometries(self._SUBDIR):
            assert 0.0 <= geom["path_zenith_rad"] <= math.pi / 2.0

    @pytest.mark.level2
    def test_transmittance_falls_with_zenith_at_each_sensor_altitude(self) -> None:
        from radiant.atmosphere.protocol import AtmosphericGeometry
        from radiant.atmosphere.tabulated import TabulatedAtmosphere

        points: list[GeometryPoint] = []
        for npz_file in sorted((_LIB / self._SUBDIR).glob("*.npz")):
            with np.load(npz_file, allow_pickle=True) as data:
                coords = dict(data["geometry"].item())
            tab = TabulatedAtmosphere.from_npz(npz_file)
            points.append(
                GeometryPoint(
                    coordinates=coords,
                    transmittance=tab.transmittance_data,
                    path_radiance=tab.path_radiance_data,
                    atm_emission_down=tab.atm_emission_down_data,
                )
            )
        model = InterpolatedAtmosphere(points, axes=["sensor_altitude_m", "path_zenith_rad"])
        wl = model.wavelength_um
        for sensor_m in (10_000.0, 100_000.0):
            taus = [
                _band_mean(
                    wl,
                    model.build_state(
                        wl,
                        AtmosphericGeometry(
                            sensor_altitude_m=sensor_m,
                            target_altitude_m=0.0,
                            path_zenith_rad=zenith_deg * _DEG,
                            solar_zenith_rad=30.0 * _DEG,
                            solar_azimuth_rad=0.0,
                        ),
                    ).transmittance.values,
                    8.0,
                    12.0,
                )
                for zenith_deg in (0.0, 48.2, 60.0)
            ]
            assert taus[0] > taus[1] > taus[2], sensor_m


# ---------------------------------------------------------------------------
# 3. CU-181 — altitude-resolved downwelling
# ---------------------------------------------------------------------------


class TestCu181AltitudeDependentDownwelling:
    #: Measured 2026-08-02 from the shipped boost-ladder NPZs: 3-5 µm and
    #: 8-12 µm band-mean ``atm_emission_down`` [W/m²/sr/µm] per target rung,
    #: and the decay ratio to the ground rung.
    _EXPECTED = {
        0: (5.284379e-01, 3.726067e00, 1.000, 1.000),
        1: (3.742912e-01, 2.203498e00, 1.412, 1.691),
        5: (7.469476e-02, 3.680689e-01, 7.075, 10.12),
        10: (1.015924e-02, 1.769970e-01, 52.02, 21.05),
        20: (3.787847e-03, 1.335638e-01, 139.5, 27.90),
        29: (5.089107e-03, 8.748766e-02, 103.8, 42.59),
        35: (4.343333e-03, 4.425610e-02, 121.7, 84.19),
        40: (3.999377e-03, 2.529624e-02, 132.1, 147.3),
        50: (3.709306e-03, 8.426179e-03, 142.5, 442.2),
        60: (3.387948e-03, 2.865881e-03, 156.0, 1300.0),
        80: (3.021602e-03, 3.471554e-04, 174.9, 1.073e4),
    }

    def _rungs(self) -> dict[int, tuple[np.ndarray, np.ndarray]]:
        out: dict[int, tuple[np.ndarray, np.ndarray]] = {}
        for npz_file in sorted((_LIB / "midlat_summer_boost_ladder").glob("s00100_*.npz")):
            with np.load(npz_file, allow_pickle=True) as data:
                wl = np.asarray(data["wavelength_um"], dtype=np.float64)
                ld = np.asarray(data["atm_emission_down"], dtype=np.float64)
                target_km = int(round(data["geometry"].item()["target_altitude_m"] / 1000.0))
            out[target_km] = (wl, ld)
        return out

    @pytest.mark.level2
    def test_the_constant_is_gone(self) -> None:
        """CU-181's reproduction, inverted: the family had ONE distinct value."""
        distinct = {ld.tobytes() for _wl, ld in self._rungs().values()}
        assert len(distinct) == 12, "every boost target rung must carry its own downwelling"

    @pytest.mark.level2
    def test_the_ground_rung_is_byte_identical_to_the_h5_value(self) -> None:
        """Zero movement where the fix does not apply: ground targets."""
        wl, ground = self._rungs()[0]
        for family, pattern in (
            ("midlat_summer_ladders", "s00100_t00.npz"),
            ("midlat_summer_sensor_ladder", "s00100.npz"),
            ("midlat_summer_upwelling_offnadir", "s00100_z00.0.npz"),
        ):
            with np.load(_LIB / family / pattern, allow_pickle=True) as data:
                np.testing.assert_array_equal(data["atm_emission_down"], ground), family

    @pytest.mark.level2
    @pytest.mark.parametrize("target_km", sorted(_EXPECTED))
    def test_measured_downwelling_per_rung(self, target_km: int) -> None:
        wl, ld = self._rungs()[target_km]
        _wl0, ground = self._rungs()[0]
        m35, m812 = _band_mean(wl, ld, 3.0, 5.0), _band_mean(wl, ld, 8.0, 12.0)
        g35, g812 = _band_mean(wl, ground, 3.0, 5.0), _band_mean(wl, ground, 8.0, 12.0)
        want35, want812, ratio35, ratio812 = self._EXPECTED[target_km]
        assert m35 == pytest.approx(want35, rel=1e-3), f"{target_km} km, 3-5 µm"
        assert m812 == pytest.approx(want812, rel=1e-3), f"{target_km} km, 8-12 µm"
        assert g35 / m35 == pytest.approx(ratio35, rel=2e-3)
        assert g812 / m812 == pytest.approx(ratio812, rel=2e-3)

    @pytest.mark.level2
    def test_the_atmosphere_top_rung_is_the_exact_zero_identity(self) -> None:
        """An observer AT 100 km has no sky above it — CU-181's worst case."""
        _wl, ld = self._rungs()[100]
        assert np.all(ld == 0.0)

    @pytest.mark.level2
    def test_the_measured_decay_falls_far_short_of_the_entry_criterion(self) -> None:
        """CU-181's ≳10⁴ acceptance criterion is NOT met — and should not be.

        The entry's decay table was computed from ``SimpleAtmosphere``'s own
        ``E_sky_thermal``, i.e. from RADIANT rather than from an independent
        reference (Rule 18's warning, in the wild).  MODTRAN says the real
        midlat_summer downwelling falls **142×** (3-5 µm) and **442×**
        (8-12 µm) across 0 → 50 km, one-to-two orders less than the entry
        predicted, because the parametric model's water-dominated column
        collapses far faster than the real stratospheric CO₂/O₃ emission does.
        Pinned as a failing criterion on purpose: the number to argue with is
        the measurement, not the model that produced the criterion.
        """
        rungs = self._rungs()
        wl, ground = rungs[0]
        _wl50, top = rungs[50]
        decay_mwir = _band_mean(wl, ground, 3.0, 5.0) / _band_mean(wl, top, 3.0, 5.0)
        decay_lwir = _band_mean(wl, ground, 8.0, 12.0) / _band_mean(wl, top, 8.0, 12.0)
        assert decay_mwir == pytest.approx(142.5, rel=5e-3)
        assert decay_lwir == pytest.approx(442.2, rel=5e-3)
        assert decay_mwir < 1.0e4 and decay_lwir < 1.0e4
        # But it is an enormous improvement on the constant it replaces.
        assert decay_mwir > 100.0

    @pytest.mark.level2
    def test_downwelling_is_non_increasing_above_the_measured_span(self) -> None:
        """No residual column gains emitters with altitude (the slope clamp)."""
        rungs = self._rungs()
        _wl, top_measured = rungs[50]
        for target_km in (60, 80):
            _w, ld = rungs[target_km]
            assert np.all(ld <= top_measured + 1e-12), target_km

    @pytest.mark.level2
    def test_the_mwir_rise_at_29_km_is_preserved_not_smoothed_away(self) -> None:
        """The stratospheric CO₂/O₃ layers really do brighten the 3-5 µm sky.

        A monotone-decay model would have hidden this; the interpolation makes
        no monotonicity assumption, so the measured 20 km → 29 km rise survives.
        """
        rungs = self._rungs()
        wl, at20 = rungs[20]
        _w, at29 = rungs[29]
        assert _band_mean(wl, at29, 3.0, 5.0) > _band_mean(wl, at20, 3.0, 5.0)
        # LWIR, where water dominates, still falls.
        assert _band_mean(wl, at29, 8.0, 12.0) < _band_mean(wl, at20, 8.0, 12.0)
