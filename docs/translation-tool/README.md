# GB2 translation tools

The [translation index](https://joey-astrologo.github.io/Shiren-GB2-Magic-Castle-of-the-Desert/translation-tool/index.html)
links to the [prose editor](https://joey-astrologo.github.io/Shiren-GB2-Magic-Castle-of-the-Desert/translation-tool/prose/).
The rescue password converter remains the site home page, with a translation-tools link
at the bottom. These URLs serve the new tools after the Pages workflow deploys this change.

This proof of concept follows the public GB1 tool's organization: a translation index,
scene navigation, Japanese beside the English draft, search, edited/error filters,
game-font previews, local drafts, and TSV import/export. GB2 has 1,768 entries in 72
project scenes. The single genuinely empty native slot is read-only. Japanese prose is
included in the catalogue, so visitors can start without selecting any files.

## Edit and download

Choose a scene and edit the English draft. Enter inserts `<br>`; Ctrl/Cmd+Enter inserts
`<page><box>`. Word wrapping is automatic; page and box boundaries are authored. The
preview uses the approved shadowed Thin Pixel-7 glyph pixels and advances, with GB2's
11px line advance. Shaded spans reserve the project's full runtime-width bounds.

Drafts, including invalid edits, are saved in browser storage. Storage errors are shown.
An incompatible saved draft is kept for recovery and editing is disabled until the user
downloads it or explicitly starts fresh. **Back up draft** downloads a JSON backup even
when an entry has errors or a large batch needs more ROM space. **Import edits** can
restore a compatible JSON backup, including unfinished entries. Download backups regularly.
There are no uploads, accounts, external fonts, package dependencies or backend services.

**Download changes** is enabled only when every edited entry passes validation. The file
contains changed entries only, each tied to its baseline and the rule revision. **Import
edits** restores a compatible download; unknown IDs, stale baselines and conflicting local
edits are rejected before any part of the file is merged. No generated scene metadata can
be edited or exported.

## Apply a download to the project

From the repository root, check the file and review its proposed diff:

```sh
ROM="Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
python3 tools/prose_web.py import "$ROM" /path/to/shiren-gb2-prose-changes.tsv
```

The importer reruns the Python wrapper, source/control rules, layout, terminology lint, ROM allocation,
and the full existing prose owner, including its generated-file conflict guards. It does
not write anything unless `--apply` is supplied. After reviewing the diff:

```sh
python3 tools/prose_web.py import "$ROM" /path/to/shiren-gb2-prose-changes.tsv --apply
python3 tools/prose_editor.py "$ROM" --apply
```

The first command updates only `script/editing/prose.tsv`, preserving its columns, scene
order and every unchanged row. The second synchronizes generated drafts and catalogs.
Then run the checks and production build in [testing-and-build.md](../testing-and-build.md),
and review the affected dialogue in game. Regenerate the public catalogue after accepted
edits. A download from an older baseline is rejected instead of overwriting newer work.

The changes format is:

```text
# format<TAB>shiren-gb2-prose-edits-v1
# revision<TAB>catalogue SHA-256
# rules<TAB>rule SHA-256
# base<TAB>stable ID<TAB>entry SHA-256
# id<TAB>english
stable ID<TAB>edited draft
```

`<TAB>` means a literal tab. UTF-8 BOMs and CRLF files are accepted. These are changes
files for the importer, not replacements for the full seven-column scene editor.

## Rule ownership and accuracy

`tools/prose_web.py export` derives the public data from the matching ROM and the existing
project owners. `prose/rules.js` implements the browser counterpart of `wrap_en.py`,
`layout.py` and `lint_en.py`, with the policy requirements below. No GB1 encoding, glyph
count, storage-slot limit or page-break rule is carried over.

The browser checks:

- The installed 79-character English font, permitted tokens and exact parameter grammar.
- Balanced word wrapping with the Python wrapper's minimum-line and tie-breaking rules.
- Composer width below 144px, renderer pen at most 144px, cumulative three-line box
  occupancy, bottom-row 8px glyph cells, and the 9px page marker on every row.
- Source page/box boundary order, including required post-wait line advances; new boxes
  need a preceding page wait. `<page>` does not reset either pen or line count.
- Exact runtime-substitution and effect counts/arguments, ordered native `<cF8>` selector
  runs, and required `<cF3>` checkpoints.
- Whitespace, sentence spacing across controls, ASCII quotes, project terminology,
  the reviewed prose glossary exception, and exact Big Moai story gift codes.
- Per-consumer runtime bounds from the full translated project. Missing bounds block
  validation. Player names have six visible characters; the current Python width contract
  conservatively reserves seven maximum-width glyphs (49px).
- Each record's encoded size and the complete script's bank packing, using the same
  table-first, next-fit placement as `allocate.py`. A storage failure blocks the changes
  TSV and asks for an allocator change; it is not a reason to remove meaning. Draft
  backups remain available.

The catalogue contains Python-generated expected layouts for every baseline. Tests compare
all of them with JavaScript, plus thousands of independently generated edited/invalid
cases covering width boundaries, controls, effects, runtime values, terms and pagination.
The Pages workflow refuses stale catalogue inputs or failed JavaScript comparisons.

Text checks cannot judge meaning, character voice, event timing, all gameplay routes, or
the final replacement of native `<cF8>` template selectors. Those entries display a
preview limitation. The browser does not build or emulate a ROM; the project importer,
production build and affected playtests remain the acceptance path.

## Regenerate, test and preview

Generation and independent Python comparisons use the project's matching local ROM.
Once generated, hosting and the JavaScript checks need no ROM. Japanese is intentionally
included only for this prose site; the raw extraction, ROM, saves and other local game
data are excluded from the Pages artifact.

```sh
python3 tools/prose_web.py export "$ROM"
python3 tools/prose_web.py export "$ROM" --check
python3 tools/prose_web.py check-assets
python3 -m unittest tests.test_prose_web -v
node tests/prose_web.test.mjs
python3 tools/build_pages.py
python3 -m http.server 8765 --bind 127.0.0.1 --directory build/pages
```

Open `http://127.0.0.1:8765/` for the rescue home, `/translation-tool/index.html` for the
translation index, or `/translation-tool/prose/` for the editor. Use HTTP rather than
opening the editor directly as a file: the browser loads its module and catalogue locally.

After an intentional rule or source change, regenerate and review the mutation oracles
with `python3 tests/test_prose_web.py --write-fixtures`, then rerun both suites. Do not
refresh fixtures to conceal a JavaScript/Python disagreement.

For browser interaction checks, stage with `python3 tools/build_pages.py --test`, serve
the same folder, and open `/checks.html` in an isolated browser profile. This exercises
typing, validation, included Japanese, preview navigation, downloads, file import,
autosave/reload, reset, stale-draft recovery and storage failures. The test restores
pre-existing saved data afterward and is excluded from normal Pages builds.

`tools/build_pages.py` stages an explicit allowlist in `build/pages`. The existing
rescue-converter Pages workflow tests and deploys the combined artifact; no new Pages
configuration is needed. Source changes that need a new catalogue fail deployment until
it has been regenerated locally with the ROM.

Thin Pixel-7 is by Sizenko Alexander (Style-7), adapted to the Game Boy cell. The required
credit appears in the editor guide and the bundled [font license](prose/font-license.txt).
