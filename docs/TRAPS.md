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

**Failure risk:** mode 3 has a hard four-byte spell contract, mode 4 needs six-character
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

## The save summary name is dynamic

**Tempting assumption:** display `Name: Shiren` because `Shiren` is the localized default.

**Why it fails:** the Japanese screen displays the persisted player name. Hardcoding the
default breaks Rename and every future English name.

**Rule:** translate only the `Name:` label and retain the runtime name producer.

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
