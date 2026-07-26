"""One reversible change to a study's **shape** (multi-configuration Phase 4c).

Phase 4b's :class:`~radiant.gui.widgets.scoped_parameter_command.ScopedParameterCommand`
reverses one parameter's scope-and-value change. The configuration manager (§4.2d)
changes something larger and coarser: *which configurations exist*, in what order,
which is baseline, which is displayed, and what spectral grid each one uses. A
Remove additionally destroys a whole column of configured values, and the plan's
acceptance criterion (§4 item 7) is that undo restores it **exactly**.

Rather than a command per manager action, this module records the study's whole
**shape** before and after the dialog's ``OK`` and applies a shape as a unit —
:class:`ConfigurationShape` is that snapshot and :class:`ConfigurationShapeCommand`
is the single undo step. That choice follows from how the dialog works: it edits a
private ``ConfigurationSet.clone()`` and the live set never sees the intermediate
states, so there are no per-action steps to reverse — there is one transaction, and
one command for it. It also side-steps the sequencing trap a per-action design has
(undoing "rename A→B" after "add A" must not collide), because a shape is applied by
construction rather than by replaying inverses.

**What a shape holds** — everything the manager can change:
configuration names *in order*, the configured table's value columns (so a removed
configuration's values come back), each configuration's ``wavelength_points``
override and the shared default, and the ``baseline`` / ``active`` designations.

**What a shape deliberately does not hold**: *which* parameters are configured, and
the shared base's values. The manager never configures or un-configures a parameter
(that is the 4b surface) and never edits a shared value, so those stay outside this
command and remain owned by ``ScopedParameterCommand`` / ``SetParameterCommand``.
Both command kinds mutate the one live ``ConfigurationSet``, so they share one undo
stack in any order.

Values are carried in the parameter's **input unit**, exactly as
``ConfigurationSet.configured()`` reports them. No colour/font/size literal lives
here (GUI plan §4.9).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from PySide6.QtGui import QUndoCommand

if TYPE_CHECKING:
    from radiant.api.config_set import ConfigurationSet


def _placeholder_names(reserved: set[str], count: int) -> list[str]:
    """*count* names guaranteed to collide with nothing in *reserved*.

    Applying a shape renames every configuration to one of these first, so the
    real renames that follow can never hit a name that is still occupied (the
    swap ``[A, B] → [B, A]`` is the smallest case that breaks a naive rename).
    """
    names: list[str] = []
    index = 0
    while len(names) < count:
        candidate = f"—configuration {index}—"
        if candidate not in reserved:
            names.append(candidate)
        index += 1
    return names


@dataclass(frozen=True)
class ConfigurationShape:
    """A study's membership, order, columns, grids, and designations at one instant.

    Attributes
    ----------
    names:
        Configuration names in set order.
    parameters:
        Configured dot-path → its value column, aligned with *names*, in input units.
    wavelength_points:
        Configuration name → its spectral point-count **override**. A name absent
        from this mapping inherits the shared default.
    shared_wavelength_points:
        The shared default in force (``ConfigurationSet.wavelength_points()``).
    baseline, active:
        The delta reference and the displayed configuration.
    """

    names: tuple[str, ...]
    parameters: dict[str, tuple[Any, ...]] = field(default_factory=dict)
    wavelength_points: dict[str, int] = field(default_factory=dict)
    shared_wavelength_points: int | None = None
    baseline: str = ""
    active: str = ""

    @classmethod
    def of(cls, config_set: ConfigurationSet) -> ConfigurationShape:
        """Snapshot *config_set*'s current shape (a copy — later edits do not leak)."""
        names = config_set.names()
        overrides: dict[str, int] = {}
        for name in names:
            points = config_set.wavelength_points(name)
            if points is not None:
                overrides[name] = points
        return cls(
            names=names,
            parameters={p: tuple(v) for p, v in config_set.configured().items()},
            wavelength_points=overrides,
            shared_wavelength_points=config_set.wavelength_points(),
            baseline=config_set.baseline,
            active=config_set.active,
        )

    def apply_to(self, config_set: ConfigurationSet) -> None:
        """Morph *config_set* into this shape using only public API calls.

        The sequence is membership → order → columns → grids → designations, and it
        works from *any* starting shape:

        1. every existing configuration is renamed to a placeholder, so no later
           rename can collide with a name that has not moved yet;
        2. the count is matched (extra placeholders removed from the end, missing
           ones added — a set always keeps at least one, and the API's cap still
           applies);
        3. the placeholders are renamed to the target names, in order;
        4. each configured parameter's whole column is rewritten (this is what
           restores the values a Remove dropped);
        5. each configuration's ``wavelength_points`` override is set or cleared,
           then the shared default;
        6. ``baseline`` and ``active`` are restored last, because ``remove`` moves
           them on its own while step 2 runs.

        Every step is an ordinary ``ConfigurationSet`` call, so the model's own
        validation applies throughout and this module holds no rules of its own.

        Two things this relies on, both worth naming:

        * Step 4 requires every dot-path in the shape to still be *configured* on the
          target set. It always is: the manager never configures or un-configures, and
          the undo stack is LIFO, so a later ``ScopedParameterCommand`` is reversed
          before this command is. A dot-path that had left the configured table would
          raise the API's own "not configured" error rather than write silently
          elsewhere.
        * Step 5's shared default is always a concrete count (``wavelength_points()``
          reports the count *in force*, never ``None``), so applying a shape pins the
          set-level default even where the base's own count had been carrying it. That
          is observationally identical — the same grid, and the same
          ``_radiant.wavelength_points`` on save.
        """
        current = config_set.names()
        placeholders = _placeholder_names(
            reserved=set(current) | set(self.names),
            count=max(len(current), len(self.names)),
        )
        for old, temp in zip(current, placeholders, strict=False):
            config_set.rename(old, temp)
        while len(config_set) > len(self.names):
            config_set.remove(config_set.names()[-1])
        while len(config_set) < len(self.names):
            config_set.add(placeholders[len(config_set)])
        for temp, final in zip(config_set.names(), self.names, strict=True):
            config_set.rename(temp, final)
        for dotpath, column in self.parameters.items():
            config_set.set_values(dotpath, column)
        for name in self.names:
            config_set.set_wavelength_points(name, self.wavelength_points.get(name))
        config_set.set_wavelength_points(None, self.shared_wavelength_points)
        config_set.baseline = self.baseline
        config_set.active = self.active


class ConfigurationShapeCommand(QUndoCommand):
    """Reverse/replay one configuration-manager transaction between two shapes.

    Parameters
    ----------
    config_set:
        The live session :class:`~radiant.api.config_set.ConfigurationSet`.
    before, after:
        The study's :class:`ConfigurationShape` before and after the dialog's ``OK``.
    on_applied:
        Called after an undo or redo mutates the set, so the window refreshes the
        master selector, the badges, the displayed configuration, and re-evaluates.
    text:
        The command label shown in the Edit menu.
    """

    def __init__(
        self,
        config_set: ConfigurationSet,
        before: ConfigurationShape,
        after: ConfigurationShape,
        on_applied: Callable[[], None],
        text: str,
    ) -> None:
        super().__init__(text)
        self._config_set = config_set
        self._before = before
        self._after = after
        self._on_applied = on_applied
        # QUndoStack.push() calls redo() immediately, but the window has already
        # applied the after-shape (so a rejected apply never reaches the stack).
        # Skip that first redo; every later one applies.
        self._skip_first_redo = True

    def redo(self) -> None:  # noqa: D401 - Qt override
        """Re-apply the after-shape (a no-op on the first, action-triggered push)."""
        if self._skip_first_redo:
            self._skip_first_redo = False
            return
        self._after.apply_to(self._config_set)
        self._on_applied()

    def undo(self) -> None:  # noqa: D401 - Qt override
        """Restore the before-shape — membership, order, columns, grids, designations."""
        self._before.apply_to(self._config_set)
        self._on_applied()


__all__ = ["ConfigurationShape", "ConfigurationShapeCommand"]
