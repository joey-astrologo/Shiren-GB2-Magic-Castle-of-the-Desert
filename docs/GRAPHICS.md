# Graphics localization

Full graphics localization is a project requirement and remains active work. This document
separates what is already engineered from what still needs an inventory, translation, and
visual acceptance pass.

The first whole-ROM graphical-text inventory is now recorded in
[GRAPHICS_AUDIT.md](GRAPHICS_AUDIT.md). It traces the clean-boot copyright/composer card,
main title, all 32 town/dungeon/floor arrival selectors, the dedicated dungeon-HUD font,
and the save/load wait sign. The
ending staff roll is
proven by native scenario/BGM labels but remains unclassified until main-ending and true-ending
save states are available. The approved English copyright/composer card, arrival cards, and
wait sign are now installed; the title and ending staff roll remain active work. Automated live
reproduction of the wait-sign route remains pending.

## Proven storage model

GB2 graphics are uncompressed. A clean PyBoy title-screen capture found 261 of 270 nonblank
VRAM tiles verbatim in the ROM. The dense high-entropy banks seen during early triage are
ordinary art, not a compressed stream, so no general decompressor is needed before editing
graphical Japanese.

This does not mean every visible screen is one stored bitmap. A route may combine raw tile
planes, a tilemap, attributes, palette selection, numbers, and text drawn by the native VWF.
Each asset still needs its producer and consumers mapped.

## Already localized or engineered

| Area | State | Owner |
|---|---|---|
| In-game proportional font | Selectable Thin Pixel-7 classic black-only or reviewed palette-color-2 `+1,+1` shadowed style in all 79 native one-byte English slots, including the straight ASCII double quote at `$59`; both retain identical color-3 ink and advances | `english_font.py` |
| Core Status template labels | English bitmap overlay generated from the selected font style; shared native graphics remain unchanged | `menu_graphics.py` |
| Player-name / Rankings-note keyboard | English A-Z/a-z/0-9 map and shared style-selected glyph atlas, including the private cursor symbols; mode 2 retains its native 13-character note field while a private graph turns fourteen formerly empty slots into spaces and lets right pad a space at the current end | `name6.py` |
| Big Moai promotional gift-code keyboard ("spells") | Approved four-row A-Z/0-9 map, private navigation, below-label `DEL`/`OK` cursors, and its own guarded copy of the selected atlas style | `spell_input.py` |
| Blank Scroll keyboard | English A-Z/a-z/0-9 map, 11-character full-name input, mode-specific hyphen cell, and shared style-selected atlas | `blank_scroll.py` |
| Unidentified-item and Rescue keyboards | English maps over the shared style-selected atlas; dedicated mode-0 `FILL IN` history and full canonical-name display, plus modes 5-8 native password mapping | `unidentified_names.py`, `rescue_presentation.py` |
| Stairs popup geometry | Widened templates and background teardown | `stairs_menu.py` |
| Rescue Team, completed-rescue delivery, warehouse, Bank Teller, and Blacksmith Info popup geometry | Exact-menu seven-interior-tile frames using six renderer-owned dynamic tiles; warehouse and Bank have stable `$B3` spill cells, Blacksmith stages the `Synthesis` suffix in `$B3`, the shorter Rescue menu exposes only off-frame `Password` overflow tiles `$A8/$BA`, and completed-rescue delivery stages those fragments in `$9C/$AE` before clearing their live cursor aliases; active-VRAM-bank bottom border, staged-tile cleanup, and two-bank save/restore of the added ninth BG column | `service_menus.py` |
| Cracked-Bracelet marker | Stock Japanese `(hibi)` composite replaced by compact `(Cr)` at native token `F2 1E` | `item_status.py` |
| Item-row status gallery | Equip, curse, blessing, plate, cracked, synthesis color, and combined states reproduced on demand | `mesen_item_formatting_gallery.lua` |
| Copyright/composer card | Approved Inter SemiBold 4.1 `CHUNSOFT` and `Koichi Sugiyama` strips; native copyright rows, map, palettes, fade, scroll, and title handoff preserved | `credit_screen.py` |
| Town/dungeon/floor arrival cards | Approved Inter SemiBold 4.1 location artwork for all 32 selectors, including the decoded `Mystery Dungeon` alias; native Latin digits plus an approved one-pixel-raised `F`, centering, floor formatter, underline, palette inheritance, fade, and transition preserved through a guarded bank-$F8 renderer clone | `arrival_cards.py` |
| Dungeon HUD digits and slash | Approved player-supplied 4x8 rasters replace decimal `0-9` in the first five packed tiles and the approved 8x8 raster replaces the discontiguous slash tile; `A-F`, `L`, `v`, `H`, `p`, meter, and reserved tiles remain byte-exact native; the read-only contact sheet accepts and audits both source and installed atlases | `hud_font.py`, `hud_font_audition.py` |
| Shop-price font audit | All ten native two-tone digits decoded from guarded source `3:$5642-$56E1`, cropped and packed at the observed five-pixel shop-tag advance with captured black/white/gray palette roles; read-only contact sheet writes no ROM changes | `shop_price_font_audition.py` |
| Save/load wait sign | Approved Thin Pixel-7 `Please` / `wait...` raster in two guarded sign blocks; both interleaved bird-art blocks preserved byte-for-byte | `wait_screen.py` |

These are not evidence that title art, story cards, ending art, or every graphical menu label
is localized.

## Remaining inventory and implementation

The graphics pass must still complete or visually verify:

- replacement art and visual acceptance for the now-traced title logo;
- opening chase/cinematic graphical text;
- menu icons, category art, status marks, and explanatory diagrams;
- gift-code/name editor decorative labels outside generated maps;
- ending cards, credits, and end marks;
- postgame/alternate-route graphics;
- Super Game Boy or DMG assets only if later evidence shows the CGB-only ROM consumes them
  (the cartridge header currently says CGB-only and no SGB support).

For each candidate, record the screen/route, ROM range, tile dimensions, tilemap/attribute
source, palette, sharing/aliasing, and whether the asset is stored or composed.

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

Until that inventory is complete, project status must continue to say that graphics
localization remains unfinished.
