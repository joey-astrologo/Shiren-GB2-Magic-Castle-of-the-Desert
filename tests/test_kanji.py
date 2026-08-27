from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import codec
import extract as script_extract
import font
import textdump


FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "kanji_map.json").read_text())
TABLE_PATH = ROOT / "data" / "kanji.tsv"
ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"


class KanjiTableTests(unittest.TestCase):
    def test_table_hash_counts_and_unique_reverse_mapping(self):
        self.assertEqual(
            FIXTURE["table_sha1"], hashlib.sha1(TABLE_PATH.read_bytes()).hexdigest()
        )
        kinds = Counter(codec.KANJI_KIND.values())
        self.assertEqual(FIXTURE["mapped_prefixed_codes"], len(codec.KANJI))
        self.assertEqual(FIXTURE["kanji_codes"], kinds["kanji"])
        self.assertEqual(FIXTURE["symbol_codes"], kinds["symbol"])
        self.assertEqual(FIXTURE["token_codes"], kinds["token"])
        self.assertEqual(len(codec.KANJI), len(set(codec.KANJI.values())))

    def test_every_mapping_decodes_and_encodes_exactly(self):
        for encoded, text in codec.KANJI.items():
            with self.subTest(code=encoded.hex().upper(), text=text):
                self.assertEqual(text, codec.decode(encoded))
                self.assertEqual(encoded, codec.encode(text))

    def test_named_token_encodings_remain_lossless(self):
        for code, text in FIXTURE["tokens"].items():
            with self.subTest(code=code):
                raw = bytes.fromhex(code)
                self.assertEqual(text, codec.decode(raw))
                self.assertEqual(raw, codec.encode(text))

    def test_duplicate_kanji_encodings_use_readable_lossless_aliases(self):
        for anchor in FIXTURE["lossless_aliases"]:
            canonical = bytes.fromhex(anchor["canonical"])
            alias = bytes.fromhex(anchor["alias"])
            text = anchor["text"]
            alias_text = "{%s=%s}" % (anchor["alias"], text)
            with self.subTest(code=anchor["alias"], text=text):
                self.assertEqual(text, codec.decode(canonical))
                self.assertEqual(alias_text, codec.decode(alias))
                self.assertEqual(canonical, codec.encode(text))
                self.assertEqual(alias, codec.encode(alias_text))

    def test_unmapped_continuation_stays_a_raw_escape(self):
        raw = bytes.fromhex("F043")
        self.assertNotIn(raw, codec.KANJI)
        self.assertEqual("{F043}", codec.decode(raw))
        self.assertEqual(raw, codec.encode("{F043}"))


class OriginalRomKanjiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = cls.path.read_bytes()
        if hashlib.sha1(cls.rom).hexdigest() != FIXTURE["rom_sha1"]:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.rows = dict(textdump._dialogue(cls.rom))
        result = script_extract.extract(cls.rom)
        cls.source_records = {record.id: record for record in result["records"]}

    def test_font_width_invariant_separates_glyphs_from_continuations(self):
        observed = {
            token.raw
            for record in self.rows.values()
            for token in codec.parse(record)
            if token.kind == "kanji"
        }
        valid = {
            encoded for encoded in observed
            if font.read_glyph(self.rom, encoded).width >= 4
        }
        continuations = observed - valid
        self.assertTrue(valid.issubset(codec.KANJI))
        self.assertEqual(
            set(FIXTURE["unmapped_continuation_codes"]),
            {encoded.hex().upper() for encoded in continuations},
        )
        for encoded in continuations:
            with self.subTest(code=encoded.hex().upper()):
                self.assertLess(font.read_glyph(self.rom, encoded).width, 4)

    def test_contextual_decode_anchors(self):
        for anchor in FIXTURE["candidate_anchors"]:
            offset = int(anchor["offset"], 16)
            with self.subTest(offset=anchor["offset"]):
                self.assertIn(anchor["contains"], codec.decode(self.rows[offset]))

    def test_authoritative_source_glyph_map_is_complete(self):
        observed = {
            token.raw
            for record in self.source_records.values()
            for token in codec.parse_source(record.raw)
            if token.kind == "kanji"
        }
        self.assertEqual(set(codec.KANJI), observed)
        for encoded in observed:
            with self.subTest(code=encoded.hex().upper()):
                self.assertGreaterEqual(font.read_glyph(self.rom, encoded).width, 4)

    def test_source_contextual_decode_anchors(self):
        for anchor in FIXTURE["source_anchors"]:
            record = self.source_records[anchor["record"]]
            with self.subTest(record=anchor["record"], text=anchor["contains"]):
                self.assertIn(anchor["contains"], record.source)

    def test_every_candidate_still_round_trips_with_unicode_kanji(self):
        for offset, record in self.rows.items():
            with self.subTest(offset="%06X" % offset):
                self.assertEqual(record, codec.encode(codec.decode(record)))


if __name__ == "__main__":
    unittest.main()
