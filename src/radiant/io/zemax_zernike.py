"""Importer for Zemax "Zernike Standard Coefficients" text exports.

Scope: the *text analysis report* that Zemax (OpticStudio) writes from
Analyze → Wavefront → Zernike Standard Coefficients → "Save As Text", NOT
the full ``.ZMX`` lens prescription.  A typical report looks like::

    Listing of Zernike Standard Coefficient Data

    File : lens.zmx
    Field                        : 0.0000, 0.0000 (deg)
    Wavelength                   :     4.0000 µm
    ...
    Z   1      0.12345678 :   1
    Z   2     -0.00234567 :   4^(1/2) (p) * COS (A)

Zemax "Standard" Zernikes use **Noll numbering**, and the coefficients are
in **waves at the stated wavelength** — exactly the convention of
:class:`radiant.optics.wavefront.WavefrontError` in ``WfeMode.ZERNIKE``
(Gaps 24/25), so the parsed dict feeds that pipeline directly via
:meth:`ZemaxZernikeResult.to_wavefront_error`.

Format tolerance (varies by Zemax version):
    * ``Z   1`` and ``Z1`` index styles;
    * an optional trailing ``:  <polynomial formula>`` after each value;
    * header wording differences — only lines starting with ``Wavelength``
      and ``Z <int>`` are consumed, everything else is ignored;
    * encodings: UTF-16 (LE/BE, Zemax on Windows usually writes UTF-16-LE
      with a BOM), UTF-8 (with or without BOM), latin-1 fallback.

The report is single-field: one coefficient set per file.  A multi-field
export concatenated into one file repeats Noll indices and is rejected with
an actionable error (export each field separately).

Piston (Z1) is parsed and kept like every other term — downstream code
decides what to discard.
"""

from __future__ import annotations

import codecs
import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from radiant.core.exceptions import RadiantError
from radiant.optics.wavefront import WavefrontError, WfeMode

logger = logging.getLogger(__name__)

__all__ = ["ZemaxParseError", "ZemaxZernikeResult", "load_zemax_zernike"]


class ZemaxParseError(RadiantError):
    """A Zemax Zernike export could not be read or parsed.

    Follows the actionable-error contract (Rule 15): carries a structured
    ``what / why / action / context`` payload, mirroring
    :class:`radiant.core.parameters.ParameterBoundsError`.

    Parameters
    ----------
    what:
        One-line description of what is wrong.
    why:
        Why it is a problem.
    action:
        What the user should do to fix it.
    context:
        Optional dict of diagnostic fields (path, line number, token, ...).
    """

    def __init__(
        self,
        what: str,
        why: str = "",
        action: str = "",
        context: dict[str, Any] | None = None,
    ) -> None:
        self.what: str = what
        self.why: str = why
        self.action: str = action
        self.context: dict[str, Any] = dict(context) if context is not None else {}

        parts: list[str] = [what]
        if why:
            parts.append(f"Why: {why}")
        if action:
            parts.append(f"Action: {action}")
        super().__init__(" | ".join(parts))


# A floating-point number: 0.123, -0.5, 1.25e-03, .5 ...
_FLOAT = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"

# "Z   4      0.05500000 : ..." or "Z4   0.055" — index then coefficient;
# anything after the coefficient (the polynomial formula) is ignored.
_Z_LINE_RE = re.compile(rf"^\s*Z\s*(\d+)\s+({_FLOAT})")

# "Wavelength                   :     4.0000 µm" (any text before the colon,
# so "Wavelength (µm) :" variants also match; units after the value ignored).
_WAVELENGTH_RE = re.compile(rf"^\s*Wavelength[^:]*:\s*({_FLOAT})", re.IGNORECASE)


def _decode(raw: bytes, path: Path) -> str:
    """Decode a Zemax text export of unknown encoding.

    Order: UTF-16 BOM (LE or BE) → UTF-8 BOM → BOM-less UTF-16-LE
    (detected via embedded NUL bytes, which cannot occur in a valid
    UTF-8/latin-1 Zemax report) → UTF-8 → latin-1 fallback.
    """
    if raw.startswith(codecs.BOM_UTF16_LE) or raw.startswith(codecs.BOM_UTF16_BE):
        encoding = "utf-16"
    elif raw.startswith(codecs.BOM_UTF8):
        encoding = "utf-8-sig"
    elif b"\x00" in raw:
        encoding = "utf-16-le"
    else:
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            logger.debug("%s: not valid UTF-8; falling back to latin-1.", path)
            return raw.decode("latin-1")

    try:
        return raw.decode(encoding)
    except UnicodeDecodeError as exc:
        raise ZemaxParseError(
            what=f"Could not decode {path} as {encoding}: {exc}.",
            why="Zemax text exports are UTF-16-LE (with BOM) or UTF-8; this file "
            "matches neither cleanly.",
            action="Re-export the analysis from Zemax with 'Save As Text', or "
            "convert the file to UTF-8.",
            context={"path": str(path), "encoding": encoding},
        ) from exc


def load_zemax_zernike(path: str | Path) -> ZemaxZernikeResult:
    """Parse a Zemax "Zernike Standard Coefficients" text export.

    Parameters
    ----------
    path:
        Path to the ``.txt`` report saved from the Zemax analysis window.

    Returns
    -------
    ZemaxZernikeResult
        Parsed Noll-indexed coefficients [waves], the report's reference
        wavelength [µm] (``None`` if the header line is absent), the term
        count, and the source path.

    Raises
    ------
    ZemaxParseError
        If the file is missing, cannot be decoded, contains no ``Z n``
        coefficient lines, repeats a Noll index, has a non-positive Noll
        index, a non-finite coefficient, or a non-positive wavelength.
    """
    p = Path(path)
    if not p.is_file():
        raise ZemaxParseError(
            what=f"Zemax Zernike export {p} does not exist or is not a file.",
            why="load_zemax_zernike needs the .txt report saved from the Zemax "
            "'Zernike Standard Coefficients' analysis window.",
            action="Check the path, or export the analysis from Zemax via "
            "'Save As Text' and point to that file.",
            context={"path": str(p)},
        )

    text = _decode(p.read_bytes(), p)

    coeffs: dict[int, float] = {}
    wavelength_um: float | None = None

    for lineno, line in enumerate(text.splitlines(), start=1):
        z_match = _Z_LINE_RE.match(line)
        if z_match is not None:
            noll_j = int(z_match.group(1))
            if noll_j < 1:
                raise ZemaxParseError(
                    what=f"{p}:{lineno}: Zernike index Z {noll_j} is not a valid Noll index.",
                    why="Zemax Standard Zernikes use Noll numbering, which starts at 1 (piston).",
                    action="Check the export — a 'Z 0' line means the file is not a "
                    "Zernike Standard Coefficients report.",
                    context={"path": str(p), "line": lineno, "index": noll_j},
                )
            if noll_j in coeffs:
                raise ZemaxParseError(
                    what=f"{p}:{lineno}: duplicate Zernike index Z {noll_j}.",
                    why="A single-field export lists each Noll index once; duplicates "
                    "usually mean several field points were concatenated into one file, "
                    "making the coefficient set ambiguous.",
                    action="Export one field point per file, or split this file into "
                    "per-field reports (multi-field import is not supported).",
                    context={"path": str(p), "line": lineno, "index": noll_j},
                )
            value = float(z_match.group(2))
            if not math.isfinite(value):
                raise ZemaxParseError(
                    what=f"{p}:{lineno}: coefficient for Z {noll_j} "
                    f"({z_match.group(2)!r}) is not finite.",
                    why="A non-finite Zernike coefficient would silently poison the "
                    "wavefront, PSF, and Strehl downstream.",
                    action="Fix or re-export the report; coefficients must be finite "
                    "values in waves.",
                    context={"path": str(p), "line": lineno, "index": noll_j},
                )
            coeffs[noll_j] = value
            continue

        if wavelength_um is None:
            wl_match = _WAVELENGTH_RE.match(line)
            if wl_match is not None:
                wavelength_um = float(wl_match.group(1))
                if not math.isfinite(wavelength_um) or wavelength_um <= 0:
                    raise ZemaxParseError(
                        what=f"{p}:{lineno}: reference wavelength "
                        f"{wl_match.group(1)} µm is not a positive finite value.",
                        why="Zernike coefficients are in waves at the reference "
                        "wavelength; a non-positive wavelength makes them meaningless.",
                        action="Re-export the analysis, or pass "
                        "reference_wavelength_um explicitly to to_wavefront_error().",
                        context={"path": str(p), "line": lineno},
                    )

    if not coeffs:
        raise ZemaxParseError(
            what=f"No 'Z <n>  <coefficient>' lines found in {p}.",
            why="Without coefficient lines this is not a usable Zernike Standard "
            "Coefficients export (wrong file, truncated export, or a different "
            "analysis type).",
            action="Export via Analyze → Wavefront → Zernike Standard Coefficients "
            "→ 'Save As Text' in Zemax, and pass that .txt file.",
            context={"path": str(p)},
        )

    logger.debug(
        "Parsed %d Zernike terms (Noll %d..%d) from %s; wavelength = %s µm.",
        len(coeffs),
        min(coeffs),
        max(coeffs),
        p,
        wavelength_um,
    )

    return ZemaxZernikeResult(
        zernike_coeffs=coeffs,
        reference_wavelength_um=wavelength_um,
        n_terms=len(coeffs),
        source_file=str(p),
    )


@dataclass(frozen=True)
class ZemaxZernikeResult:
    """Parsed contents of a Zemax Zernike Standard Coefficients export.

    Parameters
    ----------
    zernike_coeffs:
        Noll index → coefficient in waves at ``reference_wavelength_um``.
        Includes every parsed term (piston Z1 is NOT stripped).
    reference_wavelength_um:
        Wavelength stated in the report header [µm], or ``None`` if the
        report had no parseable ``Wavelength`` line.
    n_terms:
        Number of parsed Zernike terms (``len(zernike_coeffs)``).
    source_file:
        Path of the parsed export, for provenance.
    """

    zernike_coeffs: dict[int, float]
    reference_wavelength_um: float | None
    n_terms: int
    source_file: str

    def to_wavefront_error(
        self,
        reference_wavelength_um: float | None = None,
    ) -> WavefrontError:
        """Build a :class:`~radiant.optics.wavefront.WavefrontError` (ZERNIKE mode).

        Parameters
        ----------
        reference_wavelength_um:
            Explicit reference wavelength [µm].  Overrides the wavelength
            parsed from the report.  Required if the report had no
            ``Wavelength`` header line.

        Returns
        -------
        WavefrontError
            ``mode=WfeMode.ZERNIKE`` with a *copy* of the coefficient dict.

        Raises
        ------
        ZemaxParseError
            If no reference wavelength is available from either the report
            or the argument.
        """
        ref_um = (
            reference_wavelength_um
            if reference_wavelength_um is not None
            else self.reference_wavelength_um
        )
        if ref_um is None:
            raise ZemaxParseError(
                what=f"No reference wavelength available for {self.source_file}.",
                why="The export had no 'Wavelength :' header line, and Zernike "
                "coefficients in waves are meaningless without their reference "
                "wavelength.",
                action="Pass reference_wavelength_um explicitly to "
                "to_wavefront_error() (the analysis wavelength used in Zemax).",
                context={"source_file": self.source_file},
            )
        return WavefrontError(
            mode=WfeMode.ZERNIKE,
            zernike_coeffs=dict(self.zernike_coeffs),
            reference_wavelength_um=ref_um,
        )
