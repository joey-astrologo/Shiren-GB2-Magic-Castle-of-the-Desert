"""Keep the native VWF compositor's second tile inside its 144-pixel canvas.

The compositor at 0:$3922 paints a fixed eight-pixel cell. Its secondary tile
write normally crosses an ordinary tile boundary, but at x=137..143 that tile
aliases the next canvas row. In a two-line combat window it can erase the
bottom frame, even though the English glyph's ink and pen both fit.

Only the secondary write is gated. The primary tile, shifts, glyph source,
advance, line breaks, banking and upload path retain their native behavior.
The aligned-cell bypass moves inside the saved-register block so the original
six-byte gate can call a six-byte edge predicate in the verified bank-0 tail.
"""

from hashlib import sha1

import cartridge


COMPOSITOR_START = 0x3922
COMPOSITOR_END = 0x39E3
COMPOSITOR_SHA1 = "5f592102f709521dbc692378870645c058ce1e84"
EDGE_HELPER_ADDRESS = 0x3FF6
# ld a,[$C4D6]; cp $88; ret -- carry iff the origin is before the last tile.
EDGE_HELPER = bytes.fromhex("FA D6 C4 FE 88 C9")
PATCHES = (
    # ld a,[$C4CF]; and a; jr z,$3998
    # -> call $3FF6; jr nc,$3998; nop
    (0x3971, bytes.fromhex("FA CF C4 A7 28 21"),
     bytes.fromhex("CD F6 3F 30 22 00")),
    # Zero shift now skips the secondary write and restores BC/DE at $3996.
    (0x397D, bytes.fromhex("28 07"), bytes.fromhex("28 17")),
    (EDGE_HELPER_ADDRESS, bytes(len(EDGE_HELPER)), EDGE_HELPER),
)


class GlyphCellClipError(ValueError):
    """The compositor or its reserved predicate span no longer matches."""


def owned_ranges():
    return tuple((start, start + len(original))
                 for start, original, _replacement in PATCHES)


def install(rom, checksums=True):
    out = bytearray(rom)
    native = bytearray(out[COMPOSITOR_START:COMPOSITOR_END])
    for start, original, replacement in PATCHES:
        actual = bytes(out[start:start + len(original)])
        if actual not in (original, replacement):
            raise GlyphCellClipError(
                "unexpected glyph-cell clip bytes at 0:$%04X: %s"
                % (start, actual.hex().upper())
            )
        if COMPOSITOR_START <= start < COMPOSITOR_END:
            offset = start - COMPOSITOR_START
            native[offset:offset + len(original)] = original
    if sha1(native).hexdigest() != COMPOSITOR_SHA1:
        raise GlyphCellClipError("native VWF compositor contract changed")
    for start, _original, replacement in PATCHES:
        out[start:start + len(replacement)] = replacement
    if checksums:
        cartridge.fix_checksums(out)
    return bytes(out)


def verify(rom):
    for start, _original, replacement in PATCHES:
        if bytes(rom[start:start + len(replacement)]) != replacement:
            raise GlyphCellClipError("glyph-cell clip is absent at 0:$%04X" % start)
    install(rom, checksums=False)
    return True
