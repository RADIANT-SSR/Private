"""Generator for ``zernike_standard_utf16le_bom.txt`` (Rule 26 manifest).

Zemax text-analysis exports on Windows are frequently UTF-16-LE with a
byte-order mark.  The Write tooling used in this repo emits UTF-8, so the
UTF-16 test fixture is produced by this script instead:

    python src/radiant/io/tests/fixtures/make_utf16_fixture.py

The expected coefficient values are hand-mirrored in
``src/radiant/io/tests/test_zemax_zernike.py`` (``UTF16_EXPECTED``).
"""

from __future__ import annotations

import codecs
from pathlib import Path

TEXT = """Zernike Standard Coefficients

File : lens_utf16.zmx
Field         : 0.0000, 0.0000 (deg)
Wavelength    :     0.6328 µm

Z   1      0.00000000
Z   2      0.10000000
Z   3     -0.05000000
Z   4      0.02500000
"""


def main() -> None:
    """Write the UTF-16-LE (with BOM) fixture next to this script."""
    out = Path(__file__).parent / "zernike_standard_utf16le_bom.txt"
    out.write_bytes(codecs.BOM_UTF16_LE + TEXT.encode("utf-16-le"))


if __name__ == "__main__":
    main()
