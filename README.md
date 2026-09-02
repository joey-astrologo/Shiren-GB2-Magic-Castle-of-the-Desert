# Shiren GB2 English localization

**Made with AI assistance.**

This is an unofficial fan project and is not affiliated with or endorsed by the original
developers or publishers. It exists to make *Fushigi no Dungeon: Fuurai no Shiren GB2 -
Sabaku no Majou* playable in English and to document the engineering behind that work.
Third-party components remain subject to the notices under [`licenses/`](licenses/).

This repository builds an English localization of *Fushigi no Dungeon:
Fuurai no Shiren GB2 - Sabaku no Majou* from a user-supplied Japanese ROM.

The extracted player-facing script is translated, the story is available in a
scene-ordered editor, and the production ROM builds with the native variable-width
font, six-character player names, a localized four-character Big Moai gift-code editor,
the 13-character death-Rankings note editor, and a fully English Blank Scroll writer. The
note editor gives its formerly empty selectable cells a real space action, and moving right
at the end pads one space before advancing without changing player-name behavior. The unidentified-item Name screen and its cycling `FILL IN`
history recall are also localized, including a 14-character preview and full display of
canonical names longer than the native seven-character custom-label field. Recalled names
show no star padding and reset safely to ordinary free entry on typing or `DEL`.
Each confirmed recall owns a distinct native custom-name slot, so naming another
unidentified item cannot rename the first one.
Its private navigation graph is isolated from the native Adventure submenu, whose
Continue/Secrets/Reset/Recap cursor route is replayed from a real save fixture.
All fourteen title/demo and Wanderer's Secrets replay diaries also carry the localized
six-character default name `Shiren`; they no longer fall back to their embedded Japanese
snapshot name.
In the shadowed variant, the shared player-name/Blank Scroll/unidentified-item/Rescue
graphical keyboard and Big Moai's private copy use the same reviewed gray `+1,+1`
treatment as the runtime English font, including lowercase tails, digits, and cursors.
The classic variant keeps those same approved rasters black-only.
The real Big Moai NPC route is fixture-tested from his locked story state through the
localized `WISH` editor, the rendered Fortune Grass reward, and a stable follow-up
conversation; a narrow Mesen helper changes only the two measured progression bytes needed
to exercise it.
The cracked-Bracelet suffix is also localized from the stock Japanese `(hibi)` composite
to a compact `(Cr)` marker and replayed from the supplied failure state. Native dynamic
item rows now emit English arrow quantities, signed equipment modifiers, staff/Pot brackets,
and spaced Gitan amounts; a two-page Mesen gallery covers their status-symbol combinations,
and a native Synthesis Pot lab provides a repeatable transferred-seal visual route.
The clean-boot copyright/composer card now preserves its native `© 2001` rows and fade while
rendering the approved `CHUNSOFT` and `Koichi Sugiyama` art from a guarded, reproducible Inter
SemiBold source asset.
The graphical save/load wait sign is also localized as `Please` / `wait...` from a guarded
Thin Pixel-7 source raster while preserving its interleaved bird artwork byte-for-byte.
The native Wanderer Rescue codec and semantic SOS -> Revival/gift -> Thank-You chain also
reproduce a real published three-password exchange. The captured Rankings -> Await Rescue
route now renders its generated SOS code through a frozen 64-symbol English alphabet while
restoring the native buffer and preserving the matching diary record byte-for-byte. Rescue
input modes 5-8 now share a fixture-tested English keyboard that maps every visible choice
back to its native six-bit value. A requester-side controller replay accepts a linked
15-character Revival response, displays the native success message, and generates its
12-character Thank-You Password. Physical Rescue Gate traversal and capture of the
rescuer diary's own generated response remain in progress for the complete two-diary
emulator fixture.
Editorial review, full playthrough testing, and graphics localization remain active
project work.

## Current state

| Area | State | Remaining work |
|---|---|---|
| Extracted player-facing text | **Translation pass complete** | All 5,467 records have explicit English/empty values; continue editorial and route review |
| Internal runtime text | **Complete** | 200 Big Moai promotional-code records translated; 1,028 engine-only identifiers deliberately native |
| Story organization | **Complete** | 1,768 dialogue records in 72 scene families; complete editorial read-through remains |
| Font and text storage | **Engineered** | Thin Pixel-7 native VWF and 19-bank far-pointer payload pass current contracts |
| Menus and system text | **Complete for mapped text routes** | Continue discovering transition-history and rare-route visual issues in playtesting |
| Graphical input | **Engineered** | Player names/rankings/replay snapshots, the death-Rankings note editor, Big Moai gift codes and real-NPC reward route, Blank Scroll writing, and unidentified-item Name / `FILL IN` are fixture-tested |
| Wanderer Rescue | **Native protocol and English password I/O fixture-tested** | Capture physical Rescue Gate traversal, the rescuer diary's generated Revival response, and requester floor resumption to complete the two-diary SRAM/emulator fixture without changing native payloads |
| Graphics | **In progress** | Credit card, arrival cards, and wait sign are installed; create and approve title art, live-check the wait route, and capture both ending routes |
| Automated tests | **541-test suite passing** | Complete discovery passed with credit, aligned arrival-card, title-vignette, wait-sign, ranking-suffix, death-Rankings note, and warehouse horizontal-wrap regressions included |

Translation completion is not release completion. The script still needs a complete
editorial and gameplay pass, and graphical assets still require full localization.

## Requirements

- Python 3.9 or newer.
- A legally obtained clean Japanese ROM matching:
  - SHA-1: `5264f6d0c4f12c9144de1d12fddadbadd82b3e33`
  - MD5: `9e3d4ff0ba3d6deec5080f6dbed4fef8`
- PyBoy is optional but recommended for emulator-backed integration tests.
- Pillow is optional for font and graphics inspection tools.
- RGBDS is optional; when installed, the tests reassemble the name, Big Moai gift-code, Blank
  Scroll, unidentified-name, and Wanderer Rescue presentation patches and compare them
  byte-for-byte with the embedded production payloads.

The normal production build uses only Python's standard library. Optional Python
dependencies can be installed with:

```sh
python3 -m pip install pyboy pillow
```

## Build the English ROM

From the repository root, point `ROM` at the clean Japanese game. The expected filename
is shown here for convenience, but the tool accepts any path:

```sh
ROM="Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
```

On macOS, verify the source ROM with:

```sh
shasum -a 1 "$ROM"
md5 "$ROM"
```

Audit the intentionally untranslated internal identifiers, then build:

```sh
python3 tools/internal_audit.py "$ROM"
python3 tools/build.py \
  "$ROM" \
  script/en \
  build/shiren-gb2-english.gbc \
  --font-style both
```

The release build writes both `build/shiren-gb2-english-classic-font.gbc` (the original
black-only Thin Pixel-7 adaptation) and `build/shiren-gb2-english-shadowed-font.gbc` (the
new gray `+1,+1` drop shadow). A single development ROM can still be requested with
`--font-style classic` or `--font-style shadowed`; shadowed remains the single-output
default. Both variants include the matching style in the runtime font, fixed Status labels,
shared graphical keyboard, and Big Moai's private keyboard copy.

The builder automatically validates the
source ROM, translation controls and terminology, runtime-value widths, positioned text,
far-pointer allocation, installed font and patches, all 7,163 logical text references,
and both cartridge checksums before writing the ROM. It also prints the output SHA-1 so a
manually tested artifact can be identified unambiguously.

Neither the source ROM nor generated ROMs belong in Git; both are covered by
`.gitignore`.

## Run the tests

Run the complete suite from the repository root:

```sh
python3 -m unittest discover -s tests -v
```

ROM-dependent tests skip automatically when the matching source ROM is absent. PyBoy
tests likewise skip when PyBoy is unavailable, and RGBDS source-equivalence tests skip
when `rgbasm` or `rgblink` is unavailable. For the strongest validation, install those
optional tools and keep the verified source ROM at the filename shown above.

Useful focused runs include:

```sh
# Production builder and relocated text
python3 -m unittest tests.test_build tests.test_insert

# Scene editor, translation boundary, and runtime text
python3 -m unittest \
  tests.test_prose_editor \
  tests.test_internal_audit \
  tests.test_runtime_widths

# Graphical input: names, Big Moai gift codes, Blank Scroll writing, and unidentified items
python3 -m unittest \
  tests.test_save_summary \
  tests.test_name6 \
  tests.test_spell_input \
  tests.test_big_moai \
  tests.test_blank_scroll \
  tests.test_mesen_blank_scroll \
  tests.test_unidentified_names \
  tests.test_mesen_unidentified_item \
  tests.test_rescue_password \
  tests.test_rescue_presentation \
  tests.test_service_menus \
  tests.test_item_status \
  tests.test_item_formatting \
  tests.test_synthesis_lab

# Graphical-text resource audit, HUD font, and arrival-card artwork
python3 -m unittest \
  tests.test_graphics_audit \
  tests.test_font_shadow_audition \
  tests.test_hud_font_audition \
  tests.test_shop_price_font_audition \
  tests.test_arrival_card_audition \
  tests.test_arrival_cards
```

## Audit the native HUD font

Render every alphanumeric slot used by the top dungeon status bar, plus its slash and meter
tiles, without changing the ROM:

```sh
python3 -m unittest tests.test_hud_font_audition -v
python3 tools/hud_font_audition.py
```

The contact sheet at `build/hud_font_audition.png` comes directly from the guarded packed
atlas at `3:$5742-$5841`. It includes `0-9A-F`, the production `Lv` / `Hp` letters, symbol
tiles, and minimum/maximum layout proofs at native four-pixel slot widths. The ordinary HUD
uses decimal values, `F` for Floor, and the `Lv` / `Hp` labels; `A-E` are present in the
shared nibble source even though they have not been observed in normal status values.

## Audition the shop-price font

Render all ten native shop-tag digits and representative packed prices without changing
the ROM:

```sh
python3 -m unittest tests.test_shop_price_font_audition -v
python3 tools/shop_price_font_audition.py
```

The sheet at `build/shop_price_font_audition.png` is decoded from the guarded ten-tile
source at `3:$5642-$56E1`. Shop tags pack each tile's left five pixels at a five-pixel
advance. The preview retains the captured shop palette roles: color 3 black, color 1 white,
and color 2 gray (`#A8A8A8`). This is a read-only source audit, not a font installation.

## Audit the installed shadowed dialogue font

Compare the Thin Pixel-7 source raster with its installed one-pixel gray drop-shadow bake:

```sh
python3 -m unittest tests.test_font_shadow_audition -v
python3 -m unittest tests.test_font_variants -v
python3 tools/font_shadow_audition.py
```

The sheet at `build/font_shadow_audition.png` covers all 79 supported characters, magnifies
the 8x8 edge cases (including the native-shadow `+` color proof), and shows source versus
installed copy. The production encoder paints the captured palette color 2 (`#ACACAC`) at
`(x+1,y+1)` before redrawing the unchanged color-3 black glyph. For the four disconnected
bottom cutoff pixels in `,`, `g`, `j`, and `y`, it moves only that orphan one pixel left;
connected cutoff shadows remain unchanged. It also reports the `%` shadow overhang. The
audit command itself is read-only; `english_font.py` installs this reviewed treatment.
`menu_graphics.py` also consumes the installed two-tone glyph bytes for the Status screen's
14 fixed bitmap labels, which do not pass through the runtime text renderer.

## Audition arrival-card fonts

Render all 32 arrival selectors without changing the ROM:

```sh
# Bundled Inter comparison candidate
python3 tools/arrival_card_audition.py

# Any external TTF/OTF candidate
python3 tools/arrival_card_audition.py \
  --font "/path/to/Candidate.ttf" \
  --output build/arrival_cards_candidate.png

# Deliberately test a larger strike or a solid one-bit treatment
python3 tools/arrival_card_audition.py \
  --font "/path/to/Candidate.ttf" \
  --cap-height 12 \
  --style solid \
  --output build/arrival_cards_candidate_12px.png
```

The sheet reproduces the measured native location/floor bands, red underline, 16-pixel
block alignment, and 144-pixel label budget. It cycles representative floor numbers using
the native Latin digits and the approved one-pixel-raised `F`, then ends with a magnified
alignment proof covering one- and two-digit floors. It reports label overflows instead of
clipping them. Native selectors 30/31 were independently decoded as the shared `Mystery Dungeon`
card. The bundled Inter SemiBold 4.1 treatment and aligned floor suffix are approved art;
`arrival_cards.py` installs its editable block source from
`assets/graphics/arrival_cards_inter.json`.

## Edit translated text

Story and event dialogue must be edited in `script/editing/prose.tsv`, not in its
generated catalog copies. Check an edit without changing generated files:

```sh
python3 tools/prose_editor.py "$ROM"
```

After the check succeeds, synchronize and wrap it:

```sh
python3 tools/prose_editor.py "$ROM" --apply
```

Other families have separate owners:

| Text | Authoritative file | Tool |
|---|---|---|
| Story/event dialogue | `script/editing/prose.tsv` | `tools/prose_editor.py` |
| Dungeon item/action messages | `script/drafts/item_messages.tsv` | `tools/wrap_item_messages.py` |
| Combat/gameplay messages | `script/drafts/combat_messages.tsv` | `tools/combat_messages.py` |
| Item descriptions | `script/en/items.tsv` | `tools/wrap_items.py` |
| Other names, menus, Help, monsters, and labels | matching `script/en/*.tsv` | `tools/overlays.py` and validation tools |

Do not shorten English to save ROM storage. Relocation handles storage; visible line
length and runtime substitutions are checked separately. Read the
[translation policy](docs/translation-policy.md) before changing control tokens such as
`<cF3>`, `<br>`, `<page>`, or `<box>`.

## Repository layout

| Path | Contents |
|---|---|
| `tools/` | Extraction, localization, insertion, validation, and diagnostic tools |
| `script/en/` | Tracked source-free production translation catalogs |
| `script/editing/` | Authoritative scene-ordered story editor |
| `script/drafts/` | Specialized item/combat drafts and generated prose input |
| `script/organized/` | Generated source-rich catalogs; ignored by Git |
| `tests/` | Unit, fixture, ROM-integration, and emulator tests |
| `assets/` | Font and future localization assets |
| `docs/` | Canonical project, engineering, translation, and workflow documentation |
| `build/` | Generated output; ignored by Git |

## Documentation

Start with the [documentation index](docs/README.md). In particular:

- [Current project status](docs/project-status.md)
- [Translation policy](docs/translation-policy.md)
- [Item terminology audit and review catalogue](docs/ITEM_TERMINOLOGY.md)
- [Story editing workflow](docs/editing-workflow.md)
- [Build and test guide](docs/testing-and-build.md)
- [Engineering overview](docs/engineering-overview.md)
- [Internal-text audit](docs/internal-text-audit.md)
- [Text/control reference](docs/TEXT_REFERENCE.md)
- [VWF budget register](docs/VWF_BUDGETS.md)
- [ROM and persistent-memory map](docs/ROM_BANK_MAP.md)
- [Menu architecture](docs/MENU_STRUCTURE.md)
- [Blank Scroll writing system](docs/BLANK_SCROLL.md)
- [Big Moai spell system and manual unlock route](docs/BIG_MOAI.md)
- [Wanderer Rescue password system](docs/RESCUE_SYSTEM.md)
- [Unidentified item naming and manual test route](docs/UNIDENTIFIED_ITEM_NAMING.md)
- [Dynamic item rows and visual gallery](docs/ITEM_FORMATTING.md)
- [Engineering rules](docs/ENGINEERING_RULES.md)
- [Known traps](docs/TRAPS.md)
- [Graphics localization](docs/GRAPHICS.md)
- [Graphical-text audit](docs/GRAPHICS_AUDIT.md)

Nothing under `docs/` is mandatory onboarding. This README plus
[`script/README.md`](script/README.md) is enough to build and to edit text; the detailed
files are references for the moment a measured rule or architecture decision matters.

## Known limits

- Extracted-reference completeness is not the same as full route coverage. Optional events,
  endings, postgame states, and navigation-history interactions still need playtesting.
- The current suite has strong static and focused emulator coverage but not GB1's mature
  release-battery matrix.
- Graphics localization is incomplete even though ordinary text and several generated menu
  templates are English.
- The six-character player-name extension preserves known Japanese saves, but uncommon save
  histories and every ranking category still deserve real-world testing.
- Automated layout checks cannot judge character voice, sentence rhythm, or visual taste.

## Contributing

Before changing text, read [`script/README.md`](script/README.md) and the
[translation policy](docs/translation-policy.md). Before changing ROM layout, renderers,
menus, input, fonts, or persistent data, read the [engineering rules](docs/ENGINEERING_RULES.md)
and [ownership map](docs/ROM_BANK_MAP.md).

Keep ROMs, generated ROMs, ordinary saves, unreviewed emulator states, credentials, and
extracted Japanese catalogs out of commits. A deliberately reviewed regression fixture such
as the explicitly reviewed `.mss` files under `SaveStates/` are exceptions, not a precedent
for committing personal states.
Add a focused regression for every reproducible bug and run the complete suite before
handing off a change.

## Licensing and ROM policy

Thin Pixel-7 licensing information is preserved in
[`licenses/Thin-Pixel-7.txt`](licenses/Thin-Pixel-7.txt). This repository does not
distribute the game ROM or complete extracted Japanese script catalogs.
