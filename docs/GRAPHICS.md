# Graphics localization

All known graphics localization items are implemented, including the approved English
title. This document records the installed graphics, artwork workflow, and automated
visual coverage.

The first whole-ROM graphical-text inventory is now recorded in
[GRAPHICS_AUDIT.md](GRAPHICS_AUDIT.md). It traces the clean-boot copyright/composer card,
main title, all 32 town/dungeon/floor arrival selectors, the dedicated dungeon-HUD font,
and the save/load wait sign. The main-ending staff roll has a PyBoy fixture, a complete
title-plus-20-card native/English audition, and guarded production insertion. The approved
English title, copyright/composer card, main-ending staff cards, arrival cards, HUD, and wait
sign are installed. Additional automated visual coverage needs a true-ending save state and a
live capture of the wait-sign route.

## Proven storage model

GB2 graphics are uncompressed. A clean PyBoy title-screen capture found 261 of 270 nonblank
VRAM tiles verbatim in the ROM. The dense high-entropy banks seen during early triage are
ordinary art, not a compressed stream, so no general decompressor is needed before editing
graphical Japanese.

This does not mean every visible screen is one stored bitmap. A route may combine raw tile
planes, a tilemap, attributes, palette selection, numbers, and text drawn by the native VWF.
Map each asset's producer and consumers before changing its graphics.

## Already localized or engineered

| Area | State | Owner |
|---|---|---|
| Opening title | Complete approved English artwork, native moon and bat cycles, raised moon-side bat, sky gradient, castle, horizon gap, sand, and all eight slower subtitle sparkle phases; exact live pixels and native menu/attract transitions verified | `title_screen.py`, `title_graphics.py`, `title_screen_runtime.py` |
| In-game proportional font | Selectable Thin Pixel-7 classic black-only or reviewed palette-color-2 `+1,+1` shadowed style in all 79 native one-byte English slots, including the straight ASCII double quote at `$59`; both retain identical color-3 ink and advances | `english_font.py` |
| Core Status template labels | English bitmap overlay generated from the selected font style; shared native graphics remain unchanged | `menu_graphics.py` |
| Item-action cursor cells | Post-render cleanup of the two cursor-only canvas columns prevents clipped `Take Out` / `Exchange` shadow pixels from aliasing into lower blank rows; black label rasters remain complete | `menu_graphics.py` |
| Player-name / Rankings-note keyboard | English A-Z/a-z/0-9 map and shared style-selected glyph atlas, including the private cursor symbols; mode 2 retains its native 13-character note field while a private graph turns fourteen formerly empty slots into spaces and lets right pad a space at the current end | `name6.py` |
| Big Moai promotional gift-code keyboard ("spells") | Approved four-row A-Z/0-9 map, private navigation, below-label `DEL`/`OK` cursors, and its own guarded copy of the selected atlas style | `spell_input.py` |
| Blank Scroll keyboard | English A-Z/a-z/0-9 map, 11-character full-name input, mode-specific hyphen cell, and shared style-selected atlas | `blank_scroll.py` |
| Unidentified-item and Rescue keyboards | English maps over the shared style-selected atlas; dedicated mode-0 `FILL IN` history and full canonical-name display, plus modes 5-8 native password mapping | `unidentified_names.py`, `rescue_presentation.py` |
| Stairs popup geometry | Widened templates and background teardown | `stairs_menu.py` |
| Rescue Team, completed-rescue delivery, warehouse, Bank Teller, and Blacksmith Info popup geometry | Exact-menu seven-interior-tile frames using six renderer-owned dynamic tiles; warehouse and Bank have stable `$B3` spill cells, Blacksmith stages the `Synthesis` suffix in `$B3`, the shorter Rescue menu exposes only off-frame `Password` overflow tiles `$A8/$BA`, and completed-rescue delivery stages those fragments in `$9C/$AE` before clearing their live cursor aliases; active-VRAM-bank bottom border, staged-tile cleanup, and two-bank save/restore of the added ninth BG column | `service_menus.py` |
| Cracked-Bracelet marker | Stock Japanese `(hibi)` composite replaced by compact `(Cr)` at native token `F2 1E` | `item_status.py` |
| Item-row status gallery | Equip, curse, blessing, plate, cracked, synthesis color, and combined states reproduced on demand | `mesen_item_formatting_gallery.lua` |
| Copyright/composer card | Approved Inter SemiBold 4.1 `CHUNSOFT` and `Koichi Sugiyama` strips; native copyright rows, map, palettes, fade, scroll, and title handoff preserved | `credit_screen.py` |
| Main-ending staff roll | The staff-title card (`Shiren the Wanderer GB2` / `Magic Castle of the Desert` / `- Development Staff -`) and all 20 approved Inter SemiBold 4.1 role/name cards replace their exact raw 2bpp source planes; centering scroll values, fades, palettes, timing, and the Japanese `終` mark are preserved. The surrounding map uses tile `$F0`, verified black across the opening and ending planes, so wide headings cannot repeat tile `$80` around the perimeter | `ending_credits.py` |
| Town/dungeon/floor arrival cards | Approved Inter SemiBold 4.1 location artwork for all 32 selectors, including the decoded `Mystery Dungeon` alias; native Latin digits plus an approved one-pixel-raised `F`, centering, floor formatter, underline, palette inheritance, fade, and transition preserved through a guarded bank-$F8 renderer clone | `arrival_cards.py` |
| Dungeon HUD font | Approved player-supplied rasters replace decimal `0-9`, the visible `F`, tightly kerned `Lv`, `H`, and `p` labels, and the slash; `A-E`, meter, and reserved cells remain native; the read-only contact sheet accepts and audits both source and installed atlases | `hud_font.py`, `hud_font_audition.py` |
| Shop-price font audit | All ten native two-tone digits decoded from guarded source `3:$5642-$56E1`, cropped and packed at the observed five-pixel shop-tag advance with captured black/white/gray palette roles; read-only contact sheet writes no ROM changes | `shop_price_font_audition.py` |
| Save/load wait sign | Approved centered, no-shadow Thin Pixel-7 `Please` / `wait...` raster in two guarded sign blocks; native gray billboard shading retained and both interleaved bird-art blocks preserved byte-for-byte | `wait_screen.py` |

The graphical-input family contains nine logical modes but only five visible keyboard-map
variants. Four variants derive from `name6.py`; Big Moai owns the fifth in `spell_input.py`.
Every map preserves the native final row `$28 $2A...$2A $28`, which draws the complete outer
bottom border. `tests.test_graphical_input_borders` checks that invariant for modes 0-8,
while the Rankings-note PyBoy route checks the literal gray and black edge pixels without a
whole-frame hash.

Environmental Japanese shop signs and the main-ending `終` mark are intentionally
preserved under the [graphics scope decisions](GRAPHICS_AUDIT.md#scope-decisions).

## Installed title

The supplied English composition and [animation audition](TITLE_LOCALIZATION_AUDITION.md)
were approved and inserted into both font builds. The [implementation notes](TITLE_LOCALIZATION.md)
describe the palette packing, animation clocks, guarded ROM ownership, transition handling,
and reproducible preview captured from the production ROM. The native resource inventory
remains in [GRAPHICS_AUDIT.md](GRAPHICS_AUDIT.md#title-screen).

## Visual verification coverage

The separate true-ending route needs a captured trace to compare its resource loads with
the installed main-ending artwork. The English save/load wait sign has static pixel
coverage and still needs an automated live visual checkpoint. Continue watching opening
cinematics and rare/postgame transitions during playtesting; the earlier candidate list
did not establish additional missing translation assets.

For any newly reported graphical text or defect, record the screen/route, ROM range, tile
dimensions, tilemap/attribute source, palette, sharing/aliasing, and whether the asset is
stored or composed.

## Asset workflow

1. Capture the native screen and identify the exact visible Japanese pixels.
2. Trace VRAM tiles/tilemap/attributes back to ROM and native code.
3. Determine every consumer before replacing a shared asset.
4. Keep editable source artwork under `assets/graphics/` and include license/provenance notes
   for any external font or art source.
5. Build a deterministic installer with exact source hashes and collision checks.
6. Reserve its ROM range in [ROM_BANK_MAP.md](ROM_BANK_MAP.md).
7. Add a static plane/tilemap test plus a live route/screenshot regression.
8. Inspect at integer zoom in the emulator and verify every palette/state variant.

Prefer source rasters or explicit tile masks over opaque hand-edited ROM blobs. The source
asset should make the intended English artwork reviewable without opening a hex editor.

## Shared-asset rule

Do not mutate a shared native template until every consumer is mapped. The Status-menu red
window/palette regression demonstrated that visually identical entry routes can have different
redraw ownership. When only some consumers are owned, clone the asset into an exclusive bank
and redirect those consumers, as `menu_graphics.py` does.

## Font choices

Thin Pixel-7 is the approved in-game text font. Graphical title, banner, and credit artwork
may use different fonts when that better matches the native composition. Record each font's
license and keep its choice independent from the VWF metrics unless the asset truly shares the
runtime font.

## Acceptance criteria

A graphical family is complete only when:

- all native variants and routes are inventoried;
- English source artwork is committed and reproducible;
- the installer is exact-byte guarded and collision-checked;
- tile planes, maps, attributes, and palettes pass automated checks;
- live routes show no Japanese text, clipping, stale tiles, wrong palettes, or transition
  remnants;
- the result is visually approved at integer scale;
- the project status and bank map are updated.

Document uncaptured routes as verification gaps in [project-status.md](project-status.md).
