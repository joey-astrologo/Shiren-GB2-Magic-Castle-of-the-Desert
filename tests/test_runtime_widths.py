import contextlib
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
import english
import english_font
import extract
import layout
import runtime_widths
import translations
import wrap_en


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "runtime_widths.json").read_text(
        encoding="utf-8"
    )
)


class OriginalRomRuntimeWidthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = cls.path.read_bytes()
        if sha1(cls.rom).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.result = extract.extract(cls.rom)
        cls.by_id = {record.id: record for record in cls.result["records"]}
        cls.font_rom = english_font.install(cls.rom)
        cls.blank = runtime_widths.analyze(cls.font_rom, cls.result, {})

    def _complete_item_mapping(self, replacement=None):
        replacement = replacement or {}
        record_ids = {
            record_id
            for family in (
                "identified_item_names",
                "unidentified_item_appearances",
                "item_name_format_fragments",
            )
            for record_id in self.blank.families[family].record_ids
        }
        english_by_id = {}
        for record_id in record_ids:
            record = self.by_id[record_id]
            english_by_id[record_id] = (
                translations.EMPTY_SENTINEL if not record.raw else "I"
            )
        english_by_id.update(replacement)
        return translations.load_mapping(english_by_id, self.result["records"])

    def test_production_translation_readiness_and_formatter_evidence_are_frozen(self):
        translated = translations.load_path(
            ROOT / "script" / "en", self.result["records"]
        )
        analysis = runtime_widths.analyze(
            self.font_rom, self.result, translated
        )
        self.assertEqual(
            FIXTURE,
            runtime_widths.summary(
                self.font_rom, self.result, translated, analysis=analysis
            ),
        )
        self.assertTrue(analysis.domains["actor_name"].ready)
        self.assertEqual(
            (95, 95, "192:$4F42"),
            (
                analysis.domains["actor_name"].maximum.composer_pixels,
                analysis.domains["actor_name"].maximum.renderer_pixels,
                analysis.domains["actor_name"].maximum.composer_record_id,
            ),
        )
        self.assertTrue(analysis.domains["item_name"].ready)
        self.assertTrue(analysis.domains["trap_name"].ready)
        self.assertEqual(
            (87, 87, "193:$549F"),
            (
                analysis.domains["trap_name"].maximum.composer_pixels,
                analysis.domains["trap_name"].maximum.renderer_pixels,
                analysis.domains["trap_name"].maximum.composer_record_id,
            ),
        )
        self.assertTrue(analysis.domains["sender_string"].ready)
        self.assertTrue(
            analysis.domains["debug_polymorphic"].permanently_unresolved
        )

    def test_production_actor_tiers_preserve_family_alignment(self):
        translated = translations.load_path(
            ROOT / "script" / "en", self.result["records"]
        )
        by_id = {entry.record_id: entry.text for entry in translated.values()}
        expected = {
            "192:$4BD7": "Mamel",
            "192:$50BB": "Pit Mamel",
            "192:$5629": "Cave Mamel",
            "192:$4DF0": "Zenmaiger",
            "192:$531A": "Royal Wind",
            "192:$5889": "Hydro Rover",
            "192:$4DFB": "Nfuu",
            "192:$5329": "Nfuu",
            "192:$5898": "Nfuu",
            "192:$4E64": "Rookie Guard",
            "192:$538C": "Strong Guard",
            "192:$58FC": "Dragon Guard",
        }
        self.assertEqual(expected, {key: by_id[key] for key in expected})

    def test_complete_item_families_unlock_all_item_consumers(self):
        translated = self._complete_item_mapping()
        analysis = runtime_widths.analyze(
            self.font_rom, self.result, translated
        )
        item = analysis.domains["item_name"]
        self.assertTrue(item.ready)
        self.assertEqual(55, item.maximum.composer_pixels)
        self.assertEqual(55, item.maximum.renderer_pixels)

        record = self.by_id["205:$6905"]
        measured = layout.source_layout(
            self.font_rom,
            english.encode_source("<number:19:C5>"),
            runtime_contract=analysis.contract,
            record_id=record.id,
        )
        self.assertTrue(measured.safe)
        self.assertEqual("f6_item_name", measured.dynamic_expansions[0].kind)
        self.assertEqual(55, measured.lines[0].composer_pixels)
        self.assertEqual(55, measured.lines[0].renderer_pixels)

        draft = (
            "<number:19:C5> was found.<page><br>It is a sturdy wooden<br>weapon."
            "<page><box>Open the menu."
        )
        wrapped = wrap_en.wrap_record(
            self.font_rom, record, draft, runtime_contract=analysis.contract
        )
        self.assertIn("<number:19:C5>", wrapped)

    def test_one_missing_term_keeps_the_whole_item_domain_unresolved(self):
        translated = self._complete_item_mapping()
        missing_key = next(
            key
            for key, entry in translated.items()
            if entry.record_id
            == self.blank.families["identified_item_names"].record_ids[0]
        )
        del translated[missing_key]
        analysis = runtime_widths.analyze(
            self.font_rom, self.result, translated
        )
        self.assertFalse(analysis.domains["item_name"].ready)
        record = self.by_id["205:$6905"]
        with self.assertRaisesRegex(layout.LayoutError, "without translated width bounds"):
            layout.validate_overrides(
                self.font_rom,
                {
                    (record.bank, record.address): english.encode_source(
                        "<number:19:C5> found.<page><box>"
                    )
                },
                runtime_contract=analysis.contract,
            )

    def test_runtime_terms_reject_controls_before_producing_a_bound(self):
        bad_id = self.blank.families["identified_item_names"].record_ids[0]
        translated = self._complete_item_mapping({bad_id: "Bad<br>term"})
        with self.assertRaisesRegex(
            runtime_widths.RuntimeWidthError, "control or substitution"
        ):
            runtime_widths.analyze(self.font_rom, self.result, translated)

    def test_production_build_rejects_unbounded_f6_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tsv = root / "translation.tsv"
            tsv.write_text(
                "id\tenglish\n"
                "205:$6905\t<number:19:C5> found.<page><page><box>Open menu.\n",
                encoding="utf-8",
            )
            output = root / "should-not-exist.gbc"
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                with self.assertRaises(SystemExit) as raised:
                    translation_build.main(
                        (str(self.path), str(tsv), str(output))
                    )
            self.assertEqual(1, raised.exception.code)
            self.assertIn("without translated width bounds", errors.getvalue())
            self.assertFalse(output.exists())

    def test_composition_uses_maximum_of_three_shapes_not_family_sum(self):
        identified = self.blank.families["identified_item_names"].record_ids[0]
        appearance = self.blank.families[
            "unidentified_item_appearances"
        ].record_ids[0]
        fragment = next(
            record_id
            for record_id in self.blank.families[
                "item_name_format_fragments"
            ].record_ids
            if self.by_id[record_id].raw
        )
        translated = self._complete_item_mapping(
            {
                identified: "WWWWWWWW",
                appearance: "WWWWWW",
                fragment: "WWW",
            }
        )
        analysis = runtime_widths.analyze(
            self.font_rom, self.result, translated
        )
        item = analysis.domains["item_name"].maximum
        # Identified=48px; appearance=36px; fragment+custom=18+49=67px.
        self.assertEqual((67, 67), (item.composer_pixels, item.renderer_pixels))
        self.assertNotEqual(48 + 36 + 18 + 49, item.composer_pixels)


if __name__ == "__main__":
    unittest.main()
