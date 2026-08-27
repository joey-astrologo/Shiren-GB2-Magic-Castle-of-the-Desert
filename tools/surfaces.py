#!/usr/bin/env python3
"""Inventory GB2's direct, caller-positioned text path.

The ordinary source composer and the positioned drawer are different APIs.
``0:$1FA0`` copies a group/index record, including its FF terminator, to a
caller buffer.  The common bank-17 wrappers then set x/y and call ``3:$5E62``.
This module freezes that call graph directly from machine code and exposes the
first observed visual-width contract used by translation validation.
"""
import argparse
from dataclasses import dataclass
from hashlib import sha1
import json
from pathlib import Path
import sys

import codec
import extract
import layout


DIRECT_SELECTOR = (0, 0x1FA0)
DIRECT_RENDERER = (3, 0x5E62)
SELECTOR_COPY_SPAN = 0x49

# Bank 17 centralizes the reusable direct-drawing APIs.  Entries that format
# numbers build C800 themselves; record/list entries ultimately use 0:$1FA0.
POSITIONED_WRAPPERS = {
    0x4067: "draw_buffer_mode08",
    0x407D: "draw_record_mode08",
    0x408E: "draw_record",
    0x40A7: "draw_group07_list",
    0x40B9: "draw_record_right_aligned",
    0x410D: "draw_unsigned_right_aligned",
    0x4130: "draw_digit_mapped_right_aligned",
    0x4164: "draw_signed_right_aligned",
}


# Every presently known consumer of the positioned-text API has now been
# assigned to either a reusable implementation layer or a screen family whose
# geometry/domain is frozen below.  Keep this independent of ``call_graph``:
# the comparison in ``call_graph_coverage`` is deliberately fail-closed, so a
# newly discovered machine-code caller cannot inherit a guessed owner.
POSITIONED_CALL_SITE_OWNERS = {
    "direct_renderer": (
        (
            "wrapper_implementations",
            (
                "17:$4072", "17:$40A0", "17:$40D6", "17:$4106",
                "17:$4129", "17:$415D", "17:$41A9",
            ),
        ),
        (
            "history_and_ranking",
            (
                "3:$63A6", "3:$6430", "3:$64CB", "3:$64F0", "3:$65C6",
                "17:$45AF", "17:$4EFE", "17:$50A5", "17:$56D8",
                "17:$5713", "17:$5768",
            ),
        ),
        ("remaining_hub_routes", ("17:$46AB", "17:$7598")),
        ("record_picker_and_graphical_input", ("17:$5124",)),
        ("seeded_item_list", ("17:$54BF", "17:$551A", "17:$71B0")),
    ),
    "draw_buffer_mode08": (
        (
            "shared_heading_canvases",
            (
                "17:$450F", "17:$454D", "17:$4580", "17:$45DE",
                "17:$4629", "17:$4684",
            ),
        ),
    ),
    "draw_record_mode08": (
        ("seeded_item_list", ("17:$4650",)),
    ),
    "draw_record": (
        ("wrapper_implementations", ("17:$4086", "17:$40AB")),
        (
            "static_record_uses",
            (
                "17:$493E", "17:$49D4", "17:$5061", "17:$5194",
                "17:$5644", "17:$5783", "17:$57B5", "17:$6AEC",
                "17:$6B16", "17:$6EE5",
            ),
        ),
        ("status_condition_screen", ("17:$49F6",)),
        ("history_and_ranking", ("17:$4C8D",)),
        ("record_picker_and_graphical_input", ("17:$5164",)),
        ("dynamic_list_families", ("17:$5213", "17:$525B", "17:$52A3")),
        ("at_feet", ("17:$55C5",)),
        ("diary_management", ("17:$567A",)),
        ("remaining_hub_routes", ("17:$5871", "17:$58B3")),
        ("main_menu_contract", ("17:$6B21",)),
        ("seeded_item_list", ("17:$748A",)),
        (
            "dungeon_selectors",
            (
                "3:$5FFA", "3:$600B", "3:$601C", "3:$602D",
                "3:$604E", "3:$6064", "3:$608A",
            ),
        ),
        (
            "history_and_ranking",
            (
                "3:$60AE", "3:$60BD", "3:$60CC", "3:$6157",
                "3:$621F", "3:$622E", "3:$623D", "3:$62B3",
                "3:$62D2", "3:$62F1", "3:$6300", "3:$63B2",
                "3:$63E3", "3:$6453", "3:$6471", "3:$6498",
                "3:$651E", "3:$653C", "3:$6584", "3:$662D",
                "3:$67CF", "3:$6A32",
            ),
        ),
        ("adventure_start_menu", ("4:$72E9",)),
    ),
    "draw_group07_list": (
        ("remaining_hub_routes", ("17:$583D", "17:$5921")),
    ),
    "draw_record_right_aligned": (
        ("history_and_ranking", ("17:$5738",)),
        ("main_menu_contract", ("17:$6ABD",)),
    ),
    "draw_unsigned_right_aligned": (
        ("seeded_item_list", ("17:$4646",)),
        ("at_feet", ("17:$563A",)),
        ("history_and_ranking", ("17:$57AB",)),
        (
            "main_menu_numeric_status",
            (
                "17:$6A40", "17:$6A4E", "17:$6A62", "17:$6A6E",
                "17:$6A82", "17:$6A8E", "17:$6AAC", "17:$6ADA",
            ),
        ),
        (
            "history_and_ranking",
            (
                "3:$60E7", "3:$6106", "3:$6125", "3:$6258",
                "3:$6277", "3:$6296", "3:$6325", "3:$63D4",
                "3:$6405", "3:$6512",
            ),
        ),
    ),
    "draw_digit_mapped_right_aligned": (
        ("item_formatter_numeric_fragments", ("17:$53E3", "17:$540D")),
    ),
    "draw_signed_right_aligned": (
        (
            "seeded_item_list",
            (
                "17:$4DD3", "17:$4DE4", "17:$4DF5", "17:$4E17",
                "17:$4E29", "17:$4E3A", "17:$4E4C", "17:$4E5D",
            ),
        ),
    ),
}


@dataclass(frozen=True)
class PositionedSurface:
    name: str
    group: int
    index: int
    start_x: int
    start_y: int
    right_edge: int
    observed_mode: int
    observed_frame: int

    @property
    def available_pixels(self):
        return self.right_edge - self.start_x


@dataclass(frozen=True)
class StaticRecordUse:
    """A draw_record call whose group, index and x/y are statically constant."""

    call_site: int
    evidence_address: int
    evidence: bytes
    group: int
    index: int
    start_x: int
    start_y: int


@dataclass(frozen=True)
class DynamicListFamily:
    """A paged direct-record list with a finite group/index domain."""

    name: str
    group: int
    start_index: int
    end_index: int
    page_rows: int
    constructor_address: int
    caller_bank: int
    caller_address: int
    heading_group: int
    heading_index: int


@dataclass(frozen=True)
class PositionedRecordDomain:
    """All branch-selected records that can occupy one fixed menu slot."""

    name: str
    group: int
    indices: tuple
    start_x: int
    start_y: int
    right_edge: int


@dataclass(frozen=True)
class RemappedMenuStrip:
    """A canvas strip that a tilemap places into a visible menu column."""

    name: str
    canvas_left: int
    canvas_right: int
    text_start_x: int
    references: tuple
    visible_row: int


@dataclass(frozen=True)
class MainMenuNumericField:
    """One unsigned decimal value drawn into the main-menu status canvas."""

    name: str
    call_site: int
    value_source: str
    anchor_x: int
    anchor_y: int
    maximum: int
    maximum_basis: str
    left_obstruction_right: int
    observed_value: int
    observed_start_x: int
    observed_frame: int


@dataclass(frozen=True)
class ItemCategorySeed:
    """One deterministic inventory object and its observed formatted row."""

    category: str
    category_index: int
    item_index: int
    action_class: int
    object_index: int
    runtime_raw: bytes
    observed_frame: int

    @property
    def object_record(self):
        return bytes((self.item_index, self.action_class, 0, 0, 0, 0, 0, 0))


# This is the first high-confidence subset of draw_record consumers.  Each row
# is backed by the exact machine-code load sequence checked by the fixture.
# Dynamic lists and branch-selected records remain in the complete call graph
# above rather than being assigned guessed coordinates.
STATIC_RECORD_USES = (
    StaticRecordUse(0x493E, 0x4937, bytes.fromhex("110301011B07E5CD8E40"), 7, 27, 3, 1),
    StaticRecordUse(0x49D4, 0x49CE, bytes.fromhex("110101015407CD8E40"), 7, 84, 1, 1),
    StaticRecordUse(0x5061, 0x505B, bytes.fromhex("011C07110301CD8E40"), 7, 28, 3, 1),
    StaticRecordUse(0x5194, 0x518E, bytes.fromhex("01481611010CCD8E40"), 22, 72, 1, 12),
    StaticRecordUse(0x5644, 0x563D, bytes.fromhex("113020013107E5CD8E40"), 7, 49, 48, 32),
    StaticRecordUse(0x5783, 0x577C, bytes.fromhex("1E22163E013118CD8E40"), 24, 49, 34, 62),
    StaticRecordUse(0x57B5, 0x57AE, bytes.fromhex("1E77163E015307CD8E40"), 7, 83, 119, 62),
    StaticRecordUse(0x6AEC, 0x6AE6, bytes.fromhex("012307110300CD8E40"), 7, 35, 3, 0),
    StaticRecordUse(0x6B16, 0x6B10, bytes.fromhex("013F07110300CD8E40"), 7, 63, 3, 0),
    StaticRecordUse(0x6EE5, 0x6EDE, bytes.fromhex("16111E08010C07CD8E40"), 7, 12, 8, 17),
)


# The top-left new-game menu is deterministic on a clean boot.  Its inner
# background occupies x=3..84; x=85 is therefore the exclusive pen edge.
OPENING_MENU_SURFACES = (
    PositionedSurface(
        name="new_game_create_log",
        group=7,
        index=68,
        start_x=6,
        start_y=1,
        right_edge=85,
        observed_mode=0x04,
        observed_frame=580,
    ),
    PositionedSurface(
        name="new_game_wanderers_guide",
        group=7,
        index=73,
        start_x=6,
        start_y=12,
        right_edge=85,
        observed_mode=0x04,
        observed_frame=580,
    ),
)


# Selecting the second clean-boot menu entry opens the first Wanderer's Guide
# page without needing a battery save.  The heading is drawn into its own
# mode-08 layer, followed by the ten group-19 topic rows.  Topic 10 lands one
# frame later than the otherwise consecutive draws on the reference ROM.
GUIDE_MENU_SURFACES = (
    PositionedSurface(
        name="wanderers_guide_heading",
        group=7,
        index=73,
        start_x=8,
        start_y=4,
        right_edge=layout.CANVAS_WIDTH_PIXELS,
        observed_mode=0x08,
        observed_frame=646,
    ),
) + tuple(
    PositionedSurface(
        name="wanderers_guide_topic_%02d" % (index + 1),
        group=19,
        index=index,
        start_x=3,
        start_y=1 + 11 * index,
        right_edge=layout.CANVAS_WIDTH_PIXELS,
        observed_mode=0x08,
        observed_frame=647 + index + (1 if index == 9 else 0),
    )
    for index in range(10)
)


CONTROL_HELP_SURFACES = (
    PositionedSurface(
        name="control_help_heading",
        group=7,
        index=117,
        start_x=8,
        start_y=4,
        right_edge=layout.CANVAS_WIDTH_PIXELS,
        observed_mode=0x08,
        observed_frame=345,
    ),
) + tuple(
    PositionedSurface(
        name="control_help_topic_%02d" % (index + 1),
        group=20,
        index=index,
        start_x=3,
        start_y=1 + 11 * index,
        right_edge=layout.CANVAS_WIDTH_PIXELS,
        observed_mode=0x08,
        observed_frame=(346, 347, 348, 349, 349, 350, 351, 352, 353)[index],
    )
    for index in range(9)
)


TECHNIQUE_HELP_SURFACES = (
    PositionedSurface(
        name="technique_help_heading",
        group=7,
        index=114,
        start_x=8,
        start_y=4,
        right_edge=layout.CANVAS_WIDTH_PIXELS,
        observed_mode=0x08,
        observed_frame=345,
    ),
) + tuple(
    PositionedSurface(
        name="technique_help_topic_%02d" % (index + 1),
        group=21,
        index=index,
        start_x=3,
        start_y=1 + 11 * index,
        right_edge=layout.CANVAS_WIDTH_PIXELS,
        observed_mode=0x08,
        observed_frame=(346, 347, 348, 349, 350, 351, 352, 353, 354, 354)[index],
    )
    for index in range(10)
)


# A fresh-game main menu proves the ordinary branch.  The disassembly at
# 17:$6AE1-$6B23 supplies the complete finite domains for both left-column
# slots, including the transformed-state alternatives that are not reachable
# on this clean route.  Pixel x=53 is the exclusive interior edge.
MAIN_MENU_SURFACES = (
    PositionedSurface(
        name="main_menu_primary_action",
        group=7,
        index=35,
        start_x=3,
        start_y=0,
        right_edge=53,
        observed_mode=0x08,
        observed_frame=15,
    ),
    PositionedSurface(
        name="main_menu_context_action",
        group=7,
        index=36,
        start_x=3,
        start_y=12,
        right_edge=53,
        observed_mode=0x08,
        observed_frame=16,
    ),
)


MAIN_MENU_LEFT_SLOT_DOMAINS = (
    PositionedRecordDomain("primary_action", 7, (35, 63), 3, 0, 53),
    PositionedRecordDomain("context_action", 7, (36, 39, 56, 64), 3, 12, 53),
)

MAIN_MENU_SELECTOR_ADDRESS = 0x6AE1
MAIN_MENU_SELECTOR_SPAN = 0x43
MAIN_MENU_LOCATION_SELECTOR_ADDRESS = 0x6AAF
MAIN_MENU_LOCATION_SELECTOR_SPAN = 0x11
ALIGNMENT_ROUTINE = (3, 0x6DDC)
ALIGNMENT_ROUTINE_SPAN = 0x36
MAIN_MENU_LOCATION_GROUP = 24
MAIN_MENU_LOCATION_RANGE = (19, 48)
MAIN_MENU_LOCATION_LEFT_EDGE = 59
MAIN_MENU_LOCATION_ANCHOR = 142
MAIN_MENU_LOCATION_Y = 24


# ``17:$6A2C`` builds every dynamic value in the main menu's right/bottom
# status panels.  Each value is zero-extended into the four-byte C800 input,
# formatted by 17:$41B0, and right-aligned by 3:$6E07.  The left obstruction
# is the rightmost fixed-label or separator pixel in the untouched menu
# template; a value must begin strictly to its right.
MAIN_MENU_NUMERIC_FIELDS = (
    MainMenuNumericField(
        "weapon_total", 0x6A40, "120:$4740 C", 36, 77, 0xFF,
        "saturating unsigned 8-bit equipment total", 14, 0, 29, 12
    ),
    MainMenuNumericField(
        "shield_total", 0x6A4E, "120:$4740 B", 36, 88, 0xFF,
        "saturating unsigned 8-bit equipment total", 13, 0, 29, 13
    ),
    MainMenuNumericField(
        "strength_max", 0x6A62, "126:$5176 C", 135, 77, 0xFF,
        "base stat plus unsigned modifier, saturated to $FF", 112, 8, 128, 13
    ),
    MainMenuNumericField(
        "strength_current", 0x6A6E, "126:$5176 B", 106, 77, 0xFF,
        "base stat plus unsigned modifier, saturated to $FF", 60, 8, 99, 13
    ),
    MainMenuNumericField(
        "fullness_current", 0x6A82, "7:$5641 B", 106, 88, 200,
        "current fullness is clamped to the $C8 maximum", 77, 100, 87, 13
    ),
    MainMenuNumericField(
        "fullness_max", 0x6A8E, "7:$5641 C", 135, 88, 200,
        "maximum-fullness growth is capped at $C8", 112, 100, 116, 14
    ),
    MainMenuNumericField(
        "money", 0x6AAC, "7:$5674", 135, 99, 999999,
        "addition clamps to little-endian $000F423F", 24, 0, 128, 14
    ),
    MainMenuNumericField(
        "experience", 0x6ADA, "126:$538D", 144, 1, 0xFFFFFF,
        "zero-extended unsigned 24-bit experience store", 87, 0, 137, 15
    ),
)

MAIN_MENU_NUMERIC_CONSTRUCTOR = (17, 0x6A2C)
MAIN_MENU_NUMERIC_CONSTRUCTOR_SPAN = 0xB1
UNSIGNED_NUMERIC_WRAPPER = (17, 0x410D)
UNSIGNED_NUMERIC_WRAPPER_SPAN = 0x23
UNSIGNED_DECIMAL_FORMATTER = (17, 0x41B0)
UNSIGNED_DECIMAL_FORMATTER_SPAN = 0x84
MAIN_MENU_CANVAS_UPLOAD = (17, 0x6B24)
MAIN_MENU_CANVAS_UPLOAD_SPAN = 0x13
MAIN_MENU_CANVAS_TILE_BASE = 0x80
MAIN_MENU_TILEMAP_BASE = 0x9800
MAIN_MENU_RIGHT_TILEMAP_TOP_LEFT = (8, 2)
MAIN_MENU_RIGHT_TILEMAP_ROWS = tuple(
    tuple(
        (MAIN_MENU_CANVAS_TILE_BASE + canvas_row * layout.CANVAS_TILE_COLUMNS + column)
        & 0xFF
        for column in range(7, 18)
    )
    for canvas_row in range(5)
)
MAIN_MENU_BOTTOM_TILEMAP_TOP_LEFT = (1, 13)
MAIN_MENU_BOTTOM_TILEMAP_ROWS = tuple(
    tuple(
        (MAIN_MENU_CANVAS_TILE_BASE + canvas_row * layout.CANVAS_TILE_COLUMNS + column)
        & 0xFF
        for column in range(18)
    )
    for canvas_row in range(9, 14)
)

WEAPON_TOTAL_EVIDENCE = (120, 0x4740, 0x4B)
STRENGTH_TOTAL_EVIDENCE = (126, 0x5169, 0x2A)
FULLNESS_CAP_EVIDENCE = (7, 0x541E, 0x2F)
MONEY_CAP_EVIDENCE = (7, 0x5674, 0x69)
EXPERIENCE_GETTER_EVIDENCE = (126, 0x538D, 0x14)
EXPERIENCE_TABLE = (126, 0x7B33)


# The in-game Help selector is drawn into two separate six-tile canvas strips
# by 3:$67A6, then its tilemap places the strips one below the other.  Each
# strip includes eight pixels of left padding, leaving 40 pixels from the
# observed text start to the exclusive source-strip edge.
HELP_POPUP_SURFACES = (
    PositionedSurface(
        name="help_popup_controls",
        group=7,
        index=113,
        start_x=16,
        start_y=1,
        right_edge=56,
        observed_mode=0x08,
        observed_frame=203,
    ),
    PositionedSurface(
        name="help_popup_techniques",
        group=7,
        index=114,
        start_x=16,
        start_y=13,
        right_edge=56,
        observed_mode=0x08,
        observed_frame=202,
    ),
    PositionedSurface(
        name="help_popup_secret_arts",
        group=7,
        index=115,
        start_x=64,
        start_y=2,
        right_edge=104,
        observed_mode=0x08,
        observed_frame=202,
    ),
    PositionedSurface(
        name="help_popup_status",
        group=7,
        index=53,
        start_x=64,
        start_y=14,
        right_edge=104,
        observed_mode=0x08,
        observed_frame=202,
    ),
)

HELP_POPUP_STRIPS = (
    RemappedMenuStrip(
        "controls_and_techniques", 8, 56, 16, ((7, 113), (7, 114)), 5
    ),
    RemappedMenuStrip(
        "secret_arts_and_status", 56, 104, 64, ((7, 115), (7, 53)), 8
    ),
)
HELP_POPUP_CONSTRUCTOR = (3, 0x67A6)
HELP_POPUP_CONSTRUCTOR_SPAN = 0x47
HELP_POPUP_COORDINATE_TABLE = (3, 0x67ED)
HELP_POPUP_COORDINATE_TABLE_SPAN = 8
HELP_POPUP_TILE_BASE = 0x24
HELP_POPUP_TILEMAP_BASE = 0x9800
HELP_POPUP_TILEMAP_TOP_LEFT = (3, 4)
HELP_POPUP_TILEMAP_ROWS = (
    (0x7C, 0x7E, 0x7E, 0x7E, 0x7E, 0x7E, 0x7E, 0x7C),
    (0x7D, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x7D),
    (0x7D, 0x37, 0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x7D),
    (0x7D, 0x49, 0x4A, 0x4B, 0x4C, 0x4D, 0x4E, 0x7D),
    (0x7D, 0x2B, 0x2C, 0x2D, 0x2E, 0x2F, 0x30, 0x7D),
    (0x7D, 0x3D, 0x3E, 0x3F, 0x40, 0x41, 0x42, 0x7D),
    (0x7D, 0x4F, 0x50, 0x51, 0x52, 0x53, 0x54, 0x7D),
    (0x7C, 0x7E, 0x7E, 0x7E, 0x7E, 0x7E, 0x7E, 0x7C),
)


# Help -> Status has a separate two-layer layout.  The 18-column heading
# canvas occupies the top two screen rows.  The condition body is a 18x14
# canvas inside a full-width border and uses the signed tile-number sequence
# $80..$FF,$00..$7B.  On an unaffected player the body draws group 7 index 84;
# otherwise 17:$4AB8 selects group-28 labels from the finite table at $4AEE.
STATUS_CONDITION_SURFACES = (
    PositionedSurface(
        name="status_condition_heading",
        group=7,
        index=25,
        start_x=8,
        start_y=4,
        right_edge=layout.CANVAS_WIDTH_PIXELS,
        observed_mode=0x08,
        observed_frame=372,
    ),
    PositionedSurface(
        name="status_condition_healthy",
        group=7,
        index=84,
        start_x=1,
        start_y=1,
        right_edge=layout.CANVAS_WIDTH_PIXELS,
        observed_mode=0x08,
        observed_frame=374,
    ),
)
STATUS_CONDITION_GROUP = 28
STATUS_CONDITION_PAGE_ROWS = 10
STATUS_CONDITION_EFFECT_RANGE = (0, 58)
STATUS_HEADING_CONSTRUCTOR = (17, 0x44F0)
STATUS_HEADING_CONSTRUCTOR_SPAN = 0x33
STATUS_BODY_CONSTRUCTOR = (17, 0x49B5)
STATUS_BODY_CONSTRUCTOR_SPAN = 0x5A
STATUS_ACTIVE_TEST = (17, 0x4A0F)
STATUS_ACTIVE_TEST_SPAN = 0x88
STATUS_ACTIVE_COUNT = (17, 0x4A97)
STATUS_ACTIVE_COUNT_SPAN = 0x12
STATUS_CONDITION_SELECTOR = (17, 0x4AB8)
STATUS_CONDITION_SELECTOR_SPAN = 0x36
STATUS_CONDITION_POINTER_TABLE = (17, 0x4AEE)
STATUS_CONDITION_POINTER_TABLE_SPAN = 0x62
STATUS_CONDITION_MAPPING_BLOB = (17, 0x4B50)
STATUS_CONDITION_MAPPING_BLOB_SPAN = 0x97
STATUS_CONDITION_CALLER = (4, 0x43C1)
STATUS_CONDITION_CALLER_SPAN = 0x22
STATUS_TILEMAP_BASE = 0x9800
STATUS_TILEMAP_TOP_LEFT = (0, 0)
STATUS_TILEMAP_ROWS = (
    (0x7F,) + tuple(range(0x00, 0x12)) + (0x7F,),
    (0x7F,) + tuple(range(0x12, 0x24)) + (0x7F,),
    (0x7C,) + (0x7E,) * 18 + (0x7C,),
) + tuple(
    (0x7D,)
    + tuple((0x80 + row * 18 + column) & 0xFF for column in range(18))
    + (0x7D,)
    for row in range(14)
) + (
    (0x7C,) + (0x7E,) * 18 + (0x7C,),
)


# The training-dungeon and story-travel selectors share one full-screen body
# constructor.  Bank 4 selects the heading from group 7, then bank 3 draws a
# finite group-24 location domain at x=3 on 11-pixel rows.  A clean gameplay
# state has no optional training destinations unlocked, while the travel
# branch always exposes indices 3-6 and conditionally exposes index 7.
DUNGEON_SELECTOR_ENTRY = (4, 0x4687)
DUNGEON_SELECTOR_ENTRY_SPAN = 0x69
DUNGEON_SELECTOR_BODY_CONSTRUCTOR = (3, 0x5FDB)
DUNGEON_SELECTOR_BODY_CONSTRUCTOR_SPAN = 0xCB
DUNGEON_SELECTOR_GROUP = 24
DUNGEON_SELECTOR_ROW_START = (3, 1)
DUNGEON_SELECTOR_ROW_RIGHT_EDGE = layout.CANVAS_WIDTH_PIXELS
DUNGEON_SELECTOR_ROW_STEP = 11
DUNGEON_SELECTOR_TRAINING_INDICES = (0,) + tuple(range(3, 12))
DUNGEON_SELECTOR_TRAVEL_INDICES = (3, 4, 5, 6, 7)
DUNGEON_SELECTOR_TRAINING_SURFACES = (
    PositionedSurface(
        name="training_dungeon_selector_heading",
        group=7,
        index=131,
        start_x=8,
        start_y=4,
        right_edge=layout.CANVAS_WIDTH_PIXELS,
        observed_mode=0x08,
        observed_frame=0,
    ),
    PositionedSurface(
        name="training_dungeon_selector_previous",
        group=24,
        index=0,
        start_x=3,
        start_y=1,
        right_edge=layout.CANVAS_WIDTH_PIXELS,
        observed_mode=0x08,
        observed_frame=2,
    ),
)
DUNGEON_SELECTOR_TRAVEL_SURFACES = (
    PositionedSurface(
        name="travel_destination_selector_heading",
        group=7,
        index=132,
        start_x=8,
        start_y=4,
        right_edge=layout.CANVAS_WIDTH_PIXELS,
        observed_mode=0x08,
        observed_frame=0,
    ),
) + tuple(
    PositionedSurface(
        name="travel_destination_selector_%02d" % index,
        group=24,
        index=index,
        start_x=3,
        start_y=1 + DUNGEON_SELECTOR_ROW_STEP * row,
        right_edge=layout.CANVAS_WIDTH_PIXELS,
        observed_mode=0x08,
        observed_frame=2 + row,
    )
    for row, index in enumerate((3, 4, 5, 6))
)
DUNGEON_SELECTOR_SYNTHETIC_ROUTE = {
    "dispatcher": (0, 0x09AC),
    "target_bank": DUNGEON_SELECTOR_ENTRY[0],
    "target_address": DUNGEON_SELECTOR_ENTRY[1],
    "training_input_c": 0,
    "travel_input_c": 1,
    "tilemap_capture_frame": 10,
    "final_frame": 11,
}


# Adventure History is a forty-bit achievement ledger rendered ten rows at a
# time.  The adjacent Wanderer Ranking family has four views over one 32-byte
# record, plus a 133-byte memo/final-message companion.  These constants freeze
# the storage and constructor contracts before translation changes their text.
ADVENTURE_HISTORY_ENTRY = (4, 0x46F0)
ADVENTURE_HISTORY_ENTRY_SPAN = 0x6B
ADVENTURE_HISTORY_BODY = (17, 0x4E9A)
ADVENTURE_HISTORY_BODY_SPAN = 0x77
ADVENTURE_HISTORY_FLAG_SELECTOR = (11, 0x4CB0)
ADVENTURE_HISTORY_FLAG_SELECTOR_SPAN = 0x46
ADVENTURE_HISTORY_DYNAMIC_VALUES = (17, 0x4F11)
ADVENTURE_HISTORY_DYNAMIC_VALUES_SPAN = 0xEB
ADVENTURE_HISTORY_GROUP = 16
ADVENTURE_HISTORY_INDICES = tuple(range(40))
ADVENTURE_HISTORY_PAGE_ROWS = 10
ADVENTURE_HISTORY_FLAG_BASE = 0xC26A

RANKING_HEADING_REFERENCE = (7, 72)
RANKING_SCREEN_CONSTRUCTORS = {
    "current_record_list": ((4, 0x47ED), 0x26, (3, 0x612D), 0xB3),
    "paged_record_list": ((4, 0x4831), 0x4C, (3, 0x632D), 0x5E),
    "record_detail": ((4, 0x48B4), 0x40, (3, 0x65CA), 0x72),
    "final_message": ((4, 0x4924), 0x1C, (3, 0x663C), 0x36),
}
RANKING_RECORD_ADDRESS = 0xCF00
RANKING_RECORD_SIZE = 0x20
RANKING_EXTENDED_ADDRESS = 0xCF20
RANKING_EXTENDED_SIZE = 0x85
RANKING_MEMO_SIZE = 0x0D
RANKING_FINAL_MESSAGE_SIZE = 0x78
RANKING_LIST_MAX_RECORDS = 50
RANKING_PAGED_ROWS = 5
RANKING_LOCATION_INDICES = tuple(range(19, 47))
RANKING_OUTCOME_INDICES = tuple(range(41))
RANKING_TITLE_DOMAINS = {
    "wanderer": tuple(range(38, 49)),
    "trap": tuple(range(60, 71)),
    "cooking": tuple(range(49, 60)),
}
RANKING_FIXED_REFERENCES = (
    (7, 50),
    (7, 62),
) + tuple((18, index) for index in range(41, 62))
RANKING_SCHEMA = (
    ("sort_tiebreaker", 0x00, 2, "saved ordering key; not drawn"),
    ("elapsed_clock", 0x02, 4, "formatted clock on detail row 6"),
    ("turn_count", 0x06, 3, "unsigned detail value followed by group 18:55"),
    ("score", 0x09, 4, "unsigned list/detail value"),
    ("location", 0x0D, 1, "group 24 index 19 + value"),
    ("floor", 0x0E, 1, "unsigned value followed by group 7:50"),
    ("wanderer_name", 0x0F, 4, "fixed four-byte direct string"),
    ("outcome", 0x13, 1, "group 18 outcome/cause selector, low six bits"),
    ("outcome_argument", 0x14, 2, "runtime argument for the outcome string"),
    ("wanderer_title", 0x16, 1, "group 22 index 38 + value"),
    ("trap_title", 0x17, 1, "group 22 index 60 + value"),
    ("cooking_title", 0x18, 1, "group 22 index 49 + value"),
    ("rescues", 0x19, 2, "unsigned value followed by group 18:56 suffix"),
    ("maximum_hp", 0x1B, 1, "unsigned value following group 18:57"),
    ("level", 0x1C, 1, "unsigned value following group 18:46"),
    ("maximum_strength", 0x1D, 1, "unsigned value following group 18:58"),
    ("weapon", 0x1E, 1, "item id, FF selects group 18:59"),
    ("shield", 0x1F, 1, "item id, FF selects group 18:60"),
)
RANKING_NUMERIC_FIELDS = (
    ("rank", 1, 16, 1, RANKING_LIST_MAX_RECORDS),
    ("score", 4, 90, 1, 0xFFFFFFFF),
    ("floor", 1, 137, 1, 0xFF),
    ("level", 1, 139, 12, 0xFF),
    ("rescues", 2, None, 34, 0xFFFF),
    ("maximum_hp", 1, 90, 45, 0xFF),
    ("maximum_strength", 1, 142, 45, 0xFF),
    ("turn_count", 3, 118, 56, 0xFFFFFF),
)


def _ranking_seed_record():
    record = bytearray(RANKING_RECORD_SIZE)
    record[0:2] = (321).to_bytes(2, "little")
    record[2:6] = (372300).to_bytes(4, "little")
    record[6:9] = (54321).to_bytes(3, "little")
    record[9:13] = (1234567).to_bytes(4, "little")
    record[13:15] = bytes((16, 99))
    record[15:19] = codec.encode_source("シレン ")
    record[19:22] = bytes((0, 0, 0))
    record[22:25] = bytes((8, 7, 8))
    record[25:27] = (5).to_bytes(2, "little")
    record[27:30] = bytes((123, 42, 18))
    record[30:32] = bytes((0xFF, 0xFF))
    return bytes(record)


RANKING_SEEDED_RECORD = _ranking_seed_record()
RANKING_SEEDED_MEMO = (
    codec.encode_source("テストメモ")
    + codec.encode_source(" ") * 8
)
RANKING_SEEDED_FINAL_MESSAGE = codec.encode_source(
    "最後のメッセージです。"
)
RANKING_SYNTHETIC_ROUTE = {
    "dispatcher": (0, 0x09AC),
    "target_bank": 4,
    "entries": {
        "adventure_history": 0x46F0,
        "current_record_list": 0x475B,
        "paged_record_list": 0x4813,
        "record_detail": 0x487D,
        "final_message": 0x48F4,
    },
    "final_frame": 30,
}


# The two list constructors immediately following the ranking views are easy
# to conflate with the graphical editor which follows them in bank 4.  The
# first is the five-row ranking-record picker.  The second is the four-row
# Wanderer Grade category picker.  Both use the ordinary nine-way
# input dispatcher, but separate controllers.  Input mode 3 is the distinct
# four-byte graphical editor which reuses the keyboard screen already reached
# through Blank Scroll -> Write.
INPUT_INDEX_NAMES = (
    "none",
    "down",
    "up",
    "left",
    "right",
    "start",
    "select",
    "b",
    "a",
)
INPUT_INDEX_DECODER = (16, 0x42D9)
INPUT_INDEX_DECODER_SPAN = 0x18
JOYPAD_POLL = (1, 0x4609)
JOYPAD_POLL_SPAN = 0x3C
RANKING_RECORD_PICKER_ENTRY = (4, 0x4940)
RANKING_RECORD_PICKER_ENTRY_SPAN = 0x32
GRADE_CATEGORY_PICKER_ENTRY = (4, 0x4972)
GRADE_CATEGORY_PICKER_ENTRY_SPAN = 0x32
PICKER_CURSOR_RENDERER = (4, 0x77B0)
PICKER_CURSOR_RENDERER_SPAN = 0x2A
RANKING_RECORD_COUNT = (11, 0x55FE)
GRADE_CATEGORY_COUNT = (11, 0x4EB9)
RANKING_RECORD_PICKER_CONTROLLER = (16, 0x59F8)
RANKING_RECORD_PICKER_CONTROLLER_SPAN = 0x35
RANKING_RECORD_PICKER_DISPATCH = (16, 0x5A09)
GRADE_CATEGORY_PICKER_CONTROLLER = (16, 0x5A52)
GRADE_CATEGORY_PICKER_CONTROLLER_SPAN = 0x3F
GRADE_CATEGORY_PICKER_DISPATCH = (16, 0x5A63)

GRAPHICAL_INPUT_CALLER = (16, 0x7A10)
GRAPHICAL_INPUT_CALLER_SPAN = 0x73
GRAPHICAL_INPUT_ENTRY = (4, 0x4C94)
GRAPHICAL_INPUT_ENTRY_SPAN = 0x62
GRAPHICAL_INPUT_SCREEN = (4, 0x4CF6)
GRAPHICAL_INPUT_SCREEN_SPAN = 0x2F
GRAPHICAL_INPUT_CONTROLLER = (16, 0x5BCE)
GRAPHICAL_INPUT_CONTROLLER_SPAN = 0xD3
GRAPHICAL_INPUT_DISPATCH = (16, 0x5BDF)
GRAPHICAL_INPUT_MODE = 3
GRAPHICAL_INPUT_BUFFER_ADDRESS = 0xC16D
GRAPHICAL_INPUT_BUFFER_SIZE = 4
GRAPHICAL_INPUT_CHARACTER_TABLE = (18, 0x5310)
GRAPHICAL_INPUT_CHARACTER_CELLS = 49
GRAPHICAL_INPUT_NAVIGATION_TABLE = (16, 0x64B9)
GRAPHICAL_INPUT_NAVIGATION_NODES = 52
GRAPHICAL_INPUT_NAVIGATION_NODE_SIZE = 7
GRAPHICAL_INPUT_SPECIAL_CELLS = {
    "diacritic": 0x31,
    "backspace": 0x32,
    "confirm": 0x33,
}
GRAPHICAL_INPUT_TILEMAP_UPLOAD = (4, 0x49A4)
GRAPHICAL_INPUT_TILEMAP_UPLOAD_SPAN = 0x20
GRAPHICAL_INPUT_TILEMAP_SOURCE = (4, 0x49C4)
GRAPHICAL_INPUT_ATTRIBUTE_SOURCE = (4, 0x4B2C)
GRAPHICAL_INPUT_MAP_SIZE = 20 * 16
GRAPHICAL_INPUT_LENGTH_RESOLVER = (18, 0x502D)
GRAPHICAL_INPUT_LENGTH_RESOLVER_SPAN = 0x46
GRAPHICAL_INPUT_CHARACTER_INSERT = (18, 0x5359)
GRAPHICAL_INPUT_CHARACTER_INSERT_SPAN = 0x57
GRAPHICAL_INPUT_DIACRITIC = (18, 0x5517)
GRAPHICAL_INPUT_DIACRITIC_SPAN = 0x38
GRAPHICAL_INPUT_BACKSPACE = (18, 0x53B0)
GRAPHICAL_INPUT_BACKSPACE_SPAN = 0x5B
GRAPHICAL_INPUT_CONFIRM = (18, 0x50F7)
GRAPHICAL_INPUT_CONFIRM_SPAN = 0xBD
GRAPHICAL_INPUT_MODE_3_TILEMAP_ROWS = (
    (127, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 127),
    (127, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 127),
    (42,) * 20,
    (40,) + (42,) * 18 + (40,),
    (41,) + (36,) * 18 + (41,),
    (41, 36, 36, 36, 36, 36, 36, 56, 60, 36, 52, 91, 88, 36, 36, 36, 36, 36, 36, 41),
    (41,) + (36,) * 18 + (41,),
    (41,) + (36,) * 18 + (41,),
    (41, 36, 36, 36, 48, 49, 50, 51, 52, 36, 73, 74, 75, 76, 77, 36, 36, 36, 36, 41),
    (41,) + (36,) * 18 + (41,),
    (41, 36, 36, 36, 53, 54, 55, 56, 57, 36, 78, 79, 80, 81, 82, 36, 36, 36, 36, 41),
    (41,) + (36,) * 18 + (41,),
    (41, 36, 36, 36, 58, 59, 60, 61, 62, 36, 83, 36, 84, 36, 85, 36, 36, 36, 36, 41),
    (41,) + (36,) * 18 + (41,),
    (41, 36, 36, 36, 63, 64, 65, 66, 67, 36, 86, 87, 88, 89, 90, 36, 36, 36, 36, 41),
    (41,) + (36,) * 18 + (41,),
    (41, 36, 36, 36, 68, 69, 70, 71, 72, 36, 91, 92, 93, 36, 222, 36, 36, 36, 36, 41),
    (40,) + (42,) * 18 + (40,),
)


# The ten-entry front-end hub uses group-7 indices 67..76 in slot order.  Its
# predicates compact enabled labels vertically, while the selected *slot*
# still indexes the bank-16 dispatch table.  Three of those slots own diary
# management: Create and Rename share ordinary input mode 4; Delete uses the
# stock group-7 index-58 Yes/No prompt with No selected initially.
DIARY_HUB_ENTRY = (16, 0x7635)
DIARY_HUB_ENTRY_SPAN = 0xCB
DIARY_HUB_RENDERER = (17, 0x564E)
DIARY_HUB_RENDERER_SPAN = 0x50
DIARY_HUB_DISPATCH = (16, 0x7700)
DIARY_HUB_PREDICATE_DISPATCH = (11, 0x4FF3)
DIARY_HUB_LABEL_GROUP = 7
DIARY_HUB_LABEL_START = 67
DIARY_HUB_VISUAL_RIGHT_EDGE = 80
DIARY_HUB_LABEL_NAMES = (
    "start_adventure",
    "create_diary",
    "item_exchange",
    "delete_diary",
    "rename",
    "wanderer_ranking",
    "wanderers_secrets",
    "adventure_history",
    "wanderer_grade",
    "monster_notebook",
)
DIARY_CREATE_HANDLER = (16, 0x7847)
DIARY_CREATE_HANDLER_SPAN = 0x24
DIARY_DELETE_HANDLER = (16, 0x786B)
DIARY_DELETE_HANDLER_SPAN = 0x28
DIARY_RENAME_HANDLER = (16, 0x78C7)
DIARY_RENAME_HANDLER_SPAN = 0x1B
DIARY_DELETE_PRELUDE = (18, 0x4355)
DIARY_DELETE_PRELUDE_SPAN = 0x19
DIARY_DELETE_CONFIRMATION = (16, 0x527F)
DIARY_DELETE_CONFIRMATION_SPAN = 0x27
DIARY_DELETE_MUTATION = (11, 0x49D2)
DIARY_DELETE_MUTATION_SPAN = 0x1B
DIARY_SAVE = (11, 0x45E3)
DIARY_SAVE_SPAN = 0x28
DIARY_DELETE_PROMPT_REFERENCE = (7, 58)

# Choosing Start Adventure from the front-end hub opens a second, state-aware
# menu.  Nine group-24 records are keyed by their original slot; bank 11 tests
# each slot and bank 4 compacts only the enabled records into consecutive
# 11-pixel rows.  The maximum real shape excludes slot 0 and enables slots
# 1..8.  A separate ordinal mapper converts the compact cursor position back
# to the original slot before the bank-16 handler table is dispatched.
ADVENTURE_START_HANDLER = (16, 0x7714)
ADVENTURE_START_HANDLER_SPAN = 0x6A
ADVENTURE_START_SCREEN = (18, 0x436E)
ADVENTURE_START_SCREEN_SPAN = 0x30
ADVENTURE_START_HEADER = (4, 0x727D)
ADVENTURE_START_HEADER_SPAN = 0x22
ADVENTURE_START_BODY = (4, 0x72C3)
ADVENTURE_START_BODY_SPAN = 0x55
ADVENTURE_START_TILEMAP = (4, 0x7323)
ADVENTURE_START_TILEMAP_SPAN = 0x29
ADVENTURE_START_PREDICATE = (11, 0x50BB)
ADVENTURE_START_PREDICATE_SPAN = 0xA5
ADVENTURE_START_ORDINAL_MAPPER = (11, 0x5160)
ADVENTURE_START_ORDINAL_MAPPER_SPAN = 0x15
ADVENTURE_START_ENABLED_COUNT = (11, 0x5175)
ADVENTURE_START_ENABLED_COUNT_SPAN = 0x14
ADVENTURE_START_HANDLER_TABLE = (16, 0x777E)
ADVENTURE_START_HANDLER_TABLE_SPAN = 0x12
ADVENTURE_START_GROUP = 24
ADVENTURE_START_INDICES = tuple(range(50, 59))
ADVENTURE_START_SLOT_NAMES = (
    "start_from_beginning",
    "revive",
    "sos",
    "give_up",
    "continue",
    "wanderer_secret",
    "reset",
    "reminiscence",
    "thank_you_spell",
)
ADVENTURE_START_HANDLER_TARGETS = (
    0x7790,
    0x7793,
    0x77BD,
    0x77E9,
    0x77FA,
    0x77FF,
    0x7808,
    0x7832,
    0x7837,
)
ADVENTURE_START_ROW_START = (56, 3)
ADVENTURE_START_ROW_STEP = 11
ADVENTURE_START_CANVAS_RIGHT_EDGE = layout.CANVAS_WIDTH_PIXELS
ADVENTURE_START_TILEMAP_TOP_LEFT = (6, 1)
ADVENTURE_START_TILEMAP_WIDTH = 14
ADVENTURE_START_MAXIMUM_ENABLED = tuple(range(1, 9))
ADVENTURE_START_SPARSE_PROBE = (0, 3, 8)
ADVENTURE_START_VARIANT_FRAMES = {
    "maximum": (0, 1, 2, 2, 3, 4, 4, 5),
    "sparse": (0, 0, 1),
}

# The four remaining front-end hub slots are separate surface families.  Item
# Exchange is a two-row local menu followed by a link-cable protocol; Secrets
# is a ten-row event launcher; Grade compacts four enabled achievement
# categories; Monster Notebook is a graphical 27-cell page whose text comes
# from the actor-name domain, group-29 descriptions and one page counter.
ITEM_EXCHANGE_HANDLER = (16, 0x7893)
ITEM_EXCHANGE_HANDLER_SPAN = 0x34
ITEM_EXCHANGE_MENU_ENTRY = (18, 0x43F6)
ITEM_EXCHANGE_MENU_ENTRY_SPAN = 0x38
ITEM_EXCHANGE_CONTROLLER = (16, 0x457A)
ITEM_EXCHANGE_CONTROLLER_SPAN = 0x3B
ITEM_EXCHANGE_GIVE_ENTRY = (11, 0x6E2F)
ITEM_EXCHANGE_RECEIVE_ENTRY = (11, 0x6FB1)
ITEM_EXCHANGE_STORAGE_USED = (4, 0x4F92)
ITEM_EXCHANGE_STORAGE_FREE = (4, 0x4FA7)
ITEM_EXCHANGE_CHOICE_REFERENCES = ((7, 80), (7, 81))
ITEM_EXCHANGE_PROTOCOL_REFERENCES = tuple((7, index) for index in range(94, 109))

WANDERERS_SECRETS_HANDLER = (16, 0x7957)
WANDERERS_SECRETS_HANDLER_SPAN = 0x25
WANDERERS_SECRETS_ENTRY = (4, 0x40B0)
WANDERERS_SECRETS_ENTRY_SPAN = 0x10
WANDERERS_SECRETS_SCREEN = (4, 0x4083)
WANDERERS_SECRETS_SCREEN_SPAN = 0x2D
WANDERERS_SECRETS_CONTROLLER = (16, 0x45B9)
WANDERERS_SECRETS_CONTROLLER_SPAN = 0x6D
WANDERERS_SECRETS_HEADING_REFERENCE = (7, 73)
WANDERERS_SECRETS_REFERENCES = tuple((19, index) for index in range(10))
WANDERERS_SECRETS_PROSE_REFERENCES = tuple((19, index) for index in range(10, 21))

WANDERER_GRADE_HANDLER = (16, 0x79E1)
WANDERER_GRADE_HANDLER_SPAN = 0x25
WANDERER_GRADE_PICKER_ENTRY = GRADE_CATEGORY_PICKER_ENTRY
WANDERER_GRADE_PICKER_CONTROLLER = GRADE_CATEGORY_PICKER_CONTROLLER
WANDERER_GRADE_CATEGORY_RENDERER = (17, 0x5894)
WANDERER_GRADE_CATEGORY_RENDERER_SPAN = 0x42
WANDERER_GRADE_AVAILABILITY = (11, 0x4E67)
WANDERER_GRADE_AVAILABLE_COUNT = (11, 0x4EB9)
WANDERER_GRADE_CATEGORY_MAP = (11, 0x4ECF)
WANDERER_GRADE_SCREEN = (0xF4, 0x4000)
WANDERER_GRADE_SCREEN_SPAN = 0x45
WANDERER_GRADE_HEADER = (17, 0x4523)
WANDERER_GRADE_HEADER_SPAN = 0xA3
WANDERER_GRADE_BODY = (17, 0x512B)
WANDERER_GRADE_BODY_SPAN = 0xB2
WANDERER_GRADE_PICKER_REFERENCES = tuple((22, index) for index in range(30, 34))
WANDERER_GRADE_HEADER_REFERENCES = tuple((22, index) for index in range(34, 38))
WANDERER_GRADE_RESCUE_REFERENCES = tuple((22, index) for index in range(71, 74))
WANDERER_GRADE_DOMAINS = (
    ("wanderer", 0, 38),
    ("trap_mastery", 10, 60),
    ("cooking", 20, 49),
)

MONSTER_NOTEBOOK_HANDLER = (16, 0x7A06)
MONSTER_NOTEBOOK_HANDLER_SPAN = 0x0A
MONSTER_NOTEBOOK_ENTRY = (11, 0x7605)
MONSTER_NOTEBOOK_ENTRY_SPAN = 0x19
MONSTER_NOTEBOOK_SCREEN = (11, 0x4030)
MONSTER_NOTEBOOK_SCREEN_SPAN = 0x53
MONSTER_NOTEBOOK_CATALOG_BUILDER = (11, 0x7A43)
MONSTER_NOTEBOOK_CATALOG_BUILDER_SPAN = 0xC7
MONSTER_NOTEBOOK_PAGE_COUNTER = (11, 0x7B0A)
MONSTER_NOTEBOOK_PAGE_COUNTER_SPAN = 0x0E
MONSTER_NOTEBOOK_MASTER_TABLE = (11, 0x7CBD)
MONSTER_NOTEBOOK_CONTROLLER = (16, 0x7EA5)
MONSTER_NOTEBOOK_CONTROLLER_SPAN = 0x115
MONSTER_NOTEBOOK_CLEANUP = (16, 0x7FBA)
MONSTER_NOTEBOOK_DETAIL = (0xF4, 0x44E5)
MONSTER_NOTEBOOK_PAGE_SIZE = 27
MONSTER_NOTEBOOK_VARIANTS = 209
MONSTER_NOTEBOOK_ENTRY_SIZE = 3
MONSTER_NOTEBOOK_PAGE_COUNTER_REFERENCE = (24, 15)
MONSTER_NOTEBOOK_DESCRIPTION_GROUPS = (29, 30, 31)
MONSTER_NOTEBOOK_DESCRIPTION_REFERENCES = tuple(
    (group, index)
    for group in MONSTER_NOTEBOOK_DESCRIPTION_GROUPS
    for index in range(73)
)

GENERAL_INPUT_MODE_4 = 4
GENERAL_INPUT_MODE_4_SCREEN = (0xF4, 0x4045)
GENERAL_INPUT_MODE_4_SCREEN_SPAN = 0x77
GENERAL_INPUT_MODE_4_CONTROLLER = (16, 0x5AD2)
GENERAL_INPUT_MODE_4_CONTROLLER_SPAN = 0xBC
GENERAL_INPUT_MODE_4_DISPATCH = (16, 0x5AE3)
GENERAL_INPUT_MODE_4_CHARACTER_CELLS = 73
GENERAL_INPUT_MODE_4_SPECIAL_CELLS = {
    "diacritic_plain": 0x49,
    "diacritic_voiced": 0x4A,
    "kana_page": 0x4B,
    "conversion": 0x4C,
    "confirm": 0x4D,
    "buffer_right": 0x4E,
    "buffer_left": 0x4F,
    "backspace": 0x50,
}
GENERAL_INPUT_MODE_4_NAVIGATION_TABLE = (16, 0x5F9C)
GENERAL_INPUT_MODE_4_NAVIGATION_NODES = 81
GENERAL_INPUT_MODE_4_NAVIGATION_NODE_SIZE = 7
GENERAL_INPUT_MODE_4_TILEMAP_ROWS = (
    (127, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 127),
    (127, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 127),
    (42,) * 20,
    (40,) + (42,) * 18 + (40,),
    (41, 133, 143, 133, 148, 36, 36, 36, 36, 36, 36, 36, 36, 36, 36, 52, 91, 88, 36, 41),
    (41,) + (36,) * 18 + (41,),
    (41, 60, 60, 80, 36, 36, 36, 36, 82, 117, 88, 36, 36, 36, 36, 36, 56, 60, 36, 41),
    (41,) + (36,) * 18 + (41,),
    (41, 48, 49, 50, 51, 52, 36, 73, 74, 75, 76, 77, 36, 94, 95, 96, 97, 98, 36, 41),
    (41,) + (36,) * 18 + (41,),
    (41, 53, 54, 55, 56, 57, 36, 78, 79, 80, 81, 82, 36, 99, 100, 101, 102, 236, 36, 41),
    (41,) + (36,) * 18 + (41,),
    (41, 58, 59, 60, 61, 62, 36, 83, 36, 84, 36, 85, 36, 0, 1, 2, 3, 4, 36, 41),
    (41,) + (36,) * 18 + (41,),
    (41, 63, 64, 65, 66, 67, 36, 86, 87, 88, 89, 90, 36, 5, 6, 7, 8, 9, 36, 41),
    (41,) + (36,) * 18 + (41,),
    (41, 68, 69, 70, 71, 72, 36, 91, 92, 93, 36, 212, 36, 211, 38, 238, 222, 223, 36, 41),
    (40,) + (42,) * 18 + (40,),
)


def _little_endian_word_table(rom, bank, address, entries):
    at = extract.file_offset(bank, address)
    raw = rom[at:at + entries * 2]
    if len(raw) != entries * 2:
        raise ValueError("truncated word table at %s" % extract.location(bank, address))
    return [
        extract.location(bank, int.from_bytes(raw[offset:offset + 2], "little"))
        for offset in range(0, len(raw), 2)
    ]


def record_picker_and_graphical_input_summary(rom):
    """Freeze ranking/Grade pickers and the separate mode-3 editor."""
    rom = bytes(rom)
    character_at = extract.file_offset(*GRAPHICAL_INPUT_CHARACTER_TABLE)
    character_bytes = rom[
        character_at:character_at + GRAPHICAL_INPUT_CHARACTER_CELLS
    ]
    if len(character_bytes) != GRAPHICAL_INPUT_CHARACTER_CELLS:
        raise ValueError("truncated graphical input character table")
    navigation_at = extract.file_offset(*GRAPHICAL_INPUT_NAVIGATION_TABLE)
    navigation_raw = rom[
        navigation_at:navigation_at
        + GRAPHICAL_INPUT_NAVIGATION_NODES * GRAPHICAL_INPUT_NAVIGATION_NODE_SIZE
    ]
    if len(navigation_raw) != (
        GRAPHICAL_INPUT_NAVIGATION_NODES * GRAPHICAL_INPUT_NAVIGATION_NODE_SIZE
    ):
        raise ValueError("truncated graphical input navigation table")
    navigation = []
    for node in range(GRAPHICAL_INPUT_NAVIGATION_NODES):
        offset = node * GRAPHICAL_INPUT_NAVIGATION_NODE_SIZE
        raw = navigation_raw[offset:offset + GRAPHICAL_INPUT_NAVIGATION_NODE_SIZE]
        if any(value >= GRAPHICAL_INPUT_NAVIGATION_NODES for value in raw[:4]):
            raise ValueError("graphical input neighbor is outside the node domain")
        navigation.append(
            {
                "node": node,
                "neighbors": {
                    name: raw[index]
                    for index, name in enumerate(("down", "up", "left", "right"))
                },
                "cursor_sprite": list(raw[4:]),
            }
        )

    def dispatch(bank_address):
        targets = _little_endian_word_table(rom, *bank_address, len(INPUT_INDEX_NAMES))
        return [
            {"index": index, "input": name, "target": target}
            for index, (name, target) in enumerate(zip(INPUT_INDEX_NAMES, targets))
        ]

    return {
        "input_index_order": list(INPUT_INDEX_NAMES),
        "ranking_record_picker": {
            "entry": extract.location(*RANKING_RECORD_PICKER_ENTRY),
            "rows": 5,
            "count_provider": {
                "entry": extract.location(*RANKING_RECORD_COUNT),
                "result_register": "C",
            },
            "maximum_index_store": "$C151",
            "cursor_index_store": "$C14F",
            "controller": extract.location(*RANKING_RECORD_PICKER_CONTROLLER),
            "controls": {
                "down": "move with wrap",
                "up": "move with wrap",
                "b": "return $FE",
                "a": "return selected zero-based index",
                "other": "ignored",
            },
            "dispatch": dispatch(RANKING_RECORD_PICKER_DISPATCH),
            "seeded_live_outcomes": {
                "down_then_a": {"selection": 1, "result": "$01"},
                "up_then_a": {"selection": 4, "result": "$04"},
                "b": {"selection": 0, "result": "$FE"},
            },
        },
        "grade_category_picker": {
            "entry": extract.location(*GRADE_CATEGORY_PICKER_ENTRY),
            "rows": 4,
            "count_provider": {
                "entry": extract.location(*GRADE_CATEGORY_COUNT),
                "result_register": "D",
            },
            "maximum_index_store": "$C151",
            "cursor_index_store": "$C14F",
            "controller": extract.location(*GRADE_CATEGORY_PICKER_CONTROLLER),
            "controls": {
                "down": "move with wrap",
                "up": "move with wrap",
                "b": "return $FE",
                "a": "return selected zero-based index",
                "other": "ignored",
            },
            "dispatch": dispatch(GRADE_CATEGORY_PICKER_DISPATCH),
            "seeded_live_outcomes": {
                "down_then_a": {"selection": 1, "result": "$01"},
                "up_then_a": {"selection": 3, "result": "$03"},
                "b": {"selection": 0, "result": "$FE"},
            },
        },
        "shared_picker_cursor": {
            "renderer": extract.location(*PICKER_CURSOR_RENDERER),
            "selection_store": "$C14F",
            "limit_store": "$C151",
        },
        "graphical_input_mode_3": {
            "owner_path": {
                "script_bridge": "5:$5642",
                "caller": extract.location(*GRAPHICAL_INPUT_CALLER),
                "mode_branch": "C == 3",
                "entry": extract.location(*GRAPHICAL_INPUT_ENTRY),
                "screen": extract.location(*GRAPHICAL_INPUT_SCREEN),
                "controller": extract.location(*GRAPHICAL_INPUT_CONTROLLER),
            },
            "mode": GRAPHICAL_INPUT_MODE,
            "buffer": {
                "address": "$%04X" % GRAPHICAL_INPUT_BUFFER_ADDRESS,
                "bytes": GRAPHICAL_INPUT_BUFFER_SIZE,
                "blank": "$D5",
                "terminator": "$FF",
                "position_store": "$C152",
                "length_store": "$C153",
            },
            "cells": {
                "characters": GRAPHICAL_INPUT_CHARACTER_CELLS,
                "special": dict(GRAPHICAL_INPUT_SPECIAL_CELLS),
                "character_table": extract.location(
                    *GRAPHICAL_INPUT_CHARACTER_TABLE
                ),
                "character_bytes": character_bytes.hex().upper(),
                "characters_decoded": [
                    codec.decode(bytes((value,))) for value in character_bytes
                ],
                "navigation_table": extract.location(
                    *GRAPHICAL_INPUT_NAVIGATION_TABLE
                ),
                "navigation_graph": navigation,
            },
            "controls": {
                "dpad": "move through the 52-node directional graph",
                "a_character": "insert selected character; fourth byte selects confirm",
                "kana_page": (
                    "base $30-$66 cells gain $50 when the runtime page flag at "
                    "$FF8E is zero"
                ),
                "a_diacritic": "toggle the current kana diacritic pair",
                "a_backspace": "delete one byte",
                "a_confirm": "reject blank input; return $F8 for nonblank mode-3 input",
                "b": "backspace nonblank input; return $FE when blank",
                "start": "jump directly to confirm cell $33",
                "select": "toggle the current kana diacritic pair",
            },
            "dispatch": dispatch(GRAPHICAL_INPUT_DISPATCH),
            "graphics": {
                "renderer": "graphical tilemap; no direct/full text calls",
                "shared_rom_template_with": (
                    "seeded_item_list.representative_routes."
                    "container_and_writing[2].keyboard_screen"
                ),
                "mode_specific_behavior": (
                    "mode 3 blanks unavailable template cells and exposes "
                    "the 49-entry hiragana table plus three controls"
                ),
                "upload": extract.location(*GRAPHICAL_INPUT_TILEMAP_UPLOAD),
                "tilemap_source": extract.location(
                    *GRAPHICAL_INPUT_TILEMAP_SOURCE
                ),
                "attribute_source": extract.location(
                    *GRAPHICAL_INPUT_ATTRIBUTE_SOURCE
                ),
                "source_size_tiles": [20, 16],
                "visible_size_tiles": [20, 18],
                "visible_rows": [
                    list(row) for row in GRAPHICAL_INPUT_MODE_3_TILEMAP_ROWS
                ],
                "lcdc": "$E7",
                "registers": {"wx": 7, "wy": 144},
            },
            "seeded_live_outcomes": {
                "constructor": {
                    "mode": 3,
                    "maximum_bytes": 4,
                    "cursor": 0,
                    "buffer_position": 0,
                },
                "a_at_initial_cell": {
                    "base_cell": "$30 / あ",
                    "runtime_page_flag": "$00",
                    "inserted": "$80",
                    "decoded": "ア",
                    "buffer_position": 1,
                },
                "select_over_ka": {"before": "か", "after": "が"},
                "start_then_a_nonblank": {"cursor": 0x33, "result": "$F8"},
                "b_blank": {"cursor": 0, "result": "$FE"},
            },
        },
        "evidence": {
            "joypad_poll": _code_evidence(
                rom, *JOYPAD_POLL, JOYPAD_POLL_SPAN
            ),
            "input_index_decoder": _code_evidence(
                rom, *INPUT_INDEX_DECODER, INPUT_INDEX_DECODER_SPAN
            ),
            "ranking_picker_entry": _code_evidence(
                rom,
                *RANKING_RECORD_PICKER_ENTRY,
                RANKING_RECORD_PICKER_ENTRY_SPAN,
            ),
            "grade_picker_entry": _code_evidence(
                rom,
                *GRADE_CATEGORY_PICKER_ENTRY,
                GRADE_CATEGORY_PICKER_ENTRY_SPAN,
            ),
            "shared_cursor": _code_evidence(
                rom, *PICKER_CURSOR_RENDERER, PICKER_CURSOR_RENDERER_SPAN
            ),
            "ranking_controller": _code_evidence(
                rom,
                *RANKING_RECORD_PICKER_CONTROLLER,
                RANKING_RECORD_PICKER_CONTROLLER_SPAN,
            ),
            "grade_controller": _code_evidence(
                rom,
                *GRADE_CATEGORY_PICKER_CONTROLLER,
                GRADE_CATEGORY_PICKER_CONTROLLER_SPAN,
            ),
            "graphical_caller": _code_evidence(
                rom, *GRAPHICAL_INPUT_CALLER, GRAPHICAL_INPUT_CALLER_SPAN
            ),
            "graphical_entry": _code_evidence(
                rom, *GRAPHICAL_INPUT_ENTRY, GRAPHICAL_INPUT_ENTRY_SPAN
            ),
            "graphical_screen": _code_evidence(
                rom, *GRAPHICAL_INPUT_SCREEN, GRAPHICAL_INPUT_SCREEN_SPAN
            ),
            "graphical_controller": _code_evidence(
                rom,
                *GRAPHICAL_INPUT_CONTROLLER,
                GRAPHICAL_INPUT_CONTROLLER_SPAN,
            ),
            "length_resolver": _code_evidence(
                rom,
                *GRAPHICAL_INPUT_LENGTH_RESOLVER,
                GRAPHICAL_INPUT_LENGTH_RESOLVER_SPAN,
            ),
            "character_insert": _code_evidence(
                rom,
                *GRAPHICAL_INPUT_CHARACTER_INSERT,
                GRAPHICAL_INPUT_CHARACTER_INSERT_SPAN,
            ),
            "navigation_table": _code_evidence(
                rom,
                *GRAPHICAL_INPUT_NAVIGATION_TABLE,
                GRAPHICAL_INPUT_NAVIGATION_NODES
                * GRAPHICAL_INPUT_NAVIGATION_NODE_SIZE,
            ),
            "diacritic_toggle": _code_evidence(
                rom,
                *GRAPHICAL_INPUT_DIACRITIC,
                GRAPHICAL_INPUT_DIACRITIC_SPAN,
            ),
            "backspace": _code_evidence(
                rom,
                *GRAPHICAL_INPUT_BACKSPACE,
                GRAPHICAL_INPUT_BACKSPACE_SPAN,
            ),
            "confirm": _code_evidence(
                rom, *GRAPHICAL_INPUT_CONFIRM, GRAPHICAL_INPUT_CONFIRM_SPAN
            ),
            "tilemap_upload": _code_evidence(
                rom,
                *GRAPHICAL_INPUT_TILEMAP_UPLOAD,
                GRAPHICAL_INPUT_TILEMAP_UPLOAD_SPAN,
            ),
            "tilemap_source": _code_evidence(
                rom,
                *GRAPHICAL_INPUT_TILEMAP_SOURCE,
                GRAPHICAL_INPUT_MAP_SIZE,
            ),
            "attribute_source": _code_evidence(
                rom,
                *GRAPHICAL_INPUT_ATTRIBUTE_SOURCE,
                GRAPHICAL_INPUT_MAP_SIZE,
            ),
        },
    }


def diary_management_summary(rom, result=None):
    """Freeze the ten-slot hub and its Create/Delete/Rename routes."""
    rom = bytes(rom)
    result = extract.extract(rom) if result is None else result
    records = _record_reference_map(result)
    handler_targets = _little_endian_word_table(
        rom, *DIARY_HUB_DISPATCH, len(DIARY_HUB_LABEL_NAMES)
    )
    predicate_targets = _little_endian_word_table(
        rom, *DIARY_HUB_PREDICATE_DISPATCH, len(DIARY_HUB_LABEL_NAMES)
    )

    labels = []
    for slot, (name, handler, predicate) in enumerate(
        zip(DIARY_HUB_LABEL_NAMES, handler_targets, predicate_targets)
    ):
        reference = (DIARY_HUB_LABEL_GROUP, DIARY_HUB_LABEL_START + slot)
        record = records[reference]
        start_x = 6
        all_enabled_y = 1 + 11 * slot
        measured = layout.validate_direct_surface(
            rom,
            record.raw,
            start_x=start_x,
            start_y=all_enabled_y,
            right_edge=DIARY_HUB_VISUAL_RIGHT_EDGE,
        )
        labels.append(
            {
                "slot": slot,
                "name": name,
                "reference": list(reference),
                "record": record.id,
                "source": record.source,
                "raw": record.raw.hex().upper(),
                "handler": handler,
                "availability_predicate": {
                    "entry": predicate,
                    "available_when": "C == 0",
                },
                "start_x": start_x,
                "dynamic_y": "1 + 11 * enabled prior slots",
                "all_enabled_start_pen": [start_x, all_enabled_y],
                "right_edge": DIARY_HUB_VISUAL_RIGHT_EDGE,
                "available_pixels": DIARY_HUB_VISUAL_RIGHT_EDGE - start_x,
                "renderer_pixels": measured.rightmost_pen - start_x,
                "all_enabled_final_pen": [
                    measured.final_x,
                    measured.final_y,
                ],
            }
        )

    character_at = extract.file_offset(*GRAPHICAL_INPUT_CHARACTER_TABLE)
    character_bytes = rom[
        character_at:
        character_at + GENERAL_INPUT_MODE_4_CHARACTER_CELLS
    ]
    if len(character_bytes) != GENERAL_INPUT_MODE_4_CHARACTER_CELLS:
        raise ValueError("truncated mode-4 input character table")
    navigation_at = extract.file_offset(*GENERAL_INPUT_MODE_4_NAVIGATION_TABLE)
    navigation_size = (
        GENERAL_INPUT_MODE_4_NAVIGATION_NODES
        * GENERAL_INPUT_MODE_4_NAVIGATION_NODE_SIZE
    )
    navigation_raw = rom[navigation_at:navigation_at + navigation_size]
    if len(navigation_raw) != navigation_size:
        raise ValueError("truncated mode-4 input navigation table")
    navigation = []
    for node in range(GENERAL_INPUT_MODE_4_NAVIGATION_NODES):
        offset = node * GENERAL_INPUT_MODE_4_NAVIGATION_NODE_SIZE
        raw = navigation_raw[
            offset:offset + GENERAL_INPUT_MODE_4_NAVIGATION_NODE_SIZE
        ]
        if any(
            value >= GENERAL_INPUT_MODE_4_NAVIGATION_NODES
            for value in raw[:4]
        ):
            raise ValueError("mode-4 input neighbor is outside the node domain")
        navigation.append(
            {
                "node": node,
                "neighbors": {
                    name: raw[index]
                    for index, name in enumerate(("down", "up", "left", "right"))
                },
                "cursor_sprite": list(raw[4:]),
            }
        )

    prompt_record = records[DIARY_DELETE_PROMPT_REFERENCE]
    prompt_layout = layout.renderer_layout(
        rom, prompt_record.raw, mode=GENERAL_INPUT_MODE_4
    )
    if prompt_layout.auto_wraps:
        raise ValueError("delete-diary confirmation prompt auto-wraps")

    return {
        "hub": {
            "entry": extract.location(*DIARY_HUB_ENTRY),
            "renderer": extract.location(*DIARY_HUB_RENDERER),
            "dispatch_table": extract.location(*DIARY_HUB_DISPATCH),
            "predicate_table": extract.location(
                *DIARY_HUB_PREDICATE_DISPATCH
            ),
            "slots": len(labels),
            "selection_store": "$C14F",
            "labels": labels,
        },
        "create_diary": {
            "slot": 1,
            "handler": extract.location(*DIARY_CREATE_HANDLER),
            "prelude": ["11:$4244", "11:$42EB"],
            "editor": "mode_4_name_editor",
            "blank_b": "returns $FE to the handler, which re-enters the controller",
            "accepted_result": "$F8",
            "hub_continuation": {
                "entry": "16:$76DB",
                "commit": "11:$5092",
            },
            "seeded_live_outcome": {
                "inputs": ["B on blank", "A on cell 0", "Start", "A"],
                "buffer": "30FFD5D5FF",
                "result": "$F8",
                "blank_cancel_retried": True,
            },
        },
        "delete_diary": {
            "slot": 3,
            "handler": extract.location(*DIARY_DELETE_HANDLER),
            "prelude": extract.location(*DIARY_DELETE_PRELUDE),
            "confirmation_controller": extract.location(
                *DIARY_DELETE_CONFIRMATION
            ),
            "prompt": {
                "reference": list(DIARY_DELETE_PROMPT_REFERENCE),
                "record": prompt_record.id,
                "source": prompt_record.source,
                "raw": prompt_record.raw.hex().upper(),
                "renderer_mode": GENERAL_INPUT_MODE_4,
                "start_pen": [prompt_layout.start_x, prompt_layout.start_y],
                "line_widths": list(prompt_layout.line_widths),
                "renderer_pixels": (
                    prompt_layout.rightmost_pen - prompt_layout.start_x
                ),
                "final_pen": [prompt_layout.final_x, prompt_layout.final_y],
                "explicit_breaks": len(prompt_layout.explicit_breaks),
                "automatic_wraps": len(prompt_layout.auto_wraps),
                "default_choice": "no",
            },
            "outcomes": {
                "no": {
                    "controller_result": 1,
                    "handler_result": "$FB",
                    "mutation_calls": 0,
                },
                "yes": {
                    "controller_result": 0,
                    "handler_result": "$EE",
                    "mutation": extract.location(*DIARY_DELETE_MUTATION),
                    "mutation_calls": 1,
                },
            },
        },
        "rename": {
            "slot": 4,
            "handler": extract.location(*DIARY_RENAME_HANDLER),
            "editor": "mode_4_name_editor",
            "save": extract.location(*DIARY_SAVE),
            "handler_result": "$F4",
            "seeded_live_outcomes": {
                "blank_b": {"save_calls": 0, "result": "$F4"},
                "accepted": {
                    "inputs": ["A on cell 0", "Start", "A"],
                    "buffer": "30FFD5D5FF",
                    "save_calls": 1,
                    "result": "$F4",
                },
            },
        },
        "mode_4_name_editor": {
            "entry": extract.location(*GENERAL_INPUT_MODE_4_SCREEN),
            "controller": extract.location(*GENERAL_INPUT_MODE_4_CONTROLLER),
            "mode": GENERAL_INPUT_MODE_4,
            "buffer": {
                "address": "$C16D",
                "bytes": 4,
                "blank": "$D5",
                "terminator": "$FF",
                "position_store": "$C152",
                "length_store": "$C153",
            },
            "cells": {
                "characters": GENERAL_INPUT_MODE_4_CHARACTER_CELLS,
                "special": dict(GENERAL_INPUT_MODE_4_SPECIAL_CELLS),
                "character_table": extract.location(
                    *GRAPHICAL_INPUT_CHARACTER_TABLE
                ),
                "character_bytes": character_bytes.hex().upper(),
                "characters_decoded": [
                    codec.decode(bytes((value,))) for value in character_bytes
                ],
                "navigation_table": extract.location(
                    *GENERAL_INPUT_MODE_4_NAVIGATION_TABLE
                ),
                "navigation_graph": navigation,
            },
            "controls": {
                "dpad": "move through the 81-node directional graph",
                "a_character": "insert one of 73 character-table entries",
                "a_confirm": "cell $4D returns $F8 only for nonblank input",
                "b": "backspace nonblank input; return $FE when blank",
                "start": "jump directly to confirm cell $4D when permitted",
                "select": "apply the current character's diacritic transform",
            },
            "dispatch": [
                {"index": index, "input": name, "target": target}
                for index, (name, target) in enumerate(
                    zip(
                        INPUT_INDEX_NAMES,
                        _little_endian_word_table(
                            rom,
                            *GENERAL_INPUT_MODE_4_DISPATCH,
                            len(INPUT_INDEX_NAMES),
                        ),
                    )
                )
            ],
            "graphics": {
                "renderer": "graphical tilemap; no direct/full text calls",
                "shared_rom_template_with": [
                    "record_picker_and_graphical_input.graphical_input_mode_3",
                    (
                        "seeded_item_list.representative_routes."
                        "container_and_writing[2].keyboard_screen"
                    ),
                ],
                "mode_specific_behavior": (
                    "full 73-character mode-4 grid; final map differs from "
                    "mode 3 by 105 cells and from Blank Scroll by 4 cells"
                ),
                "visible_size_tiles": [20, 18],
                "visible_rows": [
                    list(row) for row in GENERAL_INPUT_MODE_4_TILEMAP_ROWS
                ],
                "lcdc": "$E7",
                "registers": {"wx": 7, "wy": 144},
            },
            "seeded_live_outcomes": {
                "constructor": {
                    "mode": 4,
                    "maximum_bytes": 4,
                    "cursor": 0,
                    "buffer_position": 0,
                },
                "a_at_initial_cell": {
                    "inserted": "$30",
                    "decoded": "あ",
                    "buffer_position": 1,
                },
                "start_then_a_nonblank": {"cursor": 0x4D, "result": "$F8"},
                "b_blank": {"cursor": 0, "result": "$FE"},
            },
        },
        "evidence": {
            "hub": _code_evidence(
                rom, *DIARY_HUB_ENTRY, DIARY_HUB_ENTRY_SPAN
            ),
            "hub_renderer": _code_evidence(
                rom, *DIARY_HUB_RENDERER, DIARY_HUB_RENDERER_SPAN
            ),
            "create_handler": _code_evidence(
                rom, *DIARY_CREATE_HANDLER, DIARY_CREATE_HANDLER_SPAN
            ),
            "delete_handler": _code_evidence(
                rom, *DIARY_DELETE_HANDLER, DIARY_DELETE_HANDLER_SPAN
            ),
            "rename_handler": _code_evidence(
                rom, *DIARY_RENAME_HANDLER, DIARY_RENAME_HANDLER_SPAN
            ),
            "delete_prelude": _code_evidence(
                rom, *DIARY_DELETE_PRELUDE, DIARY_DELETE_PRELUDE_SPAN
            ),
            "delete_confirmation": _code_evidence(
                rom,
                *DIARY_DELETE_CONFIRMATION,
                DIARY_DELETE_CONFIRMATION_SPAN,
            ),
            "delete_mutation": _code_evidence(
                rom, *DIARY_DELETE_MUTATION, DIARY_DELETE_MUTATION_SPAN
            ),
            "save": _code_evidence(rom, *DIARY_SAVE, DIARY_SAVE_SPAN),
            "mode_4_screen": _code_evidence(
                rom,
                *GENERAL_INPUT_MODE_4_SCREEN,
                GENERAL_INPUT_MODE_4_SCREEN_SPAN,
            ),
            "mode_4_controller": _code_evidence(
                rom,
                *GENERAL_INPUT_MODE_4_CONTROLLER,
                GENERAL_INPUT_MODE_4_CONTROLLER_SPAN,
            ),
            "mode_4_navigation": _code_evidence(
                rom,
                *GENERAL_INPUT_MODE_4_NAVIGATION_TABLE,
                navigation_size,
            ),
        },
    }


def remaining_hub_routes_summary(rom, result=None):
    """Freeze Item Exchange, Secrets, Grade and Monster Notebook."""
    rom = bytes(rom)
    result = extract.extract(rom) if result is None else result
    records = _record_reference_map(result)

    def record_contract(reference, mode):
        record = records[reference]
        measured = layout.renderer_layout(rom, record.raw, mode=mode)
        return {
            "reference": list(reference),
            "record": record.id,
            "source": record.source,
            "raw": record.raw.hex().upper(),
            "renderer_mode": mode,
            "start_pen": [measured.start_x, measured.start_y],
            "line_widths": list(measured.line_widths),
            "final_pen": [measured.final_x, measured.final_y],
            "explicit_breaks": len(measured.explicit_breaks),
            "automatic_wraps": len(measured.auto_wraps),
        }

    def positioned_contract(reference, start_x, start_y, mode=0x08):
        record = records[reference]
        measured = layout.validate_direct_surface(
            rom,
            record.raw,
            start_x=start_x,
            start_y=start_y,
            right_edge=layout.CANVAS_WIDTH_PIXELS,
        )
        return {
            "reference": list(reference),
            "record": record.id,
            "source": record.source,
            "raw": record.raw.hex().upper(),
            "start_pen": [start_x, start_y],
            "right_edge": layout.CANVAS_WIDTH_PIXELS,
            "available_pixels": layout.CANVAS_WIDTH_PIXELS - start_x,
            "renderer_pixels": measured.rightmost_pen - start_x,
            "final_pen": [measured.final_x, measured.final_y],
            "observed_mode": mode,
        }

    exchange_choices = [
        positioned_contract(reference, 36, 52 + row * 11, mode=1)
        for row, reference in enumerate(ITEM_EXCHANGE_CHOICE_REFERENCES)
    ]
    exchange_protocol = [
        record_contract(reference, mode=4)
        for reference in ITEM_EXCHANGE_PROTOCOL_REFERENCES
    ]

    secrets_heading = positioned_contract(
        WANDERERS_SECRETS_HEADING_REFERENCE, 8, 4
    )
    secret_rows = []
    for selection, reference in enumerate(WANDERERS_SECRETS_REFERENCES):
        secret_rows.append(
            {
                **positioned_contract(reference, 3, 1 + selection * 11),
                "selection": selection,
                "event_id": selection + 4,
            }
        )
    secret_prose = [
        record_contract(reference, mode=0x08)
        for reference in WANDERERS_SECRETS_PROSE_REFERENCES
    ]

    grade_picker = [
        positioned_contract(reference, 36, 48 + category * 11)
        for category, reference in enumerate(WANDERER_GRADE_PICKER_REFERENCES)
    ]
    grade_headers = [
        positioned_contract(reference, 4, 4)
        for reference in WANDERER_GRADE_HEADER_REFERENCES
    ]
    grade_domains = []
    for category, (name, achievement_start, title_start) in enumerate(
        WANDERER_GRADE_DOMAINS
    ):
        achievements = [
            positioned_contract(
                (22, achievement_start + row), 3, 1 + row * 11
            )
            for row in range(10)
        ]
        titles = [
            positioned_contract((22, title_start + level), 80, 4)
            for level in range(11)
        ]
        grade_domains.append(
            {
                "category": category,
                "name": name,
                "achievement_reference_range": [
                    [22, achievement_start],
                    [22, achievement_start + 9],
                ],
                "title_reference_range": [
                    [22, title_start],
                    [22, title_start + 10],
                ],
                "achievements": achievements,
                "titles": titles,
            }
        )
    grade_rescue = [
        record_contract(reference, mode=0x08)
        for reference in WANDERER_GRADE_RESCUE_REFERENCES
    ]

    master_size = MONSTER_NOTEBOOK_VARIANTS * MONSTER_NOTEBOOK_ENTRY_SIZE
    master_at = extract.file_offset(*MONSTER_NOTEBOOK_MASTER_TABLE)
    master_raw = rom[master_at:master_at + master_size]
    if len(master_raw) != master_size:
        raise ValueError("truncated Monster Notebook master table")
    notebook_descriptions = [
        record_contract(reference, mode=0x08)
        for reference in MONSTER_NOTEBOOK_DESCRIPTION_REFERENCES
    ]
    notebook_pages = (
        MONSTER_NOTEBOOK_VARIANTS + MONSTER_NOTEBOOK_PAGE_SIZE - 1
    ) // MONSTER_NOTEBOOK_PAGE_SIZE

    return {
        "item_exchange": {
            "slot": 2,
            "handler": extract.location(*ITEM_EXCHANGE_HANDLER),
            "menu": {
                "entry": extract.location(*ITEM_EXCHANGE_MENU_ENTRY),
                "controller": extract.location(*ITEM_EXCHANGE_CONTROLLER),
                "choices": exchange_choices,
                "cancel_result": "$FB",
            },
            "routes": {
                "give": {
                    "selection": 0,
                    "entry": extract.location(*ITEM_EXCHANGE_GIVE_ENTRY),
                    "empty_gate_reference": [7, 96],
                    "local_gate_result": "$F4",
                },
                "receive": {
                    "selection": 1,
                    "entry": extract.location(*ITEM_EXCHANGE_RECEIVE_ENTRY),
                    "full_gate_reference": [7, 97],
                    "local_gate_result": "$F4",
                },
            },
            "storage": {
                "wram_bank": 2,
                "address_range": ["$D000", "$D063"],
                "slots": 100,
                "empty_sentinel": "$FF",
                "used_scanner": extract.location(*ITEM_EXCHANGE_STORAGE_USED),
                "free_scanner": extract.location(*ITEM_EXCHANGE_STORAGE_FREE),
            },
            "protocol_text": {
                "reference_range": [[7, 94], [7, 108]],
                "records": exchange_protocol,
                "scope_note": (
                    "shared local/link communication domain; index 107 is the "
                    "adjacent SOS completion message"
                ),
            },
            "coverage_boundary": (
                "menu, cancel and deterministic empty/full preflight gates are "
                "locally replayable; a successful transfer requires two linked "
                "emulator instances"
            ),
        },
        "wanderers_secrets": {
            "slot": 6,
            "handler": extract.location(*WANDERERS_SECRETS_HANDLER),
            "entry": extract.location(*WANDERERS_SECRETS_ENTRY),
            "screen": extract.location(*WANDERERS_SECRETS_SCREEN),
            "controller": extract.location(*WANDERERS_SECRETS_CONTROLLER),
            "heading": secrets_heading,
            "rows": secret_rows,
            "selection_to_event": [
                {"selection": selection, "event_id": selection + 4}
                for selection in range(10)
            ],
            "related_prose": {
                "reference_range": [[19, 10], [19, 20]],
                "records": secret_prose,
                "alias_note": "indices 10 and 11 share record 194:$40DC",
            },
            "cancel_result": "$F4",
        },
        "wanderer_grade": {
            "slot": 8,
            "handler": extract.location(*WANDERER_GRADE_HANDLER),
            "picker": {
                "entry": extract.location(*WANDERER_GRADE_PICKER_ENTRY),
                "controller": extract.location(
                    *WANDERER_GRADE_PICKER_CONTROLLER
                ),
                "renderer": extract.location(*WANDERER_GRADE_CATEGORY_RENDERER),
                "availability": extract.location(*WANDERER_GRADE_AVAILABILITY),
                "available_when": "C != 0",
                "count": extract.location(*WANDERER_GRADE_AVAILABLE_COUNT),
                "compact_to_category": extract.location(
                    *WANDERER_GRADE_CATEGORY_MAP
                ),
                "rows": grade_picker,
                "cancel_result": "$FB",
            },
            "detail": {
                "entry": extract.location(*WANDERER_GRADE_SCREEN),
                "header_renderer": extract.location(*WANDERER_GRADE_HEADER),
                "body_renderer": extract.location(*WANDERER_GRADE_BODY),
                "headers": grade_headers,
                "achievement_domains": grade_domains,
                "rescue_category": {
                    "category": 3,
                    "title": "dynamic rescue count",
                    "records": grade_rescue,
                    "history_rows": 8,
                },
            },
            "handler_result_after_detail": "$F4",
        },
        "monster_notebook": {
            "slot": 9,
            "handler": extract.location(*MONSTER_NOTEBOOK_HANDLER),
            "entry": extract.location(*MONSTER_NOTEBOOK_ENTRY),
            "screen": extract.location(*MONSTER_NOTEBOOK_SCREEN),
            "controller": extract.location(*MONSTER_NOTEBOOK_CONTROLLER),
            "cleanup": extract.location(*MONSTER_NOTEBOOK_CLEANUP),
            "detail": extract.location(*MONSTER_NOTEBOOK_DETAIL),
            "catalog": {
                "master_table": extract.location(*MONSTER_NOTEBOOK_MASTER_TABLE),
                "variants": MONSTER_NOTEBOOK_VARIANTS,
                "entry_size": MONSTER_NOTEBOOK_ENTRY_SIZE,
                "bytes": master_size,
                "sha1": sha1(master_raw).hexdigest(),
                "first_entries": [
                    list(master_raw[offset:offset + MONSTER_NOTEBOOK_ENTRY_SIZE])
                    for offset in range(0, 5 * MONSTER_NOTEBOOK_ENTRY_SIZE, 3)
                ],
                "page_size": MONSTER_NOTEBOOK_PAGE_SIZE,
                "pages": notebook_pages,
                "maximum_page_index": notebook_pages - 1,
                "page_store": "$C152",
                "cursor_store": "$C14F",
                "maximum_page_store": "$C153",
                "cache": {
                    "address": "$CF00",
                    "entries": MONSTER_NOTEBOOK_PAGE_SIZE,
                    "entry_size": MONSTER_NOTEBOOK_ENTRY_SIZE,
                    "bytes": MONSTER_NOTEBOOK_PAGE_SIZE
                    * MONSTER_NOTEBOOK_ENTRY_SIZE,
                },
            },
            "text_domains": {
                "page_counter": record_contract(
                    MONSTER_NOTEBOOK_PAGE_COUNTER_REFERENCE, mode=4
                ),
                "descriptions": {
                    "tier_reference_ranges": [
                        [[group, 0], [group, 72]]
                        for group in MONSTER_NOTEBOOK_DESCRIPTION_GROUPS
                    ],
                    "records": notebook_descriptions,
                },
                "monster_names": (
                    "shared runtime_terms actor_name tier domains; the 209 "
                    "catalog variants are graphical cells, not duplicate script "
                    "name records"
                ),
            },
            "seeded_full_catalog_outcome": {
                "maximum_page_index": 7,
                "down_wrap_pages": [0, 1],
                "navigation_note": (
                    "Left/Right moves within a nine-column row; Down from the "
                    "bottom row and Up from the top row cross page boundaries"
                ),
                "a_opens_detail": extract.location(*MONSTER_NOTEBOOK_DETAIL),
                "b_result": "$F4",
            },
        },
        "evidence": {
            "item_exchange_handler": _code_evidence(
                rom, *ITEM_EXCHANGE_HANDLER, ITEM_EXCHANGE_HANDLER_SPAN
            ),
            "item_exchange_menu": _code_evidence(
                rom, *ITEM_EXCHANGE_MENU_ENTRY, ITEM_EXCHANGE_MENU_ENTRY_SPAN
            ),
            "item_exchange_give": _code_evidence(
                rom, *ITEM_EXCHANGE_GIVE_ENTRY, 0x182
            ),
            "item_exchange_receive": _code_evidence(
                rom, *ITEM_EXCHANGE_RECEIVE_ENTRY, 0x17A
            ),
            "secrets_handler": _code_evidence(
                rom, *WANDERERS_SECRETS_HANDLER, WANDERERS_SECRETS_HANDLER_SPAN
            ),
            "secrets_screen": _code_evidence(
                rom, *WANDERERS_SECRETS_SCREEN, WANDERERS_SECRETS_SCREEN_SPAN
            ),
            "grade_handler": _code_evidence(
                rom, *WANDERER_GRADE_HANDLER, WANDERER_GRADE_HANDLER_SPAN
            ),
            "grade_picker_renderer": _code_evidence(
                rom,
                *WANDERER_GRADE_CATEGORY_RENDERER,
                WANDERER_GRADE_CATEGORY_RENDERER_SPAN,
            ),
            "grade_screen": _code_evidence(
                rom, *WANDERER_GRADE_SCREEN, WANDERER_GRADE_SCREEN_SPAN
            ),
            "grade_header": _code_evidence(
                rom, *WANDERER_GRADE_HEADER, WANDERER_GRADE_HEADER_SPAN
            ),
            "grade_body": _code_evidence(
                rom, *WANDERER_GRADE_BODY, WANDERER_GRADE_BODY_SPAN
            ),
            "notebook_handler": _code_evidence(
                rom, *MONSTER_NOTEBOOK_HANDLER, MONSTER_NOTEBOOK_HANDLER_SPAN
            ),
            "notebook_entry": _code_evidence(
                rom, *MONSTER_NOTEBOOK_ENTRY, MONSTER_NOTEBOOK_ENTRY_SPAN
            ),
            "notebook_screen": _code_evidence(
                rom, *MONSTER_NOTEBOOK_SCREEN, MONSTER_NOTEBOOK_SCREEN_SPAN
            ),
            "notebook_catalog_builder": _code_evidence(
                rom,
                *MONSTER_NOTEBOOK_CATALOG_BUILDER,
                MONSTER_NOTEBOOK_CATALOG_BUILDER_SPAN,
            ),
            "notebook_controller": _code_evidence(
                rom,
                *MONSTER_NOTEBOOK_CONTROLLER,
                MONSTER_NOTEBOOK_CONTROLLER_SPAN,
            ),
        },
    }


def _adventure_start_menu_tilemap(enabled_count):
    """Build the 14-column BG slice used by the compact adventure menu."""
    if not 1 <= enabled_count <= 8:
        raise ValueError("adventure-start menu requires 1..8 enabled rows")
    interior_rows = (enabled_count * ADVENTURE_START_ROW_STEP + 7) // 8
    border = (0x7C,) + (0x7E,) * 12 + (0x7C,)
    body = tuple(
        (0x7D,)
        + tuple(
            (0x80 + row * layout.CANVAS_TILE_COLUMNS + column) & 0xFF
            for column in range(6, 18)
        )
        + (0x7D,)
        for row in range(interior_rows)
    )
    return (border,) + body + (border,)


def adventure_start_menu_summary(rom, result=None):
    """Freeze Start Adventure's conditional, compacted nine-record menu."""
    rom = bytes(rom)
    result = extract.extract(rom) if result is None else result
    records = _record_reference_map(result)

    predicate_conditions = (
        ({"event": 23, "required": True},),
        ({"event": 23, "required": False}, {"event": 13, "required": True}),
        ({"event": 23, "required": False}, {"event": 13, "required": True}),
        ({"event": 23, "required": False}, {"event": 13, "required": True}),
        (
            {"event": 23, "required": False},
            {"event": 13, "required": False},
            {"event": 11, "required": True},
        ),
        ({"event": 23, "required": False},),
        ({"event": 23, "required": False}, {"event": 10, "required": True}),
        ({"event": 23, "required": False},),
        ({"event": 23, "required": False}, {"event": 20, "required": True}),
    )
    additional_checks = {
        7: {"entry": "11:$4C29", "required_result": "C != 0"},
    }
    slots = []
    for slot, (index, name, handler, conditions) in enumerate(
        zip(
            ADVENTURE_START_INDICES,
            ADVENTURE_START_SLOT_NAMES,
            ADVENTURE_START_HANDLER_TARGETS,
            predicate_conditions,
        )
    ):
        record = records[(ADVENTURE_START_GROUP, index)]
        measured = layout.validate_direct_surface(
            rom,
            record.raw,
            start_x=ADVENTURE_START_ROW_START[0],
            start_y=ADVENTURE_START_ROW_START[1],
            right_edge=ADVENTURE_START_CANVAS_RIGHT_EDGE,
        )
        availability = {"event_conditions": list(conditions)}
        if slot in additional_checks:
            availability["additional_check"] = additional_checks[slot]
        slots.append(
            {
                "slot": slot,
                "name": name,
                "reference": [ADVENTURE_START_GROUP, index],
                "record": record.id,
                "source": record.source,
                "raw": record.raw.hex().upper(),
                "renderer_pixels": (
                    measured.rightmost_pen - ADVENTURE_START_ROW_START[0]
                ),
                "available_pixels": (
                    ADVENTURE_START_CANVAS_RIGHT_EDGE
                    - ADVENTURE_START_ROW_START[0]
                ),
                "availability": availability,
                "handler": extract.location(16, handler),
            }
        )

    def variant(name, enabled_slots):
        frames = ADVENTURE_START_VARIANT_FRAMES[name]
        rows = []
        for compact_row, (slot, frame) in enumerate(
            zip(enabled_slots, frames)
        ):
            record = records[
                (ADVENTURE_START_GROUP, ADVENTURE_START_INDICES[slot])
            ]
            start_x = ADVENTURE_START_ROW_START[0]
            start_y = (
                ADVENTURE_START_ROW_START[1]
                + compact_row * ADVENTURE_START_ROW_STEP
            )
            measured = layout.validate_direct_surface(
                rom,
                record.raw,
                start_x=start_x,
                start_y=start_y,
                right_edge=ADVENTURE_START_CANVAS_RIGHT_EDGE,
            )
            rows.append(
                {
                    "slot": slot,
                    "reference": [
                        ADVENTURE_START_GROUP,
                        ADVENTURE_START_INDICES[slot],
                    ],
                    "raw": record.raw.hex().upper(),
                    "start_pen": [start_x, start_y],
                    "final_pen": [measured.final_x, measured.final_y],
                    "observed_mode": 1,
                    "observed_frame": frame,
                }
            )
        tilemap = _adventure_start_menu_tilemap(len(enabled_slots))
        return {
            "enabled_slots": list(enabled_slots),
            "enabled_references": [row["reference"] for row in rows],
            "maximum_index": len(enabled_slots) - 1,
            "rows": rows,
            "tilemap": {
                "vram_bank": 0,
                "base": "$9800",
                "top_left_tile": list(ADVENTURE_START_TILEMAP_TOP_LEFT),
                "size_tiles": [ADVENTURE_START_TILEMAP_WIDTH, len(tilemap)],
                "sha1": sha1(
                    bytes(value for row in tilemap for value in row)
                ).hexdigest(),
            },
            "observed_final_frame": 8 if name == "maximum" else 4,
        }

    maximum = variant("maximum", ADVENTURE_START_MAXIMUM_ENABLED)
    sparse = variant("sparse", ADVENTURE_START_SPARSE_PROBE)
    sparse["compacted_ordinal_to_slot"] = [
        {"ordinal": ordinal, "slot": slot}
        for ordinal, slot in enumerate(ADVENTURE_START_SPARSE_PROBE)
    ]
    return {
        "handler": extract.location(*ADVENTURE_START_HANDLER),
        "screen": extract.location(*ADVENTURE_START_SCREEN),
        "header": {
            "entry": extract.location(*ADVENTURE_START_HEADER),
            "kind": "graphical header selected from enabled-row count",
        },
        "body": extract.location(*ADVENTURE_START_BODY),
        "predicate": extract.location(*ADVENTURE_START_PREDICATE),
        "enabled_count": extract.location(*ADVENTURE_START_ENABLED_COUNT),
        "ordinal_mapper": extract.location(*ADVENTURE_START_ORDINAL_MAPPER),
        "group": ADVENTURE_START_GROUP,
        "index_range": [
            ADVENTURE_START_INDICES[0], ADVENTURE_START_INDICES[-1]
        ],
        "slots": slots,
        "geometry": {
            "canvas_wram_bank": 7,
            "canvas_address": "$D000",
            "canvas_start_pen": list(ADVENTURE_START_ROW_START),
            "canvas_right_edge": ADVENTURE_START_CANVAS_RIGHT_EDGE,
            "available_pixels": (
                ADVENTURE_START_CANVAS_RIGHT_EDGE
                - ADVENTURE_START_ROW_START[0]
            ),
            "row_step": ADVENTURE_START_ROW_STEP,
            "visible_start_pen": [64, 19],
            "visible_right_edge": 152,
            "remap": "canvas columns 6..17 become visible BG columns 7..18",
        },
        "variants": {
            "maximum_predicate_consistent": maximum,
            "sparse_compaction_probe": sparse,
        },
        "dispatch": {
            "handler_table": extract.location(*ADVENTURE_START_HANDLER_TABLE),
            "targets": [
                extract.location(16, target)
                for target in ADVENTURE_START_HANDLER_TARGETS
            ],
            "behavior": (
                "controller returns a compact ordinal; bank 11 maps it back "
                "to an enabled original slot before this table is dispatched"
            ),
        },
        "synthetic_live_route": {
            "kind": "one-shot far-dispatch redirect with predicate-result hooks",
            "dispatcher": "0:$09AC",
            "target": extract.location(*ADVENTURE_START_SCREEN),
            "body_predicate_result_site": "4:$72D8",
            "count_predicate_result_site": "11:$517D",
            "screen_return_site": "18:$439D",
        },
        "evidence": {
            "handler": _code_evidence(
                rom, *ADVENTURE_START_HANDLER, ADVENTURE_START_HANDLER_SPAN
            ),
            "screen": _code_evidence(
                rom, *ADVENTURE_START_SCREEN, ADVENTURE_START_SCREEN_SPAN
            ),
            "header": _code_evidence(
                rom, *ADVENTURE_START_HEADER, ADVENTURE_START_HEADER_SPAN
            ),
            "body": _code_evidence(
                rom, *ADVENTURE_START_BODY, ADVENTURE_START_BODY_SPAN
            ),
            "tilemap": _code_evidence(
                rom, *ADVENTURE_START_TILEMAP, ADVENTURE_START_TILEMAP_SPAN
            ),
            "predicate": _code_evidence(
                rom,
                *ADVENTURE_START_PREDICATE,
                ADVENTURE_START_PREDICATE_SPAN,
            ),
            "ordinal_mapper": _code_evidence(
                rom,
                *ADVENTURE_START_ORDINAL_MAPPER,
                ADVENTURE_START_ORDINAL_MAPPER_SPAN,
            ),
            "enabled_count": _code_evidence(
                rom,
                *ADVENTURE_START_ENABLED_COUNT,
                ADVENTURE_START_ENABLED_COUNT_SPAN,
            ),
            "handler_table": _code_evidence(
                rom,
                *ADVENTURE_START_HANDLER_TABLE,
                ADVENTURE_START_HANDLER_TABLE_SPAN,
            ),
        },
    }


# The ordinary in-dungeon Items command first counts the 20 byte-sized object
# indices in WRAM bank 1 at $D2C1.  Each index resolves to an eight-byte item
# record in WRAM bank 2 at $D482+index*8.  Ten deterministic objects exercise
# the native name formatter's major carried-item families without depending on
# random floor generation or a battery save.  The resulting list uses the same
# 18-tile heading/body canvases and full-screen tilemap shape as Help -> Status.
ITEM_LIST_SURFACES = (
    PositionedSurface(
        name="item_list_heading",
        group=7,
        index=54,
        start_x=8,
        start_y=4,
        right_edge=layout.CANVAS_WIDTH_PIXELS,
        observed_mode=0x08,
        observed_frame=103,
    ),
    PositionedSurface(
        name="item_list_currency_suffix",
        group=7,
        index=49,
        start_x=136,
        start_y=4,
        right_edge=layout.CANVAS_WIDTH_PIXELS,
        observed_mode=0x08,
        observed_frame=103,
    ),
)
ITEM_INVENTORY_WRAM_BANK = 1
ITEM_INVENTORY_BASE = 0xD2C1
ITEM_INVENTORY_SLOTS = 20
ITEM_INVENTORY_SENTINEL = 0xFF
ITEM_OBJECT_WRAM_BANK = 2
ITEM_OBJECT_BASE = 0xD482
ITEM_OBJECT_SIZE = 8
ITEM_CATEGORY_BOUNDARY_TABLE = (120, 0x4000)
ITEM_CATEGORY_BOUNDARIES = (
    ("special", 0),
    ("weapon", 1),
    ("shield", 34),
    ("bracelet", 63),
    ("arrow", 90),
    ("food", 97),
    ("grass", 104),
    ("scroll", 124),
    ("staff", 158),
    ("jar", 184),
    ("money", 200),
    ("meat", 201),
    ("stairs", 202),
    ("trap_material", 203),
    ("tanuki", 204),
    ("silver_amulet", 207),
    ("gold_amulet", 208),
)
ITEM_CATEGORY_SEEDS = (
    ItemCategorySeed("weapon", 1, 1, 1, 2, bytes.fromhex("FE395D7A32"), 104),
    ItemCategorySeed("shield", 2, 34, 2, 3, bytes.fromhex("FE99A6A29048F01E"), 105),
    ItemCategorySeed(
        "bracelet", 3, 63, 3, 4, bytes.fromhex("FE41323548F020F032"), 105
    ),
    ItemCategorySeed("arrow", 4, 90, 4, 5, bytes.fromhex("FEF18048F024"), 106),
    ItemCategorySeed("food", 5, 97, 5, 6, bytes.fromhex("FE34456857"), 107),
    ItemCategorySeed("grass", 6, 104, 6, 7, bytes.fromhex("FE5337F026"), 107),
    ItemCategorySeed(
        "scroll", 7, 124, 7, 8, bytes.fromhex("FE3B36794148F02AF030"), 107
    ),
    ItemCategorySeed(
        "staff", 8, 158, 8, 9, bytes.fromhex("FE4B3643763B48F02EDC00DD"), 108
    ),
    ItemCategorySeed(
        "jar", 9, 184, 9, 10, bytes.fromhex("FE4D705D48F02CDC00DD"), 109
    ),
    ItemCategorySeed("money", 10, 200, 10, 11, bytes.fromhex("FE00B88FAD"), 109),
)
# Compatibility aliases for the first seeded object; callers that need the
# complete probe should iterate ITEM_CATEGORY_SEEDS.
ITEM_SEED_OBJECT_INDEX = ITEM_CATEGORY_SEEDS[0].object_index
ITEM_SEED_OBJECT = ITEM_CATEGORY_SEEDS[0].object_record
ITEM_SEED_BASE_REFERENCE = (4, ITEM_CATEGORY_SEEDS[0].item_index)
ITEM_SEED_NAME_PREFIX = bytes((0xFE,))
ITEM_NAME_START = (7, 1)
ITEM_NAME_RIGHT_EDGE = layout.CANVAS_WIDTH_PIXELS
ITEM_MONEY_ANCHOR = (136, 4)
ITEM_MONEY_OBSERVED_START = (129, 4)
ITEM_MONEY_OBSERVED_VALUE = 0
ITEM_MONEY_OBSERVED_FRAME = 103
ITEM_LIST_COUNT = (7, 0x5E04)
ITEM_LIST_COUNT_SPAN = 0x18
ITEM_SCREEN_GATE = (16, 0x6CB9)
ITEM_SCREEN_GATE_SPAN = 0x28
ITEM_HEADER_CONSTRUCTOR = (17, 0x460A)
ITEM_HEADER_CONSTRUCTOR_SPAN = 0x5A
ITEM_ROW_CONSTRUCTOR = (17, 0x45F2)
ITEM_ROW_CONSTRUCTOR_SPAN = 0x18
ITEM_NAME_FORMATTER = (120, 0x47C2)
ITEM_NAME_FORMATTER_SPAN = 0x15
ITEM_NAME_ROOT_GROUP = 12
ITEM_NAME_ROOT_ENTRIES = 123
ITEM_NAME_ROOT_MATCHER = (120, 0x4853)
ITEM_NAME_ROOT_MATCHER_SPAN = 0xB4
ITEM_NAME_ROOT_INPUT_BYTES = 7
ITEM_NAME_ROOT_DISABLED_INDICES = (69, 79, 114, 121)
ITEM_NAME_ROOT_PARTITIONS = (
    ("bracelet", 0, 26, 63),
    ("grass", 27, 46, 104),
    ("scroll", 47, 80, 124),
    ("staff", 81, 106, 158),
    ("jar", 107, 122, 184),
)
ITEM_TILEMAP_BASE = 0x9800
ITEM_TILEMAP_TOP_LEFT = (0, 0)
ITEM_TILEMAP_ROWS = STATUS_TILEMAP_ROWS

# The in-dungeon At Feet command uses the same compact header and item-name
# formatter as the ordinary Items screen, but its body is selected from the
# map cell under the player.  Empty cells draw no body text; traps resolve
# through the eight-slot floor trap table into group 17; item cells resolve an
# object index and pass it to the shared formatter at 17:$5484.  A leading FE
# in formatted item text shifts the physical pen four pixels from x=3 to x=7.
AT_FEET_ENTRY = (16, 0x4EAD)
AT_FEET_ENTRY_SPAN = 0x78
AT_FEET_BODY_RENDERER = (17, 0x559A)
AT_FEET_BODY_RENDERER_SPAN = 0x64
AT_FEET_CELL_CLASSIFIER = (0, 0x1089)
AT_FEET_TRAP_MAPPER = (0, 0x17FA)
AT_FEET_TRAP_MAPPER_SPAN = 0x0C
AT_FEET_ITEM_SELECTOR = (0, 0x106B)
AT_FEET_ITEM_RENDERER = (17, 0x5484)
AT_FEET_ITEM_RENDERER_SPAN = 0x5B
AT_FEET_ITEM_VALUE_RENDERER = (17, 0x55FE)
AT_FEET_ITEM_VALUE_RENDERER_SPAN = 0x50
AT_FEET_ATTRIBUTE_MAP = (17, 0x43B2)
AT_FEET_ATTRIBUTE_MAP_SPAN = 0x3F
AT_FEET_TRAP_REFERENCES = tuple((17, index) for index in range(1, 23))
AT_FEET_RELATED_NO_TRAP_REFERENCE = (17, 0)
AT_FEET_BODY_NOMINAL_START = (3, 1)
AT_FEET_BODY_FORMATTED_START = (7, 1)
AT_FEET_CURRENT_MONEY_RAW = bytes.fromhex("FEFEFEFE00")
AT_FEET_CURRENT_MONEY_START = (129, 4)
AT_FEET_CURRENT_MONEY_MODE = 0x01
AT_FEET_METADATA_SEED_OBJECT = bytes.fromhex("0101000001000000")
AT_FEET_METADATA_RUNTIME_FIELDS = (
    ("item_metadata", bytes.fromhex("FEFEE2E0E0"), 129, 1),
    ("item_value", bytes.fromhex("FEFE020000"), 28, 32),
)
AT_FEET_VALUE_SUFFIX_START = (48, 32)

# Selecting the minimally seeded club opens a Window-layer action surface.
# Boot progress leaves bit 1 set at $C12B, globally inhibiting ordinary item
# actions and exposing only Discard and Explain.  Clearing that bit leaves the
# same object/masks intact and exposes Equip, Throw and Place as well.  The
# eight coordinate slots are shared by all 16 object action classes.
ITEM_ACTION_INHIBITED_SURFACES = (
    PositionedSurface(
        name="item_action_discard",
        group=7,
        index=24,
        start_x=8,
        start_y=17,
        right_edge=56,
        observed_mode=0x08,
        observed_frame=201,
    ),
    PositionedSurface(
        name="item_action_explain",
        group=7,
        index=15,
        start_x=8,
        start_y=30,
        right_edge=56,
        observed_mode=0x08,
        observed_frame=201,
    ),
)
ITEM_ACTION_ORDINARY_WEAPON_SURFACES = (
    PositionedSurface(
        name="item_action_equip",
        group=7,
        index=1,
        start_x=8,
        start_y=17,
        right_edge=56,
        observed_mode=0x08,
        observed_frame=201,
    ),
    PositionedSurface(
        name="item_action_throw",
        group=7,
        index=13,
        start_x=8,
        start_y=30,
        right_edge=56,
        observed_mode=0x08,
        observed_frame=201,
    ),
    PositionedSurface(
        name="item_action_place",
        group=7,
        index=17,
        start_x=8,
        start_y=43,
        right_edge=56,
        observed_mode=0x08,
        observed_frame=201,
    ),
    PositionedSurface(
        name="item_action_discard",
        group=7,
        index=24,
        start_x=56,
        start_y=17,
        right_edge=104,
        observed_mode=0x08,
        observed_frame=202,
    ),
    PositionedSurface(
        name="item_action_explain",
        group=7,
        index=15,
        start_x=56,
        start_y=30,
        right_edge=104,
        observed_mode=0x08,
        observed_frame=202,
    ),
)
ITEM_ACTION_EQUIPPED_WEAPON_SURFACES = (
    PositionedSurface(
        name="item_action_remove",
        group=7,
        index=2,
        start_x=8,
        start_y=17,
        right_edge=56,
        observed_mode=0x08,
        observed_frame=851,
    ),
    PositionedSurface(
        name="item_action_throw",
        group=7,
        index=13,
        start_x=8,
        start_y=30,
        right_edge=56,
        observed_mode=0x08,
        observed_frame=851,
    ),
    PositionedSurface(
        name="item_action_place",
        group=7,
        index=17,
        start_x=8,
        start_y=43,
        right_edge=56,
        observed_mode=0x08,
        observed_frame=851,
    ),
    PositionedSurface(
        name="item_action_discard",
        group=7,
        index=24,
        start_x=56,
        start_y=17,
        right_edge=104,
        observed_mode=0x08,
        observed_frame=851,
    ),
    PositionedSurface(
        name="item_action_explain",
        group=7,
        index=15,
        start_x=56,
        start_y=30,
        right_edge=104,
        observed_mode=0x08,
        observed_frame=852,
    ),
)
# Compatibility alias for the original inhibited probe.
ITEM_ACTION_SURFACES = ITEM_ACTION_INHIBITED_SURFACES
ITEM_ACTION_NUMERIC_RAW = bytes.fromhex(
    "FEFEFEFE002EFEFEFEFEFEFEFEFEFE00"
)
ITEM_ACTION_NUMERIC_START = (96, 20)
ITEM_ACTION_NUMERIC_RIGHT_EDGE = layout.CANVAS_WIDTH_PIXELS
ITEM_ACTION_OBSERVED_FRAME = 201
ITEM_ACTION_WINDOW_TILEMAP_BASE = 0x9C00
ITEM_ACTION_WINDOW_REGISTER = (103, 16)
ITEM_ACTION_WINDOW_SCREEN_TOP_LEFT = (96, 16)
ITEM_ACTION_WINDOW_ROWS = (
    (124, 126, 126, 126, 126, 126, 126, 124),
    (125, 36, 37, 38, 39, 40, 41, 125),
    (125, 54, 55, 56, 57, 58, 59, 125),
    (125, 72, 73, 74, 75, 76, 77, 125),
    (125, 90, 91, 92, 93, 94, 95, 125),
    (125, 108, 109, 110, 111, 112, 113, 125),
    (125, 42, 43, 44, 45, 46, 47, 125),
    (125, 60, 61, 62, 63, 64, 65, 125),
    (125, 78, 79, 80, 81, 82, 83, 125),
    (125, 96, 97, 98, 99, 100, 101, 125),
    (125, 114, 115, 116, 117, 118, 119, 125),
    (124, 126, 126, 126, 126, 126, 126, 124),
    (124, 126, 126, 126, 126, 126, 126, 124),
    (125, 48, 49, 50, 51, 52, 53, 125),
    (125, 66, 67, 68, 69, 70, 71, 125),
    (124, 126, 126, 126, 126, 126, 126, 124),
)
ITEM_ACTION_COMMAND_POINTER_TABLE = (17, 0x71B7)
ITEM_ACTION_COMMAND_POINTER_TABLE_SPAN = 0x20
ITEM_ACTION_CLASS_COUNT = 16
ITEM_ACTION_WEAPON_COMMAND_TABLE = (17, 0x71E4)
ITEM_ACTION_WEAPON_COMMAND_TABLE_SPAN = 0x1C
ITEM_ACTION_COMMAND_FILTER = (17, 0x7367)
ITEM_ACTION_COMMAND_FILTER_SPAN = 0x1A2
ITEM_ACTION_COORDINATE_TABLE = (17, 0x7497)
ITEM_ACTION_COORDINATE_TABLE_SPAN = 0x10
ITEM_ACTION_COORDINATES = (
    (8, 17),
    (8, 30),
    (8, 43),
    (56, 17),
    (56, 30),
    (56, 43),
    (104, 17),
    (104, 30),
)
ITEM_ACTION_GLOBAL_GATE_ADDRESS = 0xC12B
ITEM_ACTION_GLOBAL_GATE_MASK = 0x02
ITEM_ACTION_INHIBITED_GATE_VALUE = 0x8F
ITEM_ACTION_ORDINARY_GATE_VALUE = 0x8D
ITEM_ACTION_SEEDED_PRIMARY_MASK = 0x1B
ITEM_ACTION_SEEDED_FALLBACK_MASK = 0x01
ITEM_ACTION_SLOT_RESOLVER = (17, 0x7509)
ITEM_ACTION_SLOT_RESOLVER_SPAN = 0x09
ITEM_ACTION_SELECTION_HANDLER = (16, 0x69B4)
ITEM_ACTION_SELECTION_HANDLER_SPAN = 0x135

# Confirming Equip dispatches the ordinary class-1 command into the dungeon
# engine.  Object byte 4 bit 4 is the stable equipment state: bank 120 tests
# it to choose Equip versus Remove, sets it on Equip, and clears it on Remove.
# The equipped inventory formatter replaces the neutral FE prefix with EA.
ITEM_EQUIPMENT_FLAG_BYTE = 4
ITEM_EQUIPMENT_FLAG_MASK = 0x10
ITEM_EQUIPMENT_HANDLER = (120, 0x4F55)
ITEM_EQUIPMENT_HANDLER_SPAN = 0x13
ITEM_EQUIP_FLAG_MUTATOR = (120, 0x50A8)
ITEM_EQUIP_FLAG_MUTATOR_SPAN = 0x0B
ITEM_REMOVE_FLAG_MUTATOR = (120, 0x520C)
ITEM_REMOVE_FLAG_MUTATOR_SPAN = 0x09
ITEM_EQUIPPED_WEAPON_RAW = bytes.fromhex("EA395D7A32")
ITEM_EQUIPPED_WEAPON_START = (3, 1)
ITEM_EQUIPPED_WEAPON_RIGHT_EDGE = layout.CANVAS_WIDTH_PIXELS
ITEM_EQUIPPED_WEAPON_OBSERVED_FRAME = 754
ITEM_EQUIPMENT_RESULT_MESSAGES = (
    (
        "equip",
        1,
        (11, 27),
        320,
        321,
        bytes.fromhex("395D7A325C24F33E32773B3FD1"),
    ),
    (
        "remove",
        2,
        (11, 28),
        970,
        971,
        bytes.fromhex("395D7A325C24F3496E3B3FD1"),
    ),
)
ITEM_EQUIPMENT_RESULT_MODE = 0x01
ITEM_EQUIPMENT_CACHE_ADDRESS = 0xC519

# Throw, Place and Discard all remove the selected object index from the
# 20-slot inventory through bank 7's compactor.  Place preserves the object
# and installs its index into the deterministic floor slot; Throw and Discard
# consume the object.  Each tuple freezes one independent clean-state route:
# name, command, compacted slot, inputs, last frame, source reference/source
# frame/render frame, expanded renderer payload, final object and floor value.
ITEM_INVENTORY_REMOVE = (7, 0x5AD6)
ITEM_INVENTORY_REMOVE_SPAN = 0x2E
ITEM_ACTION_RESULT_MODE = 0x01
ITEM_ACTION_RESULT_INVENTORY_AFTER = bytes(
    tuple(range(3, 12)) + (ITEM_INVENTORY_SENTINEL,) * 11
)
ITEM_FLOOR_OBJECT_WRAM_BANK = 3
ITEM_FLOOR_OBJECT_SLOT_ADDRESS = 0xD867
ITEM_ACTION_RESULT_ROUTES = (
    (
        "throw",
        13,
        1,
        ((250, "down"), (300, "a")),
        650,
        (11, 25),
        336,
        337,
        bytes.fromhex(
            "395D7A324924F389B3CB45303F633FD1FD"
            "FEFEFEFE01CF81AD9348C1A1D9BD5C303F333FD1"
        ),
        bytes(ITEM_OBJECT_SIZE),
        ITEM_INVENTORY_SENTINEL,
    ),
    (
        "place",
        17,
        2,
        ((250, "down"), (300, "down"), (350, "a")),
        700,
        (11, 95),
        367,
        368,
        bytes.fromhex("395D7A325C24F334313FD1"),
        ITEM_CATEGORY_SEEDS[0].object_record,
        ITEM_CATEGORY_SEEDS[0].object_index,
    ),
    (
        "discard",
        24,
        3,
        (
            (250, "down"),
            (300, "down"),
            (350, "down"),
            (400, "a"),
            (450, "left"),
            (500, "a"),
        ),
        850,
        (11, 96),
        541,
        542,
        bytes.fromhex("395D7A325C24F33C423FD1"),
        bytes(ITEM_OBJECT_SIZE),
        ITEM_INVENTORY_SENTINEL,
    ),
)
ITEM_THROW_DAMAGE_REFERENCE = (8, 1)
ITEM_THROW_TARGET_CACHE_ADDRESS = 0xC51A
ITEM_THROW_TARGET_EXPANDED_VALUE = "コッパ"
ITEM_DISCARD_CONFIRM_REFERENCE = (7, 175)
ITEM_DISCARD_CONFIRM_MODE = 0x04
ITEM_DISCARD_CONFIRM_SOURCE_FRAME = 401
ITEM_DISCARD_CONFIRM_RENDER_FRAME = 401

# Twelve additional clean-state representatives bound the remaining high-risk
# item families: three Equip/Remove cycles, five primary verbs, and four
# container/writing surfaces.  Shared action machinery is intentionally not
# re-probed for every item in its category.
ITEM_EQUIPMENT_FAMILY_ROUTES = (
    (
        "shield",
        1,
        bytes.fromhex("EA99A6A29048F01E"),
        (3, 12),
        805,
        370,
        371,
        bytes.fromhex("99A6A29048F01E5C24F33E32773B3FD1"),
        1070,
        1071,
        bytes.fromhex("99A6A29048F01E5C24F3496E3B3FD1"),
        950,
        1050,
        1300,
        (2, 13, 17, 24, 15),
    ),
    (
        "bracelet",
        2,
        bytes.fromhex("EA41323548F020F032"),
        (3, 23),
        855,
        420,
        421,
        bytes.fromhex("41323548F020F0325C24F33E32773B3FD1"),
        1170,
        1171,
        bytes.fromhex("41323548F020F0325C24F3496E3B3FD1"),
        1050,
        1150,
        1400,
        (2, 13, 17, 24, 15),
    ),
    (
        "arrow",
        3,
        bytes.fromhex("EAF18048F024"),
        (3, 34),
        906,
        469,
        470,
        bytes.fromhex("F18048F0245C24F33E32773B3FD1"),
        1268,
        1269,
        bytes.fromhex("F18048F0245C24F3496E3B3FD1"),
        1150,
        1250,
        1500,
        (2, 14, 17, 24, 15),
    ),
)
ITEM_PRIMARY_ACTION_ROUTES = (
    (
        "shoot",
        "arrow",
        3,
        14,
        1,
        ((400, "down"), (450, "a")),
        1000,
        (
            (
                (11, 25),
                490,
                491,
                bytes.fromhex(
                    "F18048F0244924F389B3CB45303F633FD1FD"
                    "FEFEFEFE01CF81AD9348C1A1D9BD5C303F333FD1"
                ),
                (8, 1),
            ),
        ),
        bytes(ITEM_OBJECT_SIZE),
    ),
    (
        "eat",
        "food",
        4,
        7,
        0,
        ((500, "a"),),
        1050,
        (
            ((11, 34), 519, 520, bytes.fromhex("344568575C24F3F022793FD1"), None),
            (
                (11, 63),
                558,
                562,
                bytes.fromhex(
                    "3A3171314E5D7D377567FDFEFEFEFE01F182F10267633FD1"
                ),
                None,
            ),
        ),
        bytes(ITEM_OBJECT_SIZE),
    ),
    (
        "drink",
        "grass",
        5,
        6,
        0,
        ((550, "a"),),
        1100,
        (
            (
                (11, 32),
                568,
                569,
                bytes.fromhex("5337F0265C24F3373C57453B42F0985D71D1"),
                None,
            ),
            (
                (11, 36),
                608,
                612,
                bytes.fromhex(
                    "3A317131111967FDFEFEFEFE01CF81AD93F10267633FD1"
                ),
                None,
            ),
        ),
        bytes(ITEM_OBJECT_SIZE),
    ),
    (
        "read",
        "scroll",
        6,
        4,
        0,
        ((600, "a"), (700, "a")),
        1350,
        (
            (
                (11, 31),
                719,
                720,
                bytes.fromhex("3B36794148F02AF0305C24F3F0945D71D1"),
                None,
            ),
            (
                (11, 60),
                777,
                778,
                bytes.fromhex("395949395D7A3245F34E4067314431D4"),
                None,
            ),
        ),
        bytes(ITEM_OBJECT_SIZE),
    ),
    (
        "wave",
        "staff",
        7,
        3,
        0,
        ((650, "a"),),
        1200,
        (
            (
                (11, 30),
                668,
                669,
                bytes.fromhex("4B3643763B48F02EDC00DD5C24F34B633FD1"),
                None,
            ),
        ),
        ITEM_CATEGORY_SEEDS[7].object_record,
    ),
)
ITEM_TARGET_SELECTOR_SURFACE = PositionedSurface(
    name="item_action_target_selector_heading",
    group=7,
    index=61,
    start_x=8,
    start_y=4,
    right_edge=layout.CANVAS_WIDTH_PIXELS,
    observed_mode=0x08,
    observed_frame=602,
)
ITEM_JAR_EMPTY_SURFACES = (
    PositionedSurface(
        name="item_jar_empty_body",
        group=7,
        index=27,
        start_x=3,
        start_y=1,
        right_edge=layout.CANVAS_WIDTH_PIXELS,
        observed_mode=0x08,
        observed_frame=704,
    ),
)
ITEM_JAR_CONTENTS_HEADING_RAW = bytes.fromhex("4D705D48F02CDC00DD")
ITEM_JAR_CONTENTS_HEADING_START = (8, 4)
ITEM_JAR_CONTENTS_HEADING_OBSERVED_FRAME = 702
ITEM_SPECIAL_ACTION_ROUTES = (
    (
        "jar_look",
        "jar",
        8,
        8,
        0,
        None,
        None,
        ((700, "a"),),
        1100,
        (8, 9, 13, 17, 24, 15),
        (),
    ),
    (
        "jar_insert_full",
        "jar",
        8,
        9,
        1,
        None,
        None,
        ((700, "down"), (750, "a"), (850, "a")),
        1450,
        (8, 9, 13, 17, 24, 15),
        (
            (
                (11, 77),
                869,
                870,
                bytes.fromhex("F02C48F120492431637B3174FD5232244931564431D1"),
                None,
            ),
        ),
    ),
    (
        "blank_scroll_write",
        "scroll",
        6,
        5,
        1,
        "scroll",
        146,
        ((600, "down"), (650, "a")),
        1100,
        (4, 5, 13, 17, 24, 15),
        (),
    ),
    (
        "suction_jar_suck",
        "jar",
        8,
        10,
        1,
        "jar",
        192,
        ((700, "down"), (750, "a")),
        1200,
        (8, 10, 11, 13, 17, 24, 15),
        (
            (
                (11, 89),
                767,
                768,
                bytes.fromhex("3B353B24444552243C3139514435633FD1"),
                None,
            ),
        ),
    ),
)
ITEM_WRITE_KEYBOARD_TILEMAP_ROWS = (
    (127, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 127),
    (127, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 127),
    (42,) * 20,
    (40,) + (42,) * 18 + (40,),
    (41, 133, 143, 133, 148, 36, 36, 36, 52, 104, 68, 50, 36, 36, 36, 52, 91, 88, 36, 41),
    (41,) + (36,) * 18 + (41,),
    (41, 60, 60, 80, 36, 36, 36, 36, 82, 117, 88, 36, 36, 36, 36, 36, 56, 60, 36, 41),
    (41,) + (36,) * 18 + (41,),
    (41, 48, 49, 50, 51, 52, 36, 73, 74, 75, 76, 77, 36, 94, 95, 96, 97, 98, 36, 41),
    (41,) + (36,) * 18 + (41,),
    (41, 53, 54, 55, 56, 57, 36, 78, 79, 80, 81, 82, 36, 99, 100, 101, 102, 236, 36, 41),
    (41,) + (36,) * 18 + (41,),
    (41, 58, 59, 60, 61, 62, 36, 83, 36, 84, 36, 85, 36, 0, 1, 2, 3, 4, 36, 41),
    (41,) + (36,) * 18 + (41,),
    (41, 63, 64, 65, 66, 67, 36, 86, 87, 88, 89, 90, 36, 5, 6, 7, 8, 9, 36, 41),
    (41,) + (36,) * 18 + (41,),
    (41, 68, 69, 70, 71, 72, 36, 91, 92, 93, 36, 212, 36, 211, 38, 238, 222, 223, 36, 41),
    (40,) + (42,) * 18 + (40,),
)
ITEM_WRITE_KEYBOARD_REGISTERS = (0xE7, 7, 144)


# Explain opens a full-screen group-6 description for the selected item.  The
# item name is reused as a direct group-4 heading; two right-aligned numbers
# are constructed separately.  Group 6 is exactly aligned with all 216 item
# indices and every stock record is finite and safe in mode 08.
ITEM_DESCRIPTION_GROUP = 6
ITEM_DESCRIPTION_ENTRIES = 216
ITEM_DETAIL_HEADER_SURFACES = (
    PositionedSurface(
        name="item_detail_seeded_weapon_heading",
        group=4,
        index=1,
        start_x=8,
        start_y=4,
        right_edge=layout.CANVAS_WIDTH_PIXELS,
        observed_mode=0x08,
        observed_frame=353,
    ),
)
ITEM_DETAIL_NUMERIC_FIELDS = (
    ("item_detail_base_strength", 0, 140, 12, 133, 359),
    ("item_detail_fusion_capacity", 4, 140, 23, 133, 359),
)
ITEM_DETAIL_SOURCE_REFERENCE = (ITEM_DESCRIPTION_GROUP, 1)
ITEM_DETAIL_SOURCE_OBSERVED_MODE = 0x08
ITEM_DETAIL_SOURCE_OBSERVED_FRAME = 355
ITEM_DETAIL_CALLER = (4, 0x451D)
ITEM_DETAIL_CALLER_SPAN = 0x74
ITEM_DETAIL_BODY_CONSTRUCTOR = (17, 0x4CAA)
ITEM_DETAIL_BODY_CONSTRUCTOR_SPAN = 0x107
ITEM_DETAIL_NUMERIC_CONSTRUCTOR = (17, 0x4DB1)
ITEM_DETAIL_NUMERIC_CONSTRUCTOR_SPAN = 0x48
ITEM_DETAIL_WINDOW_HIDDEN_REGISTER = (7, 144)

# Equipment objects carry a 24-bit synthesis bitset in bytes 5..7. The
# detail constructor maps the three item families to contiguous group-15
# ranges and draws every selected description directly at x=3.
ITEM_ABILITY_DESCRIPTION_GROUP = 15
ITEM_ABILITY_DESCRIPTION_ENTRIES = 69
ITEM_ABILITY_DESCRIPTION_START_X = 3
ITEM_ABILITY_DESCRIPTION_RIGHT_EDGE = layout.CANVAS_WIDTH_PIXELS
ITEM_ABILITY_DESCRIPTION_FAMILIES = (
    ("weapon", 0, 21, 24),
    ("shield", 22, 44, 24),
    ("bracelet", 45, 68, 13),
)
ITEM_ABILITY_MAPPING_TABLE = (17, 0x4CA4)
ITEM_ABILITY_MAPPING_RAW = bytes.fromhex("000F160F2D0F")
ITEM_ABILITY_RENDERER = (17, 0x4C2F)
ITEM_ABILITY_RENDERER_SPAN = 0x75
ITEM_ABILITY_BITSET_GETTER = (120, 0x4692)
ITEM_ABILITY_BITSET_GETTER_SPAN = 0x0C


# Each constructor is exactly $48 bytes and differs principally in the group
# and exclusive end index loaded before the shared pagination helper.  Every
# known caller supplies E=$0A, establishing ten visible rows per page.
DYNAMIC_LIST_FAMILIES = (
    DynamicListFamily(
        "wanderers_guide_topics", 19, 0, 9, 10, 0x51DD, 4, 0x40D5, 7, 73
    ),
    DynamicListFamily(
        "control_help_topics", 20, 0, 8, 10, 0x5225, 18, 0x4479, 7, 117
    ),
    DynamicListFamily(
        "technique_help_topics", 21, 0, 15, 10, 0x526D, 4, 0x41B8, 7, 114
    ),
)


def _location_at_offset(offset):
    bank = offset // extract.BANK_SIZE
    address = offset if bank == 0 else 0x4000 + offset % extract.BANK_SIZE
    return extract.location(bank, address)


def near_call_sites(rom, bank, target):
    """Return CALL target sites within one known code bank."""
    rom = bytes(rom)
    start = bank * extract.BANK_SIZE
    data = rom[start:start + extract.BANK_SIZE]
    needle = bytes((0xCD, target & 0xFF, target >> 8))
    out = []
    at = 0
    while True:
        found = data.find(needle, at)
        if found < 0:
            return tuple(out)
        out.append(_location_at_offset(start + found))
        at = found + 1


def far_call_sites(rom, target_bank, target, dispatchers=(0x09AC,)):
    """Return cross-bank target loads followed by a recognized dispatcher.

    ``0:$09AC`` is the game's banked-call trampoline.  ``0:$0A28`` has a
    superficially similar calling convention but is an LCD-safe memory writer,
    so accepting it here invents callers whenever its DE payload happens to
    resemble a bank/address pair.
    """
    rom = bytes(rom)
    found_offsets = set()
    for dispatcher in dispatchers:
        needle = bytes(
            (
                0x3E,
                target_bank,
                0x21,
                target & 0xFF,
                target >> 8,
                0xCD,
                dispatcher & 0xFF,
                dispatcher >> 8,
            )
        )
        at = 0
        while True:
            found = rom.find(needle, at)
            if found < 0:
                break
            # Report the LD HL,target opcode, matching the disassembly's
            # unambiguous reference location rather than the generic call.
            found_offsets.add(found + 2)
            at = found + 1
    return tuple(_location_at_offset(offset) for offset in sorted(found_offsets))


def call_graph(rom):
    """Return the direct entry's callers and all reusable wrapper consumers."""
    graph = {
        "direct_renderer": {
            "entry": extract.location(*DIRECT_RENDERER),
            "near": near_call_sites(rom, DIRECT_RENDERER[0], DIRECT_RENDERER[1]),
            "far": far_call_sites(
                rom, DIRECT_RENDERER[0], DIRECT_RENDERER[1], dispatchers=(0x09AC,)
            ),
        },
        "wrappers": {},
    }
    for address, name in POSITIONED_WRAPPERS.items():
        graph["wrappers"][name] = {
            "entry": extract.location(17, address),
            "near": near_call_sites(rom, 17, address),
            "far": far_call_sites(rom, 17, address),
        }
    return graph


def call_graph_coverage(rom):
    """Assign every discovered positioned-text consumer exactly once.

    Owner names are structural audit labels: most name the inventory section
    that freezes the corresponding screen contract, while implementation-only
    and source-composed paths remain explicit rather than being mislabeled as
    new standalone screens.
    """
    graph = call_graph(rom)
    apis = {"direct_renderer": graph["direct_renderer"]}
    apis.update(graph["wrappers"])

    out = {}
    for api, entry in apis.items():
        discovered = tuple(entry["near"]) + tuple(entry["far"])
        owner_rows = POSITIONED_CALL_SITE_OWNERS.get(api, ())
        assigned = tuple(
            location
            for _owner, locations in owner_rows
            for location in locations
        )
        counts = {location: assigned.count(location) for location in assigned}
        duplicates = sorted(
            location for location, count in counts.items() if count != 1
        )
        unassigned = sorted(set(discovered) - set(assigned))
        stale = sorted(set(assigned) - set(discovered))
        complete = not (unassigned or duplicates or stale) and (
            len(discovered) == len(assigned)
        )
        out[api] = {
            "entry": entry["entry"],
            "discovered_count": len(discovered),
            "assigned_count": len(assigned),
            "owners": [
                {
                    "owner": owner,
                    "site_count": len(locations),
                    "sites_sha1": sha1("\n".join(locations).encode("ascii")).hexdigest(),
                }
                for owner, locations in owner_rows
            ],
            "unassigned": unassigned,
            "duplicates": duplicates,
            "stale": stale,
            "complete": complete,
        }
    return {
        "api_count": len(out),
        "discovered_count": sum(
            row["discovered_count"] for row in out.values()
        ),
        "assigned_count": sum(row["assigned_count"] for row in out.values()),
        "complete": all(row["complete"] for row in out.values()),
        "apis": out,
    }


def _record_reference_map(result):
    out = {}
    for record in result["records"]:
        for reference in record.references:
            out[(reference.group, reference.index)] = record
    return out


def _positioned_surface_summary(rom, definitions, result=None):
    """Resolve and measure a finite set of observed positioned records."""
    rom = bytes(rom)
    result = extract.extract(rom) if result is None else result
    records = _record_reference_map(result)
    out = []
    for surface in definitions:
        record = records[(surface.group, surface.index)]
        measured = layout.validate_direct_surface(
            rom,
            record.raw,
            start_x=surface.start_x,
            start_y=surface.start_y,
            right_edge=surface.right_edge,
        )
        out.append(
            {
                "name": surface.name,
                "record": record.id,
                "reference": [surface.group, surface.index],
                "source": record.source,
                "start_pen": [surface.start_x, surface.start_y],
                "right_edge": surface.right_edge,
                "available_pixels": surface.available_pixels,
                "renderer_pixels": measured.rightmost_pen - surface.start_x,
                "final_pen": [measured.final_x, measured.final_y],
                "observed_mode": surface.observed_mode,
                "observed_frame": surface.observed_frame,
            }
        )
    return out


def opening_menu_summary(rom, result=None):
    """Resolve and measure the two clean-boot positioned menu records."""
    return _positioned_surface_summary(rom, OPENING_MENU_SURFACES, result=result)


def guide_menu_summary(rom, result=None):
    """Resolve the clean-boot Wanderer's Guide heading and first topic page."""
    return _positioned_surface_summary(rom, GUIDE_MENU_SURFACES, result=result)


def control_help_summary(rom, result=None):
    """Resolve the live first page of the in-game control-help list."""
    return _positioned_surface_summary(rom, CONTROL_HELP_SURFACES, result=result)


def technique_help_summary(rom, result=None):
    """Resolve the live first page of the in-game technique-help list."""
    return _positioned_surface_summary(rom, TECHNIQUE_HELP_SURFACES, result=result)


def main_menu_summary(rom, result=None):
    """Resolve the two left-column records observed on a fresh-game menu."""
    return _positioned_surface_summary(rom, MAIN_MENU_SURFACES, result=result)


def main_menu_contract_summary(rom, result=None):
    """Resolve every finite main-menu label and location-name candidate."""
    rom = bytes(rom)
    result = extract.extract(rom) if result is None else result
    records = _record_reference_map(result)

    slots = []
    for domain in MAIN_MENU_LEFT_SLOT_DOMAINS:
        rows = []
        for index in domain.indices:
            record = records[(domain.group, index)]
            measured = layout.validate_direct_surface(
                rom,
                record.raw,
                start_x=domain.start_x,
                start_y=domain.start_y,
                right_edge=domain.right_edge,
            )
            rows.append(
                {
                    "reference": [domain.group, index],
                    "record": record.id,
                    "source": record.source,
                    "renderer_pixels": measured.rightmost_pen - domain.start_x,
                }
            )
        slots.append(
            {
                "name": domain.name,
                "start_pen": [domain.start_x, domain.start_y],
                "visual_right_edge": domain.right_edge,
                "visual_budget": domain.right_edge - domain.start_x,
                "widest": dict(max(rows, key=lambda row: row["renderer_pixels"])),
                "records": rows,
            }
        )

    location_rows = []
    for index in range(
        MAIN_MENU_LOCATION_RANGE[0], MAIN_MENU_LOCATION_RANGE[1] + 1
    ):
        record = records[(MAIN_MENU_LOCATION_GROUP, index)]
        alignment_width = layout.direct_alignment_width(rom, record.raw)
        measured = layout.validate_direct_right_aligned_surface(
            rom,
            record.raw,
            left_edge=MAIN_MENU_LOCATION_LEFT_EDGE,
            anchor_x=MAIN_MENU_LOCATION_ANCHOR,
            start_y=MAIN_MENU_LOCATION_Y,
        )
        location_rows.append(
            {
                "index": index,
                "record": record.id,
                "source": record.source,
                "alignment_width": alignment_width,
                "start_x": measured.start_x,
                "renderer_pixels": measured.rightmost_pen - measured.start_x,
                "final_x": measured.final_x,
            }
        )

    observed = next(
        row for row in location_rows if row["index"] == 47
    )
    menu_selector_at = extract.file_offset(17, MAIN_MENU_SELECTOR_ADDRESS)
    location_selector_at = extract.file_offset(
        17, MAIN_MENU_LOCATION_SELECTOR_ADDRESS
    )
    alignment_at = extract.file_offset(*ALIGNMENT_ROUTINE)
    return {
        "left_slots": slots,
        "location_panel": {
            "group": MAIN_MENU_LOCATION_GROUP,
            "index_range": list(MAIN_MENU_LOCATION_RANGE),
            "entries": len(location_rows),
            "visual_left_edge": MAIN_MENU_LOCATION_LEFT_EDGE,
            "alignment_anchor": MAIN_MENU_LOCATION_ANCHOR,
            "alignment_budget": (
                MAIN_MENU_LOCATION_ANCHOR - MAIN_MENU_LOCATION_LEFT_EDGE
            ),
            "start_y": MAIN_MENU_LOCATION_Y,
            "observed": {
                **dict(observed),
                "reference": [MAIN_MENU_LOCATION_GROUP, observed["index"]],
                "observed_mode": 0x08,
                "observed_frame": 14,
            },
            "widest_alignment": dict(
                max(location_rows, key=lambda row: row["alignment_width"])
            ),
            "widest_renderer": dict(
                max(location_rows, key=lambda row: row["renderer_pixels"])
            ),
            "records": location_rows,
        },
        "evidence": {
            "left_slot_selector": {
                "location": extract.location(17, MAIN_MENU_SELECTOR_ADDRESS),
                "bytes": rom[
                    menu_selector_at:menu_selector_at + MAIN_MENU_SELECTOR_SPAN
                ].hex().upper(),
            },
            "location_selector": {
                "location": extract.location(
                    17, MAIN_MENU_LOCATION_SELECTOR_ADDRESS
                ),
                "bytes": rom[
                    location_selector_at:
                    location_selector_at + MAIN_MENU_LOCATION_SELECTOR_SPAN
                ].hex().upper(),
            },
            "alignment_width_and_subtraction": {
                "location": extract.location(*ALIGNMENT_ROUTINE),
                "bytes": rom[
                    alignment_at:alignment_at + ALIGNMENT_ROUTINE_SPAN
                ].hex().upper(),
            },
        },
    }


def _formatted_unsigned(value):
    """Model 17:$41B0's five/ten-column, FE-padded decimal output."""
    if not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("unsigned formatter input outside four-byte range")
    digits = bytes(int(character) for character in str(value))
    columns = 5 if value <= 0xFFFF else 10
    if len(digits) > columns:
        raise ValueError("decimal output does not fit native formatter columns")
    return b"\xFE" * (columns - len(digits)) + digits + b"\xFF"


def _code_evidence(rom, bank, address, span):
    at = extract.file_offset(bank, address)
    raw = rom[at:at + span]
    return {
        "location": extract.location(bank, address),
        "span": span,
        "sha1": sha1(raw).hexdigest(),
        "bytes": raw.hex().upper(),
    }


def main_menu_numeric_summary(rom):
    """Freeze the main menu's eight right-aligned numeric field contracts."""
    import english_font

    rom = bytes(rom)
    patched = english_font.install(rom)

    table_at = extract.file_offset(*EXPERIENCE_TABLE)
    table_raw = rom[table_at:table_at + 100 * 3]
    thresholds = [
        int.from_bytes(table_raw[offset:offset + 3], "little")
        for offset in range(0, len(table_raw), 3)
    ]
    if len(thresholds) != 100 or thresholds[-1] != 0xFFFFFF:
        raise ValueError("experience threshold table lacks its $FFFFFF sentinel")
    if thresholds[-2] != 6200000 or thresholds != sorted(thresholds):
        raise ValueError("unexpected level/experience threshold domain")

    fields = []
    for field in MAIN_MENU_NUMERIC_FIELDS:
        maximum = _formatted_unsigned(field.maximum)
        observed = _formatted_unsigned(field.observed_value)
        left_edge = field.left_obstruction_right + 1
        original = layout.validate_direct_right_aligned_surface(
            rom,
            maximum,
            left_edge=left_edge,
            anchor_x=field.anchor_x,
            start_y=field.anchor_y,
        )
        translated = layout.validate_direct_right_aligned_surface(
            patched,
            maximum,
            left_edge=left_edge,
            anchor_x=field.anchor_x,
            start_y=field.anchor_y,
        )
        observed_layout = layout.right_aligned_direct_layout(
            rom, observed, anchor_x=field.anchor_x, start_y=field.anchor_y
        )
        if observed_layout.start_x != field.observed_start_x:
            raise ValueError(
                "%s live start x=%d, formatter model produced x=%d"
                % (field.name, field.observed_start_x, observed_layout.start_x)
            )
        fields.append(
            {
                "name": field.name,
                "call_site": extract.location(17, field.call_site),
                "return_address": "$%04X" % (field.call_site + 3),
                "value_source": field.value_source,
                "input_bytes": 4,
                "maximum": field.maximum,
                "maximum_digits": len(str(field.maximum)),
                "maximum_basis": field.maximum_basis,
                "anchor": [field.anchor_x, field.anchor_y],
                "left_obstruction_right": field.left_obstruction_right,
                "left_edge": left_edge,
                "maximum_formatted": maximum.hex().upper(),
                "original_maximum": {
                    "alignment_width": layout.direct_alignment_width(rom, maximum),
                    "start_x": original.start_x,
                    "clearance_pixels": original.start_x - left_edge,
                },
                "english_maximum": {
                    "alignment_width": layout.direct_alignment_width(
                        patched, maximum
                    ),
                    "start_x": translated.start_x,
                    "clearance_pixels": translated.start_x - left_edge,
                },
                "observed": {
                    "value": field.observed_value,
                    "formatted": observed.hex().upper(),
                    "start_pen": [field.observed_start_x, field.anchor_y],
                    "mode": 0x08,
                    "frame": field.observed_frame,
                },
            }
        )

    return {
        "canvas": {
            "wram_bank": 7,
            "address": "$D000",
            "tile_columns": layout.CANVAS_TILE_COLUMNS,
            "tiles_copied": 0xFF,
            "vram_address": "$8800",
            "vram_tile_base": MAIN_MENU_CANVAS_TILE_BASE,
        },
        "visible_tilemap": {
            "base": "$%04X" % MAIN_MENU_TILEMAP_BASE,
            "right_panel": {
                "top_left": list(MAIN_MENU_RIGHT_TILEMAP_TOP_LEFT),
                "size_tiles": [11, 5],
                "source_canvas_columns": [7, 17],
                "source_canvas_rows": [0, 4],
                "rows": [list(row) for row in MAIN_MENU_RIGHT_TILEMAP_ROWS],
            },
            "bottom_panel": {
                "top_left": list(MAIN_MENU_BOTTOM_TILEMAP_TOP_LEFT),
                "size_tiles": [18, 5],
                "source_canvas_columns": [0, 17],
                "source_canvas_rows": [9, 13],
                "rows": [list(row) for row in MAIN_MENU_BOTTOM_TILEMAP_ROWS],
            },
        },
        "fields": fields,
        "experience_thresholds": {
            "location": extract.location(*EXPERIENCE_TABLE),
            "entries_before_sentinel": len(thresholds) - 1,
            "first": thresholds[0],
            "last": thresholds[-2],
            "sentinel": "$%06X" % thresholds[-1],
            "sha1": sha1(table_raw).hexdigest(),
        },
        "evidence": {
            "numeric_constructor": _code_evidence(
                rom,
                *MAIN_MENU_NUMERIC_CONSTRUCTOR,
                MAIN_MENU_NUMERIC_CONSTRUCTOR_SPAN,
            ),
            "unsigned_wrapper": _code_evidence(
                rom, *UNSIGNED_NUMERIC_WRAPPER, UNSIGNED_NUMERIC_WRAPPER_SPAN
            ),
            "decimal_formatter": _code_evidence(
                rom, *UNSIGNED_DECIMAL_FORMATTER, UNSIGNED_DECIMAL_FORMATTER_SPAN
            ),
            "canvas_upload": _code_evidence(
                rom, *MAIN_MENU_CANVAS_UPLOAD, MAIN_MENU_CANVAS_UPLOAD_SPAN
            ),
            "weapon_and_shield_totals": _code_evidence(
                rom, *WEAPON_TOTAL_EVIDENCE
            ),
            "strength_totals": _code_evidence(rom, *STRENGTH_TOTAL_EVIDENCE),
            "fullness_cap": _code_evidence(rom, *FULLNESS_CAP_EVIDENCE),
            "money_cap": _code_evidence(rom, *MONEY_CAP_EVIDENCE),
            "experience_getter": _code_evidence(
                rom, *EXPERIENCE_GETTER_EVIDENCE
            ),
        },
    }


def help_popup_summary(rom, result=None):
    """Resolve the four live Help-selector labels and their strip edges."""
    return _positioned_surface_summary(rom, HELP_POPUP_SURFACES, result=result)


def help_popup_remap_summary(rom, result=None):
    """Describe the Help selector's canvas strips and live tilemap remap."""
    rom = bytes(rom)
    result = extract.extract(rom) if result is None else result
    records = _record_reference_map(result)
    strips = []
    for strip in HELP_POPUP_STRIPS:
        first_column = strip.canvas_left // 8
        last_column = strip.canvas_right // 8 - 1
        tile_rows = []
        for canvas_row in range(3):
            tile_rows.append(
                [
                    HELP_POPUP_TILE_BASE
                    + canvas_row * layout.CANVAS_TILE_COLUMNS
                    + column
                    for column in range(first_column, last_column + 1)
                ]
            )
        strips.append(
            {
                "name": strip.name,
                "canvas_x": [strip.canvas_left, strip.canvas_right],
                "source_tile_columns": [first_column, last_column],
                "text_start_x": strip.text_start_x,
                "right_edge": strip.canvas_right,
                "text_budget": strip.canvas_right - strip.text_start_x,
                "references": [list(reference) for reference in strip.references],
                "records": [
                    {
                        "reference": list(reference),
                        "record": records[reference].id,
                        "source": records[reference].source,
                    }
                    for reference in strip.references
                ],
                "visible_tilemap_rows": [strip.visible_row, strip.visible_row + 2],
                "tile_ids": tile_rows,
            }
        )

    constructor_at = extract.file_offset(*HELP_POPUP_CONSTRUCTOR)
    coordinates_at = extract.file_offset(*HELP_POPUP_COORDINATE_TABLE)
    return {
        "canvas": {
            "wram_bank": 7,
            "address": "$D000",
            "tile_columns": layout.CANVAS_TILE_COLUMNS,
            "tile_rows_copied": 5,
            "tiles_copied": 0x5A,
            "vram_address": "$9240",
            "vram_tile_base": HELP_POPUP_TILE_BASE,
        },
        "constructor": {
            "location": extract.location(*HELP_POPUP_CONSTRUCTOR),
            "bytes": rom[
                constructor_at:constructor_at + HELP_POPUP_CONSTRUCTOR_SPAN
            ].hex().upper(),
        },
        "coordinate_table": {
            "location": extract.location(*HELP_POPUP_COORDINATE_TABLE),
            "bytes": rom[
                coordinates_at:
                coordinates_at + HELP_POPUP_COORDINATE_TABLE_SPAN
            ].hex().upper(),
            "pens_in_iteration_order": [
                [64, 14], [64, 2], [16, 13], [16, 1]
            ],
        },
        "strips": strips,
        "visible_tilemap": {
            "vram_bank": 0,
            "base": "$%04X" % HELP_POPUP_TILEMAP_BASE,
            "top_left_tile": list(HELP_POPUP_TILEMAP_TOP_LEFT),
            "size_tiles": [8, 8],
            "rows": [list(row) for row in HELP_POPUP_TILEMAP_ROWS],
        },
    }


def status_condition_summary(rom, result=None):
    """Resolve Help -> Status's live empty state and complete condition domain."""
    rom = bytes(rom)
    result = extract.extract(rom) if result is None else result
    records = _record_reference_map(result)

    table_at = extract.file_offset(*STATUS_CONDITION_POINTER_TABLE)
    cursor = table_at
    mappings = []
    for _ in range(0x100):
        pointer = int.from_bytes(rom[cursor:cursor + 2], "little")
        cursor += 2
        if pointer == 0:
            break
        if not 0x4000 <= pointer < 0x8000:
            raise ValueError("status-condition mapping pointer outside ROMX")
        mapping_at = extract.file_offset(17, pointer)
        label_index = rom[mapping_at]
        effect_ids = []
        for offset in range(1, 0x40):
            effect_id = rom[mapping_at + offset]
            if effect_id == 0xFF:
                break
            effect_ids.append(effect_id)
        else:
            raise ValueError("unterminated status-condition effect list")
        if not effect_ids:
            raise ValueError("status-condition label has no effect IDs")
        mappings.append((pointer, label_index, tuple(effect_ids)))
    else:
        raise ValueError("unterminated status-condition pointer table")

    if cursor - table_at != STATUS_CONDITION_POINTER_TABLE_SPAN:
        raise ValueError("unexpected status-condition pointer-table span")
    if len(mappings) != 48:
        raise ValueError("unexpected status-condition display domain")

    rows = []
    for pointer, label_index, effect_ids in mappings:
        record = records[(STATUS_CONDITION_GROUP, label_index)]
        measured = layout.validate_direct_surface(
            rom,
            record.raw,
            start_x=1,
            start_y=1,
            right_edge=layout.CANVAS_WIDTH_PIXELS,
        )
        rows.append(
            {
                "label_index": label_index,
                "reference": [STATUS_CONDITION_GROUP, label_index],
                "record": record.id,
                "source": record.source,
                "effect_ids": list(effect_ids),
                "mapping_location": extract.location(17, pointer),
                "renderer_pixels": measured.rightmost_pen - 1,
                "final_x": measured.final_x,
            }
        )

    mapped_effect_ids = sorted(
        effect_id for row in rows for effect_id in row["effect_ids"]
    )
    effect_domain = list(
        range(STATUS_CONDITION_EFFECT_RANGE[0], STATUS_CONDITION_EFFECT_RANGE[1] + 1)
    )
    if len(mapped_effect_ids) != len(set(mapped_effect_ids)):
        raise ValueError("status-condition effect ID is mapped more than once")

    return {
        "observed_surfaces": _positioned_surface_summary(
            rom, STATUS_CONDITION_SURFACES, result=result
        ),
        "selection": {
            "group": STATUS_CONDITION_GROUP,
            "effect_id_range": list(STATUS_CONDITION_EFFECT_RANGE),
            "mapped_effects": len(mapped_effect_ids),
            "unmapped_effect_ids": sorted(set(effect_domain) - set(mapped_effect_ids)),
            "display_entries": len(rows),
            "page_rows": STATUS_CONDITION_PAGE_ROWS,
            "row_start_pens": [
                [1, 1 + 11 * row] for row in range(STATUS_CONDITION_PAGE_ROWS)
            ],
            "right_edge": layout.CANVAS_WIDTH_PIXELS,
            "visual_budget": layout.CANVAS_WIDTH_PIXELS - 1,
            "widest": dict(max(rows, key=lambda row: row["renderer_pixels"])),
            "records": rows,
        },
        "canvas": {
            "wram_bank": 7,
            "address": "$D000",
            "tile_columns": layout.CANVAS_TILE_COLUMNS,
            "heading": {
                "size_tiles": [18, 2],
                "one_bitplane_bytes": 0x120,
                "vram_address": "$9000",
                "vram_tile_base": 0x00,
            },
            "body": {
                "size_tiles": [18, 14],
                "one_bitplane_bytes": 0x7E0,
                "vram_address": "$8800",
                "vram_tile_base": 0x80,
            },
        },
        "visible_tilemap": {
            "vram_bank": 0,
            "base": "$%04X" % STATUS_TILEMAP_BASE,
            "top_left_tile": list(STATUS_TILEMAP_TOP_LEFT),
            "size_tiles": [20, 18],
            "rows": [list(row) for row in STATUS_TILEMAP_ROWS],
        },
        "evidence": {
            "caller_and_page_offset": _code_evidence(
                rom, *STATUS_CONDITION_CALLER, STATUS_CONDITION_CALLER_SPAN
            ),
            "heading_constructor": _code_evidence(
                rom,
                *STATUS_HEADING_CONSTRUCTOR,
                STATUS_HEADING_CONSTRUCTOR_SPAN,
            ),
            "body_constructor": _code_evidence(
                rom, *STATUS_BODY_CONSTRUCTOR, STATUS_BODY_CONSTRUCTOR_SPAN
            ),
            "active_effect_test": _code_evidence(
                rom, *STATUS_ACTIVE_TEST, STATUS_ACTIVE_TEST_SPAN
            ),
            "active_effect_count": _code_evidence(
                rom, *STATUS_ACTIVE_COUNT, STATUS_ACTIVE_COUNT_SPAN
            ),
            "condition_selector": _code_evidence(
                rom,
                *STATUS_CONDITION_SELECTOR,
                STATUS_CONDITION_SELECTOR_SPAN,
            ),
            "pointer_table": _code_evidence(
                rom,
                *STATUS_CONDITION_POINTER_TABLE,
                STATUS_CONDITION_POINTER_TABLE_SPAN,
            ),
            "mapping_blob": _code_evidence(
                rom,
                *STATUS_CONDITION_MAPPING_BLOB,
                STATUS_CONDITION_MAPPING_BLOB_SPAN,
            ),
        },
    }


def dungeon_selector_summary(rom, result=None):
    """Resolve the training/travel selector's complete group-24 domains."""
    rom = bytes(rom)
    result = extract.extract(rom) if result is None else result
    records = _record_reference_map(result)

    def domain_rows(indices):
        rows = []
        for index in indices:
            record = records[(DUNGEON_SELECTOR_GROUP, index)]
            measured = layout.validate_direct_surface(
                rom,
                record.raw,
                start_x=DUNGEON_SELECTOR_ROW_START[0],
                start_y=DUNGEON_SELECTOR_ROW_START[1],
                right_edge=DUNGEON_SELECTOR_ROW_RIGHT_EDGE,
            )
            rows.append(
                {
                    "index": index,
                    "reference": [DUNGEON_SELECTOR_GROUP, index],
                    "record": record.id,
                    "source": record.source,
                    "renderer_pixels": (
                        measured.rightmost_pen - DUNGEON_SELECTOR_ROW_START[0]
                    ),
                    "final_x": measured.final_x,
                }
            )
        return rows

    training_rows = domain_rows(DUNGEON_SELECTOR_TRAINING_INDICES)
    travel_rows = domain_rows(DUNGEON_SELECTOR_TRAVEL_INDICES)
    training_observed = _positioned_surface_summary(
        rom, DUNGEON_SELECTOR_TRAINING_SURFACES, result=result
    )
    travel_observed = _positioned_surface_summary(
        rom, DUNGEON_SELECTOR_TRAVEL_SURFACES, result=result
    )
    shared = {
        "group": DUNGEON_SELECTOR_GROUP,
        "row_start": list(DUNGEON_SELECTOR_ROW_START),
        "row_step": DUNGEON_SELECTOR_ROW_STEP,
        "right_edge": DUNGEON_SELECTOR_ROW_RIGHT_EDGE,
        "visual_budget": (
            DUNGEON_SELECTOR_ROW_RIGHT_EDGE
            - DUNGEON_SELECTOR_ROW_START[0]
        ),
        "screen": {
            "lcdc": "$E7",
            "registers": {"wx": 7, "wy": 144},
            "vram_bank": 0,
            "base": "$%04X" % STATUS_TILEMAP_BASE,
            "top_left_tile": list(STATUS_TILEMAP_TOP_LEFT),
            "size_tiles": [20, 18],
            "rows": [list(row) for row in STATUS_TILEMAP_ROWS],
            "observed_frame": DUNGEON_SELECTOR_SYNTHETIC_ROUTE[
                "tilemap_capture_frame"
            ],
        },
    }
    return {
        "shared": shared,
        "variants": {
            "training": {
                "heading_reference": [7, 131],
                "input_c": DUNGEON_SELECTOR_SYNTHETIC_ROUTE[
                    "training_input_c"
                ],
                "fixed_indices": [0],
                "conditional_indices": list(range(3, 12)),
                "maximum_rows": 10,
                "row_start_pens": [
                    [
                        DUNGEON_SELECTOR_ROW_START[0],
                        DUNGEON_SELECTOR_ROW_START[1]
                        + DUNGEON_SELECTOR_ROW_STEP * row,
                    ]
                    for row in range(10)
                ],
                "widest": dict(
                    max(training_rows, key=lambda row: row["renderer_pixels"])
                ),
                "records": training_rows,
                "observed_surfaces": training_observed,
            },
            "travel": {
                "heading_reference": [7, 132],
                "input_c": DUNGEON_SELECTOR_SYNTHETIC_ROUTE[
                    "travel_input_c"
                ],
                "fixed_indices": [3, 4, 5, 6],
                "conditional_indices": [7],
                "maximum_rows": 5,
                "row_start_pens": [
                    [
                        DUNGEON_SELECTOR_ROW_START[0],
                        DUNGEON_SELECTOR_ROW_START[1]
                        + DUNGEON_SELECTOR_ROW_STEP * row,
                    ]
                    for row in range(5)
                ],
                "widest": dict(
                    max(travel_rows, key=lambda row: row["renderer_pixels"])
                ),
                "records": travel_rows,
                "observed_surfaces": travel_observed,
            },
        },
        "complete_union": {
            "entries": len(set(DUNGEON_SELECTOR_TRAINING_INDICES)
                           | set(DUNGEON_SELECTOR_TRAVEL_INDICES)),
            "indices": sorted(
                set(DUNGEON_SELECTOR_TRAINING_INDICES)
                | set(DUNGEON_SELECTOR_TRAVEL_INDICES)
            ),
        },
        "synthetic_live_route": {
            "kind": "one-shot far-dispatch redirect from deterministic gameplay",
            "dispatcher": extract.location(
                *DUNGEON_SELECTOR_SYNTHETIC_ROUTE["dispatcher"]
            ),
            "target": extract.location(
                DUNGEON_SELECTOR_SYNTHETIC_ROUTE["target_bank"],
                DUNGEON_SELECTOR_SYNTHETIC_ROUTE["target_address"],
            ),
            "final_frame": DUNGEON_SELECTOR_SYNTHETIC_ROUTE["final_frame"],
        },
        "evidence": {
            "entry_and_header_branch": _code_evidence(
                rom, *DUNGEON_SELECTOR_ENTRY, DUNGEON_SELECTOR_ENTRY_SPAN
            ),
            "body_and_finite_domains": _code_evidence(
                rom,
                *DUNGEON_SELECTOR_BODY_CONSTRUCTOR,
                DUNGEON_SELECTOR_BODY_CONSTRUCTOR_SPAN,
            ),
        },
    }


def _runtime_draw(raw, start_x, start_y, mode, frame, renderer="direct"):
    raw = bytes(raw)
    return {
        "renderer": renderer,
        "raw": raw.hex().upper(),
        "staged_text": codec.decode(raw),
        "start_pen": [start_x, start_y],
        "mode": mode,
        "frame": frame,
    }


def history_ranking_summary(rom, result=None):
    """Freeze Adventure History and all four Wanderer Ranking views."""
    rom = bytes(rom)
    result = extract.extract(rom) if result is None else result
    records = _record_reference_map(result)
    runtime_contract = layout.english_runtime_width_contract()

    history_rows = []
    for index in ADVENTURE_HISTORY_INDICES:
        record = records[(ADVENTURE_HISTORY_GROUP, index)]
        measured = layout.source_layout(
            rom, record.raw, mode=0x08, runtime_contract=runtime_contract
        )
        if len(measured.lines) != 1:
            raise ValueError("adventure-history record is not a single row")
        line = measured.lines[0]
        history_rows.append(
            {
                "index": index,
                "reference": [ADVENTURE_HISTORY_GROUP, index],
                "record": record.id,
                "source": record.source,
                "source_bytes": record.raw.hex().upper(),
                "composer_pixels_with_bounded_runtime_maxima": (
                    line.composer_pixels
                ),
                "renderer_pixels_with_bounded_runtime_maxima": (
                    line.renderer_pixels
                ),
                "dynamic_expansions": [
                    {
                        "offset": expansion.offset,
                        "kind": expansion.kind,
                        "bounded": expansion.bounded,
                    }
                    for expansion in measured.dynamic_expansions
                ],
                "unresolved_dynamic_offsets": list(
                    measured.unresolved_dynamic_offsets
                ),
            }
        )

    def record_raw(group, index):
        return records[(group, index)].raw

    history_draws = [
        _runtime_draw(record_raw(7, 74), 8, 4, 8, 8),
    ]
    history_frames = (10, 10, 11, 12, 13, 14)
    for row, frame in enumerate(history_frames):
        history_draws.append(
            _runtime_draw(record_raw(16, row), 3, 1 + row * 11, 8, frame)
        )
    history_dynamic_raw = (
        bytes.fromhex("F12AF0AAF002AB94F06EF0AE06050503058FD9AD87A780"),
        bytes.fromhex("F1EAF1ECF0A848354E7545")
        + _formatted_unsigned(0)[:-1]
        + bytes.fromhex("F066F076F078"),
        bytes.fromhex("F18EF0DC48F1904245")
        + _formatted_unsigned(0)[:-1]
        + bytes.fromhex("F066F076F078"),
        bytes.fromhex("93AD9BAEAD48F1E845")
        + _formatted_unsigned(0)[:-1]
        + bytes.fromhex("F066F076F078"),
    )
    for row, (raw, frame) in enumerate(
        zip(history_dynamic_raw, (15, 16, 18, 19)), start=6
    ):
        history_draws.append(
            _runtime_draw(raw, 3, 1 + row * 11, 8, frame)
        )

    rank = _formatted_unsigned(1)[:-1]
    score = _formatted_unsigned(1234567)[:-1]
    floor = _formatted_unsigned(99)[:-1]
    level = _formatted_unsigned(42)[:-1]
    maximum_hp = _formatted_unsigned(123)[:-1]
    maximum_strength = _formatted_unsigned(18)[:-1]
    turns = _formatted_unsigned(54321)[:-1]
    rescues = _formatted_unsigned(5)[:-1] + record_raw(18, 56)[4:]

    heading = record_raw(*RANKING_HEADING_REFERENCE)
    top_row = (
        (rank, 11, 1),
        (score, 48, 1),
        (floor, 125, 1),
        (record_raw(18, 41), 16, 1),
        (record_raw(7, 62), 90, 1),
        (record_raw(7, 50), 137, 1),
    )
    current_draws = [_runtime_draw(heading, 8, 4, 8, 5)]
    for offset, (raw, x, y) in enumerate(top_row):
        frame = (8, 9, 9, 9, 9, 10)[offset]
        current_draws.append(_runtime_draw(raw, x, y, 8, frame))
    current_draws.append(_runtime_draw(record_raw(18, 0), 0, 12, 8, 10))

    paged_draws = [_runtime_draw(heading, 8, 4, 8, 4)]
    for offset, (raw, x, y) in enumerate(top_row):
        frame = (6, 6, 6, 7, 7, 7)[offset]
        paged_draws.append(_runtime_draw(raw, x, y, 8, frame))
    paged_draws.extend(
        (
            _runtime_draw(level, 126, 12, 8, 7),
            _runtime_draw(record_raw(24, 35), 0, 12, 8, 7),
            _runtime_draw(record_raw(18, 46), 107, 12, 8, 8),
        )
    )

    detail_specs = (
        (heading, 8, 4, 0),
        (rank, 11, 1, 2),
        (score, 48, 1, 3),
        (floor, 125, 1, 4),
        (record_raw(18, 41), 16, 1, 5),
        (record_raw(7, 62), 90, 1, 5),
        (record_raw(7, 50), 137, 1, 6),
        (level, 126, 12, 6),
        (record_raw(24, 35), 0, 12, 6),
        (record_raw(18, 46), 107, 12, 8),
        (record_raw(22, 46), 3, 23, 9),
        (record_raw(22, 67), 78, 23, 10),
        (record_raw(22, 57), 3, 34, 12),
        (rescues, 0, 34, 14),
        (RANKING_SEEDED_RECORD[15:19], 0, 45, 15),
        (record_raw(18, 57), 36, 45, 15),
        (maximum_hp, 73, 45, 16),
        (record_raw(18, 58), 93, 45, 17),
        (maximum_strength, 130, 45, 18),
        (bytes.fromhex("24242405271104270706"), 2, 56, 19),
        (turns, 88, 56, 21),
        (record_raw(18, 55), 118, 56, 21),
        (record_raw(18, 59), 0, 67, 22),
        (record_raw(18, 60), 74, 67, 22),
        (record_raw(18, 0), 0, 78, 22),
        (RANKING_SEEDED_MEMO, 3, 89, 24),
        (record_raw(18, 54), 3, 100, 26),
    )
    detail_draws = [
        _runtime_draw(raw, x, y, 8 if offset == 0 else 1, frame)
        for offset, (raw, x, y, frame) in enumerate(detail_specs)
    ]
    message_draws = [_runtime_draw(heading, 8, 4, 8, 0)]
    message_source_draws = [
        _runtime_draw(
            RANKING_SEEDED_FINAL_MESSAGE,
            3,
            1,
            8,
            2,
            renderer="full_source",
        )
    ]

    def domain(group, indices):
        return [
            {
                "index": index,
                "reference": [group, index],
                "record": records[(group, index)].id,
                "source": records[(group, index)].source,
            }
            for index in indices
        ]

    numeric_fields = []
    seed_values = {
        "rank": 1,
        "score": 1234567,
        "floor": 99,
        "level": 42,
        "rescues": 5,
        "maximum_hp": 123,
        "maximum_strength": 18,
        "turn_count": 54321,
    }
    for name, byte_count, anchor_x, anchor_y, maximum in RANKING_NUMERIC_FIELDS:
        numeric_fields.append(
            {
                "name": name,
                "input_bytes": byte_count,
                "maximum": maximum,
                "maximum_digits": len(str(maximum)),
                "anchor_x": anchor_x,
                "anchor_y": anchor_y,
                "seeded_value": seed_values[name],
                "seeded_staged_bytes": _formatted_unsigned(
                    seed_values[name]
                )[:-1].hex().upper(),
            }
        )

    evidence = {
        "adventure_entry": _code_evidence(
            rom, *ADVENTURE_HISTORY_ENTRY, ADVENTURE_HISTORY_ENTRY_SPAN
        ),
        "adventure_body": _code_evidence(
            rom, *ADVENTURE_HISTORY_BODY, ADVENTURE_HISTORY_BODY_SPAN
        ),
        "adventure_flag_selector": _code_evidence(
            rom,
            *ADVENTURE_HISTORY_FLAG_SELECTOR,
            ADVENTURE_HISTORY_FLAG_SELECTOR_SPAN,
        ),
        "adventure_dynamic_values": _code_evidence(
            rom,
            *ADVENTURE_HISTORY_DYNAMIC_VALUES,
            ADVENTURE_HISTORY_DYNAMIC_VALUES_SPAN,
        ),
        "ranking_screens": {},
        "record_getters": _code_evidence(rom, 11, 0x5655, 0x162),
        "extended_record_getters": _code_evidence(rom, 11, 0x59A8, 0x35),
        "sram_record_locators": _code_evidence(rom, 11, 0x5F42, 0x2A),
    }
    for name, (entry, entry_span, body, body_span) in (
        RANKING_SCREEN_CONSTRUCTORS.items()
    ):
        evidence["ranking_screens"][name] = {
            "entry": _code_evidence(rom, *entry, entry_span),
            "body": _code_evidence(rom, *body, body_span),
        }

    widest_history = max(
        history_rows,
        key=lambda row: row["renderer_pixels_with_bounded_runtime_maxima"],
    )
    return {
        "adventure_history": {
            "heading_reference": [7, 74],
            "record_group": ADVENTURE_HISTORY_GROUP,
            "index_range": [0, 39],
            "entries": len(history_rows),
            "page_rows": ADVENTURE_HISTORY_PAGE_ROWS,
            "row_start": [3, 1],
            "row_step": 11,
            "right_edge": layout.CANVAS_WIDTH_PIXELS,
            "visual_budget": layout.CANVAS_WIDTH_PIXELS - 3,
            "flag_storage": {
                "address": "$%04X" % ADVENTURE_HISTORY_FLAG_BASE,
                "bytes": 5,
                "bits": 40,
            },
            "widest_bounded_stock_row": dict(widest_history),
            "records": history_rows,
            "seeded_first_page": {
                "enabled_indices": list(range(10)),
                "flag_bytes": "FF03000000",
                "expected_direct_draws": history_draws,
            },
        },
        "wanderer_ranking": {
            "heading_reference": list(RANKING_HEADING_REFERENCE),
            "maximum_records": RANKING_LIST_MAX_RECORDS,
            "paged_rows": RANKING_PAGED_ROWS,
            "screens": {
                name: {
                    "entry": extract.location(*entry),
                    "body": extract.location(*body),
                }
                for name, (entry, _entry_span, body, _body_span) in (
                    RANKING_SCREEN_CONSTRUCTORS.items()
                )
            },
            "record_schema": {
                "address": "$%04X" % RANKING_RECORD_ADDRESS,
                "size": RANKING_RECORD_SIZE,
                "fields": [
                    {
                        "name": name,
                        "offset": offset,
                        "size": size,
                        "render_use": render_use,
                    }
                    for name, offset, size, render_use in RANKING_SCHEMA
                ],
            },
            "extended_schema": {
                "address": "$%04X" % RANKING_EXTENDED_ADDRESS,
                "size": RANKING_EXTENDED_SIZE,
                "memo": {"offset": 0, "size": RANKING_MEMO_SIZE},
                "final_message": {
                    "offset": RANKING_MEMO_SIZE,
                    "size": RANKING_FINAL_MESSAGE_SIZE,
                },
            },
            "domains": {
                "locations": domain(24, RANKING_LOCATION_INDICES),
                "outcomes": domain(18, RANKING_OUTCOME_INDICES),
                "titles": {
                    name: domain(22, indices)
                    for name, indices in RANKING_TITLE_DOMAINS.items()
                },
                "fixed_labels": [
                    {
                        "reference": list(reference),
                        "record": records[reference].id,
                        "source": records[reference].source,
                    }
                    for reference in RANKING_FIXED_REFERENCES
                ],
            },
            "numeric_fields": numeric_fields,
            "seed": {
                "record_bytes": RANKING_SEEDED_RECORD.hex().upper(),
                "memo_bytes": RANKING_SEEDED_MEMO.hex().upper(),
                "final_message_bytes": (
                    RANKING_SEEDED_FINAL_MESSAGE.hex().upper()
                ),
                "resolved_references": {
                    "location": [24, 35],
                    "outcome": [18, 0],
                    "wanderer_title": [22, 46],
                    "trap_title": [22, 67],
                    "cooking_title": [22, 57],
                    "weapon": [18, 59],
                    "shield": [18, 60],
                },
            },
            "seeded_routes": {
                "current_record_list": {
                    "expected_direct_draws": current_draws,
                    "expected_source_draws": [
                        _runtime_draw(
                            record_raw(18, 44),
                            4,
                            4,
                            4,
                            18,
                            renderer="full_source",
                        )
                    ],
                },
                "paged_record_list": {
                    "expected_direct_draws": paged_draws,
                    "expected_source_draws": [],
                },
                "record_detail": {
                    "expected_direct_draws": detail_draws,
                    "expected_source_draws": [],
                },
                "final_message": {
                    "expected_direct_draws": message_draws,
                    "expected_source_draws": message_source_draws,
                },
            },
        },
        "synthetic_live_route": {
            "kind": "one-shot far-dispatch redirect with staged populated records",
            "dispatcher": extract.location(
                *RANKING_SYNTHETIC_ROUTE["dispatcher"]
            ),
            "target_bank": RANKING_SYNTHETIC_ROUTE["target_bank"],
            "entries": {
                name: extract.location(
                    RANKING_SYNTHETIC_ROUTE["target_bank"], address
                )
                for name, address in RANKING_SYNTHETIC_ROUTE["entries"].items()
            },
            "final_frame": RANKING_SYNTHETIC_ROUTE["final_frame"],
        },
        "canvas": {
            "wram_bank": 7,
            "address": "$D000",
            "tile_columns": layout.CANVAS_TILE_COLUMNS,
            "heading_size_tiles": [18, 2],
            "body_size_tiles": [18, 14],
            "synthetic_screen_mapping": (
                "not frozen: record-detail inherits parent menu mapping state"
            ),
        },
        "evidence": evidence,
    }


def _item_action_command_domains(rom, records):
    """Parse the 16 pointer-selected, zero-terminated command tables."""
    pointer_at = extract.file_offset(*ITEM_ACTION_COMMAND_POINTER_TABLE)
    pointer_raw = rom[
        pointer_at:pointer_at + ITEM_ACTION_COMMAND_POINTER_TABLE_SPAN
    ]
    if len(pointer_raw) != ITEM_ACTION_CLASS_COUNT * 2:
        raise ValueError("truncated item action-command pointer table")

    classes = []
    for action_class in range(ITEM_ACTION_CLASS_COUNT):
        pointer = int.from_bytes(
            pointer_raw[action_class * 2:action_class * 2 + 2], "little"
        )
        if not 0x4000 <= pointer < 0x8000:
            raise ValueError("invalid item action-command pointer $%04X" % pointer)
        table_at = extract.file_offset(17, pointer)
        entries = []
        cursor = 0
        while cursor < 0x100:
            command_index = rom[table_at + cursor]
            if command_index == 0:
                break
            primary_mask = rom[table_at + cursor + 1]
            fallback_mask = rom[table_at + cursor + 2]
            command_record = records[(7, command_index)]
            entries.append(
                {
                    "command_index": command_index,
                    "reference": [7, command_index],
                    "record": command_record.id,
                    "source": command_record.source,
                    "primary_flag_mask": "$%02X" % primary_mask,
                    "fallback_flag_mask": "$%02X" % fallback_mask,
                }
            )
            cursor += 3
        else:
            raise ValueError("unterminated item action-command table")
        classes.append(
            {
                "action_class": action_class,
                "location": extract.location(17, pointer),
                "bytes": rom[table_at:table_at + cursor + 1].hex().upper(),
                "entries": len(entries),
                "records": entries,
            }
        )
    return classes


def _item_action_numeric_surface(rom, observed_frame):
    measured = layout.validate_direct_surface(
        rom,
        ITEM_ACTION_NUMERIC_RAW,
        start_x=ITEM_ACTION_NUMERIC_START[0],
        start_y=ITEM_ACTION_NUMERIC_START[1],
        right_edge=ITEM_ACTION_NUMERIC_RIGHT_EDGE,
    )
    return {
        "name": "item_action_seeded_weapon_numbers",
        "source": codec.decode_source(ITEM_ACTION_NUMERIC_RAW),
        "raw": ITEM_ACTION_NUMERIC_RAW.hex().upper(),
        "start_pen": list(ITEM_ACTION_NUMERIC_START),
        "right_edge": ITEM_ACTION_NUMERIC_RIGHT_EDGE,
        "available_pixels": (
            ITEM_ACTION_NUMERIC_RIGHT_EDGE - ITEM_ACTION_NUMERIC_START[0]
        ),
        "renderer_pixels": measured.rightmost_pen - ITEM_ACTION_NUMERIC_START[0],
        "final_pen": [measured.final_x, measured.final_y],
        "observed_mode": 0x08,
        "observed_frame": observed_frame,
    }


def _item_equipment_cycle_summary(rom, records, result):
    """Freeze the live club Equip/Remove state transition and its messages."""
    object_address = (
        ITEM_OBJECT_BASE
        + ITEM_CATEGORY_SEEDS[0].object_index * ITEM_OBJECT_SIZE
    )
    neutral_object = ITEM_CATEGORY_SEEDS[0].object_record
    equipped_object = bytearray(neutral_object)
    equipped_object[ITEM_EQUIPMENT_FLAG_BYTE] |= ITEM_EQUIPMENT_FLAG_MASK

    equipped_layout = layout.validate_direct_surface(
        rom,
        ITEM_EQUIPPED_WEAPON_RAW,
        start_x=ITEM_EQUIPPED_WEAPON_START[0],
        start_y=ITEM_EQUIPPED_WEAPON_START[1],
        right_edge=ITEM_EQUIPPED_WEAPON_RIGHT_EDGE,
    )
    equipped_surface = {
        "name": "item_list_equipped_weapon_name",
        "source": codec.decode_source(ITEM_EQUIPPED_WEAPON_RAW),
        "raw": ITEM_EQUIPPED_WEAPON_RAW.hex().upper(),
        "marker": "$%02X" % ITEM_EQUIPPED_WEAPON_RAW[0],
        "base_reference": [4, ITEM_CATEGORY_SEEDS[0].item_index],
        "start_pen": list(ITEM_EQUIPPED_WEAPON_START),
        "right_edge": ITEM_EQUIPPED_WEAPON_RIGHT_EDGE,
        "available_pixels": (
            ITEM_EQUIPPED_WEAPON_RIGHT_EDGE - ITEM_EQUIPPED_WEAPON_START[0]
        ),
        "renderer_pixels": (
            equipped_layout.rightmost_pen - ITEM_EQUIPPED_WEAPON_START[0]
        ),
        "final_pen": [equipped_layout.final_x, equipped_layout.final_y],
        "observed_mode": 0x08,
        "observed_frame": ITEM_EQUIPPED_WEAPON_OBSERVED_FRAME,
    }

    result_messages = []
    for (
        name,
        command_index,
        reference,
        source_frame,
        render_frame,
        expanded_raw,
    ) in ITEM_EQUIPMENT_RESULT_MESSAGES:
        record = records[reference]
        measured = layout.renderer_layout(
            rom, expanded_raw, mode=ITEM_EQUIPMENT_RESULT_MODE
        )
        if measured.auto_wraps:
            raise ValueError("equipment result auto-wraps for %s" % name)
        result_messages.append(
            {
                "name": "item_%s_result" % name,
                "command_index": command_index,
                "source_reference": list(reference),
                "source_record": record.id,
                "source": record.source,
                "source_raw": record.raw.hex().upper(),
                "source_observed_mode": ITEM_EQUIPMENT_RESULT_MODE,
                "source_observed_frame": source_frame,
                "runtime_cache": {
                    "address": "$%04X" % ITEM_EQUIPMENT_CACHE_ADDRESS,
                    "control": record.raw[:4].hex().upper(),
                    "expanded_reference": [4, ITEM_CATEGORY_SEEDS[0].item_index],
                    "expanded_value": records[
                        (4, ITEM_CATEGORY_SEEDS[0].item_index)
                    ].source,
                },
                "expanded_source": codec.decode_source(expanded_raw),
                "expanded_raw": expanded_raw.hex().upper(),
                "terminated_raw": (expanded_raw + b"\xFF").hex().upper(),
                "renderer_mode": ITEM_EQUIPMENT_RESULT_MODE,
                "start_pen": [measured.start_x, measured.start_y],
                "renderer_pixels": measured.rightmost_pen - measured.start_x,
                "final_pen": [measured.final_x, measured.final_y],
                "automatic_wraps": len(measured.auto_wraps),
                "render_observed_frame": render_frame,
            }
        )

    equipped_actions = {
        "enabled_indices": [2, 13, 17, 24, 15],
        "observed_surfaces": _positioned_surface_summary(
            rom, ITEM_ACTION_EQUIPPED_WEAPON_SURFACES, result=result
        ),
        "numeric_surface": _item_action_numeric_surface(rom, 852),
    }
    return {
        "inputs": {
            "equip_confirm_frame": 300,
            "reopen_main_menu_frame": 650,
            "reopen_items_frame": 750,
            "open_equipped_actions_frame": 850,
            "remove_confirm_frame": 950,
        },
        "object_state": {
            "wram_bank": ITEM_OBJECT_WRAM_BANK,
            "object_index": ITEM_CATEGORY_SEEDS[0].object_index,
            "address": "$%04X" % object_address,
            "flag_byte_offset": ITEM_EQUIPMENT_FLAG_BYTE,
            "flag_mask": "$%02X" % ITEM_EQUIPMENT_FLAG_MASK,
            "before_equip": neutral_object.hex().upper(),
            "after_equip": bytes(equipped_object).hex().upper(),
            "after_remove": neutral_object.hex().upper(),
        },
        "equipped_list_surface": equipped_surface,
        "equipped_action_popup": equipped_actions,
        "result_messages": result_messages,
    }


def _item_action_result_summary(rom, records):
    """Freeze Throw, Place and confirmed Discard from independent states."""
    before_inventory = bytes(
        tuple(seed.object_index for seed in ITEM_CATEGORY_SEEDS)
        + (ITEM_INVENTORY_SENTINEL,) * 10
    )
    expected_commands = [1, 13, 17, 24, 15, 0, 0, 0]
    outcomes = []
    for (
        name,
        command_index,
        selected_slot,
        inputs,
        final_frame,
        source_reference,
        source_frame,
        render_frame,
        expanded_raw,
        final_object,
        final_floor_value,
    ) in ITEM_ACTION_RESULT_ROUTES:
        record = records[source_reference]
        measured = layout.renderer_layout(
            rom, expanded_raw, mode=ITEM_ACTION_RESULT_MODE
        )
        if measured.auto_wraps:
            raise ValueError("item action result auto-wraps for %s" % name)
        runtime_values = [
            {
                "kind": "cached_item_name",
                "address": "$%04X" % ITEM_EQUIPMENT_CACHE_ADDRESS,
                "control": record.raw[:4].hex().upper(),
                "expanded_reference": [4, ITEM_CATEGORY_SEEDS[0].item_index],
                "expanded_value": records[
                    (4, ITEM_CATEGORY_SEEDS[0].item_index)
                ].source,
            }
        ]
        appended_source = None
        if name == "throw":
            target_control = record.raw[7:11]
            runtime_values.append(
                {
                    "kind": "target_name_lookup",
                    "address": "$%04X" % ITEM_THROW_TARGET_CACHE_ADDRESS,
                    "control": target_control.hex().upper(),
                    "expanded_value": ITEM_THROW_TARGET_EXPANDED_VALUE,
                }
            )
            appended_record = records[ITEM_THROW_DAMAGE_REFERENCE]
            appended_source = {
                "reference": list(ITEM_THROW_DAMAGE_REFERENCE),
                "record": appended_record.id,
                "source": appended_record.source,
                "raw": appended_record.raw.hex().upper(),
            }
        outcomes.append(
            {
                "name": "item_%s_result" % name,
                "command_index": command_index,
                "selected_compacted_slot": selected_slot,
                "resolved_commands": expected_commands,
                "inputs": [
                    {"frame": input_frame, "button": button}
                    for input_frame, button in inputs
                ],
                "final_observed_frame": final_frame,
                "source_reference": list(source_reference),
                "source_record": record.id,
                "source": record.source,
                "source_raw": record.raw.hex().upper(),
                "appended_source": appended_source,
                "source_observed_mode": ITEM_ACTION_RESULT_MODE,
                "source_observed_frame": source_frame,
                "runtime_values": runtime_values,
                "expanded_source": codec.decode_source(expanded_raw),
                "expanded_raw": expanded_raw.hex().upper(),
                "terminated_raw": (expanded_raw + b"\xFF").hex().upper(),
                "renderer_mode": ITEM_ACTION_RESULT_MODE,
                "start_pen": [measured.start_x, measured.start_y],
                "renderer_pixels": measured.rightmost_pen - measured.start_x,
                "line_widths": list(measured.line_widths),
                "final_pen": [measured.final_x, measured.final_y],
                "explicit_breaks": len(measured.explicit_breaks),
                "automatic_wraps": len(measured.auto_wraps),
                "render_observed_frame": render_frame,
                "state": {
                    "inventory_before": before_inventory.hex().upper(),
                    "inventory_after": (
                        ITEM_ACTION_RESULT_INVENTORY_AFTER.hex().upper()
                    ),
                    "object_wram_bank": ITEM_OBJECT_WRAM_BANK,
                    "object_address": "$%04X"
                    % (
                        ITEM_OBJECT_BASE
                        + ITEM_CATEGORY_SEEDS[0].object_index * ITEM_OBJECT_SIZE
                    ),
                    "object_before": (
                        ITEM_CATEGORY_SEEDS[0].object_record.hex().upper()
                    ),
                    "object_after": final_object.hex().upper(),
                    "floor_slot": {
                        "wram_bank": ITEM_FLOOR_OBJECT_WRAM_BANK,
                        "address": "$%04X" % ITEM_FLOOR_OBJECT_SLOT_ADDRESS,
                        "before": "$%02X" % ITEM_INVENTORY_SENTINEL,
                        "after": "$%02X" % final_floor_value,
                    },
                },
            }
        )

    prompt_record = records[ITEM_DISCARD_CONFIRM_REFERENCE]
    prompt_layout = layout.renderer_layout(
        rom, prompt_record.raw, mode=ITEM_DISCARD_CONFIRM_MODE
    )
    if prompt_layout.auto_wraps:
        raise ValueError("discard confirmation prompt auto-wraps")
    return {
        "independent_clean_state_routes": True,
        "outcomes": outcomes,
        "discard_confirmation": {
            "reference": list(ITEM_DISCARD_CONFIRM_REFERENCE),
            "record": prompt_record.id,
            "source": prompt_record.source,
            "raw": prompt_record.raw.hex().upper(),
            "terminated_raw": (prompt_record.raw + b"\xFF").hex().upper(),
            "renderer_mode": ITEM_DISCARD_CONFIRM_MODE,
            "start_pen": [prompt_layout.start_x, prompt_layout.start_y],
            "renderer_pixels": prompt_layout.rightmost_pen - prompt_layout.start_x,
            "line_widths": list(prompt_layout.line_widths),
            "final_pen": [prompt_layout.final_x, prompt_layout.final_y],
            "explicit_breaks": len(prompt_layout.explicit_breaks),
            "automatic_wraps": len(prompt_layout.auto_wraps),
            "default_choice": "no",
            "confirmed_choice": "yes",
            "source_observed_frame": ITEM_DISCARD_CONFIRM_SOURCE_FRAME,
            "render_observed_frame": ITEM_DISCARD_CONFIRM_RENDER_FRAME,
        },
    }


def _item_route_inputs(row, action_inputs):
    inputs = [(0, "b"), (100, "a")]
    inputs.extend((150 + 50 * index, "down") for index in range(row))
    inputs.append((200 + 50 * row, "a"))
    inputs.extend(action_inputs)
    return [{"frame": frame, "button": button} for frame, button in inputs]


def _item_runtime_message_summary(
    rom,
    records,
    reference,
    source_frame,
    render_frame,
    expanded_raw,
    appended_reference=None,
):
    record = records[reference]
    measured = layout.renderer_layout(
        rom, expanded_raw, mode=ITEM_ACTION_RESULT_MODE
    )
    if measured.auto_wraps:
        raise ValueError("representative item result auto-wraps for %s" % record.id)
    appended = None
    if appended_reference is not None:
        appended_record = records[appended_reference]
        appended = {
            "reference": list(appended_reference),
            "record": appended_record.id,
            "source": appended_record.source,
            "raw": appended_record.raw.hex().upper(),
        }
    return {
        "source_reference": list(reference),
        "source_record": record.id,
        "source": record.source,
        "source_raw": record.raw.hex().upper(),
        "appended_source": appended,
        "source_observed_mode": ITEM_ACTION_RESULT_MODE,
        "source_observed_frame": source_frame,
        "expanded_source": codec.decode_source(expanded_raw),
        "expanded_raw": expanded_raw.hex().upper(),
        "terminated_raw": (expanded_raw + b"\xFF").hex().upper(),
        "renderer_mode": ITEM_ACTION_RESULT_MODE,
        "start_pen": [measured.start_x, measured.start_y],
        "renderer_pixels": measured.rightmost_pen - measured.start_x,
        "line_widths": list(measured.line_widths),
        "final_pen": [measured.final_x, measured.final_y],
        "explicit_breaks": len(measured.explicit_breaks),
        "automatic_wraps": len(measured.auto_wraps),
        "render_observed_frame": render_frame,
    }


def _additional_item_route_summary(rom, records, result):
    """Freeze twelve representative equipment/use/container live routes."""
    inventory_before = bytes(
        tuple(seed.object_index for seed in ITEM_CATEGORY_SEEDS)
        + (ITEM_INVENTORY_SENTINEL,) * 10
    )

    equipment_routes = []
    for (
        category,
        row,
        marker_raw,
        marker_start,
        marker_frame,
        equip_source_frame,
        equip_render_frame,
        equip_raw,
        remove_source_frame,
        remove_render_frame,
        remove_raw,
        equipped_popup_frame,
        remove_input_frame,
        final_frame,
        equipped_commands,
    ) in ITEM_EQUIPMENT_FAMILY_ROUTES:
        seed = ITEM_CATEGORY_SEEDS[row]
        if seed.category != category:
            raise ValueError("equipment route seed changed for %s" % category)
        equipped_object = bytearray(seed.object_record)
        equipped_object[ITEM_EQUIPMENT_FLAG_BYTE] |= ITEM_EQUIPMENT_FLAG_MASK
        marker_layout = layout.validate_direct_surface(
            rom,
            marker_raw,
            start_x=marker_start[0],
            start_y=marker_start[1],
            right_edge=layout.CANVAS_WIDTH_PIXELS,
        )
        equip_input_frame = 300 + 50 * row
        reopen_frame = equip_input_frame + 350
        items_frame = equip_input_frame + 450
        popup_frame = equip_input_frame + 550 + 50 * row
        inputs = [(0, "b"), (100, "a")]
        inputs.extend((150 + 50 * index, "down") for index in range(row))
        inputs.extend(
            (
                (200 + 50 * row, "a"),
                (equip_input_frame, "a"),
                (reopen_frame, "b"),
                (items_frame, "a"),
            )
        )
        inputs.extend(
            (equip_input_frame + 500 + 50 * index, "down")
            for index in range(row)
        )
        inputs.extend(
            ((popup_frame, "a"), (remove_input_frame, "a"))
        )
        equipment_routes.append(
            {
                "name": "item_%s_equipment_cycle" % category,
                "category": category,
                "row": row,
                "item_index": seed.item_index,
                "object_index": seed.object_index,
                "inputs": [
                    {"frame": frame, "button": button}
                    for frame, button in inputs
                ],
                "final_observed_frame": final_frame,
                "object_state": {
                    "wram_bank": ITEM_OBJECT_WRAM_BANK,
                    "address": "$%04X"
                    % (ITEM_OBJECT_BASE + seed.object_index * ITEM_OBJECT_SIZE),
                    "before_equip": seed.object_record.hex().upper(),
                    "after_equip": bytes(equipped_object).hex().upper(),
                    "after_remove": seed.object_record.hex().upper(),
                    "flag_byte_offset": ITEM_EQUIPMENT_FLAG_BYTE,
                    "flag_mask": "$%02X" % ITEM_EQUIPMENT_FLAG_MASK,
                },
                "equipped_marker": {
                    "source": codec.decode_source(marker_raw),
                    "raw": marker_raw.hex().upper(),
                    "marker": "$%02X" % marker_raw[0],
                    "start_pen": list(marker_start),
                    "right_edge": layout.CANVAS_WIDTH_PIXELS,
                    "renderer_pixels": marker_layout.rightmost_pen - marker_start[0],
                    "final_pen": [marker_layout.final_x, marker_layout.final_y],
                    "observed_mode": 0x08,
                    "observed_frame": marker_frame,
                },
                "equipped_popup": {
                    "input_frame": equipped_popup_frame,
                    "observed_frame": equipped_popup_frame + 1,
                    "enabled_indices": list(equipped_commands),
                },
                "result_messages": [
                    _item_runtime_message_summary(
                        rom,
                        records,
                        (11, 27),
                        equip_source_frame,
                        equip_render_frame,
                        equip_raw,
                    ),
                    _item_runtime_message_summary(
                        rom,
                        records,
                        (11, 28),
                        remove_source_frame,
                        remove_render_frame,
                        remove_raw,
                    ),
                ],
            }
        )

    primary_routes = []
    for (
        name,
        category,
        row,
        command_index,
        selected_slot,
        action_inputs,
        final_frame,
        messages,
        final_object,
    ) in ITEM_PRIMARY_ACTION_ROUTES:
        seed = ITEM_CATEGORY_SEEDS[row]
        common_commands = (
            [1, 14, 17, 24, 15]
            if name == "shoot"
            else [command_index, 13, 17, 24, 15]
        )
        inventory_after = bytearray(inventory_before)
        if final_object == bytes(ITEM_OBJECT_SIZE):
            del inventory_after[row]
            inventory_after.append(ITEM_INVENTORY_SENTINEL)
        selector = None
        if name == "read":
            selector = _positioned_surface_summary(
                rom, (ITEM_TARGET_SELECTOR_SURFACE,), result=result
            )[0]
        primary_routes.append(
            {
                "name": "item_%s_route" % name,
                "category": category,
                "row": row,
                "item_index": seed.item_index,
                "object_index": seed.object_index,
                "command_index": command_index,
                "selected_compacted_slot": selected_slot,
                "resolved_commands": common_commands + [0] * (8 - len(common_commands)),
                "inputs": _item_route_inputs(row, action_inputs),
                "final_observed_frame": final_frame,
                "target_selector": selector,
                "messages": [
                    _item_runtime_message_summary(
                        rom,
                        records,
                        reference,
                        source_frame,
                        render_frame,
                        expanded_raw,
                        appended_reference,
                    )
                    for (
                        reference,
                        source_frame,
                        render_frame,
                        expanded_raw,
                        appended_reference,
                    ) in messages
                ],
                "state": {
                    "inventory_before": inventory_before.hex().upper(),
                    "inventory_after": bytes(inventory_after).hex().upper(),
                    "object_wram_bank": ITEM_OBJECT_WRAM_BANK,
                    "object_address": "$%04X"
                    % (ITEM_OBJECT_BASE + seed.object_index * ITEM_OBJECT_SIZE),
                    "object_before": seed.object_record.hex().upper(),
                    "object_after": final_object.hex().upper(),
                },
            }
        )

    special_routes = []
    for (
        name,
        category,
        row,
        command_index,
        selected_slot,
        override_category,
        override_index,
        action_inputs,
        final_frame,
        commands,
        messages,
    ) in ITEM_SPECIAL_ACTION_ROUTES:
        seed = ITEM_CATEGORY_SEEDS[row]
        object_record = seed.object_record
        if override_category == category:
            object_record = bytes(
                (override_index, seed.action_class, 0, 0, 0, 0, 0, 0)
            )
        direct_surfaces = []
        if name == "jar_look":
            heading_layout = layout.validate_direct_surface(
                rom,
                ITEM_JAR_CONTENTS_HEADING_RAW,
                start_x=ITEM_JAR_CONTENTS_HEADING_START[0],
                start_y=ITEM_JAR_CONTENTS_HEADING_START[1],
                right_edge=layout.CANVAS_WIDTH_PIXELS,
            )
            direct_surfaces = [
                {
                    "name": "item_jar_contents_heading",
                    "reference": [4, 184],
                    "source": codec.decode_source(ITEM_JAR_CONTENTS_HEADING_RAW),
                    "raw": ITEM_JAR_CONTENTS_HEADING_RAW.hex().upper(),
                    "start_pen": list(ITEM_JAR_CONTENTS_HEADING_START),
                    "right_edge": layout.CANVAS_WIDTH_PIXELS,
                    "available_pixels": (
                        layout.CANVAS_WIDTH_PIXELS
                        - ITEM_JAR_CONTENTS_HEADING_START[0]
                    ),
                    "renderer_pixels": (
                        heading_layout.rightmost_pen
                        - ITEM_JAR_CONTENTS_HEADING_START[0]
                    ),
                    "final_pen": [
                        heading_layout.final_x,
                        heading_layout.final_y,
                    ],
                    "observed_mode": 0x08,
                    "observed_frame": ITEM_JAR_CONTENTS_HEADING_OBSERVED_FRAME,
                    "construction": "group-4 name plus formatted jar capacity",
                },
                *_positioned_surface_summary(
                    rom, ITEM_JAR_EMPTY_SURFACES, result=result
                ),
            ]
        elif name == "jar_insert_full":
            selector = _positioned_surface_summary(
                rom, (ITEM_TARGET_SELECTOR_SURFACE,), result=result
            )[0]
            selector["name"] = "item_jar_insert_target_selector_heading"
            selector["observed_frame"] = 752
            direct_surfaces = [selector]
        keyboard = None
        if name == "blank_scroll_write":
            keyboard = {
                "renderer": "graphical tilemap; no direct/full text calls",
                "lcdc": "$%02X" % ITEM_WRITE_KEYBOARD_REGISTERS[0],
                "registers": {
                    "wx": ITEM_WRITE_KEYBOARD_REGISTERS[1],
                    "wy": ITEM_WRITE_KEYBOARD_REGISTERS[2],
                },
                "vram_bank": 0,
                "base": "$9800",
                "size_tiles": [20, 18],
                "rows": [
                    list(row_values)
                    for row_values in ITEM_WRITE_KEYBOARD_TILEMAP_ROWS
                ],
                "observed_frame": final_frame,
            }
        special_routes.append(
            {
                "name": "item_%s_route" % name,
                "category": category,
                "row": row,
                "seed_item_index": object_record[0],
                "object_index": seed.object_index,
                "command_index": command_index,
                "selected_compacted_slot": selected_slot,
                "resolved_commands": list(commands) + [0] * (8 - len(commands)),
                "inputs": _item_route_inputs(row, action_inputs),
                "final_observed_frame": final_frame,
                "direct_surfaces": direct_surfaces,
                "messages": [
                    _item_runtime_message_summary(
                        rom,
                        records,
                        reference,
                        source_frame,
                        render_frame,
                        expanded_raw,
                        appended_reference,
                    )
                    for (
                        reference,
                        source_frame,
                        render_frame,
                        expanded_raw,
                        appended_reference,
                    ) in messages
                ],
                "keyboard_screen": keyboard,
                "state": {
                    "inventory": inventory_before.hex().upper(),
                    "object_wram_bank": ITEM_OBJECT_WRAM_BANK,
                    "object_address": "$%04X"
                    % (ITEM_OBJECT_BASE + seed.object_index * ITEM_OBJECT_SIZE),
                    "object_before": object_record.hex().upper(),
                    "object_after": object_record.hex().upper(),
                },
            }
        )

    return {
        "coverage": {
            "representative_live_routes": (
                len(equipment_routes) + len(primary_routes) + len(special_routes)
            ),
            "equipment_cycles": len(equipment_routes),
            "primary_actions": len(primary_routes),
            "container_or_writing": len(special_routes),
            "strategy": "one clean route per distinct high-risk behavior; shared handlers are not repeated per item",
        },
        "equipment_families": equipment_routes,
        "primary_actions": primary_routes,
        "container_and_writing": special_routes,
    }


def _item_description_domain(rom, records):
    """Measure the complete group-6 item-description catalog in mode 08."""
    rows = []
    histogram = {}
    for index in range(ITEM_DESCRIPTION_ENTRIES):
        record = records[(ITEM_DESCRIPTION_GROUP, index)]
        measured = layout.source_layout(rom, record.raw, mode=0x08)
        if not measured.safe:
            raise ValueError("unsafe stock item description %s" % record.id)
        if measured.dynamic_offsets:
            raise ValueError("dynamic stock item description %s" % record.id)
        line_widths = [
            [line.composer_pixels, line.renderer_pixels]
            for line in measured.lines
        ]
        row = {
            "index": index,
            "reference": [ITEM_DESCRIPTION_GROUP, index],
            "record": record.id,
            "source": record.source,
            "lines": len(measured.lines),
            "max_composer_pixels": max(width[0] for width in line_widths),
            "max_renderer_pixels": max(width[1] for width in line_widths),
            "line_widths": line_widths,
        }
        rows.append(row)
        histogram[row["lines"]] = histogram.get(row["lines"], 0) + 1
    return {
        "group": ITEM_DESCRIPTION_GROUP,
        "index_range": [0, ITEM_DESCRIPTION_ENTRIES - 1],
        "entries": len(rows),
        "mode": 0x08,
        "composer_safe_pixels": layout.COMPOSER_WRAP_AT - 1,
        "renderer_safe_pixels": layout.CANVAS_WIDTH_PIXELS,
        "safe_records": len(rows),
        "dynamic_records": 0,
        "line_count_histogram": [
            {"lines": line_count, "records": histogram[line_count]}
            for line_count in sorted(histogram)
        ],
        "longest": dict(max(rows, key=lambda row: row["lines"])),
        "widest": dict(max(rows, key=lambda row: row["max_renderer_pixels"])),
        "records": rows,
    }


def _item_name_root_domain(rom, records):
    """Freeze the category-filtered keys used by unidentified-item search."""
    rows = []
    partitions = []
    for category, first, last, first_item in ITEM_NAME_ROOT_PARTITIONS:
        category_rows = []
        for index in range(first, last + 1):
            record = records[(ITEM_NAME_ROOT_GROUP, index)]
            item_index = first_item + index - first
            item_record = records[(4, item_index)]
            disabled = index in ITEM_NAME_ROOT_DISABLED_INDICES
            if bool(record.raw and record.raw[0] == 0x21) != disabled:
                raise ValueError("item-name root disable marker changed at %d" % index)
            row = {
                "index": index,
                "reference": [ITEM_NAME_ROOT_GROUP, index],
                "record": record.id,
                "source": record.source,
                "item_reference": [4, item_index],
                "item_record": item_record.id,
                "item_source": item_record.source,
                "disabled": disabled,
            }
            rows.append(row)
            category_rows.append(row)
        partitions.append(
            {
                "category": category,
                "root_index_range": [first, last],
                "item_index_range": [first_item, first_item + last - first],
                "entries": len(category_rows),
            }
        )
    if len(rows) != ITEM_NAME_ROOT_ENTRIES:
        raise ValueError("item-name root domain is incomplete")
    return {
        "group": ITEM_NAME_ROOT_GROUP,
        "index_range": [0, ITEM_NAME_ROOT_ENTRIES - 1],
        "entries": len(rows),
        "input_bytes": ITEM_NAME_ROOT_INPUT_BYTES,
        "matcher": extract.location(*ITEM_NAME_ROOT_MATCHER),
        "disabled_indices": list(ITEM_NAME_ROOT_DISABLED_INDICES),
        "partitions": partitions,
        "records": rows,
        "evidence": _code_evidence(
            rom, *ITEM_NAME_ROOT_MATCHER, ITEM_NAME_ROOT_MATCHER_SPAN
        ),
    }


def _item_ability_description_domain(rom, records):
    """Measure all 69 direct-rendered synthesis-rune description rows."""
    mapping_at = extract.file_offset(*ITEM_ABILITY_MAPPING_TABLE)
    mapping_raw = rom[mapping_at:mapping_at + len(ITEM_ABILITY_MAPPING_RAW)]
    if mapping_raw != ITEM_ABILITY_MAPPING_RAW:
        raise ValueError("unexpected item-ability family mapping table")
    rows = []
    families = []
    for family, first, last, observed_y in ITEM_ABILITY_DESCRIPTION_FAMILIES:
        family_rows = []
        for index in range(first, last + 1):
            record = records[(ITEM_ABILITY_DESCRIPTION_GROUP, index)]
            if not record.raw or record.raw[0] != 0xEC:
                raise ValueError("item-ability marker changed for %s" % record.id)
            measured = layout.validate_direct_surface(
                rom,
                record.raw,
                start_x=ITEM_ABILITY_DESCRIPTION_START_X,
                start_y=observed_y,
                right_edge=ITEM_ABILITY_DESCRIPTION_RIGHT_EDGE,
            )
            row = {
                "index": index,
                "family": family,
                "bit": index - first,
                "reference": [ITEM_ABILITY_DESCRIPTION_GROUP, index],
                "record": record.id,
                "source": record.source,
                "raw": record.raw.hex().upper(),
                "start_pen": [ITEM_ABILITY_DESCRIPTION_START_X, observed_y],
                "right_edge": ITEM_ABILITY_DESCRIPTION_RIGHT_EDGE,
                "available_pixels": (
                    ITEM_ABILITY_DESCRIPTION_RIGHT_EDGE
                    - ITEM_ABILITY_DESCRIPTION_START_X
                ),
                "renderer_pixels": (
                    measured.rightmost_pen - ITEM_ABILITY_DESCRIPTION_START_X
                ),
                "final_pen": [measured.final_x, measured.final_y],
            }
            rows.append(row)
            family_rows.append(row)
        families.append(
            {
                "family": family,
                "index_range": [first, last],
                "bit_range": [0, last - first],
                "entries": len(family_rows),
                "observed_y": observed_y,
            }
        )
    if len(rows) != ITEM_ABILITY_DESCRIPTION_ENTRIES:
        raise ValueError("item-ability description domain is incomplete")
    return {
        "group": ITEM_ABILITY_DESCRIPTION_GROUP,
        "index_range": [0, ITEM_ABILITY_DESCRIPTION_ENTRIES - 1],
        "entries": len(rows),
        "object_flag_bytes": [5, 7],
        "mapping_table": {
            "location": extract.location(*ITEM_ABILITY_MAPPING_TABLE),
            "bytes": mapping_raw.hex().upper(),
            "family_offsets": [first for _name, first, _last, _y in ITEM_ABILITY_DESCRIPTION_FAMILIES],
        },
        "families": families,
        "widest": dict(max(rows, key=lambda row: row["renderer_pixels"])),
        "records": rows,
        "evidence": {
            "renderer": _code_evidence(
                rom, *ITEM_ABILITY_RENDERER, ITEM_ABILITY_RENDERER_SPAN
            ),
            "bitset_getter": _code_evidence(
                rom, *ITEM_ABILITY_BITSET_GETTER, ITEM_ABILITY_BITSET_GETTER_SPAN
            ),
        },
    }


def _item_detail_summary(rom, records, result):
    body = records[ITEM_DETAIL_SOURCE_REFERENCE]
    body_layout = layout.source_layout(rom, body.raw, mode=0x08)
    body_line_widths = [
        [line.composer_pixels, line.renderer_pixels]
        for line in body_layout.lines
    ]
    numeric_fields = []
    for name, value, anchor_x, start_y, expected_start_x, observed_frame in (
        ITEM_DETAIL_NUMERIC_FIELDS
    ):
        raw = _formatted_unsigned(value)
        measured = layout.validate_direct_right_aligned_surface(
            rom,
            raw,
            left_edge=0,
            anchor_x=anchor_x,
            start_y=start_y,
        )
        if measured.start_x != expected_start_x:
            raise ValueError("item-detail numeric alignment changed for %s" % name)
        numeric_fields.append(
            {
                "name": name,
                "value": value,
                "formatted": raw.hex().upper(),
                "anchor": [anchor_x, start_y],
                "start_pen": [measured.start_x, measured.start_y],
                "alignment_width": layout.direct_alignment_width(rom, raw),
                "renderer_pixels": measured.rightmost_pen - measured.start_x,
                "observed_mode": 0x08,
                "observed_frame": observed_frame,
            }
        )
    return {
        "trigger": {
            "action_popup_input_frame": 200,
            "select_explain_input_frame": 300,
            "confirm_input_frame": 350,
        },
        "heading_surface": _positioned_surface_summary(
            rom, ITEM_DETAIL_HEADER_SURFACES, result=result
        )[0],
        "body_source": {
            "reference": list(ITEM_DETAIL_SOURCE_REFERENCE),
            "record": body.id,
            "source": body.source,
            "raw": body.raw.hex().upper(),
            "lines": len(body_layout.lines),
            "max_composer_pixels": max(width[0] for width in body_line_widths),
            "max_renderer_pixels": max(width[1] for width in body_line_widths),
            "line_widths": body_line_widths,
            "observed_mode": ITEM_DETAIL_SOURCE_OBSERVED_MODE,
            "observed_frame": ITEM_DETAIL_SOURCE_OBSERVED_FRAME,
        },
        "numeric_fields": numeric_fields,
        "window_hidden": {
            "registers": {
                "wx": ITEM_DETAIL_WINDOW_HIDDEN_REGISTER[0],
                "wy": ITEM_DETAIL_WINDOW_HIDDEN_REGISTER[1],
            },
            "observed_frame": 400,
        },
        "visible_tilemap": {
            "vram_bank": 0,
            "base": "$%04X" % ITEM_TILEMAP_BASE,
            "top_left_tile": list(ITEM_TILEMAP_TOP_LEFT),
            "size_tiles": [20, 18],
            "rows": [list(row) for row in ITEM_TILEMAP_ROWS],
            "observed_frame": 400,
        },
    }


def at_feet_summary(rom, result=None):
    """Freeze the empty, trap, item, and item-value At Feet branches."""
    rom = bytes(rom)
    result = extract.extract(rom) if result is None else result
    records = _record_reference_map(result)

    def positioned_record(reference, start_x, start_y, mode=0x08):
        record = records[reference]
        measured = layout.validate_direct_surface(
            rom,
            record.raw,
            start_x=start_x,
            start_y=start_y,
            right_edge=layout.CANVAS_WIDTH_PIXELS,
        )
        return {
            "reference": list(reference),
            "record": record.id,
            "source": record.source,
            "raw": record.raw.hex().upper(),
            "start_pen": [start_x, start_y],
            "right_edge": layout.CANVAS_WIDTH_PIXELS,
            "available_pixels": layout.CANVAS_WIDTH_PIXELS - start_x,
            "renderer_pixels": measured.rightmost_pen - start_x,
            "final_pen": [measured.final_x, measured.final_y],
            "observed_mode": mode,
        }

    def runtime_field(name, raw, start_x, start_y, mode=0x08):
        measured = layout.validate_direct_surface(
            rom,
            raw,
            start_x=start_x,
            start_y=start_y,
            right_edge=layout.CANVAS_WIDTH_PIXELS,
        )
        return {
            "name": name,
            "raw": raw.hex().upper(),
            "source": codec.decode_source(raw),
            "start_pen": [start_x, start_y],
            "right_edge": layout.CANVAS_WIDTH_PIXELS,
            "available_pixels": layout.CANVAS_WIDTH_PIXELS - start_x,
            "renderer_pixels": measured.rightmost_pen - start_x,
            "final_pen": [measured.final_x, measured.final_y],
            "observed_mode": mode,
        }

    common_heading = positioned_record((7, 36), 8, 4)
    current_money = runtime_field(
        "at_feet_current_money",
        AT_FEET_CURRENT_MONEY_RAW,
        *AT_FEET_CURRENT_MONEY_START,
        mode=AT_FEET_CURRENT_MONEY_MODE,
    )
    current_money["value"] = 0
    current_money["anchor"] = [136, 4]
    current_money_suffix = positioned_record((7, 49), 136, 4)

    trap_rows = [
        {
            **positioned_record(reference, *AT_FEET_BODY_NOMINAL_START),
            "trap_name_index": reference[1],
            "live_endpoint_probe": reference[1] in (1, 22),
        }
        for reference in AT_FEET_TRAP_REFERENCES
    ]
    no_trap_record = records[AT_FEET_RELATED_NO_TRAP_REFERENCE]

    item_variants = []
    for seed in (ITEM_CATEGORY_SEEDS[0], ITEM_CATEGORY_SEEDS[-1]):
        reference = (4, seed.item_index)
        base = records[reference]
        measured = layout.validate_direct_surface(
            rom,
            seed.runtime_raw,
            start_x=AT_FEET_BODY_FORMATTED_START[0],
            start_y=AT_FEET_BODY_FORMATTED_START[1],
            right_edge=layout.CANVAS_WIDTH_PIXELS,
        )
        item_variants.append(
            {
                "category": seed.category,
                "object_index": seed.object_index,
                "object_address": "$%04X"
                % (
                    ITEM_OBJECT_BASE
                    + seed.object_index * ITEM_OBJECT_SIZE
                ),
                "object_bytes": seed.object_record.hex().upper(),
                "base_reference": list(reference),
                "base_record": base.id,
                "base_source": base.source,
                "raw": seed.runtime_raw.hex().upper(),
                "source": codec.decode_source(seed.runtime_raw),
                "nominal_start_pen": list(AT_FEET_BODY_NOMINAL_START),
                "leading_fe_shift_pixels": (
                    AT_FEET_BODY_FORMATTED_START[0]
                    - AT_FEET_BODY_NOMINAL_START[0]
                ),
                "start_pen": list(AT_FEET_BODY_FORMATTED_START),
                "right_edge": layout.CANVAS_WIDTH_PIXELS,
                "available_pixels": (
                    layout.CANVAS_WIDTH_PIXELS
                    - AT_FEET_BODY_FORMATTED_START[0]
                ),
                "renderer_pixels": (
                    measured.rightmost_pen
                    - AT_FEET_BODY_FORMATTED_START[0]
                ),
                "final_pen": [measured.final_x, measured.final_y],
                "observed_mode": 0x08,
            }
        )

    metadata_fields = [
        runtime_field(name, raw, start_x, start_y)
        for name, raw, start_x, start_y in AT_FEET_METADATA_RUNTIME_FIELDS
    ]
    metadata_value_suffix = positioned_record(
        (7, 49), *AT_FEET_VALUE_SUFFIX_START
    )

    return {
        "entry": extract.location(*AT_FEET_ENTRY),
        "common_shell": {
            "heading": common_heading,
            "current_money": {
                "number": current_money,
                "suffix": current_money_suffix,
            },
            "header_constructor": extract.location(*ITEM_HEADER_CONSTRUCTOR),
        },
        "body": {
            "classifier": {
                "entry": extract.location(*AT_FEET_CELL_CLASSIFIER),
                "empty": "carry clear: return without body text",
                "trap": "carry set and A != $FF",
                "item": "carry set and A == $FF",
            },
            "empty": {
                "positioned_records": [],
                "live_observed": True,
            },
            "trap": {
                "mapper": extract.location(*AT_FEET_TRAP_MAPPER),
                "floor_table": "$C1A4-$C1AB",
                "group": 17,
                "first_index": 1,
                "last_index": 22,
                "records": trap_rows,
                "related_non_positioned_record": {
                    "reference": list(AT_FEET_RELATED_NO_TRAP_REFERENCE),
                    "record": no_trap_record.id,
                    "source": no_trap_record.source,
                    "raw": no_trap_record.raw.hex().upper(),
                    "role": "trap-system failure text, not an underfoot label",
                },
            },
            "item": {
                "selector": extract.location(*AT_FEET_ITEM_SELECTOR),
                "renderer": extract.location(*AT_FEET_ITEM_RENDERER),
                "shared_formatter": extract.location(*ITEM_NAME_FORMATTER),
                "shared_contract": "seeded_item_list.category_matrix",
                "nominal_start_pen": list(AT_FEET_BODY_NOMINAL_START),
                "leading_fe_start_pen": list(AT_FEET_BODY_FORMATTED_START),
                "live_representatives": item_variants,
                "metadata_value_branch": {
                    "renderer": extract.location(
                        *AT_FEET_ITEM_VALUE_RENDERER
                    ),
                    "condition": (
                        "resolved item metadata bit 0 is set; exact seeded "
                        "runtime output is frozen without assigning gameplay "
                        "semantics to the field"
                    ),
                    "seed_object_index": ITEM_CATEGORY_SEEDS[0].object_index,
                    "seed_object_bytes": (
                        AT_FEET_METADATA_SEED_OBJECT.hex().upper()
                    ),
                    "runtime_fields": metadata_fields,
                    "value_suffix": metadata_value_suffix,
                },
            },
        },
        "attribute_map": {
            "entry": extract.location(*AT_FEET_ATTRIBUTE_MAP),
            "behavior": (
                "set attribute bit 7 over the selected 20x18 BG/WIN map"
            ),
        },
        "evidence": {
            "entry": _code_evidence(
                rom, *AT_FEET_ENTRY, AT_FEET_ENTRY_SPAN
            ),
            "header": _code_evidence(
                rom,
                *ITEM_HEADER_CONSTRUCTOR,
                ITEM_HEADER_CONSTRUCTOR_SPAN,
            ),
            "body_renderer": _code_evidence(
                rom,
                *AT_FEET_BODY_RENDERER,
                AT_FEET_BODY_RENDERER_SPAN,
            ),
            "trap_mapper": _code_evidence(
                rom, *AT_FEET_TRAP_MAPPER, AT_FEET_TRAP_MAPPER_SPAN
            ),
            "item_renderer": _code_evidence(
                rom,
                *AT_FEET_ITEM_RENDERER,
                AT_FEET_ITEM_RENDERER_SPAN,
            ),
            "shared_item_formatter": _code_evidence(
                rom, *ITEM_NAME_FORMATTER, ITEM_NAME_FORMATTER_SPAN
            ),
            "item_value_renderer": _code_evidence(
                rom,
                *AT_FEET_ITEM_VALUE_RENDERER,
                AT_FEET_ITEM_VALUE_RENDERER_SPAN,
            ),
            "attribute_map": _code_evidence(
                rom,
                *AT_FEET_ATTRIBUTE_MAP,
                AT_FEET_ATTRIBUTE_MAP_SPAN,
            ),
        },
    }


def seeded_item_list_summary(rom, result=None):
    """Freeze item formatters, all action classes, and all descriptions."""
    rom = bytes(rom)
    result = extract.extract(rom) if result is None else result
    records = _record_reference_map(result)

    boundary_at = extract.file_offset(*ITEM_CATEGORY_BOUNDARY_TABLE)
    boundary_raw = rom[
        boundary_at:boundary_at + len(ITEM_CATEGORY_BOUNDARIES)
    ]
    expected_boundaries = bytes(start for _category, start in ITEM_CATEGORY_BOUNDARIES)
    if boundary_raw != expected_boundaries:
        raise ValueError("unexpected item-category boundary table")

    category_rows = []
    for row_number, seed in enumerate(ITEM_CATEGORY_SEEDS):
        base_reference = (4, seed.item_index)
        base_record = records[base_reference]
        start_pen = (ITEM_NAME_START[0], ITEM_NAME_START[1] + 11 * row_number)
        name_layout = layout.validate_direct_surface(
            rom,
            seed.runtime_raw,
            start_x=start_pen[0],
            start_y=start_pen[1],
            right_edge=ITEM_NAME_RIGHT_EDGE,
        )
        category_rows.append(
            {
                "name": "item_list_seeded_%s_name" % seed.category,
                "category": seed.category,
                "category_index": seed.category_index,
                "item_index": seed.item_index,
                "action_class": seed.action_class,
                "object_index": seed.object_index,
                "object_address": "$%04X"
                % (ITEM_OBJECT_BASE + seed.object_index * ITEM_OBJECT_SIZE),
                "object_bytes": seed.object_record.hex().upper(),
                "base_record": base_record.id,
                "base_reference": list(base_reference),
                "base_source": base_record.source,
                "source": codec.decode_source(seed.runtime_raw),
                "raw": seed.runtime_raw.hex().upper(),
                "start_pen": list(start_pen),
                "right_edge": ITEM_NAME_RIGHT_EDGE,
                "available_pixels": ITEM_NAME_RIGHT_EDGE - start_pen[0],
                "renderer_pixels": name_layout.rightmost_pen - start_pen[0],
                "final_pen": [name_layout.final_x, name_layout.final_y],
                "observed_mode": 0x08,
                "observed_frame": seed.observed_frame,
            }
        )

    money = _formatted_unsigned(ITEM_MONEY_OBSERVED_VALUE)
    money_layout = layout.right_aligned_direct_layout(
        rom,
        money,
        anchor_x=ITEM_MONEY_ANCHOR[0],
        start_y=ITEM_MONEY_ANCHOR[1],
    )
    if (money_layout.start_x, money_layout.start_y) != ITEM_MONEY_OBSERVED_START:
        raise ValueError("seeded item-list money alignment changed")

    action_classes = _item_action_command_domains(rom, records)
    coordinate_at = extract.file_offset(*ITEM_ACTION_COORDINATE_TABLE)
    coordinate_raw = rom[
        coordinate_at:coordinate_at + ITEM_ACTION_COORDINATE_TABLE_SPAN
    ]
    if coordinate_raw != bytes(value for pair in ITEM_ACTION_COORDINATES for value in pair):
        raise ValueError("unexpected item action-coordinate table")

    action_variants = {
        "inhibited": {
            "gate": {
                "address": "$%04X" % ITEM_ACTION_GLOBAL_GATE_ADDRESS,
                "mask": "$%02X" % ITEM_ACTION_GLOBAL_GATE_MASK,
                "observed_value": "$%02X" % ITEM_ACTION_INHIBITED_GATE_VALUE,
            },
            "seed_masks": {
                "primary": "$%02X" % ITEM_ACTION_SEEDED_PRIMARY_MASK,
                "fallback": "$%02X" % ITEM_ACTION_SEEDED_FALLBACK_MASK,
            },
            "enabled_indices": [24, 15],
            "observed_surfaces": _positioned_surface_summary(
                rom, ITEM_ACTION_INHIBITED_SURFACES, result=result
            ),
            "numeric_surface": _item_action_numeric_surface(
                rom, ITEM_ACTION_OBSERVED_FRAME
            ),
        },
        "ordinary_weapon": {
            "gate": {
                "address": "$%04X" % ITEM_ACTION_GLOBAL_GATE_ADDRESS,
                "mask": "$%02X" % ITEM_ACTION_GLOBAL_GATE_MASK,
                "observed_value": "$%02X" % ITEM_ACTION_ORDINARY_GATE_VALUE,
            },
            "seed_masks": {
                "primary": "$%02X" % ITEM_ACTION_SEEDED_PRIMARY_MASK,
                "fallback": "$%02X" % ITEM_ACTION_SEEDED_FALLBACK_MASK,
            },
            "enabled_indices": [1, 13, 17, 24, 15],
            "observed_surfaces": _positioned_surface_summary(
                rom, ITEM_ACTION_ORDINARY_WEAPON_SURFACES, result=result
            ),
            "numeric_surface": _item_action_numeric_surface(rom, 202),
        },
    }

    return {
        "seed": {
            "inventory": {
                "wram_bank": ITEM_INVENTORY_WRAM_BANK,
                "address": "$%04X" % ITEM_INVENTORY_BASE,
                "slots": ITEM_INVENTORY_SLOTS,
                "sentinel": "$%02X" % ITEM_INVENTORY_SENTINEL,
                "first_bytes": [
                    *[seed.object_index for seed in ITEM_CATEGORY_SEEDS],
                    ITEM_INVENTORY_SENTINEL,
                ],
            },
            "object_pool": {
                "wram_bank": ITEM_OBJECT_WRAM_BANK,
                "address": "$%04X" % ITEM_OBJECT_BASE,
                "record_size": ITEM_OBJECT_SIZE,
                "record_byte_0": "item index; category is boundary-derived",
                "record_byte_1": "action class",
                "record_byte_4_bit_4": "equipped state",
            },
        },
        "observed_surfaces": _positioned_surface_summary(
            rom, ITEM_LIST_SURFACES, result=result
        ),
        "category_matrix": {
            "boundary_table": {
                "location": extract.location(*ITEM_CATEGORY_BOUNDARY_TABLE),
                "bytes": boundary_raw.hex().upper(),
                "entries": [
                    {
                        "category_index": category_index,
                        "category": category,
                        "start": start,
                    }
                    for category_index, (category, start) in enumerate(
                        ITEM_CATEGORY_BOUNDARIES
                    )
                ],
            },
            "seeded_families": len(category_rows),
            "widest": dict(
                max(category_rows, key=lambda row: row["renderer_pixels"])
            ),
            "rows": category_rows,
        },
        "money": {
            "value": ITEM_MONEY_OBSERVED_VALUE,
            "formatted": money.hex().upper(),
            "anchor": list(ITEM_MONEY_ANCHOR),
            "start_pen": list(ITEM_MONEY_OBSERVED_START),
            "alignment_width": layout.direct_alignment_width(rom, money),
            "mode": 0x08,
            "observed_frame": ITEM_MONEY_OBSERVED_FRAME,
        },
        "action_popup": {
            "trigger": {
                "input_frame": 200,
                "selected_object_index": ITEM_CATEGORY_SEEDS[0].object_index,
                "selected_category": ITEM_CATEGORY_SEEDS[0].category,
                "selected_action_class": ITEM_CATEGORY_SEEDS[0].action_class,
            },
            "coordinate_slots": {
                "location": extract.location(*ITEM_ACTION_COORDINATE_TABLE),
                "bytes": coordinate_raw.hex().upper(),
                "entries": [list(pair) for pair in ITEM_ACTION_COORDINATES],
            },
            "command_domains": {
                "action_classes": len(action_classes),
                "max_commands": max(row["entries"] for row in action_classes),
                "records": action_classes,
            },
            "variants": action_variants,
            "window": {
                "lcdc": "$E7",
                "registers": {
                    "wx": ITEM_ACTION_WINDOW_REGISTER[0],
                    "wy": ITEM_ACTION_WINDOW_REGISTER[1],
                },
                "screen_top_left": list(ITEM_ACTION_WINDOW_SCREEN_TOP_LEFT),
                "vram_bank": 0,
                "base": "$%04X" % ITEM_ACTION_WINDOW_TILEMAP_BASE,
                "top_left_tile": [0, 0],
                "size_tiles": [8, 16],
                "rows": [list(row) for row in ITEM_ACTION_WINDOW_ROWS],
                "observed_frame": 250,
            },
        },
        "equipment_cycle": _item_equipment_cycle_summary(
            rom, records, result
        ),
        "action_results": _item_action_result_summary(rom, records),
        "representative_item_routes": _additional_item_route_summary(
            rom, records, result
        ),
        "detail_screen": _item_detail_summary(rom, records, result),
        "description_domain": _item_description_domain(rom, records),
        "item_name_root_domain": _item_name_root_domain(rom, records),
        "ability_description_domain": _item_ability_description_domain(
            rom, records
        ),
        "canvas": {
            "wram_bank": 7,
            "address": "$D000",
            "tile_columns": layout.CANVAS_TILE_COLUMNS,
            "heading": {
                "size_tiles": [18, 2],
                "one_bitplane_bytes": 0x120,
                "vram_address": "$9000",
                "vram_tile_base": 0x00,
            },
            "body": {
                "size_tiles": [18, 14],
                "one_bitplane_bytes": 0x7E0,
                "vram_address": "$8800",
                "vram_tile_base": 0x80,
            },
        },
        "visible_tilemap": {
            "vram_bank": 0,
            "base": "$%04X" % ITEM_TILEMAP_BASE,
            "top_left_tile": list(ITEM_TILEMAP_TOP_LEFT),
            "size_tiles": [20, 18],
            "rows": [list(row) for row in ITEM_TILEMAP_ROWS],
        },
        "evidence": {
            "inventory_count": _code_evidence(
                rom, *ITEM_LIST_COUNT, ITEM_LIST_COUNT_SPAN
            ),
            "screen_gate": _code_evidence(
                rom, *ITEM_SCREEN_GATE, ITEM_SCREEN_GATE_SPAN
            ),
            "header_and_money_constructor": _code_evidence(
                rom, *ITEM_HEADER_CONSTRUCTOR, ITEM_HEADER_CONSTRUCTOR_SPAN
            ),
            "item_row_constructor": _code_evidence(
                rom, *ITEM_ROW_CONSTRUCTOR, ITEM_ROW_CONSTRUCTOR_SPAN
            ),
            "item_name_formatter": _code_evidence(
                rom, *ITEM_NAME_FORMATTER, ITEM_NAME_FORMATTER_SPAN
            ),
            "category_boundary_table": _code_evidence(
                rom,
                *ITEM_CATEGORY_BOUNDARY_TABLE,
                len(ITEM_CATEGORY_BOUNDARIES),
            ),
            "action_command_pointer_table": _code_evidence(
                rom,
                *ITEM_ACTION_COMMAND_POINTER_TABLE,
                ITEM_ACTION_COMMAND_POINTER_TABLE_SPAN,
            ),
            "weapon_action_command_table": _code_evidence(
                rom,
                *ITEM_ACTION_WEAPON_COMMAND_TABLE,
                ITEM_ACTION_WEAPON_COMMAND_TABLE_SPAN,
            ),
            "action_command_filter": _code_evidence(
                rom,
                *ITEM_ACTION_COMMAND_FILTER,
                ITEM_ACTION_COMMAND_FILTER_SPAN,
            ),
            "action_coordinate_table": _code_evidence(
                rom,
                *ITEM_ACTION_COORDINATE_TABLE,
                ITEM_ACTION_COORDINATE_TABLE_SPAN,
            ),
            "action_slot_resolver": _code_evidence(
                rom,
                *ITEM_ACTION_SLOT_RESOLVER,
                ITEM_ACTION_SLOT_RESOLVER_SPAN,
            ),
            "action_selection_handler": _code_evidence(
                rom,
                *ITEM_ACTION_SELECTION_HANDLER,
                ITEM_ACTION_SELECTION_HANDLER_SPAN,
            ),
            "equipment_handler": _code_evidence(
                rom,
                *ITEM_EQUIPMENT_HANDLER,
                ITEM_EQUIPMENT_HANDLER_SPAN,
            ),
            "equip_flag_mutator": _code_evidence(
                rom,
                *ITEM_EQUIP_FLAG_MUTATOR,
                ITEM_EQUIP_FLAG_MUTATOR_SPAN,
            ),
            "remove_flag_mutator": _code_evidence(
                rom,
                *ITEM_REMOVE_FLAG_MUTATOR,
                ITEM_REMOVE_FLAG_MUTATOR_SPAN,
            ),
            "inventory_remove": _code_evidence(
                rom,
                *ITEM_INVENTORY_REMOVE,
                ITEM_INVENTORY_REMOVE_SPAN,
            ),
            "detail_caller": _code_evidence(
                rom, *ITEM_DETAIL_CALLER, ITEM_DETAIL_CALLER_SPAN
            ),
            "detail_body_constructor": _code_evidence(
                rom,
                *ITEM_DETAIL_BODY_CONSTRUCTOR,
                ITEM_DETAIL_BODY_CONSTRUCTOR_SPAN,
            ),
            "detail_numeric_constructor": _code_evidence(
                rom,
                *ITEM_DETAIL_NUMERIC_CONSTRUCTOR,
                ITEM_DETAIL_NUMERIC_CONSTRUCTOR_SPAN,
            ),
        },
    }


def dynamic_list_family_summary(rom, result=None):
    """Resolve every record in the three finite, paged help-list families."""
    rom = bytes(rom)
    result = extract.extract(rom) if result is None else result
    records = _record_reference_map(result)
    out = []
    for family in DYNAMIC_LIST_FAMILIES:
        rows = []
        for index in range(family.start_index, family.end_index + 1):
            record = records[(family.group, index)]
            start_y = 1 + 11 * ((index - family.start_index) % family.page_rows)
            measured = layout.validate_direct_surface(
                rom,
                record.raw,
                start_x=3,
                start_y=start_y,
                right_edge=layout.CANVAS_WIDTH_PIXELS,
            )
            rows.append(
                {
                    "index": index,
                    "record": record.id,
                    "source": record.source,
                    "renderer_pixels": measured.rightmost_pen - 3,
                }
            )
        widest = max(rows, key=lambda row: row["renderer_pixels"])
        constructor_at = extract.file_offset(17, family.constructor_address)
        caller_at = extract.file_offset(family.caller_bank, family.caller_address)
        heading = records[(family.heading_group, family.heading_index)]
        out.append(
            {
                "name": family.name,
                "group": family.group,
                "index_range": [family.start_index, family.end_index],
                "entries": len(rows),
                "page_rows": family.page_rows,
                "start_x": 3,
                "first_start_y": 1,
                "row_step": 11,
                "physical_right_edge": layout.CANVAS_WIDTH_PIXELS,
                "physical_budget": layout.CANVAS_WIDTH_PIXELS - 3,
                "heading": {
                    "reference": [family.heading_group, family.heading_index],
                    "record": heading.id,
                    "source": heading.source,
                },
                "constructor": {
                    "location": extract.location(17, family.constructor_address),
                    "bytes": rom[constructor_at:constructor_at + 0x48].hex().upper(),
                },
                "caller": {
                    "location": extract.location(family.caller_bank, family.caller_address),
                    "bytes": rom[caller_at:caller_at + 0x0E].hex().upper(),
                },
                "widest": dict(widest),
                "records": rows,
            }
        )
    return out


def static_record_use_summary(rom, result=None):
    """Resolve the proven constant draw_record uses and physical-edge budgets."""
    rom = bytes(rom)
    result = extract.extract(rom) if result is None else result
    records = _record_reference_map(result)
    out = []
    for use in STATIC_RECORD_USES:
        record = records[(use.group, use.index)]
        measured = layout.validate_direct_surface(
            rom,
            record.raw,
            start_x=use.start_x,
            start_y=use.start_y,
            right_edge=layout.CANVAS_WIDTH_PIXELS,
        )
        out.append(
            {
                "call_site": extract.location(17, use.call_site),
                "evidence": {
                    "location": extract.location(17, use.evidence_address),
                    "bytes": use.evidence.hex().upper(),
                },
                "record": record.id,
                "reference": [use.group, use.index],
                "source": record.source,
                "start_pen": [use.start_x, use.start_y],
                "physical_right_edge": layout.CANVAS_WIDTH_PIXELS,
                "physical_budget": layout.CANVAS_WIDTH_PIXELS - use.start_x,
                "renderer_pixels": measured.rightmost_pen - use.start_x,
                "final_pen": [measured.final_x, measured.final_y],
                # A smaller visual column edge requires a screen capture.  Do
                # not silently equate the physical canvas with that UI edge.
                "visual_right_edge": None,
            }
        )
    return out


def inventory(rom):
    rom = bytes(rom)
    selector_at = extract.file_offset(*DIRECT_SELECTOR)
    selector = rom[selector_at:selector_at + SELECTOR_COPY_SPAN]
    result = extract.extract(rom)
    return {
        "selector": {
            "entry": extract.location(*DIRECT_SELECTOR),
            "span": SELECTOR_COPY_SPAN,
            "sha1": sha1(selector).hexdigest(),
            "behavior": "copy selected record through and including FF",
        },
        "call_graph": call_graph(rom),
        "call_graph_coverage": call_graph_coverage(rom),
        "static_record_uses": static_record_use_summary(rom, result=result),
        "observed_surfaces": opening_menu_summary(rom, result=result),
        "guide_surfaces": guide_menu_summary(rom, result=result),
        "control_help_surfaces": control_help_summary(rom, result=result),
        "technique_help_surfaces": technique_help_summary(rom, result=result),
        "dynamic_list_families": dynamic_list_family_summary(rom, result=result),
        "main_menu_surfaces": main_menu_summary(rom, result=result),
        "main_menu_contract": main_menu_contract_summary(rom, result=result),
        "main_menu_numeric_status": main_menu_numeric_summary(rom),
        "help_popup_surfaces": help_popup_summary(rom, result=result),
        "help_popup_remap": help_popup_remap_summary(rom, result=result),
        "status_condition_screen": status_condition_summary(rom, result=result),
        "dungeon_selectors": dungeon_selector_summary(rom, result=result),
        "history_and_ranking": history_ranking_summary(rom, result=result),
        "record_picker_and_graphical_input": (
            record_picker_and_graphical_input_summary(rom)
        ),
        "diary_management": diary_management_summary(rom, result=result),
        "remaining_hub_routes": remaining_hub_routes_summary(
            rom, result=result
        ),
        "adventure_start_menu": adventure_start_menu_summary(
            rom, result=result
        ),
        "at_feet": at_feet_summary(rom, result=result),
        "seeded_item_list": seeded_item_list_summary(rom, result=result),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom")
    args = parser.parse_args(argv)
    try:
        measured = inventory(Path(args.rom).read_bytes())
    except (OSError, ValueError, extract.ExtractError, layout.LayoutError) as exc:
        parser.exit(1, "error: %s\n" % exc)
    print(json.dumps(measured, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
