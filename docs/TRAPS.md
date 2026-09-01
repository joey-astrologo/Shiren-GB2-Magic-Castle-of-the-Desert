# Traps — mistakes that cost time

This file keeps the tempting assumptions that were disproved during GB2 development. The
goal is not to preserve a session diary; it is to stop the next person repeating a failure.

## Storage length is not display width

**Tempting assumption:** an English description should be shortened because it exceeds the
Japanese byte slot.

**Why it fails:** the production allocator relocates complete records across banks. Original
byte length no longer determines storage capacity, while the visible consumer still has a
real pixel and line budget.

**Rule:** preserve complete natural meaning. Solve storage with allocation; solve layout
with measured wrapping and surface engineering.

## `<page>` does not start a new box

**Tempting assumption:** `<page>` both waits and resets the three-line dialogue surface.

**Failure:** a long English record displayed its intermediate page for almost no readable
time or advanced into a fourth cumulative physical line.

**Measured behavior:** `<page>` waits but keeps the physical pen/line cursor. `<box>` resets
the surface but does not itself guarantee input. `<br>` advances immediately.

**Rule:** use `<page><box>` for a new reader-controlled box. Count lines from one `<box>` to
the next, including lines separated by `<page>`.

## `<cF3>` is not a decorative break

**Tempting assumption:** replace native `<cF3>` controls with authored `<br>` to make every
dynamic item or combat sentence wrap predictably.

**Failure:** short values were forced into awkward fragments and pacing no longer matched
the native conditional path.

**Measured behavior:** `<cF3>` is a composer checkpoint. It is invisible while the expanded
runtime sentence fits and rolls back to a line break only when needed.

**Rule:** preserve a source `<cF3>`. Add another only at a safe English word boundary and
validate the complete runtime domain.

## A control has zero visible spacing

**Tempting assumption:** `?<page>Next` or `!<page>Next` will naturally display a space
after the punctuation.

**Failure:** the words join because the control carries no horizontal whitespace.

**Rule:** write `?<page> Next` or `!<page> Next`. The linter protects question- and
exclamation-mark cases; authors should preserve ordinary English spacing across all
zero-width controls.

## Nested far lookups need two bank-publication contracts

**Tempting assumption:** the source selector and direct selector can share one far-pointer
helper that always publishes the selected bank to `$C4DB`.

**Failure:** a combat damage record performed a nested actor-name lookup. Publishing the
actor bank overwrote the outer message bank, so the composer resumed at the same address in
the wrong bank and eventually executed at `$0000`.

**Rule:** the source selector publishes its record bank; the direct nested selector switches
temporarily without overwriting the outer source bank. Keep both helpers and the saved-Mamel
regression.

## A shared menu template is not safe to edit in place

**Tempting assumption:** replace Japanese labels directly in the native Status graphics
template because all visible routes seem to use it.

**Failure:** after repeated Item Info navigation and Quit, windows/text could inherit the
wrong palette or stale graphical state.

**Rule:** keep the shared native template byte-exact. Build the English clone in bank 255 and
redirect only the owned open, refresh, and Help-return consumers.

## Widening a popup includes teardown

**Tempting assumption:** expanding the stairs box is complete once `Stay Here` fits.

**Failure:** the new right-hand extension remained on the dungeon floor after the popup
closed; the Status version had an independent too-small constructor.

**Rule:** own the constructor and exit cleanup for both floor and Status routes. Regression
tests must open, cancel/confirm, and inspect the restored background.

## The Items corner triangle is a page marker

**Tempting assumption:** a triangle at the upper-right corner after closing an action menu is
a cursor that failed to clear.

**Measured behavior:** a full Items page uses that static triangle to show another page is
available. The action cursor moves independently.

**Rule:** identify the tile's native role and navigation state before patching a visual
artifact.

## Every graphical input mode is separate

**Tempting assumption:** one graphical input layout/controller patch can localize every text
entry screen.

**Failure risk:** mode 3 has a hard four-byte Big Moai promotional gift-code contract,
mode 4 needs six-character
player names, mode 1 Blank Scroll needs its own 11-character full-name field plus a hyphen,
and mode 0 unidentified-item naming needs a seven-character free-name field plus its native
`FILL IN` history node. Reusing the reduced player-name graph disconnected that mode-0
node even though the screen still opened. Raising mode 0's native maximum directly is also
unsafe: its legacy `$C18D` recall copy runs into adjacent live input state. The safe route
cycles the root ID under the seven-cell native contract, then redraws the translated name
in a separate 14-cell presentation field while retaining the native seven-cell horizontal
origin. Letting the expanded capacity drive native centering shifts every recalled name
left. That recalled name is also a distinct state:
typing or `DEL` must atomically rebuild the seven-cell field, redraw once, and restore the
native tail. Treating it as an editable 14-cell free label permits invisible appends,
off-screen cursors, and a trapped delete/confirmation path.

**Rule:** generate and test each input mode independently. Freeze maximums, maps, connected
navigation, history/control reachability, confirmation, return paths, presentation-only
extensions, canonical-preview-to-free-entry transitions, and any persistent encoding
specific to that consumer.

## Big Moai gift codes are not rescue passwords

**Tempting assumption:** internal group 23 is named `password_fragments` by a compact
extraction heuristic, so its 100 four-character values must be a Wanderer Rescue
codebook.

**Why it fails:** group 23 is the runtime comparison table for Big Moai promotional
reward codes, which the game calls "spells." Chunsoft distributed those codes on cards
and in publications. They use graphical-input mode 3 and matching group-13 diagnostic
labels. Wanderer Rescue instead uses modes 5-8, code lengths 12/9/15/13, and the
64-symbol packet codec at `11:$76B2-$7D8B`.

**Rule:** keep the two systems independent. Trace rescue from its mode callers, payload
builders, and validators; never infer protocol ownership from a generated category name.
See [RESCUE_SYSTEM.md](RESCUE_SYSTEM.md).

## A full Big Moai code is already positioned on OK

**Tempting assumption:** after entering the fourth spell character, navigate from that
letter to the visible `OK` control.

**Failure:** mode 3 automatically changes `$C14F` to node `$33` (`OK`) when the four-byte
field fills. The first live `WISH` replay then followed a computed path from `H`, walked
back onto `J`, and replaced the final byte. The editor correctly submitted `WISJ`, so the
native unknown-spell response looked like a translation or comparison failure.

**Rule:** assert buffer `20 12 1C 11 FF`, position 3, and node `$33`, then press A with no
directional input. This is parallel to Rescue's auto-`OK` behavior but uses a different
mode and node. See [BIG_MOAI.md](BIG_MOAI.md).

## Big Moai control cursors use sprite-space Y coordinates

**Failure:** the underline cursor was drawn through `DEL` and `OK` instead of beneath them.

**Cause:** both mode-3 control records used Y `$31` / 49, which corresponds to the label's
tile row after the Game Boy sprite-coordinate bias. Character cells already used the next
working underline baseline.

**Rule:** the English `DEL` and `OK` control records use Y `$39` / 57. Keep their reviewed
X/width triples `(9,57,9)` and `(113,57,10)`, and require separate live framebuffers for
both selected states; keyboard-map presence alone cannot detect cursor overlap.

## Unlock a gated subsystem at its proven branch, not with broad flags

**Tempting assumption:** Big Moai's “not ready” response requires a collection of town,
NPC, or reward flags, so a test helper should copy a later save or set several plausible
bits.

**Measured behavior:** event `74:$5CEF` checks only whether `$C3EF >= $09`; the supplied
state has active/shadow pair `$06/$06`. Native save/load code serializes `$C3EF-$C3F0`
together.

**Rule:** for the disposable fixture, set only `$C3EF-$C3F0` to `$09`, verify both writes,
and leave reward-usage, inventory, and all unrelated story state untouched.

## F8 template selectors are not ordinary English letters

**Tempting assumption:** `<cF8>` is a renderer no-op, so a following lowercase letter can
be encoded through the localized English font like ordinary prose.

**Failure:** event and menu templates consume the following native 0-9/a-z byte run as a
runtime selector before rendering. Big Moai's `<cF8>g` reward-item slot originally encoded
as `F8 10`; the first English encoder changed it to `F8 36`. Fortune Grass entered the
inventory, but the formatter then jumped into graphics data at `03:$4F0E`, freezing the
CPU and audio. A regression that stopped at inventory insertion incorrectly passed.

**Rule:** preserve every F8 selector run byte-for-byte. The English source codec owns this
escape rule, translation lint compares the ordered selector runs, and live tests must prove
the interaction returns to a later stable state—not merely that an intermediate side effect
occurred.

## An apparently unused navigation type may belong to an ordinary menu

**Tempting assumption:** type `$13` in the bank-16 navigation pointer table is unused by
graphical text entry, so its pointer at `16:$5F9A` can be redirected to a private WRAM
keyboard graph.

**Failure:** `$13` is the native nine-row vertical-list type at `16:$6625`. The title-screen
Adventure submenu uses its first four nodes for Continue, Secrets, Reset, and Recap.
Redirecting it to the unidentified-item editor's `$C800` scratch made the resolved cursor
coordinates `$FF,$FF`, hid the cursor, prevented selection from advancing, and allowed
repeated movement to corrupt the screen.

**Rule:** determine pointer-table ownership from live consumers, not subsystem names.
Preserve type `$13`. Mode 0 uses private type `$F4`, whose resolver landing pair is the
Down/Up bytes of proven-unreachable English name-entry node 64 at `16:$615C`. Freeze both
the private editor route and the displaced native-menu route.

## The save summary name is dynamic

**Tempting assumption:** display `Name: Shiren` because `Shiren` is the localized default.

**Why it fails:** the Japanese screen displays the persisted player name. Hardcoding the
default breaks Rename and every future English name.

**Rule:** translate only the `Name:` label and retain the runtime name producer.

The rescue-state summary has the same composition risk: `Awaiting Rescue` and the run
count are separate draws. Measure the combined live screen; do not fold an observed run
number into the translated status record.

## Save states can contain stale popup pixels

A Mesen `.mss` contains already-rendered VRAM. Loading a state captured while a menu was
open does not prove that the current ROM constructor drew those pixels. For popup
regressions, back out and rebuild the menu through controller input before hashing or
inspecting it.

Widened shared popups also require matching teardown. The Rescue Team, warehouse, Bank
Teller, and Blacksmith Info tests
assert the exact selector set, a nine-column top and bottom copy, and every tile/attribute
pair in the added right column while open and after dismissal. Framebuffer hashes remain
secondary checks. Matching only a label, template hash, or later stable screen would miss
both stale-state false positives and the leftover-edge failure.

## Replay characters can come from embedded diary snapshots

**Tempting assumption:** once the create-name default is `Shiren`, every automated demo
and Secrets replay will inherit it.

**Failure:** the replay dispatcher bypasses the create-name routine. Event IDs 0-13 copy
complete 106-byte diary snapshots from banks 208-214 into the ordinary loaded diary, and
each clean snapshot contains the Japanese name `シレン`. Patching only four visible bytes
would also lose the final two English characters; omitting the native terminator risks a
direct consumer reading into the next field.

**Rule:** treat embedded replay saves as persistent-format fixtures. Preserve their size
and every unrelated byte, write `Shir` plus a native terminator in the five-byte name field,
and write `en A5 5A` in the proven diary tail. Freeze the event pointer order, title and
Secrets selectors, every source-record hash, and live getter results from both replay
families.

## A Mesen machine state is not a PyBoy state

**Tempting assumption:** load the `.mss` directly in PyBoy or treat the whole container as an
SRAM file.

**Measured behavior:** Mesen 2 stores named fields. `tools/mesen_state.py` extracts its
`cartRam` member as ordinary 32 KiB battery SRAM; PyBoy then boots the matching ROM with that
save.

**Rule:** extract the named field and assert the intended route after boot. A loadable save
does not prove the actor/screen state is correct.

## Static extraction is not complete route coverage

**Tempting assumption:** 6,695 extracted records and 7,163 verified references prove every
line has been seen in game.

**Why it fails:** selector coverage proves the known graph, not every event-state transition,
optional branch, graphical label, or navigation history.

**Rule:** translation completeness and playtest completeness are separate status fields. Add
a route fixture whenever playtesting reveals a new consumer or transition.

## A green build is not visual acceptance

Exact bytes, safe widths, checksums, and reference resolution can all pass while a palette,
cursor, sprite, clear region, timing interval, or sentence still feels wrong.

**Rule:** inspect player-facing changes in the real emulator route. Preserve a screenshot or
behavioral assertion when the failure is reproducible, but retain human review as a separate
gate.

## A selected-node input test does not cover the physical B handler

**Tempting assumption:** if the on-screen `DEL` node works, the physical B button must use
the same localized input handler.

**Failure:** Rescue hardware B correctly deleted the last native byte but then redrew the
remaining uppercase password symbols through the native lowercase-looking glyph table.
The selected-node overlay never ran. A broad common-loop repair made synthetic state tests
pass while changing unrelated input timing and was the wrong owner.

**Rule:** replay the exact user action through the real menu route and hook the narrowest
native owner. The Rescue test enters `AB`, presses physical B, then requires input position
1, native buffer `30 D5...FF`, and an unchanged uppercase-`A` glyph band. The patch wraps
only bank-16 `$5B22-$5B29`, the native delete far call; the common input loop stays native.

## Graphical-input constructors receive the requested mode in C

**Tempting assumption:** `$C195` is already the requested mode whenever the shared rescue
screen constructor runs, and a save state that happens to contain mode 8 proves it.

**Failure:** both the ordinary Password constructor at bank-16 `$7A49` and requester-side
Revival at `$68E4` receive the requested mode in register C while `$C195` can still contain
the previous editor. The original mode-8 fixture accidentally retained `$08`, so a broken
wrapper passed automation but delegated to the Japanese screen during a normal visit.

**Rule:** trace the owning caller's register and WRAM ordering. Both narrow wrappers accept
only incoming C values 5-8, publish that mode before constructing the English screen, and
preserve C for the native controller. The mode-8 live test deliberately overwrites the
fixture's previous-mode byte with mode 0 before navigating normally; the old implementation
must fail that test. The separate mode-7 route must enter all 15 Revival symbols and reach
both native success and the linked Thank-You Password.

## A full password field is already positioned on OK

**Tempting assumption:** after entering the final password character, a controller replay
must navigate from that character's keyboard node to `OK`.

**Failure:** the native full-field handler automatically changes node `$C14F` to `$4D`
(`OK`). The old rescue replay computed directions from the last character anyway, moved
onto `DEL`, erased the last symbol, and then treated the resulting native response as proof
of submission. The test stayed green while it was not confirming the intended code.

**Rule:** after the final cell is filled, assert the exact input buffer, final position, and
node `$4D`, then press A without directional input. Successful SOS validation must assert
the actual inaccessible-dungeon response; successful Revival validation must assert
`Revival complete!` and the linked generated Thank-You Password.

## A preserved composite glyph may still contain Japanese text

**Tempting assumption:** a named prefixed token is a language-neutral status icon, so
preserving its bitmap is sufficient localization.

**Failure:** `F2 1E` is appended to cracked Bracelets, but its 16x10 stock bitmap spells
Japanese `(hibi)`—`(crack)`—inside parentheses. Beside an English item name it appears to
be a corrupt symbol even though the renderer and bitmap are functioning exactly as written.

**Rule:** preserve the token identity and measured width contract, then inspect the actual
pixels for language content. `item_status.py` exclusively replaces the 40-byte bitmap with
`(Cr)`, retains width bytes `0F 06`, verifies every translated item-name shape with the
14-pixel suffix, and replays the supplied Mesen failure state after a forced redraw.

## A translated item root does not own its complete inventory row

**Tempting assumption:** once every group-4 item name is English, all item-list text is
English and ordinary zero-valued fixtures cover its formatter.

**Failure:** the native arrow path adds the Japanese `hon no` counter, staff and Pot paths
add Japanese corner brackets, negative modifiers use a native punctuation code, and the
Gitan-object path joins the amount directly to the English root. A
fixture whose arrows, charges, and capacities are all zero never executes the visible
branches, so a green base-name test can miss mixed-language or corrupt output.

**Rule:** classify and anchor every native dynamic producer, seed nonzero representative
records, and test combined status flags. `item_formatting.py` localizes the producer bytes;
`tests.test_item_formatting` checks all translated family maxima and freezes both pages of
the live Mesen gallery described in [ITEM_FORMATTING.md](ITEM_FORMATTING.md).

## An equipment item ID does not initialize its inherent synthesis rune

**Tempting assumption:** writing item ID `$0B` and weapon class `$01` creates a complete
Axe of the Minotaur suitable for a Synthesis Pot test.

**Failure:** the object is named and handled as an Axe, but direct WRAM injection bypasses
the native item constructor that seeds inherent rune bits. The Pot accepts the Axe and
consumes it, producing a convincing live route, yet the released Club has no transferred
effect. Testing only the two insertion screens therefore gives a false pass.

**Rule:** a synthetic equipment object must reproduce both its identity and initialized
object state. The Minotaur Axe carries weapon rune bit 10 at object byte 6, mask `$04`.
For a synthesis fixture, break the Pot and assert the released base record contains the
expected rune; do not stop at donor consumption.

## A widened template can extend beyond the native VRAM-bank update

**Tempting assumption:** if a widened popup's tile IDs, dimensions, and BG map are correct,
the native renderer will also prepare every new attribute cell.

**Failure:** the Rescue Team service popup follows a Yes/No prompt that selects dynamic
tile VRAM bank 1. The seven-tile service bottom row sits beyond the native seven-column
template's 140-byte renderer footprint, so its horizontal attributes retained bank 0.
`Cable`, `Password`, and `Quit` rendered, but the bottom border read stale bank-0 tiles and
became a black line with repeated gray blocks. The warehouse route used bank 0 and looked
clean, allowing a single-route test to hide the defect. A separate off-by-one `JR NZ`
initially jumped into the native `LD HL` operand and also corrupted the preceding Yes/No
popup. The first 8 interior pixels are occupied by the selector cursor, so a nominal
48-pixel interior provides only 40 pixels for text and still clips the 42-pixel
`Password`; positioned budgets must begin at the live text origin.

**Rule:** prove every branch target lands on an instruction boundary, and explicitly
propagate renderer-owned state into template cells outside the native footprint. For this
popup, the copy helper takes bit 3 from `$D803` and applies it to
`$D8A5,$D8A7,...,$D8B1`. The Mesen fixture must hash the Yes/No confirmation, the later
Cable/Password/Quit popup, and teardown as three separate states; a stable hash of a
damaged later frame is not a correctness test.

## A BG tile-map row increment is not a linear `$20` past `$9BFF`

**Tempting assumption:** advancing a popup column to its next row is always `address += $20`.

**Failure:** the warehouse added column begins at `$9B90`. Its fourth increment reaches
`$9BF0`; the next logical row is `$9810` because the selected 32x32 BG map wraps at
`$9BFF`. Continuing to `$9C10` writes the other BG map, leaving the top-right border damaged
and preventing the dismissed column from being restored.

**Rule:** model the Game Boy tile map as a 32x32 ring. The service save and restore helpers
explicitly wrap `$9Cxx` back to `$98xx`, and the Mesen route checks every tile and attribute
on both sides of that boundary before and after Deposit.

## A BG tile-map column increment must wrap within the same row

**Tempting assumption:** adding the widened frame's eight-tile offset directly to its
top-left BG-map address always finds the added right column.

**Failure:** after placing items in the warehouse without leaving, the camera positioned
the popup at row 14, x=28. Linear `DE + 8` produced row 15, x=4 (`$99E4`) instead of
wrapping horizontally to row 14, x=4 (`$99C4`). The cleanup guard made the same mistake
when rewinding eight cells and sampling the seventh top-interior cell. It consequently
declared the still-visible frame closed and restored scene tiles over its right border.
Leaving and re-entering changed the camera position, hiding the defect.

**Rule:** preserve address bits 5-9 while wrapping x arithmetic through the low five bits.
The floor-items fixture checks the literal 8x64 right-edge raster through every cursor
position, the live `$99C4` save marker, and exact tile/attribute restoration after closing;
the re-entered state is a clean control. Neither route uses a framebuffer hash.

## A wider row does not create another dynamic tile

**Tempting assumption:** after widening a menu from five to seven interior cells, assigning
`row_base + 0` through `row_base + 6` gives each visible cell independent storage.

**Failure:** the shared service renderer allocates only six sequential dynamic tile IDs per
row. `row_base + 6` is another row's first tile. Selecting Warehouse `Trash`/`Quit` or Rescue
`Quit` therefore redrew that aliased tile as a second cursor at the right edge of an earlier
line, even though the menu geometry and primary cursor were correct.

**Rule:** trace the renderer's dynamic-tile allocation independently from the visible tilemap
width; never assign a seventh sequential ID across all rows. Warehouse and Bank use reviewed
stable tile `$B3` throughout. Blacksmith Info copies the aliased `Synthesis` suffix into
stable `$B3`, clears `$9C` before that aliased tile can appear as an `s` beside Quit, assigns
every spill the active VRAM bank, uses blank `$B9` for the other spills, and restores `$B3`
on exit. The shorter three-entry Rescue frame may expose only `$A8/$BA`, the two aliased
off-screen-row tiles that already contain `Password`'s clipped final column, while keeping
`$B3` elsewhere. The four-entry completed-rescue frame must instead copy those fragments
to off-frame `$9C/$AE`, blank the live `$A8/$BA` cursor aliases, and use only the staged
tiles in its spill column. A live regression must move through every option—not merely open and close
the menu—verify the exact spill-cell tile IDs alongside exact framebuffers, and independently
assert any intended overflow glyph pixels. A stable copied suffix must also be checked at
every cursor position and restored during teardown.
