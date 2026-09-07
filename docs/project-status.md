# Project status

The English localization is complete apart from the opening menu/title-screen artwork.
Every player-facing text record has explicit English or an intentional empty value.
In-game menus, input screens, and the other localized graphics are implemented; playtesting
and bug fixes continue.

The [hosted rescue password converter](https://joey-astrologo.github.io/Shiren-GB2-Magic-Castle-of-the-Desert/)
is available with all three promotional mission presets. The latest release verification
passed **646 suite tests and 30 additional checks against the exact release ROMs**, with
zero failures, errors, or skips.

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
| Runtime-facing Big Moai and room-label text | 212 | 212 |
| Explicit production translations/empties | 5,679 | 5,679 |

The internal catalog contains another 1,016 records proven to be developer selectors,
debug labels, animation/effect dispatch identifiers, or internal object IDs. They are
deliberately left native and guarded by the [internal-text audit](internal-text-audit.md).

All 1,768 dialogue-box records are present in `script/editing/prose.tsv`, arranged into
72 scene families. Of those, 1,767 contain translated dialogue and one is an explicit
native empty slot. The remaining 18 prose-catalog records are ending or credit labels
edited through the ordinary catalog workflow.

## Completed engineering

- Clear Campaign and True Wanderer certificate fields use compact English `Label: value`
  spacing. The extra fixed padding before each colon is removed in the two owning
  UI text records. Both font variants were inspected from the converted spacing-report
  fixture, with the native certificate values preserved; see [CLEAR_CAMPAIGN.md](CLEAR_CAMPAIGN.md).

- The three guidebook promotional rescue missions have verified English SOS codes,
  advertised dungeon/floor payloads, and native acceptance tests in both font builds.
  The tests use disposable copies of the existing entry fixture, with separately checked
  locked and accessible dungeon conditions; complete mission playthroughs are not implied.
  A source-free Python/browser converter supports both directions and all four GB2 packet
  lengths, with generated alphabet data and Python/JavaScript codec parity checks. The
  converter is published on GitHub Pages, with updates on main deployed after its tests pass.
  Its English/Japanese interface selector translates labels, instructions, mission names,
  and validation/clipboard feedback while preserving entered passwords and results.
  The bounded ROM audit found no promotional whitelist on the SOS path or embedded
  representations of the published packets. See
  [SPECIAL_RESCUE_MISSIONS.md](SPECIAL_RESCUE_MISSIONS.md).

- Stable extraction and semantic organization of 6,695 records and 7,163 logical
  references.
- Thin Pixel-7 variable-width English font and measured line-layout validation.
- Production validation includes final-row glyph cells and cumulative physical rows across
  page waits. Item-message width bounds include full canonical recalled names with their
  category prefixes; the longest current expansion is 107 pixels.
- The shared VWF compositor clips secondary tile writes at the 144-pixel canvas edge.
  Drinking Otogirisou and Leaping Grass exposed a three-pixel bottom-border gap in a
  two-line combat window that the previous third-line audit missed. Both real item-use
  routes preserve the complete bottom border in both fonts, with unchanged message text.
- Sword/shield equipment previews start after the item-action cursor tile, so cursor
  cleanup cannot erase the current or proposed value. Both unsigned-byte values and the
  native arrow fit within 40 pixels, including three-digit totals on both sides.
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
- Clear Campaign and True Wanderer certificates display their six-symbol historical
  mail-in credentials through the established `A-Z a-z 0-9 ? !` mapping. A PyBoy replay
  freezes `QVZ9Ee` for the supplied clear-campaign state at pixel level and proves that the
  native credential remains unchanged. These credentials have no in-game input route.
- Full-name English Blank Scroll writing, including all 32 accepted roots, the required
  hyphen, and the original notebook rule. The supplied live confirmation state is retained
  as a no-reset, no-inventory-damage PyBoy regression.
- Localized unidentified-item Name screen with a reachable cycling `FILL IN` history
  control, seven-character free labels, 14-character canonical previews, and tokens that
  display complete English names without changing the native persistent slot layout.
  Canonical previews have blank tails, retain the original seven-cell horizontal origin,
  and atomically reset to the native free editor on character entry, `DEL`, or physical B.
  Live routes cover all three transitions, repeated typing without adjacent-memory writes,
  and confirmation back to Items.
- The shared English graphical-input controller ignores Select's obsolete Japanese kana
  modifier. Regressions preserve typed and recalled item names, the default player name,
  and native Rescue password symbols through Select and subsequent confirmation.
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
- Item-action labels now distinguish their 48-pixel coordinate stride from the five mapped
  label tiles (40 visible pixels) after the cursor. All black pixels fit; the one-column
  gray shadows from `Take Out` and `Exchange` are clipped by clearing the two cursor-only
  canvas columns immediately before upload. The supplied floor-item save state preserves
  the exact `$60/$72` contamination and a PyBoy regression proves it disappears after a
  real dismiss/reopen cycle.
- Rankings renders its dynamic currency and floor fields as compact suffix forms:
  `<amount>G` and `<floor>F`. The fixed score suffix at `192:$6B7D` is `G`, while the
  separate floor suffix at `192:$6B2B` remains `F`; a production-ROM controller replay
  independently guards `11250G` / `9F` and their native pixel boundaries.
- The clean-boot copyright/composer card preserves both native `© 2001` rows and replaces
  only its two private 512-byte name strips with approved `CHUNSOFT` and `Koichi Sugiyama`
  art. The editable Inter SemiBold 4.1 source, OFL provenance, exact source guards, native
  fade stages, and unchanged title handoff are all fixture-tested without a framebuffer hash.
- The main-ending staff roll replaces its exact-hash-guarded title plane and all 20 raw 2bpp
  role/name planes with approved Inter SemiBold 4.1 artwork. Native scroll positioning, fades,
  palettes, timing, and the Japanese `終` mark remain unchanged. The fixed surrounding map now
  uses tile `$F0`, verified black across the opening and ending planes, instead of the
  English-occupied tile `$80`; the title, every stable staff card, and preserved end mark are
  checked live in PyBoy without a framebuffer hash.
- All 32 town/dungeon/floor arrival selectors use approved Inter SemiBold 4.1 artwork from
  an editable block source. The native nine-block alias was decoded as `Mystery Dungeon`;
  no placeholder text ships. A guarded bank-$F8 clone retains native centering, ten byte-exact
  Latin digit blocks and formatting, underline, palettes, fade, and handoff; its shared `F`
  block is raised one pixel from the guarded native source for approved optical alignment. Every selector is independently
  decoded from production bytes, all `1F`-`99F` combinations are exhaustively composed from
  the production floor blocks, and natural Mamel stairs transitions match the approved
  `Ancient Ruins` / `1F` and `2F` pixels. A separate live regression compares the `1` and `F`
  bright caps directly; none of these checks uses a framebuffer hash.
- The save/load wait sign is localized to centered, no-shadow `Please` / `wait...` text from
  an editable Thin Pixel-7 raster. Its two 256-byte sign blocks are exact-source guarded,
  both interleaved bird-art blocks remain byte-exact, and an independent decoded-pixel
  regression covers the full sign without changing a framebuffer hash. Automated live
  reproduction of the user-observed suspend/reload route remains pending.
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

## Remaining localization

The opening menu/title screen needs approved English replacement artwork and insertion.
Its native resources are traced in [GRAPHICS_AUDIT.md](GRAPHICS_AUDIT.md#title-screen).
This is the only known missing localization item.

## Verification coverage and playtesting

The full suite and additional release battery cover the implemented localization. Further
manual testing and fixture coverage remain useful for:

- The complete Rescue Gate/two-diary exchange, including rescuer dungeon completion,
  gift delivery, SRAM persistence, and Link Cable. Native protocol compatibility,
  English SOS entry, and the requester Revival-to-Thank-You route already pass; see
  [RESCUE_SYSTEM.md](RESCUE_SYSTEM.md).
- A dedicated true-ending trace to compare its graphic resource loads with the localized
  main ending, and a live visual capture of the installed save/load wait sign.
- Full-game and rare-route playtesting, including optional allies, postgame, traps,
  uncommon save histories, dynamic text combinations, and editorial/layout polish.

The automated release run did not perform a full playthrough. Its detailed coverage is
recorded in [testing-and-build.md](testing-and-build.md#release-verification).

## Verified build and package

The 2026-09-07 build was verified from clean source revision
`535f884d4a5d3d0697231718a8a26cadacbe4b6f`:

- 646 discovered tests passed in 807.464 seconds, with no failures, errors, or skips.
- 30 additional tests passed against the exact classic and shadowed ROMs, including
  cold boot, save/reload in all four font combinations, rescue I/O, ending cards,
  equipment previews, and combat/Monster Log borders.
- All ten validation/build commands passed. A fresh local clone reproduced both ROMs
  and both IPS patches byte for byte. Both cartridge checksums and IPS reconstruction
  were verified, including patches read back from the final ZIP.
- `Shiren-GB2-English-2026-09-07.zip` contains both IPS patches, instructions, font
  licenses, checksums, the verification report, and the offline rescue converter.
  Its SHA-256 is `0cd9e5b10df9e4905cbf94ae7129adb90c8325ed2b304c9da72ec7631ad94483`.

The package and detailed logs are local generated artifacts under
`build/release-2026-09-07/`, which is ignored by Git. The package is a public test build;
the [engineering rules](ENGINEERING_RULES.md#release-claims) describe broader release
acceptance and playthrough evidence.

Both font variants use the same translation and engine patches:

- `build/shiren-gb2-english-classic-font.gbc` — SHA-1
  `4050696a08102b3bf3d25a1f790ec68cedac09b8`
- `build/shiren-gb2-english-classic-font.ips` — SHA-1
  `ad78698a13f758608cad8729ccdad4db3ca92b12`
- `build/shiren-gb2-english-shadowed-font.gbc` — SHA-1
  `b26feba0f8688b48a3eb20249089d9056ccb1227`
- `build/shiren-gb2-english-shadowed-font.ips` — SHA-1
  `6bfeb5de96e0e890321959888a916aa8866f9ad1`

Always rebuild and verify locally rather than treating those hashes as permanent release
identifiers.
