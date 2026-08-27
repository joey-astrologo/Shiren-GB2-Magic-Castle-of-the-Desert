import contextlib
import csv
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
import extract
import lint_en
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "translation_lint.json").read_text(
        encoding="utf-8"
    )
)


class OriginalRomTranslationLintTests(unittest.TestCase):
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

    def _translated(self, rows):
        out = {}
        for record_id, text in rows:
            record = self.by_id[record_id]
            explicit_empty = text == translations.EMPTY_SENTINEL
            encoded = b"" if explicit_empty else english.encode_source(text)
            out[(record.bank, record.address)] = translations.Translation(
                record_id=record.id,
                source_bank=record.bank,
                source_address=record.address,
                text="" if explicit_empty else text,
                encoded=encoded,
                explicit_empty=explicit_empty,
            )
        return out

    def _write_tsv(self, path, rows):
        with Path(path).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            writer.writerow(("id", "english"))
            writer.writerows(rows)

    def test_production_workspace_and_contract_census_are_frozen(self):
        translated = translations.load_path(
            ROOT / "script" / "en", self.result["records"]
        )
        exceptions = lint_en.load_exceptions(
            ROOT / "script" / "en" / lint_en.EXCEPTION_FILENAME, self.result
        )
        issues = lint_en.check(self.result, translated, exceptions)
        self.assertEqual((), issues)
        self.assertEqual(
            FIXTURE,
            lint_en.summary(self.result, translated, issues, exceptions),
        )

    def test_runtime_substitutions_are_exact_multisets(self):
        record = self.by_id["193:$422E"]
        missing = self._translated(((record.id, "Fell."),))
        issues = lint_en.check_runtime_tokens(record, next(iter(missing.values())))
        self.assertEqual(["token_lost"], [issue.kind for issue in issues])
        self.assertIn("<lookup:19:C5>", issues[0].detail)

        wrong = self._translated(((record.id, "<lookup:1A:C5> fell."),))
        issues = lint_en.check_runtime_tokens(record, next(iter(wrong.values())))
        self.assertEqual(["token_added", "token_lost"], sorted(i.kind for i in issues))

        exact = self._translated(((record.id, "<lookup:19:C5> fell."),))
        self.assertEqual(
            (), lint_en.check_runtime_tokens(record, next(iter(exact.values())))
        )

    def test_native_soft_wrap_checkpoint_cannot_be_dropped(self):
        record = self.by_id["193:$45A9"]
        missing = self._translated(((record.id, "Stole 100 Gitan!"),))
        issues = lint_en.check_native_soft_wrap(
            record, next(iter(missing.values()))
        )
        self.assertEqual(["soft_wrap_lost"], [issue.kind for issue in issues])
        self.assertIn("conditional wrap checkpoint", issues[0].detail)

        preserved = self._translated(
            ((record.id, "Stole <cF3>100 Gitan!"),)
        )
        self.assertEqual(
            (),
            lint_en.check_native_soft_wrap(
                record, next(iter(preserved.values()))
            ),
        )

    def test_sentence_spacing_survives_same_line_page_controls(self):
        record = self.by_id["195:$5D43"]
        for punctuation, name in (("?", "question mark"), ("!", "exclamation mark")):
            with self.subTest(punctuation=punctuation):
                missing = self._translated(
                    (
                        (
                            record.id,
                            "Pekeji: Well%s<page>Tempting.<page><box>"
                            % punctuation,
                        ),
                    )
                )
                issues = lint_en.check_sentence_spacing(
                    record, next(iter(missing.values()))
                )
                self.assertEqual(
                    ["sentence_spacing"], [issue.kind for issue in issues]
                )
                self.assertIn(name, issues[0].detail)
                self.assertIn("<page>", issues[0].detail)

                corrected = self._translated(
                    (
                        (
                            record.id,
                            "Pekeji: Well%s<page> Tempting.<page><box>"
                            % punctuation,
                        ),
                    )
                )
                self.assertEqual(
                    (),
                    lint_en.check_sentence_spacing(
                        record, next(iter(corrected.values()))
                    ),
                )

        emphatic = self._translated(
            ((record.id, "Pekeji: Really?!<page><box>"),)
        )
        self.assertEqual(
            (),
            lint_en.check_sentence_spacing(
                record, next(iter(emphatic.values()))
            ),
        )

    def test_glossary_splits_and_within_family_collisions_fail(self):
        translated = self._translated(
            (
                ("192:$4E4B", "Oryu"),
                ("192:$5373", "Oryuu"),
                ("192:$4BD7", "Same"),
                ("192:$4BDB", "Same"),
            )
        )
        definitions = lint_en.glossary_definitions(self.result, translated)
        issues = lint_en.check_glossary(definitions)
        kinds = {issue.kind for issue in issues}
        self.assertEqual({"glossary_collision", "glossary_split"}, kinds)
        self.assertTrue(
            any(
                issue.key
                == ("192:$4E4B", "glossary_split", "192:$5373")
                for issue in issues
            )
        )
        self.assertTrue(
            any(
                issue.key
                == ("192:$4BD7", "glossary_collision", "192:$4BDB")
                for issue in issues
            )
        )

    def test_longest_term_enforcement_and_reviewed_exceptions(self):
        glossary_id = "192:$4C48"
        usage_id = "193:$6943"
        translated = self._translated(
            ((glossary_id, "Dragon"), (usage_id, "Caught it."))
        )
        issues = lint_en.check(self.result, translated)
        term_issue = next(issue for issue in issues if issue.kind == "term_ignored")
        self.assertEqual(usage_id, term_issue.record_id)
        self.assertEqual(glossary_id, term_issue.related_id)

        exception = lint_en.LintException(
            usage_id,
            "term_ignored",
            glossary_id,
            "This screen deliberately replaces the species name with a pronoun.",
        )
        self.assertEqual((), lint_en.check(self.result, translated, (exception,)))

        corrected = self._translated(
            ((glossary_id, "Dragon"), (usage_id, "Caught Dragon."))
        )
        self.assertEqual((), lint_en.check(self.result, corrected))
        stale = lint_en.check(self.result, corrected, (exception,))
        self.assertEqual(["stale_exception"], [issue.kind for issue in stale])

        # An untranslated longer definition must still mask a translated term
        # nested inside it. This keeps partial glossary work from misreading a
        # compound actor name as a use of its shorter family name.
        partial = self._translated(
            (("192:$4BD7", "Mamel"), ("194:$505F", "Cave creature"))
        )
        self.assertFalse(
            any(issue.kind == "term_ignored" for issue in lint_en.check(self.result, partial))
        )

    def test_internal_explanation_actor_label_is_not_imposed_on_prose(self):
        translated = self._translated((("192:$4F4F", "Guide"),))
        definition = next(
            item
            for item in lint_en.glossary_definitions(self.result, translated)
            if item.record_id == "192:$4F4F"
        )
        self.assertFalse(definition.searchable)
        self.assertNotIn(
            "192:$4F4F",
            {term.glossary_id for term in lint_en.search_terms((definition,))},
        )

    def test_exception_contract_rejects_unknown_unreasoned_and_stale_rows(self):
        valid = {
            "id": "193:$6943",
            "kind": "term_ignored",
            "related_id": "192:$4C48",
            "reason": "Reviewed wording deliberately uses a pronoun.",
        }
        cases = (
            ("unknown stable ID", {**valid, "id": "999:$4000"}),
            ("unsupported kind", {**valid, "kind": "token_lost"}),
            ("written reason", {**valid, "reason": ""}),
        )
        for message, row in cases:
            with self.subTest(message=message):
                with tempfile.TemporaryDirectory() as temporary:
                    path = Path(temporary) / "exceptions.json"
                    path.write_text(
                        json.dumps(
                            {
                                "schema": lint_en.EXCEPTION_SCHEMA,
                                "exceptions": [row],
                            }
                        ),
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(
                        lint_en.TranslationLintError, message
                    ):
                        lint_en.load_exceptions(path, self.result)

    def test_production_build_refuses_lint_failure_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            translations_dir = root / "en"
            translations_dir.mkdir()
            self._write_tsv(
                translations_dir / "glossary.tsv",
                (("192:$4C48", "Dragon"),),
            )
            self._write_tsv(
                translations_dir / "messages.tsv",
                (("193:$6943", "Caught it."),),
            )
            output = root / "should-not-exist.gbc"
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                with self.assertRaises(SystemExit) as raised:
                    translation_build.main(
                        (str(self.path), str(translations_dir), str(output))
                    )
            self.assertEqual(1, raised.exception.code)
            self.assertIn("term_ignored", errors.getvalue())
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
