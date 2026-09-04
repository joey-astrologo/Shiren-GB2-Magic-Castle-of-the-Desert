# Engineering overview

This document records the stable architectural conclusions needed to maintain the
localization. Executable tools and tests remain the authority for byte-level details.

For full contracts, use the [text reference](TEXT_REFERENCE.md),
[VWF budget register](VWF_BUDGETS.md), [ROM ownership map](ROM_BANK_MAP.md), and
[menu architecture](MENU_STRUCTURE.md).

## Source ROM and script model

The supported source identifies itself as `SIREN GB2`. It is a 4 MiB, CGB-only MBC5
cartridge with 32 KiB of battery-backed RAM; it does not run on DMG hardware. Its clean
SHA-1 is `5264f6d0c4f12c9144de1d12fddadbadd82b3e33`.

GB2 begins with 61 completely empty ROM banks (976 KiB), plus smaller internal filler
runs. Unlike GB1, it needs neither a mapper conversion nor DTE to make English storage
possible. MBC5 can address up to 8 MiB, but the current 4 MiB image already has ample
headroom.

The extractor identifies 6,695
stable text records reached by 7,163 logical references and organizes every record into
one translator-facing category. Stable `bank:$address` IDs allow generated source-rich
catalogs to be refreshed without losing the compact English workspace.

The original game already has a proportional text renderer. The project installs the
Thin Pixel-7 English glyphs and advances, then measures both relevant native boundaries:
143 pixels at composition and 144 pixels at rendering. The production script allocator
uses far pointers and currently spans 19 ROM banks, so a logical group may grow beyond its
original local bank without sacrificing translation content.

The extraction and localization layers are intentionally separate:

- `script/script.json` and `script/script.tsv`: generated raw extraction
- `script/organized/`: generated source-rich semantic catalogs
- `script/en/`: tracked source-free production English
- `script/editing/prose.tsv`: authoritative scene-ordered dialogue editor
- `script/drafts/`: specialized generated or family-owned message worksheets

## Runtime text behavior

Text controls carry engine behavior, not editorial markup. In particular, `<page>` waits
without resetting the line cursor, `<box>` resets the surface without guaranteeing a wait,
`<br>` advances immediately, and `<cF3>` is a conditional soft-wrap checkpoint. F4/F5/F6
controls insert runtime values whose complete translated width domains must be measured.
The precise authoring rules live in [Translation policy](translation-policy.md).

Positioned menus use separate geometry from dialogue. The layout audit validates 143 of
144 positioned records directly; the remaining dynamic record is validated against its
runtime value domain. Menu, Help, Monster Notebook, combat, item-message, and item-detail
families each retain their own proven surface rules rather than sharing a guessed global
character limit.

Widened dynamic menus also retain the renderer's native tile-allocation limits. The reviewed
Rescue Team, warehouse, Bank Teller, and Blacksmith Info frames have seven visible interior
cells, but only six sequential dynamic tiles per row. Warehouse and Bank use stable tile
`$B3` for every seventh cell. Blacksmith Info stages the final `Synthesis` tile in `$B3`,
blanks its `$9C` alias in the unselected Quit cursor cell, and selects the renderer's VRAM
bank for every stable `$B9` spill. Rescue uses a
separate template exposing only the two off-screen-row overflow tiles needed by `Password`'s
final `d`, with `$B3` everywhere else. Live PyBoy routes traverse every option so cursor
redraws, tile aliasing, VRAM-bank attributes, glyph pixels, staged-tile restoration, and
teardown are tested as behavior rather than inferred from a single open frame.

## Save and name expansion

The localized player-name editor accepts up to six visible characters and defaults to
`Shiren`. In the loaded diary record's WRAM copy, characters five and six use tail bytes
`$C2A2-$C2A3`; marker `A5 5A` at `$C2A4-$C2A5` distinguishes the expanded record while
preserving old Japanese saves. The native save path persists those record offsets.
Ranking-result suffix storage uses SRAM bank 3: header `$BCD8-$BCDB` contains `N6R1`, and
the per-record suffix table occupies `$BCDC-$BECF`. The tests cover new names, existing
Japanese saves, save/resume, and ranking-name preservation.

Demo playback is a separate name source: event IDs 0-13 copy one of fourteen complete
106-byte diary snapshots from banks 208-214 into the ordinary loaded record. Events 0-3
are the non-Secrets demo family (the title attract route selects 0 or 1), while events
4-13 are the ten Wanderer's Secrets. `name6.py` patches each snapshot to the same
`Shir` + `en` + `A5 5A` contract and freezes the dispatcher table, selector code, and all
fourteen original record hashes. Ordinary Help/Hint prose pages do not use these snapshots;
only a launched replay does.

## Big Moai promotional gift-code input

The game calls these promotional/reward passwords "spells." Chunsoft published codes on
cards and in publications; players enter them at Big Moai to receive rewards. This is
independent of Wanderer Rescue. The native comparison contract is exactly four bytes.
Mode 3 is localized as the approved four-row A-Z/0-9 editor with below-label `DEL`/`OK`
cursors; it cannot be expanded to arbitrary-length prose without changing the runtime contract.
Bank 252 holds the localized keyboard/logic
and all 100 English runtime codes. Matching internal diagnostic labels and the seven story
clues are generated from the same mapping so they cannot drift.

The user-supplied locked NPC state proved the availability mechanism: event
`74:$5CEF` enters group `$6A` index `$0D` while story stage `$C3EF < $09` and reaches the
spell route at stage 9. `$C3F0` is the serialized stage shadow. The narrow PyBoy helper
changes only that pair. A live controller fixture now starts from the locked state, runs
the production helper, visits the corrected `DEL` cursor, enters `WISH`, freezes the native
auto-selection of the corrected `OK` cursor, and
asserts that item `$70` (Fortune Grass) is added. It also freezes the rendered reward and
re-enters conversation to prove the event returned safely. F8-prefixed template selectors
remain in their native byte domain even inside English source; ordinary lowercase encoding
would corrupt the dynamic reward slot. See [BIG_MOAI.md](BIG_MOAI.md).

## Wanderer Rescue passwords

Wanderer Rescue is a separate 64-symbol native protocol with 13-character SOS,
15-character Revival, and 12-character Thank-You stages. `rescue_password.py` reproduces
the packet transform, checksum, SOS fields, seed-masked gift record, rescuer diary-ID
checksum, and acknowledgement relationship. A surviving three-code exchange validates
end to end and is frozen as a fixture. The output presentation maps all 64 native values
one-to-one to `A-Z a-z 0-9 ? !` only while the dynamic text cache consumes a password;
it then restores `$C16D`, so packets, diary records, and Link Cable transport remain native.
The supplied Rankings route is replayed through the confirmation prompt and freezes the
native third-row Yes/No cursor alignment, English SOS framebuffer, and unchanged native
protocol bytes. Modes 5-8 reuse the
approved English name-entry layout plus `?` and `!`, but use private navigation type `$F5`
and convert every selected node back to its native six-bit value before confirmation. A
live PyBoy route enters the published `OEN936H9n!FVv` SOS vector through that keyboard and
returns safely from the native validator. The same route enters `AB`, presses hardware B,
and requires that native `A` remains visibly uppercase. This uses the dedicated native
hardware-B event handler; only its delete far call is wrapped, while the common input loop
remains native. The mode-8 constructor test first forces the fixture's retained `$C195` to
mode 0, proving the ordinary screen redirect consumes the requested mode from register C
rather than stale WRAM. A second controller replay covers requester-side mode 7, whose
constructor has the same register ordering, and verifies linked Revival
acceptance and Thank-You generation. Physical Rescue Gate traversal and the rescuer
diary's generated response remain the next
engineering gate. See
[RESCUE_SYSTEM.md](RESCUE_SYSTEM.md).

## Blank Scroll writing

Mode 1 uses the English graphical keyboard and a bank-251 history-filtered full-name matcher.
The presentation field accepts 11 characters and the otherwise unused `0` cell supplies the
hyphen required by `Trap-eraser`. Confirmation resolves the complete name to a Scroll root
ID, restores the native seven-character backend field, and converts from that ID. The complete
accepted-input table and manual route are documented in
[BLANK_SCROLL.md](BLANK_SCROLL.md).

## Unidentified item naming

Mode 0 retains the native seven-character free-label field and 20 persistent custom-name
slots, but owns a dedicated English bank-250 keyboard and navigation graph. Its `FILL IN`
control cycles learned canonical names directly into a build-guarded 14-character preview;
it does not open a separate list. English roots are stored as a compact
`FE FF <root-index>` occupied signature in the native eight-byte slot and expanded through the
translated root table at display time. This preserves the save layout while allowing full
series names such as `Windblade`. The exact user state, helper route, and storage contract
are documented in [UNIDENTIFIED_ITEM_NAMING.md](UNIDENTIFIED_ITEM_NAMING.md).
Its private WRAM graph is selected through an unreachable English name-entry record, not by
replacing native navigation type `$13`; the latter remains owned by ordinary vertical menus
including Adventure -> Continue/Secrets/Reset/Recap.

## Graphics

Game graphics are uncompressed. A clean PyBoy title-screen capture found 261 of 270 nonblank
VRAM tiles verbatim in the ROM, so the project does not need a graphics decompressor before
localizing artwork. Dense high-entropy banks are art rather than a packed stream. Graphics
fonts remain an art-direction decision separate from the Thin Pixel-7 in-game text font.
One important exception to blanket prefixed-font preservation is the `F2 1E` cracked-Bracelet
composite: its stock pixels spell Japanese `(hibi)`. `item_status.py` replaces only that
40-byte raster with `(Cr)`, preserving the native token and width contract.

The dungeon HUD uses another independent packed atlas. `hud_font.py` replaces its five
decimal digit tiles, the visible `F/L/v/H/p` cells in tiles seven through nine, and slash tile
ten with approved rasters. `A-E`, including the `E` half-slot co-packed with `F`, plus meter
art and reserved cells remain native. `hud_font_audition.py` renders both the verified source
atlas and this exact localized production form.

## Dynamic item rows

Group 4 supplies translated item roots, but the inventory list is not stored as complete
strings. Native bank-120 and bank-122 routines append equipment signs, arrow quantities,
staff charges, and Pot capacities; the shared status decorator adds equip, curse, blessing,
and plate glyphs. `item_formatting.py` localizes only those punctuation producers, while
`item_status.py` owns the cracked-Bracelet composite bitmap. Exhaustive width checks and a
two-page live PyBoy gallery cover the combined result. See
[ITEM_FORMATTING.md](ITEM_FORMATTING.md).

## Emulator state recovery

`../mesen-to-pyboy/mss_to_pyboy.py` converts the supported portable machine state from a
Mesen 2 container into a native PyBoy `.state`, reloads it, compares preserved registers and
memory banks, and advances a smoke test. The reviewed `.mss` sources remain beside the
generated native fixtures as provenance; automated tests consume only `.state`.

## Validation philosophy

The project favors fail-closed generated-cell ownership and fixtures over manual spot checks.
Tools preserve source hashes, stable IDs, control-token order, runtime substitutions, geometry,
and semantic-family counts. Playtesting remains essential for presentation and route coverage,
but a fixed bug should also gain a focused automated contract whenever its mechanism can be
reproduced.
