"""Narrow, guarded mutations used by PyBoy integration fixtures."""

import pyboy_route


BIG_MOAI_STAGE_ADDRESS = 0xC3EF
BIG_MOAI_STAGE_SHADOW_ADDRESS = 0xC3F0
BIG_MOAI_MINIMUM_STAGE = 9
PLAYER_ACTOR_BANK = 1
PLAYER_ACTOR_ADDRESS = 0xD000
PLAYER_ACTOR_CACHE_ADDRESS = 0xFF90
ACTIVE_ACTOR_ADDRESS = 0xFFFC
ACTOR_RECORD_SIZE = 0x20
MAX_HP_OFFSET = 0x15
CURRENT_HP_OFFSET = 0x16


class FixtureMutationError(ValueError):
    """A live fixture no longer satisfies a mutation's safety contract."""


INVENTORY = 0x12C1
INVENTORY_SLOTS = 20
INVENTORY_SENTINEL = 0xFF
OBJECTS = 0x2482
OBJECT_SIZE = 8
OBJECT_COUNT = 128
IDENTIFICATION = 0x2C82
IDENTIFIED = 0xFF
ACTION_FLAGS = 0xC12B
ACTION_INHIBIT_MASK = 0x02
SYNTHESIS_POT_ROOT = 0x71
SYNTHESIS_POT_RUNWAY_RECORDS = 8
SYNTHESIS_POT_CELL_OFFSETS = (5, 6, 7, 10, 11)


def _record(pyboy, index):
    return pyboy_route.work_read(
        pyboy, OBJECTS + index * OBJECT_SIZE, OBJECT_SIZE
    )


def _write_record(pyboy, index, record):
    record = bytes(record)
    if len(record) != OBJECT_SIZE:
        raise FixtureMutationError("an item record must be exactly eight bytes")
    pyboy_route.work_write(pyboy, OBJECTS + index * OBJECT_SIZE, record)


def identify_root(pyboy, root):
    pyboy_route.work_write_byte(pyboy, IDENTIFICATION + root * 2, IDENTIFIED)


def _allow_actions(pyboy):
    pyboy.memory[ACTION_FLAGS] &= ~ACTION_INHIBIT_MASK & 0xFF


def install_item_gallery(pyboy, records):
    """Replace the disposable inventory with twenty reviewed item records."""
    records = tuple(bytes(record) for record in records)
    if len(records) != INVENTORY_SLOTS:
        raise FixtureMutationError("the item gallery must contain twenty records")
    if any(len(record) != OBJECT_SIZE for record in records):
        raise FixtureMutationError("every gallery item must be an eight-byte record")
    targets = [
        index for index in range(OBJECT_COUNT) if _record(pyboy, index) == bytes(8)
    ][:INVENTORY_SLOTS]
    if len(targets) != INVENTORY_SLOTS:
        raise FixtureMutationError("fewer than twenty cleared item records exist")
    for slot, (target, record) in enumerate(zip(targets, records)):
        _write_record(pyboy, target, record)
        pyboy_route.work_write_byte(pyboy, INVENTORY + slot, target)
    for root in (0x09, 0x51, 0x6B):
        identify_root(pyboy, root)
    _allow_actions(pyboy)
    return tuple(targets)


def install_synthesis_lab(pyboy, base, donor, pot):
    """Install a base, donor, and native variable-length Synthesis Pot."""
    base, donor, pot = bytes(base), bytes(donor), bytes(pot)
    if any(len(record) != OBJECT_SIZE for record in (base, donor, pot)):
        raise FixtureMutationError("synthesis items must be eight-byte records")

    inventory = pyboy_route.work_read(pyboy, INVENTORY, INVENTORY_SLOTS)
    occupied = {value for value in inventory if value != INVENTORY_SENTINEL}
    pot_object = None
    for candidate in range(
        OBJECT_COUNT - SYNTHESIS_POT_RUNWAY_RECORDS, -1, -1
    ):
        runway = range(candidate, candidate + SYNTHESIS_POT_RUNWAY_RECORDS)
        if all(index not in occupied and _record(pyboy, index) == bytes(8)
               for index in runway):
            pot_object = candidate
            break
    if pot_object is None:
        raise FixtureMutationError("no cleared eight-record Pot runway exists")

    runway = range(pot_object, pot_object + SYNTHESIS_POT_RUNWAY_RECORDS)
    weapons = [
        index for index in range(OBJECT_COUNT)
        if index not in occupied and index not in runway
        and _record(pyboy, index) == bytes(8)
    ][:2]
    if len(weapons) != 2:
        raise FixtureMutationError("fewer than two cleared weapon records exist")

    _write_record(pyboy, weapons[0], base)
    _write_record(pyboy, weapons[1], donor)
    _write_record(pyboy, pot_object, pot)
    pot_base = OBJECTS + pot_object * OBJECT_SIZE
    for offset in SYNTHESIS_POT_CELL_OFFSETS:
        pyboy_route.work_write_byte(pyboy, pot_base + offset, INVENTORY_SENTINEL)
    pointers = bytes((*weapons, pot_object)) + bytes((INVENTORY_SENTINEL,)) * 17
    pyboy_route.work_write(pyboy, INVENTORY, pointers)
    identify_root(pyboy, SYNTHESIS_POT_ROOT)
    _allow_actions(pyboy)
    return weapons[0], weapons[1], pot_object


def unlock_big_moai(pyboy):
    """Advance only Big Moai's synchronized story-stage pair to stage nine."""
    stage = pyboy.memory[BIG_MOAI_STAGE_ADDRESS]
    shadow = pyboy.memory[BIG_MOAI_STAGE_SHADOW_ADDRESS]
    if stage != shadow:
        raise FixtureMutationError(
            "Big Moai stage mirrors differ: %d != %d" % (stage, shadow)
        )
    if stage > BIG_MOAI_MINIMUM_STAGE:
        raise FixtureMutationError("Big Moai is already beyond the tested stage")
    if stage == BIG_MOAI_MINIMUM_STAGE:
        return False, stage
    pyboy.memory[BIG_MOAI_STAGE_ADDRESS] = BIG_MOAI_MINIMUM_STAGE
    pyboy.memory[BIG_MOAI_STAGE_SHADOW_ADDRESS] = BIG_MOAI_MINIMUM_STAGE
    return True, stage


def prepare_rescue_request(pyboy, target_hp=1):
    """Set the live player and its HRAM mirror to the same current HP."""
    if pyboy.memory[ACTIVE_ACTOR_ADDRESS] != 0:
        raise FixtureMutationError("the active actor is not the player")
    old_bank = pyboy.memory[0xFF70]
    try:
        pyboy.memory[0xFF70] = PLAYER_ACTOR_BANK
        actor = bytes(
            pyboy.memory[
                PLAYER_ACTOR_ADDRESS:PLAYER_ACTOR_ADDRESS + ACTOR_RECORD_SIZE
            ]
        )
        cache = bytes(
            pyboy.memory[
                PLAYER_ACTOR_CACHE_ADDRESS:
                PLAYER_ACTOR_CACHE_ADDRESS + ACTOR_RECORD_SIZE
            ]
        )
        if actor != cache:
            raise FixtureMutationError("the live player and HRAM cache differ")
        maximum = actor[MAX_HP_OFFSET]
        if not 0 < target_hp <= maximum:
            raise FixtureMutationError("target HP is outside the live maximum")
        pyboy.memory[PLAYER_ACTOR_ADDRESS + CURRENT_HP_OFFSET] = target_hp
        pyboy.memory[PLAYER_ACTOR_CACHE_ADDRESS + CURRENT_HP_OFFSET] = target_hp
        return maximum
    finally:
        pyboy.memory[0xFF70] = old_bank
