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
- Four-character A-Z/0-9 Big Moai promotional gift-code entry, with the approved four-row
  keyboard, corrected below-label `DEL`/`OK` cursors, and all 100 runtime
  codes and story clues synchronized. The game calls these codes "spells"; they are
  independent of Wanderer Rescue passwords. The supplied locked NPC state proves the
  `$C3EF/$C3F0` stage-9 gate; the production helper changes only that pair, and a live
  controller route enters `WISH`, verifies the localized Fortune Grass reward, and reaches
  a fresh post-reward conversation without freezing.
- Full-name English Blank Scroll writing, including all 32 accepted roots, the required
  hyphen, and the original notebook rule. The supplied live confirmation state is retained
  as a no-reset, no-inventory-damage PyBoy regression.
- Localized unidentified-item Name screen with a reachable cycling `FILL IN` history
  control, seven-character free labels, 14-character canonical previews, and tokens that
  display complete English names without changing the native persistent slot layout.
  Canonical previews have blank tails, retain the original seven-cell horizontal origin,
  and atomically reset to the native free editor on either character entry or `DEL`; both
  transitions are live-route tested through return to Items.
- Adventure -> save-file navigation retains its native nine-row graph; the complete
  Continue/Secrets/Reset/Recap cursor route is replayed from the Mamel fixture and its
  cursor state, sprite positions, and stable framebuffer are frozen.
- Rescue Team, warehouse, Bank Teller, and Blacksmith Info service popups use exact
  selector-set detection and a 56-pixel English interior with a measured 48-pixel
  post-cursor text budget, while
  unrelated generic popups retain native geometry. All six
  user-supplied routes are rebuilt in PyBoy regressions. The initial Rescue route
  separately freezes its preceding Yes/No prompt and synchronizes the widened bottom
  border with the renderer-selected CGB VRAM bank, preventing the confirmation from
  leaking stale tiles into the later popup. Before drawing, both VRAM banks' added ninth
  column are saved and restored on either dismissal or selection. The warehouse routes
  explicitly handle vertical `$9BFF -> $9800` and horizontal x=31 -> x=0 BG-map wraps;
  the same-room floor-items fixture guards the latter with a literal right-edge raster,
  while its re-entered state is the clean control. All routes compare every added
  column tile and attribute before and after teardown. All routes traverse every option and
  enforce the native six-dynamic-tile row allocation. Warehouse and Bank keep stable tile
  `$B3` in every spill cell; Blacksmith stages `Synthesis`'s suffix in `$B3`, clears its
  `$9C` Quit-cursor alias, selects the active VRAM bank for `$B9` elsewhere, and restores the
  tile on exit; the shorter Rescue frame exposes `$A8/$BA` only where it needs
  `Password`'s final column, with `$B3` elsewhere. The completed-rescue selector stages
  those fragments in off-frame `$9C/$AE`, clears the source cursor aliases, and traverses
  Cable, Password, Cancel, and Later while rejecting left- or right-column garbage. A hash-independent pixel regression
  requires the complete final `d`, the 45x8 `Synthesis` word, and blank cells on both sides
  of unselected `Quit`; a dedicated `Password`
  transition regression prevents
  the reported vertical strip. The rescue request Yes/No cursor and the
  save-summary `Awaiting Rescue`/run-count composition are also framebuffer-frozen.
  Training Ground (`Train`), Training House (`Train+`), Pigeon Handler
  (`SOS / Revive / Thanks / Quit`), and the rescued-player
  (`Yes / No / Info / Later`) menus were manually accepted on 2026-08-31.
- Rankings renders its dynamic currency and floor fields as compact suffix forms:
  `<amount>G` and `<floor>F`. The fixed score suffix at `192:$6B7D` is `G`, while the
  separate floor suffix at `192:$6B2B` remains `F`; a production-ROM controller replay
  independently guards `11250G` / `9F` and their native pixel boundaries.
- The clean-boot copyright/composer card preserves both native `© 2001` rows and replaces
  only its two private 512-byte name strips with approved `CHUNSOFT` and `Koichi Sugiyama`
  art. The editable Inter SemiBold 4.1 source, OFL provenance, exact source guards, native
  fade stages, and unchanged title handoff are all fixture-tested without a framebuffer hash.
- All 32 town/dungeon/floor arrival selectors use approved Inter SemiBold 4.1 artwork from
  an editable block source. The native nine-block alias was decoded as `Mystery Dungeon`;
  no placeholder text ships. A guarded bank-$F8 clone retains native centering, ten byte-exact
  Latin digit blocks and formatting, underline, palettes, fade, and handoff; its shared `F`
  block is raised one pixel from the guarded native source for approved optical alignment. Every selector is independently
  decoded from production bytes, all `1F`-`99F` combinations are exhaustively composed from
  the production floor blocks, and natural Mamel stairs transitions match the approved
  `Ancient Ruins` / `1F` and `2F` pixels. A separate live regression compares the `1` and `F`
  bright caps directly; none of these checks uses a framebuffer hash.
- The save/load wait sign is localized to `Please` / `wait...` from an editable Thin Pixel-7
  raster. Its two 256-byte sign blocks are exact-source guarded, both interleaved bird-art
  blocks remain byte-exact, and an independent decoded-pixel regression covers the full sign
  without changing a framebuffer hash. Automated live reproduction of the user-observed
  suspend/reload route remains pending.
- The dedicated dungeon-HUD atlas installs approved player-supplied `0-9`, `F/L/v/H/p`, and
  slash rasters while retaining native `A-E`, meter art, and reserved cells. The `Lv` tile
  moves `v` one pixel left to match the supplied pair spacing. Both source images are
  identity-frozen, every production glyph and the complete kerned pair are pixel-tested, and
  the three owned ROM ranges fail closed without updating framebuffer hashes.
- The cracked-Bracelet suffix keeps its native `F2 1E` token and 14-pixel renderer advance,
  but its Japanese `(hibi)` bitmap is localized to `(Cr)`. All translated item-name shapes
  retain 18 pixels of worst-case row margin, and the supplied failure state is replayed in
  PyBoy after closing and reopening Items.
- Dynamic inventory producers now emit English arrow quantities, signed equipment values,
  staff/Pot brackets, and spaced Gitan amounts. Every translated family maximum fits; the widest equip + curse +
  plate combination ends at x=132 against the x=144 edge. A two-page PyBoy gallery renders
  all twenty representative rows for visual review. A separate native Synthesis Pot route
  inserts a Club base and correctly seeded Minotaur Axe donor, asserts both insertion
  transitions, breaks the Pot, asserts the released critical-hit rune, and leaves the seal
  description available for manual visual review.
- The complete 198-item terminology pass corrected 50 names to established series usage,
  synchronized every description heading and affected unidentified-item root, and freezes
  three precedent-free GB2 names in an explicit review catalogue.
- Scene-ordered prose editing and generated-cell ownership checks.
- A passing fixture suite covering translation, layout, save data, menu/input
  routes, production builds, native PyBoy state behavior, and RGBDS payload
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
  the full controller route, all thirteen cells, and native-validator return. Hardware-B deletion is also
  replayed after entering `AB`, with the uppercase rendered remainder and native buffer
  frozen independently of the on-screen `DEL` path. The patch wraps only the dedicated
  native delete far call and leaves the common input loop intact. Manual testing also accepted
  `I3CqdGY6iuyws`, an Ancient Ruins 1F SOS with a distinct diary ID; its exact native
  bytes, payload, and semantic fields are now fixture-frozen. A requester-side controller
  replay also accepts 15-character Revival response `SVgaVwAhmUmoM3u`, displays the
  native success result, and generates linked Thank-You Password `EkWsMPtHHOEE`; the same
  complete route was manually confirmed in Mesen. Add the
  physical Rescue Gate/two-diary emulator and SRAM completion fixture and preserve cable
  compatibility; see
  [RESCUE_SYSTEM.md](RESCUE_SYSTEM.md).
- Editorial read-through of the complete scene document for voice, continuity, and
  natural English.
- Full-game and rare-route playtesting, including optional allies, endings, postgame,
  traps, save/resume, rankings, and uncommon dynamic text combinations.
- Full graphics localization: the clean-boot copyright/composer card and all 32 arrival cards are installed from
  approved source art and pixel-tested across its fade and title handoff. The save/load wait
  sign is installed and statically pixel-tested but still needs its live route captured. The
  main title still needs approved English art and insertion. The ending staff roll still needs main-ending and true-ending save states before
  its visible storage/consumers can be traced; see [GRAPHICS.md](GRAPHICS.md).
- Iterative layout and font polish for issues discovered in playtesting.
- Release packaging and final clean-ROM reproducibility checks.

The release gate is intentionally stricter than “all extracted text has English.” See
[ENGINEERING_RULES.md](ENGINEERING_RULES.md) for the missing route, graphics, and clean-build
requirements.

The latest verified production build produces two font variants from the same translation
and engine patches:

- `build/shiren-gb2-english-classic-font.gbc` — SHA-1
  `40f51bda7e03b915dbf5affa8f7a3693c343914f`
- `build/shiren-gb2-english-classic-font.ips` — SHA-1
  `7b6732b33a7e1cab6ca12503d43318312cf8a4d0`
- `build/shiren-gb2-english-shadowed-font.gbc` — SHA-1
  `42c608506ee36819563374fcea76a03210e27686`
- `build/shiren-gb2-english-shadowed-font.ips` — SHA-1
  `e7284922dfd64ef734b48e990ef095bc4d5c9df2`

Always rebuild and verify locally rather than treating those hashes as permanent release
identifiers.
