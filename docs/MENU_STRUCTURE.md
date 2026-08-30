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
88-pixel budget. Its controller uses native navigation type `$13`, whose pointer at
`16:$5F9A` must remain `$6625`. That graph supplies the nine vertical cursor records used
by this and other ordinary lists; it is not spare input-editor storage. The mode-0
unidentified-item editor instead owns private type `$F4`, resolved through unreachable
name-entry node 64 at `16:$615C` to its WRAM `$C800` graph.

The exact Adventure records are nine seven-byte nodes at `16:$6625-$6663`. Each record is
Down, Up, Left, Right, x, y, and cursor metadata. The four-row submenu uses nodes 0-3 at
x `$36` and y `$17,$22,$2D,$38`; `$C151=3` bounds movement. The resolved coordinates are
published through `$FFB2-$FFB3` before the cursor sprite is emitted. Reading `$FF,$FF`
there is a graph-ownership failure, not a font, label-width, or save-file problem.

The save summary must display the persisted player name dynamically. Never hardcode
`Shiren` into the summary merely because it is the default name.

Title/demo and Secrets playback do not begin with that live diary. Their replay dispatcher
copies one of fourteen embedded 106-byte diary snapshots into the same WRAM record. Events
0-3 are the non-Secrets demo family and events 4-13 are the ten Secrets rows. Those embedded
records require the same six-character prefix/suffix marker as a live save; changing only
the create-name default cannot localize them.

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
| Mode 0 | Unidentified item Name / Fill In | Seven-character free-name field; each `FILL IN` press cycles notebook/history roots into a 14-cell canonical preview aligned to the original field origin; dedicated bank-250 map/navigation; confirmation saves a canonical token that renders the full translated root |
| Mode 3 | Big Moai promotional gift codes ("spells") | Four bytes; A-Z/0-9; dedicated bank-252 map/navigation/runtime; independent of Wanderer Rescue |
| Mode 4 | Player name | Six visible characters; A-Z/a-z/0-9 plus space and editing controls; bank 253 |
| Mode 1 / Blank Scroll | Scroll writing | 11-character presentation field; English shared map with mode-specific hyphen; full-name/history matcher resolves an ID before restoring the native seven-character backend field; bank-251 overlay |
| Modes 5-8 | Wanderer Rescue passwords | 12/9/15/13 native cells; player-name layout without SPACE plus `?`/`!`; private type `$F5` graph in `$C800`; English nodes convert to native six-bit symbols in bank 249 before validation; the common input loop repairs a live rescue editor if it arrived without type `$F5` |

The English build treats these modes as independent consumers even where the native game
shares graphical resources. Each installer owns its map, graph, maximum, and mode-specific
logic. A change to one must prove that the others remain unchanged. In particular, removing
unused player-name controls from mode 4 must not disconnect mode 0's native `FILL IN`
history node.

## Route-to-owner reference

| Area | Primary owner | Focused tests |
|---|---|---|
| Status template and return routes | `menu_graphics.py` | `test_menu_graphics.py`, `test_poc_dungeon1.py` |
| Positioned call graph and budgets | `surfaces.py`, `layout.py` | `test_surfaces.py`, `test_layout.py` |
| Help/Secrets/Notebook content | `menu_text.py` | `test_menu_text.py` |
| Stairs popups and teardown | `stairs_menu.py` | `test_stairs_menu.py` |
| Six-character names, embedded replay diaries, save summary, and Adventure submenu isolation | `name6.py`, `unidentified_names.py` | `test_name6.py`, `test_save_summary.py`, `test_unidentified_names.py` |
| Big Moai gift-code input | `spell_input.py`, `translate_spells.py` | `test_spell_input.py`, `test_translate_spells.py` |
| Blank Scroll writing | `blank_scroll.py` | `test_blank_scroll.py`, `test_mesen_blank_scroll.py` |
| Unidentified item naming | `unidentified_names.py`; manual WRAM helper | `test_unidentified_names.py`, `test_mesen_unidentified_item.py` |
| Wanderer Rescue password input/output | `rescue_presentation.py`, `rescue_password.py` | `test_rescue_password.py`, `test_rescue_presentation.py` |
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
