#!/usr/bin/env python3
"""Audit and reproduce GB2's native Wanderer Rescue password protocol.

The packet codec is a source-independent transcription of the clean-ROM routines at
11:$7B17-$7D8B.  The semantic layer reproduces the SOS builder and the linked
SOS -> Revival -> Thank-You handshake while keeping native display codes at the API edge.
Live two-diary emulator fixtures and localized presentation remain separate work.
"""
import argparse
from dataclasses import dataclass
from hashlib import sha1
import json
from pathlib import Path
import sys

import codec
import english
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

SOS_BUILDER_BANK = 0x11
SOS_BUILDER_ADDRESS = 0x792D
SOS_BUILDER_END = 0x797A
SOS_BUILDER_SHA1 = "5563e92e7ceaeeafaa8081911755b570e2c0746e"

PAYLOAD_RECORD_BANK = 0x0B
PAYLOAD_RECORD_ADDRESS = 0x518A
PAYLOAD_RECORD_END = 0x5287
PAYLOAD_RECORD_SHA1 = "b9b5aeee9cdc01ca10a546e58f38f8383a4ec767"

REVIVAL_ROUTE_BANK = 0x10
REVIVAL_ROUTE_ADDRESS = 0x68DF
REVIVAL_ROUTE_END = 0x6953
REVIVAL_ROUTE_SHA1 = "d067cc2f959c0ab772ccab551cd684f8e4ec9710"

SOS_ROUTE_BANK = 0x10
SOS_ROUTE_ADDRESS = 0x7B8A
SOS_ROUTE_END = 0x7BD1
SOS_ROUTE_SHA1 = "0531c2d396fa017ef274da970a73b2054057bb84"

# The manual requester fixture uses the native actor-0 record rather than story flags.
# Actor records are 32 bytes in WRAM bank 1, and the active record is mirrored at
# $FF90-$FFAF.  The clean-ROM accessors double/halve offset $15 as Max HP and the
# damage routine subtracts from offset $16 as current HP.
PLAYER_ACTOR_WRAM_BANK = 0x01
PLAYER_ACTOR_ADDRESS = 0xD000
PLAYER_ACTOR_FLAT_ADDRESS = 0x1000
ACTOR_RECORD_SIZE = 0x20
ACTOR_CACHE_ADDRESS = 0xFF90
ACTIVE_ACTOR_ADDRESS = 0xFFFC
MAX_HP_OFFSET = 0x15
CURRENT_HP_OFFSET = 0x16

ACTOR_RECORD_ROUTE_BANK = 0x00
ACTOR_RECORD_ROUTE_ADDRESS = 0x03C9
ACTOR_RECORD_ROUTE_END = 0x046B
ACTOR_RECORD_ROUTE_SHA1 = "000e20250bb4463ef8ec4a8da284946479aaea07"

CURRENT_HP_DAMAGE_BANK = 0x00
CURRENT_HP_DAMAGE_ADDRESS = 0x046F
CURRENT_HP_DAMAGE_END = 0x0484
CURRENT_HP_DAMAGE_SHA1 = "f3c3ae3067122a59af3a386170006b15ac2233b4"

ACTOR_HP_ACCESSOR_BANK = 0x07
ACTOR_HP_ACCESSOR_ADDRESS = 0x4A87
ACTOR_HP_ACCESSOR_END = 0x4B53
ACTOR_HP_ACCESSOR_SHA1 = "3c27778e7fea0ebafc6e5c78d75b7ab972b0cdb7"

DIARY_RECORD_BASE = 0xC23C
DIARY_RECORD_SIZE = 0x6A
PAYLOAD_RECORDS = {
    "sos": {"offset": 0x41, "length": 10},
    "revival": {"offset": 0x4B, "length": 10},
    "thank_you": {"offset": 0x55, "length": 8},
    "training": {"offset": 0x22, "length": 6},
}

# The dispatcher maps modes 5-8 to indices 2, 3, 1, and 0 in the final four-byte
# length table. Roles follow the unique documented protocol lengths. Each screen's
# live $C195 value must still be captured before these role names become patch sites.
LONG_INPUT_MODES = {
    5: {"role": "thank_you", "length": 12, "status": "length_confirmed_role_inferred"},
    6: {"role": "training", "length": 9, "status": "length_confirmed_role_inferred"},
    7: {
        "role": "revival",
        "length": 15,
        "status": "role_confirmed_by_direct_caller",
    },
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
LOCALIZED_ALPHABET = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789?!"
)
PAYLOAD_LENGTHS = {"sos": 9, "revival": 10, "thank_you": 8, "training": 6}


class RescuePasswordAuditError(ValueError):
    """The native rescue-password contract no longer matches reviewed evidence."""


class RescuePasswordCodecError(ValueError):
    """A password is outside the native alphabet or fails its packet checksum."""


@dataclass(frozen=True)
class SOSPayload:
    """Semantic fields carried by a native nine-byte SOS packet.

    The requester diary identifier is deliberately named ``diary_id_low16``: the SOS
    builder copies four bytes from SRAM ``$A007`` but the actor-position fields overwrite
    the upper two before packet encoding.  The complete ten-byte diary record retains the
    unpacked X/Y, dungeon, and floor bytes; the displayed packet bit-packs those four
    fields into its final three bytes.
    """

    dungeon_seed: int
    diary_id_low16: int
    x: int
    y: int
    dungeon_id: int
    internal_floor: int

    def __post_init__(self):
        limits = {
            "dungeon_seed": (self.dungeon_seed, 0xFFFFFFFF),
            "diary_id_low16": (self.diary_id_low16, 0xFFFF),
            "x": (self.x, 0x1F),
            "y": (self.y, 0x1F),
            "dungeon_id": (self.dungeon_id, 0x0F),
            "internal_floor": (self.internal_floor, 0x7F),
        }
        for name, (value, maximum) in limits.items():
            if not isinstance(value, int) or isinstance(value, bool):
                raise RescuePasswordCodecError("%s must be an integer" % name)
            if not 0 <= value <= maximum:
                raise RescuePasswordCodecError(
                    "%s is %d, expected 0..%d" % (name, value, maximum)
                )

    def to_payload(self):
        packed_location = (
            self.x
            | (self.y << 5)
            | (self.dungeon_id << 10)
            | (self.internal_floor << 14)
        )
        return (
            self.dungeon_seed.to_bytes(4, "little")
            + self.diary_id_low16.to_bytes(2, "little")
            + packed_location.to_bytes(3, "little")
        )

    def to_diary_record(self):
        """Return the ten-byte unpacked record saved at diary offset ``+$41``."""
        return (
            self.dungeon_seed.to_bytes(4, "little")
            + self.diary_id_low16.to_bytes(2, "little")
            + bytes((self.x, self.y, self.dungeon_id, self.internal_floor))
        )

    @classmethod
    def from_payload(cls, payload):
        payload = bytes(payload)
        if len(payload) != PAYLOAD_LENGTHS["sos"]:
            raise RescuePasswordCodecError(
                "SOS payload has %d bytes, expected %d"
                % (len(payload), PAYLOAD_LENGTHS["sos"])
            )
        packed_location = int.from_bytes(payload[6:9], "little")
        if packed_location >> 21:
            raise RescuePasswordCodecError("SOS location has nonzero reserved bits")
        return cls(
            dungeon_seed=int.from_bytes(payload[0:4], "little"),
            diary_id_low16=int.from_bytes(payload[4:6], "little"),
            x=packed_location & 0x1F,
            y=(packed_location >> 5) & 0x1F,
            dungeon_id=(packed_location >> 10) & 0x0F,
            internal_floor=(packed_location >> 14) & 0x7F,
        )


def encode_sos(fields):
    """Encode one semantic SOS record to native text-code bytes."""
    if not isinstance(fields, SOSPayload):
        raise RescuePasswordCodecError("encode_sos requires an SOSPayload")
    return encode_payload(fields.to_payload())


def decode_sos(raw):
    """Decode one native SOS password to its semantic record."""
    return SOSPayload.from_payload(decode_password(raw, PAYLOAD_LENGTHS["sos"]))


def _alternating_checksum(values):
    """Return the clean-ROM 11:$7C43 even/odd byte sums as ``(even, odd)``."""
    values = bytes(values)
    return sum(values[0::2]) & 0xFF, sum(values[1::2]) & 0xFF


@dataclass(frozen=True)
class RevivalPayload:
    """Fields recoverable from a Revival packet when its SOS record is available.

    Byte 1 of the optional eight-byte gift is not transmitted: the builder overwrites
    that wire byte with an eight-bit weighted checksum of the rescuer's four-byte diary
    ID.  ``gift_bytes[1]`` is therefore canonicalized to zero by the decoder and ignored
    by the encoder, matching the original generator.
    """

    rescuer_diary_checksum: int
    gift_bytes: bytes

    def __post_init__(self):
        if not isinstance(self.rescuer_diary_checksum, int) or isinstance(
            self.rescuer_diary_checksum, bool
        ):
            raise RescuePasswordCodecError(
                "rescuer_diary_checksum must be an integer"
            )
        if not 0 <= self.rescuer_diary_checksum <= 0xFF:
            raise RescuePasswordCodecError(
                "rescuer_diary_checksum is %d, expected 0..255"
                % self.rescuer_diary_checksum
            )
        gift = bytes(self.gift_bytes)
        if len(gift) != 8:
            raise RescuePasswordCodecError(
                "Revival gift has %d bytes, expected 8" % len(gift)
            )
        object.__setattr__(self, "gift_bytes", gift)

    def to_payload(self, sos):
        if not isinstance(sos, SOSPayload):
            raise RescuePasswordCodecError(
                "Revival encoding requires the matching SOSPayload"
            )
        seed = sos.dungeon_seed.to_bytes(4, "little")
        mask = seed + seed
        payload = bytearray(
            (mask[index] + self.gift_bytes[index]) & 0xFF
            for index in range(8)
        )
        payload[1] = self.rescuer_diary_checksum
        even, odd = _alternating_checksum(sos.to_diary_record()[:9])
        payload.extend((even, odd))
        return bytes(payload)

    @classmethod
    def from_payload(cls, payload, sos):
        payload = bytes(payload)
        if len(payload) != PAYLOAD_LENGTHS["revival"]:
            raise RescuePasswordCodecError(
                "Revival payload has %d bytes, expected %d"
                % (len(payload), PAYLOAD_LENGTHS["revival"])
            )
        if not isinstance(sos, SOSPayload):
            raise RescuePasswordCodecError(
                "Revival decoding requires the matching SOSPayload"
            )
        even, odd = _alternating_checksum(sos.to_diary_record()[:9])
        if payload[8:10] != bytes((even, odd)):
            raise RescuePasswordCodecError(
                "Revival password does not match the SOS checksum"
            )
        seed = sos.dungeon_seed.to_bytes(4, "little")
        mask = seed + seed
        gift = bytearray(
            (payload[index] - mask[index]) & 0xFF for index in range(8)
        )
        gift[1] = 0
        return cls(payload[1], bytes(gift))


def encode_revival(fields, sos):
    """Encode one semantic Revival record for its matching SOS request."""
    if not isinstance(fields, RevivalPayload):
        raise RescuePasswordCodecError("encode_revival requires a RevivalPayload")
    return encode_payload(fields.to_payload(sos))


def decode_revival(raw, sos):
    """Decode and bind a native Revival password to its matching SOS request."""
    return RevivalPayload.from_payload(
        decode_password(raw, PAYLOAD_LENGTHS["revival"]), sos
    )


def thank_you_payload(sos, revival):
    """Build the eight-byte acknowledgement payload for one completed rescue."""
    if not isinstance(sos, SOSPayload) or not isinstance(revival, RevivalPayload):
        raise RescuePasswordCodecError(
            "Thank-You generation requires SOSPayload and RevivalPayload"
        )
    seed = sos.dungeon_seed.to_bytes(4, "little")
    even, odd = _alternating_checksum(sos.to_diary_record()[:9])
    return bytes(
        (
            revival.gift_bytes[0],
            revival.rescuer_diary_checksum,
            revival.gift_bytes[2],
            odd,
            odd,
            even,
            (~seed[2]) & 0xFF,
            (~seed[3]) & 0xFF,
        )
    )


def encode_thank_you(sos, revival):
    """Encode the Thank-You password paired with an SOS and Revival record."""
    return encode_payload(thank_you_payload(sos, revival))


def validate_exchange(sos_raw, revival_raw, thank_you_raw):
    """Validate all three passwords in one native rescue exchange."""
    sos = decode_sos(sos_raw)
    revival = decode_revival(revival_raw, sos)
    actual = decode_password(thank_you_raw, PAYLOAD_LENGTHS["thank_you"])
    expected = thank_you_payload(sos, revival)
    if actual != expected:
        raise RescuePasswordCodecError(
            "Thank-You password does not match the SOS and Revival passwords"
        )
    return sos, revival


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
LOCALIZED_ALPHABET_CODES = english.encode(LOCALIZED_ALPHABET)


def localize_password(raw):
    """Map native rescue code bytes to the frozen 64-symbol English alphabet."""
    raw = bytes(raw)
    try:
        return "".join(
            LOCALIZED_ALPHABET[NATIVE_ALPHABET_CODES.index(code)]
            for code in raw
        )
    except ValueError as error:
        code = next(code for code in raw if code not in NATIVE_ALPHABET_CODES)
        raise RescuePasswordCodecError(
            "byte $%02X is not in the native rescue alphabet" % code
        ) from error


def delocalize_password(text):
    """Map a case-sensitive English rescue password back to native text bytes."""
    if not isinstance(text, str):
        raise RescuePasswordCodecError("localized password must be text")
    unknown = next(
        (character for character in text if character not in LOCALIZED_ALPHABET),
        None,
    )
    if unknown is not None:
        raise RescuePasswordCodecError(
            "character %r is not in the localized rescue alphabet" % unknown
        )
    return bytes(
        NATIVE_ALPHABET_CODES[LOCALIZED_ALPHABET.index(character)]
        for character in text
    )


def localized_display_codes(raw):
    """Return the English-font byte sequence for native rescue code bytes."""
    return english.encode(localize_password(raw))


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
            "localized": localize_password(raw),
            "encoded_hex": raw.hex().upper(),
            "payload_hex": payload.hex().upper(),
        }
        if role == "sos":
            fields = SOSPayload.from_payload(payload)
            rows[role]["semantic_fields"] = {
                "diary_id_low16": "$%04X" % fields.diary_id_low16,
                "dungeon_id": fields.dungeon_id,
                "dungeon_seed": "$%08X" % fields.dungeon_seed,
                "internal_floor": fields.internal_floor,
                "x": fields.x,
                "y": fields.y,
            }
    _sos, revival = validate_exchange(
        bytes.fromhex(rows["sos"]["encoded_hex"]),
        bytes.fromhex(rows["revival"]["encoded_hex"]),
        bytes.fromhex(rows["thank_you"]["encoded_hex"]),
    )
    rows["revival"]["semantic_fields"] = {
        "gift_hex_byte_1_not_transmitted": revival.gift_bytes.hex().upper(),
        "rescuer_diary_checksum": "$%02X" % revival.rescuer_diary_checksum,
        "sos_match": True,
    }
    rows["thank_you"]["semantic_fields"] = {
        "exchange_match": True,
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
    # Check the semantic builder before the broader containing protocol range so damage
    # reports the most specific contract that failed.
    _checked_digest(
        rom,
        SOS_BUILDER_BANK,
        SOS_BUILDER_ADDRESS,
        SOS_BUILDER_END,
        SOS_BUILDER_SHA1,
        "SOS semantic builder",
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
    _checked_digest(
        rom,
        PAYLOAD_RECORD_BANK,
        PAYLOAD_RECORD_ADDRESS,
        PAYLOAD_RECORD_END,
        PAYLOAD_RECORD_SHA1,
        "diary payload-record dispatcher",
    )
    _checked_digest(
        rom,
        REVIVAL_ROUTE_BANK,
        REVIVAL_ROUTE_ADDRESS,
        REVIVAL_ROUTE_END,
        REVIVAL_ROUTE_SHA1,
        "Revival decode and Thank-You generation route",
    )
    _checked_digest(
        rom,
        SOS_ROUTE_BANK,
        SOS_ROUTE_ADDRESS,
        SOS_ROUTE_END,
        SOS_ROUTE_SHA1,
        "SOS generation route",
    )
    _checked_digest(
        rom,
        ACTOR_RECORD_ROUTE_BANK,
        ACTOR_RECORD_ROUTE_ADDRESS,
        ACTOR_RECORD_ROUTE_END,
        ACTOR_RECORD_ROUTE_SHA1,
        "actor record/cache route",
    )
    _checked_digest(
        rom,
        CURRENT_HP_DAMAGE_BANK,
        CURRENT_HP_DAMAGE_ADDRESS,
        CURRENT_HP_DAMAGE_END,
        CURRENT_HP_DAMAGE_SHA1,
        "current-HP damage route",
    )
    _checked_digest(
        rom,
        ACTOR_HP_ACCESSOR_BANK,
        ACTOR_HP_ACCESSOR_ADDRESS,
        ACTOR_HP_ACCESSOR_END,
        ACTOR_HP_ACCESSOR_SHA1,
        "actor Max-HP/current-HP accessors",
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
            "sos_builder": "%02X:$%04X-$%04X"
            % (SOS_BUILDER_BANK, SOS_BUILDER_ADDRESS, SOS_BUILDER_END),
            "sos_builder_sha1": SOS_BUILDER_SHA1,
            "payload_record_dispatcher": "%02X:$%04X-$%04X"
            % (
                PAYLOAD_RECORD_BANK,
                PAYLOAD_RECORD_ADDRESS,
                PAYLOAD_RECORD_END,
            ),
            "payload_record_dispatcher_sha1": PAYLOAD_RECORD_SHA1,
            "revival_thank_you_route": "%02X:$%04X-$%04X"
            % (REVIVAL_ROUTE_BANK, REVIVAL_ROUTE_ADDRESS, REVIVAL_ROUTE_END),
            "revival_thank_you_route_sha1": REVIVAL_ROUTE_SHA1,
            "sos_route": "%02X:$%04X-$%04X"
            % (SOS_ROUTE_BANK, SOS_ROUTE_ADDRESS, SOS_ROUTE_END),
            "sos_route_sha1": SOS_ROUTE_SHA1,
            "actor_record_route": "%02X:$%04X-$%04X"
            % (
                ACTOR_RECORD_ROUTE_BANK,
                ACTOR_RECORD_ROUTE_ADDRESS,
                ACTOR_RECORD_ROUTE_END,
            ),
            "actor_record_route_sha1": ACTOR_RECORD_ROUTE_SHA1,
            "current_hp_damage_route": "%02X:$%04X-$%04X"
            % (
                CURRENT_HP_DAMAGE_BANK,
                CURRENT_HP_DAMAGE_ADDRESS,
                CURRENT_HP_DAMAGE_END,
            ),
            "current_hp_damage_route_sha1": CURRENT_HP_DAMAGE_SHA1,
            "actor_hp_accessors": "%02X:$%04X-$%04X"
            % (
                ACTOR_HP_ACCESSOR_BANK,
                ACTOR_HP_ACCESSOR_ADDRESS,
                ACTOR_HP_ACCESSOR_END,
            ),
            "actor_hp_accessors_sha1": ACTOR_HP_ACCESSOR_SHA1,
        },
        "requester_fixture_state": {
            "active_actor": "$%04X" % ACTIVE_ACTOR_ADDRESS,
            "actor_cache": "$%04X" % ACTOR_CACHE_ADDRESS,
            "actor_record": "%d:$%04X" % (
                PLAYER_ACTOR_WRAM_BANK,
                PLAYER_ACTOR_ADDRESS,
            ),
            "actor_record_flat_wram": "$%04X" % PLAYER_ACTOR_FLAT_ADDRESS,
            "actor_record_size": ACTOR_RECORD_SIZE,
            "current_hp_offset": "$%02X" % CURRENT_HP_OFFSET,
            "max_hp_offset": "$%02X" % MAX_HP_OFFSET,
        },
        "diary_payload_records": {
            "base": "$%04X" % DIARY_RECORD_BASE,
            "record_size": "$%02X" % DIARY_RECORD_SIZE,
            "stages": {
                role: {
                    "length": row["length"],
                    "offset": "$%02X" % row["offset"],
                }
                for role, row in sorted(PAYLOAD_RECORDS.items())
            },
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
        "codec_status": "reference_three_password_handshake_codec",
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
