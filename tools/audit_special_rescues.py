#!/usr/bin/env python3
"""Report source-ROM evidence for the three published GB2 rescue missions.

This is a bounded search for embedded versions of known packets, combined with
reviewed native rescue-route regions. It cannot enumerate unpublished passwords
or establish that no other externally distributed rescue request ever existed.
"""
import argparse
from hashlib import sha1
import json
from pathlib import Path

import extract
import rescue_converter
import rescue_password as protocol


REGIONS = (
    (0x11, 0x76CA, 0x77C4, "SOS decode, semantic validation, diary storage, and dungeon setup"),
    (0x11, 0x792D, 0x797A, "ordinary SOS generation from current dungeon and player position"),
    (0x11, 0x7B17, 0x7DF4, "shared packet codec and location bit packing"),
    (0x0B, 0x60C7, 0x613A, "35-entry rescue history in SRAM bank 3, not a ROM password table"),
    (0x05, 0x6443, 0x648A, "dungeon access checks and required progression table"),
)


def occurrences(rom, pattern):
    found, start = [], 0
    while True:
        at = rom.find(pattern, start)
        if at < 0:
            return found
        bank = at // 0x4000
        found.append({"file_offset": at, "bank": bank,
                      "address": at if bank == 0 else 0x4000 + at % 0x4000})
        start = at + 1


def analyze(rom):
    if sha1(rom).hexdigest() != extract.ROM_SHA1:
        raise ValueError("This audit requires the verified original Japanese ROM.")
    protocol.analyze(rom)
    missions = []
    for mission in rescue_converter.mission_data()["missions"]:
        raw = protocol.delocalize_password(mission["english"])
        sos = protocol.decode_sos(raw)
        patterns = {
            "native_display_bytes": raw,
            "six_bit_symbols": bytes(protocol.NATIVE_ALPHABET_CODES.index(code) for code in raw),
            "packed_payload": sos.to_payload(),
            "unpacked_diary_record": sos.to_diary_record(),
            "seed_little_endian": sos.dungeon_seed.to_bytes(4, "little"),
            "seed_big_endian": sos.dungeon_seed.to_bytes(4, "big"),
        }
        missions.append({"id": mission["id"], "english": mission["english"],
                         "dungeon_id": sos.dungeon_id, "floor": sos.internal_floor,
                         "record_hex": sos.to_diary_record().hex(),
                         "matches": {key: occurrences(rom, value) for key, value in patterns.items()}})
    return {
        "rom_sha1": extract.ROM_SHA1,
        "missions": missions,
        "reviewed_regions": [
            {"bank": bank, "start": start, "end_inclusive": end, "description": label,
             "sha1": sha1(rom[extract.file_offset(bank, start):extract.file_offset(bank, end) + 1]).hexdigest()}
            for bank, start, end, label in REGIONS
        ],
        "scope": "Known-code representations were searched across the entire ROM. The reviewed SOS route has no promotional whitelist. This is not an exhaustive catalogue of published passwords.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(analyze(args.rom.read_bytes()), indent=2))
    except (OSError, ValueError) as error:
        parser.exit(1, "error: %s\n" % error)


if __name__ == "__main__":
    main()
