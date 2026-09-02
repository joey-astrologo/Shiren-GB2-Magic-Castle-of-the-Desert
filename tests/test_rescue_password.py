from hashlib import sha1
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import codec
import capture_dialogue
import extract
import pyboy_fixtures
import pyboy_route
import pyboy_state
import rescue_password


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "rescue_password.json").read_text(
        encoding="utf-8"
    )
)
REQUESTER_FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "rescue_requester.json").read_text(
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

    def test_localized_alphabet_is_frozen_unique_and_font_encodable(self):
        alphabet = rescue_password.LOCALIZED_ALPHABET
        self.assertEqual(64, len(alphabet))
        self.assertEqual(64, len(set(alphabet)))
        self.assertEqual(
            rescue_password.LOCALIZED_ALPHABET_CODES,
            rescue_password.english.encode(alphabet),
        )
        self.assertEqual(
            bytes(range(0x0A, 0x24))
            + bytes(range(0x30, 0x4A))
            + bytes(range(0x00, 0x0A))
            + bytes((0x4E, 0x4F)),
            rescue_password.LOCALIZED_ALPHABET_CODES,
        )

    def test_localized_alphabet_round_trips_every_native_symbol(self):
        localized = rescue_password.localize_password(
            rescue_password.NATIVE_ALPHABET_CODES
        )
        self.assertEqual(rescue_password.LOCALIZED_ALPHABET, localized)
        self.assertEqual(
            rescue_password.NATIVE_ALPHABET_CODES,
            rescue_password.delocalize_password(localized),
        )
        self.assertEqual(
            rescue_password.LOCALIZED_ALPHABET_CODES,
            rescue_password.localized_display_codes(
                rescue_password.NATIVE_ALPHABET_CODES
            ),
        )

    def test_public_exchange_has_a_stable_localized_representation(self):
        for role, row in FIXTURE["public_exchange"].items():
            with self.subTest(role=role):
                raw = bytes.fromhex(row["encoded_hex"])
                localized = rescue_password.localize_password(raw)
                self.assertEqual(row["localized"], localized)
                self.assertEqual(raw, rescue_password.delocalize_password(localized))

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

    def test_sos_semantic_codec_matches_public_exchange(self):
        row = FIXTURE["public_exchange"]["sos"]
        raw = bytes.fromhex(row["encoded_hex"])
        fields = rescue_password.decode_sos(raw)
        self.assertEqual(
            rescue_password.SOSPayload(
                dungeon_seed=0xBC03C8CD,
                diary_id_low16=0x8955,
                x=6,
                y=26,
                dungeon_id=6,
                internal_floor=27,
            ),
            fields,
        )
        self.assertEqual(bytes.fromhex(row["payload_hex"]), fields.to_payload())
        self.assertEqual(raw, rescue_password.encode_sos(fields))

    def test_sos_semantic_codec_round_trips_field_boundaries(self):
        records = (
            rescue_password.SOSPayload(0, 0, 0, 0, 0, 0),
            rescue_password.SOSPayload(
                0xFFFFFFFF,
                0xFFFF,
                0x1F,
                0x1F,
                0x0F,
                0x7F,
            ),
        )
        for fields in records:
            with self.subTest(fields=fields):
                raw = rescue_password.encode_sos(fields)
                self.assertEqual(13, len(raw))
                self.assertEqual(fields, rescue_password.decode_sos(raw))

    def test_sos_semantic_codec_rejects_bad_fields_and_reserved_bits(self):
        with self.assertRaisesRegex(
            rescue_password.RescuePasswordCodecError,
            "x is 32",
        ):
            rescue_password.SOSPayload(0, 0, 32, 0, 0, 0)
        with self.assertRaisesRegex(
            rescue_password.RescuePasswordCodecError,
            "requires an SOSPayload",
        ):
            rescue_password.encode_sos(bytes(9))
        with self.assertRaisesRegex(
            rescue_password.RescuePasswordCodecError,
            "nonzero reserved bits",
        ):
            rescue_password.SOSPayload.from_payload(bytes(8) + b"\x80")

    def test_public_three_password_exchange_is_semantically_linked(self):
        rows = FIXTURE["public_exchange"]
        sos, revival = rescue_password.validate_exchange(
            bytes.fromhex(rows["sos"]["encoded_hex"]),
            bytes.fromhex(rows["revival"]["encoded_hex"]),
            bytes.fromhex(rows["thank_you"]["encoded_hex"]),
        )
        self.assertEqual(0xA9, revival.rescuer_diary_checksum)
        self.assertEqual(bytes.fromhex("6C00000004000000"), revival.gift_bytes)
        self.assertEqual(
            bytes.fromhex(rows["revival"]["encoded_hex"]),
            rescue_password.encode_revival(revival, sos),
        )
        self.assertEqual(
            bytes.fromhex(rows["thank_you"]["encoded_hex"]),
            rescue_password.encode_thank_you(sos, revival),
        )

    def test_revival_rejects_a_password_for_a_different_sos(self):
        rows = FIXTURE["public_exchange"]
        sos = rescue_password.decode_sos(
            bytes.fromhex(rows["sos"]["encoded_hex"])
        )
        wrong_sos = rescue_password.SOSPayload(
            sos.dungeon_seed ^ 1,
            sos.diary_id_low16,
            sos.x,
            sos.y,
            sos.dungeon_id,
            sos.internal_floor,
        )
        with self.assertRaisesRegex(
            rescue_password.RescuePasswordCodecError,
            "does not match the SOS checksum",
        ):
            rescue_password.decode_revival(
                bytes.fromhex(rows["revival"]["encoded_hex"]), wrong_sos
            )

    def test_thank_you_rejects_a_mismatched_exchange(self):
        rows = FIXTURE["public_exchange"]
        raw = bytearray(bytes.fromhex(rows["thank_you"]["encoded_hex"]))
        payload = bytearray(rescue_password.decode_password(raw))
        payload[0] ^= 1
        wrong_thanks = rescue_password.encode_payload(payload)
        with self.assertRaisesRegex(
            rescue_password.RescuePasswordCodecError,
            "does not match the SOS and Revival",
        ):
            rescue_password.validate_exchange(
                bytes.fromhex(rows["sos"]["encoded_hex"]),
                bytes.fromhex(rows["revival"]["encoded_hex"]),
                wrong_thanks,
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

    def test_sos_builder_guard_rejects_damage(self):
        damaged = bytearray(self.rom)
        damaged[
            extract.file_offset(
                rescue_password.SOS_BUILDER_BANK,
                rescue_password.SOS_BUILDER_ADDRESS,
            )
        ] ^= 1
        with self.assertRaisesRegex(
            rescue_password.RescuePasswordAuditError,
            "SOS semantic builder",
        ):
            rescue_password.analyze(damaged)

    def test_diary_payload_record_guard_rejects_damage(self):
        damaged = bytearray(self.rom)
        damaged[
            extract.file_offset(
                rescue_password.PAYLOAD_RECORD_BANK,
                rescue_password.PAYLOAD_RECORD_ADDRESS,
            )
        ] ^= 1
        with self.assertRaisesRegex(
            rescue_password.RescuePasswordAuditError,
            "diary payload-record dispatcher",
        ):
            rescue_password.analyze(damaged)

    def test_stage_route_guard_rejects_damage(self):
        damaged = bytearray(self.rom)
        damaged[
            extract.file_offset(
                rescue_password.SOS_ROUTE_BANK,
                rescue_password.SOS_ROUTE_ADDRESS,
            )
        ] ^= 1
        with self.assertRaisesRegex(
            rescue_password.RescuePasswordAuditError,
            "SOS generation route",
        ):
            rescue_password.analyze(damaged)

    def test_revival_thank_you_route_guard_rejects_damage(self):
        damaged = bytearray(self.rom)
        damaged[
            extract.file_offset(
                rescue_password.REVIVAL_ROUTE_BANK,
                rescue_password.REVIVAL_ROUTE_ADDRESS,
            )
        ] ^= 1
        with self.assertRaisesRegex(
            rescue_password.RescuePasswordAuditError,
            "Revival decode and Thank-You generation route",
        ):
            rescue_password.analyze(damaged)

    def test_requester_actor_hp_guards_reject_damage(self):
        regions = (
            (
                rescue_password.ACTOR_RECORD_ROUTE_BANK,
                rescue_password.ACTOR_RECORD_ROUTE_ADDRESS,
                "actor record/cache route",
            ),
            (
                rescue_password.CURRENT_HP_DAMAGE_BANK,
                rescue_password.CURRENT_HP_DAMAGE_ADDRESS,
                "current-HP damage route",
            ),
            (
                rescue_password.ACTOR_HP_ACCESSOR_BANK,
                rescue_password.ACTOR_HP_ACCESSOR_ADDRESS,
                "actor Max-HP/current-HP accessors",
            ),
        )
        for bank, address, label in regions:
            with self.subTest(label=label):
                damaged = bytearray(self.rom)
                damaged[extract.file_offset(bank, address)] ^= 1
                with self.assertRaisesRegex(
                    rescue_password.RescuePasswordAuditError,
                    re.escape(label),
                ):
                    rescue_password.analyze(damaged)


class RescueRequesterPrepHelperTests(unittest.TestCase):
    MAMEL_STATE_SHA1 = "f03f9ed6e5a9562789903e1360892caff68382be"

    @classmethod
    def setUpClass(cls):
        cls.state = ROOT / "SaveStates" / "Mamel.state"
        if not cls.state.is_file():
            raise unittest.SkipTest("Mamel PyBoy state fixture is unavailable")

    def test_helper_addresses_match_the_guarded_native_actor_contract(self):
        self.assertEqual(
            rescue_password.PLAYER_ACTOR_WRAM_BANK,
            pyboy_fixtures.PLAYER_ACTOR_BANK,
        )
        self.assertEqual(
            rescue_password.PLAYER_ACTOR_ADDRESS,
            pyboy_fixtures.PLAYER_ACTOR_ADDRESS,
        )
        self.assertEqual(
            rescue_password.PLAYER_ACTOR_FLAT_ADDRESS,
            pyboy_fixtures.PLAYER_ACTOR_BANK * 0x1000
            + pyboy_fixtures.PLAYER_ACTOR_ADDRESS - 0xD000,
        )
        self.assertEqual(
            rescue_password.ACTOR_RECORD_SIZE,
            pyboy_fixtures.ACTOR_RECORD_SIZE,
        )
        self.assertEqual(
            rescue_password.ACTOR_CACHE_ADDRESS,
            pyboy_fixtures.PLAYER_ACTOR_CACHE_ADDRESS,
        )
        self.assertEqual(
            rescue_password.ACTIVE_ACTOR_ADDRESS,
            pyboy_fixtures.ACTIVE_ACTOR_ADDRESS,
        )
        self.assertEqual(
            rescue_password.MAX_HP_OFFSET,
            pyboy_fixtures.MAX_HP_OFFSET,
        )
        self.assertEqual(
            rescue_password.CURRENT_HP_OFFSET,
            pyboy_fixtures.CURRENT_HP_OFFSET,
        )

    def test_mamel_fixture_has_a_synchronized_live_player_record(self):
        self.assertEqual(
            self.MAMEL_STATE_SHA1,
            sha1(self.state.read_bytes()).hexdigest(),
        )
        work_ram = pyboy_state.work_ram(self.state)
        high_ram = pyboy_state.high_ram(self.state)
        actor_at = rescue_password.PLAYER_ACTOR_FLAT_ADDRESS
        cache_at = rescue_password.ACTOR_CACHE_ADDRESS - 0xFF80
        active_at = rescue_password.ACTIVE_ACTOR_ADDRESS - 0xFF80
        actor = work_ram[actor_at:actor_at + rescue_password.ACTOR_RECORD_SIZE]
        cache = high_ram[cache_at:cache_at + rescue_password.ACTOR_RECORD_SIZE]
        self.assertEqual(rescue_password.ACTOR_RECORD_SIZE, len(actor))
        self.assertEqual(actor, cache)
        self.assertEqual(0, high_ram[active_at])
        self.assertEqual(40, actor[rescue_password.MAX_HP_OFFSET])
        self.assertEqual(40, actor[rescue_password.CURRENT_HP_OFFSET])


class RescueRequesterCaptureTests(unittest.TestCase):
    BUFFER_OFFSET = 0x16D
    MODE_OFFSET = 0x195
    POSITION_OFFSET = 0x152
    MAXIMUM_OFFSET = 0x153
    SOS_DIARY_RECORD_OFFSET = 0x23C + 0x41

    def _load_capture(self, key):
        row = REQUESTER_FIXTURE[key]
        state = ROOT / row["path"]
        if not state.is_file():
            self.skipTest("%s fixture is unavailable" % row["path"])
        self.assertEqual(row["sha1"], sha1(state.read_bytes()).hexdigest())
        return row, pyboy_state.work_ram(state)

    def test_manually_accepted_localized_sos_is_a_stable_semantic_fixture(self):
        row = REQUESTER_FIXTURE["manual_accepted_sos"]
        raw = rescue_password.delocalize_password(row["localized_password"])
        self.assertEqual(bytes.fromhex(row["native_hex"]), raw)
        self.assertEqual(
            bytes.fromhex(row["payload_hex"]),
            rescue_password.decode_password(raw),
        )
        fields = rescue_password.decode_sos(raw)
        expected = row["semantic_fields"]
        self.assertEqual(
            int(expected["dungeon_seed"].removeprefix("$"), 16),
            fields.dungeon_seed,
        )
        self.assertEqual(
            int(expected["diary_id_low16"].removeprefix("$"), 16),
            fields.diary_id_low16,
        )
        self.assertEqual(expected["x"], fields.x)
        self.assertEqual(expected["y"], fields.y)
        self.assertEqual(expected["dungeon_id"], fields.dungeon_id)
        self.assertEqual(expected["internal_floor"], fields.internal_floor)
        self.assertEqual("accepted_in_localized_rescue_editor", row["result"])

    def test_revival_response_fixture_is_linked_to_the_captured_request(self):
        row = REQUESTER_FIXTURE["revival_response_test"]
        sos_raw = rescue_password.delocalize_password(row["matching_sos"])
        revival_raw = rescue_password.delocalize_password(
            row["revival"]["localized_password"]
        )
        thank_you_raw = rescue_password.delocalize_password(
            row["thank_you"]["localized_password"]
        )
        self.assertEqual(bytes.fromhex(row["revival"]["native_hex"]), revival_raw)
        self.assertEqual(
            bytes.fromhex(row["revival"]["payload_hex"]),
            rescue_password.decode_password(revival_raw),
        )
        self.assertEqual(
            bytes.fromhex(row["thank_you"]["native_hex"]),
            thank_you_raw,
        )
        self.assertEqual(
            bytes.fromhex(row["thank_you"]["payload_hex"]),
            rescue_password.decode_password(thank_you_raw),
        )
        _sos, revival = rescue_password.validate_exchange(
            sos_raw, revival_raw, thank_you_raw
        )
        self.assertEqual(
            int(row["revival"]["rescuer_diary_checksum"].removeprefix("$"), 16),
            revival.rescuer_diary_checksum,
        )
        self.assertEqual(bytes.fromhex(row["revival"]["gift_hex"]), revival.gift_bytes)
        self.assertEqual(
            "accepted_and_generated_thank_you_password",
            row["result"],
        )
        self.assertEqual(
            "revival_and_thank_you_password_confirmed_in_mesen",
            row["manual_result"],
        )

    def test_rankings_capture_precedes_sos_generation(self):
        row, work_ram = self._load_capture("ranking_state")
        self.assertEqual(row["mode"], work_ram[self.MODE_OFFSET])
        self.assertEqual(row["position"], work_ram[self.POSITION_OFFSET])
        self.assertEqual(row["maximum"], work_ram[self.MAXIMUM_OFFSET])
        self.assertEqual(
            bytes.fromhex(row["buffer_hex"]),
            work_ram[self.BUFFER_OFFSET:self.BUFFER_OFFSET + 14],
        )
        self.assertEqual(
            bytes.fromhex(row["sos_diary_record_hex"]),
            work_ram[
                self.SOS_DIARY_RECORD_OFFSET:self.SOS_DIARY_RECORD_OFFSET + 10
            ],
        )

    def test_sos_capture_password_matches_the_saved_diary_record(self):
        row, work_ram = self._load_capture("sos_state")
        self.assertEqual(row["mode"], work_ram[self.MODE_OFFSET])
        self.assertEqual(row["position"], work_ram[self.POSITION_OFFSET])
        self.assertEqual(row["maximum"], work_ram[self.MAXIMUM_OFFSET])
        buffer = work_ram[self.BUFFER_OFFSET:self.BUFFER_OFFSET + 14]
        self.assertEqual(bytes.fromhex(row["buffer_hex"]), buffer)
        raw = buffer.split(b"\xFF", 1)[0]
        self.assertEqual(row["native_password"], codec.decode(raw))
        self.assertEqual(
            row["localized_password"],
            rescue_password.localize_password(raw),
        )
        self.assertEqual(
            bytes.fromhex(row["payload_hex"]),
            rescue_password.decode_password(raw),
        )
        fields = rescue_password.decode_sos(raw)
        expected = row["semantic_fields"]
        self.assertEqual(
            int(expected["dungeon_seed"].removeprefix("$"), 16),
            fields.dungeon_seed,
        )
        self.assertEqual(
            int(expected["diary_id_low16"].removeprefix("$"), 16),
            fields.diary_id_low16,
        )
        self.assertEqual(expected["x"], fields.x)
        self.assertEqual(expected["y"], fields.y)
        self.assertEqual(expected["dungeon_id"], fields.dungeon_id)
        self.assertEqual(expected["internal_floor"], fields.internal_floor)
        diary = work_ram[
            self.SOS_DIARY_RECORD_OFFSET:self.SOS_DIARY_RECORD_OFFSET + 10
        ]
        self.assertEqual(bytes.fromhex(row["sos_diary_record_hex"]), diary)
        self.assertEqual(diary, fields.to_diary_record())

    def test_sos_capture_sram_is_frozen_with_the_state(self):
        row = REQUESTER_FIXTURE["sos_state"]
        sram = ROOT / row["sram_path"]
        if not sram.is_file():
            self.skipTest("%s fixture is unavailable" % row["sram_path"])
        self.assertEqual(row["sram_sha1"], sha1(sram.read_bytes()).hexdigest())

    def test_read_only_capture_probe_does_not_write_emulated_memory(self):
        state = ROOT / REQUESTER_FIXTURE["sos_state"]["path"]
        before = state.read_bytes()
        pyboy_state.work_ram(state)
        self.assertEqual(before, state.read_bytes())


class RescueRequesterPrepLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = ROOT / ROM_NAME
        cls.state = ROOT / "SaveStates" / "Mamel.state"
        if not cls.rom.is_file() or not cls.state.is_file():
            raise unittest.SkipTest("original ROM and Mamel state are required")
        if sha1(cls.rom.read_bytes()).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc

    def test_helper_updates_both_current_hp_views_and_preserves_max_hp(self):
        pyboy = pyboy_route.start(self.PyBoy, self.rom, self.state)
        try:
            before = pyboy_route.flat_work_ram(pyboy)
            maximum = pyboy_fixtures.prepare_rescue_request(pyboy)
            after = pyboy_route.flat_work_ram(pyboy)
            differences = [
                index for index, pair in enumerate(zip(before, after))
                if pair[0] != pair[1]
            ]
            self.assertEqual(40, maximum)
            self.assertEqual(
                [
                    rescue_password.PLAYER_ACTOR_FLAT_ADDRESS
                    + rescue_password.CURRENT_HP_OFFSET
                ],
                differences,
            )
            self.assertEqual(
                1,
                pyboy.memory[
                    rescue_password.ACTOR_CACHE_ADDRESS
                    + rescue_password.CURRENT_HP_OFFSET
                ],
            )
            self.assertEqual(
                40,
                pyboy.memory[
                    rescue_password.ACTOR_CACHE_ADDRESS
                    + rescue_password.MAX_HP_OFFSET
                ],
            )
        finally:
            pyboy.stop(save=False)


if __name__ == "__main__":
    unittest.main()
