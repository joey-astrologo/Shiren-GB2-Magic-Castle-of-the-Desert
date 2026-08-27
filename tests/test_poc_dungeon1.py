from hashlib import sha1
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import codec
import english_font
import extract
import layout
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "poc_dungeon1.json").read_text(
        encoding="utf-8"
    )
)


def _control_signature(raw):
    return tuple(
        (token.code, token.args)
        for token in codec.parse_source(raw)
        if token.kind not in ("glyph", "kanji")
        and token.code in (0xF4, 0xF5, 0xF6, 0xFA, 0xFB, 0xFC)
    )


class DungeonOnePocTranslationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / ROM_NAME
        if not path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = path.read_bytes()
        if sha1(cls.rom).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.result = extract.extract(cls.rom)
        cls.by_id = {record.id: record for record in cls.result["records"]}
        cls.by_reference = {
            (reference.group, reference.index): record
            for record in cls.result["records"]
            for reference in record.references
        }
        cls.translated = translations.load_path(
            ROOT / "script" / "en", cls.result["records"]
        )
        cls.font_rom = english_font.install(cls.rom)

    def entry(self, record):
        return self.translated[(record.bank, record.address)]

    def test_fixed_save_summary_and_quit_text_are_frozen(self):
        for record_id, expected in FIXTURE["fixed_text"].items():
            with self.subTest(record=record_id):
                self.assertEqual(expected, self.entry(self.by_id[record_id]).text)
        run = self.entry(self.by_id["192:$6C22"])
        measured = layout.validate_direct_surface(
            self.font_rom, run.encoded, start_x=119, start_y=62, right_edge=144
        )
        self.assertLessEqual(measured.rightmost_pen, 144)

    def test_history_is_complete_and_every_bounded_row_fits(self):
        fixture = FIXTURE["history"]
        actor_width = max(
            layout.direct_layout(
                self.font_rom,
                self.entry(self.by_reference[(group, index)]).encoded,
                start_x=0,
                start_y=0,
            ).rightmost_pen
            for group in (1, 2, 3)
            for index in range(150)
        )
        translated = 0
        for index in range(fixture["index_range"][0], fixture["index_range"][1] + 1):
            record = self.by_reference[(fixture["group"], index)]
            entry = self.entry(record)
            bounds = {}
            for token in codec.parse_source(entry.encoded):
                if token.kind == "source_control" and token.code == 0xF6:
                    bounds[(record.id, token.raw)] = layout.RuntimeF6Bound(
                        "actor_name", actor_width, actor_width
                    )
            measured = layout.source_layout(
                self.font_rom,
                entry.encoded,
                mode=8,
                runtime_contract=layout.english_runtime_width_contract(bounds),
                record_id=record.id,
            )
            self.assertEqual((), measured.unresolved_dynamic_offsets)
            self.assertEqual(1, len(measured.lines))
            line = measured.lines[0]
            self.assertLess(line.composer_pixels, 144)
            self.assertLessEqual(
                line.renderer_pixels,
                fixture["right_edge"] - fixture["start_x"],
            )
            translated += 1
        self.assertEqual(fixture["records"], translated)

    def test_wanderer_rating_is_complete_and_uses_its_real_field_budgets(self):
        fixture = FIXTURE["wanderer_rating"]
        group = fixture["group"]
        expected_indices = set()
        for first, last in (
            fixture["achievement_ranges"]
            + [fixture["category_range"]]
            + fixture["title_ranges"]
            + [fixture["rescue_range"]]
        ):
            expected_indices.update(range(first, last + 1))
        self.assertEqual(fixture["translated_records"], len(expected_indices))

        for index in fixture["empty_indices"]:
            record = self.by_reference[(group, index)]
            self.assertEqual(b"", record.raw)
            entry = self.translated[(record.bank, record.address)]
            self.assertTrue(entry.explicit_empty)
            self.assertEqual(b"", entry.encoded)

        for first, last in fixture["achievement_ranges"]:
            for index in range(first, last + 1):
                record = self.by_reference[(group, index)]
                measured = layout.validate_direct_surface(
                    self.font_rom,
                    self.entry(record).encoded,
                    start_x=fixture["achievement_start_x"],
                    start_y=1,
                    right_edge=fixture["achievement_right_edge"],
                )
                self.assertLessEqual(measured.rightmost_pen, 144)

        for first, last in fixture["title_ranges"]:
            for index in range(first, last + 1):
                record = self.by_reference[(group, index)]
                measured = layout.validate_direct_surface(
                    self.font_rom,
                    self.entry(record).encoded,
                    start_x=fixture["title_start_x"],
                    start_y=4,
                    right_edge=fixture["title_right_edge"],
                )
                self.assertLessEqual(measured.rightmost_pen, 144)

    def test_opening_chase_batch_is_complete_and_preserves_pacing_controls(self):
        record_ids = FIXTURE["opening_chase_records"]
        self.assertEqual(34, len(record_ids))
        self.assertEqual(34, len(set(record_ids)))
        for record_id in record_ids:
            with self.subTest(record=record_id):
                record = self.by_id[record_id]
                entry = self.entry(record)
                self.assertTrue(entry.text)
                source_controls = _control_signature(record.raw)
                english_controls = _control_signature(entry.encoded)
                self.assertEqual(source_controls, english_controls)
                measured = layout.source_layout(
                    self.font_rom,
                    entry.encoded,
                    runtime_contract=layout.english_runtime_width_contract(),
                    record_id=record.id,
                )
                self.assertTrue(measured.safe)


if __name__ == "__main__":
    unittest.main()
