import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import unicodedata
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import rescue_converter as converter
import rescue_password as protocol


def browser_vectors():
    """Independent native-codec oracle for the browser's reimplementation."""
    rng = random.Random(0x474232)
    vectors = []
    for size in protocol.PAYLOAD_LENGTHS.values():
        for _ in range(256):
            payload = bytes(rng.randrange(256) for _ in range(size))
            raw = protocol.encode_payload(payload)
            english = protocol.localize_password(raw)
            japanese = "".join(protocol.NATIVE_ALPHABET[protocol.NATIVE_ALPHABET_CODES.index(code)] for code in raw)
            expected = {
                "japanese": japanese, "english": english,
                "kind": converter.KINDS[len(raw)], "length": len(raw),
                "payload_hex": payload.hex(),
            }
            vectors.extend([
                {"input": japanese, "to": "english", "expected": expected},
                {"input": english, "to": "japanese", "expected": expected},
            ])
    # The decoder ignores low padding bits in an incomplete high-bit group.
    # A converter must preserve these symbols, not decode/re-encode them away.
    for size in (8, 10):
        raw = protocol.encode_payload(bytes(range(size)))
        values = [protocol.NATIVE_ALPHABET_CODES.index(code) for code in raw]
        unpacked = protocol._swap_pairs(list(reversed(values)))
        unpacked[-2] |= 1
        preserved = bytes(protocol.NATIVE_ALPHABET_CODES[value]
                          for value in reversed(protocol._swap_pairs(unpacked)))
        english = protocol.localize_password(preserved)
        japanese = "".join(protocol.NATIVE_ALPHABET[protocol.LOCALIZED_ALPHABET.index(c)] for c in english)
        expected = {"japanese": japanese, "english": english,
                    "kind": converter.KINDS[len(raw)], "length": len(raw),
                    "payload_hex": bytes(range(size)).hex()}
        vectors.append({"input": japanese, "to": "english", "expected": expected})
        vectors.append({"input": english, "to": "japanese", "expected": expected})
    for mission in converter.mission_data()["missions"]:
        expected = {key: mission[key] for key in ("japanese", "english", "payload_hex")}
        expected.update(kind="sos", length=13)
        vectors.extend([
            {"input": mission["japanese"], "to": "english", "expected": expected},
            {"input": mission["english"], "to": "japanese", "expected": expected},
        ])
    example = vectors[-6]
    for text in (
        " ろいほおん\nりぶづおき\tぐすも\u3000",
        unicodedata.normalize("NFD", example["input"]),
        "ﾛｲﾎｵﾝﾘﾌﾞﾂﾞｵｷｸﾞｽﾓ",
    ):
        vectors.append(dict(example, input=text))
    vectors.append({"input": "ｑＢｄＥｔｎ！６ＥＧｗＭｉ", "to": "japanese", "expected": example["expected"]})
    return vectors


class RescueConverterTests(unittest.TestCase):
    def test_published_missions_and_destinations(self):
        missions = converter.mission_data()["missions"]
        self.assertEqual(["qBdEtn!6EGwMi", "e!8myroubgO8A", "AIGJ!7XWTVL!x"],
                         [mission["english"] for mission in missions])
        self.assertEqual([(8, 20), (7, 40), (6, 98)],
                         [(mission["dungeon_id"], mission["floor"]) for mission in missions])

    def test_native_codec_parity_all_packet_types_and_preserved_padding(self):
        symbols = set()
        for vector in browser_vectors():
            with self.subTest(code=vector["input"], to=vector["to"]):
                result = converter.convert(vector["input"], vector["to"])
                self.assertEqual(vector["expected"], result)
                symbols.update(result["english"])
        self.assertEqual(set(protocol.LOCALIZED_ALPHABET), symbols)

    def test_invalid_input_fails_without_a_converted_result(self):
        for text, to in [("", "english"), ("あ" * 6, "english"), ("WISH", "japanese"),
                         ("ろいほおんりぶづおきぐすA", "english"),
                         ("qBdEtn!6EGwMi", "english"), ("ろいほおんりぶづおきぐすも", "japanese"),
                         ("qBdEtn!6EGwMA", "japanese"), ("qBdEtn!6EGwMi", "invalid"),
                         ("qBdEtn!6EGwMi\u200b", "japanese"), ("😀" * 13, "english")]:
            with self.subTest(text=text, to=to):
                with self.assertRaises(ValueError):
                    converter.convert(text, to)

    def test_browser_data_is_generated_from_the_patch_alphabet(self):
        self.assertEqual(converter.web_data(),
                         (ROOT / "docs/rescue-converter/password-data.js").read_text())

    def test_cli_stdin_reverse_json_and_errors(self):
        command = [sys.executable, str(ROOT / "tools/rescue_converter.py")]
        success = subprocess.run(command + ["-"], input="ろいほおんりぶづおきぐすも\n", text=True, capture_output=True)
        self.assertEqual(0, success.returncode, success.stderr)
        self.assertEqual("qBdEtn!6EGwMi\n", success.stdout)
        reverse = subprocess.run(command + ["qBdEtn!6EGwMi", "--to", "japanese", "--json"], text=True, capture_output=True)
        self.assertEqual(0, reverse.returncode, reverse.stderr)
        self.assertEqual("ろいほおんりぶづおきぐすも", json.loads(reverse.stdout)["japanese"])
        failure = subprocess.run(command + ["qBdEtn!6EGwMA", "--to", "japanese"], text=True, capture_output=True)
        self.assertNotEqual(0, failure.returncode)
        self.assertEqual("", failure.stdout)
        self.assertIn("checksum", failure.stderr)

    def test_browser_javascript_matches_native_python_codec(self):
        node = os.environ.get("SHIREN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for browser-codec parity; set SHIREN_NODE if necessary")
        process = subprocess.run(
            [node, str(ROOT / "tests/rescue_converter.test.cjs")],
            input=json.dumps(browser_vectors()), text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)
        self.assertIn("browser codec checks passed", process.stdout)


if __name__ == "__main__":
    unittest.main()
