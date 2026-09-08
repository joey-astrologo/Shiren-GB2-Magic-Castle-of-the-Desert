#!/usr/bin/env python3
"""Stage the rescue home page and translation tools using a public-file allowlist."""
from pathlib import Path
import argparse
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build/pages"
RESCUE_FILES = ("index.html", "style.css", "page.js", "i18n.js", "converter.js", "password-data.js")
TRANSLATION_FILES = ("index.html", "style.css", "prose/index.html", "prose/style.css",
                     "prose/app.js", "prose/rules.js", "prose/catalog.json", "prose/font-license.txt")


def build(output=OUTPUT):
    output = Path(output)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    for name in RESCUE_FILES:
        shutil.copyfile(ROOT / "docs/rescue-converter" / name, output / name)
    for name in TRANSLATION_FILES:
        destination = output / "translation-tool" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "docs/translation-tool" / name, destination)
    print("Pages artifact: %s" % output)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true", help="include the local browser test page")
    args = parser.parse_args()
    output = build()
    if args.test:
        shutil.copyfile(ROOT / "tests/prose_web.browser.html", output / "checks.html")
