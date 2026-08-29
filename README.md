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
font, six-character player names, a localized four-character spell editor, and a fully
English Blank Scroll writer. The unidentified-item Name screen and its cycling `FILL IN`
history recall are also localized, including a 14-character preview and full display of
canonical names longer than the native seven-character custom-label field. Recalled names
show no star padding and reset safely to ordinary free entry on typing or `DEL`.
Its private navigation graph is isolated from the native Adventure submenu, whose
Continue/Secrets/Reset/Recap cursor route is replayed from a real save fixture.
All fourteen title/demo and Wanderer's Secrets replay diaries also carry the localized
six-character default name `Shiren`; they no longer fall back to their embedded Japanese
snapshot name.
The cracked-Bracelet suffix is also localized from the stock Japanese `(hibi)` composite
to a compact `(Cr)` marker and replayed from the supplied failure state. Native dynamic
item rows now emit English arrow quantities, signed equipment modifiers, staff/Pot brackets,
and spaced Gitan amounts; a two-page Mesen gallery covers their status-symbol combinations,
and a native Synthesis Pot lab provides a repeatable transferred-seal visual route.
Editorial review, full playthrough testing, and graphics localization remain active
project work.

## Current state

| Area | State | Remaining work |
|---|---|---|
| Extracted player-facing text | **Translation pass complete** | All 5,467 records have explicit English/empty values; continue editorial and route review |
| Internal runtime text | **Complete** | 200 spell-runtime records translated; 1,028 engine-only identifiers deliberately native |
| Story organization | **Complete** | 1,768 dialogue records in 72 scene families; complete editorial read-through remains |
| Font and text storage | **Engineered** | Thin Pixel-7 native VWF and 19-bank far-pointer payload pass current contracts |
| Menus and system text | **Complete for mapped text routes** | Continue discovering transition-history and rare-route visual issues in playtesting |
| Graphical input | **Engineered** | Player names/rankings/replay snapshots, spells, Blank Scroll writing, and unidentified-item Name / `FILL IN` are fixture-tested |
| Graphics | **In progress** | Cracked-Bracelet marker plus generated input/status assets are localized; complete the remaining graphical-Japanese inventory, replacement art, insertion, and visual QA |
| Automated tests | **371-test fixture suite passing** | Expand rare live routes and create a release-battery workflow comparable to GB1 |

Translation completion is not release completion. The script still needs a complete
editorial and gameplay pass, and graphical assets still require full localization.

## Requirements

- Python 3.9 or newer.
- A legally obtained clean Japanese ROM matching:
  - SHA-1: `5264f6d0c4f12c9144de1d12fddadbadd82b3e33`
  - MD5: `9e3d4ff0ba3d6deec5080f6dbed4fef8`
- PyBoy is optional but recommended for emulator-backed integration tests.
- Pillow is optional for font and graphics inspection tools.
- RGBDS is optional; when installed, the tests reassemble the name, spell-input, Blank
  Scroll, and unidentified-name patches and compare them byte-for-byte with the embedded
  production payloads.

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
  build/shiren-gb2-english.gbc
```

The output is `build/shiren-gb2-english.gbc`. The builder automatically validates the
source ROM, translation controls and terminology, runtime-value widths, positioned text,
far-pointer allocation, installed font and patches, all 7,163 logical text references,
and both cartridge checksums before writing the ROM.

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

# Graphical input: names, spells, Blank Scroll writing, and unidentified items
python3 -m unittest \
  tests.test_save_summary \
  tests.test_name6 \
  tests.test_spell_input \
  tests.test_blank_scroll \
  tests.test_mesen_blank_scroll \
  tests.test_unidentified_names \
  tests.test_mesen_unidentified_item \
  tests.test_item_status \
  tests.test_item_formatting \
  tests.test_synthesis_lab
```

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
- [Unidentified item naming and manual test route](docs/UNIDENTIFIED_ITEM_NAMING.md)
- [Dynamic item rows and visual gallery](docs/ITEM_FORMATTING.md)
- [Engineering rules](docs/ENGINEERING_RULES.md)
- [Known traps](docs/TRAPS.md)
- [Graphics localization](docs/GRAPHICS.md)

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
