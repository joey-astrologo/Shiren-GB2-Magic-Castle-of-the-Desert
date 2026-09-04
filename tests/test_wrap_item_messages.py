from hashlib import sha1
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build as translation_build
import capture_dialogue
import english
import english_font
import extract
import layout
import pyboy_state
import runtime_widths
import surfaces
import translations
import wrap_item_messages


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
ROM_SHA1 = "5264f6d0c4f12c9144de1d12fddadbadd82b3e33"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "item_message_wrap.json").read_text(
        encoding="utf-8"
    )
)


class ItemMessageWrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("matching original ROM not present")
        cls.rom = cls.path.read_bytes()
        if sha1(cls.rom).hexdigest() != ROM_SHA1:
            raise unittest.SkipTest("matching original ROM not present")
        cls.result = extract.extract(cls.rom)
        cls.eligible = wrap_item_messages.message_rows(cls.result)
        cls.drafts = wrap_item_messages.read_draft(
            ROOT / "script" / "drafts" / "item_messages.tsv", cls.eligible
        )
        cls.state = wrap_item_messages.load_state(
            ROOT / "script" / "drafts" / "item_messages.generated.json",
            cls.result,
            cls.eligible,
        )
        cls.translated = translations.load_path(
            ROOT / "script" / "en", cls.result["records"]
        )
        cls.font_rom = english_font.install(cls.rom)
        cls.runtime = runtime_widths.analyze(
            cls.font_rom, cls.result, cls.translated
        )

    def test_source_free_family_contract_is_frozen(self):
        wrapped = {
            row.record.id: self.translated[(row.record.bank, row.record.address)].text
            for row in self.eligible
            if self.drafts[row.record.id].draft
        }
        measured = wrap_item_messages.contract_summary(
            self.result, self.eligible, self.drafts, wrapped, self.state
        )
        self.assertEqual(FIXTURE, measured)
        self.assertEqual(list(range(20, 170)), [row.index for row in self.eligible])
        self.assertEqual(
            FIXTURE["deferred_indices"],
            [
                row.index
                for row in self.eligible
                if not self.drafts[row.record.id].draft
            ],
        )

    def test_every_generated_message_is_safe_and_idempotent(self):
        generated = self.state["generated"]
        self.assertEqual(150, len(generated))
        for row in self.eligible:
            draft = self.drafts[row.record.id].draft
            if not draft:
                self.assertNotIn(row.record.id, generated)
                continue
            with self.subTest(index=row.index, record=row.record.id):
                text = self.translated[(row.record.bank, row.record.address)].text
                self.assertEqual(
                    text,
                    wrap_item_messages.wrap_message(
                        self.font_rom,
                        row.record,
                        draft,
                        self.runtime.contract,
                    ),
                )
                self.assertEqual(
                    sha1(draft.encode("utf-8")).hexdigest(),
                    generated[row.record.id]["draft_sha1"],
                )
                self.assertEqual(
                    sha1(text.encode("utf-8")).hexdigest(),
                    generated[row.record.id]["wrapped_sha1"],
                )
                measured = layout.source_layout(
                    self.font_rom,
                    english.encode_source(text),
                    mode=0x01,
                    runtime_contract=self.runtime.contract,
                    record_id=row.record.id,
                    simulate_soft_wrap=True,
                )
                self.assertTrue(measured.safe)
                self.assertFalse(measured.unresolved_dynamic_offsets)

    def test_reviewed_pickup_and_primary_verb_wording_is_present(self):
        expected = {
            27: "Equipped <cF3><number:19:C5>.",
            30: "Waved <cF3><number:19:C5>.",
            31: "Read <cF3><number:19:C5>.",
            32: "Made <number:19:C5> <cF3>into medicine <cF3>and consumed it.",
            34: "Ate <cF3><number:19:C5>.",
            94: "Got <cF3><number:19:C5>.",
            95: "Put down <cF3><number:19:C5>.",
            96: "Discarded <cF3><number:19:C5>.",
        }
        by_index = {row.index: row.record for row in self.eligible}
        for index, text in expected.items():
            record = by_index[index]
            with self.subTest(index=index):
                self.assertEqual(
                    text,
                    self.translated[(record.bank, record.address)].text,
                )

    def test_reviewed_trap_operation_wording_is_present(self):
        expected = {
            145: "Placed <lookup:19:C5> on<br>the ground.",
            146: "Modified <lookup:19:C5> <cF3>into <lookup:1B:C5>.",
            147: "Picked up <lookup:19:C5><br>as Trap Parts.",
            148: "<lookup:19:C5> is already <cF3>set.",
            149: "This trap cannot be modified.",
            150: "It could not be salvaged as<br>Trap Parts.",
            151: "<lookup:19:C5> got damp<br>and broke.",
            152: "Broke <lookup:19:C5>.",
            153: "Trap Parts cannot be<br>exchanged.",
        }
        by_index = {row.index: row.record for row in self.eligible}
        for index, text in expected.items():
            record = by_index[index]
            with self.subTest(index=index):
                self.assertEqual(
                    text,
                    self.translated[(record.bank, record.address)].text,
                )

    def test_reviewed_actor_message_wording_is_present(self):
        expected = {
            25: "<number:19:C5> <cF3>hit <lookup:1A:C5>.",
            39: "<lookup:19:C5> <cF3>choked on <cF3><number:1B:C5>.",
            40: "<lookup:19:C5> <cF3>turned into a <cF3>Squid Sushi Scroll.",
            69: "<lookup:19:C5> <cF3>failed to emerge.",
            75: "<lookup:19:C5> was <cF3>sucked into <cF3><number:1B:C5>.",
            88: "<lookup:19:C5> <cF3>splashed water.",
            113: "<lookup:19:C5> vanished<br>from the dungeon!",
            135: "<lookup:19:C5> was not <cF3>carrying anything.",
            142: "A fiery breath scorched <cF3><lookup:19:C5>!",
        }
        by_index = {row.index: row.record for row in self.eligible}
        for index, text in expected.items():
            record = by_index[index]
            with self.subTest(index=index):
                self.assertEqual(
                    text,
                    self.translated[(record.bank, record.address)].text,
                )


class LiveLocalizedItemMessageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("matching original ROM not present")
        cls.rom = cls.path.read_bytes()
        if sha1(cls.rom).hexdigest() != ROM_SHA1:
            raise unittest.SkipTest("matching original ROM not present")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))
        result = extract.extract(cls.rom)
        translated = translations.load_path(ROOT / "script" / "en", result["records"])
        cls.font_rom = english_font.install(cls.rom)
        runtime = runtime_widths.analyze(cls.font_rom, result, translated)
        output, _allocation, _validation = translation_build.build_rom(
            cls.rom,
            translations.encoded_overrides(translated),
            runtime_contract=runtime.contract,
        )
        cls.temporary = tempfile.TemporaryDirectory()
        cls.localized_path = Path(cls.temporary.name) / "localized.gbc"
        cls.localized_path.write_bytes(output)

        owner = cls.PyBoy(str(cls.path), window="null")
        owner.set_emulation_speed(0)
        try:
            capture_dialogue.run_to_dialogue(owner)
            for current in range(15000):
                if current % 180 == 0:
                    owner.button("a", capture_dialogue.PRESS_FRAMES)
                owner.tick()
            state = io.BytesIO()
            owner.save_state(state)
            cls.state_bytes = state.getvalue()
        finally:
            owner.stop(save=False)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def _seed_inventory(self, target):
        old_svbk = target.memory[0xFF70]
        target.memory[0xFF70] = surfaces.ITEM_INVENTORY_WRAM_BANK
        for slot, seed in enumerate(surfaces.ITEM_CATEGORY_SEEDS):
            target.memory[surfaces.ITEM_INVENTORY_BASE + slot] = seed.object_index
        target.memory[
            surfaces.ITEM_INVENTORY_BASE + len(surfaces.ITEM_CATEGORY_SEEDS)
        ] = surfaces.ITEM_INVENTORY_SENTINEL
        target.memory[0xFF70] = surfaces.ITEM_OBJECT_WRAM_BANK
        for seed in surfaces.ITEM_CATEGORY_SEEDS:
            object_at = (
                surfaces.ITEM_OBJECT_BASE
                + seed.object_index * surfaces.ITEM_OBJECT_SIZE
            )
            for offset, value in enumerate(seed.object_record):
                target.memory[object_at + offset] = value
        target.memory[0xFF70] = old_svbk & 7

    def _run_action(self, inputs, final_frame):
        pyboy = self.PyBoy(str(self.localized_path), window="null")
        pyboy.set_emulation_speed(0)
        frame = [0]
        events = []

        def at_full_renderer(_context=None):
            if frame[0] < 200:
                return
            raw = bytearray()
            for offset in range(0x100):
                value = pyboy.memory[0xC800 + offset]
                raw.append(value)
                if value == 0xFF:
                    break
            events.append(bytes(raw))

        try:
            pyboy.load_state(io.BytesIO(self.state_bytes))
            self._seed_inventory(pyboy)
            pyboy.memory[surfaces.ITEM_ACTION_GLOBAL_GATE_ADDRESS] &= (
                ~surfaces.ITEM_ACTION_GLOBAL_GATE_MASK & 0xFF
            )
            pyboy.hook_register(
                *layout.FULL_RENDERER_ENTRY, at_full_renderer, None
            )
            scheduled = dict(inputs)
            for current in range(final_frame + 1):
                frame[0] = current
                if current in scheduled:
                    pyboy.button(
                        scheduled[current], capture_dialogue.PRESS_FRAMES
                    )
                pyboy.tick()
            return events
        finally:
            pyboy.stop(save=False)

    def test_live_place_and_eat_routes_expand_english_item_names(self):
        place = next(
            route
            for route in surfaces.ITEM_ACTION_RESULT_ROUTES
            if route[0] == "place"
        )
        place_inputs = ((0, "b"), (100, "a"), (200, "a"), *place[3])
        place_events = self._run_action(place_inputs, place[4])
        self.assertEqual(
            1,
            place_events.count(
                english.encode("Put down ")
                + b"\xF3"
                + english.encode("Club.")
                + b"\xFF"
            ),
        )

        eat = next(
            route for route in surfaces.ITEM_PRIMARY_ACTION_ROUTES if route[0] == "eat"
        )
        eat_inputs = [(0, "b"), (100, "a")]
        eat_inputs.extend((150 + 50 * index, "down") for index in range(eat[2]))
        eat_inputs.append((200 + 50 * eat[2], "a"))
        eat_inputs.extend(eat[5])
        eat_events = self._run_action(eat_inputs, eat[6])
        self.assertEqual(
            1,
            eat_events.count(
                english.encode("Ate ")
                + b"\xF3"
                + english.encode("Onigiri.")
                + b"\xFF"
            ),
        )

    def test_live_drink_route_uses_balanced_native_soft_wrap(self):
        drink = next(
            route
            for route in surfaces.ITEM_PRIMARY_ACTION_ROUTES
            if route[0] == "drink"
        )
        inputs = [(0, "b"), (100, "a")]
        inputs.extend((150 + 50 * index, "down") for index in range(drink[2]))
        inputs.append((200 + 50 * drink[2], "a"))
        inputs.extend(drink[5])
        events = self._run_action(inputs, drink[6])
        expected = (
            english.encode("Made Herb ")
            + b"\xF3"
            + english.encode("into medicine ")
            + b"\xFD\xF3"
            + english.encode("and consumed it.")
            + b"\xFF"
        )
        self.assertEqual(1, events.count(expected))
        measured = layout.renderer_layout(self.font_rom, expected[:-1], mode=0x01)
        self.assertEqual((116, 75), measured.line_widths)
        self.assertFalse(measured.auto_wraps)

    def test_live_at_feet_route_draws_relocated_english_trap_names(self):
        representatives = {
            1: "Poison Arrow Trap",
            18: "Wooden Arrow Trap",
            22: "Rage Trap",
        }

        for trap_index, expected in representatives.items():
            with self.subTest(trap=trap_index, name=expected):
                pyboy = self.PyBoy(str(self.localized_path), window="null")
                pyboy.set_emulation_speed(0)
                redirected = [False]
                draws = []

                def at_dispatch(_context=None):
                    if redirected[0]:
                        return
                    redirected[0] = True
                    pyboy.register_file.A = surfaces.AT_FEET_ENTRY[0]
                    pyboy.register_file.HL = surfaces.AT_FEET_ENTRY[1]
                    pyboy.register_file.C = 1

                def at_direct_draw(_context=None):
                    pointer = (
                        (pyboy.register_file.D << 8) | pyboy.register_file.E
                    )
                    raw = bytearray()
                    for offset in range(0x100):
                        value = pyboy.memory[(pointer + offset) & 0xFFFF]
                        if value == 0xFF:
                            break
                        raw.append(value)
                    draws.append(bytes(raw))

                def force_classifier(_context=None):
                    pyboy.register_file.F |= 0x10
                    pyboy.register_file.A = 0

                def force_trap(_context=None):
                    pyboy.register_file.A = trap_index

                try:
                    pyboy.load_state(io.BytesIO(self.state_bytes))
                    pyboy.hook_register(0, 0x09AC, at_dispatch, None)
                    pyboy.hook_register(
                        *surfaces.DIRECT_RENDERER, at_direct_draw, None
                    )
                    pyboy.hook_register(17, 0x55B3, force_classifier, None)
                    pyboy.hook_register(17, 0x5607, force_classifier, None)
                    pyboy.hook_register(17, 0x55BD, force_trap, None)
                    for _current in range(20):
                        pyboy.tick()
                    self.assertTrue(redirected[0])
                    self.assertIn(english.encode(expected), draws)
                finally:
                    pyboy.stop(save=False)

    def test_live_mamel_attack_expands_relocated_english_actor_name(self):
        state_path = ROOT / "SaveStates" / "Mamel.state"
        if not state_path.exists():
            raise unittest.SkipTest("Mamel native PyBoy state is not present")
        ram = pyboy_state.cart_ram(state_path)
        pyboy = self.PyBoy(
            str(self.localized_path),
            window="null",
            ram_file=io.BytesIO(ram),
            sound_emulated=False,
        )
        pyboy.set_emulation_speed(0)
        rendered = []

        def at_full_renderer(_context=None):
            if pyboy.frame_count < 900:
                return
            staged = bytes(pyboy.memory[0xC800:0xC900])
            try:
                end = staged.index(0xFF) + 1
            except ValueError:
                return
            rendered.append(staged[:end])

        try:
            pyboy.hook_register(*layout.FULL_RENDERER_ENTRY, at_full_renderer, None)
            for frame in range(1001):
                if frame in (120, 240, 420, 600, 780, 960):
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                if frame in (180, 360):
                    pyboy.button("start", capture_dialogue.PRESS_FRAMES)
                pyboy.tick()
            self.assertTrue(rendered)
            self.assertTrue(
                any(english.encode("Mamel") in event for event in rendered)
            )
            self.assertNotEqual(0, pyboy.register_file.PC)
        finally:
            pyboy.stop(save=False)


if __name__ == "__main__":
    unittest.main()
