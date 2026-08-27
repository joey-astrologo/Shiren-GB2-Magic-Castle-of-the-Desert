#!/usr/bin/env python3
"""Read named fields from a Mesen 2 ``.mss`` save state.

Mesen stores its Game Boy state as a zlib member containing a flat sequence of
``name\0, u32 byte_count, payload`` fields.  The archive also contains a zlib
preview image, so the state member is identified by its ``cpu.pc`` first field
instead of relying on a version-specific file offset.

The most useful interoperable field is ``cartRam``: it is ordinary battery SRAM
and can be supplied to PyBoy as its ``ram_file`` argument.
"""

import argparse
from pathlib import Path
import sys
import zlib


ZLIB_HEADERS = (b"\x78\x01", b"\x78\x9C", b"\x78\xDA")
STATE_PREFIX = b"cpu.pc\0"


class MesenStateError(ValueError):
    """The input is not a supported, intact Mesen named-field state."""


def state_payload(raw):
    """Return the decompressed named-field member from one Mesen state."""
    raw = bytes(raw)
    for offset in range(max(0, len(raw) - 1)):
        if raw[offset:offset + 2] not in ZLIB_HEADERS:
            continue
        try:
            payload = zlib.decompress(raw[offset:])
        except zlib.error:
            continue
        if payload.startswith(STATE_PREFIX):
            return payload
    raise MesenStateError("Mesen named-field payload was not found")


def parse_fields(payload):
    """Parse a decompressed Mesen named-field payload into ``{name: bytes}``."""
    payload = bytes(payload)
    fields = {}
    offset = 0
    while offset < len(payload):
        try:
            name_end = payload.index(0, offset)
        except ValueError as exc:
            raise MesenStateError("unterminated field name") from exc
        size_at = name_end + 1
        if size_at + 4 > len(payload):
            raise MesenStateError("truncated size for field at $%X" % offset)
        try:
            name = payload[offset:name_end].decode("ascii")
        except UnicodeDecodeError as exc:
            raise MesenStateError("non-ASCII field name at $%X" % offset) from exc
        size = int.from_bytes(payload[size_at:size_at + 4], "little")
        value_at = size_at + 4
        value_end = value_at + size
        if value_end > len(payload):
            raise MesenStateError("truncated payload for field %s" % name)
        if name in fields:
            raise MesenStateError("duplicate field %s" % name)
        fields[name] = payload[value_at:value_end]
        offset = value_end
    return fields


def load_fields(path):
    """Read ``path`` and return all Mesen named fields."""
    return parse_fields(state_payload(Path(path).read_bytes()))


def cart_ram(path):
    """Return the battery-backed Game Boy RAM embedded in ``path``."""
    fields = load_fields(path)
    try:
        ram = fields["cartRam"]
    except KeyError as exc:
        raise MesenStateError("state has no cartRam field") from exc
    if not ram or len(ram) % 0x2000:
        raise MesenStateError(
            "cartRam has invalid length %d (expected whole 8 KiB banks)" % len(ram)
        )
    return ram


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Extract Game Boy battery SRAM from a Mesen 2 save state"
    )
    parser.add_argument("state", help="input .mss state")
    parser.add_argument("output", help="output raw .srm/.ram file")
    args = parser.parse_args(argv)
    try:
        ram = cart_ram(args.state)
        Path(args.output).write_bytes(ram)
    except (OSError, MesenStateError) as exc:
        parser.exit(1, "error: %s\n" % exc)
    print("wrote %d bytes to %s" % (len(ram), args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
