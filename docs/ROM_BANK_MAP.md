# ROM and persistent-memory ownership map

Read this before placing or moving ROM code, tables, text, font data, graphics, or
persistent-save extensions. The constants, expected-byte guards, and overlap checks in
the named installer are authoritative; update this map in the same change when ownership
moves.

A run of `$00` or `$FF` bytes is not by itself proof that a span is unused. GB2 has large
measured empty regions, but production owners use explicit reservations and verify them
before writing.

## Address notation

- `17:$5A2C-$6A2B` means switchable ROM bank 17, CPU addresses `$5A2C` through
  `$6A2B`, inclusive.
- For bank `n > 0`, raw file offset is `n * $4000 + address - $4000`.
- Bank 0 uses its CPU address directly.
- Unless stated otherwise, ranges in tables are inclusive.
- “Guarded patch” means only the named installer may replace the range after confirming
  the expected source bytes or digest.

## Cartridge and allocation strategy

The supported ROM is 4 MiB/256 banks, MBC5, CGB-only, with 32 KiB battery RAM. The source
contains 61 completely empty banks. The script allocator deliberately restricts itself to
banks 215-239, a contiguous 25-bank arena whose input contents are verified as empty.

The complete current English script uses banks 215-233:

| Property | Current value |
|---|---:|
| Far-pointer tables | 118 physical tables for 126 logical directory groups |
| Logical references | 7,163 |
| Unique records | 6,695 |
| Pointer bytes | 20,531 |
| Text bytes | 283,941 |
| Total payload | 304,481 bytes |
| Used arena banks | 19 (`215-233`) |
| Unused capacity inside used banks | 6,815 bytes |
| Completely untouched arena banks | 6 (`234-239`) |

Do not allocate a new subsystem in the text arena merely because the current translation
does not fill it. Banks 215-239 belong to `tools/allocate.py` and may be consumed by future
text growth.

## Native and guarded ROM ranges

| Bank | CPU range | Owner / contents | Rule |
|---:|:---|---|---|
| 0 | `$03C9-$046B` | Native actor-record/cache pointer and copy route; actor 0 begins at bank 1 `$D000` and its active cache begins at `$FF90` | Preserved and guarded by `rescue_password.py` for requester fixtures |
| 0 | `$046F-$0484` | Native current-HP subtract/zero route using actor offset `$16` / `$FFA6` | Preserved and guarded by `rescue_password.py` |
| 0 | `$1F8C-$1F8E` | `far_text.py`: source selector call | Guarded patch |
| 0 | `$1FD3-$1FD5` | `far_text.py`: direct selector call | Guarded patch |
| 0 | `$37B9-$37BE` | `dialogue_pacing.py`: explicit-page auto-advance bypass | Guarded patch |
| 0 | `$3FBD-$3FF5` | `far_text.py`: publishing and nonpublishing far selectors | Exclusive verified cave |
| 3 | `$4442-$4841` | Native four-page width table; English advances installed here | `english_font.py` only |
| 3 | `$4842-$5841` | Native one-byte font; Thin Pixel-7 English slots installed here | `english_font.py` only |
| 3 | `$6A49-$6A53` | Shared floor-popup template load hook | `stairs_menu.py` installs the bank-254 base; `service_menus.py` chains through its installed helper |
| 3 | `$6A8F-$6A9F` | Shared floor-popup copy/cleanup hook | `stairs_menu.py` installs the bank-254 base; `service_menus.py` chains through its installed helper |
| 4 | `$4148-$414F` | Status-menu Help-return template redirect | `menu_graphics.py` only |
| 4 | `$4CF6-$4CFD` | Mode-3 Big Moai gift-code input screen redirect | `spell_input.py` only |
| 4 | `$660E-$6787` | 126-entry script group directory | Rewritten only by `insert.py` |
| 5 | `$4553-$459F` | Native `$C3EF-$C3F0` story-stage save/load pair | Preserve; Big Moai availability fixture traces this serializer and loader |
| 5 | `$591D-$5930` | Native event opcode `$60`: branch when `$C3EF` meets its operand threshold | Preserve; Big Moai uses threshold `$09` |
| 6 | `$6268-$626A`, `$7FF4-$7FFF` | Town-refresh call and service-popup cleanup trampoline | `service_menus.py` redirects the native `$69A1` call through guarded bank-254 ninth-column restoration, then resumes `$69A1` |
| 7 | `$4A87-$4B53` | Native actor Max-HP/current-HP accessors; offset `$15` is doubled/halved Max HP and offset `$16` is current HP | Preserved and guarded by `rescue_password.py` |
| 11 | `$518A-$5287` | Loaded-diary Training/SOS/Revival/Thank-You record read/write dispatchers | Preserved and guarded by `rescue_password.py`; records are relative to `$C23C + diary * $6A` |
| 11 | `$42EB-$4301` | Default-name routine | `name6.py` only |
| 11 | `$4B2F-$4B5C` | Compatible player-name getter/setter | `name6.py` only |
| 11 | `$5639-$5654` | Ranking-name load | `name6.py` only |
| 11 | `$56E2-$56FB` | Ranking-name renderer | `name6.py` only |
| 11 | `$5F1C-$5F2E` | Ranking-name write | `name6.py` only |
| 11 | `$5FB3-$5FDC` | Fourteen-entry replay diary pointer table | Preserved byte-exact and guarded by `name6.py`; event IDs 0-3 are non-Secrets demos and 4-13 are Secrets |
| 11 | `$68DE-$68F6` | Status stairs-popup hook | `stairs_menu.py` only |
| 17 | `$76B2-$7D8B` | Native Training/SOS/Revival/Thank-You payload builders, packet codec, checksum, and bit transforms | Preserve while `rescue_password.py` freezes and reproduces the protocol; do not overlay before the two-diary fixture passes |
| 17 | `$792D-$797A` | SOS semantic builder: seed, diary-ID low word, actor position, dungeon, floor, diary record, and bit packing | Preserved and guarded by `rescue_password.py` |
| 17 | `$4747-$474E` | Generated communication-code dynamic-text cache call | `rescue_presentation.py` redirects this call only; native `$C16D` bytes are restored after the localized cache copy |
| 16 | `$68DF-$6953` | Revival decoder success route and immediate Thank-You generator | Preserved and guarded by `rescue_password.py` |
| 16 | `$7B8A-$7BD1` | SOS generation route | Preserved and guarded by `rescue_password.py` |
| 16 | `$464F-$4656` | Status-menu open template redirect | `menu_graphics.py` only |
| 16 | `$4689-$4690` | Status-menu refresh template redirect | `menu_graphics.py` only |
| 16 | `$5B22-$5B29` | Rescue hardware-B native delete far-call wrapper | `rescue_presentation.py` only; calls native bank-18 `$53B0`, then redraws through the localized view only for modes 5-8 with private navigation `$F5` |
| 16 | `$5B66-$5B6D` | Shared graphical-input redirect | `name6.py`, mode-1 `blank_scroll.py`, mode-0 `unidentified_names.py`, then rescue modes 5-8 `rescue_presentation.py`; every layer delegates modes it does not own |
| 16 | `$5B84-$5B8B` | Shared confirmation hook | Mode-1 `blank_scroll.py`, then mode-0 `unidentified_names.py` overlay |
| 16 | `$5F74-$5F99` | Native navigation pointer types `$00-$12` | Preserve; the generic resolver indexes this table as `$5F74 + 2 * type` |
| 16 | `$5F9A-$5F9B` | Native navigation type `$13` pointer to `$6625` | Preserve; shared nine-row list used by Adventure -> Continue/Secrets/Reset/Recap |
| 16 | `$5F9C-$61D2` | Mode-4 name navigation graph | Replaced by `name6.py`; dead node-64 bytes `$615C-$615F` then hold the two private `$C800` graph pointers below |
| 16 | `$615C-$615D` | Private mode-0 navigation pointer `$C800` | `unidentified_names.py` only; overlaps the proven-unreachable Down/Up pair of English name-entry node 64 |
| 16 | `$615E-$615F` | Private rescue navigation pointer `$C800` | `rescue_presentation.py` only; type `$F5`, overlapping the proven-unreachable Left/Right pair of English name-entry node 64 |
| 16 | `$64B9-$6624` | Mode-3 Big Moai gift-code navigation graph | Replaced by `spell_input.py` |
| 16 | `$6625-$6663` | Native nine-node vertical-list graph | Preserve; seven-byte records with fixed x `$36` and y `$17,$22,...,$6F` |
| 16 | `$681B-$6822` | Mode-0 item-name screen redirect | `unidentified_names.py` only |
| 16 | `$68E4-$68EB` | Requester-side mode-7 Revival screen redirect before `$C195` is initialized | `rescue_presentation.py` only; guarded by incoming C and preserves it for the native controller |
| 16 | `$6A33-$6A3A` | Mode-0 history-return screen redirect | `unidentified_names.py` only |
| 16 | `$6A4C-$6A53` | Blank Scroll screen redirect | `blank_scroll.py` only |
| 16 | `$6B98-$6B9F` | Mode-0 secondary screen redirect | `unidentified_names.py` only |
| 16 | `$7A49-$7A50` | Modes 5-8 rescue-password screen redirect before `$C195` is reliable | `rescue_presentation.py` only; guarded by incoming C, publishes that mode, and delegates all other modes to the native bank-244 constructor |
| 16 | `$7859-$7860` | Create-name screen redirect | `name6.py` only |
| 16 | `$78C9-$78D0` | Rename screen redirect | `name6.py` only |
| 17 | `$5A2C-$6A2B` | Shared native Status/template graphics source | Must remain byte-exact |
| 18 | `$4130-$4137` | Status stairs-popup exit cleanup | `stairs_menu.py` only |
| 18 | `$502D-$5072` | Shared graphical-input mode-to-maximum dispatcher; modes 5-8 select 12/9/15/13 password characters | Preserved and guarded; the localized rescue overlay intercepts explicit shared calls without changing this table |
| 18 | `$5310-$5340` | Mode-3 Big Moai gift-code selectable character table | Replaced by `spell_input.py` |
| 78 | `$480B-$480D` | Custom item-name display resolver call | `unidentified_names.py` only |
| 78 | `$7E90-$7E9F` | Far resolver trampoline and preserved-slot wrapper | Exclusive verified cave for `unidentified_names.py` |
| 116 | `$5CEF-$5CF5` | Big Moai event gate: stage `$09` branch or group `$6A` index `$0D` locked dialogue | Preserve and fixture-test; ROM bank `$74` is decimal 116 |
| 120 | `$484A-$484B` | Equipment negative-sign producer | `item_formatting.py` only |
| 120 | `$6474-$647A` | Arrow counter/separator producer | `item_formatting.py` only |
| 120 | `$6889-$688A`, `$6891-$6892` | Pot capacity brackets | `item_formatting.py` only |
| 122 | `$4E10-$4E11`, `$4E20-$4E21`, `$4E33-$4E34` | Staff charge brackets and negative sign | `item_formatting.py` only |
| 122 | `$5EF5-$5EFC` | Blank Scroll candidate-comparison resolver hook | `blank_scroll.py` only |
| 122 | `$6FAD-$6FAF` | Gitan numeric-conversion call redirect | `item_formatting.py` only |
| 122 | `$76C5-$76CB` | Gitan separator wrapper after native code ends at `$76C4` | Exclusive verified cave for `item_formatting.py`; clean tail `$76C5-$7FFF` is zero-filled, but only these seven bytes are owned |
| 208-214 | `$4016-$401A`, `$4066-$4069`, `$6016-$601A`, `$6066-$6069` | Name field and six-character tail/marker in fourteen embedded 106-byte replay diaries | `name6.py` only; all other snapshot bytes remain byte-exact |
| 192-205 | full banks | Original script records and pointer tables | Preserved as source evidence; never use as free space |
| 206 | `$4000-$6A57`, `$6A80-$7BFF` | Prefixed 8x10/16x10 glyph slices | Preserve; `font.py` verifies the clean source digest |
| 206 | `$6A58-$6A7F` | `F2 1E` cracked-Bracelet composite glyph | `item_status.py` replaces only this 40-byte bitmap with `(Cr)`; native width bytes `0F 06` remain unchanged |
| 244 | `$4066-$406D` | Shared graphical-input maximum hook | `name6.py`, then `blank_scroll.py` mode-1 overlay |

The header checksum byte at `$014D` and global checksum at `$014E-$014F` are regenerated
after every ROM writer. They are output metadata, not allocation space.

## Relocated and dedicated high banks

| Bank(s) | CPU range | Owner / contents | Rule |
|---:|:---|:---|:---|
| 215-239 | `$4000-$7FFF` | `allocate.py`/`insert.py`: far tables and relocated records | Script arena only |
| 249 | `$4000-$473F` | `rescue_presentation.py`: bounded native/English output mapping, modes 5-8 input/screen wrappers, requester-side pre-mode Revival constructor, dedicated hardware-B delete wrapper, native/English 64-symbol tables, private 81-node graph, and approved keyboard map | Exclusive; runtime code ends at `$42A1`, graph begins `$4300`, map begins `$4600` |
| 250 | `$4000-$45BF` | `unidentified_names.py`: mode-0 editor overlay, navigation/map resources, safe seven-cell history cycle plus 14-cell translated preview aligned to the native seven-cell origin, canonical-to-free edit reset, canonical-token confirmation, and display resolver | Exclusive |
| 251 | `$4000-$43FF` | `blank_scroll.py`: mode-1 editor, full-name matcher/table, safe native-tail restore, and ID resolver | Exclusive |
| 252 | `$4000-$488F` | `spell_input.py`: mode-3 Big Moai gift-code runtime, map, glyphs | Exclusive |
| 253 | `$4000-$4ACF` | `name6.py`: name/ranking code, map, glyphs | Exclusive |
| 254 | `$4000-$4732` | `stairs_menu.py` base through `$426A`, followed by `service_menus.py` exact Rescue/warehouse/Bank Teller/Blacksmith Info detector, standard/Rescue/Blacksmith seven-interior-tile frames, Blacksmith `Synthesis` suffix staging with Quit-alias clearing and spill-bank synchronization, chained load/copy/controller-exit helpers, active-VRAM-bank bottom-border synchronization, and ninth-column save/restore routines | Shared only by this ordered installer pair; `service_menus.py` must verify the installed stairs helpers before replacing their reserved slots |
| 255 | `$4000-$4A2C` | `menu_graphics.py`: cloned English Status template and loader | Exclusive |

Banks 250-255 were measured empty before these reservations. Their unused tails are not a
general pool; each bank belongs to its subsystem so its installer can reject collisions
deterministically.

## Font ownership

GB2 already has a native proportional renderer. `english_font.py` changes only the
English-owned one-byte code slots and their width entries, using the approved
`assets/fonts/thin_pixel_7_compact.json` source. The prefixed font in bank 206 remains
byte-exact except for the exclusively owned `F2 1E` composite: its Japanese `(hibi)`
bitmap is replaced by the reviewed `(Cr)` raster in
`assets/graphics/item_status_symbols.json`. Its native 15-pixel width metadata and
14-pixel two-slice renderer advance are preserved.

Any font change affects every renderer budget. It therefore requires the complete layout,
runtime-width, menu, build, and emulator matrix—not only a font-region hash update.

## Diary and ranking persistence

The ordinary diary working record is 106 bytes. In its WRAM copy:

| Working address | Diary offset | Meaning |
|:---|---:|---|
| `$C252-$C255` | `$16-$19` | Native four-character player-name prefix |
| `$C2A2-$C2A3` | `$66-$67` | Characters five and six |
| `$C2A4-$C2A5` | `$68-$69` | Expansion marker `A5 5A` |

Those are WRAM addresses for the loaded diary record, not literal SRAM-window addresses.
The native diary save/load path persists the complete record. If the marker is absent,
the compatible getter returns only the native prefix, so Japanese saves require no
migration pass.

Ranking records remain exactly 32 native bytes in their original storage. Their two-byte
name suffixes use otherwise unused SRAM bank 3 space:

| SRAM bank/window | Meaning |
|---|---|
| `3:$BCD8-$BCDB` | Header `N6R1` |
| `3:$BCDC-$BECF` | 5 categories × 50 physical slots × 2 suffix bytes |

The table initializes lazily when its header is absent. Do not grow it into another SRAM
region without proving every native structure and every bank-selection path.

## Unidentified-item naming persistence

The loaded unidentified-item state uses WRAM bank 2:

| Working address | Meaning |
|:---|---|
| `$DC82` | 123 two-byte root mappings: appearance index, custom-name slot |
| `$DD78` | 20 custom-name slots of eight bytes each |
| `$DE1C` | learned-name/history bitset consumed by `FILL IN` |

Free labels remain seven glyph bytes plus `$FF`. A canonical `FILL IN` recall stores
`FF FE <root> FF FF FF FF FF` in the same slot. The bank-250 resolver expands that token
through the translated root-name table, so names such as `Windblade` are not truncated and
the native persistent layout does not grow. See
[UNIDENTIFIED_ITEM_NAMING.md](UNIDENTIFIED_ITEM_NAMING.md).

## Service-popup transient scratch

`service_menus.py` uses WRAM bank 7 `$D8C0-$D8DA` only while a reviewed widened service
popup is live. `$D8C0-$D8D3` packs up to ten original tile/attribute pairs from its added
rightmost BG column; `$D8D4-$D8D5` store the BG destination, `$D8D6` the row count, and
`$D8D7-$D8D8` the two-byte `$A5/$5A` live marker, and `$D8D9-$D8DA` the Blacksmith
suffix tile's VRAM bank and `$A6` marker. The widened frame template ends at
`$D8B3`, so these ranges do not overlap. The two-byte marker prevents uninitialized WRAM
from authorizing a restore. This is transient rendering state, not SRAM and not general
free WRAM.

## Rescue requester live actor state

The requester setup helper changes transient live state only. Actor records are 32 bytes
in WRAM bank 1; actor 0 begins at CPU `$D000` and flat Mesen Work RAM `$1000`. When actor 0
is active, the engine mirrors the complete record at High RAM `$FF90-$FFAF` and stores the
active actor index at `$FFFC`.

| Actor location | Offset | Meaning |
|:---|---:|---|
| bank 1 `$D015` / flat `$1015` / cache `$FFA5` | `$15` | Max HP |
| bank 1 `$D016` / flat `$1016` / cache `$FFA6` | `$16` | Current HP |

`tools/mesen_prepare_rescue_request.lua` refuses to write unless `$FFFC` is actor 0 and
all 32 backing/cache bytes match. It then changes only both current-HP views to 1 and
rolls back if either verified write fails. These addresses are test-fixture ownership,
not free WRAM or a production localization patch.

## Big Moai progression fixture

CPU `$C3EF` is the active story stage and `$C3F0` is the serialized shadow. The supplied
Big Moai state contains `$06 $06`; his event requires stage `$09`. In Mesen's flat Work
RAM domain these are offsets `$03EF-$03F0`. `tools/mesen_unlock_big_moai.lua` owns those
two bytes only during an explicit disposable test and never writes SRAM directly.

Native save/load code persists the pair. In `SaveStates/big-moai-locked.mss`, the two
observed native `cartRam` mirrors contain the pair at flat offsets `$2517-$2518` and
`$4517-$4518`, with checksum `$0C` immediately after each. Those offsets describe this
hash-frozen fixture; they are not a license to edit arbitrary SRAM files. See
[BIG_MOAI.md](BIG_MOAI.md).

## Live dungeon inventory and item formatting

These are transient WRAM structures, not allocation space. The deterministic visual helper
uses only cleared object records in the disposable `Mamel.mss` state and resolves all
twenty targets before writing any of them.

| Flat Mesen Work RAM / CPU view | Meaning |
|:---|---|
| `$12C1-$12D4` / bank 1 `$D2C1-$D2D4` | Twenty inventory object indices |
| `$2482-$2881` / bank 2 `$D482-$D881` | 128 object records of eight bytes |
| `$2C82...` / bank 2 `$DC82...` | Two-byte unidentified/identified root mappings |
| CPU `$C12B` | Live action flags; bit 1 can inhibit ordinary item actions |

Within an eight-byte gallery record, byte 0 is the item ID, byte 1 is the action class,
byte 2 carries arrow/staff/Pot values (or the low numeric/index byte), byte 3 carries signed
equipment modifiers/cracked state (or the high numeric/group byte), and byte 4 carries status
flags. Bytes 5-7 hold synthesis bits for equipment. A capacity-five Pot uses a sparse native
contents list at byte offsets 5, 6, 7, 10, and 11 from the Pot record; every unused cell
must be `$FF`. Because the last two cells cross into the following record, deterministic
helpers must reserve and clear a contiguous runway rather than treating the Pot as one
isolated eight-byte object. Direct injection also bypasses inherent-rune initialization:
an Axe of the Minotaur donor requires weapon rune bit 10 at object byte 6, mask `$04`, not
only item ID `$0B`. Confirmed byte-4 flags are `$02`
cursed, `$04` plated, `$08` blessed, and `$10` equipped. See
[ITEM_FORMATTING.md](ITEM_FORMATTING.md) before extending this fixture.

## Menu navigation runtime state

These addresses are transient runtime state, not free WRAM. The generic bank-16 cursor
machinery consumes seven-byte graph records in the order Down, Up, Left, Right, x, y, and
cursor metadata.

| Address | Meaning | Observed/owned contract |
|:---|---|---|
| `$C14E` | Navigation type | `$13` on Adventure -> Continue; `$F4` only inside the localized mode-0 item-name editor |
| `$C14F` | Current node/selection | Adventure submenu visits `0,1,2,3` for Continue, Secrets, Reset, Recap |
| `$C150` | Previously rendered node | Tracks `$C14F`; used to erase/redraw the cursor safely |
| `$C151` | Maximum selectable index | `3` for the four-row Adventure submenu |
| `$C152` | Graphical-input character position | Separate from menu selection; zero-based input cursor cell |
| `$C153` | Graphical-input maximum | `7` for free unidentified labels and `14` only for canonical preview presentation |
| `$C800-$CA36` | Mode-0 navigation scratch in fixed WRAM bank 0 | 81 records x 7 bytes (`$0237`); uploaded on screen entry and after native `FILL IN` cycling |
| `$FFB2-$FFB3` | Resolved cursor x/y | Adventure row 0 is `$36,$17`; rows 1-3 use y `$22,$2D,$38` |
| `$FE00-$FE03` | First OAM cursor sprite | Diagnostic output, not owned storage; Adventure rows produce OAM y/x `$1F/$3E`, `$2A/$3E`, `$35/$3E`, `$40/$3E` |

The original regression replaced the type `$13` pointer with `$C800`. Outside the input
editor that scratch held `$FF`, so `$FFB2-$FFB3` became `$FF,$FF`; the cursor sprite wrapped
to OAM `$07,$07`, selection stopped advancing, and repeated movement could corrupt the
screen. The production installer now leaves `16:$5F9A` byte-exact as `25 66` and writes
`00 C8` only at the private `$F4` landing pair `16:$615C`.

## Safe allocation procedure

1. Prefer an existing reservation owned by the same subsystem.
2. Search this map, the owning module, and the repository for the proposed bank/address.
3. Prove native semantics; empty-looking bytes are insufficient.
4. Add exact expected-byte or digest guards before replacement.
5. Add an overlap assertion or owned-range report.
6. Add a behavioral regression for the displaced risk.
7. Update this map and run the complete suite plus a real emulator route.

Useful searches include both common address styles:

```sh
rg -n '6A49|0x6A49|\$6A49' tools tests docs README.md
```

If the range cannot be proven safe, leave it untouched.
