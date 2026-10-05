"""Display metadata for the bundled substrate library (Gap 142, plan §9.1).

``radiant.gui`` may import ``radiant.api`` and ``radiant.core`` only, so this is the
GUI's window into :mod:`radiant.data.substrate` — a read-only projection, exactly as
:func:`radiant.api.fpa_preset.available_fpa_parts` is for the FPA part library.

The projection deliberately carries the **confidence tier** and the **anchor count**,
not just the name. A substrate picker that lists germanium beside ZnSe without saying
that one rests on three published absorption anchors and the other on five would be
hiding the single most important thing about this library: α data quality varies by
orders of magnitude between materials, and the user choosing the material is the only
one positioned to decide whether that matters for their analysis.

It also re-exports :func:`entry_supports_substrate`, the io parser's own predicate for
"can a named substrate reach the answer on this entry". The GUI needs that to decide
whether to offer the picker at all, and must read the **parser's** answer rather than
restate the rule: the two disagreed when this door landed, and a substrate named on a
simple refractive row was accepted, saved, and silently ignored.
"""

from __future__ import annotations

from dataclasses import dataclass

from radiant.data.substrate import SubstrateLibrary
from radiant.io.element_config import entry_supports_substrate

__all__ = ["SubstrateInfo", "available_substrates", "entry_supports_substrate"]


@dataclass(frozen=True)
class SubstrateInfo:
    """Display metadata for one library substrate.

    Attributes
    ----------
    name:
        Canonical library name, as a config's ``substrate:`` key takes it.
    formula:
        Chemical formula, for the label an optical engineer actually reads ("Ge").
    tier:
        ``"A"`` — alpha from five or six published laser-line anchors spanning the
        band. ``"B"`` — one to three anchors with modelled shape between them, shipped
        because an analyst cannot avoid the material.
    window_um:
        Published transparency window. Outside it the library refuses rather than
        extrapolating.
    reference_temperature_K:
        The temperature alpha is published at.
    valid_temperature_K:
        Declared validity window, where one is known, else ``None``.
    grade_sensitivity:
        Lot-to-lot or grade-to-grade spread in alpha, in the vendor's own words —
        silicon's exceeds 10x between CZ and FZ growth.
    """

    name: str
    display_name: str
    formula: str
    tier: str
    window_um: tuple[float, float]
    reference_temperature_K: float
    valid_temperature_K: tuple[float, float] | None
    grade_sensitivity: str

    @property
    def is_flagged(self) -> bool:
        """True for a tier-B material, whose alpha is class-typical rather than measured."""
        return self.tier.upper() == "B"

    @property
    def label(self) -> str:
        """Picker label: ``"Germanium (Ge)"``.

        Uses the material's declared ``display_name`` when it has one, because a few
        names do not survive title-casing — "zinc_sulphide_ms" is the multispectral
        grade, not a surname.
        """
        pretty = self.display_name or self.name.replace("_", " ").title()
        return f"{pretty} ({self.formula})" if self.formula else pretty


def available_substrates(*, library: SubstrateLibrary | None = None) -> tuple[SubstrateInfo, ...]:
    """Every library substrate as display metadata.

    Sorted **tier first, then name**, so a picker built by iterating this gets the
    measured materials above the flagged ones without encoding a roster of its own.
    """
    lib = library or SubstrateLibrary()
    infos = [
        SubstrateInfo(
            name=m.name,
            display_name=m.display_name,
            formula=m.formula,
            tier=m.tier,
            window_um=m.window_um,
            reference_temperature_K=m.reference_temperature_K,
            valid_temperature_K=m.valid_temperature_K,
            grade_sensitivity=m.grade_sensitivity,
        )
        for m in (lib.material(name) for name in lib.names())
    ]
    return tuple(sorted(infos, key=lambda i: (i.tier.upper(), i.name)))
