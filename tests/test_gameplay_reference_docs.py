import csv
import json
from pathlib import Path
import re
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import translate_spells


TABLE_ROW = re.compile(r"^\|\s*(?:`([^`]+)`|(\d+))\s*\|\s*(?:`([^`]+)`|([^|]+?))\s*\|$")


def _table_rows(path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = TABLE_ROW.match(line)
        if not match:
            continue
        left = match.group(1) or match.group(2)
        right = match.group(3) or match.group(4).strip()
        rows.append((left, right))
    return rows


class GameplayReferenceDocsTests(unittest.TestCase):
    def test_blank_scroll_reference_lists_every_writable_input_and_result(self):
        fixture = json.loads(
            (ROOT / "tests" / "fixtures" / "blank_scroll.json").read_text(
                encoding="utf-8"
            )
        )
        with (ROOT / "script" / "organized" / "glossary.tsv").open(
            encoding="utf-8", newline=""
        ) as handle:
            glossary = list(csv.DictReader(handle, delimiter="\t"))

        expected = []
        for entry in fixture["accepted"]:
            item_index = 124 + entry["root_index"] - 47
            reference = f"g004[{item_index:03d}]"
            item = next(row["english"] for row in glossary if reference in row["references"])
            expected.append((entry["input"], item))

        path = ROOT / "docs" / "BLANK_SCROLL_INPUTS.md"
        self.assertEqual(expected, _table_rows(path))

    def test_big_moai_reference_lists_all_100_enterable_codes(self):
        expected = [
            (str(index + 1), translate_spells.spell_code(index))
            for index in range(100)
        ]
        path = ROOT / "docs" / "BIG_MOAI_CODES.md"
        self.assertEqual(expected, _table_rows(path))

    def test_docs_index_links_both_player_references(self):
        index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        self.assertIn("[BLANK_SCROLL_INPUTS.md](BLANK_SCROLL_INPUTS.md)", index)
        self.assertIn("[BIG_MOAI_CODES.md](BIG_MOAI_CODES.md)", index)


if __name__ == "__main__":
    unittest.main()
