# Shiren GB2 — English translation

**Made with AI assistance.**

This is a personal, unofficial English localization of *Fushigi no Dungeon:
Fuurai no Shiren GB2 — Sabaku no Majou* (Chunsoft, Game Boy Color, 2001). It is not
affiliated with or endorsed by the original developers or publishers.

This repository contains the translation, graphics assets, build tools, and tests. The
browser tools include Japanese text for reference. The game ROM is not included; local
builds and imports require your own matching Japanese cartridge dump.

## Project status

**The opening menu/title-screen artwork is the only remaining localization work.**
Story and gameplay text, in-game menus, input screens, and the other localized graphics
are implemented. Both font variants have passed the complete test suite and release checks.

| Area | State | Details |
|---|---|---|
| Text | **Complete** | All 5,679 production records have explicit English or intentional empty values |
| In-game menus and input | **Complete** | Player names, Rankings notes, Big Moai codes, Blank Scrolls, unidentified-item naming, service menus, and system screens are localized and fixture-tested |
| Fonts | **Complete** | Builds are available with either the classic black-only Thin Pixel-7 font or the approved gray-shadowed variant |
| Opening menu/title screen | **Localization remaining** | English replacement artwork and insertion |
| Other graphics | **Implemented** | Copyright card, main-ending staff title and all 20 staff cards, arrival cards, save/load sign, and dungeon-HUD digits/labels/slash are installed |
| Wanderer Rescue | **English input/output implemented and tested** | Native password compatibility, promotional mission acceptance, and Japanese ↔ English conversion are verified |
| Automated verification | **649 suite tests + 34 release-battery checks passed — 2026-09-08** | Zero failures, errors, or skips; both fonts rebuilt identically from a fresh local clone, with IPS application and save/reload verified |

Playtesting and bug fixes continue. See [project status](docs/project-status.md) for
verification coverage, the remaining manual route checks, and current artifact hashes.

## Requirements

- Python 3.9 or newer.
- A clean Japanese ROM matching:
  - Size: `4194304` bytes
  - SHA-1: `5264f6d0c4f12c9144de1d12fddadbadd82b3e33`
  - MD5: `9e3d4ff0ba3d6deec5080f6dbed4fef8`
- [PyBoy](https://github.com/Baekalfen/PyBoy) and Pillow for the complete emulator and
  graphics test suite.
- RGBDS for optional assembly-source equivalence tests.
- Node.js for the browser rescue-converter and prose-rule parity tests.

Install the Python dependencies with:

```sh
python3 -m pip install pyboy pillow
```

The normal ROM build uses Pillow to reproduce the approved main-ending credit rasters from
their licensed Inter source font.

## Build

From the repository root, point `ROM` at the clean Japanese game and run the production
builder:

```sh
ROM="Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"

python3 tools/build.py \
  "$ROM" \
  script/en \
  build/shiren-gb2-english.gbc \
  --font-style both
```

This validates the source, translation, runtime substitutions, layouts, ROM ownership,
installed graphics, relocated text, and cartridge checksums before writing:

| Output | Font style |
|---|---|
| `build/shiren-gb2-english-classic-font.gbc` | Black-only Thin Pixel-7 |
| `build/shiren-gb2-english-classic-font.ips` | IPS patch for the classic build |
| `build/shiren-gb2-english-shadowed-font.gbc` | Gray `+1,+1` shadowed Thin Pixel-7 |
| `build/shiren-gb2-english-shadowed-font.ips` | IPS patch for the shadowed build |

Use `--font-style classic` or `--font-style shadowed` to produce only one variant. The
single-output default is `shadowed`. Every generated IPS is reapplied in memory and must
reconstruct its paired ROM exactly before it is written.

To use a release patch, apply the desired `.ips` to an untouched ROM with the hashes above
using an IPS-compatible patcher. Do not apply both font patches to the same ROM.

ROMs, patches, saves, and generated files under `build/` are ignored by Git.

## Rescue passwords and special missions

**[Open the rescue password converter](https://joey-astrologo.github.io/Shiren-GB2-Magic-Castle-of-the-Desert/)**

Convert GB2 passwords between Japanese and this English patch, with checksum checks
and presets for the three original guidebook rescue missions. Choose **English** or
**日本語** for the interface using the language selector. No ROM or account is needed.

The [special rescue mission guide](docs/SPECIAL_RESCUE_MISSIONS.md) explains the codes
and how to enter them. An [offline browser copy](docs/rescue-converter/index.html) and
[Python converter](tools/rescue_converter.py) are also included. See the
[website maintenance guide](docs/rescue-converter/README.md) for GitHub Pages deployment.

The rescue page also links to the hosted translation tools. See [Edit the translation](#edit-the-translation)
below for browser editing and importing downloaded changes into this project.

## Edit the translation

### Use the hosted editor

**[Open the GB2 translation tools](https://joey-astrologo.github.io/Shiren-GB2-Magic-Castle-of-the-Desert/translation-tool/index.html)**

Choose a subject workbench and a scene or group. Japanese source and the current English
are included, so browser editing needs no ROM or script upload. Edit the English and review
the immediate GB2 rule checks and game-font preview. **Preview font** switches between
Classic and Shadowed; clickable codes open the
[control code reference](https://joey-astrologo.github.io/Shiren-GB2-Magic-Castle-of-the-Desert/translation-tool/controls/).
Fixed or unconfirmed entries remain visible with an explanation.

All subjects share a draft saved in this browser. Use **Needs attention** to resolve errors,
including other entries affected by a name change. **Download changes** produces a TSV of
your edits once all checks pass. **Back up draft** saves unfinished work as JSON, and
**Import edits** reopens compatible TSV downloads or JSON backups in the browser.

### Import downloaded edits into the project

Use `tools/workbench_web.py` with a local checkout, the [build dependencies](#requirements)
and your matching Japanese ROM. From the repository root, check the downloaded TSV first:

```sh
ROM="Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
EDITS="/path/to/shiren-gb2-workbench-changes.tsv"

python3 tools/workbench_web.py import "$ROM" "$EDITS"
```

This prints the proposed diff and validates the full prospective script, including runtime
substitutions, terminology, layouts, draft owners and an in-memory ROM build. It changes no
project files. Downloads carry their rule version and original-entry baselines; incompatible
or stale downloads are rejected rather than overwriting current work.

After reviewing the successful check and diff, apply the same download:

```sh
python3 tools/workbench_web.py import "$ROM" "$EDITS" --apply
```

The importer updates the appropriate authoritative TSVs, generated text and ownership
records together. Then refresh both browser catalogues:

```sh
python3 tools/prose_web.py export "$ROM"
python3 tools/workbench_web.py export "$ROM"
```

Review the resulting `git diff`, [build the patched ROM](#build), and run the affected
[tests and in-game checks](docs/testing-and-build.md). The browser preview cannot judge
translation meaning or event behavior. JSON backups are for reopening in the browser;
the project importer takes the **Download changes** TSV.

See the [workbench guide](docs/translation-tool/workbench/README.md#download-and-project-import)
for details. Downloads from the earlier standalone prose editor use its
[separate importer](docs/translation-tool/prose/README.md#apply-a-download-to-the-project).

### Use the full spreadsheet dump

[`script/translator-review.tsv`](script/translator-review.tsv) contains all extracted
records with Japanese, inserted English and a blank `edited_en` column. Edit that
column, then use its separate checker/importer:

```sh
# Validate and inspect the diff without writing.
python3 tools/import_script_sheet.py "$ROM" /path/to/returned-review.tsv
# Insert into a separate test ROM and IPS; keep project translations unchanged.
python3 tools/import_script_sheet.py "$ROM" /path/to/returned-review.tsv --output build/sheet-review.gbc
# Apply approved edits to the authoritative project files.
python3 tools/import_script_sheet.py "$ROM" /path/to/returned-review.tsv --apply
```

Keep all rows and baseline columns unchanged. The [spreadsheet guide](script/translator-review.md)
covers font variants, validation, refreshing catalogues and exporting the next sheet.

### Edit local TSV files

Generate or refresh the ignored source-rich reference catalogs from your own ROM with:

```sh
python3 tools/extract.py "$ROM" --out script
python3 tools/organize.py "$ROM"
python3 tools/overlays.py "$ROM"
```

`overlays.py` synchronizes English cells between `script/organized/` and the tracked
`script/en/` workspace. It stops on conflicting nonblank values instead of choosing one.

Story and event dialogue is authored in the scene-ordered
[`script/editing/prose.tsv`](script/editing/prose.tsv):

```sh
python3 tools/prose_editor.py "$ROM"          # validate without writing
python3 tools/prose_editor.py "$ROM" --apply  # wrap and synchronize approved edits
```

Other text families have separate owners:

| Text | Authoritative file | Validation or synchronization tool |
|---|---|---|
| Names and terminology | `script/en/glossary.tsv` | `tools/overlays.py` and `tools/lint_en.py` |
| Story and event dialogue | `script/editing/prose.tsv` | `tools/prose_editor.py` |
| Dungeon item/action messages | `script/drafts/item_messages.tsv` | `tools/wrap_item_messages.py` |
| Combat and gameplay messages | `script/drafts/combat_messages.tsv` | `tools/combat_messages.py` |
| Item descriptions | `script/en/items.tsv` | `tools/wrap_items.py` |
| Menus, Help, monsters, and other labels | Matching `script/en/*.tsv` | `tools/overlays.py` and the production build |

The source-rich files under `script/organized/` are generated references. It is safe to edit
their `english` cells while consulting Japanese context, but run `tools/overlays.py` to copy
those changes into the tracked `script/en/` workspace. Story prose is the exception: edit it
only through `script/editing/prose.tsv`.

Do not remove or casually reorder controls such as `<lookup:...>`, `<number:...>`, `<name>`,
`<speaker>`, `<br>`, `<page>`, or `<box>`. They carry runtime behavior. Read the
[translator guide](script/README.md) and [translation policy](docs/translation-policy.md)
before changing them.

## Run the tests

Run the complete suite from the repository root:

```sh
python3 -m unittest discover -s tests -v
```

ROM-dependent tests skip when the matching source ROM is absent. PyBoy, RGBDS, and Node.js
checks also skip when their dependencies are unavailable. The browser parity test uses
`node` on PATH or an executable path in `SHIREN_NODE`. All automated emulator routes use
native PyBoy `.state` fixtures; Mesen is not required.

Useful focused checks:

```sh
# Production build and relocated text
python3 -m unittest tests.test_build tests.test_insert -v

# Translation, terminology, and layout checks
python3 tools/internal_audit.py "$ROM"
python3 tools/lint_en.py "$ROM"
python3 tools/runtime_widths.py "$ROM"

# Graphics inventory and audition tools
python3 tools/graphics_audit.py "$ROM"
python3 tools/font_shadow_audition.py
python3 tools/arrival_card_audition.py
python3 tools/ending_credits_audition.py
python3 tools/hud_font_audition.py
python3 tools/shop_price_font_audition.py
```

The audition commands write review images under `build/` and do not modify the input ROM.
The ending-credits command uses `SaveStates/ending-one.state` to pair the captured staff-roll title
and all 20 main-ending cards with the same English rasters installed by the production builder.
They use the opening copyright screen's font and palette treatment; the Japanese end mark is
intentionally preserved.
See the [build and test guide](docs/testing-and-build.md) for feature-specific tests,
fixture routes, and every diagnostic command.

## Repository map

| Path | Contents |
|---|---|
| `tools/` | Extraction, editing, insertion, validation, graphics, and diagnostic tools |
| `script/en/` | Tracked source-free production English catalogs |
| `script/editing/` | Authoritative scene-ordered story editor |
| `script/drafts/` | Specialized item, combat, and generated prose worksheets |
| `script/organized/` | Generated source-rich catalogs; ignored by Git |
| `assets/` | Approved font and graphics sources |
| `SaveStates/` | Reviewed fixture states and conversion provenance |
| `tests/` | Unit, ROM-integration, pixel, and PyBoy route tests |
| `docs/` | Detailed project, translation, graphics, and engineering references |
| `build/` | Generated ROMs, IPS patches, and audition images; ignored by Git |

## Documentation

Start with the [documentation index](docs/README.md). The most commonly needed references
are:

- [Detailed project status](docs/project-status.md)
- [Build and test guide](docs/testing-and-build.md)
- [Translation policy](docs/translation-policy.md)
- [Text and control reference](docs/TEXT_REFERENCE.md)
- [VWF and surface budgets](docs/VWF_BUDGETS.md)
- [Graphics localization](docs/GRAPHICS.md)
- [ROM ownership map](docs/ROM_BANK_MAP.md)
- [Engineering rules](docs/ENGINEERING_RULES.md)
- [Known traps](docs/TRAPS.md)

The root README and [`script/README.md`](script/README.md) are enough to build and edit the
project. The detailed documents are references for the feature or subsystem being changed.

## Contributing

Add the narrowest useful regression for every reproducible bug. Run the focused test while
iterating and the complete suite before handing off a player-visible or ROM-layout change.
Visual changes should include an audition image or screenshot when practical.

Before changing ROM layout, renderers, menus, fonts, input, or persistent data, read the
[engineering rules](docs/ENGINEERING_RULES.md) and [ROM ownership map](docs/ROM_BANK_MAP.md).

Do not commit ROMs, generated patches, personal saves, credentials, or complete extracted
Japanese catalogs. The reviewed fixture states under `SaveStates/` are deliberate project
test data, not a precedent for committing unrelated emulator states.

## Licensing and ROM policy

Thin Pixel-7 licensing information is preserved in
[`licenses/Thin-Pixel-7.txt`](licenses/Thin-Pixel-7.txt). Other third-party components remain
subject to the notices under [`licenses/`](licenses/). This project is distributed as tools,
translation data, and original localization assets only; you must supply your own original
game dump.
