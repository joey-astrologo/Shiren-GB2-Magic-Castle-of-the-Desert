from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import codec
import textdump


FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "control_dispatch.json").read_text()
)
ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"


def _code(entry):
    return int(entry["code"], 16)


class ControlParserTests(unittest.TestCase):
    def test_fixture_matches_canonical_tables(self):
        for entry in FIXTURE["entries"]:
            code = _code(entry)
            self.assertEqual(entry["arity"], codec.token_size(code) - 1)
            if entry["kind"] == "kanji":
                self.assertIn(code, codec.KANJI_PREFIX)
            elif entry["kind"] == "glyph":
                self.assertIn(code, codec.SPECIAL_GLYPHS)
            elif entry["kind"] == "control":
                self.assertEqual(entry["name"], codec.CONTROLS[code])
                self.assertEqual(entry["arity"], codec.CONTROL_ARITY.get(code, 0))
            else:
                self.assertEqual("terminator", entry["kind"])
                self.assertEqual(codec.TERMINATOR, code)

    def test_synthetic_probe_parses_at_measured_offsets(self):
        probe = FIXTURE["runtime_probe"]
        payload = bytes.fromhex(probe["payload"])
        content = payload[:-1]
        tokens = codec.parse(content)
        offsets = []
        position = 0
        for token in tokens:
            offsets.append(position)
            position += len(token.raw)
        self.assertEqual(probe["dispatch_offsets"][:-1], offsets)
        self.assertEqual(content, codec.serialize(tokens))
        self.assertEqual(
            "<cF3><F4><F5><F6><hspace:05><cF8><cF9:47:00>"
            "<delay:01><br><cFE>",
            codec.decode(content),
        )
        self.assertEqual(content, codec.encode(codec.decode(content)))

    def test_argument_ff_is_not_a_record_terminator(self):
        data = bytes.fromhex("F7 FF 30 FF F9 47 FF 31 FF")
        records = codec.strings(data)
        self.assertEqual(
            [(0, bytes.fromhex("F7 FF 30")), (4, bytes.fromhex("F9 47 FF 31"))],
            records,
        )
        for _offset, record in records:
            self.assertEqual(record, codec.serialize(codec.parse(record)))

    def test_truncated_multibyte_tokens_are_rejected(self):
        malformed = (
            bytes.fromhex("F0"),
            bytes.fromhex("F7"),
            bytes.fromhex("F9"),
            bytes.fromhex("F9 47"),
            bytes.fromhex("FA"),
        )
        for data in malformed:
            with self.subTest(data=data.hex()), self.assertRaises(codec.ParseError):
                codec.parse(data)

    def test_encoder_enforces_names_and_arities(self):
        invalid = ("<hspace>", "<hspace:01:02>", "<cF9:47>",
                   "<page:01>", "<name:01>", "<mystery>")
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                codec.encode(text)

    def test_d0_through_ef_and_f4_through_f6_are_glyphs(self):
        for code in tuple(range(0xD0, 0xF0)) + tuple(codec.SPECIAL_GLYPHS):
            with self.subTest(code=code):
                token, = codec.parse(bytes((code,)))
                self.assertEqual("glyph", token.kind)


class SourceComposerParserTests(unittest.TestCase):
    def test_source_controls_are_atomic_and_round_trip(self):
        cases = (
            ("F4 01 19 C5", "<copy:01:19:C5>"),
            ("F5 FF", "<name>"),
            ("F5 00", "<name:00>"),
            ("F6 01 19 C5", "<lookup:19:C5>"),
            ("F6 03 19 C5", "<number:19:C5>"),
            ("F6 07 19 C5", "<sourceF6:07:19:C5>"),
        )
        for raw_hex, source in cases:
            with self.subTest(raw=raw_hex):
                raw = bytes.fromhex(raw_hex)
                token, = codec.parse_source(raw)
                self.assertEqual("source_control", token.kind)
                self.assertEqual(raw, token.raw)
                self.assertEqual(source, codec.decode_source(raw))
                self.assertEqual(raw, codec.encode_source(source))

    def test_f5_argument_ff_is_not_a_source_terminator(self):
        raw = bytes.fromhex("F5 FF 49 24 40 35 56 41 36 3F D1")
        tokens = codec.parse_source(raw)
        self.assertEqual(bytes.fromhex("F5 FF"), tokens[0].raw)
        self.assertEqual("<name>は ちからつきた。", codec.decode_source(raw))
        self.assertEqual(raw, codec.encode_source(codec.decode_source(raw)))

    def test_renderer_and_source_stages_keep_distinct_f4_f6_grammar(self):
        for code, arity in codec.SOURCE_SPECIAL_ARITY.items():
            with self.subTest(code=code):
                rendered, = codec.parse(bytes((code,)))
                self.assertEqual("glyph", rendered.kind)
                source, = codec.parse_source(bytes((code,)) + bytes(arity))
                self.assertEqual("source_control", source.kind)

    def test_source_parser_rejects_bare_terminator_and_truncated_controls(self):
        malformed = (
            bytes.fromhex("FF"),
            bytes.fromhex("F4 01 19"),
            bytes.fromhex("F5"),
            bytes.fromhex("F6 01 19"),
        )
        for raw in malformed:
            with self.subTest(raw=raw.hex()), self.assertRaises(codec.ParseError):
                codec.parse_source(raw)


class OriginalRomControlIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = cls.path.read_bytes()
        if hashlib.sha1(cls.rom).hexdigest() != FIXTURE["rom_sha1"]:
            raise unittest.SkipTest("ROM hash does not match the fixture")

    def test_dispatch_table_bytes_and_targets(self):
        dispatch = FIXTURE["dispatcher"]
        start = int(dispatch["table"], 16)
        raw = self.rom[start:start + dispatch["table_size"]]
        self.assertEqual(dispatch["table_sha1"], hashlib.sha1(raw).hexdigest())
        targets = [raw[i] | (raw[i + 1] << 8) for i in range(0, len(raw), 2)]
        self.assertEqual(
            [int(entry["target"], 16) for entry in FIXTURE["entries"]],
            targets,
        )

    def test_every_candidate_parses_and_round_trips(self):
        rows = list(textdump._dialogue(self.rom))
        self.assertEqual(FIXTURE["corpus"]["candidate_count"], len(rows))
        rendered = 0
        controls = Counter()
        prefixed = Counter()
        for offset, record in rows:
            with self.subTest(offset="%06X" % offset):
                tokens = codec.parse(record)
                self.assertEqual(record, codec.serialize(tokens))
                self.assertEqual(record, codec.encode(codec.decode(record)))
                rendered += sum(token.kind in ("glyph", "kanji") for token in tokens)
                controls.update(token.code for token in tokens if token.kind == "control")
                for token in tokens:
                    if token.kind != "kanji":
                        continue
                    prefixed[token.raw] += 1

        corpus = FIXTURE["corpus"]
        self.assertEqual(corpus["rendered_glyphs"], rendered)
        mapped = {code: count for code, count in prefixed.items() if code in codec.KANJI}
        actual = {code: count for code, count in mapped.items()
                  if codec.KANJI_KIND[code] == "kanji"}
        unmapped = {code: count for code, count in prefixed.items()
                    if code not in codec.KANJI}
        self.assertEqual(corpus["prefixed_codes"], len(prefixed))
        self.assertEqual(corpus["prefixed_occurrences"], sum(prefixed.values()))
        self.assertEqual(corpus["mapped_prefixed_codes"], len(mapped))
        self.assertEqual(corpus["mapped_prefixed_occurrences"], sum(mapped.values()))
        self.assertEqual(corpus["mapped_kanji_codes"], len(actual))
        self.assertEqual(corpus["mapped_kanji_occurrences"], sum(actual.values()))
        self.assertEqual(corpus["unmapped_continuation_codes"], len(unmapped))
        self.assertEqual(
            corpus["unmapped_continuation_occurrences"], sum(unmapped.values())
        )
        self.assertEqual(corpus["speaker_occurrences"], prefixed[bytes(codec.SPEAKER)])
        self.assertEqual(
            {int(code, 16): count for code, count in corpus["control_counts"].items()},
            dict(controls),
        )

    def test_font_bank_is_not_part_of_the_script_census(self):
        self.assertNotIn(206, textdump.SCRIPT_BANKS)
        bank = 206
        block = self.rom[bank * textdump.BANK:(bank + 1) * textdump.BANK]
        false_rows = [
            record for _offset, record in codec.strings(block, bank * textdump.BANK, 6)
            if sum(1 for value in record if 0x30 <= value < 0xD0)
            >= len(record) * 0.55
        ]
        self.assertEqual(
            FIXTURE["corpus"]["excluded_bank_206_font_records"], len(false_rows)
        )


if __name__ == "__main__":
    unittest.main()
