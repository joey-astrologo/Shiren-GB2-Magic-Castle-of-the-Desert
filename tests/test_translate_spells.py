from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import translate_spells


class SpellTranslationTests(unittest.TestCase):
    def test_codes_are_unique_uppercase_and_exactly_four_bytes(self):
        codes = [translate_spells.spell_code(index) for index in range(100)]
        self.assertEqual(100, len(set(codes)))
        for code in codes:
            self.assertEqual(4, len(code))
            self.assertEqual(code, code.upper())
            self.assertTrue(code.isalnum())

    def test_story_spells_use_memorable_enterable_codes(self):
        self.assertEqual(
            ["WISH", "RANU", "BADE", "SUGI", "TSUB", "MAMA", "HOYO"],
            [translate_spells.spell_code(index) for index in range(93, 100)],
        )

    def test_runtime_and_debug_tables_have_matching_complete_coverage(self):
        targets = translate_spells.catalog_targets()
        self.assertEqual(200, len(targets))
        values = list(targets.values())
        for index in range(100):
            code = translate_spells.spell_code(index)
            self.assertIn(code, values)
            self.assertIn(f"Spell {index + 1}: {code}", values)


if __name__ == "__main__":
    unittest.main()
