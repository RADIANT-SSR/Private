"""Blind A/B pairs and contact sheets from two capture sets (Gap 143 audit protocol).

``pairs`` lays each before/after image pair side by side with the order **randomised per
pair** and labelled only "A" / "B"; the mapping is written to ``key.json`` for the
orchestrator and never shown to an auditor. ``sheet`` builds the downscaled before/after
contact sheet a package's audit record commits (Rule 26: this file is its generator).

Usage (from the repo root)::

    python dev_tools/gui_capture/pairs.py pairs --before .impeccable/captures/baseline \\
        --after .impeccable/captures/wp1 --out .impeccable/audits/wp1/pairs \\
        --seed 143 mwir_leo_minimal/figures/light_mtf.png mwir_leo_minimal/figures/dark_mtf.png

    python dev_tools/gui_capture/pairs.py sheet --before ... --after ... --out sheet.png \\
        --columns 2 <relative image paths...>

Relative paths are the same under both roots (the capture harness guarantees that).
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_LABEL_BAND_PX = 36
_GUTTER_PX = 16
_BG = (235, 238, 242)  # tokens.LIGHT bg
_INK = (27, 34, 48)


def _font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype("Helvetica.ttc", size)
    except OSError:
        return ImageFont.load_default()


def _labelled(image: Image.Image, label: str) -> Image.Image:
    """The image with a label band above it."""
    canvas = Image.new("RGB", (image.width, image.height + _LABEL_BAND_PX), _BG)
    draw = ImageDraw.Draw(canvas)
    draw.text((12, 8), label, fill=_INK, font=_font(20))
    canvas.paste(image, (0, _LABEL_BAND_PX))
    return canvas


def _side_by_side(left: Image.Image, right: Image.Image) -> Image.Image:
    height = max(left.height, right.height)
    canvas = Image.new("RGB", (left.width + right.width + _GUTTER_PX, height), _BG)
    canvas.paste(left, (0, 0))
    canvas.paste(right, (left.width + _GUTTER_PX, 0))
    return canvas


def make_pairs(before: Path, after: Path, out: Path, rel_paths: list[str], seed: int) -> Path:
    """Write one randomised A/B composite per relative path and the key file."""
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    key: list[dict[str, object]] = []
    for index, rel in enumerate(rel_paths, start=1):
        img_before = Image.open(before / rel).convert("RGB")
        img_after = Image.open(after / rel).convert("RGB")
        after_is_a = rng.random() < 0.5
        a, b = (img_after, img_before) if after_is_a else (img_before, img_after)
        composite = _side_by_side(_labelled(a, "A"), _labelled(b, "B"))
        name = f"pair_{index:02d}.png"
        composite.save(out / name)
        key.append({"pair": name, "source": rel, "after_is": "A" if after_is_a else "B"})
    key_path = out / "key.json"
    key_path.write_text(json.dumps({"seed": seed, "pairs": key}, indent=2), encoding="utf-8")
    manifest = out / "manifest.txt"
    manifest.write_text("\n".join(p["pair"] for p in key) + "\n", encoding="utf-8")  # type: ignore[misc]
    return key_path


def make_sheet(
    before: Path, after: Path, out: Path, rel_paths: list[str], columns: int, width: int
) -> Path:
    """A downscaled grid: each row is one source, before on the left, after on the right."""
    tiles: list[Image.Image] = []
    for rel in rel_paths:
        row = _side_by_side(
            _labelled(Image.open(before / rel).convert("RGB"), f"before · {rel}"),
            _labelled(Image.open(after / rel).convert("RGB"), "after"),
        )
        scale = width / row.width
        tiles.append(row.resize((width, int(row.height * scale)), Image.LANCZOS))
    rows = [tiles[i : i + columns] for i in range(0, len(tiles), columns)]
    row_height = max(t.height for t in tiles)
    sheet = Image.new(
        "RGB",
        (columns * width + (columns - 1) * _GUTTER_PX, len(rows) * (row_height + _GUTTER_PX)),
        _BG,
    )
    for r, row in enumerate(rows):
        for c, tile in enumerate(row):
            sheet.paste(tile, (c * (width + _GUTTER_PX), r * (row_height + _GUTTER_PX)))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("pairs", "sheet"):
        p = sub.add_parser(name)
        p.add_argument("--before", required=True, type=Path)
        p.add_argument("--after", required=True, type=Path)
        p.add_argument("--out", required=True, type=Path)
        p.add_argument("paths", nargs="+", help="relative image paths present under both roots")
        if name == "pairs":
            p.add_argument("--seed", type=int, default=143)
        else:
            p.add_argument("--columns", type=int, default=1)
            p.add_argument(
                "--width", type=int, default=1400, help="pixel width of each before+after row"
            )
    args = parser.parse_args(argv)
    if args.command == "pairs":
        key = make_pairs(args.before, args.after, args.out, args.paths, args.seed)
        print(f"wrote {len(args.paths)} pairs; key at {key}")
    else:
        sheet = make_sheet(args.before, args.after, args.out, args.paths, args.columns, args.width)
        print(f"wrote {sheet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
