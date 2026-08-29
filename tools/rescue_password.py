#!/usr/bin/env python3
"""Audit and reproduce GB2's native Wanderer Rescue password boundary.

The packet codec below is a source-independent transcription of the clean-ROM routines
at 11:$7B17-$7D8B.  It intentionally operates on opaque payload bytes: interpreting and
mutating rescue state remains a separate reverse-engineering step.
"""
import argparse
from hashlib import sha1
import json
from pathlib import Path
import sys

import codec
import extract


SCHEMA = "shiren-gb2-rescue-password-audit-v1"
ROM_SHA1 = extract.ROM_SHA1

INPUT_MODE_ADDRESS = 0xC195
INPUT_POSITION_ADDRESS = 0xC152
INPUT_MAXIMUM_ADDRESS = 0xC153
INPUT_BUFFER_ADDRESS = 0xC16D

MODE_DISPATCH_BANK = 0x12
MODE_DISPATCH_ADDRESS = 0x502D
MODE_DISPATCH_BYTES = bytes.fromhex(
    "FA95C1FE02281CFE08282CFE042818FE032814FE07281CFE062814FE0528"
    "0C3E07181F3E0D181B3E0418170E02180A0E0318060E0118020E003E1121"
    "BE76CDAC0978EA53C1C9"
)

LONG_LENGTH_BANK = 0x11
LONG_LENGTH_ADDRESS = 0x76BE
LONG_LENGTH_BYTES = bytes.fromhex("060021C6760946C90D0F0C09")

PROTOCOL_BANK = 0x11
PROTOCOL_ADDRESS = 0x76B2
PROTOCOL_END = 0x7D8B
PROTOCOL_SHA1 = "c2e48f2c5abf2c6f196cb0951dfddb830bd22050"

CONFIRM_STAGING_BANK = 0x12
CONFIRM_STAGING_ADDRESS = 0x50F7
CONFIRM_STAGING_END = 0x515E
CONFIRM_STAGING_SHA1 = "56de42ff8d3db4f6ce069663776236b3c6c66981"

SRAM_STAGING_BANK = 0x0B
SRAM_STAGING_ADDRESS = 0x5F79
SRAM_STAGING_END = 0x5FB2
SRAM_STAGING_SHA1 = "9242c3e5b9d639030a067a103265867d89b2d670"

# The dispatcher maps modes 5-8 to indices 2, 3, 1, and 0 in the final four-byte
# length table. Roles follow the unique documented protocol lengths. Each screen's
# live $C195 value must still be captured before these role names become patch sites.
LONG_INPUT_MODES = {
    5: {"role": "thank_you", "length": 12, "status": "length_confirmed_role_inferred"},
    6: {"role": "training", "length": 9, "status": "length_confirmed_role_inferred"},
    7: {"role": "revival", "length": 15, "status": "length_confirmed_role_inferred"},
    8: {"role": "sos", "length": 13, "status": "length_confirmed_role_inferred"},
}

PUBLIC_EXCHANGE_URL = "https://bbs6.sekkaku.net/bbs/dobuntya/"
PUBLIC_EXCHANGE = {
    "sos": "そおせばぞづくばりぶかにぎ",
    "revival": "そかちにざゆねぜねあごせげほれ",
    "thank_you": "おゆまゆまでわかやれうか",
}
PUBLIC_LENGTHS = {"sos": 13, "revival": 15, "thank_you": 12}

NATIVE_ALPHABET = (
    "あいうえおかきくけこさしすせそた"
    "ちつてとなにぬねのはひふへほまみ"
    "むめもやゆよらりるれろわをんがぎ"
    "ぐげござじずぜぞだぢづでどばびぶ"
)
PAYLOAD_LENGTHS = {"sos": 9, "revival": 10, "thank_you": 8, "training": 6}


class RescuePasswordAuditError(ValueError):
    """The native rescue-password contract no longer matches reviewed evidence."""


class RescuePasswordCodecError(ValueError):
    """A password is outside the native alphabet or fails its packet checksum."""


def _compact_code(value):
    """Map a six-bit value through the native 11:$7C81 display-code gaps."""
    if not 0 <= value < 64:
        raise RescuePasswordCodecError("password symbol value is outside 0..63")
    code = value + 0x30
    if code >= 0x5E:
        code += 9
        if code >= 0xAE:
            code += 9
    return code


NATIVE_ALPHABET_CODES = bytes(_compact_code(value) for value in range(64))


def _native_value(code):
    """Reverse the clean-ROM display-code gap transform at 11:$7C97."""
    code = int(code)
    if code not in NATIVE_ALPHABET_CODES:
        raise RescuePasswordCodecError(
            "byte $%02X is not in the native rescue alphabet" % code
        )
    return NATIVE_ALPHABET_CODES.index(code)


def _swap_pairs(values):
    values = bytearray(values)
    for at in range(0, len(values) - 1, 2):
        values[at], values[at + 1] = values[at + 1], values[at]
    return values


def _transpose8(values):
    """Transpose the bit matrix used by 11:$7CEE and its inverse at $7D5A."""
    if len(values) != 8:
        raise RescuePasswordCodecError("bit transpose requires exactly eight bytes")
    scratch = bytearray(values)
    result = bytearray(8)
    for column in range(8):
        value = 0
        for row in range(8):
            carry = scratch[row] >> 7
            scratch[row] = (scratch[row] << 1) & 0xFF
            value = ((value << 1) | carry) & 0xFF
        result[column] = value
    return result


def _transpose_long(values):
    """Reproduce the overlapping eight-byte transform used for 8+ byte payloads."""
    values = bytearray(values)
    if len(values) < 8:
        return values
    scratch = bytearray(values)
    values[:8] = _transpose8(scratch[:8])
    extra = len(values) - 8
    if extra:
        scratch = bytearray(values)
        values[extra:extra + 8] = _transpose8(scratch[extra:extra + 8])
    return values


def _untranspose_long(values):
    """Reverse ``_transpose_long`` in the order used by 11:$7D17."""
    values = bytearray(values)
    if len(values) < 8:
        return values
    extra = len(values) - 8
    if extra:
        scratch = bytearray(values)
        values[extra:extra + 8] = _transpose8(scratch[extra:extra + 8])
    scratch = bytearray(values)
    values[:8] = _transpose8(scratch[:8])
    return values


def _checksum(values):
    """Return the low six bits of the weighted checksum at 11:$7C12."""
    size = len(values)
    total = 0
    for index, value in enumerate(values):
        weight = 2 * (size - index) + 1
        total = (total + value * weight) & 0xFF
    return total & 0x3F


def encode_payload(payload):
    """Encode one opaque 6/8/9/10-byte native packet to ROM text-code bytes."""
    payload = bytes(payload)
    if len(payload) not in set(PAYLOAD_LENGTHS.values()):
        raise RescuePasswordCodecError(
            "unsupported payload length %d (expected 6, 8, 9, or 10)" % len(payload)
        )

    transformed = _transpose_long(payload)
    running = 0
    cumulative = bytearray()
    for value in transformed:
        running = (running + value) & 0xFF
        cumulative.append(running)

    symbols = bytearray(value & 0x3F for value in cumulative)
    for at in range(0, len(cumulative), 3):
        packed = 0
        for value in cumulative[at:at + 3]:
            packed = (packed << 2) | (value >> 6)
        missing = 3 - len(cumulative[at:at + 3])
        packed <<= 2 * missing
        symbols.append(packed)
    symbols.append(_checksum(cumulative))

    compact = bytearray(value + 0x30 for value in symbols)
    compact = _swap_pairs(compact)
    compact.reverse()
    return bytes(_compact_code(value - 0x30) for value in compact)


def decode_password(raw, payload_length=None):
    """Decode and checksum one native password, returning its opaque payload bytes."""
    raw = bytes(raw)
    if payload_length is None:
        candidates = [
            size
            for size in PAYLOAD_LENGTHS.values()
            if size + (size + 2) // 3 + 1 == len(raw)
        ]
        if len(candidates) != 1:
            raise RescuePasswordCodecError(
                "password length %d does not identify one native payload" % len(raw)
            )
        payload_length = candidates[0]
    if payload_length not in set(PAYLOAD_LENGTHS.values()):
        raise RescuePasswordCodecError("unsupported payload length %d" % payload_length)
    expected = payload_length + (payload_length + 2) // 3 + 1
    if len(raw) != expected:
        raise RescuePasswordCodecError(
            "password has %d symbols, expected %d" % (len(raw), expected)
        )

    compact = bytearray(_native_value(code) + 0x30 for code in raw)
    compact.reverse()
    compact = _swap_pairs(compact)
    symbols = bytearray(code - 0x30 for code in compact)

    cumulative = bytearray(symbols[:payload_length])
    high_symbols = symbols[
        payload_length:payload_length + (payload_length + 2) // 3
    ]
    for group, packed in enumerate(high_symbols):
        for offset in range(3):
            index = group * 3 + offset
            if index >= payload_length:
                break
            shift = 4 - 2 * offset
            cumulative[index] |= ((packed >> shift) & 0x03) << 6

    expected_checksum = symbols[-1]
    actual_checksum = _checksum(cumulative)
    if actual_checksum != expected_checksum:
        raise RescuePasswordCodecError(
            "password checksum is %02X, expected %02X"
            % (expected_checksum, actual_checksum)
        )

    transformed = bytearray()
    previous = 0
    for value in cumulative:
        transformed.append((value - previous) & 0xFF)
        previous = value
    return bytes(_untranspose_long(transformed))


def _offset(bank, address):
    return extract.file_offset(bank, address)


def _checked_region(rom, bank, address, expected, label):
    at = _offset(bank, address)
    actual = bytes(rom[at:at + len(expected)])
    if actual != expected:
        raise RescuePasswordAuditError(
            "%s at %02X:$%04X changed: SHA-1 %s, expected %s"
            % (
                label,
                bank,
                address,
                sha1(actual).hexdigest(),
                sha1(expected).hexdigest(),
            )
        )
    return actual


def _checked_digest(rom, bank, address, end, expected_sha1, label):
    at = _offset(bank, address)
    actual = bytes(rom[at:at + end - address + 1])
    actual_sha1 = sha1(actual).hexdigest()
    if actual_sha1 != expected_sha1:
        raise RescuePasswordAuditError(
            "%s at %02X:$%04X-$%04X changed: SHA-1 %s, expected %s"
            % (label, bank, address, end, actual_sha1, expected_sha1)
        )
    return actual


def _public_exchange():
    rows = {}
    for role, text in PUBLIC_EXCHANGE.items():
        expected_length = PUBLIC_LENGTHS[role]
        if len(text) != expected_length:
            raise RescuePasswordAuditError(
                "%s public vector has %d characters, expected %d"
                % (role, len(text), expected_length)
            )
        raw = codec.encode(text)
        if len(raw) != expected_length:
            raise RescuePasswordAuditError(
                "%s public vector encodes to %d bytes, expected %d"
                % (role, len(raw), expected_length)
            )
        if codec.decode(raw) != text:
            raise RescuePasswordAuditError(
                "%s public vector does not round-trip through the native text codec"
                % role
            )
        payload = decode_password(raw, PAYLOAD_LENGTHS[role])
        if encode_payload(payload) != raw:
            raise RescuePasswordAuditError(
                "%s public vector does not round-trip through the packet codec" % role
            )
        rows[role] = {
            "characters": expected_length,
            "native": text,
            "encoded_hex": raw.hex().upper(),
            "payload_hex": payload.hex().upper(),
        }
    return rows


def analyze(rom):
    """Return the frozen native input boundary and external rescue-code fixture."""
    rom = bytes(rom)
    _checked_region(
        rom,
        MODE_DISPATCH_BANK,
        MODE_DISPATCH_ADDRESS,
        MODE_DISPATCH_BYTES,
        "graphical-input mode/maximum dispatcher",
    )
    length_region = _checked_region(
        rom,
        LONG_LENGTH_BANK,
        LONG_LENGTH_ADDRESS,
        LONG_LENGTH_BYTES,
        "long-input length resolver",
    )
    _checked_digest(
        rom,
        PROTOCOL_BANK,
        PROTOCOL_ADDRESS,
        PROTOCOL_END,
        PROTOCOL_SHA1,
        "native password protocol",
    )
    _checked_digest(
        rom,
        CONFIRM_STAGING_BANK,
        CONFIRM_STAGING_ADDRESS,
        CONFIRM_STAGING_END,
        CONFIRM_STAGING_SHA1,
        "graphical-input confirmation staging",
    )
    _checked_digest(
        rom,
        SRAM_STAGING_BANK,
        SRAM_STAGING_ADDRESS,
        SRAM_STAGING_END,
        SRAM_STAGING_SHA1,
        "password SRAM staging",
    )
    table = length_region[-4:]
    mode_indices = {5: 2, 6: 3, 7: 1, 8: 0}
    measured = {
        str(mode): {
            "role": contract["role"],
            "length": table[mode_indices[mode]],
            "status": contract["status"],
        }
        for mode, contract in sorted(LONG_INPUT_MODES.items())
    }
    for mode, contract in LONG_INPUT_MODES.items():
        if measured[str(mode)]["length"] != contract["length"]:
            raise RescuePasswordAuditError(
                "mode %d length is %d, expected %d"
                % (mode, measured[str(mode)]["length"], contract["length"])
            )

    return {
        "schema": SCHEMA,
        "clean_rom_sha1": ROM_SHA1,
        "input_state": {
            "mode": "$%04X" % INPUT_MODE_ADDRESS,
            "position": "$%04X" % INPUT_POSITION_ADDRESS,
            "maximum": "$%04X" % INPUT_MAXIMUM_ADDRESS,
            "buffer": "$%04X" % INPUT_BUFFER_ADDRESS,
        },
        "native_regions": {
            "mode_dispatch": "%02X:$%04X-$%04X"
            % (
                MODE_DISPATCH_BANK,
                MODE_DISPATCH_ADDRESS,
                MODE_DISPATCH_ADDRESS + len(MODE_DISPATCH_BYTES) - 1,
            ),
            "mode_dispatch_sha1": sha1(MODE_DISPATCH_BYTES).hexdigest(),
            "length_resolver": "%02X:$%04X-$%04X"
            % (
                LONG_LENGTH_BANK,
                LONG_LENGTH_ADDRESS,
                LONG_LENGTH_ADDRESS + len(LONG_LENGTH_BYTES) - 1,
            ),
            "length_resolver_sha1": sha1(LONG_LENGTH_BYTES).hexdigest(),
            "length_table_hex": table.hex().upper(),
            "protocol": "%02X:$%04X-$%04X"
            % (PROTOCOL_BANK, PROTOCOL_ADDRESS, PROTOCOL_END),
            "protocol_sha1": PROTOCOL_SHA1,
            "confirmation_staging": "%02X:$%04X-$%04X"
            % (
                CONFIRM_STAGING_BANK,
                CONFIRM_STAGING_ADDRESS,
                CONFIRM_STAGING_END,
            ),
            "confirmation_staging_sha1": CONFIRM_STAGING_SHA1,
            "sram_staging": "%02X:$%04X-$%04X"
            % (SRAM_STAGING_BANK, SRAM_STAGING_ADDRESS, SRAM_STAGING_END),
            "sram_staging_sha1": SRAM_STAGING_SHA1,
        },
        "long_input_modes": measured,
        "native_alphabet": {
            "characters": len(NATIVE_ALPHABET),
            "text": NATIVE_ALPHABET,
            "encoded_hex": NATIVE_ALPHABET_CODES.hex().upper(),
        },
        "payload_lengths": dict(sorted(PAYLOAD_LENGTHS.items())),
        "public_exchange_url": PUBLIC_EXCHANGE_URL,
        "public_exchange": _public_exchange(),
        "codec_status": "reference_packet_codec",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="clean or contract-compatible Shiren GB2 ROM")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        measured = analyze(Path(args.rom).read_bytes())
    except (OSError, ValueError, extract.ExtractError, RescuePasswordAuditError) as exc:
        parser.exit(1, "error: %s\n" % exc)
    if args.json:
        print(json.dumps(measured, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            "rescue input boundary: modes %s; codec %s"
            % (", ".join(measured["long_input_modes"]), measured["codec_status"])
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
