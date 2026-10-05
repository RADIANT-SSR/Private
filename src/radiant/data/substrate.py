"""Bundled optical-substrate material library (Gap 142).

A refractive element emits through the cavity model, which needs the bulk absorption
coefficient ``alpha`` [1/m]. That is a property of **germanium**, not of the
instrument: an analyst holding a lens drawing knows the material and the thickness, and
should not be expected to know the bulk absorption coefficient at 4.2 µm. This module
resolves a material *name* to that spectrum.

What the library is not
-----------------------
It is a convenience over the explicit inputs, never a replacement (plan §7.5, owner
requirement 2026-10-04). An analyst with their own measured alpha — a lot-specific CVD
coupon, a proprietary substrate, anything the shipped set does not carry — states
``alpha`` directly — a scalar, a CSV path, or an inline table — and gets identical
physics. The two doors resolve to the same
:class:`~radiant.optics.cavity_model.CavityModel`; naming a substrate *and*
giving an explicit alpha is an over-specified element and is refused at parse time.

``thickness_m`` is never part of a material. Thickness is a property of the lens.

Data confidence
---------------
Each material carries a ``tier``:

* **A** — alpha built from five or six published laser-line anchors spanning the useful
  band (ZnSe, CaF2, multispectral ZnS).
* **B** — one to three anchors, with modelled shape between them, shipped because an
  analyst cannot avoid the material: germanium *is* the LWIR refractive substrate and
  silicon the MWIR one. Their ``grade_sensitivity`` field states the lot-to-lot spread,
  which for silicon exceeds 10x between CZ and FZ growth.

The distinction is not cosmetic. The tabulated ``k(lambda)`` that dispersion databases
carry is a **null** inside a transparency window — Querry's ZnSe table reports
k = 0.0000000 from 2 to 14 µm, a floor three times the true absorption — so alpha cannot
be read from the same source as n, and the anchor count is the library's real quality
metric.

Temperature
-----------
alpha ships at a single reference temperature (293 K for most of the set). There is no
temperature axis in v1 because **no published alpha(lambda, T) exists to build one
from** — n(lambda, T) is published for germanium at nine temperatures; alpha is not.
Germanium carries a declared validity window and the caller is expected to enforce it;
outside it a 293 K alpha is wrong by more than the term it computes (+54 % at 230 K,
-38 % at 350 K), which is why that is an error rather than a caveat.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import numpy as np
import yaml

from radiant.core.exceptions import RadiantError

__all__ = ["Substrate", "SubstrateError", "SubstrateLibrary"]

_SUBSTRATE_ROOT: Final[Path] = Path(__file__).resolve().parent / "tables" / "substrates"

#: alpha is stored in the unit every substrate datasheet publishes it in.
_ALPHA_FILE_UNIT: Final[str] = "1/cm"
_CM_PER_M: Final[float] = 100.0


class SubstrateError(RadiantError):
    """A substrate could not be resolved, or its document is malformed.

    Carries the ``what`` / ``why`` / ``action`` shape every RADIANT error uses (Rule 15).
    The action line names the **custom-material path first**: a user who wants a
    substrate the library does not carry should be told they can state ``alpha`` and
    ``alpha`` directly before being told to file a capability gap.
    """

    def __init__(
        self,
        what: str,
        why: str = "",
        action: str = "",
        context: dict[str, Any] | None = None,
    ) -> None:
        self.what = what
        self.why = why
        self.action = action
        self.context = context or {}
        parts = [what]
        if why:
            parts.append(f"Why: {why}")
        if action:
            parts.append(f"Action: {action}")
        super().__init__(" | ".join(parts))


@dataclass(frozen=True)
class Substrate:
    """One resolved substrate material.

    ``wavelength_um`` / ``n_refr`` / ``alpha_per_m`` are the library's own sampling.

    ``n_refr`` is published dispersion the library keeps as **data**, not as a model
    input: the cavity has no index (CU-399). It is kept because it is real measured
    material data and the absorption figure plots it beside alpha.
    Use :meth:`resample` to put them on a chain grid.
    """

    name: str
    display_name: str
    formula: str
    tier: str
    window_um: tuple[float, float]
    reference_temperature_K: float
    grade_sensitivity: str
    wavelength_um: np.ndarray
    n_refr: np.ndarray
    alpha_per_m: np.ndarray
    valid_temperature_K: tuple[float, float] | None = None

    def resample(self, wavelength_um: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return ``(n_refr, alpha_per_m)`` on *wavelength_um*.

        n is interpolated linearly; alpha in **log-log**, which is how the published
        anchors were fitted and the only interpolation that keeps a multiphonon edge
        looking like a multiphonon edge — CaF2's alpha rises 4500x between 2.7 and
        10.6 µm, and a linear interpolant through that is not a curve, it is a chord.

        Raises
        ------
        SubstrateError
            If any requested wavelength lies outside the material's published window.
            Extrapolating a transparency window past its absorption edge is exactly
            where the answer goes wrong fastest, so it is refused (Rule 17).
        """
        grid = np.asarray(wavelength_um, dtype=np.float64)
        lo, hi = self.window_um
        outside = (grid < lo) | (grid > hi)
        if bool(np.any(outside)):
            worst = float(grid[np.argmax(np.abs(grid - np.clip(grid, lo, hi)))])
            raise SubstrateError(
                what=(
                    f"substrate {self.name!r} has no data at {worst:g} µm "
                    f"(published window {lo:g}-{hi:g} µm)"
                ),
                why=(
                    "outside its window the material is past an absorption edge, where "
                    "alpha changes by orders of magnitude over a short span — an "
                    "extrapolated value there is not an approximation, it is a "
                    "different material"
                ),
                action=(
                    f"Restrict the spectral grid to {lo:g}-{hi:g} µm, choose a substrate "
                    "whose window covers the band, or state alpha explicitly "
                    "on the element."
                ),
                context={"substrate": self.name, "window_um": self.window_um},
            )
        n = np.interp(grid, self.wavelength_um, self.n_refr)
        # Guard the log: a published alpha can legitimately be ~1e-5 cm^-1 but never 0.
        alpha = np.exp(
            np.interp(np.log(grid), np.log(self.wavelength_um), np.log(self.alpha_per_m))
        )
        return n, alpha


class SubstrateLibrary:
    """Access to the bundled substrate library.

    Parameters
    ----------
    data_root:
        Override path to the substrate directory. Defaults to the bundled
        ``tables/substrates/`` inside the package.
    """

    def __init__(self, data_root: Path | None = None) -> None:
        self._root = Path(data_root) if data_root is not None else _SUBSTRATE_ROOT

    def names(self) -> list[str]:
        """Sorted canonical names of the available substrates."""
        if not self._root.is_dir():
            return []
        return sorted(p.stem for p in self._root.glob("*.yaml"))

    def material(self, name: str) -> Substrate:
        """Load the substrate called *name*, accepting its declared aliases.

        Raises
        ------
        SubstrateError
            If no substrate of that name exists, or its document is malformed.
        """
        canonical = self._resolve_name(name)
        meta = yaml.safe_load((self._root / f"{canonical}.yaml").read_text(encoding="utf-8"))
        table = self._root / f"{canonical}.csv"
        if not table.is_file():
            raise SubstrateError(
                what=f"substrate {canonical!r} has metadata but no spectral table",
                why=f"{table.name} is missing from the bundled library",
                action="Reinstall the package, or report this as a packaging defect.",
                context={"substrate": canonical},
            )
        wl, n, alpha_cm = self._read_table(table)
        window = meta.get("window_um") or [float(wl[0]), float(wl[-1])]
        valid_t = meta.get("valid_temperature_K")
        return Substrate(
            name=canonical,
            display_name=str(meta.get("display_name", "")),
            formula=str(meta.get("formula", "")),
            tier=str(meta.get("tier", "")),
            window_um=(float(window[0]), float(window[1])),
            reference_temperature_K=float(meta.get("reference_temperature_K", 293.0)),
            grade_sensitivity=str((meta.get("alpha") or {}).get("grade_sensitivity", "")),
            wavelength_um=wl,
            n_refr=n,
            alpha_per_m=alpha_cm * _CM_PER_M,
            valid_temperature_K=(
                (float(valid_t[0]), float(valid_t[1])) if valid_t is not None else None
            ),
        )

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _resolve_name(self, name: str) -> str:
        key = str(name).strip().lower().replace(" ", "_")
        available = self.names()
        if key in available:
            return key
        for candidate in available:
            meta = yaml.safe_load((self._root / f"{candidate}.yaml").read_text(encoding="utf-8"))
            aliases = {str(a).strip().lower().replace(" ", "_") for a in meta.get("aliases", [])}
            if key in aliases or key == str(meta.get("formula", "")).lower():
                return candidate
        raise SubstrateError(
            what=f"unknown substrate {name!r}",
            why=f"the bundled library carries {', '.join(available) or 'no materials'}",
            action=(
                "State the material's alpha explicitly on the element — a scalar, a CSV "
                "path, or an inline table — the "
                "named library is a convenience over that path, not a replacement — or "
                "pick one of the names above. If the material is a common one that "
                "should ship, file a gap against the substrate library."
            ),
            context={"requested": name, "available": available},
        )

    @staticmethod
    def _read_table(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        wl: list[float] = []
        n: list[float] = []
        alpha: list[float] = []
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                wl.append(float(row["wavelength_um"]))
                n.append(float(row["n_refr"]))
                alpha.append(float(row["alpha_cm_inv"]))
        return np.asarray(wl), np.asarray(n), np.asarray(alpha)
