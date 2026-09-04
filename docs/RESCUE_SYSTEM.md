# Wanderer Rescue password system

GB2's Wanderer Rescue feature is a three-password, two-diary protocol. This document
records the original player flow, confirmed native input contracts, localization design,
manual and automated test strategy, and the reverse-engineering gates that must be passed
before production code changes.

The rescue implementation has a reproduced native protocol and fixture-tested English
input/output layers. The native alphabet, packet codec, SOS fields, Revival/gift
relationship, and Thank-You acknowledgement are reproduced by an automated reference
implementation. The supplied Rankings and SOS captures prove one live requester record,
and the production ROM replays that route with an English code while restoring the native
buffer and preserving the diary record byte-for-byte. The supplied Password-menu capture
also enters a published English SOS code through the localized keyboard and proves its
native bytes before the original validator runs. The complete live two-diary emulator
fixture remains to be implemented.

## Original GB2 flow and availability

The requester does not need to find a late-game Rescue menu. After an eligible dungeon
collapse, the Rankings screen offers `Select -> Await Rescue`. Once accepted, the Adventure
menu enters the waiting state and exposes the SOS data.

The complete password flow is:

1. The requester collapses and chooses **Await Rescue** on the Rankings screen.
2. GB2 produces a 13-character **SOS Password**.
3. A second diary receives that password at the Rescue Team building in Ilpa.
4. The rescuer enters the Rescue Gate, traverses a recreation of the requester's dungeon,
   reaches the collapse floor, and talks to the fallen Shiren.
5. The rescuer returns to Rescue Team headquarters and produces a 15-character
   **Revival Password**. One eight-byte gift item may be included.
6. The requester enters the Revival Password and resumes at the collapse floor with their
   equipment restored.
7. The requester produces a 12-character **Thank-You Password**.
8. The rescuer gives the Thank-You Password to the Pigeon Handler for rescue credit,
   rewards, titles, and history.

Link Cable exchange is an alternative transport for the same feature and must remain
unchanged by password localization.

The original GB2 site describes the post-collapse Rankings route, password/cable exchange,
Ilpa Rescue Team building, recreated rescue dungeon, reward history, and optional gift:

- [Official GB2 Rescue Team page](https://www.spike-chunsoft.co.jp/pages/games/shirengb2/system05.html)

The rescuer must have access to Ilpa and the Rescue Team facility. Native dialogue also
shows two temporary gate states: the receptionist may be absent, or the adjacent
receptionist may still need to unlock the Rescue Gate. There is not yet evidence of a
single late-game global requester unlock. If **Await Rescue** is unavailable after a
collapse, record the dungeon, floor, story state, active theft state, remaining rescues,
and whether the adventure is already a rescue attempt before changing flags.

## Confirmed native input contracts

The shared graphical-input engine stores its current mode at WRAM `$C195`, input position
at `$C152`, maximum length at `$C153`, and active buffer at `$C16D`.

The clean-ROM dispatcher at `12:$502D-$5072` and length table/routine at
`11:$76BE-$76C9` confirm these long-code modes:

| Input mode | Native maximum | Role and evidence |
|---:|---:|---|
| 5 | 12 | Thank-You Password; role inferred from unique protocol length, live capture pending |
| 6 | 9 | Training Dungeon password; role inferred from unique protocol length, live capture pending |
| 7 | 15 | Revival Password; directly selected by `10:$68DF-$68E7` |
| 8 | 13 | SOS Password; live `rescue-entry-menu.state` capture and controller replay confirmed |

Mode 2 is the separate 13-character Rankings-note editor opened with Start on the death
Rankings result. Its dedicated constructor call at `10:$7BD4` uses the approved English
name keyboard through `name6.py`; its native maximum and storage remain independent from
the 13-character SOS route. It selects a private type-`$F6` graph copied to `$C800`, where
fourteen otherwise spare nodes make the first fourteen internal blank cells selectable
space actions. On an empty message cell, the visual right-arrow action inserts one English
space before advancing. Mode 4 player naming retains its original graph and empty-cell
right-arrow no-op.

The packet roles are additionally confirmed by their callers: `10:$7B8A-$7BD1` invokes
type 0 to generate SOS, while `10:$68DF-$6953` explicitly opens mode 7, decodes type 1
Revival, and then generates type 2 Thank-You. Modes 5 and 6 still require live `$C195`
captures before their inferred role names become stage-specific fixture contracts.

## Deterministic requester-state preparation

The committed `SaveStates/Mamel.state` state has actor 0 active, a synchronized 32-byte
actor record/cache, Max HP 40, current HP 40, and a Mamel beside Shiren. Native code proves
the relevant fields rather than relying on state-file correlation:

- `00:$03C9-$046B` maps 32-byte actor records in WRAM bank 1 and mirrors the active actor
  at High RAM `$FF90-$FFAF`;
- `07:$4A87-$4B53` doubles/halves actor offset `$15`, identifying it as Max HP, and owns
  the adjacent current-HP getters/setters at offset `$16`; and
- `00:$046F-$0484` subtracts damage from `$FFA6`, confirming active actor offset `$16` as
  current HP.

Actor 0 begins at bank 1 `$D000` (flat WRAM offset `$1000`). Max HP is bank 1 `$D015`
/ cache `$FFA5`; current HP is bank 1 `$D016` / cache `$FFA6`; `$FFFC` is the active actor
index. `pyboy_fixtures.prepare_rescue_request` compares every backing/cache byte, requires
actor 0, validates `0 < current HP <= Max HP`, and changes only the two current-HP views to
1. Any mismatch or failed verified write aborts or rolls back. No ROM, SRAM, inventory,
Max HP, story flag, or rescue flag is written.

## Important protocol-boundary correction

Group 23 in the extracted internal script contains 100 four-character records beginning
with `ためぜつ`. The compact English overlay currently calls this section
`password_fragments` and translates the records as `S001` through the remaining four-byte
Big Moai promotional gift codes. The game calls these codes "spells"; Chunsoft distributed
codes through cards and publications so players could enter them at Big Moai for rewards.

An initial rescue audit treated that suggestive section name as evidence that these were a
rescue codebook. The stronger local evidence does **not** support that conclusion:

- group 13 contains matching diagnostic records such as `まじない1 ためぜつ`, translated
  as `Spell 1: S001`;
- the project deliberately localizes the 100 runtime records and 100 matching diagnostic
  labels together; and
- graphical input mode 3 is the separately engineered four-character Big Moai promotional
  gift-code editor.

Therefore, do not restore or freeze group 23 as rescue data. It remains owned by the Big
Moai promotional gift-code system unless a direct rescue decoder reference is later
proven. The rescue encoder/decoder must be traced from modes 5-8 and their callers rather
than inferred from an extracted category label. Its independent gate, `WISH` reward route,
and manual fixture are documented in [BIG_MOAI.md](BIG_MOAI.md).

## Password sizes and encoded data

The packet layer at `11:$7B17-$7D8B` and the three rescue-stage semantics are reproduced
by `tools/rescue_password.py`. Before symbol packing, the four payload sizes are:

| Code | Payload bytes | Password characters |
|---|---:|---:|
| Training | 6 | 9 |
| Thank-You | 8 | 12 |
| SOS | 9 | 13 |
| Revival | 10 | 15 |

The native alphabet contains exactly 64 symbols, in six-bit value order:

```text
あいうえおかきくけこさしすせそた
ちつてとなにぬねのはひふへほまみ
むめもやゆよらりるれろわをんがぎ
ぐげござじずぜぞだぢづでどばびぶ
```

The codec bit-transposes long payloads, applies a cumulative-byte transform, emits low and
high six-bit groups, adds a six-bit weighted checksum, and reorders the displayed symbols.
The decoder reverses those operations and rejects a checksum mismatch. This checksum is
not a promise that every possible one-character substitution is detectable; per-stage
field validation is an additional layer still being traced.

The local clean-ROM trace confirms these rescue records:

| Code | Characters | Native semantic payload |
|---|---:|---|
| Training | 9 | Six bytes; external documentation identifies dungeon seed, dungeon ID, and internal floor; the local builder still needs a dedicated trace |
| SOS | 13 | Dungeon seed, requester diary-ID low 16 bits, Shiren X/Y, dungeon ID, internal floor |
| Revival | 15 | Seed-derived mask plus optional eight-byte gift, rescuer diary-ID checksum, and two SOS-record checksums |
| Thank-You | 12 | Gift bytes 0 and 2, rescuer diary checksum, SOS checksums, and complemented seed bytes |

The SOS wire layout is nine bytes. Bytes 0-3 are the little-endian dungeon seed, bytes
4-5 are the requester diary ID's low word, and bytes 6-8 are a little-endian bit stream:
X (5 bits), Y (5), dungeon ID (4), and internal floor (7). The clean builder at
`11:$792D-$797A` first saves an unpacked ten-byte form and then packs those four fields.

The loaded diary table begins at WRAM `$C23C` with `$6A` bytes per diary. The dispatchers
at `0B:$518A-$5287` own these protocol records:

| Stage | Diary offset | Stored bytes |
|---|---:|---:|
| Training | `+$22` | 6 |
| SOS | `+$41` | 10 |
| Revival | `+$4B` | 10 |
| Thank-You | `+$55` | 8 |

The Revival code does not transmit the rescuer's four-byte diary ID literally. It stores
an eight-bit weighted checksum of that ID in wire byte 1. Gift byte 1 is overwritten and
therefore is not transported; the reference decoder canonicalizes it to zero. The
remaining gift bytes, including the item ID, base value, modifier, flags, and seals, are
recovered relative to a mask derived from the SOS dungeon seed.

The gift bytes contain item ID, item type, base and modifier values, status flags, and
three bytes of seal data. Known flags include curse, blessing, plating, and doubled seal
capacity. These fields make item serialization part of the rescue protocol test surface,
not merely an optional menu detail.

- [GB2 password generator and field documentation](https://w.atwiki.jp/sansara_naga2_sfc/pages/145.html)

## Public protocol regression vector

A surviving GB2 rescue board contains a complete real exchange from May 2025:

| Stage | Native password |
|---|---|
| SOS | `そおせばぞづくばりぶかにぎ` |
| Revival | `そかちにざゆねぜねあごせげほれ` |
| Thank-You | `おゆまゆまでわかやれうか` |

These are 13, 15, and 12 characters respectively and form the first external end-to-end
fixture. They must never be rewritten as translation text. The reference implementation
now proves all three relationships:

- SOS decodes to seed `$BC03C8CD`, diary ID low word `$8955`, position `(6,26)`, dungeon
  ID `6`, and internal floor `27`;
- Revival matches the SOS checksums, contains rescuer diary checksum `$A9`, and recovers
  canonical gift bytes `6C 00 00 00 04 00 00 00`; and
- those fields generate the published Thank-You password exactly.

- [Public GB2 SOS, Revival, and Thank-You exchange](https://bbs6.sekkaku.net/bbs/dobuntya/)

## Localization architecture

The architecture preserves the original payload, checksum, code lengths, and
Link Cable data while localizing only password presentation:

1. Prove and retain the native encoder/decoder and native symbol values.
2. Define a one-to-one mapping from every native password symbol to one distinct
   English-font symbol.
3. On output, render the mapped English symbol without changing the encoded payload.
4. On input, make the English keyboard write the corresponding native symbol value.
5. Provide a deterministic Japanese-to-English and English-to-Japanese converter so
   passwords remain shareable with unmodified Japanese copies.

The native domain is proven to contain 64 symbols. The frozen presentation alphabet is
`A-Z`, `a-z`, `0-9`, `?`, and `!`, in that exact order. It is one-to-one and
case-sensitive. `tools/rescue_password.py` performs deterministic conversion in both
directions.

The output hook at `17:$4747` intercepts only the dynamic-text cache call made after the
native generator has filled `$C16D`. Bank 249 maps each symbol to its English-font byte,
caches the localized string, and immediately maps `$C16D` back to native. The loop stops
at `$FF` and is bounded to 15 symbols, so the same path covers Training, SOS, Revival, and
Thank-You without changing their lengths or packet data. The captured SOS
`ぜづれうほまぐうむぜづだじ` therefore displays as `26pCdewCg2640` while its native
buffer remains `6F 73 59 32 4D 4E 69 32 50 6F 73 71 6D FF`.

The input overlay intercepts the shared graphical-input call at `16:$5B66` only when
`$C195` is mode 5, 6, 7, or 8. At both screen-constructor redirects the requested mode is
authoritative in register C; `$C195` may still describe whichever editor ran previously.
The ordinary wrapper at `16:$7A49` guards incoming C, publishes it to `$C195`, and reuses
the approved player-name keyboard resources. Requester-side Revival is a distinct native
path: `16:$68E4` invokes the screen constructor while mode 7 is still only in register C.
Its guarded wrapper follows the same rule and preserves C for the native controller.
Both routes remove `SPACE`, add `?` and `!`, copy a dedicated 81-node navigation graph to
WRAM `$C800`, and select private type `$F5`. Visible nodes
follow the same three-column layout as name entry; `OK`, left/right cursor controls, and
`DEL` retain their native actions. Character nodes 0-63 write the corresponding native
password byte from the frozen six-bit table. Screen refresh temporarily maps `$C16D` to
English and restores it immediately. Confirmation delegates directly to the native route
without another presentation conversion because the decoder may use the buffer as scratch.

Codes should be grouped visually while spaces remain presentation-only:

- SOS: `XXXX XXXX XXXX X`
- Revival: `XXXX XXXX XXXX XXX`
- Thank-You: `XXXX XXXX XXXX`

The established English labels are **SOS Password**, **Revival Password**, and
**Thank-You Password**. Any graphical Japanese header, controls, cursor routes, error
messages, and return paths must be localized and fixture-tested with their owning screen.

## Comparison with later games

GB2 has no official Internet service. Its compact offline codes were intended to be shared
through a cable, phone, email, fax, or community board.

Shiren 5 retains the request/rescue/revival/thank-you sequence, but offers server requests,
a 12-digit online rescue number, and a 54-character offline password. Shiren 6 uses an
online Rescue Board, a shareable Rescue ID, and Rescue Self while retaining replicated
dungeons and up to three requests per adventure.

- [Shiren 5 Wanderer Rescue](https://sharksnack.github.io/shiren-5/system/wanderer-rescue/)
- [Official Shiren 6 Rescue system](https://www.spike-chunsoft.co.jp/pages/shiren6/en/system/)

The GB2 localization should preserve its compact offline character rather than imitate a
server. Modern expectations should inform readability, grouping, clear stage labels,
retry behavior, and compatibility tooling.

## Automated test plan

### Protocol discovery and static fixtures

- Freeze the clean-ROM mode-length dispatcher and long-code length table.
- Capture each live rescue screen's mode, buffer, maximum, character table, navigation
  type, renderer, confirmation routine, and error return. Mode 8 is frozen; modes 5-7
  still need stage-specific live captures even though the shared overlay covers them.
- The native 64-symbol domain, frozen English mapping, packet lengths, codec, checksum, mode dispatcher, diary
  records, stage callers, and three public vectors are frozen in
  `tests/fixtures/rescue_password.json`.
- The SOS builder, three rescue-stage relationships, loaded-diary records, and optional
  gift boundary are frozen. Complete the Training builder trace and live SRAM locations.
- Capture modes 5-7 live and prove their stage-specific callers use the shared alphabet.
- Add semantic malformed-field fixtures after the stage validators are reproduced.

### Encoder/decoder behavior

- Round-trip boundary and randomized payloads for every code type.
- Validate the native checksum and catalogue substitutions it cannot detect by itself.
- Reject semantically invalid and wrong-stage codes without damaging game state.
- Verify seed, diary IDs, coordinates, dungeon ID, and floor exactly.
- Cover no gift plus item-family, upgrade, curse, blessing, plating, and seal combinations.
- Confirm English/native symbol mapping is bijective and case-sensitive where applicable.

### Emulator fixtures

Use two disposable one-adventure SRAM profiles:

- `rescue-requester.srm`
- `rescue-rescuer.srm`

Create reviewed save states at:

1. the requester immediately before an eligible collapse;
2. Rankings with **Await Rescue** available;
3. waiting state and SOS display;
4. rescuer at SOS input;
5. rescuer beside the fallen Shiren;
6. Revival Password generation and optional gift selection;
7. requester at Revival input and resumed floor; and
8. Thank-You display and Pigeon Handler input.

The automated route starts with `pyboy_fixtures.prepare_rescue_request` and
`SaveStates/Mamel.state`. Its PyBoy regression requires both current-HP views to become 1,
Max HP to remain 40, and active actor 0 to remain selected. The reviewed requester captures
are `SaveStates/rescue-requester-rankings.state` (SHA-1
`fa7097cb14db7c7b668923b562f7388a3114b999`) and
`SaveStates/rescue-requester-sos.state` (SHA-1
`2937fd35b62e8d9cd72fdc3a0f439235dc672458`). `tests.test_rescue_presentation`
replays `Select`, the explanation, confirmation, and generation. The two-row question and
native third-row Yes/No cursor are frozen at screen checksum `$17D77035`; the route then
freezes English SOS checksum `$7F6D7FB9`, restored native `$C16D`, and the ten-byte SOS
diary record. The SOS SRAM also drives the title-screen save-summary regression, where
`Awaiting Rescue` must remain separate from the dynamic run count.

`SaveStates/rescue-entry-menu.state` (SHA-1
`8c79794a9ae28857dd51ebe343191e1796007164`) starts with Password selected in the Rescue
Team Cable / Password / Quit menu. `tests.test_rescue_presentation` advances the native
dialogue, but first forces the retained previous-mode byte `$C195` to non-rescue mode 0.
The constructor must still select mode 8 from incoming register C. This deliberately makes
the pre-fix `$C195`-based wrapper fail before the editor checkpoint rather than letting the
capture's accidentally retained mode 8 conceal the production route. The test then
requires settled English editor checksum `$58E436FE` with the shared shadowed atlas, enters the published
`OEN936H9n!FVv` code through controller navigation, and freezes native input
`3E343D76707337765778354568FF` before choosing `OK`. The old public request cannot be
entered because this diary has not unlocked the Abyssal Depths; its deterministic
`You cannot enter that dungeon yet!` response proves native validation was reached and did
not freeze, not that a complete rescue was accepted.

The same route also enters `AB`, presses the hardware B button, and requires both the
rendered field and the native buffer to retain uppercase `A`. Hardware B has a dedicated
native event-table handler at `16:$5B0F`; its deletion call at `16:$5B22-$5B29` bypasses
the selected keyboard-node dispatcher. The patch replaces only that far call with bank-249
wrapper `$4260`, which runs native bank-18 `$53B0` first and then refreshes through the
localized view only when mode is 5-8 and navigation type is `$F5`. The rest of the native
handler remains byte-exact. This checkpoint is distinct from the on-screen `DEL` node and
covers the user-reported lowercase-redraw failure directly.

The requester-side Revival fixture independently traverses Adventure -> Revive! ->
Password with controller input. It requires the mode-7 English editor, exact native bytes
for all 15 symbols, the native `Revival complete!` result, and the generated 12-symbol
Thank-You Password. This prevents the earlier mode-ordering bug from silently restoring
the Japanese constructor on a rescue path that mode-8 SOS entry did not exercise.

The editor intentionally recalls the last password entered on that save. Resetting or
power-cycling does not blank it: the native game persists the retained length/buffer state
around `$C491/$C493`, then preloads it on the next Password visit. Localization preserves
that behavior. `DEL` or hardware B edits the recalled code; no patch should clear it merely
because the English screen constructor ran.

The connection popup itself is a separate geometry owner. The native five-interior-tile
frame clips `Password`; `tools/service_menus.py` recognizes only the exact Cable / Password
/ Quit selector sequence and uses a seven-interior-tile frame. Its 56-pixel interior leaves
48 pixels after the fixed 8-pixel cursor column, enough for the 42-pixel label. Because the
state already contains old menu pixels, `tests.test_service_menus` first backs out, rebuilds
the route, checks the clean
nine-column service popup, and then dismisses it to prove the new right edge is removed.
This sequence is intentional: the confirmation selects dynamic-text VRAM bank 1, while
the warehouse normally uses bank 0. The widened service bottom row therefore copies the
renderer-selected bank bit into its seven border attributes before the BG transfer; otherwise
the Rescue popup alone displays stale tile graphics under `Quit`.
The label renderer provides only six sequential dynamic tile IDs per row. A generic seventh
sequential ID aliases another row's cursor and can produce a duplicate arrow when lower
options are selected, so the shared warehouse/Bank Teller template uses stable tile `$B3`
throughout. Rescue has a separate three-entry template: only the two physical spill cells containing the final
column of `Password` use the already-rendered overflow tiles `$A8/$BA`; every other spill
cell remains `$B3`. Those aliased lower rows are outside the shorter Rescue frame. A separate
PyBoy regression compares the final `d` against its literal approved 5x8 raster, while the
live route visits Cable, Password, and Quit and requires distinct corrected frames.
The completed-rescue Cable / Password / Cancel / Later selector is taller, so `$A8/$BA`
are live cursor rows there. Its dedicated constructor copies the two `Password` fragments
to off-frame `$9C/$AE`, clears the source aliases, and uses `$B3` for every other spill.
The `at-rescue.state` regression drives all four real
cursor positions, requiring the same literal `d`, one left cursor, and a blank right spill
at every stop.
The native town redraw clears only eight columns, so it cannot erase the ninth column added
for English. Before drawing a widened popup, the service owner saves that column from both
CGB VRAM banks in reserved bank-5 popup state `$D9C0-$D9DA` (the final two bytes select and mark either
Blacksmith or completed-rescue suffix staging). The shared controller-exit path restores it
for ordinary dismissals, while a guarded post-town-refresh hook covers `Password`, whose
transition leaves the town loop immediately. Both paths consume a two-byte `$A5/$5A` live
marker so uninitialized scratch cannot trigger cleanup. Warehouse begins at added-column
destination `$9B90`; row four crosses the Game Boy BG-map boundary and must wrap from
`$9BF0` to `$9810`, not continue into `$9C10`.
`tests.test_service_menus` selects `Password` rather than merely backing
out and freezes the transition with saved destination `$9950` and flag `$00`; this is the
regression for the reported vertical white strip. The Rescue, warehouse, Bank Teller, and
Blacksmith Info tests capture every original tile/attribute pair in the added column,
require every widened border cell
while open, and compare every pair after dismissal. Framebuffer hashes are supplementary,
not the cleanup oracle.

Manual testing on 2026-08-29 supplied the generated localized code
`I3CqdGY6iuyws` through the repaired English editor and the game accepted it. The code
decodes to seed `$C4C2C13E`, diary ID low word `$1234`, position `(9,8)`, dungeon ID 2
(Ancient Ruins), and internal floor 1. Its distinct diary ID avoids the native self-rescue
check that applies to the requester capture's `$7F8F` diary. This proves the localized
13-character input and native codec work together for an accessible dungeon. The code and
fields are frozen in `tests/fixtures/rescue_requester.json`; automated controller replay
of the complete accepted route remains a separate coverage improvement.

### Deterministic Revival response fixture

The captured requester SOS `26pCdewCg2640` now has a deterministic no-gift Revival
response: `SVgaVwAhmUmoM3u`. Its native bytes are
`42 45 50 4A 45 69 30 51 56 44 56 58 3C 70 67`, its rescuer diary checksum is `$A9`,
and its gift record is eight zero bytes. The response is bound to the requester's saved SOS
checksums; it is not a free-standing password.

The controller regression loads `SaveStates/rescue-requester-sos.state`, follows
**Adventure -> Revive! -> Password**, enters all 15 localized characters, and requires:

1. the cursor to move to `OK` automatically after the fifteenth character;
2. the native `Revival complete!` result;
3. generation of Thank-You Password `EkWsMPtHHOEE`; and
4. exact English/native bytes, payloads, and framebuffer checksums for both codes.

For a manual check, load that requester state in Mesen with a current English build, press
A to close the SOS guide, choose **Adventure**, choose the diary, then choose
**Revive! -> Password**. Enter `SVgaVwAhmUmoM3u` exactly, including capitalization, and
select `OK`. The game must say `Revival complete! Select Continue to resume the game.`
Press A once more and confirm the displayed Thank-You Password is `EkWsMPtHHOEE`.
This complete manual route was confirmed in Mesen on 2026-08-30.

This fixture is distinct from the manually accepted `I3CqdGY6iuyws` rescue request. To
capture the response produced by that live rescuer diary, complete its Ancient Ruins 1F
Rescue Gate, return to Good, decline the optional gift for the first pass, and save both a
Mesen state and SRAM while the 15-character Revival Password is visible. That generated
code will let the fixture replace the fixed `$A9` test identity with a full two-diary
exchange.

The first attempted regression used a state captured after the editor was already active
and added a common-loop repair. That did not represent the reproducible menu route and was
removed. The retained test always starts from `rescue-entry-menu.state`, constructs the editor
through controller input, and exercises the actual hardware-B event handler. Static tests
freeze its single guarded hook and the RGBDS payload.

The PyBoy route tests hash-check their committed states, build the ROM at a fresh temporary
path, start a new headless emulator instance, and stop without saving. This keeps the
fixtures immutable and prevents a route from retaining an earlier ROM build.

The route must assert inventory/equipment restoration, floor and position, cleared rescue
room state, rescue history/count/reward updates, and stable SRAM on save/reload. Screen
fixtures must cover cursor reachability, exact limits, `DEL`, confirm, cancel, invalid-code
retry, grouping, and all three rendered lengths. A Link Cable dispatch smoke test must prove
the password overlay does not intercept cable mode.

## Manual discovery route

To create the requester half of the deterministic fixture:

1. Back up the current SRAM and use a disposable copy of the English ROM state.
2. Load `SaveStates/Mamel.mss`, pause Mesen, and run
   `tools/mesen_prepare_rescue_request.lua` from **Debug > Script Window**.
3. Resume, dismiss the existing message if necessary, and let the adjacent Mamel hit
   Shiren once. Do not attack it first.
4. Save a state on Rankings before changing any selection.
5. Press `Select`, choose **Await Rescue**, and save a second state at the generated SOS
   screen. Preserve the matching requester `.srm` if Mesen writes one.
6. Record the Adventure -> `SOS!` route and the live input/output state addresses.
7. Use a second disposable SRAM for the rescuer, enter the Rescue Team building, speak to
   the receptionist if the gate is closed, and record the password screen before entering
   any data.

Do not force broad story flags. If **Await Rescue** is absent, keep the Rankings state and
record the dungeon/floor and visible options; that is evidence for the eligibility trace,
not permission to toggle an inferred unlock flag.

## Implementation order and release gate

1. ~~Add the clean-ROM mode/length and external-vector fixtures.~~ Complete.
2. ~~Trace and document the native symbol and packet-codec paths.~~ Complete.
3. ~~Implement the reference packet codec and prove public-vector compatibility.~~ Complete.
4. ~~Trace the SOS/Revival/Thank-You builders, loaded-diary records, and semantic
   relationship.~~ Complete; live SRAM persistence remains part of step 5.
5. Capture the two-SRAM native handshake. Requester one-HP setup, Rankings, and SOS are
   complete; rescuer, Revival, resumed-floor, and Thank-You states remain.
6. ~~Add the presentation mapping and localized input/output screens.~~ Complete for the
   shared generated-code path and input modes 5-8; stage-specific modes 5-7 captures remain
   part of the handshake fixture.
7. Replay the complete handshake in the English build, including gifts and persistence.
8. Update this document, [ROM_BANK_MAP.md](ROM_BANK_MAP.md), the root README, and project
   status with every confirmed address, reservation, fixture, and remaining limitation.

The feature is not complete when a password merely appears or accepts characters. Release
requires a complete requester-to-rescuer-to-requester-to-rescuer exchange, malformed-input
coverage, gift serialization coverage, save/reload persistence, and native-code conversion.
