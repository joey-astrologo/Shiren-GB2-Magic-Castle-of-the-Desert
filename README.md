# Shiren GB2 — English translation

**Made with AI assistance.**

This is a personal, unofficial English localization of *Fushigi no Dungeon:
Fuurai no Shiren GB2 — Sabaku no Majou* (Chunsoft, Game Boy Color, 2001). It is not
affiliated with or endorsed by the original developers or publishers.

This repository contains the translation, graphics assets, build tools, and tests. It does
not contain the game ROM or complete extracted Japanese script. You must supply your own
matching Japanese cartridge dump.

## Project status

| Area | State | Remaining work |
|---|---|---|
| Text | **Translation pass complete** | All 5,667 production records have explicit English or intentional empty values; editorial review and playtesting continue |
| Menus and input | **Complete for known routes** | Player names, Rankings notes, Big Moai codes, Blank Scrolls, unidentified-item naming, service menus, and known system screens are localized and fixture-tested |
| Fonts | **Complete** | Builds are available with either the classic black-only Thin Pixel-7 font or the approved gray-shadowed variant |
| Graphics | **In progress** | Copyright card, arrival cards, save/load sign, and dungeon-HUD digits/labels/slash are installed; the title and ending credits remain |
| Wanderer Rescue | **Protocol and English I/O tested** | The complete physical Rescue Gate and two-diary route still needs capture |
| Automated tests | **562 tests passing — 2026-09-04** | Continue adding focused regressions for issues found during playtesting |

Translation completion is not release completion. Optional events, endings, postgame
states, uncommon save histories, and rare visual interactions still need manual testing.
See [project status](docs/project-status.md) for the detailed coverage and current artifact
hashes.

## Requirements

- Python 3.9 or newer.
- A clean Japanese ROM matching:
  - Size: `4194304` bytes
  - SHA-1: `5264f6d0c4f12c9144de1d12fddadbadd82b3e33`
  - MD5: `9e3d4ff0ba3d6deec5080f6dbed4fef8`
- [PyBoy](https://github.com/Baekalfen/PyBoy) and Pillow for the complete emulator and
  graphics test suite.
- RGBDS for optional assembly-source equivalence tests.

Install the Python dependencies with:

```sh
python3 -m pip install pyboy pillow
```

The normal ROM build itself uses only Python's standard library.

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

## Edit the translation

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

ROM-dependent tests skip when the matching source ROM is absent. PyBoy and RGBDS checks
also skip when their dependencies are unavailable. All automated emulator routes use native
PyBoy `.state` fixtures; Mesen is not required.

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
python3 tools/hud_font_audition.py
python3 tools/shop_price_font_audition.py
```

The audition commands write review images under `build/` and do not modify the input ROM.
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
