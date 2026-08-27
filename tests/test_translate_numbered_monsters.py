from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import translate_numbered_monsters as numbered


class NumberedMonsterTranslationTests(unittest.TestCase):
    def test_native_numbering_omits_synthetic_number_one(self):
        self.assertEqual("Zenmaiger", numbered.variant_name(116, 0))
        self.assertEqual("Zenmaiger No. 2", numbered.variant_name(116, 1))
        self.assertEqual("Zenmaiger No. 99", numbered.variant_name(116, 98))

    def test_all_nine_tables_have_complete_unique_coverage(self):
        variants = numbered.catalog_variants()
        self.assertEqual(891, len(variants))
        for group in numbered.BASE_NAMES:
            self.assertEqual(
                set(range(99)),
                {index for candidate, index in variants.values() if candidate == group},
            )

    def test_fill_rows_does_not_overwrite_existing_translation(self):
        variants = {"a": (116, 0), "b": (116, 1)}
        rows = [
            {"id": "a", "sections": numbered.SECTION, "english": "Approved"},
            {"id": "b", "sections": numbered.SECTION, "english": ""},
        ]
        self.assertEqual(1, numbered.fill_rows(rows, variants))
        self.assertEqual("Approved", rows[0]["english"])
        self.assertEqual("Zenmaiger No. 2", rows[1]["english"])


if __name__ == "__main__":
    unittest.main()
