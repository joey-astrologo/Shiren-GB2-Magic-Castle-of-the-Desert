#!/usr/bin/env python3
"""Make native ``<page>`` controls require a fresh button press.

GB2's page handler at 0:$3751 normally waits for button release and then a
fresh A/B press.  A global automatic-text flag at $C4D9 bypasses that wait at
0:$37BD, even when the source record explicitly contains FB (``<page>``).
That is unsuitable for expanded English story dialogue: a scripted scene can
discard a completed page immediately, and the same mode also affects any
untranslated Japanese record in the scene.

The game's genuinely automatic cinematic records remain automatic because
they contain no FB control and use their native FA delays.  This patch clears
the automatic flag only upon entering an explicit page, then falls through to
the stock release/fresh-press loop.  Clearing the flag is necessary because
the per-frame input service also synthesizes an advance while it remains set.
"""

import cartridge


PAGE_AUTO_BYPASS_ADDRESS = 0x37B9
# ld a,[$C4D9]; and a; jr nz,0:$37EF
ORIGINAL_BYPASS = bytes.fromhex("FA D9 C4 A7 20 30")
# xor a; ld [$C4D9],a; nop; nop
WAIT_FOR_INPUT = bytes.fromhex("AF EA D9 C4 00 00")


class DialoguePacingError(ValueError):
    """The audited page-handler bytes no longer match the target ROM."""


def owned_range():
    return PAGE_AUTO_BYPASS_ADDRESS, PAGE_AUTO_BYPASS_ADDRESS + len(WAIT_FOR_INPUT)


def install(rom, checksums=True):
    """Return ``rom`` with the automatic FB bypass disabled."""
    out = bytearray(rom)
    actual = bytes(
        out[
            PAGE_AUTO_BYPASS_ADDRESS:
            PAGE_AUTO_BYPASS_ADDRESS + len(ORIGINAL_BYPASS)
        ]
    )
    if actual not in (ORIGINAL_BYPASS, WAIT_FOR_INPUT):
        raise DialoguePacingError(
            "page auto-bypass at 0:$%04X is %s, expected %s"
            % (
                PAGE_AUTO_BYPASS_ADDRESS,
                actual.hex().upper(),
                ORIGINAL_BYPASS.hex().upper(),
            )
        )
    out[
        PAGE_AUTO_BYPASS_ADDRESS:
        PAGE_AUTO_BYPASS_ADDRESS + len(WAIT_FOR_INPUT)
    ] = WAIT_FOR_INPUT
    if checksums:
        cartridge.fix_checksums(out)
    return bytes(out)


def verify(rom):
    """Reject a ROM whose explicit page controls can still bypass input."""
    start, end = owned_range()
    if bytes(rom[start:end]) != WAIT_FOR_INPUT:
        raise DialoguePacingError("explicit page wait patch is absent")
    return True
