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
| 0 | `$0044-$0046`, `$004C-$004E`, `$07D9-$081B` | `title_screen.py`: VBlank/STAT gates and displaced title-gradient handler | Exact-byte guarded; private renderer requires scene `$C3B4=$9D` and mode `$C0E5=9`; other routes delegate natively. Preserve shared return `$081C-$081E` |
| 0 | `$0207-$021E` | Original HRAM DMA routine and its initializer | Preserved and hash-guarded by `title_screen.py`; entry `$FF82` accepts source page A, allowing title-only DMA directly from `245:$5000` |
| 0 | `$03C9-$046B` | Native actor-record/cache pointer and copy route; actor 0 begins at bank 1 `$D000` and its active cache begins at `$FF90` | Preserved and guarded by `rescue_password.py` for requester fixtures |
| 0 | `$046F-$0484` | Native current-HP subtract/zero route using actor offset `$16` / `$FFA6` | Preserved and guarded by `rescue_password.py` |
| 0 | `$1F8C-$1F8E` | `far_text.py`: source selector call | Guarded patch |
| 0 | `$1FD3-$1FD5` | `far_text.py`: direct selector call | Guarded patch |
| 0 | `$37B9-$37BE` | `dialogue_pacing.py`: explicit-page auto-advance bypass | Guarded patch |
| 0 | `$3971-$3976`, `$397D-$397E` | `glyph_cell_clip.py`: VWF secondary-tile write gate and aligned-cell bypass | Guards the complete native `$3922-$39E2` compositor; clips only the secondary write at x>=136 and preserves primary-tile rendering |
| 0 | `$355F-$3566`, `$3573-$357A` | True Wanderer and Clear Campaign six-symbol display-generator calls | `rescue_presentation.py` redirects only the two certificate display copies; native `$C16D` values remain unchanged |
| 0 | `$3FBD-$3FF5` | `far_text.py`: publishing and nonpublishing far selectors | Exclusive verified cave |
| 0 | `$3FF6-$3FFB` | `glyph_cell_clip.py`: six-byte right-edge predicate | Exclusive verified remainder of the same bank-0 tail; native table data ends at `$3FBC`, far selectors end at `$3FF5`, and `$3FFC-$3FFF` stays unused |
| 3 | `$4442-$4841` | Native four-page width table; English advances installed here | `english_font.py` only |
| 3 | `$4842-$5841` | Native one-byte font with style-selected Thin Pixel-7 English slots. Its `$5742-$5841` suffix is also the packed top-HUD atlas: `hud_font.py` replaces decimal tiles `$5742-$5791`, label tiles `$57B2-$57E1` (`E/F`, `L/v`, `H/p`, preserving native `E`), and slash tile `$57E2-$57F1`; `$5792-$57B1` (`A-D`) and `$57F2-$5841` (meter/blanks) stay native and are audited read-only | `english_font.py` owns its English slots; `hud_font.py` exclusively owns `$5742-$5791`, `$57B2-$57E1`, and `$57E2-$57F1` |
| 3 | `$6A49-$6A53` | Shared floor-popup template load hook | `stairs_menu.py` installs the bank-254 base; `service_menus.py` chains through its installed helper |
| 3 | `$6A8F-$6A9F` | Shared floor-popup copy/cleanup hook | `stairs_menu.py` installs the bank-254 base; `service_menus.py` chains through its installed helper |
| 4 | `$4148-$414F` | Status-menu Help-return template redirect | `menu_graphics.py` only |
| 4 | `$4CF6-$4CFD` | Mode-3 Big Moai gift-code input screen redirect | `spell_input.py` only |
| 4 | `$660E-$6787` | 126-entry script group directory | Rewritten only by `insert.py` |
| 5 | `$4553-$459F` | Native `$C3EF-$C3F0` story-stage save/load pair | Preserve; Big Moai availability fixture traces this serializer and loader |
| 5 | `$591D-$5930` | Native event opcode `$60`: branch when `$C3EF` meets its operand threshold | Preserve; Big Moai uses threshold `$09` |
| 5 | `$5E13-$5E20` | Native display-mode setter, wrapped by `title_screen.py` | Exact-byte guarded; stage title-only WRAM before mode 9, preserve native BC/DE/HL and mode initialization |
| 6 | `$423D-$4245` | Native fade palette commit, wrapped by `title_screen.py` | Exact-byte guarded; title departure applies the original fade progression to all raster palettes; other scenes delegate to the native writer. The original dispatch table `$426B-$4282` and interpolation `$4334-$4398` remain hash-guarded |
| 24 | `$4000-$4007` | Native map-selector prefix, wrapped by `title_screen.py` | Title moon selectors 0-3 use the private renderer only in the owning scene; other selectors retain the original pointer lookup |
| 25 | `$4000-$400F` | Native object-selector prefix, wrapped by `title_screen.py` | Suppress native title overlays only for selectors 0-2 in the owning scene; preserve generic lookup and `$C445/$C446` results elsewhere |
| 6 | `$6268-$626A`, `$7FF4-$7FFF` | Town-refresh call and service-popup cleanup trampoline | `service_menus.py` redirects the native `$69A1` call through guarded bank-254 ninth-column restoration, then resumes `$69A1` |
| 7 | `$4A87-$4B53` | Native actor Max-HP/current-HP accessors; offset `$15` is doubled/halved Max HP and offset `$16` is current HP | Preserved and guarded by `rescue_password.py` |
| 11 | `$518A-$5287` | Loaded-diary Training/SOS/Revival/Thank-You record read/write dispatchers | Preserved and guarded by `rescue_password.py`; records are relative to `$C23C + diary * $6A` |
| 11 | `$42EB-$4301` | Default-name routine | `name6.py` only |
| 11 | `$4B2F-$4B5C` | Compatible player-name getter/setter | `name6.py` only |
| 11 | `$5639-$5654` | Ranking-name load | `name6.py` only |
| 11 | `$56E2-$56FB` | Ranking-name renderer | `name6.py` only |
| 11 | `$5F1C-$5F2E` | Ranking-name write | `name6.py` only |
| 11 | `$5FB3-$5FDC` | Fourteen-entry replay diary pointer table | Preserved byte-exact and guarded by `name6.py`; event IDs 0-3 are non-Secrets demos and 4-13 are Secrets |
| 11 | `$68DE-$68F6` | Native Status stairs-popup constructor | Guarded byte-exact by `stairs_menu.py`; it must execute in bank 11 so `$68F7/$6967` resolve to the native frame data |
| 17 | `$76B2-$7D8B` | Native Training/SOS/Revival/Thank-You payload builders, packet codec, checksum, and bit transforms | Preserve while `rescue_password.py` freezes and reproduces the protocol; do not overlay before the two-diary fixture passes |
| 17 | `$792D-$797A` | SOS semantic builder: seed, diary-ID low word, actor position, dungeon, floor, diary record, and bit packing | Preserved and guarded by `rescue_password.py` |
| 17 | `$4747-$474E` | Generated communication-code dynamic-text cache call | `rescue_presentation.py` redirects this call only; native `$C16D` bytes are restored after the localized cache copy |
| 17 | `$4309-$430E` | Multiple-item town-shop count suffix | `shop_sale_count.py` terminates the cached decimal value instead of appending Japanese `ko` |
| 17 | `$6F04-$6F15` | Item-action rendered-canvas upload tail | `menu_graphics.py` redirects the guarded native copy through bank 255 so cursor-only alias tiles are cleared before the same `$D240-$D7DF` to `$9240-$97DF` upload |
| 17 | `$71A2` | Sword/shield equipment-preview X origin | `menu_graphics.py` guards both native coordinate stores at `$71A1-$71AA` and changes only x=96 to x=104; the first interior tile stays reserved for cursor cleanup and the remaining 40 px fit both unsigned-byte values plus the arrow |
| 16 | `$68DF-$6953` | Revival decoder success route and immediate Thank-You generator | Preserved and guarded by `rescue_password.py` |
| 16 | `$7B8A-$7BD1` | SOS generation route | Preserved and guarded by `rescue_password.py` |
| 16 | `$464F-$4656` | Status-menu open template redirect | `menu_graphics.py` only |
| 16 | `$4689-$4690` | Status-menu refresh template redirect | `menu_graphics.py` only |
| 16 | `$5AEF-$5AF0` | Shared graphical-input Select event pointer | `name6.py` redirects the Japanese kana modifier to existing idle handler `$5B5B`; guards the complete `$5AE3-$5AF4` event table and idle-handler bytes, preserving every other input event |
| 16 | `$5B22-$5B29` | Graphical-input hardware-B delete far-call wrapper | `unidentified_names.py` first redirects native bank-18 `$53B0` through bank-250 `$45C0`; `rescue_presentation.py` guards that installed call and wraps it with the localized redraw for modes 5-8/private navigation `$F5` |
| 16 | `$5B36-$5B3D` | Graphical-input Start-recall redirect | `blank_scroll.py` installs the bounded mode-1 prefix helper at `251:$4320`; `unidentified_names.py` wraps it for mode-0's 14-cell preview. Other modes delegate to native `18:$5073` |
| 16 | `$5B66-$5B6D` | Shared graphical-input redirect | `name6.py`, mode-1 `blank_scroll.py`, mode-0 `unidentified_names.py`, then rescue modes 5-8 `rescue_presentation.py`; every layer delegates modes it does not own |
| 16 | `$5B84-$5B8B` | Shared confirmation hook | Mode-1 `blank_scroll.py`, then mode-0 `unidentified_names.py` overlay |
| 16 | `$5F74-$5F99` | Native navigation pointer types `$00-$12` | Preserve; the generic resolver indexes this table as `$5F74 + 2 * type` |
| 16 | `$5F9A-$5F9B` | Native navigation type `$13` pointer to `$6625` | Preserve; shared nine-row list used by Adventure -> Continue/Secrets/Reset/Recap |
| 16 | `$5F9C-$61D2` | Mode-4 name navigation graph | Replaced by `name6.py`; dead node-64 bytes `$615C-$6161` then hold the three private `$C800` graph pointers below |
| 16 | `$615C-$615D` | Private mode-0 navigation pointer `$C800` | `unidentified_names.py` only; overlaps the proven-unreachable Down/Up pair of English name-entry node 64 |
| 16 | `$615E-$615F` | Private rescue navigation pointer `$C800` | `rescue_presentation.py` only; type `$F5`, overlapping the proven-unreachable Left/Right pair of English name-entry node 64 |
| 16 | `$6160-$6161` | Private mode-2 Rankings-note navigation pointer `$C800` | `name6.py` only; type `$F6`, overlapping the proven-unreachable x/y pair of English name-entry node 64 |
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
| 16 | `$7BD4-$7BDB` | Mode-2 death-Rankings note screen redirect | `name6.py` only; preserves the native 13-character field/backend and replaces only the keyboard presentation |
| 17 | `$5A2C-$6A2B` | Shared native Status/template graphics source | Must remain byte-exact |
| 18 | `$4130-$4137` | Shared popup exit-dispatch base | `stairs_menu.py` installs the compatibility shim; `service_menus.py` chains its guarded cleanup through it |
| 18 | `$502D-$5072` | Shared graphical-input mode-to-maximum dispatcher; modes 5-8 select 12/9/15/13 password characters | Preserved and guarded; the localized rescue overlay intercepts explicit shared calls without changing this table |
| 18 | `$5310-$5340` | Mode-3 Big Moai gift-code selectable character table | Replaced by `spell_input.py` |
| 78 | `$480B-$480D` | Custom item-name display resolver call | `unidentified_names.py` only |
| 78 | `$7E90-$7E9F` | Far resolver trampoline and preserved-slot wrapper | Exclusive verified cave for `unidentified_names.py` |
| 86 | `$7A80-$7B7F`, `$7C80-$7D7F` | Approved `Please` / `wait...` save/load sign blocks | `wait_screen.py` only; exact-hash guard both 256-byte sign blocks and preserve the interleaved bird blocks byte-for-byte |
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
| 243 | `$5F00-$60FF`, `$6300-$64FF` | Approved `CHUNSOFT` and `Koichi Sugiyama` credit-card strips | `credit_screen.py` only; exact-hash guard both 512-byte native strips and preserve the rest of `F3:$5D00-$64FF` |
| 244 | `$4066-$406D` | Shared graphical-input maximum hook | `name6.py`, then `blank_scroll.py` mode-1 overlay |

## Audited native graphical-text resources

These are native source contracts, not free space. They are emitted by `graphics_audit.py`
and explained in [GRAPHICS_AUDIT.md](GRAPHICS_AUDIT.md). The rules below identify installed
replacements and preserved native evidence. Any later graphics installer must exact-byte
guard or clone every affected resource and account for the recorded aliases before changing it.

| Bank | CPU range | Native contents | Audit rule |
|---:|:---|---|---|
| 0 | `$3CD3-$3CD5`, `$3E0B-$3E0D` | Title selector-0 and credit selector-104 tilemap descriptors | `title_screen.py` redirects only title selector 0 to `246:$6000`; credit descriptor remains native |
| 5 | `$6F35-$6F37`, `$6FE3-$6FE5` | Title selector-0 and credit selector-58 `$8800` plane pointers | `title_screen.py` redirects only title selector 0 to `246:$4000`; credit pointer remains native |
| 23 | `$416F-$41AE`, `$5D75-$5DB4` | Title BG and OBJ palettes 0-7 | `title_screen.py` exact-byte guards and replaces both complete 64-byte records; bank `$17` is decimal 23 |
| 23 | `$58F6-$592D` | Credit base palettes 0-6 | Preserve native palette/fade behavior |
| 24 | `$4014-$4243` | Native map-selector table and four moon maps | Read-only source/hash guard for `title_screen.py`; preserve all native selectors |
| 25 | `$4025-$4224`, `$4260-$4418` | Native object-selector table, bat descriptors, and static castle overlays | Read-only source/hash guards for `title_screen.py`; preserve native motion and generic selectors |
| 28 | `$4000-$5421` | Title `$8800` plane header/data split across CGB VRAM banks 1 and 0 | Preserved and hash-guarded as native composition evidence; replacement stored in bank 246 |
| 45 | `$4F12-$5583` | Credit-transition/backing `$8800` plane header/data | Preserve; live tracing proves this is not the stable visible name plane |
| 49 | `$4000-$4B01` | Title `$8000` plane header/data split across CGB VRAM banks 1 and 0 | Preserved and hash-guarded as native bat/overlay evidence; replacement stored in bank 247 |
| 54 | `$614A-$626B` | Credit-transition/backing `$8000` plane header/data | Preserve both aliased selectors 57 and 58; not the stable visible name plane |
| 56 | `$4000-$42D1` | Title 20x18 interleaved tile/attribute map | Preserved and hash-guarded as native composition evidence; replacement stored in bank 246 |
| 59 | `$7980-$7E81` | Credit-transition 20x32 interleaved tile/attribute map | Selector 104; preserve transition rows |
| 63 | `$4017-$4019`, `$40C2-$40C7` | Title selector-0 and aliased credit selectors 57/58 `$8000` plane pointers | `title_screen.py` redirects only title selector 0 to `247:$4000`; preserve both credit aliases |
| 86 | `$7A80-$7E7F` | Save/load wait sign and interleaved bird art | `wait_screen.py` owns only `$7A80-$7B7F` and `$7C80-$7D7F`; preserve both intervening bird blocks |
| 127 | `$4000-$62EE` | Native arrival-card renderer, 128-block atlas, palette constants, 32-pointer table, and 31 unique sequences | `arrival_cards.py` guards the family and replaces only `$4000-$4008` with a far-call wrapper; native assets remain source evidence |
| 240 | `$4057-$409E`, `$40EF-$40F1`, `$410A` | Visible credit map generator, selector-24 pointer, and eight-page length | `ending_credits.py` changes only `$4067-$4068` from `ld d,$80` to `ld d,$F0`, reserving tile `$F0`—verified black across every affected opening and ending plane—for outer map cells; all other bytes are preserved |
| 240 | `$410B-$490A` | Main-ending staff-title card, raw row-major 2bpp plane | `ending_credits.py` exact-hash guards and replaces the localized title plane |
| 240 | `$490B-$7B0A` | Main-ending staff cards 1-6, raw row-major 2bpp planes | `ending_credits.py` exact-hash guards and replaces the six planes only |
| 241 | `$4000-$7FFF` | Main-ending staff cards 7-11, raw row-major 2bpp planes | `ending_credits.py` exact-hash guards and replaces the five planes only |
| 242 | `$4000-$7EFF` | Main-ending staff cards 12-18, raw row-major 2bpp planes | `ending_credits.py` exact-hash guards and replaces the seven planes only |
| 243 | `$4000-$55FF` | Main-ending staff cards 19-20, raw row-major 2bpp planes | `ending_credits.py` exact-hash guards and replaces the two planes only; Japanese end mark `$5600-$58FF` remains native |
| 240 | `$409F-$40A6` | Credit-card BG palette-0 transition override | Preserve native fade behavior |
| 243 | `$5D00-$64FF` | Visible credit foreground copied verbatim to VRAM bank 1 `$8800-$8FFF` | `credit_screen.py` owns only the two ranges listed above; both copyright rows and all other bytes remain native |

The header checksum byte at `$014D` and global checksum at `$014E-$014F` are regenerated
after every ROM writer. They are output metadata, not allocation space.

## Relocated and dedicated high banks

| Bank(s) | CPU range | Owner / contents | Rule |
|---:|:---|:---|:---|
| 215-239 | `$4000-$7FFF` | `allocate.py`/`insert.py`: far tables and relocated records | Script arena only |
| 245 | `$4000-$7FFF` | `title_screen.py`: title renderer, independent animation clocks, OAM reuse, palette/attribute bands, original-selector mirrors, and staged sky handler | Exclusive full-bank zero/collision guard; runtime/data locations detailed in `title_screen_runtime.py` |
| 246 | `$4000-$7FFF` | `title_screen.py`: localized BG plane at `$4000`, title map at `$6000` | Exclusive full-bank zero/collision guard; native loader header `$1FF0` preserves its two-VRAM-bank contract |
| 247 | `$4000-$7FFF` | `title_screen.py`: localized correction/shine OBJ plane and preserved native bat tiles at `$4000`; complete RGB555 fade tables at `$5400-$74D3`, palette uploader at `$7600` | Exclusive full-bank zero/collision guard |
| 248 | `$4000-$7FFF` | `arrival_cards.py`: cloned native renderer, palette constants, 32-pointer table, 30 unique English sequences, ten byte-exact native Latin digit blocks, one native-derived `F` raised by the approved one pixel, and 206 approved label blocks | Exclusive exact-zero-guarded bank; used data ends at `$797F` |
| 249 | `$4000-$473F` | `rescue_presentation.py`: bounded native/English output mapping, Clear Campaign and True Wanderer display-only wrappers, modes 5-8 input/screen wrappers, requester-side pre-mode Revival constructor, dedicated hardware-B delete wrapper, native/English 64-symbol tables, private 81-node graph, and approved keyboard map | Exclusive; runtime code ends at `$42D3`, graph begins `$4300`, map begins `$4600` |
| 250 | `$4000-$45FF` | `unidentified_names.py`: mode-0 editor overlay, navigation/map resources, safe seven-cell history cycle plus 14-cell translated preview aligned to the native seven-cell origin, canonical-to-free edit reset, canonical-token confirmation, and display resolver; `$45C0-$45FF` owns the hardware-B reset helper | Exclusive |
| 251 | `$4000-$43FF` | `blank_scroll.py`: mode-1 editor, full-name matcher/table, safe native-tail restore, ID resolver, and bounded Start autocomplete at `$4320` | Exclusive |
| 252 | `$4000-$488F` | `spell_input.py`: mode-3 Big Moai gift-code runtime, map, and private style-selected glyph atlas | Exclusive |
| 253 | `$4000-$4D3F` | `name6.py`: player-name/ranking-suffix code, mode-2 Rankings-note presentation and private graph, shared map, and style-selected graphical-input glyph atlas | Exclusive; mode-2 graph begins at `$4B00` |
| 254 | `$4000-$49C1` | `stairs_menu.py` base through `$42AA`, including the exact two-record detector, eight-column dungeon frame, five-cell underlay save/restore, native-template clone, and controller-exit cleanup; followed by `service_menus.py` exact Rescue/warehouse/Bank Teller/Blacksmith Info/Training detector, seven-interior-tile frames, suffix staging, chained helpers, and ninth-column save/restore routines | Shared only by this ordered installer pair; `service_menus.py` must verify the installed stairs helpers before replacing their reserved slots |
| 254 | `$5000-$7EFF` | `debug_menus.py`: main/category/Weapons-Shields/Bracelets-Grass/Scrolls-Staves/Pots-Arrows/all-three-Meat-pages/Set-Flag controller and constructor clones, exact gates, saved-background helpers, cached cursor navigation, private map copier, separate artwork for 9×7, 13×11, 8×9, 10×7, 7×5, 11×11 and 13×9 frames | Normal-build owner, retaining the accepted prototype's exact reservation and runtime. Native-dependency and exact-zero guards. `$49C2-$4FFF` separates it from the other popup helpers; packed Set Flag artwork ends at `$7EF5` |
| 255 | `$4000-$4A7C`, `$4B00-$4B38` | `menu_graphics.py`: English Status bitmap overlay generated from the installed two-tone font, plus the item-action cursor-column cleanup/upload wrapper | Exclusive; `$4A7D-$4AFF` remains unused separation between the two guarded payloads |

Banks 245-255 were measured empty before these reservations. Their unused tails are not a
general pool; each bank belongs to its subsystem so its installer can reject collisions
deterministically.

The normal-build debug installer also owns **5:`$58E6-$58ED`**, replacing the
event-choice call to 18:`$401D` with its exact gate. It copies the reviewed production
18:`$4000-$4139` controller to 254:`$5000-$5139`; the original controller and its
production exit chain remain intact. Its event identity and first nine exact choice
records occupy `$5140-$51AF`; the tenth record (Set Flag) occupies `$51F0-$51FB`.
Geometry occupies `$51B0-$51E9`, selecting 11×11 for each Meat page and 13×9 for
Set Flag. Assembler assertions keep these neighbors disjoint from the gate at `$5200`.
The other pre-constructor helpers end at `$54F4`,
before the fixed constructor at `$5500`. Only this clone redirects construction, cursor
painting and pre-redraw restoration. The guarded native constructor
3:`$69E9-$6AA4` is copied to 254:`$5500-$55BB`, followed by its 14-byte layout
table at `$55BC-$55C9`. The unchanged NextCell/NextRow map-stepping routines
occupy `$55D0-$55E7`. Its three local table references are relocated, and only its map-display
call is suppressed. Native text, bitmap-cache and template preparation remain;
the original bank-3 routine is unchanged. At 254:`$5600`, it also copies the guarded
16:`$5D1A-$5D6C` input routine, 16:`$5E38-$5E92` cursor-position routine and type-9
navigation graph. Private glyph calls preserve the native bitmap cache using
the compositor's existing `$C4DA` bit-2 upload suppression. Only two cursor BG
cells are changed together during VBlank; the 49-tile artwork is uploaded only
when opening. The private map copier at `$56F7` rechecks LCD access after DI
before writing each tile/attribute pair. These helpers end before category
artwork at `$5800`; main artwork occupies `$5C2E-$5FBB`. Weapons/Shields artwork
occupies `$6000-$639F`, Bracelets/Grass occupies `$6400-$679B`, Scrolls/Staves
occupies `$6800-$6B9F`. The remaining blocks are contiguous: Pots/Arrows
`$6BA0-$6EF5`, Meat page 1 `$6EF6-$72F7`, Meat page 2 `$72F8-$76F9`, Meat page 3
`$76FA-$7AFB`, and Set Flag `$7AFC-$7EF5`. Removing unused padding fits all ten
menus into the unchanged `$5000-$7EFF` reservation. Each block keeps
its 49-tile payload; the final five tile payloads end at `$6EAF`, `$7205`, `$7607`,
`$7A09`, and `$7E0B`, followed by 35, 121, 121, 121 and 117 interleaved frame
cells respectively. The installer verifies the complete controller, constructor,
navigation and cursor routines, the native popup border at 3:`$4AE2-$4AF1`,
layout at 3:`$6AA5-$6AB2`, graph at 16:`$6315-$6337`, event choices at
180:`$4A92-$4BCA`, graph pointer and exact hook operands, approved font glyphs
and advances, and the entire zero-filled reservation. Ordinary translation edits
do not require a new whole-ROM allowlist. The historical `debug_room_prototype.py`
adapter additionally requires one of its two frozen pre-integration ROM hashes.

## Font ownership

GB2 already has a native proportional renderer. `english_font.py` changes only the
English-owned one-byte code slots and their width entries, using the approved
`assets/fonts/thin_pixel_7_compact.json` source. The selectable classic build retains its
black-only source raster. The shadowed build bakes palette-color-2 pixels at `+1,+1`,
redraws the unchanged color-3 source ink on top, and joins the four reviewed disconnected
bottom cutoff pixels one position left. Both use identical advances. The
Status screen's fixed English labels are not runtime strings: `menu_graphics.py` therefore
copies the selected style into its private bitmap overlay. The graphical-input atlas in
bank 253 uses the same selected style for player names, Blank Scroll, unidentified-item
naming, and Rescue passwords. Big Moai's isolated bank-252 editor carries a guarded copy.
Literal ROM-byte regressions freeze both classic and shadowed encodings, while the default
shadowed build retains its live-RGB regression.
The
prefixed font in bank 206 remains
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

## Blank Scroll autocomplete scratch

While the mode-1 editor is active, `blank_scroll.py` uses `$C16D-$C178` for the
eleven-character presentation and terminator, and `$C179-$C184` for a separate
twelve-byte autocomplete prefix. Both fit within the shared `$C16D-$C18C` input
area. Other input modes are mutually exclusive users of this area. Start retains
the prefix for cycling until an edit clears the candidate at `$C196`; the next
Start replaces it. No persistent item or SRAM record grows. The native seven-cell
scratch at `$C18D-$C194` and live mode/cache at `$C195/$C196` are not prefix storage.

## Unidentified-item naming persistence

The loaded unidentified-item state uses WRAM bank 2:

| Working address | Meaning |
|:---|---|
| `$DC82` | 123 two-byte root mappings: appearance index, custom-name slot |
| `$DD78` | 20 custom-name slots of eight bytes each |
| `$DE1C` | learned-name/history bitset consumed by `FILL IN` |

Free labels remain seven glyph bytes plus `$FF`. A canonical `FILL IN` recall stores
`FE FE <root> FF FF FF FF FF` in the same slot. Its occupied first byte prevents the
native allocator from reusing it, and its non-terminating second byte lets the native SRAM
journal preserve the root. Interim `FE FF <root>` and legacy `FF FE <root>` tokens remain
readable when present in live state. The bank-250 resolver expands all three forms through
the translated root-name table, so names such as `Windblade` are not truncated and the
native persistent layout does not grow. See
[UNIDENTIFIED_ITEM_NAMING.md](UNIDENTIFIED_ITEM_NAMING.md).

## Popup transient scratch

WRAM bank 7 `$D800-$D8B3` holds staged popup templates, but the apparent gap after the
largest localized template is not free. An untouched Japanese ROM changes every byte in
`$D8B4-$D8F7` during ordinary dungeon UI activity. Earlier widened-popup code placed live
restore records there; native writes could corrupt an underlay or its marker and later make
cleanup copy a stale window tile back onto the dungeon map.

The popup helpers reserve a slice of WRAM bank 5 `$D9C0-$D9F7`. That slice is clear on
retained gameplay fixtures and controller stress routes that can invoke these popups.
Ending-credit code reuses nine non-marker bytes in the upper slice, but the ending is
mutually exclusive with dungeon popups and leaves the complementary live marker clear.
`service_menus.py` owns `$D9C0-$D9DA`: `$D9C0-$D9D3` packs up to
ten original tile/attribute pairs from the added rightmost BG column, `$D9D4-$D9D5` stores
the BG destination, `$D9D6` the row count, `$D9D7-$D9D8` the `$A5/$5A` live marker, and
`$D9D9-$D9DA` the staged suffix tile's VRAM bank and marker. Destination arithmetic
preserves the current tile-map row while wrapping the low five x bits, then wraps vertical
row traversal between `$9Bxx` and `$98xx`.

`stairs_menu.py` owns the disjoint upper reservation `$D9E0-$D9F7`. `$D9E0-$D9E9` stores
the five tile/attribute pairs covered by the dungeon popup's single added column,
`$D9F4-$D9F5` stores its BG destination, and `$D9F6-$D9F7` holds the complementary
`$53/$AC` live marker. The native-width Status popup never arms this state. Both owners
select bank 5 only around state access and restore the caller's bank. Suffix rendering
explicitly returns to bank 7 before reading or editing the staged frame. This is transient
rendering state, not SRAM and not general free WRAM.

An English save state captured inside an open popup can legitimately retain this
live state. `debug-room.state` freezes an armed stairs marker and the five saved
BG pairs for the added column at `$991B`. Its explicit fixture contract checks
the entire saved payload and state digest, and a live B/cancel regression requires
restoration of both tile and attribute bytes plus marker clearing in both font
builds. The additional ten-free-slot `debug-room.state.state` capture has a
separate frozen contract for its armed column at `$994F`, including exact state
digest and saved payload, and passes the same live restoration check. Every
other archived fixture must still leave that marker unarmed.

The debug-menu installer conditionally borrows WRAM bank 5 **`$DA00-$DB21`**.
This is disjoint from the stairs/service popup state and remains within the previously
traced dungeon-popup gap through `$DBFF`. It is **not declared generally free**:
the exact dungeon event/choice gate additionally requires every borrowed byte to be
zero on entry. An occupied byte selects the original controller without touching the
slice. `$DA00-$DA01` stores the BG destination, `$DA02` the last displayed cursor
selection, and `$DA03` selects category (0), main (1), Weapons/Shields (2),
Bracelets/Grass (3), Scrolls/Staves (4), Pots/Arrows (5), Meat page 1 (6), Meat page 2 (7), Meat page 3 (8) or Set Flag (9) geometry.
Starting at `$DA04`, the main frame saves 63 interleaved tile/attribute pairs,
Weapons/Shields and Scrolls/Staves each save 72 through `$DA93`, Bracelets/Grass
saves 70 through `$DA8F`, Pots/Arrows saves 35 through `$DA49`, all three Meat pages
save 121 through `$DAF5`, Set Flag saves 117 through `$DAED`, and categories
save 143 through `$DB21`. The synchronous wrapper clears the entire borrowed
slice before returning; there is no
persistent marker or SRAM allocation. Tests guard the following 16 bytes, reject
occupied scratch, and compare both full VRAM banks after repeated exits and map wraps.

The debug menus use the existing dungeon popup's VRAM bank-0 **`$8900-$8C0F`**:
48 text/cursor tiles plus the original border tile. It leaves the native bank-7
`$D900-$DC0F` bitmap cache available for restoration before native dungeon redraw,
including all native cursor erase/draw edits during navigation.
The compact static artwork uses 17 of the 48 text/cursor tiles for main and 40 for
categories; unused slots are blank. The saved map is restored before replacing
private artwork with the native cache, preventing visible glyph aliases on exit.
Bank-1 fixed border tiles are only referenced, never rewritten. Normal builds now
include these reservations; integration adds no memory use beyond the accepted
ten-menu prototype.

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

Native save/load code persists the pair. In `SaveStates/big-moai-locked.state`, the two
observed native `cartRam` mirrors contain the pair at flat offsets `$2517-$2518` and
`$4517-$4518`, with checksum `$0C` immediately after each. Those offsets describe this
hash-frozen fixture; they are not a license to edit arbitrary SRAM files. See
[BIG_MOAI.md](BIG_MOAI.md).

## Live dungeon inventory and item formatting

These are transient WRAM structures, not allocation space. The deterministic visual helper
uses only cleared object records in the disposable `Mamel.state` fixture and resolves all
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
| `$C14E` | Navigation type | `$13` on Adventure -> Continue; private `$F4`, `$F5`, and `$F6` select the localized mode-0, Rescue, and Rankings-note graphs respectively |
| `$C14F` | Current node/selection | Adventure submenu visits `0,1,2,3` for Continue, Secrets, Reset, Recap |
| `$C150` | Previously rendered node | Tracks `$C14F`; used to erase/redraw the cursor safely |
| `$C151` | Maximum selectable index | `3` for the four-row Adventure submenu |
| `$C152` | Graphical-input character position | Separate from menu selection; zero-based input cursor cell |
| `$C153` | Graphical-input maximum | `7` for free unidentified labels and `14` only for canonical preview presentation |
| `$C800-$CA36` | Private navigation scratch in fixed WRAM bank 0 | 81 records x 7 bytes (`$0237`); uploaded by localized mode 0, Rescue modes 5-8, or Rankings-note mode 2 while its editor is active |
| `$FFB2-$FFB3` | Resolved cursor x/y | Adventure row 0 is `$36,$17`; rows 1-3 use y `$22,$2D,$38` |
| `$FE00-$FE03` | First OAM cursor sprite | Diagnostic output, not owned storage; Adventure rows produce OAM y/x `$1F/$3E`, `$2A/$3E`, `$35/$3E`, `$40/$3E` |

The original regression replaced the type `$13` pointer with `$C800`. Outside the input
editor that scratch held `$FF`, so `$FFB2-$FFB3` became `$FF,$FF`; the cursor sprite wrapped
to OAM `$07,$07`, selection stopped advancing, and repeated movement could corrupt the
screen. The production installer now leaves `16:$5F9A` byte-exact as `25 66` and writes
`00 C8` only at the private `$F4` landing pair `16:$615C`.

## Title runtime state

`title_screen.py` temporarily aliases part of the navigation scratch while display mode
`$C0E5` is 9 **and** scene `$C3B4` is `$9D`. `$C800-$C805` is an offscreen native map
descriptor, `$C880-$C8DF` stores animation clocks and staged sparkle objects, and
`$C900-$C9DF` holds the fast sky handler with its palette and event tables. Title entry
clears state and reloads that handler before enabling the display mode. Title OAM
`$FE00-$FE9F` is initialized directly from `245:$5000` through native HRAM DMA, followed
by the animated bat records. The engine retains its ordinary `$C000-$C09F` shadow;
the private renderer suppresses its pending `$C0EB` DMA and `$C0EC` subtitle palette
requests only while the title owns the scene.
`$C886/$C887` store pending/applied native fade levels, `$C890-$C8A7` store the
corresponding lower palette bytes, and `$C980-$C9BB` holds the current sky ramp.

Attract startup briefly retains mode 9 after releasing title scratch. The scene check is
therefore required on every title dispatch; this interval uses a ROM-resident native
gradient fallback, and other modes retain native dispatch. Natural attract replay and
return verify scratch release/reinitialization. The localized keyboard later replaces
the buffer with its own navigation graph. These allocations are transient fixed WRAM,
with no SRAM or persistent save changes. See [TITLE_LOCALIZATION.md](TITLE_LOCALIZATION.md).

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
