# Project status

The extracted text translation pass is complete. This means every player-facing
record has explicit English or an intentional empty value; it does not mean the
localization has completed editing, playtesting, or graphics work.

## Text coverage

| Catalog | Complete | Total |
|---|---:|---:|
| Glossary and names | 1,938 | 1,938 |
| Item descriptions | 216 | 216 |
| Monster information | 459 | 459 |
| UI and system text | 493 | 493 |
| Help and Secrets | 176 | 176 |
| Gameplay messages | 399 | 399 |
| Story, events, and endings | 1,786 | 1,786 |
| Player-facing subtotal | 5,467 | 5,467 |
| Runtime-facing Big Moai gift-code text | 200 | 200 |
| Explicit production translations/empties | 5,667 | 5,667 |

The internal catalog contains another 1,028 records proven to be developer selectors,
debug labels, animation/effect dispatch identifiers, or internal object IDs. They are
deliberately left native and guarded by the [internal-text audit](internal-text-audit.md).

All 1,768 dialogue-box records are present in `script/editing/prose.tsv`, arranged into
72 scene families. Of those, 1,767 contain translated dialogue and one is an explicit
native empty slot. The remaining 18 prose-catalog records are ending or credit labels
edited through the ordinary catalog workflow.

## Completed engineering

- Stable extraction and semantic organization of 6,695 records and 7,163 logical
  references.
- Thin Pixel-7 variable-width English font and measured line-layout validation.
- Far-pointer allocation that separates ROM storage from visible line constraints.
- Localized menus, Help/Secrets, Monster Notebook, item information, gameplay messages,
  combat text, and story/event text.
- Six-character player names, default name `Shiren`, save compatibility metadata,
  expanded ranking-result name storage, and localized names in all fourteen embedded
  title/demo and Wanderer's Secrets replay diaries.
- Four-character A-Z/0-9 Big Moai promotional gift-code entry, with all 100 runtime
  codes and story clues synchronized. The game calls these codes "spells"; they are
  independent of Wanderer Rescue passwords.
- Full-name English Blank Scroll writing, including all 32 accepted roots, the required
  hyphen, and the original notebook rule. The supplied live confirmation state is retained
  as a no-reset, no-inventory-damage Mesen regression.
- Localized unidentified-item Name screen with a reachable cycling `FILL IN` history
  control, seven-character free labels, 14-character canonical previews, and tokens that
  display complete English names without changing the native persistent slot layout.
  Canonical previews have blank tails, retain the original seven-cell horizontal origin,
  and atomically reset to the native free editor on either character entry or `DEL`; both
  transitions are live-route tested through return to Items.
- Adventure -> save-file navigation retains its native nine-row graph; the complete
  Continue/Secrets/Reset/Recap cursor route is replayed from the Mamel fixture and its
  cursor state, sprite positions, and stable framebuffer are frozen.
- The cracked-Bracelet suffix keeps its native `F2 1E` token and 14-pixel renderer advance,
  but its Japanese `(hibi)` bitmap is localized to `(Cr)`. All translated item-name shapes
  retain 18 pixels of worst-case row margin, and the supplied failure state is replayed in
  Mesen after closing and reopening Items.
- Dynamic inventory producers now emit English arrow quantities, signed equipment values,
  staff/Pot brackets, and spaced Gitan amounts. Every translated family maximum fits; the widest equip + curse +
  plate combination ends at x=132 against the x=144 edge. A two-page Mesen gallery freezes
  all twenty representative rows for visual review. A separate native Synthesis Pot route
  inserts a Club base and correctly seeded Minotaur Axe donor, freezes both insertion
  transitions, breaks the Pot, asserts the released critical-hit rune, and leaves the seal
  description available for manual visual review.
- The complete 198-item terminology pass corrected 50 names to established series usage,
  synchronized every description heading and affected unidentified-item root, and freezes
  three precedent-free GB2 names in an explicit review catalogue.
- Scene-ordered prose editing and generated-cell ownership checks.
- A passing 416-test fixture suite covering translation, layout, save data, menu/input
  routes, production builds, PyBoy behavior, Mesen reproduction paths, and RGBDS payload
  equivalence.

## Remaining project work

- Wanderer Rescue protocol engineering: the native packet codec and semantic
  SOS -> Revival/gift -> Thank-You chain reproduce a real published exchange. The supplied
  Rankings and SOS states are hash-frozen, and their generated SOS code exactly matches the
  saved diary record. The live Rankings -> Await Rescue route now renders the frozen
  `A-Z a-z 0-9 ? !` mapping while restoring `$C16D` to its native bytes and leaving the
  diary record untouched. Modes 5-8 now use a private English name-layout keyboard with
  `?` and `!`; each selection is converted back to the corresponding native password byte
  before validation. The supplied Password-menu state and published SOS vector exercise
  the full controller route, all thirteen cells, and native-validator return. A separate
  captured failure fixture starts inside the Japanese mode-8 editor and proves the common
  input-loop repair replaces its complete 320-tile map and navigation graph. A live Mesen
  regression also loads that broken state and requires the installed loop hook to fire
  naturally, without calling the repair routine from the test. Manual testing also accepted
  `I3CqdGY6iuyws`, an Ancient Ruins 1F SOS with a distinct diary ID; its exact native
  bytes, payload, and semantic fields are now fixture-frozen. A requester-side controller
  replay also accepts 15-character Revival response `SVgaVwAhmUmoM3u`, displays the
  native success result, and generates linked Thank-You Password `EkWsMPtHHOEE`. Add the
  physical Rescue Gate/two-diary emulator and SRAM completion fixture and preserve cable
  compatibility; see
  [RESCUE_SYSTEM.md](RESCUE_SYSTEM.md).
- Editorial read-through of the complete scene document for voice, continuity, and
  natural English.
- Full-game and rare-route playtesting, including optional allies, endings, postgame,
  traps, save/resume, rankings, and uncommon dynamic text combinations.
- Full graphics localization: inventory, replacement art, insertion, and visual QA; see
  [GRAPHICS.md](GRAPHICS.md).
- Iterative layout and font polish for issues discovered in playtesting.
- Release packaging and final clean-ROM reproducibility checks.

The release gate is intentionally stricter than “all extracted text has English.” See
[ENGINEERING_RULES.md](ENGINEERING_RULES.md) for the missing route, graphics, and clean-build
requirements.

The latest verified production build is `build/shiren-gb2-english.gbc`. Its SHA-1 at
the time this status was consolidated was
`5363954192bdd29a97dc151aea36b26051a2c66d`; always rebuild and verify locally rather
than treating that hash as a permanent release identifier.
