from pathlib import Path
import re
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import extract
import mesen_state


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
LOADOUT = ROOT / "tools" / "mesen_prepare_endgame.lua"
ADVANCE = ROOT / "tools" / "mesen_advance_floor.lua"


def lua_constants(source):
    return {
        name: int(value, 0)
        for name, value in re.findall(
            r"^local\s+([A-Z][A-Z0-9_]*)\s*=\s*(0x[0-9A-Fa-f]+|[0-9]+)\s*$",
            source,
            re.MULTILINE,
        )
    }


def lua_record(source, name, constants):
    match = re.search(
        r"^local\s+%s\s*=\s*\{([^}]*)\}" % re.escape(name),
        source,
        re.MULTILINE,
    )
    if match is None:
        raise AssertionError("Lua record %s was not found" % name)
    values = []
    for token in match.group(1).split(","):
        token = token.strip()
        values.append(constants[token] if token in constants else int(token, 0))
    return bytes(values)


def item_definition(rom, item_id):
    pointer_at = extract.file_offset(0x77, 0x552E + item_id * 2)
    pointer = int.from_bytes(rom[pointer_at:pointer_at + 2], "little")
    at = extract.file_offset(0x77, pointer)
    return rom[at:at + 16]


def stairs_in(work_ram, constants):
    found = []
    for cell, object_index in enumerate(
        work_ram[
            constants["FLOOR_OBJECT_GRID"]:
            constants["FLOOR_OBJECT_GRID"] + constants["MAP_CELLS"]
        ]
    ):
        if object_index >= constants["OBJECT_COUNT"]:
            continue
        at = constants["OBJECTS"] + object_index * constants["OBJECT_SIZE"]
        record = work_ram[at:at + constants["OBJECT_SIZE"]]
        if record[:2] == bytes((constants["STAIR_ITEM"], constants["STAIR_CLASS"])):
            found.append((cell % constants["MAP_WIDTH"], cell // constants["MAP_WIDTH"]))
    return found


class MesenEndgameLoadoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = LOADOUT.read_text(encoding="utf-8")
        cls.constants = lua_constants(cls.source)
        cls.weapon = lua_record(cls.source, "WEAPON_RECORD", cls.constants)
        cls.shield = lua_record(cls.source, "SHIELD_RECORD", cls.constants)

    def test_level_and_equipment_contract(self):
        self.assertEqual(99, self.constants["MAX_LEVEL"])
        self.assertEqual(250, self.constants["MAX_HP"])
        self.assertEqual(bytes.fromhex("C09A5E"), lua_record(
            self.source, "LEVEL_99_EXPERIENCE", self.constants
        ))
        self.assertEqual(bytes.fromhex("100128631CFF9F09"), self.weapon)
        self.assertEqual(bytes.fromhex("30021E631CF9FF2F"), self.shield)

    def test_only_conservative_positive_seal_bits_are_enabled(self):
        weapon_bits = int.from_bytes(self.weapon[5:8], "little")
        shield_bits = int.from_bytes(self.shield[5:8], "little")
        self.assertEqual(set(range(22)) - {13, 14, 17, 18, 20, 21}, {
            bit for bit in range(22) if weapon_bits & (1 << bit)
        })
        self.assertEqual(set(range(23)) - {1, 2, 20, 22}, {
            bit for bit in range(23) if shield_bits & (1 << bit)
        })
        self.assertEqual(0, weapon_bits >> 22)
        self.assertEqual(0, shield_bits >> 23)

    def test_japanese_rom_definitions_and_level_99_threshold_match(self):
        path = ROOT / ROM_NAME
        if not path.is_file():
            self.skipTest("matching Japanese ROM is required")
        rom = path.read_bytes()
        self.assertEqual(extract.ROM_SHA1, __import__("hashlib").sha1(rom).hexdigest())

        # Item-definition byte 12 is copied to live equipment byte 2. The selected
        # records therefore retain the real bases rather than displaying +99 on a
        # zero-strength injected object.
        self.assertEqual(self.weapon[2], item_definition(rom, self.weapon[0])[12])
        self.assertEqual(self.shield[2], item_definition(rom, self.shield[0])[12])

        threshold_at = extract.file_offset(
            0x7E, 0x7B33 + (self.constants["MAX_LEVEL"] - 1) * 3
        )
        self.assertEqual(bytes.fromhex("C09A5E"), rom[threshold_at:threshold_at + 3])

    def test_final_gate_has_valid_equipped_targets_without_inventory_loss(self):
        path = ROOT / "SaveStates" / "final-gate.mss"
        if not path.is_file():
            self.skipTest("final-gate Mesen state is required")
        fields = mesen_state.load_fields(path)
        work = fields["workRam"]
        high = fields["highRam"]
        actor = work[0x1000:0x1020]
        self.assertEqual(actor, high[0x10:0x30])
        self.assertEqual(0, high[0x7C])

        inventory = work[0x12C1:0x12D5]
        weapon_object, shield_object = work[0x12B1], work[0x12B2]
        self.assertIn(weapon_object, inventory)
        self.assertIn(shield_object, inventory)
        weapon_at = 0x2482 + weapon_object * 8
        shield_at = 0x2482 + shield_object * 8
        self.assertEqual(1, work[weapon_at + 1])
        self.assertEqual(2, work[shield_at + 1])

        mutated = bytearray(work)
        mutated[weapon_at:weapon_at + 8] = self.weapon
        mutated[shield_at:shield_at + 8] = self.shield
        mutated[0x12A0:0x12A3] = bytes.fromhex("C09A5E")
        for offset, value in ((2, 99), (10, 99), (11, 250), (12, 250)):
            mutated[0x1000 + offset] = value
        self.assertEqual(inventory, mutated[0x12C1:0x12D5])
        self.assertEqual(self.weapon, mutated[weapon_at:weapon_at + 8])
        self.assertEqual(self.shield, mutated[shield_at:shield_at + 8])

    def test_empty_categories_can_use_two_clear_records_without_replacing_mamel_item(self):
        path = ROOT / "SaveStates" / "Mamel.mss"
        if not path.is_file():
            self.skipTest("Mamel Mesen state is required")
        work = mesen_state.load_fields(path)["workRam"]
        inventory = work[0x12C1:0x12D5]
        self.assertGreaterEqual(inventory.count(0xFF), 2)
        occupied = {value for value in inventory if value != 0xFF}
        occupied.update(value for value in work[0x3800:0x3C00] if value < 128)
        cleared = [
            index for index in range(128)
            if index not in occupied
            and work[0x2482 + index * 8:0x248A + index * 8] == bytes(8)
        ]
        self.assertGreaterEqual(len(cleared), 2)
        self.assertEqual(0, inventory[0])


class MesenAdvanceFloorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ADVANCE.read_text(encoding="utf-8")
        cls.constants = lua_constants(cls.source)

    def test_uses_native_staircase_and_never_writes_the_floor_counter(self):
        self.assertEqual(0xCA, self.constants["STAIR_ITEM"])
        self.assertEqual(0x0C, self.constants["STAIR_CLASS"])
        self.assertNotIn("writeWork(FLOOR", self.source)
        self.assertIn("emu.setInput", self.source)
        self.assertIn("emu.removeEventCallback", self.source)
        self.assertIn("dungeon ~= oldDungeon or floor ~= oldFloor", self.source)
        self.assertNotIn("native transition started", self.source)

    def test_two_independent_mesen_floors_resolve_one_staircase(self):
        expected = {
            "Mamel.mss": (5, 18),
            "final-gate.mss": (24, 22),
        }
        for name, coordinate in expected.items():
            path = ROOT / "SaveStates" / name
            if not path.is_file():
                self.skipTest("%s is required" % name)
            work = mesen_state.load_fields(path)["workRam"]
            with self.subTest(state=name):
                self.assertEqual([coordinate], stairs_in(work, self.constants))

    def test_each_fixture_has_a_safe_adjacent_setup_cell(self):
        expected = {
            "Mamel.mss": ((5, 18), (5, 17)),
            "final-gate.mss": ((24, 22), (23, 22)),
        }
        for name, (stair, preferred) in expected.items():
            path = ROOT / "SaveStates" / name
            if not path.is_file():
                self.skipTest("%s is required" % name)
            fields = mesen_state.load_fields(path)
            work = fields["workRam"]
            high = fields["highRam"]
            old = (high[0x13], high[0x14])
            candidates = (
                (stair[0], stair[1] - 1),
                (stair[0], stair[1] + 1),
                (stair[0] - 1, stair[1]),
                (stair[0] + 1, stair[1]),
            )

            def safe(point):
                x, y = point
                cell = y * 32 + x
                terrain = work[0x3000 + cell]
                actor = work[0x3400 + cell]
                expected_actor = 0 if point == old else 0xFF
                return (
                    terrain & 0x80
                    and actor == expected_actor
                    and work[0x3800 + cell] == 0xFF
                    and work[0x3C00 + cell] == 0xFF
                )

            safe_candidates = [point for point in candidates if safe(point)]
            with self.subTest(state=name):
                self.assertIn(preferred, safe_candidates)
                if old in safe_candidates:
                    self.assertEqual(preferred, old)


if __name__ == "__main__":
    unittest.main()
