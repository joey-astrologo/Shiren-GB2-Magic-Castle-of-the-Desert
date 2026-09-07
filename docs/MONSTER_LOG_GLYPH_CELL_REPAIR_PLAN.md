# Monster Log glyph-cell repair plan and completion record

## Decision summary

Status: **implemented and live-verified on 2026-09-07**.

GFX-03 required changes to **44 of the 219 stored Monster Notebook descriptions**.
The later combat reproduction also requires the shared compositor repair described below;
the original three-line audit did not cover the bottom of a two-line combat window.

The Monster Log repair is content plus surface-aware validation:

1. teach the shared layout model to report any full-renderer glyph whose fixed eight-pixel
   compositor cell crosses x=144 and to reject crossings into an unowned or persistent row;
2. validate the live Monster Log composition (name, then the two description lines), not
   only each stored description by itself;
3. apply the 44 reviewed description changes below;
4. enforce bottom-row/frame safety for story dialogue, gameplay messages, item
   descriptions, Help, and bounded runtime substitutions, while reporting earlier-row
   crossings for surface-specific review; and
5. add a PyBoy regression based on `SaveStates/monster-logs.mss` for both font variants.

This content repair covers the Monster Log. Production additionally installs
`tools/glyph_cell_clip.py`, which prevents the shared compositor's secondary tile write
from crossing the 144-pixel canvas edge. It repairs the reproduced combat gap without
changing message wording or line breaks. The raw glyph-cell diagnostics remain in place.

The wording below was approved and has been applied to
[`script/en/monsters.tsv`](../script/en/monsters.tsv).

## Combat scope correction and runtime repair

Drinking **Otogirisou** or **Leaping Grass** through the real item menu composes group 11
index 32 (`194:$5679`) into a two-line mode-`$10` window:

```text
Made Otogirisou
into medicine and consumed it.
```

The final period begins at x=139/y=40. Its advance of two pixels fits, but its eight-pixel
cell crosses the canvas by three pixels and erases the first inner bottom-border tile.
The original audit measured gameplay third lines and therefore missed this reachable
second-line bottom. A mode with an unbounded/context-dependent lifetime cannot be declared
safe because `bottom_line_glyph_cell_overflows` returns no bounded-row violations.

The guarded native patch changes the secondary-write gate at `0:$3971` and moves the
aligned-cell bypass to the existing register-restoration path at `$3996`. A six-byte
predicate at `0:$3FF6` identifies the final canvas tile. Primary-tile drawing, interior tile
crossings, font-bank switching, pen movement, and source composition remain native.

`tests/test_glyph_cell_clip.py` reproduces both item-use routes from `SaveStates/Mamel.state`
with a disposable identified-grass inventory. The test failed on all four item/font
combinations before the patch and passes after it, checking the unchanged message,
mode `$10`, period origin, and entire bottom frame over three settled frames. Its separate
pixel-oracle test exercises all 144 origins in five modes, both font styles, and both
native glyph heights/source banks, including destination canaries and bank/stack restoration.

## What is being measured

The Monster Log renders this three-line runtime buffer:

```text
monster name
description line 1
description line 2
```

The VWF pen uses each glyph's variable advance, but the original compositor writes an
eight-pixel cell. The conservative unpatched-footprint rule requires an origin at x=136
or earlier:

```text
glyph origin + 8 <= 144
```

All 44 records below had an unsafe final glyph on description line 2, which is physical
line 3 and can therefore overwrite the first inner bottom-border tile. Some also had an
unsafe glyph on description line 1; that write lands in the next text row and is normally
painted over, but the applied result satisfies the fixed-cell rule on both lines.

Every applied edit below was encoded and measured with the current shadowed and classic font
builds. Each one:

- remains exactly two description lines;
- stays below the source composer's 144-pixel wrap threshold;
- stays within the full renderer's 144-pixel pen limit; and
- keeps every eight-pixel glyph cell inside the 144-pixel canvas.

The “spill” column is the currently predicted and live-confirmed class of bottom-border
damage on physical line 3. Stable record IDs are the authoritative way to locate these
entries; the group/index reference documents their Monster Notebook slot.

## Break moves only (11 records)

These entries can preserve every visible word and punctuation mark. Only `<br>` moves.

| Monster | Record / reference | Before | Applied | Previous line-3 spill |
|---|---|---|---|---:|
| Pop Tank | `200:$50EF` / `29:10` | `Attacks with a huge cannon.<br>A fine old man, inside and out.` | `Attacks with a huge cannon. A<br>fine old man, inside and out.` | 4 px |
| Squid King | `200:$55D3` / `29:46` | `Excels at blinding attacks.<br>A dungeon squid, and delicious!` | `Excels at blinding attacks. A<br>dungeon squid, and delicious!` | 5 px |
| Vampire Baron | `200:$58D7` / `29:68` | `Likes walks and imitation.<br>It likes the monster Bow Boy.` | `Likes walks and imitation. It<br>likes the monster Bow Boy.` | 2 px |
| Ghost Hannya | `200:$5AD8` / `30:5` | `Full of pure resentment.<br>It holds a grudge against all.` | `Full of pure resentment. It<br>holds a grudge against all.` | 1 px |
| Pumphantom | `200:$5B66` / `30:9` | `Delicious when defeated.<br>Rich in vitamins and carotene.` | `Delicious when defeated. Rich<br>in vitamins and carotene.` | 3 px |
| Crash Boar | `200:$5C0F` / `30:14` | `An eternal duelist.<br>The dungeon's wildest bruiser.` | `An eternal duelist. The<br>dungeon's wildest bruiser.` | 2 px |
| Concusschin | `200:$5EB6` / `30:33` | `Looks tasty, but is a bomb.<br>A huge explosion soon follows.` | `Looks tasty, but is a bomb. A<br>huge explosion soon follows.` | 3 px |
| Scold Hermit | `200:$6157` / `30:53` | `Somehow it lectures you.<br>You may kneel down and listen.` | `Somehow it lectures you. You<br>may kneel down and listen.` | 4 px |
| Cave Mamel | `200:$6488` / `31:0` | `A much stronger Mamel.<br>Its tail smells faintly sweet.` | `A much stronger Mamel. Its<br>tail smells faintly sweet.` | 2 px |
| Wrecker Boar | `200:$6642` / `31:14` | `A forbidden lethal weapon.<br>It wounds all that it touches.` | `A forbidden lethal weapon. It<br>wounds all that it touches.` | 3 px |
| Dagyagyagan | `200:$6D53` / `31:69` | `Its two tails can also sing.<br>A popular dungeon songstress.` | `Its two tails can also sing. A<br>popular dungeon songstress.` | 1 px |

## Copy edits (33 records)

These entries could not retain all existing words in exactly two raster-safe lines,
regardless of where `<br>` was placed. The approved edits keep the gameplay fact or joke
while shortening the copy.

| Monster | Record / reference | Before | Applied | Previous line-3 spill |
|---|---|---|---|---:|
| Pumphantasm | `200:$50CD` / `29:9` | `Delicious after you defeat it.<br>Boiled or steamed, still tasty.` | `Delicious once you defeat it.<br>Tasty boiled or steamed.` | 5 px |
| Boy Tank | `200:$5199` / `29:15` | `A kid who shoots Iron Arrows.<br>Stronger, but still only a kid.` | `A kid shooting Iron Arrows.<br>Stronger, but only a kid.` | 3 px |
| Dragon | `200:$51FA` / `29:18` | `Breathes scorching flames.<br>One hit cooks you medium rare.` | `Breathes scorching flames.<br>One hit cooks you rare.` | 5 px |
| Death Reaper | `200:$5240` / `29:20` | `Attacks without expression.<br>Its scythe is a hand-me-down.` | `Attacks without expression.<br>Its scythe is secondhand.` | 2 px |
| Rock Head | `200:$53BD` / `29:31` | `Waits still until you approach.<br>It lives to startle wanderers.` | `Waits until you approach.<br>It loves startling wanderers.` | 4 px |
| Mini Mixer | `200:$54B5` / `29:38` | `Combines two items in its gut.<br>They emerge smelling strange.` | `Mixes two items in its gut.<br>They come out smelling odd.` | 1 px |
| Sheep Priest | `200:$5543` / `29:42` | `Halves your attack power.<br>Still misses its old love Mary.` | `Halves your attack power.<br>Still misses dear old Mary.` | 5 px |
| Dark Slasher | `200:$56A0` / `29:52` | `Staves do not work on it.<br>Find another way to defeat it.` | `Staves do not work on it.<br>Find some other way to win.` | 4 px |
| Dozy Genie | `200:$56E6` / `29:54` | `As its name says, it may nap.<br>You cannot help caring for it.` | `As its name says, it may nap.<br>You cannot help but care.` | 2 px |
| Jungarian | `200:$5730` / `29:56` | `Takes your item and throws it.<br>Even that cute face throws it.` | `Takes an item and throws it.<br>Even that cute face hurls it.` | 5 px |
| Morabi | `200:$579B` / `29:59` | `Its halfhearted kicks annoy<br>absolutely everyone around it.` | `Its halfhearted kicks annoy<br>everyone around it.` | 3 px |
| Chintala | `200:$5825` / `29:63` | `Second in monster popularity.<br>It may be the tastiest of all.` | `Second in monster popularity.<br>It may be the tastiest one.` | 2 px |
| Grampa Tank | `200:$5B89` / `30:10` | `An old man beyond stubborn.<br>His obstinacy is electrifying.` | `An old man beyond stubborn.<br>His stubbornness is electric.` | 1 px |
| Mini Tank | `200:$5C2D` / `30:15` | `Shoots Silver Arrows at you.<br>Stronger, yet still only a kid.` | `Shoots Silver Arrows at you.<br>Stronger, but only a kid.` | 3 px |
| Groggy Genie | `200:$6178` / `30:54` | `As its name says, it may nap.<br>You may want to nap beside it.` | `As its name says, it may nap.<br>You may nap right beside it.` | 4 px |
| Pot Angler | `200:$619B` / `30:55` | `Steals a Pot and runs away.<br>Its cunning erodes your trust.` | `Steals a Pot and runs away.<br>Its tricks erode your trust.` | 5 px |
| Killer Gyaza | `200:$61E2` / `30:57` | `Painful, scary, and ruinous.<br>Crab grill, hot pot, crab rice.` | `Painful, scary, and ruinous.<br>Crab grill, hot pot, rice.` | 2 px |
| Vampire Duke | `200:$6334` / `30:68` | `Reads books and copies others.<br>Its favorite is Healer Rabbit.` | `Reads books to copy others.<br>It favors Healer Rabbit.` | 4 px |
| Tunnel Dragon | `200:$6570` / `31:8` | `Its body makes you wonder.<br>Maybe it lazes around at home.` | `Its body makes you wonder.<br>Maybe it lazes at home.` | 4 px |
| Ooze | `200:$666E` / `31:16` | `Stench beyond natural limits?!<br>It shows how precious life is.` | `Stench beyond all limits?!<br>It makes you cherish life.` | 3 px |
| Gulp Leech | `200:$67CB` / `31:26` | `Gulp Leech drains Strength.<br>Its drinking makes you writhe.` | `Gulp Leech drains Strength.<br>It drinks, and you writhe.` | 5 px |
| Mirage Devil | `200:$680E` / `31:28` | `Reflects staff effects wildly.<br>It is best not to use a staff.` | `Reflects staff effects.<br>Do not use a staff on it.` | 2 px |
| Demon Rock | `200:$687A` / `31:31` | `Waits still until you approach.<br>Sometimes it really is asleep.` | `Waits until you approach.<br>Sometimes it truly is asleep.` | 2 px |
| Fulminachin | `200:$68C1` / `31:33` | `Looks tempting, but is a bomb.<br>A colossal blast soon follows.` | `Tempting, but it is a bomb.<br>A colossal blast follows.` | 2 px |
| Gigahead | `200:$692D` / `31:36` | `Attacks by launching its face.<br>It thinks itself the dandiest.` | `Attacks by hurling its face.<br>It thinks itself quite dandy.` | 2 px |
| Mini Mixergon | `200:$6976` / `31:38` | `Combines four items at once.<br>They emerge smelling of sauce.` | `Combines four items at once.<br>They smell like sauce.` | 5 px |
| Trap Jonin | `200:$69A9` / `31:40` | `Leaves a Trap when defeated.<br>A splendid, dishonorable ninja.` | `Leaves a Trap when defeated.<br>A fine, dishonorable ninja.` | 4 px |
| Gyandora | `200:$6A36` / `31:44` | `Weakens item special powers.<br>It stinks and weakens things...` | `Weakens item special powers.<br>It stinks and weakens items...` | 4 px |
| Slinger Beetle | `200:$6B02` / `31:50` | `Eat its Meat to move Stairs.<br>Make good use of that ability.` | `Eat its Meat to move Stairs.<br>Use that ability wisely.` | 2 px |
| Spry Hermit | `200:$6B6E` / `31:53` | `Somehow it always dodges you.<br>You may want to grab its robe.` | `Somehow, it always dodges.<br>Try grabbing its robe.` | 5 px |
| Hell Gyaza | `200:$6BFF` / `31:57` | `Strong, painful, and enraging.<br>Crab paste, sashimi, porridge.` | `Strong, painful, and enraging.<br>Crab paste, sashimi, congee.` | 1 px |
| Mocker Monkey | `200:$6CA6` / `31:62` | `Monkey ears and tail, as ever.<br>It hates being looked down on.` | `Monkey ears and tail, always.<br>It hates being belittled.` | 4 px |
| Emperor Tusker | `200:$6CEA` / `31:64` | `Uses a Quarter Staff on you.<br>It clings tightly to this role.` | `Uses a Quarter Staff on you.<br>It clings tightly to its role.` | 4 px |

## Implementation and acceptance results

### 1. Make the budget executable

Implemented: glyph-origin tracing in `tools/layout.py` exposes fixed-cell overflow results on
`SourceLayout`. Each result must include the surface, physical row, origin, and spill so a
consumer can distinguish a bottom-frame overwrite from an earlier row that it demonstrably
repaints. A bottom-row source is unsafe if any ordinary glyph has `origin + 8 > 144`, even
when its final VWF pen is legal. Add focused unit cases for a period at x=136 and x=137,
plus a wide final glyph, `<hspace>`, explicit line breaks, and both font variants.

### 2. Validate the real Monster Log buffer

Implemented: `tools/menu_text.py` reads the native two-byte catalog at `11:$7CBD`, resolves
the paired monster name for all **209 visible entries**, and measures
`name<br>line 1<br>line 2` in mode `$02`. The repository contains 219 nonempty stored
descriptions, but ten `Undefined (Bug)` variants are intentionally absent from the native
catalog. The frozen result is zero bottom-line crossings. Twenty-eight earlier-row
crossings remain explicit diagnostics because the following text row repaints their spill;
they are not bottom-frame corruption.

### 3. Apply reviewed copy

Completed after editorial approval: 44 stable IDs were updated in
[`script/en/monsters.tsv`](../script/en/monsters.tsv). Names, monster-meat descriptions,
and unrelated dialogue were not changed. The English linter passes and the translation
and menu-text fixtures contain the resulting hashes and widest record.

### 4. Enforce the dangerous-row rule across other full-renderer consumers

Implemented: a fixed-cell crossing from the last owned text row is now a build failure for story
prose, gameplay-message templates with their bounded runtime values, item descriptions,
Help, and other known full-renderer surfaces. The 647 measured prose third-line instances
and 40 gameplay third-line instances had no crossing, but that finding did not cover
two-line combat windows. Keep raw crossings from other rows in the audit output until the
consumer's lifetime is explicitly modeled. The shared runtime clip now blocks these
secondary writes at the canvas edge regardless of which row owns the frame.

### 5. Prove the visible repair

Completed: `SaveStates/monster-logs.mss` was converted with the existing Mesen-to-PyBoy converter.
The live regression added in `tests/test_monster_log.py` visits:

- Death Reaper (the supplied two-pixel case);
- Jungarian (the supplied five-pixel class); and
- one unaffected control entry.

For classic and shadowed builds, it asserts the entire bottom frame row, exact tilemap and
attribute rows, both VRAM banks, and two additional settled frames.

Acceptance result:

- 44/44 edited records safe under composer, renderer-pen, and fixed-cell checks;
- 209/209 native visible Monster Log compositions have safe bottom rows;
- zero raw crossings on the audited ordinary-dialogue and gameplay **third** rows;
- runtime protection and live border regressions for the reproduced two-line combat window;
- exact bottom-border preservation in the converted-state test; and
- both production font variants build successfully.

## Visual-review unlock helper

[`tools/mesen_unlock_monster_log.lua`](../tools/mesen_unlock_monster_log.lua) enables all
209 entries for one manual-review session. Open Monster Notebook and stay on its graphical
catalog grid before running the helper. It derives the required discovery masks from the
same native catalog contract, ORs them into the transient live WRAM history at bank 2
`$DE48`, preserves pre-existing and reserved bits, verifies each write, and rolls back if
a write cannot be verified. Resume and change pages after running it, returning to the
initial page to refresh that page too. Inspect all eight pages before exiting the Notebook:
exit/re-entry rebuilds this workspace from the save's real encounter history. The helper
does not edit the ROM or battery SRAM.

## Effect on in-game dialogue

The content edits alone repair only the Monster Log because those 44 strings are used
there. The shared validator also rejects raw third-line crossings in ordinary dialogue.
Combat required the additional native clip because its frame can be below line two.
Production now suppresses the offending secondary tile write in the shared compositor,
preserving existing message wording, native wrapping, and all pixels inside x=0..143.
Static diagnostics remain conservative authoring checks; a clipped cell does not prove
that an overlong sentence, visible glyph, or page marker fits its intended surface.
