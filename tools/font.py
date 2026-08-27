#!/usr/bin/env python3
"""Inspect and render Shiren GB2's dialogue fonts.

The live renderer at bank 0:$3922 consumes two font stores:

* one-byte codes use 8x8 2bpp records in bank 3 at $4842, 16 bytes each;
* F0/F1/F2-prefixed codes use 8x10 2bpp slices in bank 206 at $4000,
  20 bytes each. Glyphs whose measured width is at least 10 pixels consume the
  following slice too, producing a 16x10 source canvas.

Both stores share the proportional-width table in bank 3 at $4442. Its four
256-byte pages are one-byte, F0, F1 and F2 respectively.
"""
import argparse
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
import sys


BANK_SIZE = 0x4000

WIDTH_BANK = 3
WIDTH_ADDRESS = 0x4442
WIDTH_SIZE = 0x400

SINGLE_BANK = 3
SINGLE_ADDRESS = 0x4842
SINGLE_STRIDE = 16
SINGLE_HEIGHT = 8
SINGLE_SIZE = 0x100 * SINGLE_STRIDE

KANJI_BANK = 206
KANJI_ADDRESS = 0x4000
KANJI_STRIDE = 20
KANJI_HEIGHT = 10
KANJI_PAGES = 3
KANJI_SIZE = KANJI_PAGES * 0x100 * KANJI_STRIDE

KANJI_PREFIXES = (0xF0, 0xF1, 0xF2)

# These hashes make accidental address/size drift fail loudly when the original
# Japanese ROM is available. They cover font assets only, not the whole ROM.
REGION_SHA1 = {
    "widths": "d0ea77dddff92fe58b72adfe17b3dd6069d7edbd",
    "single": "be9b189c3ac55d66ec516b36bd6b26063400ac92",
    "kanji": "b1e8c516402959fc73832a4a8bfdf95c2ce26604",
}


@dataclass(frozen=True)
class GlyphLocation:
    encoded: bytes
    width_index: int
    bank: int
    address: int
    stride: int
    height: int


@dataclass(frozen=True)
class Glyph:
    location: GlyphLocation
    width: int
    source_width: int
    pixels: tuple


def banked_offset(bank, address):
    """Translate a bank:CPU address to a ROM file offset."""
    if bank < 0:
        raise ValueError("bank must be non-negative")
    if bank == 0:
        if not 0 <= address < 0x4000:
            raise ValueError("bank 0 address must be in $0000-$3FFF")
        return address
    if not 0x4000 <= address < 0x8000:
        raise ValueError("switchable-bank address must be in $4000-$7FFF")
    return bank * BANK_SIZE + address - 0x4000


def glyph_location(encoded):
    """Return the width-table and bitmap location for one encoded glyph."""
    encoded = bytes(encoded)
    if len(encoded) == 1:
        code = encoded[0]
        return GlyphLocation(
            encoded=encoded,
            width_index=code,
            bank=SINGLE_BANK,
            address=SINGLE_ADDRESS + code * SINGLE_STRIDE,
            stride=SINGLE_STRIDE,
            height=SINGLE_HEIGHT,
        )
    if len(encoded) == 2 and encoded[0] in KANJI_PREFIXES:
        page = encoded[0] - 0xF0
        slot = page * 0x100 + encoded[1]
        return GlyphLocation(
            encoded=encoded,
            width_index=0x100 + slot,
            bank=KANJI_BANK,
            address=KANJI_ADDRESS + slot * KANJI_STRIDE,
            stride=KANJI_STRIDE,
            height=KANJI_HEIGHT,
        )
    raise ValueError("expected one byte or an F0/F1/F2-prefixed pair")


def decode_2bpp_slices(data, height, slices=1):
    """Decode sequential 8-pixel 2bpp slices into rows of color indexes 0-3."""
    expected = height * 2 * slices
    if len(data) != expected:
        raise ValueError("expected %d bytes, got %d" % (expected, len(data)))
    rows = [[] for _ in range(height)]
    for piece in range(slices):
        start = piece * height * 2
        for y in range(height):
            low, high = data[start + y * 2:start + y * 2 + 2]
            rows[y].extend(
                (((high >> bit) & 1) << 1) | ((low >> bit) & 1)
                for bit in range(7, -1, -1)
            )
    return tuple(tuple(row) for row in rows)


def read_glyph(rom, encoded):
    """Read a glyph, including the second 8-pixel slice used by wide kanji."""
    loc = glyph_location(encoded)
    width_off = banked_offset(WIDTH_BANK, WIDTH_ADDRESS) + loc.width_index
    if width_off >= len(rom):
        raise ValueError("ROM is too small for the width table")
    width = rom[width_off]
    slices = 2 if len(loc.encoded) == 2 and width >= 10 else 1
    size = loc.height * 2 * slices
    data_off = banked_offset(loc.bank, loc.address)
    data = bytes(rom[data_off:data_off + size])
    if len(data) != size:
        raise ValueError("ROM is too small for glyph %s" % loc.encoded.hex().upper())
    return Glyph(
        location=loc,
        width=width,
        source_width=8 * slices,
        pixels=decode_2bpp_slices(data, loc.height, slices),
    )


def font_regions(rom):
    """Return the three load-bearing font regions by name."""
    specs = {
        "widths": (WIDTH_BANK, WIDTH_ADDRESS, WIDTH_SIZE),
        "single": (SINGLE_BANK, SINGLE_ADDRESS, SINGLE_SIZE),
        "kanji": (KANJI_BANK, KANJI_ADDRESS, KANJI_SIZE),
    }
    out = {}
    for name, (bank, address, size) in specs.items():
        off = banked_offset(bank, address)
        data = bytes(rom[off:off + size])
        if len(data) != size:
            raise ValueError("ROM is too small for the %s region" % name)
        out[name] = data
    return out


def verify_regions(rom):
    """Verify the located regions against hashes from the traced Japanese ROM."""
    got = {name: sha1(data).hexdigest() for name, data in font_regions(rom).items()}
    bad = {name: (got[name], want) for name, want in REGION_SHA1.items()
           if got[name] != want}
    if bad:
        details = ", ".join("%s=%s (want %s)" % (n, a, b)
                            for n, (a, b) in sorted(bad.items()))
        raise ValueError("font region hash mismatch: " + details)
    return got


def _draw_glyph(image, glyph, x, y, palette):
    pix = image.load()
    for gy, row in enumerate(glyph.pixels):
        for gx, color in enumerate(row):
            pix[x + gx, y + gy] = palette[color]


def _scaled(image, scale):
    if scale == 1:
        return image
    from PIL import Image
    return image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)


def render_single_sheet(rom, scale=3):
    """Render all 256 one-byte slots in code order (16 columns by 16 rows)."""
    from PIL import Image
    cell_w, cell_h = 10, 10
    image = Image.new("RGB", (16 * cell_w, 16 * cell_h), (28, 28, 28))
    palette = ((0, 0, 0), (0, 0, 0), (80, 80, 80), (248, 248, 248))
    for code in range(0x100):
        glyph = read_glyph(rom, bytes((code,)))
        x = (code % 16) * cell_w + 1
        y = (code // 16) * cell_h + 1
        _draw_glyph(image, glyph, x, y, palette)
    return _scaled(image, scale)


def render_kanji_sheet(rom, prefix, scale=2):
    """Render one 256-slot kanji page in code order."""
    from PIL import Image
    if prefix not in KANJI_PREFIXES:
        raise ValueError("prefix must be F0, F1 or F2")
    cell_w, cell_h = 18, 12
    image = Image.new("RGB", (16 * cell_w, 16 * cell_h), (28, 28, 28))
    palette = ((0, 0, 0), (0, 0, 0), (80, 80, 80), (248, 248, 248))
    for code in range(0x100):
        glyph = read_glyph(rom, bytes((prefix, code)))
        x = (code % 16) * cell_w + 1
        y = (code // 16) * cell_h + 1
        _draw_glyph(image, glyph, x, y, palette)
    return _scaled(image, scale)


def render_glyph_image(glyph, scale=16, padding=4):
    """Render one glyph as a high-contrast, padded image for visual/OCR review."""
    from PIL import Image
    width = glyph.source_width + padding * 2
    height = glyph.location.height + padding * 2
    image = Image.new("L", (width, height), 255)
    pix = image.load()
    for y, row in enumerate(glyph.pixels):
        for x, color in enumerate(row):
            if color >= 2:
                pix[x + padding, y + padding] = 0
    return image.resize((width * scale, height * scale), Image.Resampling.NEAREST)


def write_glyph_images(rom, output_dir, scale=16):
    """Write isolated review images for every prefixed slot, named by encoded code."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for prefix in KANJI_PREFIXES:
        for code in range(0x100):
            encoded = bytes((prefix, code))
            path = output_dir / (encoded.hex().upper() + ".png")
            render_glyph_image(read_glyph(rom, encoded), scale=scale).save(path)
            paths.append(path)
    return paths


def write_sheets(rom, output_dir, scale):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = [output_dir / "single-byte.png"]
    render_single_sheet(rom, scale=scale).save(paths[0])
    for prefix in KANJI_PREFIXES:
        path = output_dir / ("kanji-%02x.png" % prefix)
        render_kanji_sheet(rom, prefix, scale=max(1, scale - 1)).save(path)
        paths.append(path)
    return paths


def _print_info(rom):
    hashes = verify_regions(rom)
    print("renderer       0:$3922")
    print("width table    3:$4442  4 x 256 bytes  sha1 %s" % hashes["widths"])
    print("one-byte font  3:$4842  256 x 16 bytes sha1 %s" % hashes["single"])
    print("kanji font   206:$4000  768 x 20 bytes sha1 %s" % hashes["kanji"])
    print("native layout  proportional widths; 8x8 one-byte, 8x10/16x10 prefixed")
    print("Latin codes    $0A-$23 contain visually uppercase A-Z glyphs")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="original Shiren GB2 ROM")
    parser.add_argument("--output-dir", default="build/font",
                        help="sheet output directory (default: build/font)")
    parser.add_argument("--scale", type=int, default=3,
                        help="nearest-neighbour sheet scale (default: 3)")
    parser.add_argument("--info", action="store_true",
                        help="only verify and print the located regions")
    parser.add_argument("--glyph-dir",
                        help="write isolated high-contrast prefixed glyph images here")
    args = parser.parse_args(argv)
    if args.scale < 1:
        parser.error("--scale must be positive")
    rom = Path(args.rom).read_bytes()
    if args.info:
        _print_info(rom)
        return 0
    verify_regions(rom)
    if args.glyph_dir:
        paths = write_glyph_images(rom, args.glyph_dir)
        print("wrote %d isolated glyph images under %s" % (len(paths), args.glyph_dir))
        return 0
    for path in write_sheets(rom, args.output_dir, args.scale):
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
