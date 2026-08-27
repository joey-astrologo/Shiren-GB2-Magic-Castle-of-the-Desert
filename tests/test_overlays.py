import csv
from hashlib import sha1
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build as translation_build
import capture_dialogue
import extract
import organize
import overlays
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "english_overlays.json").read_text(
        encoding="utf-8"
    )
)
SMOKE_ID = "195:$562F"
SMOKE_TEXT = "Hello, Shiren!<br>Native VWF works.<page><box>"


def _set_english(path, record_id, text):
    path = Path(path)
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames
        rows = list(reader)
    found = 0
    for row in rows:
        if row["id"] == record_id:
            row["english"] = text
            found += 1
    if found != 1:
        raise AssertionError("expected one row for %s; found %d" % (record_id, found))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


class OriginalRomEnglishOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = cls.path.read_bytes()
        if sha1(cls.rom).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.result = extract.extract(cls.rom)

    def _workspace(self, temporary):
        root = Path(temporary)
        catalog = root / "organized"
        english = root / "en"
        paths, measured = overlays.synchronize(self.result, catalog, english)
        return catalog, english, paths, measured

    def test_blank_source_free_workspace_and_manifest_are_frozen(self):
        with tempfile.TemporaryDirectory() as temporary:
            _catalog, english, paths, measured = self._workspace(temporary)
            self.assertEqual(FIXTURE["manifest"], measured)
            self.assertTrue(measured["source_free"])
            self.assertEqual(6695, measured["records"])
            self.assertEqual(0, measured["translated_records"])
            actual = {
                path.name: sha1(path.read_bytes()).hexdigest() for path in paths
            }
            self.assertEqual(FIXTURE["output_sha1"], actual)
            for category in organize.CATEGORIES:
                data = (english / category.filename).read_bytes()
                data.decode("ascii")
                header = data.splitlines()[0].decode("ascii")
                self.assertEqual("id\tsections\tenglish", header)

    def test_translation_synchronizes_in_both_directions(self):
        with tempfile.TemporaryDirectory() as temporary:
            catalog, english, _paths, _measured = self._workspace(temporary)
            _set_english(english / "prose.tsv", SMOKE_ID, SMOKE_TEXT)
            overlays.synchronize(self.result, catalog, english)
            rich = translations.load_path(catalog, self.result["records"])
            compact = translations.load_path(english, self.result["records"])
            key = (195, 0x562F)
            self.assertEqual(SMOKE_TEXT, rich[key].text)
            self.assertEqual(SMOKE_TEXT, compact[key].text)

            second = next(
                row for row in organize.classify(self.result)
                if row.category == "glossary"
            )
            _set_english(catalog / "glossary.tsv", second.record.id, "One")
            overlays.synchronize(self.result, catalog, english)
            compact = translations.load_path(english, self.result["records"])
            self.assertEqual(
                "One", compact[(second.record.bank, second.record.address)].text
            )

    def test_conflicting_nonblank_cells_fail_before_either_side_is_written(self):
        with tempfile.TemporaryDirectory() as temporary:
            catalog, english, _paths, _measured = self._workspace(temporary)
            _set_english(catalog / "prose.tsv", SMOKE_ID, "One")
            _set_english(english / "prose.tsv", SMOKE_ID, "Two")
            before = {
                path: sha1(path.read_bytes()).hexdigest()
                for path in (catalog / "prose.tsv", english / "prose.tsv")
            }
            with self.assertRaisesRegex(overlays.OverlayError, "conflicts"):
                overlays.synchronize(self.result, catalog, english)
            self.assertEqual(
                before,
                {path: sha1(path.read_bytes()).hexdigest() for path in before},
            )

    def test_compact_overlay_directory_drives_a_real_relocated_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            catalog, english, _paths, _measured = self._workspace(temporary)
            _set_english(english / "prose.tsv", SMOKE_ID, SMOKE_TEXT)
            overlays.synchronize(self.result, catalog, english)
            loaded = translations.load_path(english, self.result["records"])
            output, _allocation, validation = translation_build.build_rom(
                self.rom, translations.encoded_overrides(loaded)
            )
            self.assertEqual(len(self.rom), len(output))
            self.assertEqual(1, len(loaded))
            self.assertGreater(validation["overridden_references"], 0)
            self.assertEqual(7163, validation["exact_references"])


if __name__ == "__main__":
    unittest.main()
