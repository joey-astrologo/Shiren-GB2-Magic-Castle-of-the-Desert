#!/usr/bin/env python3
"""Reproduce foundational ROM/text triage numbers straight from the ROM.

The maintained conclusions live in ``docs/engineering-overview.md`` and
``docs/ROM_BANK_MAP.md``.

This is a reporting tool, not the extractor. The control dispatcher is solved, so these
counts are renderer-aware; a separate pointer-based extractor must still identify referenced
records and aliases before this candidate census becomes the translation corpus.

    textdump.py <rom> --space    free banks and filler runs
    textdump.py <rom> --volume   script volume, banks 192-205
    textdump.py <rom> --sample   decoded dialogue
    textdump.py <rom> --kanji    two-byte code census
    textdump.py <rom> --controls control-code census
"""
import sys
from collections import Counter

sys.path.insert(0, __file__.rsplit('/', 1)[0])
import codec

# Bank 206 is the 15 KiB prefixed font store at 206:$4000, not script. The initial
# density census included it and admitted 122 font-art records as false strings.
SCRIPT_BANKS = range(192, 206)
BANK = 0x4000


def _banks(d):
    return [d[b * BANK:(b + 1) * BANK] for b in range(len(d) // BANK)]


def _dialogue(d):
    """Japanese strings in the script banks. 55% threshold keeps binary tables out."""
    for bank in SCRIPT_BANKS:
        blk = d[bank * BANK:(bank + 1) * BANK]
        for off, s in codec.strings(blk, bank * BANK, 6):
            if sum(1 for x in s if 0x30 <= x < 0xD0) >= len(s) * 0.55:
                yield off, s


def _glyphs(s):
    """Rendered source glyphs; controls and argument bytes consume no cells."""
    return sum(token.kind in ('glyph', 'kanji') for token in codec.parse(s))


def space(d):
    free = [i for i, b in enumerate(_banks(d)) if not any(b)]
    print('fully free banks: %d  (%.0f KiB)' % (len(free), len(free) * 16))
    rng, start, prev = [], free[0], free[0]
    for v in free[1:]:
        if v != prev + 1:
            rng.append((start, prev))
            start = v
        prev = v
    rng.append((start, prev))
    print('  ' + ', '.join(str(a) if a == b else '%d-%d' % (a, b) for a, b in rng))

    runs, i, n = [], 0, len(d)
    while i < n:
        j = i
        while j + 1 < n and d[j + 1] == d[i]:
            j += 1
        if j - i + 1 >= 64:
            runs.append((j - i + 1, i, d[i]))
        i = j + 1
    print('filler runs >=64 bytes: %d, totalling %.0f KiB'
          % (len(runs), sum(r[0] for r in runs) / 1024))
    for L, o, b in sorted(runs, reverse=True)[:5]:
        bank = o // BANK
        print('  %7d B  0x%06X  bank %3d:$%04X  fill %02X'
              % (L, o, bank, (o % BANK) + (BANK if bank else 0), b))


def volume(d):
    n = g = dn = dg = 0
    for _, s in _dialogue(d):
        gl = _glyphs(s)
        n += 1
        g += gl
        if any(x in (0xFB, 0xFC, 0xFD) for x in s) and gl >= 20:
            dn += 1
            dg += gl
    print('banks 192-205')
    print('  Japanese strings      %6d   (~%d rendered glyphs)' % (n, g))
    print('  multi-line dialogue   %6d   (~%d glyphs)' % (dn, dg))
    print('  names / menus / items %6d   (~%d glyphs)' % (n - dn, g - dg))
    print('\nGB1 for scale: 1,264 strings / 32,548 JP chars.')


def sample(d, count=12):
    ss = sorted(_dialogue(d), key=lambda t: -_glyphs(t[1]))
    shown = 0
    for off, s in ss:
        txt = codec.decode(s)
        if txt.count('<speaker>') < 2:   # prefer real conversation over tables
            continue
        print('0x%06X (%d glyphs)\n  %s\n' % (off, _glyphs(s), txt[:400]))
        shown += 1
        if shown >= count:
            break


def kanji(d):
    c = Counter()
    for _, s in _dialogue(d):
        for token in codec.parse(s):
            if token.kind == 'kanji':
                c[tuple(token.raw)] += 1
    mapped = {code: count for code, count in c.items() if bytes(code) in codec.KANJI}
    actual = {code: count for code, count in mapped.items()
              if codec.KANJI_KIND[bytes(code)] == 'kanji'}
    symbols = {code: count for code, count in mapped.items()
               if codec.KANJI_KIND[bytes(code)] != 'kanji'}
    continuations = {code: count for code, count in c.items()
                     if bytes(code) not in codec.KANJI}
    print('reviewed kanji: %d codes   occurrences: %d' % (len(actual), sum(actual.values())))
    print('prefixed symbols/tokens: %d codes   occurrences: %d'
          % (len(symbols), sum(symbols.values())))
    print('binary continuation slices: %d codes   occurrences: %d'
          % (len(continuations), sum(continuations.values())))
    print('speaker separator F224: %d' % c[codec.SPEAKER])
    for p in sorted(codec.KANJI_PREFIX):
        sec = [k[1] for k in actual if k[0] == p]
        if sec:
            print('  prefix %02X: %3d distinct, second byte %02X-%02X'
                  % (p, len(sec), min(sec), max(sec)))
    print('  no prefix takes FF as second byte:', not any(k[1] == 0xFF for k in c))
    print('\nmost frequent reviewed kanji:')
    print('  ' + '  '.join('%sx%d' % (codec.KANJI[bytes(k)], v)
                          for k, v in Counter(actual).most_common(10)))
    print('\nunmapped slices (all width 1-3):')
    print('  ' + ' '.join('%02X%02X' % k for k in sorted(continuations)))


def controls(d):
    c = Counter()
    arguments = {code: Counter() for code in codec.CONTROLS}
    for _, s in _dialogue(d):
        for token in codec.parse(s):
            if token.kind != 'control':
                continue
            c[token.code] += 1
            if token.args:
                arguments[token.code][token.args.hex().upper()] += 1
    print('dispatcher 0:$3657; table 0:$3671')
    for code in sorted(codec.CONTROLS):
        target = {
            0xF3: 0x3858, 0xF7: 0x3863, 0xF8: 0x387D,
            0xF9: 0x387F, 0xFA: 0x36B6, 0xFB: 0x3751,
            0xFC: 0x386C, 0xFD: 0x382F, 0xFE: 0x3858,
        }[code]
        arity = codec.CONTROL_ARITY.get(code, 0)
        suffix = ''
        if arguments[code]:
            suffix = '  args ' + ', '.join(
                '%s×%d' % item for item in arguments[code].most_common(8)
            )
        print('  %02X  %-6s  -> $%04X  args %d  count %d%s'
              % (code, codec.CONTROLS[code], target, arity, c[code], suffix))


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    d = open(sys.argv[1], 'rb').read()
    mode = sys.argv[2]
    fn = {'--space': space, '--volume': volume, '--sample': sample,
          '--kanji': kanji, '--controls': controls}
    if mode not in fn:
        sys.exit(__doc__)
    fn[mode](d)


if __name__ == '__main__':
    main()
