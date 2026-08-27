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
| Runtime-facing internal spell text | 200 | 200 |
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
- Six-character player names, default name `Shiren`, save compatibility metadata, and
  expanded ranking-result name storage.
- Four-character A-Z/0-9 Big Moai spell entry, with all 100 runtime codes and story
  clues synchronized.
- Scene-ordered prose editing and generated-cell ownership checks.
- Fixture-backed translation, layout, save-data, menu, and production-build tests.

## Remaining project work

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
`f849e819a7409d64fe3c08a3fa7218af593ad7d9`; always rebuild and verify locally rather
than treating that hash as a permanent release identifier.
