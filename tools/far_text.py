#!/usr/bin/env python3
"""Install the relocated-script far-pointer selectors.

The stock selectors at 0:$1F58 and 0:$1FA0 call the shared 16-bit table
lookup at 0:$09E0.  Relocated builds replace only those two call operands
with bank-0 routines in the verified zero tail at 0:$3FBD.  Their table
format is ``u16 entry_count`` followed by three bytes per entry:
``address_low, address_high, bank``.

Both callers already save and restore the active ROM bank around the lookup,
but they have different contracts for ``$C4DB``.  The source selector must
publish its selected record bank for the composer.  The direct selector copies
its record immediately and must leave an outer source bank untouched; F6 actor
lookups are nested inside that outer source.  Giving both callers the publishing
routine makes the composer resume a combat sentence at the right address in the
actor-name bank, which turns allocation bytes into text and can overrun WRAM.
"""

import cartridge


SOURCE_CALL_SITE = 0x1F8C
DIRECT_CALL_SITE = 0x1FD3
CALL_SITES = (SOURCE_CALL_SITE, DIRECT_CALL_SITE)
OLD_CALL = bytes.fromhex("CD E0 09")
FAR_SOURCE_LOOKUP_ADDRESS = 0x3FBD

# push hl; push bc; ld h,d; ld l,e; skip u16 count; BC=index;
# HL += index*3; load address+bank; publish/switch bank; restore; return.
FAR_SOURCE_LOOKUP = bytes.fromhex(
    "E5 C5 62 6B 23 23 06 00 4F 09 09 09 "
    "2A 5F 2A 57 7E EA DB C4 F3 E0 F7 EA 00 21 FB C1 E1 C9"
)

# The direct selector needs the same lookup and temporary bank switch, but it
# must not overwrite the source composer's outer record bank at $C4DB.
FAR_DIRECT_LOOKUP_ADDRESS = FAR_SOURCE_LOOKUP_ADDRESS + len(FAR_SOURCE_LOOKUP)
FAR_DIRECT_LOOKUP = bytes.fromhex(
    "E5 C5 62 6B 23 23 06 00 4F 09 09 09 "
    "2A 5F 2A 57 7E F3 E0 F7 EA 00 21 FB C1 E1 C9"
)

SOURCE_CALL = bytes(
    (0xCD, FAR_SOURCE_LOOKUP_ADDRESS & 0xFF, FAR_SOURCE_LOOKUP_ADDRESS >> 8)
)
DIRECT_CALL = bytes(
    (0xCD, FAR_DIRECT_LOOKUP_ADDRESS & 0xFF, FAR_DIRECT_LOOKUP_ADDRESS >> 8)
)
# Compatibility names retained for callers which only describe the publishing
# source-selector routine.
FAR_LOOKUP_ADDRESS = FAR_SOURCE_LOOKUP_ADDRESS
FAR_LOOKUP = FAR_SOURCE_LOOKUP
NEW_CALL = SOURCE_CALL


class FarTextError(ValueError):
    """The selector patch no longer matches its audited stock bytes."""


def owned_ranges():
    return tuple((address, address + len(SOURCE_CALL)) for address in CALL_SITES) + (
        (
            FAR_SOURCE_LOOKUP_ADDRESS,
            FAR_DIRECT_LOOKUP_ADDRESS + len(FAR_DIRECT_LOOKUP),
        ),
    )


def install(rom):
    """Return ``rom`` with the two selector calls and far lookup installed."""
    out = bytearray(rom)
    for address, replacement in (
        (SOURCE_CALL_SITE, SOURCE_CALL),
        (DIRECT_CALL_SITE, DIRECT_CALL),
    ):
        actual = bytes(out[address:address + len(OLD_CALL)])
        # Accept the first implementation, which sent both sites to the source
        # routine, so an already-built diagnostic ROM can be upgraded safely.
        if actual not in (OLD_CALL, SOURCE_CALL, DIRECT_CALL):
            raise FarTextError(
                "selector call at 0:$%04X is %s, expected %s"
                % (address, actual.hex().upper(), OLD_CALL.hex().upper())
            )
        out[address:address + len(replacement)] = replacement

    start = FAR_SOURCE_LOOKUP_ADDRESS
    payload = FAR_SOURCE_LOOKUP + FAR_DIRECT_LOOKUP
    actual = bytes(out[start:start + len(payload)])
    old_payload = FAR_SOURCE_LOOKUP + bytes(len(FAR_DIRECT_LOOKUP))
    if actual not in (bytes(len(payload)), old_payload, payload):
        raise FarTextError(
            "far-selector cave at 0:$%04X is not the verified zero span" % start
        )
    out[start:start + len(payload)] = payload
    cartridge.fix_checksums(out)
    return bytes(out)


def verify(rom):
    """Reject a ROM whose relocated-script selector patch is incomplete."""
    rom = bytes(rom)
    for address, expected in (
        (SOURCE_CALL_SITE, SOURCE_CALL),
        (DIRECT_CALL_SITE, DIRECT_CALL),
    ):
        if rom[address:address + len(expected)] != expected:
            raise FarTextError("far-selector call is absent at 0:$%04X" % address)
    payload = FAR_SOURCE_LOOKUP + FAR_DIRECT_LOOKUP
    if (
        rom[
            FAR_SOURCE_LOOKUP_ADDRESS:FAR_SOURCE_LOOKUP_ADDRESS + len(payload)
        ]
        != payload
    ):
        raise FarTextError("far-selector routines are absent")
    return True
