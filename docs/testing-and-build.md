# Testing and build

The prescriptive change gates are in [ENGINEERING_RULES.md](ENGINEERING_RULES.md), and the
tracked fixture conventions are documented in
[`tests/fixtures/README.md`](../tests/fixtures/README.md).

All tools expect a user-supplied matching Japanese ROM. A convenient shell variable is:

```sh
ROM="Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
```

The expected clean source is a 4 MiB, CGB-only MBC5 ROM with SHA-1
`5264f6d0c4f12c9144de1d12fddadbadd82b3e33` and MD5
`9e3d4ff0ba3d6deec5080f6dbed4fef8`.

## Normal validation

For a story edit, check and apply the authoritative scene document first:

```sh
python3 tools/prose_editor.py "$ROM"
python3 tools/prose_editor.py "$ROM" --apply
```

Then run the cross-catalog and runtime checks:

```sh
python3 tools/overlays.py "$ROM"
python3 tools/internal_audit.py "$ROM"
python3 tools/lint_en.py "$ROM"
python3 tools/runtime_widths.py "$ROM"
python3 tools/menu_text.py "$ROM"
```

The production build installs and validates the player-name, death-Rankings note, Big Moai
promotional-code, Blank Scroll, unidentified-item naming, and Wanderer Rescue password I/O
patches. Their focused contracts can also be run directly through
`tests.test_name6`, `tests.test_ranking_note_input`, `tests.test_spell_input`, `tests.test_blank_scroll`,
`tests.test_pyboy_blank_scroll`, `tests.test_unidentified_names`, and
`tests.test_pyboy_unidentified_item`.

Ranking score/floor suffixes have a hash-independent static pixel contract plus a live
complete-production replay. Run both focused checks with:

```sh
python3 -m unittest \
  tests.test_surfaces.OriginalRomPositionedSurfaceTests.test_production_ranking_score_and_floor_suffixes_are_unambiguous \
  tests.test_surfaces.ProductionRankingSuffixTests -v
```

The Big Moai NPC gate and first accepted-code route have their own focused family:

```sh
python3 -m unittest tests.test_big_moai -v
```

It hash-freezes `SaveStates/big-moai-locked.state`, replays the native “not ready” branch,
requires `pyboy_fixtures.unlock_big_moai` to change only `$C3EF-$C3F0`, then enters
`WISH` through the real localized mode-3 editor and requires item `$70` (Fortune Grass)
in inventory. The route visits `DEL` first and freezes both its corrected below-label cursor
and the native auto-selected `OK` cursor. It then freezes the localized reward framebuffer
and starts a second Big Moai conversation, requiring group `$6A` index `$1A`; this would be
unreachable if the reward formatter were still frozen. Manual use and the complete gate are in
[BIG_MOAI.md](BIG_MOAI.md).

The read-only native Wanderer Rescue audit can be run independently:

```sh
python3 tools/rescue_password.py "$ROM" --json
python3 -m unittest tests.test_rescue_password tests.test_rescue_presentation -v
```

It freezes the native input limits, protocol code, loaded-diary record dispatchers, stage
callers, SOS field layout, native actor Max/current-HP paths, a one-HP requester setup
helper, and a real linked SOS/Revival/Thank-You exchange. The presentation test builds the
ROM, replays the supplied Rankings state through **Await Rescue**, requires the English SOS
framebuffer, and asserts the restored native buffer and matching diary record. A second
PyBoy route loads `SaveStates/rescue-entry-menu.state`, opens Password, freezes the English
64-symbol keyboard, enters the published `OEN936H9n!FVv` vector, requires its exact native
bytes before confirmation, and submits it to the original validator. The expected result
is the native inaccessible-dungeon response because that diary has not unlocked the
Abyssal Depths. Before opening Password, this route deliberately changes the capture's
accidentally retained previous-mode byte `$C195` from `$08` to mode 0. It leaves the mode
requested by the game in register C alone. The old production wrapper therefore fails
before reaching the English-editor checkpoint; the corrected constructor publishes mode 8
and completes physical-B deletion, full entry, and native validation. A requester-side
route separately opens **Adventure -> Revive! ->
Password**, enters linked response `SVgaVwAhmUmoM3u` in the 15-character editor, requires
`Revival complete!`, and freezes generated Thank-You Password `EkWsMPtHHOEE`. That route
also guards the native behavior that moves a completely filled password to `OK`; previous
test navigation could accidentally select `DEL` instead of submitting.
It additionally covers the distinct bank-16 `$68E4` constructor ordering, where mode 7 is
still carried in register C before native `$C195` is initialized; the English wrapper must
publish that mode and preserve C before the controller begins.
Before entering the public vector, the mode-8 route now enters `AB`, presses hardware B,
and freezes both the rendered uppercase `A` and native `30 D5...FF` buffer. This catches the
dedicated native hardware-B path bypassing the selected English keyboard-node overlay. It then
clears that cell and continues the public-vector route in the same fresh process.
The SOS route proved a working constructor path but did not reproduce the manually
observed hardware-B redraw until the test used that exact input path. The retained route
constructs mode 8 from `rescue-entry-menu.state`, enters `AB`, presses the physical B button,
and requires native buffer `30 D5...FF` plus an unchanged visible uppercase-`A` glyph band.
This exercises the dedicated event-table handler rather than the on-screen `DEL` node. The
earlier already-active-editor repair fixture and common-loop hook were removed because they
did not model this reproducible route. The suite does not yet claim a complete live
two-diary emulator pass. Each route hash-checks its committed native `.state`, builds a ROM
at a new temporary path, launches a fresh headless PyBoy instance, and stops without saving
over the fixture. It therefore cannot reuse cached ROM or emulator state.

When their owned files change, also run the relevant family check before applying:

```sh
python3 tools/wrap_item_messages.py "$ROM"
python3 tools/wrap_item_messages.py "$ROM" --apply
python3 tools/combat_messages.py "$ROM"
python3 tools/combat_messages.py "$ROM" --warnings-json
python3 tools/combat_messages.py "$ROM" --apply
python3 tools/wrap_items.py "$ROM" script/en/items.tsv script/en/items.tsv
```

Do not use `tools/wrap_en.py --apply` as the normal story-authoring entry point. The
scene editor owns that workflow and invokes the measured wrapper itself.

## Build

```sh
python3 tools/build.py "$ROM" script/en build/shiren-gb2-english.gbc --font-style both
```

This writes `build/shiren-gb2-english-classic-font.gbc` and
`build/shiren-gb2-english-shadowed-font.gbc`, plus a same-named `.ips` for each font.
Every IPS uses the verified original Japanese ROM as its base. The builder reapplies each
generated patch and requires the result to equal its paired ROM byte for byte before the
patch is written. Use `--font-style classic` or `--font-style shadowed` for one ROM at the
exact output path; shadowed is the default, and the corresponding `.ips` is still produced.
The production builder reruns required safety checks before writing each output. Text is
relocated through far pointers, so storage growth does not justify shortening visible
English. The builder prints SHA-1 identifiers for the exact ROM and IPS artifacts.

## Tests

```sh
python3 -m unittest discover -s tests
```

For a focused graphical-input check:

```sh
python3 -m unittest \
  tests.test_save_summary \
  tests.test_name6 \
  tests.test_spell_input \
  tests.test_blank_scroll \
  tests.test_pyboy_blank_scroll \
  tests.test_unidentified_names \
  tests.test_pyboy_unidentified_item \
  tests.test_pyboy_state_fixtures \
  tests.test_rescue_password \
  tests.test_rescue_presentation \
  tests.test_service_menus \
  tests.test_item_status \
  tests.test_item_formatting \
  tests.test_item_terminology \
  tests.test_synthesis_lab
```

For the read-only graphical-text inventory:

```sh
python3 tools/graphics_audit.py "$ROM"
python3 -m unittest tests.test_graphics_audit -v
```

This verifies native tile-plane headers, resource aliases, interleaved maps/attributes,
palette provenance, all 32 arrival-card sequences, and the explicit ending-route gap. It does
not write a ROM or update framebuffer hashes.

For the ROM-independent 32-selector arrival-card font audition:

```sh
python3 -m unittest tests.test_arrival_card_audition -v
python3 tools/arrival_card_audition.py
```

The tests freeze the measured native bands and palette, complete selector coverage,
16-pixel underline alignment, 144-pixel fit enforcement, the decoded shared `Mystery
Dungeon` label, and CLI contact-sheet generation. The sheet command writes only its requested
PNG unless `--asset-output` is explicitly supplied.

For the native top-status-bar font audit:

```sh
python3 -m unittest tests.test_hud_font_audition -v
python3 tools/hud_font_audition.py
```

This reads the guarded 16-tile source at `3:$5742-$5841` and writes only
`build/hud_font_audition.png` by default. The regression freezes every `0-9A-F`, `L/v/H/p`,
slash, and meter source raster needed by the sheet, proves all 20 alphanumeric slots are
distinct and nonempty, and checks a native-width `99F Lv 99 Hp 999/999` proof. It never
updates framebuffer hashes or modifies the ROM.

For the dedicated shop-price digit font:

```sh
python3 -m unittest tests.test_shop_price_font_audition -v
python3 tools/shop_price_font_audition.py
```

This hash-verifies and decodes all ten 2bpp tiles at `3:$5642-$56E1`, crops the live
five-pixel digit cells, and writes only `build/shop_price_font_audition.png`. The tests
freeze representative literal color-index rasters, all ten distinct digits, five-pixel
packing, the captured color-3 black / color-1 white / color-2 `#A8A8A8` shade mapping,
maximum five-digit proofs, CLI rendering, and read-only behavior.

For the installed Thin Pixel-7 dialogue-font shadow audit:

```sh
python3 -m unittest tests.test_font_shadow_audition -v
python3 -m unittest tests.test_font_variants -v
python3 tools/font_shadow_audition.py
```

This loads the approved font source, compares its raw glyphs against the installed captured
palette-color-2 gray (`#ACACAC`) offset by `(1,1)` with the original black pixels redrawn on
top, and writes only `build/font_shadow_audition.png`. The production encoder's cutoff
cleanup moves a
disconnected bottom shadow pixel left for `,`, `g`, `j`, and `y`; connected cutoff shadows
are retained. Tests cover all 79 characters, the `+` palette-color proof, unchanged advances
and black pixels, 8x8 bottom clipping, proportional-advance overhang, 2bpp round-tripping,
production/audit equivalence, and CLI sheet generation. The audit command does not edit the
font JSON, change layout contracts, or modify a ROM.

`tests.test_menu_graphics` separately freezes a literal color-index raster and exact
shadow/ink counts for all 14 fixed Status-screen labels. Those labels are a generated bitmap
overlay rather than runtime strings, so this regression ensures they stay pixel-identical to
the installed two-tone font across menu open, refresh, and Help-return routes.

For the approved arrival-card source and production insertion:

```sh
python3 -m unittest tests.test_arrival_cards -v
```

This regenerates the approved location JSON in memory, independently decodes all 32 production
selector sequences, proves all eleven native Latin floor source glyphs re-encode byte-for-byte,
proves the ten production digit blocks stay native and the shared `F` receives only its approved
one-pixel upward adjustment, and composes every floor from `1F` through `99F`. It guards the
native entry and dedicated bank `$F8`, traverses the natural Mamel stairs route to compare
`Ancient Ruins` / `1F` and `2F` pixels, and directly compares the live `1`/`F` bright-cap rows.
It does not accept or refresh a framebuffer hash.

For the approved copyright/composer card source and production insertion:

```sh
python3 -m unittest \
  tests.test_credit_screen_mockup \
  tests.test_credit_screen -v
```

These tests freeze the licensed font provenance and editable four-level source, exact-hash
guard both native name strips, confine production mutations to those ranges, and compare live
pixels across the native fade and title handoff. They do not accept or refresh a framebuffer
hash.

For the approved save/load wait-sign source and production insertion:

```sh
python3 -m unittest tests.test_wait_screen -v
```

This independently decodes both 64x16 ROM blocks, compares the complete production sign to
the approved `Please` / `wait...` raster, confines mutations to those blocks and checksum
bytes, and proves both interleaved bird-art blocks remain byte-identical. It does not accept
or refresh a framebuffer hash. The supplied screenshot is an exact static reference; an
automated emulator trigger for this transient screen remains pending.

The suite covers extraction and catalogs, translation fixtures, control preservation, VWF
widths, wrapping, menus, save/name expansion, Big Moai promotional-code input and live NPC reward, Blank Scroll input,
unidentified-item free/history naming, runtime text domains, scene ownership, internal
classification, and deterministic production builds.
User-reported regressions should receive a focused fixture or behavioral test whenever the
mechanism is reproducible.

`tests.test_item_terminology` freezes all 50 approved series-name corrections, all affected
unidentified-item roots, every identified description-title/name pair, and the reviewed
Help/UI/dialogue layouts whose literal item references changed. The Wanda equipment lesson
fixture also preserves its `<page><box>` reader wait.

The complete run on 2026-09-02 used the matching ROM, PyBoy, and RGBDS. Mesen is not a test
dependency. It includes the graphics-audit, credit-source/insertion, wait-sign,
arrival-card, ranking-suffix, death-Rankings note, and warehouse horizontal-wrap regressions. The required gate
is always discovery of the complete `tests/` directory, not a hard-coded count.

`tests.test_save_summary` also replays the exact title-screen Adventure -> save-file route
with `SaveStates/Mamel.state`. It freezes native navigation type `$13`, all four
Continue/Secrets/Reset/Recap cursor positions, the cursor OAM coordinates, and a
cursor-masked framebuffer hash. This guards against input-editor navigation patches
stealing a live menu graph or corrupting the submenu during Up/Down movement.
The supplied requester SOS SRAM adds a second live summary fixture: `Awaiting Rescue` and
the independent run count must render together without collision.

`tests.test_service_menus` chains its installer after the stairs-popup owner, measures all
Rescue Team, warehouse, Bank Teller, and Blacksmith Info labels against the 48-pixel live
text budget inside the new 56-pixel interior, and rejects any
unexpected predecessor bytes or occupied reservation. Its PyBoy routes rebuild the menus
through controller input, require nine-column background copies, traverse every cursor
position, and require clean B-button teardown. The native renderer owns only
six dynamic tiles per row. Warehouse and Bank therefore require stable tile `$B3` on every
spill row. Blacksmith Info stages `Synthesis`'s suffix in `$B3`, clears the `$9C` alias from
unselected Quit, maps other spills to stable blank `$B9` in the active VRAM bank, and
restores `$B3` on close.
The three-entry Rescue menu requires `$A8/$BA` only for the two `Password` overflow rows and
`$B3` elsewhere. The completed-rescue four-entry menu stages those fragments in off-frame
`$9C/$AE`, clears the cursor-owned sources, and keeps `$B3` in every other spill. Its
`at-rescue.state` regression visits Cable, Password,
Cancel, and Later with real input while checking the literal `d` and both cursor columns.
The other routes visit all three initial Rescue entries, four entries in Warehouse and
Bank, and all five Blacksmith Info entries. This catches the
duplicate right-edge cursor that an open-only test missed. A separate test compares the
final `d` with a literal approved 5x8 mask; another compares the complete 45x8 `Synthesis`
raster and requires blank 8x8 cells on both sides of unselected `Quit`. Both are
independent of every framebuffer hash. The routes also capture the original tile
and attribute in every added-column row, require the complete right border while open, and
require exact restoration after dismissal. The warehouse assertion includes the hardware
BG-map wrap from `$9BF0` to `$9810`. The Rescue route additionally freezes its
preceding native Yes/No confirmation and verifies the widened bottom border inherits the
renderer-selected CGB VRAM bank. This avoids accepting stale VRAM already embedded in a
save state or a deterministic but visibly damaged popup. A separate Rescue selection route
chooses `Password`, verifies the saved ninth-column destination is `$9950`, requires its
two-byte live marker to be cleared, and freezes the immediate transition. That test owns
the reported leftover vertical strip; eventual arrival at a stable editor is not accepted
as a substitute.

`SaveStates/warehouse-floor-items.state` adds the camera-history case discovered after
placing items without leaving the warehouse; its widened frame crosses x=31. The regression
requires the added column at row 14/x4 (`$99C4`), checks the literal 8x64 right edge through
all four options, and verifies teardown from saved tile/attribute pairs. The companion
`warehouse-floor-items-reenter.state` proves the same check on the clean post-reentry
camera position. These pixel checks are independent of the existing full-screen hashes.

`tests.test_name6` freezes the title and Secrets event selectors, the complete fourteen-row
replay pointer table, and the SHA-1 of every original 106-byte embedded diary. It proves
that installation changes only each snapshot's five-byte native name field and four-byte
suffix/marker tail. A PyBoy-backed getter check then loads the patched title-family event 0
and the first/last Secrets events 4 and 13 and requires the complete `Shiren` result.
It also freezes literal two-plane bytes for uppercase, lowercase-tail, digit, and cursor
glyphs in the installed graphical-input atlas, then checks the live `A` tile pixel-for-pixel
against black ink, gray shadow, and white background RGB values. `tests.test_spell_input`
independently freezes the same literal `A` in Big Moai's private atlas; live editor routes
cover Blank Scroll, unidentified items, Rescue entry/revival, and Big Moai `WISH`.
`tests.test_ranking_note_input` attacks the adjacent Mamel from the frozen one-HP state,
reaches the death Rankings result, presses Start, requires mode 2 with its native
13-character maximum, and compares the live editor against independently synthesized
English keyboard pixels without adopting a framebuffer hash. A second controller-only
route selects a formerly empty cell and exercises the visual right arrow at an empty
message end; both must write English space `$24` and advance exactly one position. Static
and live PyBoy checks cover every one of the fourteen available space nodes and prove the
same right-arrow operation remains a no-op in player-name mode 4.

`tests.test_multiple_unidentified_names` loads
`SaveStates/multiple-unidentified-items.state`, names the Pot `Preservation`, then names the
Rabbit Scroll `Escape` entirely through controller input. It requires distinct native
custom-name slots containing roots 107 and 67. A live PyBoy check separately proves that
both current `FE FF` and legacy `FF FE` canonical tokens resolve.

`tests.test_item_status` freezes the exact `SaveStates/broken-bracelet.state` supplied for the
bad cracked-marker report. Because a machine state retains already-rendered VRAM, the live
PyBoy route closes and reopens Items before asserting the `(Cr)` screen. Static checks also
guard the original 40-byte `F2 1E` bitmap, native `0F 06` width pair, reviewed replacement
raster, exclusive ROM ownership, and the 18-pixel worst-case item-row margin.

`tests.test_item_formatting` guards all nine native producer/cave patches, measures every
translated weapon/shield/arrow/staff/Pot dynamic row, and replays the two-page item gallery
from `SaveStates/Mamel.state`. Its widest combined status row ends at x=132 against the
x=144 item-list edge. Manual gallery instructions and the twenty expected rows are in
[ITEM_FORMATTING.md](ITEM_FORMATTING.md).

`tests.test_synthesis_lab` drives a real Synthesis Pot through both `Put In` operations
from the same disposable state. It drives every intervening native menu and asserts that
the Club becomes the contained base, the Axe donor is consumed, the sparse Pot sentinels
remain valid, and the native deferred-synthesis state is reached. It then throws and breaks
the Pot and asserts that the released Club carries weapon rune bit 10. The manual route
reviews the recovered weapon's seal description; see
[ITEM_FORMATTING.md](ITEM_FORMATTING.md#synthesis-seal-manual-route).

The committed fixtures are deliberate contracts. If an intentional change updates one,
review the semantic difference rather than accepting fixture churn blindly.

## Diagnostic and recovery tools

These are not required for an ordinary text edit, but remain useful when investigating
ROM or emulator behavior:

```sh
python3 tools/codec.py "$ROM"
python3 tools/textdump.py "$ROM" --space
python3 tools/font.py "$ROM" --info
python3 tools/allocate.py "$ROM" --output build/script-allocation.json
python3 tools/layout.py "$ROM"
python3 tools/surfaces.py "$ROM"
python3 ../mesen-to-pyboy/mss_to_pyboy.py SaveStates/ \
  --rom "$ROM" --output-dir SaveStates --verify-frames 12 --force
```

The converter keeps the original `.mss` inputs untouched, writes native `.state` files,
reloads and compares the supported machine state, and advances each result. Automated
tests consume only `.state`; `tests.test_pyboy_state_fixtures` enforces the pairing and
rejects Mesen-only test routes.

### Wanderer Rescue requester capture

`tools/mesen_prepare_rescue_request.lua` provides the first deterministic rescue-fixture
step. Load the current English ROM and `SaveStates/Mamel.mss`, pause, run the helper through
**Debug > Script Window**, and resume. It verifies that actor 0 is active and that the full
32-byte bank-1 actor record matches the `$FF90-$FFAF` cache before changing both current-HP
views from 40 to 1. It never writes Max HP, story/rescue flags, inventory, SRAM, or ROM.

Dismiss the existing message if necessary, then let the adjacent Mamel hit Shiren once;
do not attack it first. On the resulting Rankings screen, press `Select` and choose
**Await Rescue**. The reviewed test fixtures are
`SaveStates/rescue-requester-rankings.state` and
`SaveStates/rescue-requester-sos.state`; the matching SRAM remains ignored. The focused tests
freeze both state hashes, decode the 13 native symbols, prove they match diary offset
`+$41`, replay the complete Rankings confirmation route, and require English output with
the native bytes restored. `SaveStates/rescue-entry-menu.state` and
`tests/fixtures/rescue_entry.json` add the rescuer-side Password-menu/editor boundary: the
route uses only controller input, verifies private navigation type `$F5`, writes all 13
published SOS symbols as native bytes, and returns from native validation with the expected
inaccessible-dungeon message. `tests.test_rescue_presentation` also reuses the requester
SOS state without memory writes, enters a linked no-gift Revival response, and
requires both native success and the exact generated Thank-You Password.
The same rescuer-side route enters `AB`, presses hardware B, and proves the remaining
uppercase glyph, input position, and native buffer agree before it continues with the
published SOS vector.
The linked requester response is accepted, but physical Rescue Gate traversal and capture
of a Revival Password generated by the rescuer diary remain in the broader two-diary
handshake.

### Dynamic item-row gallery

`tools/mesen_item_formatting_gallery.lua` injects a disposable twenty-item inventory into
`SaveStates/Mamel.mss`. It presents status symbols and combinations on page 1, then numeric
and category-specific formats on page 2. See [ITEM_FORMATTING.md](ITEM_FORMATTING.md) for
the exact route and checklist. Do not sort or save the injected run.

### Synthesis Pot manual route

`tools/mesen_spawn_synthesis_lab.lua` replaces the disposable Mamel inventory with a
Synthesis Pot, a Club base, and an Axe of the Minotaur donor. Use **Synthesis Pot > Put
In > Club**, repeat with the Axe, break the Pot against a wall, recover the Club, and
inspect Info for `More frequent critical hits.` The exact route and native structure are
documented in [ITEM_FORMATTING.md](ITEM_FORMATTING.md#synthesis-seal-manual-route). This
helper deliberately erases the prior inventory; never run it against a save you intend to
keep.

### Blank Scroll manual route

`tools/mesen_spawn_blank_scroll.lua` safely adds one real Blank Scroll to the first free
inventory slot for manual Mesen testing. Enter a dungeon, pause emulation, load the helper
through **Debug > Script Window**, and press **Run (F5)**. Resume and reopen Items.

The item name, description, `Write` action, and 11-character full-name keyboard are
translated. The `0` cell enters the hyphen required by `Trap-eraser`. Recognition retains
the native notebook rule: only a Scroll already discovered on that save can be written.
The complete accepted-name table and mechanism are in
[BLANK_SCROLL.md](BLANK_SCROLL.md).

Back up the save or use a disposable state because Mesen may persist later in-game saves
after the live WRAM injection.

### Unidentified item naming manual route

`SaveStates/unidentified-item-naming.state` freezes the exact reported Rabbit Scroll route.
Because it was captured after the old screen was drawn, back out and reopen **Name** after
loading it with the latest ROM. From the initial `A` cell, **Up, Right, Up** reaches the
localized `FILL IN` history control. Each activation cycles to the next learned name; it
does not open a separate list.

`tools/mesen_spawn_unidentified_item.lua` provides a second disposable route from
`Mamel.mss`: it creates a real item, presents it through a chosen unidentified appearance,
and enables exactly its learned-name/history bit. Reload the state between free-name and
`FILL IN` tests. Canonical recalls use a build-guarded 14-character preview and render their
full translated root after confirmation; free labels retain the native seven-character
maximum. The live regression also freezes the no-star `Windblade` preview, typing-after-fill
reset, `DEL`-after-fill reset, and successful return to Items after a new free name. The
complete checklist, token contract, alternate categories, and regression command are in
[UNIDENTIFIED_ITEM_NAMING.md](UNIDENTIFIED_ITEM_NAMING.md).
