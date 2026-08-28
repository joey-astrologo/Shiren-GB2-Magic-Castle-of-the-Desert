# Menu systems and display ownership

GB2 does not have one universal “menu renderer.” It combines direct positioned text,
source-composed text, copied graphical templates, tilemap constructors, and several
independent input controllers. This document records the ownership boundaries that matter
when changing menu text, geometry, or navigation.

The executable call-graph inventory is `tools/surfaces.py`; exact translated-family
coverage is checked by `tools/menu_text.py` and the production builder.

## Text APIs

### Source-composed/full renderer

Selector `0:$1F58` resolves a group/index record for the composer at `0:$312B`. Runtime
substitutions expand into WRAM before the full proportional renderer runs. Dialogue,
item-detail pages, and combat messages use mode-specific variants of this path.

### Direct positioned renderer

Selector `0:$1FA0` copies the selected record, including its terminator, into a caller
buffer. Bank-17 wrappers set x/y and call the direct renderer at `3:$5E62`. These rows do
not inherit a general dialogue width; the caller's coordinates and surrounding fields set
the budget.

`surfaces.py` discovers 120 direct-renderer call sites across nine APIs and assigns every
site to a known owner. An unassigned future call site is a failing audit, not a surface to
guess.

## Core in-dungeon Status menu

The native template at `17:$5A2C-$6A2B` is shared by several routes. Editing it in place
caused palette/window contamination after nested Info and Quit navigation, so the English
build deliberately leaves it byte-exact.

`tools/menu_graphics.py` constructs an English clone in bank 255 and redirects exactly
three consumers:

| Consumer | Hook |
|---|---|
| Menu open | `16:$464F` |
| Menu refresh | `16:$4689` |
| Return from Help | `4:$4148` |

The overlay owns `Exp`, `Location`, `Map`, `Hints`, `Quit`, `Atk`, `Strength`, `Def`,
`Fullness`, `Gitan`, the separators, `%`, and `G`. The final `%` and `G` glyphs end exactly
at x=144 and are valid edge fits.

Dynamic item names, experience, location, Ancient Ruins status, numeric fields, and the
character sprite are drawn separately over that template. A template test alone therefore
does not prove the complete Status screen.

## Items and action menus

The Items list, At Feet row, category action boxes, Blank Scroll actions, Pot actions, and
equipped-state actions share labels but not necessarily one constructor. Group 7 indices
1-24 are the complete compact action vocabulary; each is validated inside a 48-pixel
column.

The small triangular marker at the upper right of a full Items page is a native page
indicator. It is not the action-menu cursor left behind. Tests should distinguish a static
page marker from the action cursor's movement before treating it as corruption.

Action labels are ordinary direct text. Item names and suffixes are runtime-composed and
must be checked against item-name domains rather than the literal row alone.

## Help, Hints, Secrets, and Monster Notebook

These families span several pointer groups and include aliases and intentional empty
slots. `tools/menu_text.py` verifies:

- 395 required family records;
- four separately positioned headings;
- intentional aliases and native empty Notebook slots;
- required controls and vertical budgets;
- one- and two-line Monster Notebook geometry.

Returning from a selected Hint reconstructs the Status screen. The bank-255 overlay hook
on the Help-return route is what prevents the menu from reverting to Japanese.

## Stairs popups

There are two visible `Proceed / Stay Here` consumers:

1. the floor popup shown while standing on stairs;
2. the popup opened from the Status menu's Stairs option.

The native interiors are too narrow for `Stay Here`. `tools/stairs_menu.py` builds widened
templates and cleanup helpers in bank 254, patches both constructors, and restores the
correct background on exit. The English interior is 56 pixels from x=8 to x=64; `Proceed`
uses 36 pixels and `Stay Here` 46.

Geometry and teardown are one feature. Widening only the visible box leaves the added
right-hand column behind after dismissal, which is why both routes have explicit exit
regressions.

## Front-end diary hub

GB2 has one native adventure diary, not three independent adventure files. The visible hub
is conditional:

- when no diary exists, `New Game` is enabled;
- when a diary exists, `Adventure` and diary-management routes become available;
- Create, Rename, Delete, Rankings, Wanderer Rank, History, Item Exchange, Secrets, and
  other routes retain independent predicates and handlers.

The compact hub rows start at x=6 and end before x=80, giving a 74-pixel text budget.
Selecting Start Adventure opens a different submenu whose rows start at x=56 and have an
88-pixel budget.

The save summary must display the persisted player name dynamically. Never hardcode
`Shiren` into the summary merely because it is the default name.

## Adventure History, rankings, and Grade

Adventure History is a paged 40-row domain selected by progression flags. Rankings use a
32-byte native record plus separately loaded dynamic fields and the two-byte name extension.

The two adjacent pickers are different systems:

- `4:$4940` is a five-slot ranking-record picker;
- `4:$4972` is a four-category Wanderer Grade picker.

They share a cursor renderer but have different count routines and controller dispatches.
Do not infer one picker's navigation or row count from the other.

## Graphical input modes

The graphical input dispatcher has independent modes and consumers:

| Mode/path | Purpose | Contract |
|---|---|---|
| Mode 3 | Big Moai spells | Four bytes; A-Z/0-9; dedicated bank-252 map/navigation/runtime |
| Mode 4 | Player name | Six visible characters; A-Z/a-z/0-9 plus space and editing controls; bank 253 |
| Mode 1 / Blank Scroll | Scroll writing | 11-character presentation field; English shared map with mode-specific hyphen; full-name/history matcher resolves an ID before restoring the native seven-character backend field; bank-251 overlay |

Mode 3 and mode 4 share native graphical resources as source material, but the English
installers generate separate maps, graphs, glyph copies, and runtime logic. A change to one
must prove that the other remains unchanged.

## Route-to-owner reference

| Area | Primary owner | Focused tests |
|---|---|---|
| Status template and return routes | `menu_graphics.py` | `test_menu_graphics.py`, `test_poc_dungeon1.py` |
| Positioned call graph and budgets | `surfaces.py`, `layout.py` | `test_surfaces.py`, `test_layout.py` |
| Help/Secrets/Notebook content | `menu_text.py` | `test_menu_text.py` |
| Stairs popups and teardown | `stairs_menu.py` | `test_stairs_menu.py` |
| Six-character names and rankings | `name6.py` | `test_name6.py`, `test_save_summary.py` |
| Spell input | `spell_input.py`, `translate_spells.py` | `test_spell_input.py`, `test_translate_spells.py` |
| Blank Scroll writing | `blank_scroll.py` | `test_blank_scroll.py`, `test_mesen_blank_scroll.py` |
| Main-menu proof route | build/surface contracts | `test_poc_dungeon1.py`, `test_build.py` |

## Rules for menu changes

1. Identify the exact constructor, text API, template, controller, and return path.
2. Measure the actual interior after borders, cursor cells, values, and suffixes.
3. Preserve shared native templates unless every consumer is owned; cloning is safer when
   a translated route has different redraw requirements.
4. Test opening, refreshing, backing out, and re-entering after a different nested route.
5. A clean static width is necessary but not sufficient—inspect the real palette, cursor,
   character sprite, and cleared region.
6. Update [ROM_BANK_MAP.md](ROM_BANK_MAP.md) for any new hook or data reservation.
