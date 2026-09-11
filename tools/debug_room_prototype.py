#!/usr/bin/env python3
"""Reproduce the accepted debug-menu audition from its frozen English baselines.

Normal builds use debug_menus directly. This compatibility wrapper keeps the
historical before/after audit reproducible without a second runtime implementation.
"""
import argparse
from hashlib import sha1
from pathlib import Path
import debug_menus
from debug_menus import BANK, START, END, HOOK_BANK, HOOK, EXPECTED_HOOK, offset

BASELINE_SHA1 = {
    "classic": "afca7145d4e68bfc2f1a762196b53a7df0072dc7",
    "shadowed": "3838dd39959ef075dfaf5a4c30363db6579573c2",
}


def install(rom):
    if sha1(rom).hexdigest() not in BASELINE_SHA1.values():
        raise ValueError("unreviewed baseline ROM; rebuild/review the prototype first")
    return debug_menus.install(rom)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.baseline.resolve() == args.output.resolve():
        parser.error("use a separate experimental output path")
    patched, report = install(args.baseline.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patched)
    print("Experimental main/category/weapons/bracelets/scrolls/pots/meat1/meat2/meat3/flags popups: %d/48, %d/48, %d/48, %d/48, %d/48, %d/48, %d/48, %d/48, %d/48, %d/48 tiles; %s"
          % (report["main_tiles_used"], report["tiles_used"], report["weapons_tiles_used"],
             report["bracelets_tiles_used"], report["scrolls_tiles_used"], report["pots_tiles_used"], report["meat1_tiles_used"], report["meat2_tiles_used"], report["meat3_tiles_used"], report["flags_tiles_used"], args.output))


if __name__ == "__main__":
    main()
