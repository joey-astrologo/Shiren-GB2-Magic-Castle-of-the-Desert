from collections import Counter
from hashlib import sha1
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import codec
import english
import english_font
import extract
import layout


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "text_layout.json").read_text(encoding="utf-8")
)


def _location(value):
    bank_text, address_text = value.split(":$")
    return int(bank_text), int(address_text, 16)


def _offset(bank, address):
    return address if bank == 0 else bank * 0x4000 + address - 0x4000


def _direct_calls(rom, bank, target):
    start = bank * 0x4000
    data = rom[start:start + 0x4000]
    needle = bytes((0xCD, target & 0xFF, target >> 8))
    out = []
    at = 0
    while True:
        found = data.find(needle, at)
        if found < 0:
            return out
        address = found if bank == 0 else found + 0x4000
        out.append("%d:$%04X" % (bank, address))
        at = found + 1


class LayoutRuleTests(unittest.TestCase):
    def test_canvas_and_mode_profiles_are_frozen(self):
        canvas = FIXTURE["canvas"]
        self.assertEqual(canvas["tile_columns"], layout.CANVAS_TILE_COLUMNS)
        self.assertEqual(canvas["pixels"], layout.CANVAS_WIDTH_PIXELS)
        self.assertEqual(canvas["composer_wrap_at"], layout.COMPOSER_WRAP_AT)
        self.assertEqual(canvas["renderer_wrap_at"], layout.RENDERER_WRAP_AT)
        self.assertEqual(
            canvas["renderer_auto_line_advance"],
            layout.RENDERER_AUTO_LINE_ADVANCE,
        )

        for name, expected in FIXTURE["profiles"].items():
            profile = layout.SURFACE_PROFILES[name]
            with self.subTest(profile=name):
                self.assertEqual(expected, {
                    "representative_mode": profile.representative_mode,
                    "initial_y": profile.initial_y,
                    "explicit_line_advance": profile.explicit_line_advance,
                    "composer_line_limit": profile.composer_line_limit,
                    "safe_full_lines": profile.safe_full_lines,
                    "renderer": profile.renderer,
                })

        for mode, y, advance, limit in (
            (0x01, 21, 11, 3),
            (0x02, 21, 11, 3),
            (0x04, 21, 11, 3),
            (0x08, 1, 11, 11),
            (0x10, 24, 16, None),
            (0x20, 21, 11, 3),
            (0x60, 21, 11, 3),
        ):
            with self.subTest(mode=mode):
                self.assertEqual(y, layout.initial_y(mode))
                self.assertEqual(advance, layout.explicit_line_advance(mode))
                self.assertEqual(limit, layout.composer_line_limit(mode))


class OriginalRomLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = cls.path.read_bytes()
        if sha1(cls.rom).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")

    def test_opcode_anchors_and_direct_call_sites_are_frozen(self):
        for anchor in FIXTURE["opcode_anchors"]:
            bank, address = _location(anchor["location"])
            expected = bytes.fromhex(anchor["bytes"])
            at = _offset(bank, address)
            with self.subTest(location=anchor["location"]):
                self.assertEqual(expected, self.rom[at:at + len(expected)])

        self.assertEqual(
            FIXTURE["direct_calls"]["composer"],
            _direct_calls(self.rom, 3, 0x312B)
            + _direct_calls(self.rom, 17, 0x312B),
        )
        self.assertEqual(
            FIXTURE["direct_calls"]["full_renderer"],
            _direct_calls(self.rom, 3, 0x35ED)
            + _direct_calls(self.rom, 17, 0x35ED),
        )

    def test_opening_trace_matches_the_renderer_model(self):
        expected = FIXTURE["opening_trace"]
        measured = layout.renderer_layout(
            self.rom, capture_dialogue.DIALOGUE_PREFIX, mode=expected["mode"]
        )
        self.assertEqual(tuple(expected["initial_pen"]),
                         (measured.start_x, measured.start_y))
        self.assertEqual(tuple(expected["line_widths"]), measured.line_widths)
        self.assertEqual(
            tuple(tuple(row) for row in expected["explicit_breaks"]),
            measured.explicit_breaks,
        )
        self.assertEqual(
            tuple(tuple(row) for row in expected["boundaries"]),
            measured.boundaries,
        )
        self.assertEqual(tuple(expected["final_pen"]),
                         (measured.final_x, measured.final_y))
        self.assertEqual(expected["auto_wraps"], len(measured.auto_wraps))

        # The source composer counts the first width byte, while the renderer
        # consumes an eight-pixel slice plus the following continuation width.
        glyph = bytes.fromhex("F03E")
        self.assertEqual(12, layout.composer_advance(self.rom, glyph))
        self.assertEqual((8, 3), layout.renderer_slice_advances(self.rom, glyph))
        self.assertEqual(11, layout.renderer_advance(self.rom, glyph))

    def test_renderer_exact_edge_and_overflow_model(self):
        probe = FIXTURE["renderer_boundary_probe"]
        measured = layout.renderer_layout(
            self.rom,
            bytes.fromhex(probe["payload"]),
            mode=probe["mode"],
            start_x=probe["initial_pen"][0],
            start_y=probe["initial_pen"][1],
        )
        self.assertEqual((144, 136, 9), measured.line_widths)
        self.assertEqual(1, len(measured.auto_wraps))
        wrapped = measured.auto_wraps[0]
        overflow = probe["overflow_glyph"]
        self.assertEqual(overflow["offset"], wrapped.offset)
        self.assertEqual(overflow["code"], wrapped.encoded[0])
        self.assertEqual(overflow["width"], wrapped.advance)
        self.assertEqual(tuple(overflow["after_wrap"]), (wrapped.x, wrapped.y))
        self.assertEqual(tuple(probe["final_pen"]),
                         (measured.final_x, measured.final_y))

    def test_composer_and_renderer_edges_remain_independent(self):
        patched = english_font.install(self.rom)
        just_below = layout.source_layout(
            patched, english.encode_source("W" * 23 + "a<page><box>")
        )
        exact = layout.source_layout(
            patched, english.encode_source("W" * 24 + "<page><box>")
        )
        self.assertEqual((143, 143), (
            just_below.lines[0].composer_pixels,
            just_below.lines[0].renderer_pixels,
        ))
        self.assertTrue(just_below.safe)
        self.assertEqual((144, 144), (
            exact.lines[0].composer_pixels,
            exact.lines[0].renderer_pixels,
        ))
        self.assertEqual(1, len(exact.composer_overflows))
        self.assertEqual(0, len(exact.renderer_overflows))
        self.assertEqual(
            {
                "checked_records": 1,
                "dynamic_records": 0,
                "max_composer_pixels": 143,
                "max_renderer_pixels": 143,
            },
            layout.validate_overrides(
                patched,
                {(195, 0x562F): english.encode_source("W" * 23 + "a<page><box>")},
            ),
        )
        with self.assertRaisesRegex(
            layout.LayoutError,
            r"195:\$562F surface 1 line 1: composer 144px",
        ):
            layout.validate_overrides(
                patched,
                {(195, 0x562F): english.encode_source("W" * 24 + "<page><box>")},
            )
        with self.assertRaisesRegex(layout.LayoutError, "renderer 145px"):
            layout.validate_overrides(
                patched,
                {
                    (195, 0x562F): english.encode_source(
                        "W" * 23 + "<hspace:07><page><box>"
                    )
                },
            )

        smoke = english.encode_source(
            "Hello, Shiren!<br>Native VWF works.<page><box>"
        )
        smoke_layout = layout.source_layout(patched, smoke)
        self.assertEqual([(63, 63), (84, 84)], [
            (line.composer_pixels, line.renderer_pixels)
            for line in smoke_layout.lines
        ])
        self.assertTrue(smoke_layout.safe)

    def test_third_dialogue_line_reserves_room_for_page_marker(self):
        patched = english_font.install(self.rom)
        unsafe = english.encode_source(
            "Good: The Wanderer Rescue<br>"
            "Federation will award you a<br>"
            "Revival Password and an item!<page><box>"
        )
        measured = layout.source_layout(patched, unsafe)
        self.assertEqual(
            [(0, 2, 139, 9, True)],
            [
                (
                    endpoint.surface,
                    endpoint.line,
                    endpoint.renderer_pixels,
                    endpoint.marker_pixels,
                    endpoint.wraps,
                )
                for endpoint in measured.page_endpoints
            ],
        )
        self.assertEqual(measured.page_endpoints, measured.page_marker_overflows)
        with self.assertRaisesRegex(
            layout.LayoutError,
            r"199:\$6F39 surface 1 line 3: page marker .*wrap",
        ):
            layout.validate_overrides(patched, {(199, 0x6F39): unsafe})

        safe = english.encode_source(
            "Good: The Wanderer Rescue<br>"
            "Federation awards you an item<br>"
            "and a Revival Password!<page><box>"
        )
        layout.validate_overrides(patched, {(199, 0x6F39): safe})

        # Native pages can wrap their marker on an earlier line because the
        # automatic ten-pixel descent remains inside the dialogue canvas.
        earlier_line_wrap = english.encode_source(
            "Revival Password and an item!<page><br>Done.<page><box>"
        )
        measured = layout.source_layout(patched, earlier_line_wrap)
        self.assertTrue(measured.page_endpoints[0].wraps)
        self.assertEqual(0, measured.page_endpoints[0].line)
        self.assertEqual((), measured.page_marker_overflows)
        layout.validate_overrides(
            patched, {(199, 0x6F39): earlier_line_wrap}
        )

    def test_f3_soft_wrap_depends_on_the_runtime_value_width(self):
        patched = english_font.install(self.rom)
        record_id = "193:$4192"
        source = english.encode_source(
            "Hit <lookup:19:C5> for <cF3><copy:01:1B:C5> damage."
        )
        lookup = next(
            token
            for token in codec.parse_source(source)
            if token.kind == "source_control" and token.code == 0xF6
        )

        def measured(actor_pixels):
            contract = layout.english_runtime_width_contract(
                {
                    (record_id, lookup.raw): layout.RuntimeF6Bound(
                        "actor", actor_pixels, actor_pixels
                    )
                }
            )
            return layout.source_layout(
                patched,
                source,
                mode=0x10,
                runtime_contract=contract,
                record_id=record_id,
                simulate_soft_wrap=True,
            )

        short = measured(24)
        self.assertEqual((), short.soft_wraps)
        self.assertEqual([(118, 118)], [
            (line.composer_pixels, line.renderer_pixels) for line in short.lines
        ])

        long = measured(95)
        self.assertEqual(((0, 0, 13),), long.soft_wraps)
        self.assertEqual([(137, 137), (52, 52)], [
            (line.composer_pixels, line.renderer_pixels) for line in long.lines
        ])
        self.assertTrue(long.safe)

        contract = layout.english_runtime_width_contract(
            {
                (record_id, lookup.raw): layout.RuntimeF6Bound(
                    "actor", 95, 95
                )
            }
        )
        layout.validate_overrides(
            patched,
            {(193, 0x4192): source},
            runtime_contract=contract,
        )

    def test_page_wait_preserves_pen_until_an_explicit_break(self):
        patched = english_font.install(self.rom)
        joined = layout.source_layout(
            patched,
            english.encode_source("Got Herb.<page>Drink it.<page><box>"),
        )
        literal = layout.source_layout(
            patched,
            english.encode_source("Got Herb.Drink it.<page><box>"),
        )
        separated = layout.source_layout(
            patched,
            english.encode_source("Got Herb.<page><br>Drink it.<page><box>"),
        )

        # FB is a wait, not horizontal movement. Only FD resets x, exactly as
        # the first-discovery screenshots demonstrate.
        self.assertEqual(1, len(joined.lines))
        self.assertEqual(
            literal.lines[0].composer_pixels,
            joined.lines[0].composer_pixels,
        )
        self.assertEqual(2, len(separated.lines))
        self.assertEqual(
            [
                layout.source_layout(
                    patched, english.encode_source(text)
                ).lines[0].composer_pixels
                for text in ("Got Herb.", "Drink it.")
            ],
            [line.composer_pixels for line in separated.lines],
        )

    def test_runtime_substitution_opcodes_and_corpus_semantics_are_frozen(self):
        runtime = FIXTURE["runtime_substitutions"]
        for anchor in runtime["opcode_anchors"]:
            bank, address = _location(anchor["location"])
            expected = bytes.fromhex(anchor["bytes"])
            at = _offset(bank, address)
            with self.subTest(location=anchor["location"]):
                self.assertEqual(expected, self.rom[at:at + len(expected)])

        counts = Counter()
        for record in extract.extract(self.rom)["records"]:
            for token in codec.parse_source(record.raw):
                if token.kind != "source_control":
                    continue
                if token.code == 0xF4:
                    counts["unsigned_integer_%d_byte" % token.args[0]] += 1
                elif token.code == 0xF5:
                    key = "player_name" if token.args == b"\xFF" else "player_name_byte"
                    counts[key] += 1
                elif token.code == 0xF6 and token.args[0] == 0x01:
                    counts["record_lookup"] += 1
                elif token.code == 0xF6 and token.args[0] == 0x03:
                    counts["cached_string_legacy_number_token"] += 1
        self.assertEqual(runtime["corpus_controls"], dict(counts))

    def test_numeric_and_player_name_maximum_width_contracts(self):
        patched = english_font.install(self.rom)
        contract = layout.english_runtime_width_contract()
        cases = (
            ("<copy:01:19:C5>", "unsigned_integer_1_byte"),
            ("<copy:02:19:C5>", "unsigned_integer_2_byte"),
            ("<copy:03:19:C5>", "unsigned_integer_3_byte"),
            ("<copy:04:19:C5>", "unsigned_integer_4_byte"),
            ("<name>", "player_name"),
            ("<name:00>", "player_name_byte"),
        )
        maximums = FIXTURE["runtime_substitutions"]["english_maximum_pixels"]
        for source, kind in cases:
            measured = layout.source_layout(
                patched,
                english.encode_source(source),
                runtime_contract=contract,
            )
            with self.subTest(source=source):
                self.assertTrue(measured.safe)
                self.assertEqual((0,), measured.bounded_dynamic_offsets)
                self.assertEqual((), measured.unresolved_dynamic_offsets)
                self.assertEqual(kind, measured.dynamic_expansions[0].kind)
                self.assertEqual(maximums[kind], measured.lines[0].composer_pixels)
                self.assertEqual(maximums[kind], measured.lines[0].renderer_pixels)

        safe_name = english.encode_source("W" * 15 + "<name>")
        self.assertEqual(
            139,
            layout.source_layout(
                patched, safe_name, runtime_contract=contract
            ).lines[0].composer_pixels,
        )
        layout.validate_overrides(patched, {(195, 0x562F): safe_name})
        with self.assertRaisesRegex(layout.LayoutError, "composer 145px"):
            layout.validate_overrides(
                patched,
                {(195, 0x562F): english.encode_source("W" * 16 + "<name>")},
            )

    def test_lookup_and_legacy_number_token_remain_fail_closed(self):
        patched = english_font.install(self.rom)
        contract = layout.english_runtime_width_contract()
        cases = (
            ("<lookup:19:C5>", "record_lookup"),
            ("<number:19:C5>", "cached_string"),
        )
        for source, kind in cases:
            measured = layout.source_layout(
                patched,
                english.encode_source(source),
                runtime_contract=contract,
            )
            with self.subTest(source=source):
                self.assertFalse(measured.safe)
                self.assertEqual((), measured.bounded_dynamic_offsets)
                self.assertEqual((0,), measured.unresolved_dynamic_offsets)
                self.assertEqual(kind, measured.dynamic_expansions[0].kind)
                self.assertIsNone(measured.dynamic_expansions[0].composer_pixels)

    def test_referenced_corpus_geometry_is_frozen(self):
        self.assertEqual(FIXTURE["corpus"], layout.corpus_summary(self.rom))

    def test_representative_stable_records_cover_the_known_surfaces(self):
        records = {
            record.id: record for record in extract.extract(self.rom)["records"]
        }
        representatives = FIXTURE["representative_records"]

        dialogue = representatives["dialogue"]
        record = records[dialogue["id"]]
        self.assertIn(tuple(dialogue["reference"]), {
            (reference.group, reference.index) for reference in record.references
        })
        measured = layout.source_layout(
            self.rom, record.raw, mode=dialogue["observed_mode"]
        )
        first_page = [line for line in measured.lines if line.surface == 0]
        self.assertEqual(dialogue["first_page_composer_widths"],
                         [line.composer_pixels for line in first_page])
        self.assertEqual(dialogue["first_page_renderer_widths"],
                         [line.renderer_pixels for line in first_page])

        full_screen = representatives["full_screen"]
        record = records[full_screen["id"]]
        self.assertIn(tuple(full_screen["reference"]), {
            (reference.group, reference.index) for reference in record.references
        })
        measured = layout.source_layout(self.rom, record.raw, mode=0x08)
        self.assertEqual(full_screen["observed_lines"], len(measured.lines))
        self.assertEqual(full_screen["max_composer_width"],
                         max(line.composer_pixels for line in measured.lines))
        self.assertEqual(full_screen["max_renderer_width"],
                         max(line.renderer_pixels for line in measured.lines))
        self.assertFalse(measured.line_limit_overflows)

        for positioned in representatives["positioned"]:
            record = records[positioned["id"]]
            self.assertEqual(positioned["text"], record.source)
            self.assertIn(tuple(positioned["reference"]), {
                (reference.group, reference.index) for reference in record.references
            })
            measured = layout.source_layout(self.rom, record.raw, mode=0x04)
            self.assertEqual(1, len(measured.lines))
            self.assertEqual(positioned["composer_width"],
                             measured.lines[0].composer_pixels)
            self.assertEqual(positioned["renderer_width"],
                             measured.lines[0].renderer_pixels)


class NativeRendererBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        if sha1(cls.path.read_bytes()).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))

    def test_unmodified_renderer_accepts_144_then_wraps_at_145(self):
        probe = FIXTURE["renderer_boundary_probe"]
        payload = bytes.fromhex(probe["payload"])
        pyboy = self.PyBoy(str(self.path), window="null")
        pyboy.set_emulation_speed(0)
        armed = {"value": True}
        active = {"value": False, "token": None}
        dispatches = []
        overflow = {}

        def pointer():
            return pyboy.memory[0xC4E0] | (pyboy.memory[0xC4E1] << 8)

        def at_dispatch(_context=None):
            if armed["value"]:
                armed["value"] = False
                active["value"] = True
                for index, value in enumerate(payload):
                    pyboy.memory[0xC800 + index] = value
                pyboy.memory[0xC4E0] = 0x00
                pyboy.memory[0xC4E1] = 0xC8
                pyboy.memory[0xC4DA] = probe["mode"]
                pyboy.memory[0xC4D6] = probe["initial_pen"][0]
                pyboy.memory[0xC4D7] = probe["initial_pen"][1]
            if not active["value"]:
                return
            at = pointer()
            code = pyboy.memory[at]
            token = (at - 0xC800, code)
            active["token"] = token
            dispatches.append((token[0], code, pyboy.memory[0xC4D6],
                               pyboy.memory[0xC4D7]))
            if code == 0xFC:
                active["value"] = False

        def at_pre_wrap(_context=None):
            if active["value"] and active["token"][0] == 36:
                overflow["width"] = pyboy.memory[0xC4D5]
                overflow["before"] = (
                    pyboy.memory[0xC4D6], pyboy.memory[0xC4D7]
                )

        def at_post_wrap(_context=None):
            if active["value"] and active["token"][0] == 36:
                overflow["after"] = (
                    pyboy.memory[0xC4D6], pyboy.memory[0xC4D7]
                )

        try:
            capture_dialogue.run_to_dialogue(pyboy)
            capture_dialogue.validate_dialogue(pyboy)
            pyboy.hook_register(0, 0x3657, at_dispatch, None)
            pyboy.hook_register(3, 0x6F1F, at_pre_wrap, None)
            pyboy.hook_register(3, 0x6F37, at_post_wrap, None)
            pyboy.button("a", capture_dialogue.PRESS_FRAMES)
            for _ in range(180):
                pyboy.tick()

            expected_edge = tuple(probe["exact_edge_dispatch"])
            self.assertIn(expected_edge, dispatches)
            self.assertEqual(probe["overflow_glyph"]["width"], overflow["width"])
            self.assertEqual(tuple(probe["overflow_glyph"]["before"]),
                             overflow["before"])
            self.assertEqual(tuple(probe["overflow_glyph"]["after_wrap"]),
                             overflow["after"])
            self.assertIn(
                (37, 0xFC, probe["final_pen"][0], probe["final_pen"][1]),
                dispatches,
            )
        finally:
            pyboy.stop(save=False)


if __name__ == "__main__":
    unittest.main()
