#!/usr/bin/env python3
"""Build a translation-aware relocated GB2 ROM.

English overrides are keyed by the stable original ``bank:$address`` record IDs emitted
by ``extract.py``. Before any output is written, runtime substitutions and derived-glossary
consistency are linted. Every nonblank override is then source-encoded, the affected table
units are resized and repacked, all directory rows are rewritten, Thin Pixel-7 is installed,
and every output reference is validated against either its override or original bytes.
"""
import argparse
from hashlib import sha1
from pathlib import Path
import sys

import allocate
import blank_scroll
import dialogue_pacing
import english_font
import extract
import insert
import item_formatting
import item_status
import layout
import lint_en
import menu_graphics
import name6
import rescue_presentation
import runtime_widths
import spell_input
import stairs_menu
import service_menus
import translations as translation_file
import unidentified_names


# Group 15 contains all synthesis-rune descriptions. The item-detail
# constructor draws each record directly from x=3 to the 144-pixel canvas
# edge; unlike source-composed prose, these rows therefore have 141 pixels.
ITEM_ABILITY_DESCRIPTION_GROUP = 15
ITEM_ABILITY_DESCRIPTION_ENTRIES = 69
ITEM_ABILITY_DESCRIPTION_START_X = 3
ITEM_ABILITY_DESCRIPTION_RIGHT_EDGE = layout.CANVAS_WIDTH_PIXELS

MAIN_MENU_LEFT_DOMAINS = (
    (7, (35, 63), 3, 0, 53),
    (7, (36, 39, 56, 64), 3, 12, 53),
)
MAIN_MENU_LOCATION_GROUP = 24
MAIN_MENU_LOCATION_RANGE = (19, 48)
MAIN_MENU_LOCATION_LEFT_EDGE = 59
MAIN_MENU_LOCATION_ANCHOR = 142
MAIN_MENU_LOCATION_Y = 24

# Every item-action command is drawn into one of eight fixed 48-pixel columns.
# Group 7 index 0 is the independent Items heading; indices 1..24 are the
# complete command vocabulary shared by all 16 item and trap action classes.
ITEM_ACTION_GROUP = 7
ITEM_ACTION_INDEX_RANGE = (1, 24)
ITEM_ACTION_START_X = 8
ITEM_ACTION_RIGHT_EDGE = 56

# Help -> Status uses a 136-pixel heading row and a separate full-width body.
# The affected branch selects every nonempty group-28 record through one finite
# effect table, while the clean branch draws group 7 index 84 in the same body.
STATUS_CONDITION_GROUP = 28
STATUS_CONDITION_INDEX_RANGE = (0, 55)
STATUS_CONDITION_BODY_START_X = 1
STATUS_CONDITION_BODY_RIGHT_EDGE = layout.CANVAS_WIDTH_PIXELS
STATUS_CONDITION_UI_DOMAINS = (
    (7, (25,), 8, 4, layout.CANVAS_WIDTH_PIXELS),
    (7, (27, 28), 3, 1, layout.CANVAS_WIDTH_PIXELS),
    (7, (61,), 8, 4, layout.CANVAS_WIDTH_PIXELS),
    (7, (84,), 1, 1, layout.CANVAS_WIDTH_PIXELS),
)

# The title/save hub draws ten conditional rows directly from x=6. Choosing
# Start Adventure opens a narrower conditional menu whose rows begin at x=56.
# These surfaces bypass the ordinary full-width composer, so their real pixel
# budgets must be enforced separately for every translated build.
FRONT_END_HUB_GROUP = 7
FRONT_END_HUB_INDEX_RANGE = (67, 76)
FRONT_END_HUB_START_X = 6
# The dynamic hub box is eleven tiles wide. Its right border begins at x=80,
# so text starting at x=6 owns the 74-pixel interior to that exclusive edge.
FRONT_END_HUB_RIGHT_EDGE = 80
ADVENTURE_START_GROUP = 24
ADVENTURE_START_INDEX_RANGE = (50, 58)
ADVENTURE_START_START_X = 56
ADVENTURE_START_RIGHT_EDGE = layout.CANVAS_WIDTH_PIXELS

# The in-dungeon stairs overlay uses a fixed tilemap rather than the ordinary
# menu constructor. ``stairs_menu`` expands its interior from 40 to 56 pixels;
# these two direct-rendered labels must remain inside that engineered frame.
STAIRS_MENU_GROUP = stairs_menu.STAIRS_GROUP
STAIRS_MENU_INDICES = stairs_menu.STAIRS_INDICES
STAIRS_MENU_START_X = stairs_menu.TEXT_START_X
STAIRS_MENU_RIGHT_EDGE = stairs_menu.TEXT_RIGHT_EDGE

# Ordinary service-menu labels reserve their first interior tile for the
# cursor/indent.  ``service_menus`` widens only its two reviewed selectors to
# seven interior tiles, leaving 48 pixels for label glyphs after that indent.
SERVICE_MENU_GROUP = service_menus.SERVICE_GROUP
SERVICE_MENU_INDICES = tuple(sorted({
    index
    for _menu, indices, _labels in service_menus.SERVICE_LABEL_SETS
    for index in indices
}))
SERVICE_MENU_START_X = service_menus.TEXT_START_X
SERVICE_MENU_RIGHT_EDGE = service_menus.TEXT_RIGHT_EDGE


def _item_ability_positioned_contracts(rom):
    result = extract.extract(rom)
    by_reference = {
        (reference.group, reference.index): (record.bank, record.address)
        for record in result["records"]
        for reference in record.references
    }
    return {
        by_reference[(ITEM_ABILITY_DESCRIPTION_GROUP, index)]: (
            ITEM_ABILITY_DESCRIPTION_START_X,
            1,
            ITEM_ABILITY_DESCRIPTION_RIGHT_EDGE,
        )
        for index in range(ITEM_ABILITY_DESCRIPTION_ENTRIES)
    }


def _record_keys_by_reference(rom):
    result = extract.extract(rom)
    return {
        (reference.group, reference.index): (record.bank, record.address)
        for record in result["records"]
        for reference in record.references
    }


def _main_menu_positioned_contracts(rom):
    by_reference = _record_keys_by_reference(rom)
    left = {}
    for group, indices, start_x, start_y, right_edge in MAIN_MENU_LEFT_DOMAINS:
        for index in indices:
            left[by_reference[(group, index)]] = (
                start_x, start_y, right_edge
            )
    locations = {
        by_reference[(MAIN_MENU_LOCATION_GROUP, index)]: (
            MAIN_MENU_LOCATION_LEFT_EDGE,
            MAIN_MENU_LOCATION_ANCHOR,
            MAIN_MENU_LOCATION_Y,
        )
        for index in range(
            MAIN_MENU_LOCATION_RANGE[0], MAIN_MENU_LOCATION_RANGE[1] + 1
        )
    }
    return left, locations


def _item_action_positioned_contracts(rom):
    by_reference = _record_keys_by_reference(rom)
    return {
        by_reference[(ITEM_ACTION_GROUP, index)]: (
            ITEM_ACTION_START_X,
            17,
            ITEM_ACTION_RIGHT_EDGE,
        )
        for index in range(
            ITEM_ACTION_INDEX_RANGE[0], ITEM_ACTION_INDEX_RANGE[1] + 1
        )
    }


def _status_condition_positioned_contracts(rom):
    by_reference = _record_keys_by_reference(rom)
    contracts = {
        by_reference[(STATUS_CONDITION_GROUP, index)]: (
            STATUS_CONDITION_BODY_START_X,
            1,
            STATUS_CONDITION_BODY_RIGHT_EDGE,
        )
        for index in range(
            STATUS_CONDITION_INDEX_RANGE[0],
            STATUS_CONDITION_INDEX_RANGE[1] + 1,
        )
    }
    for group, indices, start_x, start_y, right_edge in (
        STATUS_CONDITION_UI_DOMAINS
    ):
        for index in indices:
            contracts[by_reference[(group, index)]] = (
                start_x,
                start_y,
                right_edge,
            )
    return contracts


def _front_end_positioned_contracts(rom):
    by_reference = _record_keys_by_reference(rom)
    contracts = {
        by_reference[(FRONT_END_HUB_GROUP, index)]: (
            FRONT_END_HUB_START_X,
            1,
            FRONT_END_HUB_RIGHT_EDGE,
        )
        for index in range(
            FRONT_END_HUB_INDEX_RANGE[0],
            FRONT_END_HUB_INDEX_RANGE[1] + 1,
        )
    }
    contracts.update(
        {
            by_reference[(ADVENTURE_START_GROUP, index)]: (
                ADVENTURE_START_START_X,
                3,
                ADVENTURE_START_RIGHT_EDGE,
            )
            for index in range(
                ADVENTURE_START_INDEX_RANGE[0],
                ADVENTURE_START_INDEX_RANGE[1] + 1,
            )
        }
    )
    return contracts


def _stairs_menu_positioned_contracts(rom):
    by_reference = _record_keys_by_reference(rom)
    return {
        by_reference[(STAIRS_MENU_GROUP, index)]: (
            STAIRS_MENU_START_X,
            1,
            STAIRS_MENU_RIGHT_EDGE,
        )
        for index in STAIRS_MENU_INDICES
    }


def _service_menu_positioned_contracts(rom):
    by_reference = _record_keys_by_reference(rom)
    return {
        by_reference[(SERVICE_MENU_GROUP, index)]: (
            SERVICE_MENU_START_X,
            1,
            SERVICE_MENU_RIGHT_EDGE,
        )
        for index in SERVICE_MENU_INDICES
    }


def build_rom(rom, record_overrides, runtime_contract=None):
    """Return ``(output, allocation, validation)`` for encoded record overrides."""
    rom = bytes(rom)
    overrides = {key: bytes(raw) for key, raw in record_overrides.items()}
    allocation = allocate.allocate(rom, record_overrides=overrides)
    relocated, _allocation = insert.write_relocated(rom, allocation)
    output = english_font.install(relocated)
    output = item_formatting.install(output)
    output = item_status.install(output)
    output = menu_graphics.install(output)
    output = stairs_menu.install(output)
    output = service_menus.install(output)
    output = dialogue_pacing.install(output)
    output = name6.install(output)
    output = blank_scroll.install(output)
    output = spell_input.install(output)
    output = unidentified_names.install(output)
    output = rescue_presentation.install(output)
    layout.validate_overrides(
        output, overrides, runtime_contract=runtime_contract
    )
    layout.validate_positioned_overrides(
        output, overrides, _item_ability_positioned_contracts(rom)
    )
    layout.validate_positioned_overrides(
        output, overrides, _item_action_positioned_contracts(rom)
    )
    layout.validate_positioned_overrides(
        output, overrides, _status_condition_positioned_contracts(rom)
    )
    layout.validate_positioned_overrides(
        output, overrides, _front_end_positioned_contracts(rom)
    )
    layout.validate_positioned_overrides(
        output, overrides, _stairs_menu_positioned_contracts(rom)
    )
    layout.validate_positioned_overrides(
        output, overrides, _service_menu_positioned_contracts(rom)
    )
    menu_left, menu_locations = _main_menu_positioned_contracts(rom)
    layout.validate_positioned_overrides(output, overrides, menu_left)
    layout.validate_right_aligned_positioned_overrides(
        output, overrides, menu_locations
    )
    validation = insert.validate_relocated(rom, output, allocation, overrides)
    return output, allocation, validation


def _validate_blank_scroll_catalog(extracted, translated):
    by_reference = {
        (reference.group, reference.index): record
        for record in extracted["records"]
        for reference in record.references
    }
    roots = {}
    for index in range(blank_scroll.ROOT_FIRST, blank_scroll.ROOT_LAST + 1):
        record = by_reference[(blank_scroll.ROOT_GROUP, index)]
        value = translated.get((record.bank, record.address))
        if value is None:
            raise blank_scroll.BlankScrollError(
                "Scroll root %d is not translated" % index
            )
        roots[index] = value.text
    blank_scroll.validate_root_catalog(roots)


def _validate_unidentified_name_catalog(extracted, translated):
    by_reference = {
        (reference.group, reference.index): record
        for record in extracted["records"]
        for reference in record.references
    }
    roots = {}
    for index in range(unidentified_names.ROOT_ENTRIES):
        record = by_reference[(unidentified_names.ROOT_GROUP, index)]
        value = translated.get((record.bank, record.address))
        if value is None:
            raise unidentified_names.UnidentifiedNameError(
                "item root %d is not translated" % index
            )
        roots[index] = value.text
    unidentified_names.validate_root_catalog(roots)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="original Shiren GB2 Japanese ROM")
    parser.add_argument(
        "translations",
        help="full/compact English TSV or category directory",
    )
    parser.add_argument("output", help="output translated development ROM")
    args = parser.parse_args(argv)
    source = Path(args.rom).read_bytes()
    try:
        extracted = extract.extract(source)
        translated = translation_file.load_path(
            args.translations, extracted["records"]
        )
        if not translated:
            raise translation_file.TranslationError(
                "%s contains no nonblank English overrides" % args.translations
            )
        exceptions = lint_en.load_exceptions(
            lint_en.default_exceptions_path(args.translations), extracted
        )
        lint_summary = lint_en.require_clean(extracted, translated, exceptions)
        width_analysis = runtime_widths.analyze(
            english_font.install(source), extracted, translated
        )
        overrides = translation_file.encoded_overrides(translated)
        output, allocation, validation = build_rom(
            source, overrides, runtime_contract=width_analysis.contract
        )
        _validate_blank_scroll_catalog(extracted, translated)
        _validate_unidentified_name_catalog(extracted, translated)
    except (
        OSError,
        allocate.AllocationError,
        blank_scroll.BlankScrollError,
        dialogue_pacing.DialoguePacingError,
        english_font.FontError,
        extract.ExtractError,
        insert.InsertError,
        item_formatting.ItemFormattingError,
        layout.LayoutError,
        lint_en.TranslationLintError,
        menu_graphics.MenuGraphicsError,
        name6.Name6Error,
        runtime_widths.RuntimeWidthError,
        spell_input.SpellInputError,
        unidentified_names.UnidentifiedNameError,
        stairs_menu.StairsMenuError,
        translation_file.TranslationError,
    ) as exc:
        parser.exit(1, "error: %s\n" % exc)

    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(output)
    print(
        "%d translated record(s) / %d logical reference(s)"
        % (len(translated), validation["overridden_references"])
    )
    print(
        "lint         : %d glossary definition(s), %d reviewed exception(s)"
        % (
            lint_summary["translated_glossary_records"],
            lint_summary["reviewed_exceptions"],
        )
    )
    print(
        "%d total references verified; %d bank(s) written"
        % (validation["exact_references"], validation["written_banks"])
    )
    print("script bytes : %d" % allocation.summary["payload_bytes"])
    print(
        "checksums    : header $%s global $%s"
        % (validation["header_checksum"], validation["global_checksum"])
    )
    print("sha1         : %s" % sha1(output).hexdigest())
    print("output       : %s" % destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
