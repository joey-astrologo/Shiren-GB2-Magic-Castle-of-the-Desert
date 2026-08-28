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
| Total payload | 304,472 bytes |
| Used arena banks | 19 (`215-233`) |
| Unused capacity inside used banks | 6,824 bytes |
| Completely untouched arena banks | 6 (`234-239`) |

Do not allocate a new subsystem in the text arena merely because the current translation
does not fill it. Banks 215-239 belong to `tools/allocate.py` and may be consumed by future
text growth.

## Native and guarded ROM ranges

| Bank | CPU range | Owner / contents | Rule |
|---:|:---|---|---|
| 0 | `$1F8C-$1F8E` | `far_text.py`: source selector call | Guarded patch |
| 0 | `$1FD3-$1FD5` | `far_text.py`: direct selector call | Guarded patch |
| 0 | `$37B9-$37BE` | `dialogue_pacing.py`: explicit-page auto-advance bypass | Guarded patch |
| 0 | `$3FBD-$3FF5` | `far_text.py`: publishing and nonpublishing far selectors | Exclusive verified cave |
| 3 | `$4442-$4841` | Native four-page width table; English advances installed here | `english_font.py` only |
| 3 | `$4842-$5841` | Native one-byte font; Thin Pixel-7 English slots installed here | `english_font.py` only |
| 3 | `$6A49-$6A53` | Floor stairs-popup load hook | `stairs_menu.py` only |
| 3 | `$6A8F-$6A9F` | Floor stairs-popup copy/cleanup hook | `stairs_menu.py` only |
| 4 | `$4148-$414F` | Status-menu Help-return template redirect | `menu_graphics.py` only |
| 4 | `$4CF6-$4CFD` | Mode-3 spell-input screen redirect | `spell_input.py` only |
| 4 | `$660E-$6787` | 126-entry script group directory | Rewritten only by `insert.py` |
| 11 | `$42EB-$4301` | Default-name routine | `name6.py` only |
| 11 | `$4B2F-$4B5C` | Compatible player-name getter/setter | `name6.py` only |
| 11 | `$5639-$5654` | Ranking-name load | `name6.py` only |
| 11 | `$56E2-$56FB` | Ranking-name renderer | `name6.py` only |
| 11 | `$5F1C-$5F2E` | Ranking-name write | `name6.py` only |
| 11 | `$68DE-$68F6` | Status stairs-popup hook | `stairs_menu.py` only |
| 16 | `$464F-$4656` | Status-menu open template redirect | `menu_graphics.py` only |
| 16 | `$4689-$4690` | Status-menu refresh template redirect | `menu_graphics.py` only |
| 16 | `$5B66-$5B6D` | Shared graphical-input redirect | `name6.py`, then `blank_scroll.py` mode-1 overlay |
| 16 | `$5B84-$5B8B` | Blank Scroll full-name confirmation hook | `blank_scroll.py` only |
| 16 | `$5F9C-$61D2` | Mode-4 name navigation graph | Replaced by `name6.py` |
| 16 | `$64B9-$6624` | Mode-3 spell navigation graph | Replaced by `spell_input.py` |
| 16 | `$6A4C-$6A53` | Blank Scroll screen redirect | `blank_scroll.py` only |
| 16 | `$7859-$7860` | Create-name screen redirect | `name6.py` only |
| 16 | `$78C9-$78D0` | Rename screen redirect | `name6.py` only |
| 17 | `$5A2C-$6A2B` | Shared native Status/template graphics source | Must remain byte-exact |
| 18 | `$4130-$4137` | Status stairs-popup exit cleanup | `stairs_menu.py` only |
| 18 | `$5310-$5340` | Mode-3 selectable character table | Replaced by `spell_input.py` |
| 122 | `$5EF5-$5EFC` | Blank Scroll candidate-comparison resolver hook | `blank_scroll.py` only |
| 192-205 | full banks | Original script records and pointer tables | Preserved as source evidence; never use as free space |
| 206 | `$4000-$7BFF` | Three pages of prefixed 8x10/16x10 glyph slices | Preserve; `font.py` verifies digest |
| 244 | `$4066-$406D` | Shared graphical-input maximum hook | `name6.py`, then `blank_scroll.py` mode-1 overlay |

The header checksum byte at `$014D` and global checksum at `$014E-$014F` are regenerated
after every ROM writer. They are output metadata, not allocation space.

## Relocated and dedicated high banks

| Bank(s) | CPU range | Owner / contents | Rule |
|---:|:---|:---|:---|
| 215-239 | `$4000-$7FFF` | `allocate.py`/`insert.py`: far tables and relocated records | Script arena only |
| 251 | `$4000-$43FF` | `blank_scroll.py`: mode-1 editor, full-name matcher/table, safe native-tail restore, and ID resolver | Exclusive |
| 252 | `$4000-$488F` | `spell_input.py`: mode-3 code, map, glyphs | Exclusive |
| 253 | `$4000-$4ACF` | `name6.py`: name/ranking code, map, glyphs | Exclusive |
| 254 | `$4000-$426A` | `stairs_menu.py`: both popup templates and cleanup helpers | Exclusive |
| 255 | `$4000-$4A2C` | `menu_graphics.py`: cloned English Status template and loader | Exclusive |

Banks 251-255 were measured empty before these reservations. Their unused tails are not a
general pool; each bank belongs to its subsystem so its installer can reject collisions
deterministically.

## Font ownership

GB2 already has a native proportional renderer. `english_font.py` changes only the
English-owned one-byte code slots and their width entries, using the approved
`assets/fonts/thin_pixel_7_compact.json` source. The prefixed font in bank 206 is not
rewritten.

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
