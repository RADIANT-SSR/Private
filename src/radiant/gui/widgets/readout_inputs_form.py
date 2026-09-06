"""The Readout stage's **Inputs** section — noise / ADC / well / acquisition knobs.

:class:`ReadoutInputsForm` is the *Inputs* section of the Readout stage's contextual center
(arch doc §4.4 section 1, GUI plan Phase PS-5, expanded per Gap 102). The form shows the
readout-chain parameters — per-frame read noise, ADC conversion gain + bit depth, full-well
capacity, and (Gap 102, 2026-07-24) the acquisition knobs: TDI (``n_tdi`` / ``tdi_mode`` /
``tdi_misalign_pixels``), co-adding (``n_coadds`` / ``coadd_mode``), on/off-chip binning,
and frame timing (``frame_period_s`` beside the shared integration time) — as editable
schema-driven rows, beside the scalar outputs (``signal_dn_final``, ``sigma_total_e``,
``duty_cycle``, …) and the scalar noise budget. It is the readout sibling of
:class:`~radiant.gui.widgets.detector_inputs_form.DetectorInputsForm`: edit the TDI stage
count or the gain and watch the noise budget and the DN output respond on the next
evaluation.

**The grouping.** Architecture / Digital counting / Read noise / ADC / Full well / TDI /
Co-adds / Binning / Acquisition headings are a presentation choice only, no schema change —
the sensor dot-paths are the schema names verbatim — mirroring the Spectral-Integration
form's grouped layout. The remaining readout schema parameters (``cds_enabled``,
``node_capacitance_F``, ``electronics_sigma_um``) stay tree/YAML/scripting-only by scope
(Gap 102 suggested fix).

**Architecture-contextual visibility (Gap 117, plan Phase 3).** The *Digital counting*
group shows only under ``readout.architecture = "digital_counting"``, and the
``full_well_capacity_e`` / ``gain_e_per_dn`` rows hide there — the form mirrors the
stage's Rule-16 validation (counting rows under analog are an over-specification error;
an explicit FWC under counting is rejected; the DN gain derives from the packet per
ruling D2) instead of inviting a rejected edit. ``adc_bits`` stays visible under counting
as the residue-ADC depth. Visibility re-applies on every :meth:`refresh`, so an
architecture edit flips the groups on the next repaint.

**Schema-driven, one API call per edit (Gap 70 / R-API).** Every field is built from and
formatted through the public :class:`~radiant.api.sensor.Sensor` surface; editing a field
opens the shared
:class:`~radiant.gui.widgets.parameter_editor_dialog.ParameterEditorDialog`, so a commit is
exactly one ``sensor.set`` validated on a throwaway clone first (a rejected value never
touches the live sensor; the actionable what/why/action shows inline) — the identical
edit+reject discipline as the parameter tree (Phase 2), the Geometry Inputs form (Phase 5),
and the Source / Optics / Detector / Spectral-Integration Inputs forms (Phases PS-1..4). The
value shows in the row's **display unit**, sharing the parameter panel's session display-unit
store so a unit chosen on any surface agrees. Each accepted edit re-emits
:attr:`parameterEdited`, so the host debounces a full re-evaluation and the Outputs readout +
noise budget refresh (edit-and-watch).

Every field is the shared :class:`~radiant.gui.widgets.field_row.FieldRow` — the same
building block every other schema-driven field uses — so these inputs render **identically
by construction** to every other field (owner hard rule). All colour/typography comes from
the QSS theme via object names (GUI plan §4.9); this file holds no colour/font literal. One
widget class per file (Rule 19).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from radiant.core.exceptions import RadiantError
from radiant.gui.dialog_lifetime import exec_dialog
from radiant.gui.param_format import field_display_text
from radiant.gui.widgets.field_row import UNSET as _UNSET
from radiant.gui.widgets.field_row import FieldRow
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

# The read-noise knob (label, dot-path). Bounds/units/description all come from the live
# schema (never transcribed) — only the human label + the grouping is a literal here (CU-120,
# tracked with the geometry/source/optics/detector/spectral/platform manifests).
_NOISE_FIELDS: Final[tuple[tuple[str, str], ...]] = (("Read noise", "readout.read_noise_e_rms"),)

# Readout architecture selector (Gap 117, plan Phase 3): analog charge well vs
# digital-pixel (DROIC) counting. The enum edits through the shared editor's combo.
_ARCHITECTURE_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Architecture", "readout.architecture"),
)

# Digital-counting knobs (Gap 117). Shown ONLY under architecture =
# "digital_counting" (contextual-relevance convention) — the stage rejects them
# as over-specification under "analog_well", so the form must not invite them.
_COUNTING_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Counter depth", "readout.counter_bits"),
    ("Charge packet", "readout.count_packet_e"),
    ("Residue readout", "readout.residue_readout"),
    ("Max count rate", "readout.max_count_rate_hz"),
)

# Analog-only rows hidden under digital_counting: an explicit full well is
# rejected (the effective well is 2^N × packet) and the conversion gain is
# unused (DN gain derives from the packet per ruling D2). adc_bits stays
# visible — under counting it is the residue-ADC depth.
_ANALOG_ONLY_DOTPATHS: Final[frozenset[str]] = frozenset(
    {"readout.full_well_capacity_e", "readout.gain_e_per_dn"}
)

# The ADC knobs (conversion gain + bit depth).
_ADC_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Conversion gain", "readout.gain_e_per_dn"),
    ("ADC bit depth", "readout.adc_bits"),
)

# The full-well capacity (saturation) knob.
_WELL_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Full well capacity", "readout.full_well_capacity_e"),
)

# TDI knobs (Gap 102): stage count, accumulation mode (enum → combo in the shared
# editor), and cross-scan misalignment in pixels.
_TDI_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("TDI stages", "readout.n_tdi"),
    ("TDI mode", "readout.tdi_mode"),
    ("TDI misalignment", "readout.tdi_misalign_pixels"),
)

# Co-adding knobs (Gap 102): frame count and combination mode (enum → combo).
_COADD_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Co-added frames", "readout.n_coadds"),
    ("Co-add mode", "readout.coadd_mode"),
)

# Binning factors (Gap 102): on-chip (pre-read, read noise once) vs off-chip
# (post-read, read noise per binned pixel) — x/y each.
_BINNING_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("On-chip binning (x)", "readout.binning_x_onchip"),
    ("On-chip binning (y)", "readout.binning_y_onchip"),
    ("Off-chip binning (x)", "readout.binning_x_offchip"),
    ("Off-chip binning (y)", "readout.binning_y_offchip"),
)

# Acquisition timing. Integration time (owner request 2026-07-16) is the SAME parameter
# the Spectral Integration card edits — schema-owned by spectral_integration (Rule 8:
# t_int is consumed in the one spectral→scalar collapse), mirrored here because operators
# look for it beside the readout knobs; both surfaces edit the one dot-path and stay in
# sync through the shared refresh. Frame period (Gap 102) is readout-owned (R3.4 frame
# timing contract, Conventions §4): 0.0 = unset → defaults to t_int (duty cycle 1.0);
# the derived frame_rate_hz / duty_cycle appear in the stage's Outputs readout.
_ACQUISITION_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Integration time", "spectral_integration.integration_time_s"),
    ("Frame period", "readout.frame_period_s"),
)

_TITLE = "Readout — architecture, noise, ADC, well & acquisition"
_ARCHITECTURE_HEADING = "Architecture"
_COUNTING_HEADING = "Digital counting"
_NOISE_HEADING = "Read noise"
_ADC_HEADING = "ADC"
_WELL_HEADING = "Full well"
_TDI_HEADING = "TDI"
_COADD_HEADING = "Co-adds"
_BINNING_HEADING = "Binning"
_ACQUISITION_HEADING = "Acquisition"


class ReadoutInputsForm(QWidget):
    """The Readout inputs card: schema-driven :class:`FieldRow` per readout-chain knob.

    Parameters
    ----------
    parent:
        The owning widget, if any.

    Signals
    -------
    parameterEdited(str):
        Emitted with the dot-path after an accepted edit, so the host window can refresh
        the parameter tree, this form, and schedule a re-evaluation — the same contract as
        :attr:`DetectorInputsForm.parameterEdited`.
    """

    parameterEdited = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("readoutInputsForm")

        self._sensor: Sensor | None = None
        self._display_units: dict[str, str] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # One ``geoModeFamily`` card (same object name → same QSS as every geometry/source/
        # optics/detector/spectral/platform card), so these inputs sit in an identical card.
        card = QWidget(self)
        card.setObjectName("geoModeFamily")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setProperty("state", "normal")
        box = QVBoxLayout(card)
        box.setContentsMargins(12, 10, 12, 10)
        box.setSpacing(6)

        title = QLabel(_TITLE, card)
        title.setObjectName("geoModeFamilyTitle")
        title.setWordWrap(True)
        box.addWidget(title)

        self._rows: dict[str, FieldRow] = {}
        self._headings: dict[str, QLabel] = {}
        self._add_group(box, card, _ARCHITECTURE_HEADING, _ARCHITECTURE_FIELDS)
        self._add_group(box, card, _COUNTING_HEADING, _COUNTING_FIELDS)
        self._add_group(box, card, _NOISE_HEADING, _NOISE_FIELDS)
        self._add_group(box, card, _ADC_HEADING, _ADC_FIELDS)
        self._add_group(box, card, _WELL_HEADING, _WELL_FIELDS)
        self._add_group(box, card, _TDI_HEADING, _TDI_FIELDS)
        self._add_group(box, card, _COADD_HEADING, _COADD_FIELDS)
        self._add_group(box, card, _BINNING_HEADING, _BINNING_FIELDS)
        self._add_group(box, card, _ACQUISITION_HEADING, _ACQUISITION_FIELDS)

        layout.addWidget(card)

    def _add_group(
        self,
        box: QVBoxLayout,
        card: QWidget,
        heading: str,
        fields: tuple[tuple[str, str], ...],
    ) -> None:
        """Add a titled sub-group (a heading over its :class:`FieldRow`s) to the card."""
        label = QLabel(heading, card)
        label.setObjectName("geoModeGroupHeading")
        box.addWidget(label)
        self._headings[heading] = label
        for text, dotpath in fields:
            row = FieldRow(dotpath, text, self._open_editor)
            box.addWidget(row)
            self._rows[dotpath] = row

    # -- binding / refresh --------------------------------------------------

    def bind_sensor(self, sensor: Sensor | None, display_units: dict[str, str]) -> None:
        """Bind the live *sensor* and the shared *display_units* store, then refresh.

        *display_units* is the parameter panel's session display-unit dict (shared by
        reference), so a unit chosen on any surface reflects here. A ``None`` sensor blanks
        every field (the pre-config state).
        """
        self._sensor = sensor
        self._display_units = display_units
        self.refresh()

    def refresh(self) -> None:
        """Re-read every field's value+unit text from the bound sensor (— if no sensor)."""
        for dotpath, row in self._rows.items():
            row.set_value_text(self._value_text(dotpath))
        self._apply_architecture_visibility()

    def _architecture(self) -> str:
        """The resolved readout architecture ('analog_well' when unbound)."""
        if self._sensor is None:
            return "analog_well"
        try:
            return str(self._sensor.get("readout.architecture"))
        except Exception:  # unresolved sensor — keep the analog default view
            return "analog_well"

    def _apply_architecture_visibility(self) -> None:
        """Show only the parameter groups meaningful under the current architecture.

        Counting rows are rejected by the stage under ``analog_well`` (Gap 117
        over-specification posture) and an explicit full well / conversion gain
        is rejected or unused under ``digital_counting`` — the form mirrors the
        validation instead of inviting a rejected edit.
        """
        counting = self._architecture() == "digital_counting"
        self._headings[_COUNTING_HEADING].setVisible(counting)
        for _text, dotpath in _COUNTING_FIELDS:
            self._rows[dotpath].setVisible(counting)
        self._headings[_WELL_HEADING].setVisible(not counting)
        for dotpath in _ANALOG_ONLY_DOTPATHS:
            self._rows[dotpath].setVisible(not counting)

    def _value_text(self, dotpath: str) -> str:
        """The value+unit text for *dotpath* in its display unit (— if unset).

        The two counting parameters whose schema default 0.0 means "unset"
        (Gap 117) render their sentinel as words, not as a legitimate-looking
        value: a required-but-empty packet showing "0 e-" read as configured
        on the live review (2026-09-06, second pass).
        """
        sensor = self._sensor
        if sensor is None:
            return _UNSET
        if dotpath in ("readout.count_packet_e", "readout.max_count_rate_hz"):
            try:
                unset = float(sensor.get(dotpath)) <= 0.0
            except (RadiantError, KeyError):
                unset = False
            if unset:
                return (
                    "unset — required"
                    if dotpath == "readout.count_packet_e"
                    else "none — no ceiling"
                )
        return field_display_text(sensor, dotpath, self._display_units)

    # -- editing (reuses the Parameter Editor dialog + reject discipline) ----

    def _open_editor(self, dotpath: str) -> None:
        """Open the full Parameter Editor for *dotpath* (one API call on commit)."""
        if self._sensor is None:
            return
        dialog = ParameterEditorDialog(
            self._sensor,
            dotpath,
            self._after_commit,
            self,
            display_unit=self._display_units.get(dotpath),
        )
        exec_dialog(dialog)

    def _after_commit(self, dotpath: str, unit: str | None) -> None:
        """Record the chosen display unit, refresh, and signal the edit upstream."""
        if unit is not None:
            self._display_units[dotpath] = unit
        self.refresh()
        self.parameterEdited.emit(dotpath)

    # -- accessors (tests) --------------------------------------------------

    def field_dotpaths(self) -> tuple[str, ...]:
        """The parameter dot-paths this form edits, in order."""
        return tuple(self._rows)

    def field_value_text(self, dotpath: str) -> str:
        """The displayed value+unit text of the field for *dotpath*."""
        return self._rows[dotpath].value_text()

    def row(self, dotpath: str) -> FieldRow:
        """The :class:`FieldRow` for *dotpath* (KeyError if unknown)."""
        return self._rows[dotpath]


__all__ = ["ReadoutInputsForm"]
