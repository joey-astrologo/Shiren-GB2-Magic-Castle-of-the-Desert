import csv
import io
from hashlib import sha1
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import english
import extract
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
SMOKE_ID = "195:$562F"
SMOKE_TEXT = "Hello, Shiren!<br>Native VWF works.<page><box>"


class OriginalRomTranslationFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = cls.path.read_bytes()
        if sha1(cls.rom).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.extracted = extract.extract(cls.rom)
        cls.records = cls.extracted["records"]
        cls.by_id = {record.id: record for record in cls.records}

    def _load(self, contents):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "translations.tsv"
            path.write_text(contents, encoding="utf-8")
            return translations.load_tsv(path, self.records)

    def _tsv(self, header, rows):
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
        return stream.getvalue()

    def test_compact_fixture_loads_one_stable_id_override(self):
        loaded = translations.load_tsv(
            ROOT / "tests" / "fixtures" / "translation_smoke.tsv", self.records
        )
        self.assertEqual({(195, 0x562F)}, set(loaded))
        translation = loaded[(195, 0x562F)]
        self.assertEqual(SMOKE_ID, translation.record_id)
        self.assertEqual(SMOKE_TEXT, translation.text)
        self.assertEqual(english.encode_source(SMOKE_TEXT), translation.encoded)
        self.assertFalse(translation.explicit_empty)
        self.assertEqual(
            {(195, 0x562F): translation.encoded},
            translations.encoded_overrides(loaded),
        )

    def test_full_extractor_tsv_columns_guard_against_stale_source(self):
        record = self.by_id[SMOKE_ID]
        contents = self._tsv(
            (
                "id",
                "length",
                "original_hex",
                "references",
                "interior_of",
                "japanese",
                "english",
            ),
            (
                (
                    record.id,
                    len(record.raw),
                    record.raw.hex().upper(),
                    "ignored-by-loader",
                    record.interior_of,
                    record.source,
                    SMOKE_TEXT,
                ),
            ),
        )
        loaded = self._load(contents)
        self.assertEqual(
            english.encode_source(SMOKE_TEXT),
            loaded[(record.bank, record.address)].encoded,
        )

    def test_blank_means_untranslated_and_empty_requires_explicit_sentinel(self):
        first, second = self.records[:2]
        contents = self._tsv(
            ("id", "english"),
            ((first.id, ""), (second.id, translations.EMPTY_SENTINEL)),
        )
        loaded = self._load(contents)
        self.assertNotIn((first.bank, first.address), loaded)
        empty = loaded[(second.bank, second.address)]
        self.assertEqual(b"", empty.encoded)
        self.assertEqual("", empty.text)
        self.assertTrue(empty.explicit_empty)

    def test_rejects_unknown_duplicate_and_unencodable_rows(self):
        cases = (
            (
                "unknown record ID",
                self._tsv(("id", "english"), (("999:$4000", "No"),)),
            ),
            (
                "duplicates record ID",
                self._tsv(
                    ("id", "english"),
                    ((SMOKE_ID, "One"), (SMOKE_ID, "Two")),
                ),
            ),
            (
                "cannot encode",
                self._tsv(("id", "english"), ((SMOKE_ID, "日本語"),)),
            ),
        )
        for message, contents in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(translations.TranslationError, message):
                    self._load(contents)

    def test_rejects_missing_malformed_and_stale_source_columns(self):
        record = self.by_id[SMOKE_ID]
        cases = (
            (
                "missing required column",
                self._tsv(("id", "translation"), ((record.id, SMOKE_TEXT),)),
            ),
            (
                "wrong number of TSV columns",
                "id\tenglish\n%s\n" % record.id,
            ),
            (
                "source length changed",
                self._tsv(
                    ("id", "length", "english"),
                    ((record.id, len(record.raw) + 1, SMOKE_TEXT),),
                ),
            ),
            (
                "original bytes changed",
                self._tsv(
                    ("id", "original_hex", "english"),
                    ((record.id, "00", SMOKE_TEXT),),
                ),
            ),
            (
                "Japanese source changed",
                self._tsv(
                    ("id", "japanese", "english"),
                    ((record.id, "stale", SMOKE_TEXT),),
                ),
            ),
        )
        for message, contents in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(translations.TranslationError, message):
                    self._load(contents)

    def test_organized_directory_merges_files_and_rejects_duplicate_overrides(self):
        first, second = self.records[:2]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "a.tsv").write_text(
                self._tsv(("id", "english"), ((first.id, "One"),)),
                encoding="utf-8",
            )
            (directory / "b.tsv").write_text(
                self._tsv(("id", "english"), ((second.id, "Two"),)),
                encoding="utf-8",
            )
            loaded = translations.load_path(directory, self.records)
            self.assertEqual(
                {(first.bank, first.address), (second.bank, second.address)},
                set(loaded),
            )

            (directory / "c.tsv").write_text(
                self._tsv(("id", "english"), ((first.id, "Again"),)),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                translations.TranslationError, "duplicates translated record ID"
            ):
                translations.load_path(directory, self.records)


if __name__ == "__main__":
    unittest.main()
