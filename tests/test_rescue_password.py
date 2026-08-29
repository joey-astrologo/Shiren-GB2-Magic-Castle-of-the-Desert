import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import codec
import extract
import rescue_password


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "rescue_password.json").read_text(
        encoding="utf-8"
    )
)


class RescuePasswordStaticTests(unittest.TestCase):
    def test_native_alphabet_is_exactly_the_64_value_codec_domain(self):
        self.assertEqual(64, len(rescue_password.NATIVE_ALPHABET))
        self.assertEqual(64, len(set(rescue_password.NATIVE_ALPHABET)))
        self.assertEqual(
            rescue_password.NATIVE_ALPHABET_CODES,
            codec.encode(rescue_password.NATIVE_ALPHABET),
        )

    def test_public_exchange_is_native_round_trip_and_exact_length(self):
        for role, row in FIXTURE["public_exchange"].items():
            with self.subTest(role=role):
                text = row["native"]
                raw = bytes.fromhex(row["encoded_hex"])
                self.assertEqual(row["characters"], len(text))
                self.assertEqual(row["characters"], len(raw))
                self.assertEqual(raw, codec.encode(text))
                self.assertEqual(text, codec.decode(raw))
                payload = rescue_password.decode_password(raw)
                self.assertEqual(row["payload_hex"], payload.hex().upper())
                self.assertEqual(raw, rescue_password.encode_payload(payload))

    def test_packet_codec_round_trips_boundary_payloads_for_every_stage(self):
        for role, size in rescue_password.PAYLOAD_LENGTHS.items():
            payloads = (
                bytes(size),
                bytes([0xFF]) * size,
                bytes((index * 37 + size) & 0xFF for index in range(size)),
            )
            for payload in payloads:
                with self.subTest(role=role, payload=payload.hex()):
                    password = rescue_password.encode_payload(payload)
                    self.assertEqual(
                        rescue_password.PUBLIC_LENGTHS.get(role, 9),
                        len(password),
                    )
                    self.assertEqual(
                        payload,
                        rescue_password.decode_password(password, size),
                    )

    def test_packet_codec_rejects_bad_length_unknown_glyph_and_bad_checksum(self):
        with self.assertRaisesRegex(
            rescue_password.RescuePasswordCodecError,
            "does not identify",
        ):
            rescue_password.decode_password(b"")
        with self.assertRaisesRegex(
            rescue_password.RescuePasswordCodecError,
            "not in the native rescue alphabet",
        ):
            rescue_password.decode_password(bytes([0x00]) * 13)

        raw = bytearray(codec.encode(rescue_password.PUBLIC_EXCHANGE["sos"]))
        raw[-1] = rescue_password.NATIVE_ALPHABET_CODES[
            (rescue_password.NATIVE_ALPHABET_CODES.index(raw[-1]) + 1) % 64
        ]
        with self.assertRaisesRegex(
            rescue_password.RescuePasswordCodecError,
            "checksum",
        ):
            rescue_password.decode_password(raw)

    def test_documented_long_modes_have_unique_protocol_lengths(self):
        modes = rescue_password.LONG_INPUT_MODES
        self.assertEqual({5, 6, 7, 8}, set(modes))
        self.assertEqual({9, 12, 13, 15}, {row["length"] for row in modes.values()})
        self.assertEqual(
            {"training", "sos", "revival", "thank_you"},
            {row["role"] for row in modes.values()},
        )


class OriginalRomRescuePasswordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / ROM_NAME
        if not path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = path.read_bytes()

    def test_native_input_boundary_and_public_exchange_are_frozen(self):
        self.assertEqual(FIXTURE, rescue_password.analyze(self.rom))

    def test_mode_dispatch_guard_rejects_damage(self):
        damaged = bytearray(self.rom)
        damaged[
            extract.file_offset(
                rescue_password.MODE_DISPATCH_BANK,
                rescue_password.MODE_DISPATCH_ADDRESS,
            )
        ] ^= 1
        with self.assertRaisesRegex(
            rescue_password.RescuePasswordAuditError,
            "mode/maximum dispatcher",
        ):
            rescue_password.analyze(damaged)

    def test_length_resolver_guard_rejects_damage(self):
        damaged = bytearray(self.rom)
        damaged[
            extract.file_offset(
                rescue_password.LONG_LENGTH_BANK,
                rescue_password.LONG_LENGTH_ADDRESS,
            )
        ] ^= 1
        with self.assertRaisesRegex(
            rescue_password.RescuePasswordAuditError,
            "length resolver",
        ):
            rescue_password.analyze(damaged)

    def test_protocol_guard_rejects_damage_beyond_the_length_table(self):
        damaged = bytearray(self.rom)
        damaged[
            extract.file_offset(
                rescue_password.PROTOCOL_BANK,
                rescue_password.PROTOCOL_ADDRESS + 0x80,
            )
        ] ^= 1
        with self.assertRaisesRegex(
            rescue_password.RescuePasswordAuditError,
            "native password protocol",
        ):
            rescue_password.analyze(damaged)


if __name__ == "__main__":
    unittest.main()
