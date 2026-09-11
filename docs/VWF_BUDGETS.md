# VWF budget register

This is the canonical answer to “does this text fit?” for the Thin Pixel-7 GB2 build.
A single character count is never a sufficient verdict.

Every consumer can impose several independent constraints:

1. **ROM storage** — handled by far-pointer relocation.
2. **Composer width** — the source composer wraps when a prospective glyph reaches 144 px.
3. **Renderer width** — the renderer accepts a final pen at 144 px and rejects a slice that
   would reach 145 px.
4. **Glyph-cell footprint** — the native compositor paints an eight-pixel cell even when a
   glyph's variable advance is narrower; that cell must not cross the consumer's right edge.
5. **Vertical geometry** — line count, starting baseline, and line advance depend on mode.
6. **Runtime values** — names, items, locations, counters, and player input expand after
   the literal template is read.
7. **Caller geometry** — positioned menus may expose only part of the 144 px canvas.

## Core renderer profiles

| Profile | Representative mode | Horizontal contract | Vertical contract | Owner |
|---|---:|---|---|---|
| Dialogue | `$02` | `<144` composer px and `<=144` renderer pen; the bottom line must keep every 8px glyph cell inside x=144; a third-line `<page>` must end at x<=135 | 3 physical lines per `<box>`; y=21; `<br>` +11 | `prose_editor.py`, `wrap_en.py`, `wrap_item_messages.py` |
| Full-screen item detail | `$08` | Same pen limits; fixed-cell acceptance depends on the spill target and final owned row | 11 composer lines; y=1; `<br>` +11 | `wrap_items.py` |
| Stepped combat window | `$10` | Same pen limits, native `<cF3>` rollback, and compositor edge clipping | y=24; break step +16; context controls lifetime; two-line windows are reachable | `combat_messages.py`, `glyph_cell_clip.py` |
| Positioned/direct | `$04` representative | Surface-specific subrange of the 144 px canvas | One row unless the caller proves otherwise | `surfaces.py`, `build.py` |

“143 composer pixels” means the source line must remain strictly below the `$90` wrap
threshold. “144 renderer pixels” means a final pen position at the right edge is legal.
The two totals can differ for wide prefixed glyph slices and for `<hspace>`, which the
renderer applies without adding it to the composer's width counter.

## Glyph-cell edge safety

The VWF advance is not the complete native painted-memory footprint. The renderer positions the
next character with the variable advance in `$C4D5`, but the native compositor at
`0:$3922` receives an eight-pixel cell. On an 18-tile row-major canvas, a cell beginning at
x=137 or later crosses the x=144 boundary and aliases the first tile of the following row.

The raw full-renderer footprint is:

```text
glyph origin + 8 <= 144
```

This must be measured for every glyph, not inferred solely from the final pen. A crossing
is a defect when the aliased cell belongs to a frame, another persistent surface, or memory
the consumer does not subsequently repaint. For example, a final period on the bottom line
of a dialogue box advances two pixels, so it is border-safe only when the period begins no
later than x=136—equivalently, when the final pen is at most 138. Other final glyphs have
different advances but the same eight-pixel compositor footprint. Earlier text-row
crossings remain diagnostics until the consumer's following-row repaint is modeled; they
must not be treated as proof of the bottom-border defect.

This rule was discovered from
[GFX-03](GRAPHICS_ARTIFACT_AUDIT.md#gfx-03-fixed--a-right-edge-glyph-cell-overwrote-the-bottom-frame-row):
Monster Log final periods at x=138 and x=141 overwrite two and five pixels respectively in
the first bottom-border tile. Runtime composition matters: the Monster Notebook stores a
two-line description, but the live surface prepends the monster name and displays the
description on physical lines two and three.

Combat also reaches this defect on physical line **two** in mode `$10`: drinking
Otogirisou or Leaping Grass renders `Made <name>` followed by `into medicine and consumed
it.` The period starts at x=139, y=40 and the native eight-pixel cell erases three columns
of the bottom frame. A three-line dialogue audit cannot certify this variable-lifetime
consumer; `bottom_line_glyph_cell_overflows` has no bounded last row for mode `$10`.

Production now installs `glyph_cell_clip.py`. Its bank-0 compositor gate skips the
secondary tile write when the origin is in the final canvas tile (x>=136), while retaining
the primary tile and the native variable advance. Aligned cells elsewhere still skip the
secondary write; unaligned cells inside the canvas still paint both tiles. This protects
every row using this compositor without adding a line break or changing message text.
Raw fixed-cell diagnostics and conservative authoring checks remain useful: clipping does
not excuse text ink, a pen, a page marker, or vertical content that actually exceeds its
surface's budget.

The production build checks fixed glyph cells on the final physical row of known
full-renderer surfaces as well as their pen widths. Dialogue uses three rows; item detail
and Help retain their eleven-row profile. Streamed combat retains its own lifetime and
receives the runtime edge protection above; absence of a bounded-row diagnostic is not
evidence that its unpatched border was safe.
Composed Monster Notebook descriptions still use their separate name-plus-description
check. The page marker has a separate nine-pixel advance rule described below. Satisfying the
glyph-cell rule does not prove that a following marker also fits.

## Dialogue box accounting

The three-line limit is physical, not textual. `<page>` waits but does not reset the line
cursor, so these two fragments do not have the same occupancy:

```text
Line 1<br>Line 2<page><br>Line 3
Line 1<br>Line 2<page><box>Line 1 in a new box
```

The first consumes three cumulative lines in one box. The second waits, resets the box,
and begins again. If English needs a fourth cumulative line, add `<page><box>` and repeat
the visible speaker label where appropriate.

`wrap_en.py` uses the fewest safe lines and balances word spaces, but it never invents a
reader-controlled page/box decision. The editor owns pacing.

Both explicit and soft-wrap layout analysis keep the physical surface and row across
`<page>`, including a wait in the middle of a row. Only `<box>` resets them; splitting a
message into reader-controlled waits cannot hide a bottom-row glyph-cell spill.

The blinking page marker is a native nine-pixel glyph. On the third line, a text pen at
x=136 or later makes that marker reach the renderer's 145-pixel wrap threshold. It then
descends below the dialogue canvas and can leave stale triangles in all four window
corners. The build therefore reserves nine pixels at every third-line `<page>` and rejects
those endpoints while retaining native earlier-line marker wraps inside the canvas.

## Positioned surfaces

The build has explicit contracts for known direct-rendered rows:

| Surface | Start/right edge | Available width | Notes |
|---|---:|---:|---|
| Synthesis-rune description | x=3 to 144 | 141 px | One direct row |
| Item-action command | x=8 to 48 visible; x=56 logical stride | 40 px visible | Black ink must fit the five mapped label tiles. `Take Out` and `Exchange` advance 41 px only because one gray shadow column enters the next cursor-only tile; `menu_graphics.py` clears both alias columns before upload |
| Equipment comparison | x=104 to 144; y=20 | 40 px | Current and proposed unsigned-byte values (0..255), separated by the native eight-pixel arrow, need at most 38 px. x=96..103 belongs to the cursor cleanup; rendering there erases leading digits |
| Status condition body | x=1 to 144 | 143 px | Heading fields have separate contracts |
| Diary/front-end hub | x=6 to 80 | 74 px | Conditional rows |
| Start Adventure submenu | x=56 to 144 | 88 px | Up to eight enabled rows |
| Dungeon stairs popup labels | x=8 to 48 | 40 px | Floor route adds one interior tile; Status keeps its native eight-column frame |
| Debug main menu | x=8 to 56 | 48 px | Separate 9×7 frame; three static 8 px text rows at 16 px pitch; 17/48 native text/cursor tiles. Installed by `debug_menus.py` |
| Debug item categories | x=8 to 88 | 80 px | Separate 13×11 frame; five static 8 px text rows at 16 px pitch; 40/48 native text/cursor tiles. Installed by `debug_menus.py`; see [DEBUG-ROOM.md](DEBUG-ROOM.md#isolated-debug-menu-prototype) |
| Debug Weapons/Shields | x=8 to 48 | 40 px | Separate 8×9 frame; four static 8 px text rows at 16 px pitch; 14/48 native text/cursor tiles. Uses the shared private debug scratch and native popup tiles |
| Debug Bracelets/Grass | x=8 to 64 | 56 px | Separate 10×7 frame; three static 8 px text rows at 16 px pitch; 12/48 native text/cursor tiles in classic, 14/48 in shadowed. Uses the shared private debug scratch and native popup tiles |
| Debug Scrolls/Staves | x=8 to 48 | 40 px | Separate 8×9 frame; four static 8 px text rows at 16 px pitch; widest label 38 px; 15/48 native text/cursor tiles in both fonts. Uses the shared private debug scratch and native popup tiles |
| Debug Pots/Arrows | x=8 to 40 | 32 px | Separate 7×5 frame; two static 8 px text rows at 16 px pitch; widest label 27 px; 8/48 native text/cursor tiles in both fonts. Uses the shared private debug scratch and native popup tiles |
| Debug Meat page 1 | x=8 to 72 | 64 px | Separate 11×11 frame; five static 8 px text rows at 16 px pitch; widest label 57 px; 23/48 classic and 24/48 shadowed text/cursor tiles. Counts and numbered batches are private artwork; uses the shared private debug scratch and native popup tiles |
| Debug Meat page 2 | x=8 to 72 | 64 px | Separate 11×11 frame; five static 8 px text rows at 16 px pitch; widest label 57 px; 23/48 classic and 24/48 shadowed text/cursor tiles. Counts and numbered batches are private artwork; uses the shared private debug scratch and native popup tiles |
| Debug Meat page 3 | x=8 to 72 | 64 px | Separate 11×11 frame; five static 8 px text rows at 16 px pitch; widest label 62 px; 25/48 classic and 26/48 shadowed text/cursor tiles. Counts and numbered batches are private artwork; uses the shared private debug scratch and native popup tiles |
| Debug Set Flag | x=8 to 88 | 80 px | Separate 13×9 frame; four static 8 px text rows at 16 px pitch; Enable Zenmaiger uses exactly 80 px, verified against the complete glyph raster; 30/48 text/cursor tiles in both fonts. Private action labels retain native progression scripts and result messages; no additional WRAM or VRAM |
| Main-menu left slots | caller-specific | 50 px typical | Exact slot domains live in `build.py`/`surfaces.py` |
| Main-menu location | right-aligned to x=142 | 83 px from x=59 | Uses the native alignment wrapper |

The status-menu graphical overlay has its own measured label coordinates. Two suffixes
intentionally end exactly at x=144: `%` and `G`. Their exact edge fit is accepted and
fixture-tested.

`surfaces.py` assigns all 120 discovered direct-renderer call sites to known owners. The
positioned audit validates 143 records statically and validates the remaining dynamic row
against its runtime domain.

## Runtime domains

`runtime_widths.py` refuses a bound until every member of the relevant translated family
is explicit. Current maxima are:

| Domain | Maximum |
|---|---:|
| Actor/monster names | 95 px |
| Trap names | 87 px |
| Item names, including prefixed canonical recalls | 107 px |
| Locations | 80 px |
| Seven-byte custom item-name slot | 49 px |

The warning audit for combat templates enumerates actual translated values rather than
substituting one universal worst-case string. A short value may remain on one line while a
long value activates `<cF3>` at the authored word boundary.

The player editor itself is capped at six visible characters. A separate conservative
49-pixel F5 reservation remains in the runtime analyzer for legacy producer shapes; it is
not the name-entry limit.

## Family-specific rules

### Story and ordinary dialogue

- Maximum three cumulative physical lines per `<box>`.
- Keep every third-line ordinary glyph's eight-pixel compositor cell inside x=144; a glyph
  must begin at x=136 or earlier. Report earlier-line crossings separately until the
  following-row repaint is modeled.
- End third-line `<page>` text at x=135 or earlier so the nine-pixel marker cannot wrap.
- Keep source pages, boxes, delays, and effect controls in order.
- Use `<page><box>` when a new readable surface is required.
- Allow the measured wrapper to generate normal `<br>` placement from spaces.

### Dungeon item/action messages

- Preserve every source `<cF3>`; all 57 source-bearing rows retain at least one.
- Additional `<cF3>` markers may be added at safe English word boundaries.
- Validate against actual item, actor, trap, and player-name domains before applying.

### Combat/gameplay messages

- Indices 0-109 use the live-proven stepped mode `$10` policy.
- Indices 110-200 include shop, companion, behavior, and scripted families with their own
  modes; do not apply one combat-window assumption to all 201 rows.
- Run `combat_messages.py --warnings-json` after a template or glossary change.

### Item descriptions

- Mode `$08`, 144 px, 11 composer lines; measure fixed-cell crossings on every line and
  reject any crossing whose target is not owned and repainted by this surface.
- Title/stat headers are preserved.
- The wrapper may change only body spaces and `<br>` boundaries; visible wording must
  remain identical.
- Storage expansion is handled by relocation, never by shortening the description.

### Menus and graphical input

- Measure the actual interior, not the overall box width or screen width.
- A cursor or page marker may occupy cells outside the text payload.
- Mode 3 Big Moai promotional gift-code input has a four-byte buffer; mode 4 player input has six visible
  characters; mode 1 Blank Scroll input has a separately guarded 11-character maximum and
  history-filtered matcher.
- Mode 0 unidentified-item free labels remain seven characters. A `FILL IN` canonical
  recall—or its native **Start** shortcut—uses a separate 14-cell presentation field because
  its native slot stores a root
  token and the ordinary item-name renderer expands the complete translated root. Those
  14 cells render from the original seven-cell horizontal origin instead of shifting left. Every
  active group-12 root is build-validated against that 14-cell limit.

Runtime item-message bounds include every enabled canonical root with its actual category
prefix, in addition to identified names, appearances, and seven-character free labels.
The current maximum is `Bracelet: Far-throwing` at 107 pixels. Canonical recall is a token
expansion, so the seven-byte free-label bound cannot stand in for that domain. The
`Pushed <name>.` message has a native soft-wrap checkpoint before the name.

## Acceptance policy

Accept an exact pen-edge fit only when the compositor footprint is also owned or clipped;
pen width alone is not proof that the backing tiles are safe. Do not add speculative
padding by shortening established terminology. Conversely, do not extend a budget from
one surface to another because both happen to use the same font.

After any font-metric change, invalidate every stored width assumption and rerun the full
layout, runtime-domain, menu, build, and emulator test matrix.
