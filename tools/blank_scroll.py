#!/usr/bin/env python3
"""Install a fully English, full-name Blank Scroll editor.

The native mode-1 editor matches the category-filtered item-root table and
considers only roots whose notebook-history bit is set.  The localized mode
accepts the longest English Scroll root and adds the hyphen required by
``Trap-eraser``.  Full names exist only in the editor/matcher: after a match is
resolved to an item ID, the post-match hook restores the native seven-byte
field boundary before the converted Scroll effect runs.
"""
from hashlib import sha1

from cartridge import fix_checksums
import english
import extract
import name6


RUNTIME_BANK = 251
RUNTIME_ADDRESS = 0x4000
MAXIMUM_ADDRESS = 0x4000
INPUT_ADDRESS = 0x4020
SCREEN_ADDRESS = 0x4040
CONFIRM_ADDRESS = 0x4080
RESOLVE_ADDRESS = 0x40B0
MATCHER_ADDRESS = 0x4100
MATCH_TABLE_ADDRESS = 0x4180
CODE_END = 0x4400

INPUT_MODE_ADDRESS = 0xC195
INPUT_MAXIMUM_ADDRESS = 0xC153
INPUT_BUFFER_ADDRESS = 0xC16D
INPUT_SCRATCH_ADDRESS = 0xC18D
MATCH_CACHE_ADDRESS = 0xC196
MODE = 1
MAXIMUM_CHARACTERS = 11
NATIVE_FIELD_CHARACTERS = 7

ROOT_GROUP = 12
ROOT_FIRST = 47
ROOT_LAST = 80
ROOT_DISABLED = (69, 79)
ROOT_MATCHER_BANK = 120
ROOT_MATCHER_ADDRESS = 0x4853
ROOT_HISTORY_ADDRESS = 0xDE1C

HYPHEN_NODE = 52
HYPHEN_CHARACTER = "-"
HYPHEN_TILE_ADDRESS = 0x998D

MAXIMUM_PATCH = (
    0xF4,
    0x4066,
    bytes.fromhex("3EFD217B40CDAC09"),
    MAXIMUM_ADDRESS,
)
INPUT_PATCH = (
    16,
    0x5B66,
    bytes.fromhex("3EFD21D941CDAC09"),
    INPUT_ADDRESS,
)
SCREEN_PATCH = (
    16,
    0x6A4C,
    bytes.fromhex("3EF4214540CDAC09"),
    SCREEN_ADDRESS,
)
CONFIRM_PATCH = (
    0x10,
    0x5B84,
    bytes.fromhex("3E1221F750CDAC09"),
    CONFIRM_ADDRESS,
)
RESOLVE_PATCH = (
    0x7A,
    0x5EF5,
    bytes.fromhex("3E78215543CDAC09"),
    RESOLVE_ADDRESS,
)
CALL_PATCHES = (
    MAXIMUM_PATCH,
    INPUT_PATCH,
    SCREEN_PATCH,
    CONFIRM_PATCH,
    RESOLVE_PATCH,
)
PATCHES = CALL_PATCHES


class BlankScrollError(ValueError):
    """The shared editor, translated roots, or reserved payload changed."""


# Assembled from tools/blank_scroll.asm at $FB:$4000.
ASSEMBLED_CODE = bytes.fromhex(
    "3efd217b40cdac09fa95c1fe01c03e0bea53c1c9000000000000000000000000fa95c1fe01200f79fe34200a064d3e12214c52c3ac093efd21d941c3ac090000"
    "3efd213242cdac09afe04f3e4dea8d99afe04fc90000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "cd0041fa95c1fe012003cdbe403e1221f750c3ac09000000000000000000000000000000000000000000000000000000fa96c1bb2804010000c9010001c93eff"
    "ea74c13ed5ea75c1ea76c1ea77c1ea78c1c900000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "3effea96c1f070f53e02e0702180412afeff28414f2a572a5f2a47d5c5e5116dc11abe202713230520f71afed52804feff2019d1c1d1e5c5211cde7d826f7ea3"
    "c1e128cb79ea96c1f1e070c9e1c158160019d118baf1e070c9000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "2f05800a1233343d4338353834413006010716303f3f383d363106020a193e434d443f423849343206040920383d33313b30333433060806164449493b343406"
    "10091c46383543240f3e34350620071c3b443c31344136064008193e463441241e3f370680060b3e3c3134413807010920303b3b4d3b34424239070207163e3d"
    "424334413a0704090c3e3d354442383e3d3b07080b0e41303338323043383e3d3c0710040f3430413d07200a0e474341303243383e3d3e0740090c304141484d"
    "31303d3f0780080e473e413238423c4008010811343045343d3b48410802070e304143373b4842080407193b3043383d36430808060e4232303f34440810041d"
    "41303f460840091c303d3243443041484708800a123d30323244413043344809010b1d41303f4d3441304234414909020a1c434441334824193e434a0904071b"
    "3442433e323a4b09080a0a434341303243383e3d4c0910080a3b43414438423c4d0920090e473f3b3e42383e3d4e0940040d303c3f500a010b1c40443833241c"
    "44423738ff0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
)


def _offset(bank, address):
    return extract.file_offset(bank, address)


def _far_call(address):
    return bytes(
        (
            0x3E,
            RUNTIME_BANK,
            0x21,
            address & 0xFF,
            address >> 8,
            0xCD,
            0xAC,
            0x09,
        )
    )


def accepted_root_indices():
    """Return the complete native Scroll-root domain, excluding sentinels."""
    disabled = set(ROOT_DISABLED)
    return tuple(
        index
        for index in range(ROOT_FIRST, ROOT_LAST + 1)
        if index not in disabled
    )


def selectable_inputs(names):
    """Return the complete localized root entered for every accepted Scroll."""
    names = tuple(names)
    if max(map(len, names)) > MAXIMUM_CHARACTERS:
        raise BlankScrollError("a Scroll name exceeds the localized input limit")
    return names


def encoded_match_table(roots):
    """Encode the localized full-name table consumed by the ROM matcher."""
    payload = bytearray()
    for index in accepted_root_indices():
        raw = english.encode(roots[index])
        payload.extend((index, index // 8, 1 << (index & 7), len(raw)))
        payload.extend(raw)
    payload.append(0xFF)
    return bytes(payload)


def embedded_match_table(size):
    """Return ``size`` bytes from the checked-in matcher-table payload."""
    start = MATCH_TABLE_ADDRESS - RUNTIME_ADDRESS
    return runtime_payload()[start:start + size]


def runtime_payload():
    if english.ENGLISH_CODES[HYPHEN_CHARACTER] != 0x4D:
        raise BlankScrollError("English hyphen encoding changed")
    if len(ASSEMBLED_CODE) != CODE_END - RUNTIME_ADDRESS:
        raise BlankScrollError("assembled Blank Scroll code length changed")
    return ASSEMBLED_CODE


def owned_ranges():
    return tuple(
        (_offset(bank, address), _offset(bank, address) + len(expected))
        for bank, address, expected, _target in PATCHES
    ) + (
        (
            _offset(RUNTIME_BANK, RUNTIME_ADDRESS),
            _offset(RUNTIME_BANK, CODE_END),
        ),
    )


def install(rom, verify_original=True, checksums=True):
    """Return a name6-enabled ROM with English Blank Scroll input."""
    out = bytearray(rom)
    for bank, address, expected, target in CALL_PATCHES:
        at = _offset(bank, address)
        current = bytes(out[at:at + len(expected)])
        replacement = _far_call(target)
        if verify_original and current not in (expected, replacement):
            raise BlankScrollError(
                "Blank Scroll prerequisite at %s is not installed"
                % extract.location(bank, address)
            )
        out[at:at + len(replacement)] = replacement

    payload = runtime_payload()
    runtime_at = _offset(RUNTIME_BANK, RUNTIME_ADDRESS)
    existing = bytes(out[runtime_at:runtime_at + len(payload)])
    if verify_original and any(existing) and existing != payload:
        raise BlankScrollError(
            "reserved Blank Scroll range is not empty at %s"
            % extract.location(RUNTIME_BANK, RUNTIME_ADDRESS)
        )
    out[runtime_at:runtime_at + len(payload)] = payload
    if checksums:
        fix_checksums(out)
    return bytes(out)


def summary(names):
    names = tuple(names)
    if len(names) != len(accepted_root_indices()):
        raise BlankScrollError("accepted Scroll-root list is incomplete")
    inputs = selectable_inputs(names)
    return {
        "mode": MODE,
        "maximum_characters": MAXIMUM_CHARACTERS,
        "root_group": ROOT_GROUP,
        "root_index_range": [ROOT_FIRST, ROOT_LAST],
        "disabled_indices": list(ROOT_DISABLED),
        "history_bits": "$%04X" % ROOT_HISTORY_ADDRESS,
        "player_facing_match": "full localized root, without ' Scroll'",
        "localized_matcher": extract.location(RUNTIME_BANK, MATCHER_ADDRESS),
        "legacy_matcher_compatibility": extract.location(
            ROOT_MATCHER_BANK, ROOT_MATCHER_ADDRESS
        ),
        "match_cache": "$%04X" % MATCH_CACHE_ADDRESS,
        "native_field_characters": NATIVE_FIELD_CHARACTERS,
        "backend_contract": "resolved Scroll root ID",
        "hyphen_node": HYPHEN_NODE,
        "accepted": [
            {
                "root_index": index,
                "name": name,
                "input": input_text,
            }
            for index, name, input_text in zip(
                accepted_root_indices(), names, inputs
            )
        ],
        "runtime": {
            "bank": RUNTIME_BANK,
            "start": extract.location(RUNTIME_BANK, RUNTIME_ADDRESS),
            "end_exclusive": extract.location(RUNTIME_BANK, CODE_END),
            "sha1": sha1(runtime_payload()).hexdigest(),
        },
    }


def validate_root_catalog(roots):
    """Validate every translated Scroll root and return the public summary."""
    required = set(range(ROOT_FIRST, ROOT_LAST + 1))
    missing = required - set(roots)
    if missing:
        raise BlankScrollError(
            "translated Scroll roots are missing indices: %s"
            % ", ".join(map(str, sorted(missing)))
        )

    disabled = set(ROOT_DISABLED)
    for index in range(ROOT_FIRST, ROOT_LAST + 1):
        name = roots[index]
        try:
            raw = english.encode(name)
        except (KeyError, ValueError) as exc:
            raise BlankScrollError(
                "Scroll root %d cannot be entered: %s" % (index, exc)
            ) from exc
        is_sentinel = bool(raw) and raw[0] == 0x21
        if index in disabled and not is_sentinel:
            raise BlankScrollError(
                "disabled Scroll root %d must retain the $21 sentinel" % index
            )
        if index not in disabled and is_sentinel:
            raise BlankScrollError(
                "enabled Scroll root %d begins with the $21 sentinel" % index
            )

    table = encoded_match_table(roots)
    if len(table) > CODE_END - MATCH_TABLE_ADDRESS:
        raise BlankScrollError("localized Scroll matcher table exceeds its reservation")
    if embedded_match_table(len(table)) != table:
        raise BlankScrollError(
            "translated Scroll roots do not match the embedded full-name table"
        )

    return summary(tuple(roots[index] for index in accepted_root_indices()))
