#!/usr/bin/env python3
"""Widen ordinary service popups whose English labels exceed five tiles.

The generic bank-3 popup constructor exposes only five interior tiles (40
pixels).  ``stairs_menu`` already redirects its template-load and BG-copy
sites through bank 254.  This installer deliberately chains after that patch:
it preserves the stairs discriminator, routes every non-stairs popup through
an exact record-set detector, and uses a seven-interior-tile template only for
reviewed service menus.  All other generic popups retain the native template.
"""
from hashlib import sha1

from cartridge import fix_checksums
import english_font
import extract
import stairs_menu


RUNTIME_BANK = stairs_menu.RUNTIME_BANK
LOAD_HELPER_ADDRESS = (
    stairs_menu.HELPER_ADDRESS + len(stairs_menu._is_stairs_helper())
)
COPY_HELPER_ADDRESS = LOAD_HELPER_ADDRESS + len(stairs_menu._load_helper())

SUPPORT_ADDRESS = stairs_menu.RUNTIME_END
SERVICE_EXIT_HELPER_ADDRESS = SUPPORT_ADDRESS
SERVICE_EXIT_HELPER_LENGTH = 7
DETECTOR_ADDRESS = SERVICE_EXIT_HELPER_ADDRESS + SERVICE_EXIT_HELPER_LENGTH

RESCUE_RECORDS = ((0x80, 0x07), (0x7F, 0x07), (0x87, 0x07))
RESCUE_DELIVERY_RECORDS = (
    (0x80, 0x07),
    (0x7F, 0x07),
    (0x92, 0x07),
    (0x9E, 0x07),
)
WAREHOUSE_RECORDS = (
    (0x85, 0x07),
    (0x86, 0x07),
    (0x90, 0x07),
    (0x87, 0x07),
)
BANK_RECORDS = (
    (0x85, 0x07),
    (0x93, 0x07),
    (0x56, 0x07),
    (0x87, 0x07),
)
BLACKSMITH_INFO_RECORDS = (
    (0x94, 0x07),
    (0x95, 0x07),
    (0x97, 0x07),
    (0x96, 0x07),
    (0x87, 0x07),
)
SERVICE_RECORD_SETS = (
    RESCUE_RECORDS,
    RESCUE_DELIVERY_RECORDS,
    WAREHOUSE_RECORDS,
    BANK_RECORDS,
    BLACKSMITH_INFO_RECORDS,
)
SERVICE_GROUP = 7
RESCUE_INDICES = (128, 127, 135)
RESCUE_LABELS = ("Cable", "Password", "Quit")
RESCUE_DELIVERY_INDICES = (128, 127, 146, 158)
RESCUE_DELIVERY_LABELS = ("Cable", "Password", "Cancel", "Later")
WAREHOUSE_INDICES = (133, 134, 144, 135)
WAREHOUSE_LABELS = ("Deposit", "Withdraw", "Trash", "Quit")
BANK_INDICES = (133, 147, 86, 135)
BANK_LABELS = ("Deposit", "Withdraw", "Balance", "Quit")
BLACKSMITH_INFO_INDICES = (148, 149, 151, 150, 135)
BLACKSMITH_INFO_LABELS = ("Forge", "Repair", "Synthesis", "Remove", "Quit")
SERVICE_LABEL_SETS = (
    ("rescue", RESCUE_INDICES, RESCUE_LABELS),
    (
        "rescue_delivery",
        RESCUE_DELIVERY_INDICES,
        RESCUE_DELIVERY_LABELS,
    ),
    ("warehouse", WAREHOUSE_INDICES, WAREHOUSE_LABELS),
    ("bank", BANK_INDICES, BANK_LABELS),
    ("blacksmith_info", BLACKSMITH_INFO_INDICES, BLACKSMITH_INFO_LABELS),
)

NATIVE_COLUMNS = 7
ENGLISH_COLUMNS = 9
NATIVE_INTERIOR_COLUMNS = 5
ENGLISH_INTERIOR_COLUMNS = 7
TILE_PIXELS = 8
TEXT_START_X = TILE_PIXELS
TEXT_RIGHT_EDGE = ENGLISH_INTERIOR_COLUMNS * TILE_PIXELS
# The native dynamic-text arena assigns exactly six consecutive tiles to each
# physical row.  A nine-column frame needs a seventh interior cell, but mapping
# every ``base + 6`` aliases lower cursor rows. Warehouse and Bank keep the
# reviewed blank tile $B3 in every spill cell. Blacksmith Info copies its
# Synthesis suffix to stable tile $B3 and uses reviewed blank $B9 elsewhere.
# The three-entry Rescue selector can expose Password's two overflow tiles
# because their cursor-owned rows are outside its frame. The four-entry
# post-rescue selector cannot: it stages both halves in its two off-frame rows,
# then blanks the live aliases before the frame is copied.
SERVICE_BLANK_TILE = 0xB3
BLACKSMITH_BLANK_TILE = 0xB9
BLACKSMITH_SUFFIX_SOURCE_TILE = 0x9C
BLACKSMITH_SUFFIX_TILE = 0xB3
RESCUE_DELIVERY_SUFFIX_SOURCE_TILES = (0xA8, 0xBA)
RESCUE_DELIVERY_SUFFIX_TILES = (0x9C, 0xAE)

ORIGINAL_INSTALLED_LOAD = stairs_menu._load_helper()
ORIGINAL_INSTALLED_COPY = stairs_menu._copy_helper()
ORIGINAL_INSTALLED_EXIT = stairs_menu._status_exit_helper_bytes()
LOAD_SUPPORT_LENGTH = 51
COPY_SUPPORT_LENGTH = 77

SERVICE_LOOP_BANK = 6
SERVICE_LOOP_CALL_ADDRESS = 0x6268
SERVICE_LOOP_CALL_EXPECTED = bytes.fromhex("CDA169")
SERVICE_LOOP_TRAMPOLINE_ADDRESS = 0x7FF4
SERVICE_LOOP_TRAMPOLINE_EXPECTED = bytes(12)
NATIVE_TOWN_REFRESH_ADDRESS = 0x69A1

# The widened template ends at bank-7 WRAM $D8B3, but the bytes following it
# are not free: native dungeon UI writes through $D8F7.  Share the explicitly
# reserved bank-5 popup-state block declared by stairs_menu instead.  This
# lower slice retains the ten tile/attribute pairs in the added BG column plus
# its metadata and staged-tile state; stairs owns the upper slice.
POPUP_STATE_WRAM_BANK = stairs_menu.POPUP_STATE_WRAM_BANK
SAVED_COLUMN_ADDRESS = 0xD9C0
SAVED_DESTINATION_ADDRESS = 0xD9D4
SAVED_ROWS_ADDRESS = 0xD9D6
SAVED_FLAG_ADDRESS = 0xD9D7
SAVED_FLAG_END_ADDRESS = 0xD9D8
SAVED_FLAG_VALUE = 0xA5
SAVED_FLAG_END_VALUE = 0x5A
BLACKSMITH_TILE_BANK_ADDRESS = 0xD9D9
BLACKSMITH_TILE_FLAG_ADDRESS = 0xD9DA
BLACKSMITH_TILE_FLAG_VALUE = 0xA6
RESCUE_DELIVERY_TILE_FLAG_VALUE = 0xA7
MAXIMUM_SERVICE_ROWS = 10


class ServiceMenuError(ValueError):
    """The chained popup helpers, reservation, or exact menu set changed."""


def _offset(address, bank=RUNTIME_BANK):
    return extract.file_offset(bank, address)


def _exact_menu_detector(records=RESCUE_RECORDS):
    """Return with Z set only for the exact active group/index sequence."""
    payload = bytes.fromhex("F0B0") + bytes((0xFE, len(records), 0xC0))
    for slot, (index, group) in enumerate(records):
        address = 0xB2 + slot * 2
        payload += bytes.fromhex("F0") + bytes((address, 0xFE, index, 0xC0))
        payload += bytes.fromhex("F0") + bytes((address + 1, 0xFE, group))
        payload += bytes((0xC9 if slot == len(records) - 1 else 0xC0,))
    return payload


def _service_exit_helper_bytes():
    """Run both widened-popup cleanups after the native controller exit."""
    floor_cleanup = stairs_menu.floor_cleanup_address()
    restore = service_restore_address()
    return (
        bytes((0xCD, floor_cleanup & 0xFF, floor_cleanup >> 8))
        + bytes((0xCD, restore & 0xFF, restore >> 8, 0xC9))
    )


def _patched_status_exit_helper():
    """Tail-dispatch the chained stairs exit through service cleanup."""
    native_prefix = ORIGINAL_INSTALLED_EXIT[:8]
    result = (
        native_prefix
        + bytes((0xC3, SERVICE_EXIT_HELPER_ADDRESS & 0xFF,
                 SERVICE_EXIT_HELPER_ADDRESS >> 8, 0x00))
    )
    if len(result) != len(ORIGINAL_INSTALLED_EXIT):
        raise ServiceMenuError("chained controller-exit helper changed size")
    return result


def detector_bytes():
    """Return with Z set for any reviewed service-menu record set."""
    predicates = tuple(_exact_menu_detector(records) for records in SERVICE_RECORD_SETS)
    dispatch_length = 4 * (len(predicates) - 1) + 3
    addresses = []
    address = DETECTOR_ADDRESS + dispatch_length
    for predicate in predicates:
        addresses.append(address)
        address += len(predicate)
    dispatch = b"".join(
        bytes((0xCD, target & 0xFF, target >> 8, 0xC8))
        for target in addresses[:-1]
    ) + bytes((0xC3, addresses[-1] & 0xFF, addresses[-1] >> 8))
    return dispatch + b"".join(predicates)


def exact_detector_address(records):
    """Return an exact predicate embedded after the detector dispatcher."""
    try:
        index = SERVICE_RECORD_SETS.index(records)
    except ValueError as exc:
        raise ServiceMenuError("unknown service-menu record set") from exc
    return (
        DETECTOR_ADDRESS
        + 4 * (len(SERVICE_RECORD_SETS) - 1)
        + 3
        + sum(
            len(_exact_menu_detector(previous))
            for previous in SERVICE_RECORD_SETS[:index]
        )
    )


def rescue_detector_address():
    """Return the exact Rescue predicate embedded after the dispatcher."""
    return exact_detector_address(RESCUE_RECORDS)


def rescue_delivery_detector_address():
    """Return the completed-rescue delivery predicate after the dispatcher."""
    return exact_detector_address(RESCUE_DELIVERY_RECORDS)


def blacksmith_info_detector_address():
    """Return the exact Blacksmith Info predicate after the dispatcher."""
    return exact_detector_address(BLACKSMITH_INFO_RECORDS)


def load_support_address():
    return DETECTOR_ADDRESS + len(detector_bytes())


def _load_support_bytes():
    """Load the exact service template or delegate to the native copy."""
    standard = service_template_address()
    rescue = rescue_template_address()
    rescue_delivery = rescue_delivery_template_address()
    blacksmith = blacksmith_info_template_address()
    native = stairs_menu.NATIVE_TEMPLATE_ADDRESS
    service_body = (
        bytes((0x21, standard & 0xFF, standard >> 8))
        + bytes((
            0xCD,
            rescue_detector_address() & 0xFF,
            rescue_detector_address() >> 8,
        ))
        + bytes.fromhex("2003")
        + bytes((0x21, rescue & 0xFF, rescue >> 8))
        + bytes((
            0xCD,
            rescue_delivery_detector_address() & 0xFF,
            rescue_delivery_detector_address() >> 8,
        ))
        + bytes.fromhex("2003")
        + bytes((0x21, rescue_delivery & 0xFF, rescue_delivery >> 8))
        + bytes((
            0xCD,
            blacksmith_info_detector_address() & 0xFF,
            blacksmith_info_detector_address() >> 8,
        ))
        + bytes.fromhex("2003")
        + bytes((0x21, blacksmith & 0xFF, blacksmith >> 8))
        + bytes.fromhex("1100D8")
        + bytes((0x06, 10 * ENGLISH_COLUMNS * 2))
        + bytes.fromhex("C35B0A")
    )
    native_body = (
        bytes((0x21, native & 0xFF, native >> 8))
        + bytes.fromhex("1100D8068CC35B0A")
    )
    # Derive the relative jump from the complete service body.  A previous
    # hand-written +12 landed on the native LD HL immediate operand.
    return (
        bytes((0xCD, DETECTOR_ADDRESS & 0xFF, DETECTOR_ADDRESS >> 8))
        + bytes((0x20, len(service_body)))
        + service_body
        + native_body
    )


def copy_support_address():
    return load_support_address() + LOAD_SUPPORT_LENGTH


def _copy_support_bytes():
    """Copy a nine-column service frame or the native seven columns.

    The native renderer chooses one of the two CGB VRAM tile banks and updates
    the attributes inside its original 7-column/140-byte template footprint.
    Our widened bottom row lives beyond that footprint, so its seven horizontal
    cells must inherit the selected bank bit immediately before the BG copy.
    Otherwise a Rescue menu opened after the Yes/No prompt reads the border
    tile from the stale bank and displays garbage; warehouse happens to use
    bank zero and therefore used to hide the bug.
    """
    bottom = 0xD800 + 9 * ENGLISH_COLUMNS * 2
    first_bottom_attribute = bottom + 3
    bank_sync = (
        bytes.fromhex("C5FA03D8E608F6C7")
        + bytes((0x21, first_bottom_attribute & 0xFF,
                 first_bottom_attribute >> 8))
        + bytes((0x06, ENGLISH_INTERIOR_COLUMNS))
        + bytes.fromhex("22230520FBC1")
    )
    save = service_save_address()
    stage_blacksmith = blacksmith_tile_support_address()
    stage_rescue_delivery = rescue_delivery_tile_support_address()
    service_copy = (
        bytes((0xCD, save & 0xFF, save >> 8))
        + bytes((
            0xCD,
            rescue_delivery_detector_address() & 0xFF,
            rescue_delivery_detector_address() >> 8,
        ))
        + bytes.fromhex("2003")
        + bytes((
            0xCD,
            stage_rescue_delivery & 0xFF,
            stage_rescue_delivery >> 8,
        ))
        + bytes((
            0xCD,
            blacksmith_info_detector_address() & 0xFF,
            blacksmith_info_detector_address() >> 8,
        ))
        + bytes.fromhex("2003")
        + bytes((0xCD, stage_blacksmith & 0xFF, stage_blacksmith >> 8))
        + bytes((0x0E, ENGLISH_COLUMNS))
        + bytes.fromhex("2100D8CDEA0A")
        + bytes((0x21, bottom & 0xFF, bottom >> 8))
        + bytes((0x01, ENGLISH_COLUMNS, 0x01))
        + bytes.fromhex("C3EA0A")
    )
    service_body = bank_sync + service_copy
    native_body = bytes.fromhex(
        "0E072100D8CDEA0A217ED8010701C3EA0A"
    )
    return (
        bytes((0xCD, DETECTOR_ADDRESS & 0xFF, DETECTOR_ADDRESS >> 8))
        + bytes((0x20, len(service_body)))
        + service_body
        + native_body
    )


def service_save_address():
    return copy_support_address() + COPY_SUPPORT_LENGTH


def _patch_relative(raw, branch, target):
    distance = target - (branch + 2)
    if not -128 <= distance <= 127:
        raise ServiceMenuError("service-menu relative branch leaves its routine")
    raw[branch + 1] = distance & 0xFF


def _save_support_bytes():
    """Save the added rightmost BG column in both CGB VRAM banks.

    B is the native number of top rows and DE is the popup's top-left BG cell.
    The bottom border adds one row. All caller registers and both bank selectors
    are restored before the widened renderer resumes.
    """
    raw = bytearray.fromhex(
        "F5C5D5E5"          # preserve AF/BC/DE/HL
        "F04FF5F070F5"      # preserve VBK and SVBK
        "3E05E070"          # select reserved popup-state WRAM bank 5
        "AFEADAD9"          # clear staged suffix-tile marker
        "7BE6E06F"          # preserve the BG row bits from E in L
        "7BC608E61FB5"       # wrap x + 8 inside the same 32-tile row
        "EAD4D96F"          # save extra-column low destination and L
        "7AEAD5D967"        # keep the original BG row high byte in H
        "783CEAD6D94F"      # B + bottom row -> saved height and C
        "11C0D9"            # packed tile/attribute destination
    )
    loop = len(raw)
    raw += bytearray.fromhex(
        "C5E5"              # retain row counter and BG source
        "AFE04F010100CD6B0A"  # copy tile from VRAM bank 0
        "E13E01E04F010100CD6B0A"  # copy attribute from bank 1
        "7DC61F6F"          # advance from x+1 to same x next row
    )
    carry = len(raw)
    raw += bytearray.fromhex("300124")  # JR NC,+1 / INC H
    if raw[carry + 1] != 1:
        raise ServiceMenuError("service save carry branch changed")
    raw += bytearray.fromhex(
        "7CFE9C20023E9867"  # wrap first BG map $9Cxx back to $98xx
    )
    raw += bytearray.fromhex("C10D")
    branch = len(raw)
    raw += bytearray.fromhex("2000")
    _patch_relative(raw, branch, loop)
    raw += bytearray.fromhex(
        "3EA5EAD7D9"        # first saved-column magic byte
        "3E5AEAD8D9"        # second saved-column magic byte
        "F1E070F1E04F"      # restore SVBK and VBK
        "E1D1C1F1C9"        # restore registers
    )
    return bytes(raw)


def service_restore_address():
    return service_save_address() + len(_save_support_bytes())


def _restore_support_bytes():
    """Restore the saved column only after the drawn popup has disappeared.

    The dynamic-text selector records are transient: they can disappear while
    the popup itself is still on screen.  The first implementation treated
    that as the close signal and erased the added right border prematurely.
    Instead, test the native eight-column portion of the actual BG frame.  Its
    top-left/interior/interior ``$7E,$C0,$C0`` signature survives for the full
    popup lifetime and disappears when the native teardown really runs.
    """
    raw = bytearray.fromhex(
        "F5C5D5E5"          # preserve AF/BC/DE/HL
        "F04FF5F070F5"      # preserve VBK and SVBK
        "3E05E070"          # select reserved popup-state WRAM bank 5
        "FAD7D9FEA5"        # first saved-column magic byte
    )
    no_saved = len(raw)
    raw += bytearray.fromhex("C20000")  # JP NZ, epilogue
    raw += bytearray.fromhex("FAD8D9FE5A")  # second magic byte
    no_saved_end = len(raw)
    raw += bytearray.fromhex("C20000")  # JP NZ, epilogue
    raw += bytearray.fromhex(
        "AFE04F"            # inspect tile IDs in VRAM bank 0
        "FAD4D96FFAD5D967"  # saved extra-column destination
        "7DE6E05F"          # preserve the saved destination's BG row bits
        "7DD608E61FB36F"    # wrap x - 8 to the popup top-left
    )
    raw += bytearray.fromhex("7EFE7E")  # top-left corner
    frame_gone_corner = len(raw)
    raw += bytearray.fromhex("2000")
    raw += bytearray.fromhex("237EFEC0")  # first top interior
    frame_gone_first = len(raw)
    raw += bytearray.fromhex("2000")
    raw += bytearray.fromhex(
        "7DE6E05F"          # preserve the top row while crossing x = 31
        "7DC606E61FB36F"    # wrap to the seventh top interior
    )
    raw += bytearray.fromhex("7EFEC0")
    frame_gone_last = len(raw)
    raw += bytearray.fromhex("2000")
    still_open = len(raw)
    raw += bytearray.fromhex("C30000")  # JP epilogue
    restore = len(raw)
    for branch in (frame_gone_corner, frame_gone_first, frame_gone_last):
        _patch_relative(raw, branch, restore)
    raw += bytearray.fromhex(
        "AFEAD7D9EAD8D9"    # consume both magic bytes before VRAM
        "21C0D9"            # packed tile/attribute source
        "FAD4D95FFAD5D957"  # saved extra-column destination
        "FAD6D94F"          # saved row count
    )
    loop = len(raw)
    raw += bytearray.fromhex(
        "C5D5"              # retain row counter and BG destination
        "AFE04F010100CD6B0A"  # restore tile to VRAM bank 0
        "D13E01E04F010100CD6B0A"  # restore attribute to bank 1
        "7BC61F5F"          # advance from x+1 to same x next row
    )
    carry = len(raw)
    raw += bytearray.fromhex("300114")  # JR NC,+1 / INC D
    if raw[carry + 1] != 1:
        raise ServiceMenuError("service restore carry branch changed")
    raw += bytearray.fromhex(
        "7AFE9C20023E9857"  # wrap first BG map $9Cxx back to $98xx
    )
    raw += bytearray.fromhex("C10D")
    branch = len(raw)
    raw += bytearray.fromhex("2000")
    _patch_relative(raw, branch, loop)
    raw += bytearray.fromhex("FADAD9FEA6")
    no_blacksmith_tile = len(raw)
    raw += bytearray.fromhex("2000")
    raw += bytearray.fromhex(
        "AFEADAD9"          # consume suffix-tile marker before VRAM
        "FAD9D9E04F"        # select the renderer's recorded VRAM bank
        "21908B"            # stable blank tile $B9
        "11308B"            # staged suffix tile $B3
        "011000CD6B0A"      # copy one 16-byte tile
    )
    blacksmith_done = len(raw)
    raw += bytearray.fromhex("1800")
    rescue_delivery = len(raw)
    _patch_relative(raw, no_blacksmith_tile, rescue_delivery)
    raw += bytearray.fromhex("FEA7")
    no_rescue_delivery_tile = len(raw)
    raw += bytearray.fromhex("2000")
    raw += bytearray.fromhex(
        "AFEADAD9"          # consume delivery suffix marker before VRAM
        "FAD9D9E04F"        # select the renderer's recorded VRAM bank
        "21308B"            # stable blank tile $B3
        "11C089"            # first staged suffix tile $9C
        "011000CD6B0A"      # clear one 16-byte staged tile
        "21308B"            # stable blank tile $B3
        "11E08A"            # second staged suffix tile $AE
        "011000CD6B0A"      # clear one 16-byte staged tile
    )
    tile_done = len(raw)
    _patch_relative(raw, blacksmith_done, tile_done)
    _patch_relative(raw, no_rescue_delivery_tile, tile_done)
    done = len(raw)
    done_address = service_restore_address() + done
    for branch in (no_saved, no_saved_end, still_open):
        raw[branch + 1:branch + 3] = bytes(
            (done_address & 0xFF, done_address >> 8)
        )
    raw += bytearray.fromhex(
        "F1E070F1E04F"      # restore SVBK and VBK
        "E1D1C1F1C9"        # restore registers
    )
    return bytes(raw)


def blacksmith_tile_support_address():
    return service_restore_address() + len(_restore_support_bytes())


def _blacksmith_tile_support_bytes():
    """Stage Synthesis's suffix, clear its cursor alias, and sync spill banks."""
    source = 0x8000 + BLACKSMITH_SUFFIX_SOURCE_TILE * 16
    destination = 0x8000 + BLACKSMITH_SUFFIX_TILE * 16
    blank = 0x8000 + BLACKSMITH_BLANK_TILE * 16
    return (
        bytes.fromhex(
            "F5C5D5E5"      # preserve AF/BC/DE/HL
            "F04FF5F070F5"  # preserve VBK and SVBK
            "3E07E070"      # select the bank-7 staged frame
            "FA03D8E608"    # renderer-selected VRAM bank bit
            "0F0F0F"        # move bit 3 into bit 0
            "F5"            # retain bank 0/1 while updating attributes
            "0707074F"      # selected bank 0/1 -> attribute bit 3 in C
            "2121D8"        # first displayed spill-cell attribute
            "111200"        # one widened template row is $12 bytes
            "0607"          # seven displayed content rows
            "7EE6F7B1771905"  # replace bank bit and advance one row
            "20F7"          # loop over every displayed spill cell
            "F1"            # recover selected VRAM bank 0/1
            "4FE04F"        # keep it in C and select that VRAM bank
            "3E05E070"      # select reserved popup-state WRAM bank 5
            "79EAD9D9"      # record the renderer's VRAM bank
        )
        + bytes((0x21, source & 0xFF, source >> 8))
        + bytes((0x11, destination & 0xFF, destination >> 8))
        + bytes.fromhex(
            "011000CD6B0A"  # copy one 16-byte tile
        )
        + bytes((0x21, blank & 0xFF, blank >> 8))
        + bytes((0x11, source & 0xFF, source >> 8))
        + bytes.fromhex(
            "011000CD6B0A"  # blank the aliased unselected Quit cursor
            "3EA6EADAD9"    # mark suffix tile live
            "F1E070F1E04F"  # restore SVBK and VBK
            "E1D1C1F1C9"    # restore registers
        )
    )


def rescue_delivery_tile_support_address():
    return blacksmith_tile_support_address() + len(_blacksmith_tile_support_bytes())


def _rescue_delivery_tile_support_bytes():
    """Stage Password's suffix away from the four-entry cursor tile rows."""
    blank = 0x8000 + SERVICE_BLANK_TILE * 16
    sources = tuple(
        0x8000 + tile * 16 for tile in RESCUE_DELIVERY_SUFFIX_SOURCE_TILES
    )
    destinations = tuple(
        0x8000 + tile * 16 for tile in RESCUE_DELIVERY_SUFFIX_TILES
    )
    raw = bytearray.fromhex(
        "F5C5D5E5"        # preserve AF/BC/DE/HL
        "F04FF5F070F5"    # preserve VBK and SVBK
        "3E07E070"        # select the bank-7 staged frame
        "FA03D8E608"      # renderer-selected VRAM bank bit
        "0F0F0F"          # move bit 3 into bit 0
        "F5"              # retain bank 0/1 while updating attributes
        "0707074F"        # selected bank 0/1 -> attribute bit 3 in C
        "2121D8"          # first displayed spill-cell attribute
        "111200"          # one widened template row is $12 bytes
        "0607"            # seven possible displayed content rows
        "7EE6F7B1771905"  # replace bank bit and advance one row
        "20F7"            # loop over every displayed spill cell
        "F1"              # recover selected VRAM bank 0/1
        "4FE04F"          # keep it in C and select that VRAM bank
        "3E05E070"        # select reserved popup-state WRAM bank 5
        "79EAD9D9"        # record the renderer's VRAM bank
    )
    for source, destination in zip(sources, destinations):
        raw += bytes((0x21, source & 0xFF, source >> 8))
        raw += bytes((0x11, destination & 0xFF, destination >> 8))
        raw += bytes.fromhex("011000CD6B0A")
    for source in sources:
        raw += bytes((0x21, blank & 0xFF, blank >> 8))
        raw += bytes((0x11, source & 0xFF, source >> 8))
        raw += bytes.fromhex("011000CD6B0A")
    raw += bytearray.fromhex(
        "3EA7EADAD9"      # mark both staged suffix tiles live
        "F1E070F1E04F"    # restore SVBK and VBK
        "E1D1C1F1C9"      # restore registers
    )
    return bytes(raw)


def _service_loop_trampoline():
    """Run guarded cleanup after the native town BG refresh.

    The native refresh is what actually erases the seven-column popup.  The
    Rescue Password path leaves the town loop immediately afterward, so a
    pre-refresh check never gets a second chance to restore our ninth column.
    The far call preserves the native routine's return registers and flags.
    """
    restore = service_restore_address()
    return (
        bytes((0xCD, NATIVE_TOWN_REFRESH_ADDRESS & 0xFF,
               NATIVE_TOWN_REFRESH_ADDRESS >> 8))
        + bytes((0x3E, RUNTIME_BANK, 0x21, restore & 0xFF, restore >> 8))
        + bytes.fromhex("CDAC09")
        + bytes((0xC9,))
    )


def service_template_address():
    return (
        rescue_delivery_tile_support_address()
        + len(_rescue_delivery_tile_support_bytes())
    )


def rescue_template_address():
    return service_template_address() + len(service_template_bytes())


def rescue_delivery_template_address():
    return rescue_template_address() + len(rescue_template_bytes())


def blacksmith_info_template_address():
    return (
        rescue_delivery_template_address()
        + len(rescue_delivery_template_bytes())
    )


def _patched_load_helper():
    """Keep the stairs path inline and tail-dispatch everything else."""
    service_load = load_support_address()
    stairs_load = bytes((
        0x21,
        stairs_menu.TEMPLATE_ADDRESS & 0xFF,
        stairs_menu.TEMPLATE_ADDRESS >> 8,
    )) + bytes.fromhex("1100D8065AC35B0A")
    result = (
        bytes((0xCD, stairs_menu.HELPER_ADDRESS & 0xFF,
               stairs_menu.HELPER_ADDRESS >> 8))
        + bytes.fromhex("280A")
        + bytes((0xC3, service_load & 0xFF, service_load >> 8))
        + bytes(8)
        + stairs_load
    )
    if len(result) != len(ORIGINAL_INSTALLED_LOAD):
        raise ServiceMenuError("chained load helper changed size")
    return result


def _patched_copy_helper():
    """Keep the stairs path inline and tail-dispatch everything else."""
    service_copy = copy_support_address()
    stairs_copy = bytes.fromhex(
        "CD5E400E092100D8CDEA0A2148D8010901C3EA0A"
    )
    result = (
        bytes((0xCD, stairs_menu.HELPER_ADDRESS & 0xFF,
               stairs_menu.HELPER_ADDRESS >> 8))
        + bytes.fromhex("2811")
        + bytes((0xC3, service_copy & 0xFF, service_copy >> 8))
        + bytes(14)
        + stairs_copy
    )
    if len(result) != len(ORIGINAL_INSTALLED_COPY):
        raise ServiceMenuError("chained copy helper changed size")
    return result


def _cells_to_bytes(cells):
    return bytes(value for tile, attribute in cells for value in (tile, attribute))


def _service_template_bytes(
    overflow_bases=(), default_spill=SERVICE_BLANK_TILE, spill_overrides=None
):
    """Return a widened frame with only explicitly reviewed overflow tiles."""
    overflow_bases = frozenset(overflow_bases)
    spill_overrides = dict(spill_overrides or {})
    top = (
        [(0x7E, 0x8F)]
        + [(0xC0, 0x87)] * ENGLISH_INTERIOR_COLUMNS
        + [(0x7E, 0xAF)]
    )

    def content(base):
        spill = spill_overrides.get(
            base, base + 6 if base in overflow_bases else default_spill
        )
        tiles = [base + column for column in range(6)] + [spill]
        return (
            [(0x7F, 0x8F)]
            + [(tile, 0x87) for tile in tiles]
            + [(0x7F, 0xAF)]
        )

    bases = (0x90, 0xA2, 0xB4, 0x96, 0xA8, 0xBA, 0x9C, 0xAE)
    bottom = (
        [(0x7E, 0xCF)]
        + [(0xC0, 0xC7)] * ENGLISH_INTERIOR_COLUMNS
        + [(0x7E, 0xEF)]
    )
    result = _cells_to_bytes(top + sum((content(base) for base in bases), []) + bottom)
    if len(result) != 10 * ENGLISH_COLUMNS * 2:
        raise ServiceMenuError("service template has the wrong size")
    return result


def service_template_bytes():
    """Return the standard service frame with stable blank spill cells."""
    return _service_template_bytes()


def rescue_template_bytes():
    """Expose only the two tiles containing `Password`'s final pixel column."""
    return _service_template_bytes((0xA2, 0xB4))


def rescue_delivery_template_bytes():
    """Use off-frame staged tiles for the four-entry Password suffix."""
    return _service_template_bytes(
        spill_overrides=dict(zip(
            (0xA2, 0xB4), RESCUE_DELIVERY_SUFFIX_TILES
        )),
    )


def blacksmith_info_template_bytes():
    """Use a staged stable suffix tile only on Synthesis's spill row."""
    return _service_template_bytes(
        default_spill=BLACKSMITH_BLANK_TILE,
        spill_overrides={0x96: BLACKSMITH_SUFFIX_TILE},
    )


def runtime_payload():
    return (
        _service_exit_helper_bytes()
        + detector_bytes()
        + _load_support_bytes()
        + _copy_support_bytes()
        + _save_support_bytes()
        + _restore_support_bytes()
        + _blacksmith_tile_support_bytes()
        + _rescue_delivery_tile_support_bytes()
        + service_template_bytes()
        + rescue_template_bytes()
        + rescue_delivery_template_bytes()
        + blacksmith_info_template_bytes()
    )


RUNTIME_END = SUPPORT_ADDRESS + len(runtime_payload())


def owned_ranges():
    return (
        (
            _offset(LOAD_HELPER_ADDRESS),
            _offset(LOAD_HELPER_ADDRESS) + len(ORIGINAL_INSTALLED_LOAD),
        ),
        (
            _offset(COPY_HELPER_ADDRESS),
            _offset(COPY_HELPER_ADDRESS) + len(ORIGINAL_INSTALLED_COPY),
        ),
        (
            _offset(stairs_menu.STATUS_EXIT_HELPER_ADDRESS),
            _offset(stairs_menu.STATUS_EXIT_HELPER_ADDRESS)
            + len(ORIGINAL_INSTALLED_EXIT),
        ),
        (
            _offset(SERVICE_LOOP_CALL_ADDRESS, SERVICE_LOOP_BANK),
            _offset(SERVICE_LOOP_CALL_ADDRESS, SERVICE_LOOP_BANK)
            + len(SERVICE_LOOP_CALL_EXPECTED),
        ),
        (
            _offset(SERVICE_LOOP_TRAMPOLINE_ADDRESS, SERVICE_LOOP_BANK),
            _offset(SERVICE_LOOP_TRAMPOLINE_ADDRESS, SERVICE_LOOP_BANK)
            + len(SERVICE_LOOP_TRAMPOLINE_EXPECTED),
        ),
        (_offset(SUPPORT_ADDRESS), _offset(RUNTIME_END)),
    )


def verify_source(rom):
    rom = bytes(rom)
    expected = (
        (LOAD_HELPER_ADDRESS, ORIGINAL_INSTALLED_LOAD, "stairs load helper"),
        (COPY_HELPER_ADDRESS, ORIGINAL_INSTALLED_COPY, "stairs copy helper"),
        (
            stairs_menu.STATUS_EXIT_HELPER_ADDRESS,
            ORIGINAL_INSTALLED_EXIT,
            "stairs controller-exit helper",
        ),
    )
    for address, raw, label in expected:
        actual = rom[_offset(address):_offset(address) + len(raw)]
        if actual != raw:
            raise ServiceMenuError(
                "%s changed at %s"
                % (label, extract.location(RUNTIME_BANK, address))
            )
    loop = rom[
        _offset(SERVICE_LOOP_CALL_ADDRESS, SERVICE_LOOP_BANK):
        _offset(SERVICE_LOOP_CALL_ADDRESS, SERVICE_LOOP_BANK)
        + len(SERVICE_LOOP_CALL_EXPECTED)
    ]
    if loop != SERVICE_LOOP_CALL_EXPECTED:
        raise ServiceMenuError(
            "town refresh call changed at %s"
            % extract.location(SERVICE_LOOP_BANK, SERVICE_LOOP_CALL_ADDRESS)
        )
    trampoline = rom[
        _offset(SERVICE_LOOP_TRAMPOLINE_ADDRESS, SERVICE_LOOP_BANK):
        _offset(SERVICE_LOOP_TRAMPOLINE_ADDRESS, SERVICE_LOOP_BANK)
        + len(SERVICE_LOOP_TRAMPOLINE_EXPECTED)
    ]
    if trampoline != SERVICE_LOOP_TRAMPOLINE_EXPECTED:
        raise ServiceMenuError(
            "service cleanup trampoline is not empty at %s"
            % extract.location(SERVICE_LOOP_BANK, SERVICE_LOOP_TRAMPOLINE_ADDRESS)
        )
    reserved = rom[_offset(SUPPORT_ADDRESS):_offset(RUNTIME_END)]
    if len(reserved) != len(runtime_payload()) or any(reserved):
        raise ServiceMenuError(
            "service-menu reservation is not empty at %s"
            % extract.location(RUNTIME_BANK, SUPPORT_ADDRESS)
        )


def install(rom, checksums=True):
    """Return a stairs-patched ROM with the reviewed service popup widened."""
    verify_source(rom)
    out = bytearray(rom)
    out[
        _offset(LOAD_HELPER_ADDRESS):
        _offset(LOAD_HELPER_ADDRESS) + len(ORIGINAL_INSTALLED_LOAD)
    ] = _patched_load_helper()
    out[
        _offset(COPY_HELPER_ADDRESS):
        _offset(COPY_HELPER_ADDRESS) + len(ORIGINAL_INSTALLED_COPY)
    ] = _patched_copy_helper()
    out[
        _offset(stairs_menu.STATUS_EXIT_HELPER_ADDRESS):
        _offset(stairs_menu.STATUS_EXIT_HELPER_ADDRESS)
        + len(ORIGINAL_INSTALLED_EXIT)
    ] = _patched_status_exit_helper()
    loop_at = _offset(SERVICE_LOOP_CALL_ADDRESS, SERVICE_LOOP_BANK)
    out[loop_at:loop_at + len(SERVICE_LOOP_CALL_EXPECTED)] = bytes((
        0xCD,
        SERVICE_LOOP_TRAMPOLINE_ADDRESS & 0xFF,
        SERVICE_LOOP_TRAMPOLINE_ADDRESS >> 8,
    ))
    trampoline_at = _offset(
        SERVICE_LOOP_TRAMPOLINE_ADDRESS, SERVICE_LOOP_BANK
    )
    trampoline = _service_loop_trampoline()
    if len(trampoline) != len(SERVICE_LOOP_TRAMPOLINE_EXPECTED):
        raise ServiceMenuError("service cleanup trampoline changed size")
    out[trampoline_at:trampoline_at + len(trampoline)] = trampoline
    out[_offset(SUPPORT_ADDRESS):_offset(RUNTIME_END)] = runtime_payload()
    if checksums:
        fix_checksums(out)
    return bytes(out)


def summary(rom, approved=None):
    verify_source(rom)
    approved = approved or english_font.load_approved()
    labels = []
    for menu, indices, texts in SERVICE_LABEL_SETS:
        for index, text in zip(indices, texts):
            width = sum(approved.advances[character] for character in text)
            native_text_pixels = (
                NATIVE_INTERIOR_COLUMNS * TILE_PIXELS - TEXT_START_X
            )
            english_text_pixels = TEXT_RIGHT_EDGE - TEXT_START_X
            labels.append({
                "menu": menu,
                "group": SERVICE_GROUP,
                "index": index,
                "text": text,
                "renderer_pixels": width,
                "text_start_pixels": TEXT_START_X,
                "native_clearance_pixels": native_text_pixels - width,
                "english_clearance_pixels": english_text_pixels - width,
            })
    return {
        "schema": "shiren-gb2-service-menus-v2",
        "runtime_bank": RUNTIME_BANK,
        "load_helper": extract.location(RUNTIME_BANK, LOAD_HELPER_ADDRESS),
        "copy_helper": extract.location(RUNTIME_BANK, COPY_HELPER_ADDRESS),
        "controller_exit_helper": extract.location(
            RUNTIME_BANK, stairs_menu.STATUS_EXIT_HELPER_ADDRESS
        ),
        "service_exit_helper": extract.location(
            RUNTIME_BANK, SERVICE_EXIT_HELPER_ADDRESS
        ),
        "support": extract.location(RUNTIME_BANK, SUPPORT_ADDRESS),
        "save_helper": extract.location(RUNTIME_BANK, service_save_address()),
        "restore_helper": extract.location(
            RUNTIME_BANK, service_restore_address()
        ),
        "blacksmith_tile_helper": extract.location(
            RUNTIME_BANK, blacksmith_tile_support_address()
        ),
        "rescue_delivery_tile_helper": extract.location(
            RUNTIME_BANK, rescue_delivery_tile_support_address()
        ),
        "template": extract.location(RUNTIME_BANK, service_template_address()),
        "rescue_template": extract.location(
            RUNTIME_BANK, rescue_template_address()
        ),
        "rescue_delivery_template": extract.location(
            RUNTIME_BANK, rescue_delivery_template_address()
        ),
        "blacksmith_info_template": extract.location(
            RUNTIME_BANK, blacksmith_info_template_address()
        ),
        "town_refresh_hook": extract.location(
            SERVICE_LOOP_BANK, SERVICE_LOOP_CALL_ADDRESS
        ),
        "town_refresh_trampoline": extract.location(
            SERVICE_LOOP_BANK, SERVICE_LOOP_TRAMPOLINE_ADDRESS
        ),
        "saved_column_scratch": "$%04X-$%04X" % (
            SAVED_COLUMN_ADDRESS, BLACKSMITH_TILE_FLAG_ADDRESS
        ),
        "saved_column_wram_bank": POPUP_STATE_WRAM_BANK,
        "runtime_end": extract.location(RUNTIME_BANK, RUNTIME_END),
        "detector_sha1": sha1(detector_bytes()).hexdigest(),
        "load_support_sha1": sha1(_load_support_bytes()).hexdigest(),
        "copy_support_sha1": sha1(_copy_support_bytes()).hexdigest(),
        "save_support_sha1": sha1(_save_support_bytes()).hexdigest(),
        "restore_support_sha1": sha1(_restore_support_bytes()).hexdigest(),
        "blacksmith_tile_support_sha1": sha1(
            _blacksmith_tile_support_bytes()
        ).hexdigest(),
        "rescue_delivery_tile_support_sha1": sha1(
            _rescue_delivery_tile_support_bytes()
        ).hexdigest(),
        "town_refresh_trampoline_sha1": sha1(
            _service_loop_trampoline()
        ).hexdigest(),
        "load_helper_sha1": sha1(_patched_load_helper()).hexdigest(),
        "copy_helper_sha1": sha1(_patched_copy_helper()).hexdigest(),
        "controller_exit_helper_sha1": sha1(
            _patched_status_exit_helper()
        ).hexdigest(),
        "service_exit_helper_sha1": sha1(
            _service_exit_helper_bytes()
        ).hexdigest(),
        "template_sha1": sha1(service_template_bytes()).hexdigest(),
        "rescue_template_sha1": sha1(
            rescue_template_bytes()
        ).hexdigest(),
        "rescue_delivery_template_sha1": sha1(
            rescue_delivery_template_bytes()
        ).hexdigest(),
        "blacksmith_info_template_sha1": sha1(
            blacksmith_info_template_bytes()
        ).hexdigest(),
        "runtime_payload_sha1": sha1(runtime_payload()).hexdigest(),
        "runtime_payload_bytes": len(runtime_payload()),
        "native_columns": NATIVE_COLUMNS,
        "english_columns": ENGLISH_COLUMNS,
        "native_interior_pixels": NATIVE_INTERIOR_COLUMNS * TILE_PIXELS,
        "english_interior_pixels": ENGLISH_INTERIOR_COLUMNS * TILE_PIXELS,
        "labels": labels,
    }
