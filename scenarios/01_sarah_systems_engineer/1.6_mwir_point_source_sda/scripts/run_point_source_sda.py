"""1.6 MWIR Point-Source SDA runner — reproduces the walkthrough numbers.

Loads the point-source config and evaluates it, then sweeps the emitting area to
show the linear-in-intensity, inverse-square-in-range point-source behavior. All
outputs carry units. Guarded with ``if __name__ == '__main__'`` so importing this
module for its config factory has no side effects (CU-164 lesson).
"""

from __future__ import annotations

from pathlib import Path

from radiant.api.sensor import Sensor

_CONFIG = (
    Path(__file__).resolve().parents[1] / "inputs" / "1.6_mwir_point_source_sda.yaml"
)


def load_sensor() -> Sensor:
    """The scenario's baseline point-source sensor (importable, side-effect-free)."""
    return Sensor.from_yaml(_CONFIG)


def main() -> None:
    sensor = load_sensor()
    result = sensor.evaluate()

    regime = result.stage_outputs["optics"]["regime"]
    snr = result.metrics["snr"]
    det_km = result.metrics["detection_range_m"] / 1000.0
    signal_e = result.stage_outputs["readout"]["signal_e_final"]
    q = result.metrics["q_center"]

    print("=== 1.6 MWIR Point-Source SDA — baseline ===")
    print(f"  regime            : {getattr(regime, 'value', regime)}")
    print(f"  signal            : {signal_e:,.0f} e-")
    print(f"  SNR               : {snr:.2f} (dimensionless)")
    print(f"  detection range   : {det_km:.1f} km (at SNR = 6.0)")
    print(f"  sampling Q_center : {q:.2f} (dimensionless)")

    print("\n=== Emitting-area sweep (linear in intensity) ===")
    print(f"  {'A_emit [m^2]':>12} {'SNR':>8} {'signal [e-]':>14}")
    base_area = sensor.get_input("source.target.point_intensity_area_m2")
    for scale in (0.5, 1.0, 2.0, 4.0):
        s = load_sensor()
        s.set("source.target.point_intensity_area_m2", base_area * scale)
        r = s.evaluate()
        print(
            f"  {base_area * scale:12.1f} {r.metrics['snr']:8.2f} "
            f"{r.stage_outputs['readout']['signal_e_final']:14,.0f}"
        )


if __name__ == "__main__":
    main()
