#!/usr/bin/env python3
"""Remove the Japanese item counter from the town shop's sale-count value.

The multiple-item sale formatter converts the selected count to decimal text,
then appends hiragana ``ko`` (``$39``) before caching the value used by the
``<cF8>5`` template slot.  The English font owns that byte as lowercase ``j``,
so the native value ``4ko`` renders as ``4j``.

The translated sentence supplies the English noun and punctuation after the
dynamic value.  This patch therefore terminates the cached decimal string at
the instruction that formerly appended ``ko``.  No generic text-copy routine,
other template slot, or number converter is changed.
"""
import argparse
from pathlib import Path

import cartridge
import font


COUNT_SUFFIX_BANK = 17
COUNT_SUFFIX_ADDRESS = 0x4309
# ld a,$39; ldi [hl],a; ld a,$FF; ldi [hl],a
ORIGINAL_SUFFIX = bytes.fromhex("3E39223EFF22")
# ld a,$FF; ldi [hl],a; nop; nop; nop
ENGLISH_TERMINATOR = bytes.fromhex("3EFF22000000")


class ShopSaleCountError(ValueError):
    """The audited multiple-sale count producer no longer matches."""


def owned_range():
    """Return the exclusive ROM range owned by this installer."""
    start = font.banked_offset(COUNT_SUFFIX_BANK, COUNT_SUFFIX_ADDRESS)
    return start, start + len(ORIGINAL_SUFFIX)


def install(rom, checksums=True):
    """Return ``rom`` with the cached sale count terminated after its digits."""
    out = bytearray(rom)
    start, end = owned_range()
    current = bytes(out[start:end])
    if current not in (ORIGINAL_SUFFIX, ENGLISH_TERMINATOR):
        raise ShopSaleCountError(
            "unexpected sale-count suffix bytes at %d:$%04X: %s"
            % (COUNT_SUFFIX_BANK, COUNT_SUFFIX_ADDRESS, current.hex().upper())
        )
    out[start:end] = ENGLISH_TERMINATOR
    if checksums:
        cartridge.fix_checksums(out)
    return bytes(out)


def verify(rom):
    """Reject a ROM that still appends the Japanese item counter."""
    start, end = owned_range()
    if bytes(rom[start:end]) != ENGLISH_TERMINATOR:
        raise ShopSaleCountError("English sale-count terminator patch is absent")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="input Shiren GB2 ROM")
    parser.add_argument("output", help="output ROM")
    args = parser.parse_args(argv)
    try:
        output = install(Path(args.rom).read_bytes())
    except (OSError, ShopSaleCountError) as exc:
        parser.exit(1, "error: %s\n" % exc)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(output)
    print("multiple-sale count: digits only")


if __name__ == "__main__":
    main()
