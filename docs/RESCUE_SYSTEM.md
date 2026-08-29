# Wanderer Rescue password system

GB2's Wanderer Rescue feature is a three-password, two-diary protocol. This document
records the original player flow, confirmed native input contracts, localization design,
manual and automated test strategy, and the reverse-engineering gates that must be passed
before production code changes.

The rescue implementation is currently in the **protocol-audit stage**. The surrounding
English labels and dialogue are present. The native alphabet and packet codec are now
reproduced by an automated reference implementation, but the payload fields, localized
renderer/input layer, and complete two-diary handshake have not yet been proven in an
emulator fixture.

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

| Input mode | Native maximum | Inferred role from unique native length |
|---:|---:|---|
| 5 | 12 | Thank-You Password |
| 6 | 9 | Training Dungeon password |
| 7 | 15 | Revival Password |
| 8 | 13 | SOS Password |

Mode 2 is a separate 13-character input route and must not be patched merely because its
length matches SOS. Its caller and purpose remain a trace target.

The role mapping above is strongly identified by the four unique documented protocol
lengths, but each live screen must still capture `$C195` in Mesen before its role is treated
as a patch-site contract.

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
than inferred from an extracted category label.

## Password sizes and encoded data

The packet layer at `11:$7B17-$7D8B` is now reproduced by
`tools/rescue_password.py`. Before symbol packing, the four payload sizes are:

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

The independently reverse-engineered GB2 generator documents:

| Code | Characters | Confirmed payload |
|---|---:|---|
| Training | 9 | Dungeon seed, dungeon ID, internal floor |
| SOS | 13 | Dungeon seed, requester diary-ID low 16 bits, Shiren X/Y, dungeon ID, internal floor |
| Revival | 15 | SOS data, rescuer diary ID, optional eight-byte gift |
| Thank-You | 12 | Derived acknowledgement for the completed rescue |

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
fixture. They must never be rewritten as translation text. Once a reference decoder is
implemented, it must validate the relationship among all three codes rather than checking
only their lengths.

- [Public GB2 SOS, Revival, and Thank-You exchange](https://bbs6.sekkaku.net/bbs/dobuntya/)

## Localization architecture

The preferred architecture preserves the original payload, checksum, code lengths, and
Link Cable data while localizing only password presentation:

1. Prove and retain the native encoder/decoder and native symbol values.
2. Define a one-to-one mapping from every native password symbol to one distinct
   English-font symbol.
3. On output, render the mapped English symbol without changing the encoded payload.
4. On input, make the English keyboard write the corresponding native symbol value.
5. Provide a deterministic Japanese-to-English and English-to-Japanese converter so
   passwords remain shareable with unmodified Japanese copies.

The native domain is now proven to contain 64 symbols. A candidate presentation alphabet
is `A-Z`, `a-z`, `0-9`, `?`, and `!`, preserving a one-to-one, case-sensitive mapping.
The final two symbols and keyboard layout remain a visual-review decision; the mapping
must be frozen before any public English passwords are generated.

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
  type, renderer, confirmation routine, and error return.
- The native 64-symbol domain, packet lengths, codec, checksum, mode dispatcher, and three
  public vectors are frozen in `tests/fixtures/rescue_password.json`.
- Locate and freeze the per-stage payload builders/validators, SRAM/WRAM request state,
  and optional-gift paths.
- Capture the live modes and prove that all four input screens use the same alphabet.
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

The route must assert inventory/equipment restoration, floor and position, cleared rescue
room state, rescue history/count/reward updates, and stable SRAM on save/reload. Screen
fixtures must cover cursor reachability, exact limits, `DEL`, confirm, cancel, invalid-code
retry, grouping, and all three rendered lengths. A Link Cable dispatch smoke test must prove
the password overlay does not intercept cable mode.

## Manual discovery route

Until the deterministic fixtures exist:

1. Back up the current SRAM and use a disposable copy.
2. Enter an ordinary early dungeon after reaching Ilpa.
3. Save immediately before an intentional death.
4. On Rankings, press `Select` for **Await Rescue**.
5. Record the generated SOS screen and Adventure -> `SOS!` route.
6. Use a second disposable SRAM for the rescuer, enter the Rescue Team building, speak to
   the receptionist if the gate is closed, and record the password screen before entering
   any data.

Do not force broad story flags. If a helper becomes necessary, identify the exact event
flag and guard it against a known state before creating a test-only Mesen script.

## Implementation order and release gate

1. ~~Add the clean-ROM mode/length and external-vector fixtures.~~ Complete.
2. ~~Trace and document the native symbol and packet-codec paths.~~ Complete.
3. ~~Implement the reference packet codec and prove public-vector compatibility.~~ Complete.
4. Trace the SOS/Revival/Thank-You payload builders, semantic validators, and save state.
5. Capture the two-SRAM native handshake.
6. Add the presentation mapping and localized input/output screens.
7. Replay the complete handshake in the English build, including gifts and persistence.
8. Update this document, [ROM_BANK_MAP.md](ROM_BANK_MAP.md), the root README, and project
   status with every confirmed address, reservation, fixture, and remaining limitation.

The feature is not complete when a password merely appears or accepts characters. Release
requires a complete requester-to-rescuer-to-requester-to-rescuer exchange, malformed-input
coverage, gift serialization coverage, save/reload persistence, and native-code conversion.
