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

## Save and name expansion

The localized player-name editor accepts up to six visible characters and defaults to
`Shiren`. In the loaded diary record's WRAM copy, characters five and six use tail bytes
`$C2A2-$C2A3`; marker `A5 5A` at `$C2A4-$C2A5` distinguishes the expanded record while
preserving old Japanese saves. The native save path persists those record offsets.
Ranking-result suffix storage uses SRAM bank 3: header `$BCD8-$BCDB` contains `N6R1`, and
the per-record suffix table occupies `$BCDC-$BECF`. The tests cover new names, existing
Japanese saves, save/resume, and ranking-name preservation.

## Big Moai spell input

The native spell comparison contract is exactly four bytes. Mode 3 is localized as a compact
A-Z/0-9 editor; it cannot be expanded to arbitrary-length prose without changing the runtime
contract. Bank 252 holds the localized keyboard/logic and all 100 English runtime codes.
Matching internal diagnostic labels and the seven story clues are generated from the same
mapping so they cannot drift.

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
`FF FE <root-index>` signature in the native eight-byte slot and expanded through the
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

## Emulator state recovery

`tools/mesen_state.py` reads Mesen 2's named-field save-state container and extracts its
`cartRam` member as a normal 32 KiB `.srm` file for PyBoy. That route was used to reproduce
the Mamel combat freeze that exposed nested far-pointer bank publication, and it remains the
preferred way to turn a user-provided Mesen state into a deterministic PyBoy fixture.

## Validation philosophy

The project favors fail-closed generated-cell ownership and fixtures over manual spot checks.
Tools preserve source hashes, stable IDs, control-token order, runtime substitutions, geometry,
and semantic-family counts. Playtesting remains essential for presentation and route coverage,
but a fixed bug should also gain a focused automated contract whenever its mechanism can be
reproduced.
