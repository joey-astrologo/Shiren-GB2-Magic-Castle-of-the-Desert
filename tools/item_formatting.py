#!/usr/bin/env python3
"""Localize dynamic item-name punctuation emitted by native formatter code.

GB2 does not store every visible item row as one translatable record.  Category
formatters append counts, signs, and brackets after resolving the translated
base name.  The original arrow formatter emits ``N<kanji:hon>no Name`` while
staff and Pot formatters emit Japanese corner brackets.  Once the English font
owns the old hiragana range those fragments become mixed-language or corrupt.

This installer changes only the immediate producer instructions:

* arrow stacks become ``N Name``;
* weapon/shield and depleted-staff negatives use the English hyphen;
* staff charges and Pot capacity use ``[N]``.
* Gitan objects become ``N Gitan``.

The routines, number conversion, item records, status flags, and terminators are
otherwise untouched.
"""
import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

from cartridge import fix_checksums
import english
import font


@dataclass(frozen=True)
class FormatterPatch:
    name: str
    bank: int
    address: int
    original: bytes
    localized: bytes
    purpose: str

    @property
    def offset(self):
        return font.banked_offset(self.bank, self.address)


class ItemFormattingError(ValueError):
    """A dynamic item formatter no longer matches its reviewed instruction."""


EN_SPACE = english.ENGLISH_CODES[" "]
EN_MINUS = english.ENGLISH_CODES["-"]
EN_OPEN = english.ENGLISH_CODES["["]
EN_CLOSE = english.ENGLISH_CODES["]"]


PATCHES = (
    FormatterPatch(
        "equipment_negative_sign",
        120,
        0x484A,
        bytes.fromhex("3ED7"),
        bytes((0x3E, EN_MINUS)),
        "negative weapon/shield modifier",
    ),
    FormatterPatch(
        "arrow_counter_separator",
        120,
        0x6474,
        bytes.fromhex("3EF1223E482222"),
        bytes((0x3E, EN_SPACE, 0x22, 0x00, 0x00, 0x00, 0x00)),
        "replace the Japanese arrow counter suffix with one space",
    ),
    FormatterPatch(
        "pot_capacity_open",
        120,
        0x6889,
        bytes.fromhex("3EDC"),
        bytes((0x3E, EN_OPEN)),
        "opening Pot-capacity bracket",
    ),
    FormatterPatch(
        "pot_capacity_close",
        120,
        0x6891,
        bytes.fromhex("3EDD"),
        bytes((0x3E, EN_CLOSE)),
        "closing Pot-capacity bracket",
    ),
    FormatterPatch(
        "staff_charge_open",
        122,
        0x4E10,
        bytes.fromhex("3EDC"),
        bytes((0x3E, EN_OPEN)),
        "opening staff-charge bracket",
    ),
    FormatterPatch(
        "staff_negative_sign",
        122,
        0x4E20,
        bytes.fromhex("3ED7"),
        bytes((0x3E, EN_MINUS)),
        "negative depleted-staff charge delta",
    ),
    FormatterPatch(
        "staff_charge_close",
        122,
        0x4E33,
        bytes.fromhex("3EDD"),
        bytes((0x3E, EN_CLOSE)),
        "closing staff-charge bracket",
    ),
    FormatterPatch(
        "gitan_separator_call",
        122,
        0x6FAD,
        bytes.fromhex("CD1131"),
        bytes.fromhex("CDC576"),
        "route numeric conversion through the Gitan separator wrapper",
    ),
    FormatterPatch(
        "gitan_separator_wrapper",
        122,
        0x76C5,
        bytes.fromhex("00000000000000"),
        bytes((0xCD, 0x11, 0x31, 0x3E, EN_SPACE, 0x22, 0xC9)),
        "convert the amount, append one space, and return to the Gitan formatter",
    ),
)


def owned_ranges():
    """Return exclusive ROM ranges asserted and owned by this installer."""
    return tuple(
        (patch.offset, patch.offset + len(patch.original)) for patch in PATCHES
    )


def install(rom, checksums=True):
    """Return ``rom`` with English dynamic item punctuation installed."""
    out = bytearray(rom)
    for patch in PATCHES:
        current = bytes(out[patch.offset:patch.offset + len(patch.original)])
        if current not in (patch.original, patch.localized):
            raise ItemFormattingError(
                "unexpected %s bytes at %d:$%04X: %s"
                % (patch.name, patch.bank, patch.address, current.hex().upper())
            )
        out[patch.offset:patch.offset + len(patch.localized)] = patch.localized
    if checksums:
        fix_checksums(out)
    return bytes(out)


def summary():
    """Return the frozen producer contract used by tests and documentation."""
    return {
        "english_codes": {
            "space": "%02X" % EN_SPACE,
            "minus": "%02X" % EN_MINUS,
            "open_bracket": "%02X" % EN_OPEN,
            "close_bracket": "%02X" % EN_CLOSE,
        },
        "patches": [
            {
                "name": patch.name,
                "location": "%d:$%04X" % (patch.bank, patch.address),
                "original": patch.original.hex().upper(),
                "localized": patch.localized.hex().upper(),
                "purpose": patch.purpose,
            }
            for patch in PATCHES
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="input Shiren GB2 ROM")
    parser.add_argument("output", help="output ROM")
    args = parser.parse_args(argv)
    try:
        output = install(Path(args.rom).read_bytes())
    except (OSError, ItemFormattingError) as exc:
        parser.exit(1, "error: %s\n" % exc)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(output)
    print("arrow      : N Name")
    print("staff/Pot  : Name[N]")
    print("Gitan      : N Gitan")
    print("negative   : English hyphen")
    print("output     : %s" % destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
