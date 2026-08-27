#!/usr/bin/env python3
"""Measure GB2 text with the game's composer and renderer geometry.

There are two independent horizontal limits:

* the ROM-source composer at 0:$312B starts a new line when adding a glyph
  reaches $90 (144), so a source line must stay below 144 pixels;
* the pixel renderer accepts a pen position of exactly 144 and wraps before a
  slice that would reach $91 (145).

Keeping both models visible is important.  A string can fit the painted canvas
yet still be reflowed by the composer, and F7 horizontal spacing is applied by
the renderer without being included in the composer's counter.
"""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Optional

import codec
import extract
import font


CANVAS_TILE_COLUMNS = 18
CANVAS_WIDTH_PIXELS = CANVAS_TILE_COLUMNS * 8
COMPOSER_WRAP_AT = 0x90
RENDERER_WRAP_AT = 0x91
RENDERER_AUTO_LINE_ADVANCE = 10

FULL_RENDERER_ENTRY = (0, 0x35ED)
DIRECT_RENDERER_ENTRY = (3, 0x5E62)
GLYPH_RENDERER_ENTRY = (3, 0x6EDD)
CANVAS_ADDRESS_ENTRY = (3, 0x6F46)


class LayoutError(ValueError):
    """An inserted source line would be reflowed or spill past the canvas."""


@dataclass(frozen=True)
class SurfaceProfile:
    """Mode-derived behavior shared by a family of runtime text surfaces."""

    name: str
    representative_mode: int
    initial_y: int
    explicit_line_advance: int
    composer_line_limit: Optional[int]
    safe_full_lines: Optional[int]
    renderer: str = "full"


SURFACE_PROFILES = {
    "dialogue": SurfaceProfile(
        name="dialogue",
        representative_mode=0x02,
        initial_y=21,
        explicit_line_advance=11,
        composer_line_limit=3,
        safe_full_lines=3,
    ),
    "full_screen": SurfaceProfile(
        name="full_screen",
        representative_mode=0x08,
        initial_y=1,
        explicit_line_advance=11,
        # The composer permits eleven lines.  The longest referenced stock
        # records use ten, which also stays inside the complete WRAM rows.
        composer_line_limit=11,
        safe_full_lines=10,
    ),
    "stepped_window": SurfaceProfile(
        name="stepped_window",
        representative_mode=0x10,
        initial_y=24,
        explicit_line_advance=16,
        composer_line_limit=None,
        safe_full_lines=None,
    ),
    "positioned": SurfaceProfile(
        name="positioned",
        representative_mode=0x04,
        initial_y=0,
        explicit_line_advance=10,
        composer_line_limit=1,
        safe_full_lines=1,
        renderer="direct",
    ),
}


def initial_y(mode):
    """Return the initial baseline selected by 0:$363E-$3654."""
    if mode == 0x08:
        return 1
    if mode == 0x10:
        return 24
    return 21


def explicit_line_advance(mode):
    """Return the FD line movement selected by 0:$382F-$3849."""
    return 16 if mode & 0x10 else 11


def composer_line_limit(mode):
    """Return the number of lines the source composer permits per chunk."""
    if mode == 0x10:
        return None
    return 11 if mode == 0x08 else 3


def profile_for_mode(mode):
    """Classify a full-renderer mode by its geometry-affecting behavior."""
    if mode == 0x08:
        return SURFACE_PROFILES["full_screen"]
    if mode == 0x10:
        return SURFACE_PROFILES["stepped_window"]
    return SURFACE_PROFILES["dialogue"]


def _width(rom, page, code):
    index = page * 0x100 + code
    at = font.banked_offset(font.WIDTH_BANK, font.WIDTH_ADDRESS) + index
    if at >= len(rom):
        raise ValueError("ROM is too small for width-table entry $%03X" % index)
    return rom[at]


def composer_advance(rom, encoded):
    """Return the single width counted by the ROM-source composer."""
    encoded = bytes(encoded)
    location = font.glyph_location(encoded)
    return _width(rom, location.width_index // 0x100, location.width_index & 0xFF)


def renderer_slice_advances(rom, encoded):
    """Return each pen movement made while the renderer consumes a glyph.

    A prefixed width of ten or more selects an eight-pixel bitmap slice and
    recursively consumes the following slot.  The final movement can therefore
    differ from the first width-table byte: the opening's first width-12 glyph
    advances 8 + 3 = 11 pixels at runtime.
    """
    encoded = bytes(encoded)
    location = font.glyph_location(encoded)
    page = location.width_index // 0x100
    code = location.width_index & 0xFF
    out = []
    for _piece in range(0x100):
        width = _width(rom, page, code)
        out.append(8 if width >= 10 else width)
        if width < 10:
            return tuple(out)
        code += 1
        if code > 0xFF:
            page += 1
            code = 0
    raise ValueError("glyph continuation chain does not terminate")


def renderer_advance(rom, encoded):
    """Return the total native pen movement for one rendered glyph."""
    return sum(renderer_slice_advances(rom, encoded))


@dataclass(frozen=True)
class GlyphPlacement:
    offset: int
    encoded: bytes
    slice_index: int
    x: int
    y: int
    advance: int
    auto_wrapped: bool


@dataclass(frozen=True)
class RendererLayout:
    mode: int
    start_x: int
    start_y: int
    final_x: int
    final_y: int
    placements: tuple
    explicit_breaks: tuple
    boundaries: tuple
    hspace_overflows: tuple

    @property
    def auto_wraps(self):
        return tuple(item for item in self.placements if item.auto_wrapped)

    @property
    def line_widths(self):
        """Return final pen extents for each visited baseline."""
        widths = {}
        for item in self.placements:
            widths[item.y] = max(widths.get(item.y, 0), item.x + item.advance)
        return tuple(widths[y] for y in sorted(widths))

    @property
    def rightmost_pen(self):
        """Return the furthest exclusive x position reached by painted glyphs."""
        return max((item.x + item.advance for item in self.placements), default=self.start_x)


def renderer_layout(rom, data, mode=0x02, start_x=None, start_y=None):
    """Run exact staged bytes through the renderer's horizontal pen model."""
    rom = bytes(rom)
    data = bytes(data)
    x = 0 if start_x is None else start_x
    y = initial_y(mode) if start_y is None else start_y
    origin_x, origin_y = x, y
    placements = []
    breaks = []
    boundaries = []
    hspace_overflows = []
    offset = 0
    for token in codec.parse(data):
        if token.kind in ("glyph", "kanji"):
            for piece, advance in enumerate(renderer_slice_advances(rom, token.raw)):
                wrapped = x + advance >= RENDERER_WRAP_AT
                if wrapped:
                    x = 0
                    y += RENDERER_AUTO_LINE_ADVANCE
                placements.append(
                    GlyphPlacement(
                        offset=offset,
                        encoded=token.raw,
                        slice_index=piece,
                        x=x,
                        y=y,
                        advance=advance,
                        auto_wrapped=wrapped,
                    )
                )
                x = (x + advance) & 0xFF
        elif token.code == 0xF7:
            before = x
            x = (x + token.args[0]) & 0xFF
            if before + token.args[0] > CANVAS_WIDTH_PIXELS:
                hspace_overflows.append((offset, before, token.args[0], x))
        elif token.code == 0xFD:
            breaks.append((offset, x, y))
            x = 0
            y = (y + explicit_line_advance(mode)) & 0xFF
        elif token.code in (0xFB, 0xFC):
            boundaries.append((offset, codec.CONTROLS[token.code], x, y))
            if token.code == 0xFC:
                break
        offset += len(token.raw)
    return RendererLayout(
        mode=mode,
        start_x=origin_x,
        start_y=origin_y,
        final_x=x,
        final_y=y,
        placements=tuple(placements),
        explicit_breaks=tuple(breaks),
        boundaries=tuple(boundaries),
        hspace_overflows=tuple(hspace_overflows),
    )


def direct_layout(rom, data, start_x, start_y):
    """Measure bytes consumed by the positioned drawer at ``3:$5E62``.

    This entry is intentionally not modeled with :func:`renderer_layout`.  It
    recognizes only F0-F2 as two-byte glyph prefixes, stops at FF, and passes
    every other byte straight to the glyph renderer.  Consequently bytes such
    as FD and F7 are glyph codes here, not newline or spacing controls.
    """
    rom = bytes(rom)
    data = bytes(data)
    x, y = start_x, start_y
    placements = []
    offset = 0
    while offset < len(data):
        code = data[offset]
        if code == codec.TERMINATOR:
            break
        if code in (0xF0, 0xF1, 0xF2):
            if offset + 1 >= len(data):
                raise ValueError(
                    "truncated direct-renderer prefix %02X at offset %d"
                    % (code, offset)
                )
            encoded = data[offset:offset + 2]
        else:
            encoded = data[offset:offset + 1]
        for piece, advance in enumerate(renderer_slice_advances(rom, encoded)):
            wrapped = x + advance >= RENDERER_WRAP_AT
            if wrapped:
                x = 0
                y += RENDERER_AUTO_LINE_ADVANCE
            placements.append(
                GlyphPlacement(
                    offset=offset,
                    encoded=encoded,
                    slice_index=piece,
                    x=x,
                    y=y,
                    advance=advance,
                    auto_wrapped=wrapped,
                )
            )
            x = (x + advance) & 0xFF
        offset += len(encoded)
    return RendererLayout(
        mode=0,
        start_x=start_x,
        start_y=start_y,
        final_x=x,
        final_y=y,
        placements=tuple(placements),
        explicit_breaks=(),
        boundaries=(),
        hspace_overflows=(),
    )


def direct_alignment_width(rom, data):
    """Mirror the width accumulator at ``3:$6DDC``.

    The right-alignment helper is related to the positioned drawer, but it is
    not identical to it: F0-F2 consume a following glyph byte, F3-FE are
    skipped, and each accepted glyph contributes only its first width-table
    value.  The accumulator is an eight-bit Game Boy register, so additions
    wrap at 256 exactly as they do in the ROM.
    """
    rom = bytes(rom)
    data = bytes(data)
    width = 0
    offset = 0
    while offset < len(data):
        code = data[offset]
        offset += 1
        if code == codec.TERMINATOR:
            break
        if code >= 0xF3:
            continue
        if code >= 0xF0:
            if offset >= len(data):
                raise ValueError(
                    "truncated alignment prefix %02X at offset %d"
                    % (code, offset - 1)
                )
            encoded = data[offset - 1:offset + 1]
            offset += 1
        else:
            encoded = data[offset - 1:offset]
        width = (width + composer_advance(rom, encoded)) & 0xFF
    return width


def right_aligned_direct_layout(rom, data, anchor_x, start_y):
    """Measure a positioned string after the ROM's right-alignment step."""
    width = direct_alignment_width(rom, data)
    start_x = (anchor_x - width) & 0xFF
    return direct_layout(rom, data, start_x=start_x, start_y=start_y)


def validate_direct_surface(rom, data, start_x, start_y, right_edge):
    """Validate one positioned string against an exclusive visual right edge.

    ``right_edge`` is a pen coordinate: a final pen equal to it fits.  Any
    automatic physical-canvas wrap is a failure even if the wrapped glyph then
    happens to have a small x coordinate.
    """
    if not 0 <= start_x <= right_edge <= CANVAS_WIDTH_PIXELS:
        raise ValueError(
            "invalid positioned surface x range %d..%d" % (start_x, right_edge)
        )
    measured = direct_layout(rom, data, start_x=start_x, start_y=start_y)
    if measured.auto_wraps:
        first = measured.auto_wraps[0]
        raise LayoutError(
            "positioned text automatically wraps at source offset %d"
            % first.offset
        )
    if measured.rightmost_pen > right_edge:
        raise LayoutError(
            "positioned text reaches x=%d beyond visual edge x=%d"
            % (measured.rightmost_pen, right_edge)
        )
    return measured


def validate_direct_right_aligned_surface(rom, data, left_edge, anchor_x, start_y):
    """Validate text positioned by ``3:$6E07`` inside a visual panel."""
    if not 0 <= left_edge <= anchor_x <= CANVAS_WIDTH_PIXELS:
        raise ValueError(
            "invalid right-aligned surface x range %d..%d"
            % (left_edge, anchor_x)
        )
    measured = right_aligned_direct_layout(
        rom, data, anchor_x=anchor_x, start_y=start_y
    )
    if measured.start_x < left_edge or measured.start_x > anchor_x:
        raise LayoutError(
            "right-aligned text starts at x=%d outside visual range %d..%d"
            % (measured.start_x, left_edge, anchor_x)
        )
    if measured.auto_wraps:
        first = measured.auto_wraps[0]
        raise LayoutError(
            "right-aligned text automatically wraps at source offset %d"
            % first.offset
        )
    if measured.rightmost_pen > anchor_x:
        raise LayoutError(
            "right-aligned text reaches x=%d beyond anchor x=%d"
            % (measured.rightmost_pen, anchor_x)
        )
    return measured


@dataclass(frozen=True)
class SourceLine:
    surface: int
    line: int
    start_offset: int
    end_offset: int
    composer_pixels: int
    renderer_pixels: int
    dynamic: bool


@dataclass(frozen=True)
class RuntimeWidthContract:
    """Translation-time bounds for runtime-generated source substitutions."""

    player_name_max_bytes: int
    player_name_codes: tuple
    f6_bounds: Optional[dict] = None


@dataclass(frozen=True)
class RuntimeF6Bound:
    """A translated maximum for one classified F6 consumer."""

    kind: str
    composer_pixels: int
    renderer_pixels: int


@dataclass(frozen=True)
class DynamicExpansion:
    offset: int
    kind: str
    composer_pixels: Optional[int]
    renderer_pixels: Optional[int]

    @property
    def bounded(self):
        return self.composer_pixels is not None and self.renderer_pixels is not None


@dataclass(frozen=True)
class SourceLayout:
    mode: int
    lines: tuple
    dynamic_offsets: tuple
    bounded_dynamic_offsets: tuple = ()
    unresolved_dynamic_offsets: tuple = ()
    dynamic_expansions: tuple = ()
    soft_wraps: tuple = ()

    @property
    def composer_overflows(self):
        return tuple(line for line in self.lines
                     if line.composer_pixels >= COMPOSER_WRAP_AT)

    @property
    def renderer_overflows(self):
        return tuple(line for line in self.lines
                     if line.renderer_pixels > CANVAS_WIDTH_PIXELS)

    @property
    def line_limit_overflows(self):
        limit = composer_line_limit(self.mode)
        if limit is None:
            return ()
        counts = {}
        for line in self.lines:
            counts[line.surface] = max(counts.get(line.surface, 0), line.line + 1)
        return tuple((surface, count) for surface, count in sorted(counts.items())
                     if count > limit)

    @property
    def safe(self):
        return not (
            self.unresolved_dynamic_offsets
            or self.composer_overflows
            or self.renderer_overflows
            or self.line_limit_overflows
        )


def english_runtime_width_contract(f6_bounds=None):
    """Return the name-entry limits used by an English translation build.

    Bank 18 ``$5160-$5168`` caps the editable byte count at seven.  All
    translation glyphs are one-byte codes, so the widest permitted English
    code is a conservative per-byte player-name bound.
    """
    import english

    return RuntimeWidthContract(
        player_name_max_bytes=7,
        player_name_codes=tuple(sorted(english.ENGLISH_CODES.values())),
        f6_bounds=None if f6_bounds is None else dict(f6_bounds),
    )


def _maximum_code_widths(rom, codes):
    composer = max(composer_advance(rom, bytes((code,))) for code in codes)
    renderer = max(renderer_advance(rom, bytes((code,))) for code in codes)
    return composer, renderer


def dynamic_expansion(rom, token, offset, runtime_contract, record_id=None):
    """Return a conservative staged-width expansion for one F4-F6 token."""
    if token.code == 0xF4:
        byte_count = token.args[0]
        if not 1 <= byte_count <= 4:
            return DynamicExpansion(offset, "unsigned_integer", None, None)
        maximum_value = (1 << (byte_count * 8)) - 1
        digits = len(str(maximum_value))
        composer, renderer = _maximum_code_widths(rom, range(10))
        return DynamicExpansion(
            offset,
            "unsigned_integer_%d_byte" % byte_count,
            digits * composer,
            digits * renderer,
        )
    if token.code == 0xF5:
        if runtime_contract is None:
            return DynamicExpansion(offset, "player_name", None, None)
        composer, renderer = _maximum_code_widths(
            rom, runtime_contract.player_name_codes
        )
        if token.args == b"\xFF":
            count = runtime_contract.player_name_max_bytes
            kind = "player_name"
        else:
            count = 1
            kind = "player_name_byte"
        return DynamicExpansion(offset, kind, count * composer, count * renderer)
    if token.code == 0xF6:
        mode = token.args[0]
        # Mode 1 resolves a runtime group/index pair.  Mode 3 copies an
        # FF-terminated generic string from banked WRAM $DE00+offset; callers
        # cache directory records, formatted numbers and composed item names.
        # The legacy source spelling is `<number>`, but it is not necessarily
        # numeric.
        kind = {0x01: "record_lookup", 0x03: "cached_string"}.get(
            mode, "source_f6_mode_%02X" % mode
        )
        if runtime_contract is not None and runtime_contract.f6_bounds:
            bound = runtime_contract.f6_bounds.get((record_id, token.raw))
            if bound is not None:
                return DynamicExpansion(
                    offset,
                    bound.kind,
                    bound.composer_pixels,
                    bound.renderer_pixels,
                )
        return DynamicExpansion(offset, kind, None, None)
    raise AssertionError("not a dynamic source token: %02X" % token.code)


def source_layout(
    rom,
    data,
    mode=0x02,
    runtime_contract=None,
    record_id=None,
    simulate_soft_wrap=False,
):
    """Measure explicit ROM-source lines without guessing runtime substitutions.

    Dynamic F4-F6 substitutions are reported through ``dynamic_offsets``.
    When ``runtime_contract`` is supplied, numeric F4 and player-name F5
    expansions contribute their conservative maximum widths. F6 lookup/cache
    strings contribute only when the contract contains a bound for this stable
    record and token; otherwise they remain explicitly unresolved. F3 is a
    zero-width soft-wrap marker. F7 affects painted width but not the
    composer's counter.
    """
    if simulate_soft_wrap:
        return _soft_wrapped_source_layout(
            rom,
            data,
            mode=mode,
            runtime_contract=runtime_contract,
            record_id=record_id,
        )

    rom = bytes(rom)
    data = bytes(data)
    surface = line = 0
    line_start = 0
    composer_pixels = renderer_pixels = 0
    dynamic = False
    dynamic_offsets = []
    bounded_dynamic_offsets = []
    unresolved_dynamic_offsets = []
    expansions = []
    lines = []
    offset = 0
    after_boundary = False
    pending_page = False

    def resume_after_page():
        """Start the next paced chunk without discarding the current pen width.

        FB pauses the renderer but does not move its pen.  A following FD ends
        the old physical line and starts line zero of the next paced chunk.  If
        text resumes without FD, its width must instead accumulate on the same
        physical line even though it belongs to the next chunk.
        """
        nonlocal surface, line, pending_page
        if pending_page:
            surface += 1
            line = 0
            pending_page = False

    def finish(end_offset):
        lines.append(
            SourceLine(
                surface=surface,
                line=line,
                start_offset=line_start,
                end_offset=end_offset,
                composer_pixels=composer_pixels,
                renderer_pixels=renderer_pixels,
                dynamic=dynamic,
            )
        )

    for token in codec.parse_source(data):
        if token.kind in ("glyph", "kanji"):
            resume_after_page()
            after_boundary = False
            composer_pixels += composer_advance(rom, token.raw)
            renderer_pixels += renderer_advance(rom, token.raw)
        elif token.kind == "source_control":
            resume_after_page()
            after_boundary = False
            dynamic = True
            dynamic_offsets.append(offset)
            expansion = dynamic_expansion(
                rom, token, offset, runtime_contract, record_id=record_id
            )
            expansions.append(expansion)
            if expansion.bounded:
                bounded_dynamic_offsets.append(offset)
                composer_pixels += expansion.composer_pixels
                renderer_pixels += expansion.renderer_pixels
            else:
                unresolved_dynamic_offsets.append(offset)
        elif token.code == 0xF7:
            resume_after_page()
            after_boundary = False
            renderer_pixels += token.args[0]
        elif token.code == 0xFD:
            after_boundary = False
            finish(offset)
            if pending_page:
                surface += 1
                line = 0
                pending_page = False
            else:
                line += 1
            line_start = offset + len(token.raw)
            composer_pixels = renderer_pixels = 0
            dynamic = False
        elif token.code == 0xFB:
            # FB is only a wait.  Live tutorial playback proves that neither
            # the composer nor renderer resets x here: omitting the stock FD
            # from `<page><br>` concatenates the next sentence on this line.
            pending_page = True
            after_boundary = False
        elif token.code == 0xFC:
            # FC returns from this renderer invocation and therefore owns the
            # actual box/canvas reset.  In the common `<page><box>` pair, the
            # pending FB does not invent an empty paced chunk.
            if not after_boundary:
                finish(offset)
            surface += 1
            after_boundary = True
            line = 0
            line_start = offset + len(token.raw)
            composer_pixels = renderer_pixels = 0
            dynamic = False
            pending_page = False
        elif token.code == 0xF3:
            resume_after_page()
            after_boundary = False
        offset += len(token.raw)
    if line_start < len(data) or not lines:
        finish(len(data))
    return SourceLayout(
        mode=mode,
        lines=tuple(lines),
        dynamic_offsets=tuple(dynamic_offsets),
        bounded_dynamic_offsets=tuple(bounded_dynamic_offsets),
        unresolved_dynamic_offsets=tuple(unresolved_dynamic_offsets),
        dynamic_expansions=tuple(expansions),
    )


def _soft_wrapped_source_layout(
    rom, data, mode=0x02, runtime_contract=None, record_id=None
):
    """Measure the source after the native F3 rollback policy is applied.

    F3 records the current source/output positions. If a later glyph reaches
    the composer's 144-pixel threshold, bank 4:$724B rewinds to the most recent
    marker and replaces it with FD. The remainder is then composed on the next
    line. This is especially important for streamed combat messages: a short
    runtime name stays on one line while a long one can break at a translator-
    selected word boundary.

    The simulation remains conservative for runtime substitutions by using the
    supplied per-consumer bounds. An overflow before the latest checkpoint is
    not rescued by a marker that the real composer has not reached yet.
    """
    rom = bytes(rom)
    data = bytes(data)
    surface = line = 0
    line_start = 0
    units = []
    checkpoint = None
    unrecoverable = False
    dynamic_offsets = []
    bounded_dynamic_offsets = []
    unresolved_dynamic_offsets = []
    expansions = []
    lines = []
    soft_wraps = []
    offset = 0
    after_boundary = False
    pending_page = False

    def totals():
        return (
            sum(unit[1] for unit in units),
            sum(unit[2] for unit in units),
            any(unit[3] for unit in units),
        )

    def finish(end_offset):
        composer_pixels, renderer_pixels, dynamic = totals()
        lines.append(
            SourceLine(
                surface=surface,
                line=line,
                start_offset=line_start,
                end_offset=end_offset,
                composer_pixels=composer_pixels,
                renderer_pixels=renderer_pixels,
                dynamic=dynamic,
            )
        )

    def resume_after_page():
        nonlocal surface, line, pending_page
        if pending_page:
            surface += 1
            line = 0
            pending_page = False

    def add_unit(source_offset, composer, renderer, dynamic):
        nonlocal units, checkpoint, line, line_start, unrecoverable
        units.append((source_offset, composer, renderer, dynamic))
        composer_pixels, _renderer_pixels, _dynamic = totals()
        if composer_pixels < COMPOSER_WRAP_AT:
            return
        if checkpoint is None or unrecoverable:
            unrecoverable = True
            return
        checkpoint_offset, checkpoint_index = checkpoint
        prefix = units[:checkpoint_index]
        remainder = units[checkpoint_index:]
        units = prefix
        finish(checkpoint_offset)
        soft_wraps.append((surface, line, checkpoint_offset))
        line += 1
        line_start = checkpoint_offset + 1
        units = remainder
        checkpoint = None
        composer_pixels, _renderer_pixels, _dynamic = totals()
        unrecoverable = composer_pixels >= COMPOSER_WRAP_AT

    for token in codec.parse_source(data):
        if token.kind in ("glyph", "kanji"):
            resume_after_page()
            after_boundary = False
            add_unit(
                offset,
                composer_advance(rom, token.raw),
                renderer_advance(rom, token.raw),
                False,
            )
        elif token.kind == "source_control":
            resume_after_page()
            after_boundary = False
            dynamic_offsets.append(offset)
            expansion = dynamic_expansion(
                rom, token, offset, runtime_contract, record_id=record_id
            )
            expansions.append(expansion)
            if expansion.bounded:
                bounded_dynamic_offsets.append(offset)
                add_unit(
                    offset,
                    expansion.composer_pixels,
                    expansion.renderer_pixels,
                    True,
                )
            else:
                unresolved_dynamic_offsets.append(offset)
                add_unit(offset, 0, 0, True)
        elif token.code == 0xF7:
            resume_after_page()
            after_boundary = False
            add_unit(offset, 0, token.args[0], False)
        elif token.code == 0xF3:
            resume_after_page()
            after_boundary = False
            composer_pixels, _renderer_pixels, _dynamic = totals()
            checkpoint = (
                (offset, len(units))
                if not unrecoverable and composer_pixels < COMPOSER_WRAP_AT
                else None
            )
        elif token.code == 0xFD:
            after_boundary = False
            finish(offset)
            if pending_page:
                surface += 1
                line = 0
                pending_page = False
            else:
                line += 1
            line_start = offset + len(token.raw)
            units = []
            checkpoint = None
            unrecoverable = False
        elif token.code == 0xFB:
            pending_page = True
            after_boundary = False
        elif token.code == 0xFC:
            if not after_boundary:
                finish(offset)
            surface += 1
            after_boundary = True
            line = 0
            line_start = offset + len(token.raw)
            units = []
            checkpoint = None
            unrecoverable = False
            pending_page = False
        offset += len(token.raw)
    if line_start < len(data) or not lines:
        finish(len(data))
    return SourceLayout(
        mode=mode,
        lines=tuple(lines),
        dynamic_offsets=tuple(dynamic_offsets),
        bounded_dynamic_offsets=tuple(bounded_dynamic_offsets),
        unresolved_dynamic_offsets=tuple(unresolved_dynamic_offsets),
        dynamic_expansions=tuple(expansions),
        soft_wraps=tuple(soft_wraps),
    )


def corpus_summary(rom):
    """Return stable geometry facts for every pointer-referenced source record."""
    result = extract.extract(rom)
    explicit_histogram = {}
    soft_wrap_markers = 0
    dynamic_records = 0
    determinate_lines = 0
    composer_overflow_lines = 0
    renderer_overflow_lines = 0
    max_composer_pixels = 0
    max_renderer_pixels = 0
    max_explicit_lines = 0
    for record in result["records"]:
        measured = source_layout(rom, record.raw)
        if measured.dynamic_offsets:
            dynamic_records += 1
        for line_item in measured.lines:
            if not line_item.dynamic:
                determinate_lines += 1
                max_composer_pixels = max(max_composer_pixels, line_item.composer_pixels)
                max_renderer_pixels = max(max_renderer_pixels, line_item.renderer_pixels)
                composer_overflow_lines += line_item.composer_pixels >= COMPOSER_WRAP_AT
                renderer_overflow_lines += line_item.renderer_pixels > CANVAS_WIDTH_PIXELS
        by_surface = {}
        for line_item in measured.lines:
            by_surface[line_item.surface] = max(
                by_surface.get(line_item.surface, 0), line_item.line + 1
            )
        record_max = max(by_surface.values(), default=1)
        max_explicit_lines = max(max_explicit_lines, record_max)
        explicit_histogram[record_max] = explicit_histogram.get(record_max, 0) + 1
        soft_wrap_markers += sum(token.code == 0xF3
                                 for token in codec.parse_source(record.raw))
    return {
        "records": len(result["records"]),
        "soft_wrap_markers": soft_wrap_markers,
        "dynamic_records": dynamic_records,
        "determinate_lines": determinate_lines,
        "composer_overflow_lines": composer_overflow_lines,
        "renderer_overflow_lines": renderer_overflow_lines,
        "max_composer_pixels": max_composer_pixels,
        "max_renderer_pixels": max_renderer_pixels,
        "max_explicit_lines": max_explicit_lines,
        "explicit_line_histogram": {
            str(key): explicit_histogram[key] for key in sorted(explicit_histogram)
        },
    }


def validate_overrides(rom, record_overrides, runtime_contract=None):
    """Fail closed on statically provable horizontal overflow in translations.

    Surface-specific line counts are intentionally not guessed here; the caller
    inventory still decides whether a record is dialogue, a full-screen page or
    positioned UI text.  Horizontal geometry is shared, so it is already safe
    to enforce.  F4 integer and F5 player-name maxima contribute conservative
    widths. F6 record/cached strings must have a consumer-specific translated-
    domain bound; an unresolved substitution fails instead of allowing a
    partially measured line into a build.
    """
    checked = dynamic = 0
    max_composer = max_renderer = 0
    runtime_contract = runtime_contract or english_runtime_width_contract()
    for key, raw in sorted(record_overrides.items()):
        measured = source_layout(
            rom,
            raw,
            runtime_contract=runtime_contract,
            record_id=extract.location(*key),
            simulate_soft_wrap=True,
        )
        checked += 1
        dynamic += bool(measured.dynamic_offsets)
        if measured.unresolved_dynamic_offsets:
            raise LayoutError(
                "%s has %d runtime substitution(s) without translated width bounds"
                % (extract.location(*key), len(measured.unresolved_dynamic_offsets))
            )
        for line_item in measured.lines:
            max_composer = max(max_composer, line_item.composer_pixels)
            max_renderer = max(max_renderer, line_item.renderer_pixels)
            problems = []
            if line_item.composer_pixels >= COMPOSER_WRAP_AT:
                problems.append(
                    "composer %dpx reaches its %dpx wrap threshold"
                    % (line_item.composer_pixels, COMPOSER_WRAP_AT)
                )
            if line_item.renderer_pixels > CANVAS_WIDTH_PIXELS:
                problems.append(
                    "renderer %dpx exceeds its %dpx canvas"
                    % (line_item.renderer_pixels, CANVAS_WIDTH_PIXELS)
                )
            if problems:
                raise LayoutError(
                    "%s surface %d line %d: %s"
                    % (
                        extract.location(*key),
                        line_item.surface + 1,
                        line_item.line + 1,
                        "; ".join(problems),
                    )
                )
    return {
        "checked_records": checked,
        "dynamic_records": dynamic,
        "max_composer_pixels": max_composer,
        "max_renderer_pixels": max_renderer,
    }


def validate_positioned_overrides(rom, record_overrides, contracts):
    """Validate translated records whose callers provide a nonzero x origin.

    The ordinary source composer only knows about the full 144-pixel canvas.
    Direct-rendered records can begin further right, so their actual budget is
    smaller. ``contracts`` maps stable ``(bank, address)`` keys to
    ``(start_x, start_y, right_edge)`` tuples established by caller tracing.
    """
    checked = 0
    widest = 0
    for key, geometry in sorted(contracts.items()):
        raw = record_overrides.get(key)
        if raw is None:
            continue
        start_x, start_y, right_edge = geometry
        controls = [
            token for token in codec.parse_source(raw)
            if token.kind not in ("glyph", "kanji")
        ]
        if controls:
            raise LayoutError(
                "%s: positioned text contains source control %02X"
                % (extract.location(*key), controls[0].code)
            )
        try:
            measured = validate_direct_surface(
                rom,
                raw,
                start_x=start_x,
                start_y=start_y,
                right_edge=right_edge,
            )
        except LayoutError as exc:
            raise LayoutError("%s: %s" % (extract.location(*key), exc)) from exc
        checked += 1
        widest = max(widest, measured.rightmost_pen - start_x)
    return {
        "checked_records": checked,
        "widest_renderer_pixels": widest,
    }


def validate_right_aligned_positioned_overrides(rom, record_overrides, contracts):
    """Validate translated records drawn against a fixed right-alignment anchor.

    ``contracts`` maps stable record keys to ``(left_edge, anchor_x, start_y)``.
    The direct renderer first measures the complete record, subtracts that width
    from ``anchor_x``, and must not cross the exclusive left obstruction.
    """
    checked = 0
    widest = 0
    minimum_clearance = None
    for key, geometry in sorted(contracts.items()):
        raw = record_overrides.get(key)
        if raw is None:
            continue
        left_edge, anchor_x, start_y = geometry
        controls = [
            token for token in codec.parse_source(raw)
            if token.kind not in ("glyph", "kanji")
        ]
        if controls:
            raise LayoutError(
                "%s: right-aligned text contains source control %02X"
                % (extract.location(*key), controls[0].code)
            )
        try:
            measured = validate_direct_right_aligned_surface(
                rom,
                raw,
                left_edge=left_edge,
                anchor_x=anchor_x,
                start_y=start_y,
            )
        except LayoutError as exc:
            raise LayoutError("%s: %s" % (extract.location(*key), exc)) from exc
        width = measured.rightmost_pen - measured.start_x
        clearance = measured.start_x - left_edge
        checked += 1
        widest = max(widest, width)
        minimum_clearance = (
            clearance
            if minimum_clearance is None
            else min(minimum_clearance, clearance)
        )
    return {
        "checked_records": checked,
        "widest_renderer_pixels": widest,
        "minimum_clearance_pixels": minimum_clearance,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="original or translated Shiren GB2 ROM")
    parser.add_argument(
        "--source", help="measure one English-style source string instead of the corpus"
    )
    parser.add_argument("--mode", type=lambda value: int(value, 0), default=0x02)
    args = parser.parse_args(argv)
    rom = Path(args.rom).read_bytes()
    if args.source is None:
        print(json.dumps(corpus_summary(rom), indent=2, sort_keys=True))
        return 0
    try:
        import english
        import english_font
        approved = english_font.load_approved()
        width_base = font.banked_offset(font.WIDTH_BANK, font.WIDTH_ADDRESS)
        installed = all(
            rom[width_base + code] == approved.advances[character]
            for character, code in english.ENGLISH_CODES.items()
        )
        if not installed:
            rom = english_font.install(rom, approved)
        data = english.encode_source(args.source)
        measured = source_layout(
            rom,
            data,
            mode=args.mode,
            runtime_contract=english_runtime_width_contract(),
        )
    except (ValueError, codec.ParseError, english_font.FontError) as exc:
        parser.exit(1, "error: %s\n" % exc)
    print(json.dumps({
        "mode": measured.mode,
        "safe": measured.safe,
        "dynamic_offsets": measured.dynamic_offsets,
        "bounded_dynamic_offsets": measured.bounded_dynamic_offsets,
        "unresolved_dynamic_offsets": measured.unresolved_dynamic_offsets,
        "dynamic_expansions": [item.__dict__ for item in measured.dynamic_expansions],
        "composer_overflows": [line.__dict__ for line in measured.composer_overflows],
        "renderer_overflows": [line.__dict__ for line in measured.renderer_overflows],
        "line_limit_overflows": measured.line_limit_overflows,
        "lines": [line.__dict__ for line in measured.lines],
    }, indent=2))
    return 0 if measured.safe else 1


if __name__ == "__main__":
    sys.exit(main())
