# Graphics Artifact Bug Audit

## Status and scope

This audit began as a read-only snapshot on 2026-09-06. The follow-up repair on the same
date fixes the reproduced defects, freezes their generated machine-code contracts, and
adds live regressions. The review followed the reported symptoms through the dungeon popup,
service-menu, dialogue-frame, and proportional-font paths, then compared the suspicious
machine code with a fresh `mgbdis --print-hex` disassembly of the Japanese ROM.

Three defects were confirmed and are now fixed:

1. the added stairs-popup column was saved and restored with linear VRAM addresses instead
   of 32x32 BG-map wrapping;
2. the shadowed `Withdraw` raster wrote four gray pixels into the dynamic tile later shown
   as the unselected `Quit` cursor cell in Warehouse and Bank menus; and
3. the shadowed `Exchange` item-action raster wrote three gray pixels into cursor-only
   tiles that the compact action-window map exposes on lower blank rows.

The reported dialogue-border and missing-glyph-row symptoms have not been reproduced as stable
defects. The relevant native renderers are byte-identical to the Japanese ROM and the
current static layout audits are clean, but the live tests do not yet cover the complete
border lifecycle or every glyph at every tile phase. Those are actionable coverage gaps,
not proof that the reports are invalid.

## Baseline and method

- Japanese ROM SHA-1: `5264f6d0c4f12c9144de1d12fddadbadd82b3e33`.
- Pre-repair shadowed English build SHA-1: `49df090f7b1de0e6a448f096f99c093756a55b65`.
- Pre-repair classic English build SHA-1: `1b148e487b988ea94614cc8c59a18002427ff636`.
- Earlier repaired shadowed build (before GFX-06) SHA-1: `e38b010a93401fe203e9b091854706c78c567974`.
- Earlier repaired classic build (before GFX-06) SHA-1: `9463146f296472364ab18199100d8057bfea87ef`.
- Current repaired shadowed English build SHA-1: `8a8f8e3e2ba88748e453ab0c7959d154b6a2dbe7`.
- Current repaired classic English build SHA-1: `f543abf33ea0016c503c252686cefd0590ce9f43`.
- Japanese disassembly: `build/mgbdis/`.
- Fresh shadowed-build disassembly: `build/mgbdis-graphics-audit/`.
- Disassembler: `../mgbdis/mgbdis.py`, with `--print-hex`.

The source/English comparison found these graphics primitives unchanged:

| Routine | Range | Japanese SHA-1 | Fresh English result |
|---|---|---|---|
| BG tilemap/attribute copier | `0:$0AEA-$0B5F` | `330fcbbda1ba5d22c7deb94c9591c1dfb645ecc3` | byte-identical |
| Native VWF compositor | `0:$3922-$39E2` | `5f592102f709521dbc692378870645c058ce1e84` | byte-identical |
| Direct text renderer entry | `3:$5E62-$5EAA` | `877c9a68a2ffd94b8f98472d38becb0157922c74` | byte-identical |
| Width/glyph dispatch core | `3:$6DD3-$7020` | `2dc6c52dc96a1af22021f52ee2d0218975753257` | byte-identical |

The expected differences are font/table data and the guarded hooks installed by the
localization. In particular, the Japanese floor-popup constructor at `3:$6A65-$6A9F`
still calculates the BG destination from `SCY`/`SCX`; only its load/copy tail is redirected
for the wider English template.

## Confirmed defects and repairs

### GFX-01: fixed — stairs underlay helper did not wrap either BG-map axis

Severity: **high**. This is a direct cause of camera-dependent stray dungeon tiles after a
stairs prompt closes.

The Japanese constructor at `3:$6A65-$6A84` derives an even tile coordinate in the complete
`0..30` range for each axis:

- `SCY` high nibble, plus one, masked to four bits, multiplied by `$40`;
- `SCX` high nibble, plus one, masked to four bits, doubled; and
- base address `$9800`.

It then calls the native copier at `0:$0AEA`. The Japanese `mgbdis` output shows that copier
handling the tilemap as a ring:

- `0:$0B2A-$0B3C` checks `E & $1F` and wraps a column crossing within the same row;
- `0:$0B45-$0B4C` maps `$9Cxx` back to `$98xx`; and
- `0:$0B4E-$0B52` maps `$A0xx` back to `$9Cxx` for the second BG map.

Before this repair, the localization's separate underlay routines did not preserve those
rules. In
[`tools/stairs_menu.py`](../tools/stairs_menu.py), `_floor_save_bytes()` uses `HL = DE + 7`
and `_floor_restore_bytes()` reconstructs `DE = saved_destination + 7`. Their row loops rely
on the one-byte copy increment followed by `+ $1F`, giving a linear `+ $20`. Neither path
masks the low five x bits, and neither maps `$9Cxx` back to `$98xx`.

Both failures are reachable:

- A popup starting at x=26, 28, or 30 crosses the x=31 boundary when the eighth column is
  added.
- A five-row popup starting at y=28 or 30 crosses the y=31 boundary.

Deterministic PyBoy probes on the fresh shadowed build forced constructor inputs that the
native formula can produce and sampled both VRAM banks at the instant the restore helper
returned:

| Probe | Popup top-left | Correct added-column cell | Result after B dismissal |
|---|---:|---:|---|
| Horizontal wrap only (`SCX=$D0`, `SCY=$50`) | `$999C` | `$9983` | original `41/81` replaced by stale top-right frame `7E/AF` |
| Vertical wrap only (`SCX=$30`, `SCY=$D0`) | `$9B88` | `$980F` | original `41/81` replaced by stale bottom-right frame `7E/EF` |
| Both axes (`SCX=$D0`, `SCY=$D0`) | `$9B9C` | `$9B83`, `$9803` | both top-right `7E/AF` and bottom-right `7E/EF` remain |

The pre-repair live regression in
[`tests/test_stairs_menu.py`](../tests/test_stairs_menu.py) samples only the fixed safe
destination `$9988`. Its `tilemap_cells()` helper also calculates
`top_left + row * 32 + column` linearly, so adding an edge fixture without first making that
test helper ring-aware would encode the same mistake.

Repair implemented:

1. `_floor_save_bytes()` now preserves the BG row bits, computes `(x + 7) & $1F`, and
   stores that actual wrapped destination.
2. `_floor_restore_bytes()` consumes the stored destination directly instead of adding
   seven a second time.
3. Both loops apply `$9C->$98` and `$A0->$9C` after each row step, matching the Japanese
   copier's two-map ring semantics.
4. The live stairs test now uses a ring-aware tilemap reader and covers horizontal-only,
   vertical-only, and combined edges through both B cancellation and `Stay`. It records
   tile IDs and attributes at the save entry, while the frame is open, and at the restore
   return before later dungeon streaming can legitimately redraw those cells.

### GFX-02: fixed — shadowed `Withdraw` contaminated the unselected `Quit` cursor tile

Severity: **medium**. This exactly reproduces the thin vertical line to the left of `Quit`
in the Warehouse and Bank Teller menus.

The Japanese popup template at `3:$6AB3` exposes five dynamic tiles per physical row. The
English service template exposes six dynamic tiles plus a stable seventh spill tile. The
native renderer still writes sequential dynamic tiles, so a write to `row_base + 6` aliases
the first tile of a later physical row. That alias was already recognized and handled for
`Password` and `Synthesis`, but not for `Withdraw` in the standard Warehouse/Bank path.

With the shadowed font:

- `Withdraw` has a 41-pixel advance;
- text begins after the 8-pixel cursor cell;
- its last gray shadow pixel is therefore at frame x=48, the first pixel of the seventh
  dynamic cell; and
- for the affected physical row, `base $B4 + 6 = $BA`.

Tile `$BA` is later mapped as the `Quit` cursor cell. The visible right spill uses stable
blank tile `$B3`, so the shadow column is clipped from `Withdraw` but survives in `$BA` and
appears beside unselected `Quit`. A live VRAM capture found this bank-0 tile raster while
`Quit` was unselected:

```text
11111111
11111111
21111111
21111111
21111111
21111111
11111111
11111111
```

`1` is the popup background and `2` is the gray shadow color. At screen coordinates x=16,
y=66..69, the shadowed Warehouse and Bank captures contain four `(168,168,168)` pixels.
The same cursor cell is entirely background in the Japanese ROM and fresh classic build.
Selecting `Quit` overwrites `$BA` with the normal arrow, explaining why the artifact is
state-dependent.

The pre-repair gap in [`tests/test_service_menus.py`](../tests/test_service_menus.py) was
specific:
`_exercise_lifecycle()` saves every cursor-position framebuffer but only requires enough
distinct screens. It does not require unselected cursor cells to be blank. The completed-
rescue route has an exact one-cursor assertion, and Blacksmith has a focused blank-cell
assertion, but Warehouse and Bank do not.

Repair implemented:

1. The copy dispatcher now recognizes only the exact Warehouse and Bank record sets before
   calling `_standard_tile_support_bytes()`.
2. That helper selects the renderer's active VRAM bank and copies reviewed blank tile `$B3`
   over aliased cursor tile `$BA` before the frame reaches the BG map. Rescue is excluded
   because its shorter Password menu legitimately exposes `$BA` outside its live cursor rows.
3. The final one-pixel gray shadow column remains intentionally clipped. Preserving it would
   require a separately owned, staged tile; sharing a nonblank seventh tile would repeat the
   fragment on every content row. All black `Withdraw` pixels remain visible.
4. A live regression visits all four selector positions in both Warehouse and Bank with
   both classic and shadowed builds. It requires exactly one nonblank cursor cell and exact
   background pixels in the other three cells at every stop.

## Unconfirmed reports and test gaps

### GFX-03: intermittent missing dialogue-border tiles

No current static defect was found in the ordinary dialogue frame path:

- the Japanese and English BG copier is byte-identical;
- the Japanese and English VWF code is byte-identical;
- the production layout validator accepted all 5,679 translated records in the fresh
  build, including bounded runtime substitutions; and
- `dialogue_page_marker_audit.py` currently reports zero detached markers and zero
  third-line marker overflows.

The previous marker failure is visually relevant: an overflowing nine-pixel page marker can
leave triangles in window corners and resemble a damaged frame. The current catalogue no
longer contains those endpoints. Graphical-input bottom borders are a separate, already
repaired path; `tests.test_graphical_input_borders` verifies the complete 20-tile bottom row
for modes 0-8.

There is still no focused live test that records every ordinary dialogue border tile and
attribute through initial draw, each `<page>` wait, `<box>` reset, and close. Existing live
dialogue tests prove the selected record and text raster, not the full frame lifecycle. A
future reproduction should record the ROM build/font variant, save state, exact page, screen
coordinate, and whether the bad tile persists for two consecutive settled frames. The
regression should inspect both VRAM banks rather than accepting only a framebuffer hash.

### GFX-04: intermittent missing horizontal glyph rows

No corrupt installed glyph or changed renderer was found:

- all 79 English glyphs and advances are hash-frozen and decoded pixel-for-pixel from the
  installed ROM;
- the Japanese/English compositor and glyph-dispatch spans in the table above are identical;
  and
- the live native-renderer smoke test checks every raster row of `Hello, Shiren!` and
  `Native VWF works.` in the shadowed font.

That smoke test covers only those strings and their naturally occurring pen positions. It
does not exercise all 79 glyphs at every x phase (`pen & 7`), the classic variant through
the live compositor, page transitions, or two consecutive settled frames. An exhaustive
phase matrix is the correct next diagnostic. It should compare the live color-index raster
with the approved glyph source and separately capture any transient partial draw; without a
specific failing record or state, changing the native renderer would be speculative.

## Additional audit issue

### GFX-05: fixed — the documented stairs width was stale

Before this repair, [`docs/VWF_BUDGETS.md`](VWF_BUDGETS.md) said the stairs labels ran from
x=8 to x=64 with 56 pixels available and that both floor and Status routes used widened
geometry. Current
[`tools/stairs_menu.py`](../tools/stairs_menu.py) intentionally uses six interior columns:
x=8 to x=48, 40 label pixels, and leaves the separate Status constructor byte-exact. The
tests and build-time positioned contract use the code value, so this was not the source of a
runtime artifact. [`docs/VWF_BUDGETS.md`](VWF_BUDGETS.md) now records the implemented floor
and Status geometry.

### GFX-06: fixed — item-action logical slots hid cursor-tile aliases

Severity: **medium**. This exactly reproduces the thin gray line below `Info` in the
supplied `stray-item-menu-tile.mss` floor-item popup.

The native action renderer uses an 18-tile-wide canvas and places up to eight commands at
x=`8,56,104`. Those coordinates are 48 pixels apart, but the compact Window tilemap maps
only a cursor cell followed by five label tiles for each row. The sixth nominal label tile
is therefore the next logical column's cursor cell. The prior action audit checked only the
48-pixel pen stride and called all 24 labels safe; it did not model that tilemap remap or
the separate black/shadow raster extents.

In the shadowed font, `Exchange` advances 41 pixels. Its black raster ends inside the 40
visible pixels, but its final gray column lands at canvas x=48. At y=43 that contaminates
VRAM-bank-1 tiles `$60` and `$72` with exactly these bytes:

```text
$60  00000000000000000000000000000080
$72  00800000008000000000000000000000
```

The action tilemap reuses those tiles as lower cursor cells, producing the three gray
pixels at screen x=104. `Take Out` has the same class of overflow with one gray pixel.

Repair implemented:

1. `menu_graphics.py` redirects the guarded bank-17 `$6F04-$6F15` action upload tail
   through a 57-byte bank-255 helper.
2. After rendering and before the unchanged `$D240-$D7DF` to `$9240-$97DF` copy, the
   helper clears cursor-only canvas columns 6 and 12 for tile rows 2-6: `$2A,$3C,$4E,$60,
   $72` and `$30,$42,$54,$66,$78`.
3. The build now separately rejects any item-action black ink that enters those tiles.
   The audit reports the 40-pixel visible label budget, the 48-pixel logical stride, and
   the exact shadow-only exceptions instead of conflating the two.
4. The converted PyBoy fixture first proves that the supplied state contains the exact
   dirty `$60/$72` bytes, then dismisses and reopens the menu through controller input. It
   requires all ten alias tiles and all three reported framebuffer pixels to be blank.

## Verification performed

- Built fresh classic and shadowed ROMs from the matching Japanese source.
- Disassembled the Japanese and fresh shadowed ROMs with `mgbdis --print-hex`.
- Byte-compared the four native rendering spans listed above.
- Ran the detached-page-marker and runtime-width audits; production domains are complete
  and the only permanently unresolved width domain is the existing debug-only polymorphic
  family.
- Ran 137 focused font, layout, surface, input-border, stairs, service-menu, and page-marker
  tests successfully.
- Ran full test discovery after the repairs and fixture refreshes: 611 tests, all passing.
- Ran live edge probes for both stairs axes and exact classic/shadowed/Japanese service-menu
  pixel comparisons.

Follow-up repair verification:

- The stairs live regression passes all three edge placements through both exit routes.
- The service-menu cursor regression passes all four positions for Warehouse and Bank in
  both classic and shadowed builds.
- The supplied floor-item state reproduces exact shadow contamination in action tiles
  `$60/$72`; a real dismiss/reopen passes with all ten cursor aliases and the three
  reported screen pixels blank.
- The revised menu-action audit distinguishes the 48-pixel coordinate stride from the
  40-pixel visible label raster and reports only the two reviewed shadow-only overflows.
- The stale script-extraction output hashes caused by the earlier `F250` kanji correction
  were refreshed so that failure no longer obscures graphics-suite results.
- Full discovery exercised 611 tests, all passing.

## Remaining follow-up order

1. Add the GFX-03 dialogue-border lifecycle fixture before changing dialogue code.
2. Add the GFX-04 exhaustive glyph/phase probe; use a captured failing record to narrow any
   remaining transient defect.
