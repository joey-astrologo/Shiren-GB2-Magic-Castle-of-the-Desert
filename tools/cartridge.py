#!/usr/bin/env python3
"""Game Boy cartridge checksum helpers shared by every GB2 ROM writer."""


HEADER_CHECKSUM = 0x14D
GLOBAL_CHECKSUM = 0x14E


def header_checksum(data):
    value = 0
    for offset in range(0x134, HEADER_CHECKSUM):
        value = (value - data[offset] - 1) & 0xFF
    return value


def global_checksum(data):
    return (
        sum(data[:GLOBAL_CHECKSUM]) + sum(data[GLOBAL_CHECKSUM + 2:])
    ) & 0xFFFF


def checksum_values(data):
    """Return the calculated ``(header, global)`` checksum pair."""
    return header_checksum(data), global_checksum(data)


def stored_checksums(data):
    """Return the checksum pair currently stored in the cartridge header."""
    return data[HEADER_CHECKSUM], int.from_bytes(
        data[GLOBAL_CHECKSUM:GLOBAL_CHECKSUM + 2], "big"
    )


def verify_checksums(data):
    """Raise ``ValueError`` unless both stored checksums are correct."""
    calculated = checksum_values(data)
    stored = stored_checksums(data)
    if stored != calculated:
        raise ValueError(
            "cartridge checksum mismatch: stored header/global $%02X/$%04X, "
            "calculated $%02X/$%04X"
            % (stored[0], stored[1], calculated[0], calculated[1])
        )
    return stored


def fix_checksums(buffer):
    """Fix both cartridge checksums in a mutable byte buffer and return them."""
    buffer[HEADER_CHECKSUM] = header_checksum(buffer)
    buffer[GLOBAL_CHECKSUM] = buffer[GLOBAL_CHECKSUM + 1] = 0
    value = global_checksum(buffer)
    buffer[GLOBAL_CHECKSUM] = value >> 8
    buffer[GLOBAL_CHECKSUM + 1] = value & 0xFF
    return buffer[HEADER_CHECKSUM], value

