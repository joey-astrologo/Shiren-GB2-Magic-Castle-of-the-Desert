#!/usr/bin/env python3
"""Install the approved English title, native moon/bats, and subtitle sparkle."""

import argparse
from pathlib import Path

from cartridge import fix_checksums
import title_graphics
from title_graphics import TitleScreenError
import title_screen_runtime


RUNTIME_BANKS = (245, 246, 247)


def owned_ranges():
    """Exclusive byte ranges, with end offsets excluded."""
    hooks = title_graphics.recipe()["native_hooks"]
    ranges = [
        (
            title_graphics.offset(h["bank"], h["address"]),
            title_graphics.offset(h["bank"], h["address"])
            + len(bytes.fromhex(h["bytes"])),
        )
        for h in hooks
    ]
    return tuple(
        ranges + [(bank * 0x4000, (bank + 1) * 0x4000) for bank in RUNTIME_BANKS]
    )


def install(rom):
    """Return a guarded, deterministic, idempotent title-screen installation."""
    source = bytes(rom)
    plan = title_graphics.recipe()
    graphics = title_graphics.compile_graphics(source, plan)
    clean = bytearray(source)
    for bank in RUNTIME_BANKS:
        clean[bank * 0x4000 : (bank + 1) * 0x4000] = bytes(0x4000)
    generated, _metrics = title_screen_runtime.build(clean, graphics)
    for hook in plan["native_hooks"]:
        start = title_graphics.offset(hook["bank"], hook["address"])
        expected = bytes.fromhex(hook["bytes"])
        end = start + len(expected)
        if source[start:end] not in (expected, generated[start:end]):
            raise TitleScreenError(
                "title hook changed at %02X:%04X" % (hook["bank"], hook["address"])
            )
    for bank in RUNTIME_BANKS:
        start, end = bank * 0x4000, (bank + 1) * 0x4000
        if source[start:end] not in (bytes(0x4000), generated[start:end]):
            raise TitleScreenError("title runtime bank %d is already occupied" % bank)
    output = bytearray(generated)
    fix_checksums(output)
    return bytes(output)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        output = install(args.rom.read_bytes())
    except (OSError, TitleScreenError) as error:
        parser.exit(1, "title screen: %s\n" % error)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output)
    print("Installed localized title: %s" % args.output)


if __name__ == "__main__":
    main()
