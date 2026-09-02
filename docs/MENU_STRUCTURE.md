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
regressions. The floor route stores its ten covered BG cells and destination in bank-7
scratch `$D8E0-$D8F7`, beyond every generic/localized popup template and the service-popup
scratch block. Cleanup requires the exact two-byte `$53/$AC` live marker; ordinary popup
staging therefore cannot accidentally authorize a stale stairs restore.

## Service popups

The ordinary bank-3 service-menu frame has five interior tiles, or 40 pixels. That is too
narrow for `Password`, `Withdraw`, `Deposit`, `Balance`, and `Synthesis`.
`tools/service_menus.py` chains after the stairs installer and gives only five exact group-7
selector sequences a seven-tile/56-pixel interior. The selector reserves the first 8 pixels,
leaving 48 pixels for each label:

- Rescue Team: `$80/$07`, `$7F/$07`, `$87/$07` (`Cable`, `Password`, `Quit`);
- completed-rescue delivery: `$80/$07`, `$7F/$07`, `$92/$07`, `$9E/$07`
  (`Cable`, `Password`, `Cancel`, `Later`);
- warehouse: `$85/$07`, `$86/$07`, `$90/$07`, `$87/$07` (`Deposit`, `Withdraw`,
  `Trash`, `Quit`);
- Bank Teller: `$85/$07`, `$93/$07`, `$56/$07`, `$87/$07` (`Deposit`, `Withdraw`,
  `Balance`, `Quit`);
- Blacksmith Info: `$94/$07`, `$95/$07`, `$97/$07`, `$96/$07`, `$87/$07` (`Forge`,
  `Repair`, `Synthesis`, `Remove`, `Quit`).

Every other consumer delegates to the original seven-column frame. This exact-set check
prevents a shared label such as `Quit` from widening unrelated menus. The load and copy
paths make the same decision. Because the native town redraw erases only eight columns,
the service owner saves the added ninth BG column from both CGB VRAM banks before drawing.
The shared controller-exit cleanup restores it for B/A dismissals; a post-town-refresh
cleanup covers transitions such as selecting `Password`. Bank-7 scratch `$D8C0-$D8DA`
holds the packed column, destination, height, two-byte live marker, and Blacksmith
or completed-rescue suffix-tile bank/marker. Warehouse rows cross the BG-map boundary and explicitly wrap
`$9BFF -> $9800`. The Rescue route opens a native Yes/No prompt
immediately before the service popup and can leave the dynamic tiles in VRAM bank 1. The
widened bottom row lies beyond the native renderer's 140-byte attribute footprint, so the
copy helper propagates the active bank bit from `$D803` to its seven horizontal border cells
at `$D8A5,$D8A7,...,$D8B1`. Without that synchronization the labels are readable but the
bottom border renders stale graphics.

The label renderer owns only six sequential dynamic tile IDs per physical row. The seventh
interior map cell cannot use `row_base + 6` indiscriminately: that value aliases the first tile
of another row, so moving the selector can redraw a second cursor on the right. Warehouse
and Bank map every spill cell to reviewed stable tile `$B3`. The three-entry Rescue selector
uses a separate template whose two `Password` spill cells use `$A8/$BA`, exposing the final
`d` column already rendered into rows outside that shorter frame; all its other spill cells
remain `$B3`. The four-entry completed-rescue selector makes those rows visible and cursor-
owned, so it first copies the two suffix fragments to off-frame tiles `$9C/$AE`, blanks
`$A8/$BA`, and references only the staged copies plus `$B3`. Blacksmith Info cannot expose
`Synthesis`'s aliased `$9C` overflow tile directly
because the same tile owns the visible Quit row. Its copy helper stages that suffix in stable
tile `$B3`, blanks `$9C` for unselected Quit, maps every other spill to reviewed blank `$B9`,
and synchronizes every displayed spill attribute to the renderer-selected VRAM bank before
restoring `$B3` on exit. Existing service routes traverse the original four menus, verify
their exact tile IDs and bank bits, and freeze each resulting framebuffer. The completed-
rescue route independently rebuilds the fifth menu from `at-rescue.state`, checks its full
right border in both VRAM banks, overwrites the cursor-owned source tiles after the approved
render, and then uses real Down inputs through all four cursor positions. It requires the
final `d` at every stop, exactly one cursor in the left column, and no graphic in the right
spill column.
Hash-independent pixel assertions check both `Password` paths' complete final `d`, the
complete 45x8 `Synthesis` raster, and blank cells on both sides of unselected `Quit`. The
shared tests also freeze the Yes/No prompt, B-button teardown, and the initial `Password`
selection transition separately. Each cleanup-covered added-column tile and attribute is
compared with its captured pre-popup value; hashes remain secondary presentation fixtures.

The complete native event-choice inventory and current overflow list are maintained in
[MENU_ACTION_AUDIT.md](MENU_ACTION_AUDIT.md). Its ROM scan covers every literal opcode `$1E`
choice record, including menus that do not yet have a convenient save-state route.

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
`Shiren` into the summary merely because it is the default name. Its rescue-state label is
the independent record `193:$70E6`, now `Awaiting Rescue`; the run count is a separate
dynamic field. `tests.test_save_summary` renders the supplied SOS SRAM and freezes the
collision-free combination rather than testing either string in isolation.

Title/demo and Secrets playback do not begin with that live diary. Their replay dispatcher
copies one of fourteen embedded 106-byte diary snapshots into the same WRAM record. Events
0-3 are the non-Secrets demo family and events 4-13 are the ten Secrets rows. Those embedded
records require the same six-character prefix/suffix marker as a live save; changing only
the create-name default cannot localize them.

## Adventure History, rankings, and Grade

Adventure History is a paged 40-row domain selected by progression flags. Rankings use a
32-byte native record plus separately loaded dynamic fields and the two-byte name extension.
Its top row right-aligns the dynamic score before the fixed `G` at x=90 and the dynamic
floor before the fixed `F` at x=137. These are independent fields (`11250G`, `9F`), not
literal translations of the native suffix glyphs.

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
| Mode 2 | Rankings note after death | 13-character native field and storage; dedicated screen call at `16:$7BD4`; approved English name-keyboard map/input in bank 253; private type `$F6` graph in `$C800` makes fourteen blank slots enter spaces, and right at the empty message end pads one space before advancing |
| Mode 3 | Big Moai promotional gift codes ("spells") | Four bytes; A-Z/0-9; dedicated bank-252 map/navigation/runtime; independent of Wanderer Rescue |
| Mode 4 | Player name | Six visible characters; A-Z/a-z/0-9 plus space and editing controls; bank 253 |
| Mode 1 / Blank Scroll | Scroll writing | 11-character presentation field; English shared map with mode-specific hyphen; full-name/history matcher resolves an ID before restoring the native seven-character backend field; bank-251 overlay |
| Modes 5-8 | Wanderer Rescue passwords | 12/9/15/13 native cells; player-name layout without SPACE plus `?`/`!`; private type `$F5` graph in `$C800`; English nodes convert to native six-bit symbols in bank 249 before validation; the dedicated hardware-B deletion call is wrapped so remaining native symbols are redrawn through the English view |

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
| Rescue Team, warehouse, Bank Teller, and Blacksmith Info service popups | `service_menus.py` (chained after `stairs_menu.py`) | `test_service_menus.py` |
| Six-character names, embedded replay diaries, save summary, and Adventure submenu isolation | `name6.py`, `unidentified_names.py` | `test_name6.py`, `test_save_summary.py`, `test_unidentified_names.py` |
| Big Moai gift-code input | `spell_input.py`, `translate_spells.py` | `test_spell_input.py`, `test_translate_spells.py` |
| Blank Scroll writing | `blank_scroll.py` | `test_blank_scroll.py`, `test_pyboy_blank_scroll.py` |
| Unidentified item naming | `unidentified_names.py`; manual WRAM helper | `test_unidentified_names.py`, `test_pyboy_unidentified_item.py` |
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
