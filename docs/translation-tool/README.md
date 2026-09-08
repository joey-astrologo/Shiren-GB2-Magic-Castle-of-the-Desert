# GB2 translation tools

The [translation index](https://joey-astrologo.github.io/Shiren-GB2-Magic-Castle-of-the-Desert/translation-tool/index.html)
organizes all 6,695 extracted records into 12 subject workbenches. Japanese source
and current English load automatically. The rescue converter remains the hosted
home page, with a link to this translation index at the bottom.

The [workbench guide](workbench/README.md) explains editing, shared checks,
download/import and the reference-only cases. The [coverage page](coverage.html)
lists counts and the owners of graphics and code-generated text outside the script.
Prose retains all 72 project scenes. Each record has one primary subject; aliases
are counted once.

The workbenches share one browser draft. Names update runtime widths and
terminology checks throughout that draft; any affected invalid entry blocks
download. Classic and Shadowed previews use the installed game glyphs. Dialogue
uses the GB2 window; other subjects show their measured text canvas. Fixed engine
data and unconfirmed/composite surfaces remain visible with an explanation.

The [earlier standalone prose editor](prose/README.md) remains available at
[prose/](prose/). Its saved drafts and download format remain separate.

## Import workbench edits

With the matching local ROM and normal project build dependencies:

~~~sh
python3 tools/workbench_web.py import "$ROM" /path/to/shiren-gb2-workbench-changes.tsv
# After reviewing validation and the diff:
python3 tools/workbench_web.py import "$ROM" /path/to/shiren-gb2-workbench-changes.tsv --apply
~~~

The importer checks the entire prospective script with the Python owners,
terminology lint, runtime domains, menu/input checks and a complete in-memory
ROM build before writing. Apply synchronizes authoritative drafts, both catalogue
views and ownership states together. Then run the project's
[game acceptance checks](../testing-and-build.md).

## Regenerate, test and preview

~~~sh
python3 tools/prose_web.py export "$ROM"
python3 tools/workbench_web.py export "$ROM"
python3 tools/prose_web.py check-assets
python3 tools/workbench_web.py check-assets
python3 -m unittest tests.test_prose_web tests.test_workbench_web -v
node tests/prose_web.test.mjs
node tests/workbench_web.test.mjs
python3 tools/build_pages.py --test
python3 -m http.server 8765 --bind 127.0.0.1 --directory build/pages
~~~

Open the rescue home at port 8765, the translation index at
/translation-tool/index.html, and browser checks at /checks.html and
/workbench-checks.html. Use an isolated browser profile for the checks. Normal
packaging excludes test pages, raw extraction, ROMs and saves.

After intentional rule changes, regenerate and review independent fixtures with
the --write-fixtures option in tests/test_prose_web.py and
tests/test_workbench_web.py. The Pages workflow refuses stale snapshots or failed
Python/JavaScript comparisons. Publishing uses the existing Pages workflow.

Thin Pixel-7 by Sizenko Alexander (Style-7) is adapted to the Game Boy cell;
the [font credit and license](prose/font-license.txt) remain included.
