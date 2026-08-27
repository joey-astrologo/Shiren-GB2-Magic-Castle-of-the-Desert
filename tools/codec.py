#!/usr/bin/env python3
"""Canonical Shiren GB2 text codec. decode(bytes) -> str, encode(str) -> bytes.

This is NOT the GB1 codec with new numbers. Three things genuinely differ, and each one
changes the design:

* Voiced kana are PRECOMPOSED. One byte is が. GB1 stored dakuten as a byte that modified
  the PRECEDING kana, so its codec had to NFD/NFC round-trip combining marks. None of that
  machinery is needed or wanted here.

* There are KANJI, via two-byte codes with prefix F0/F1/F2. GB1 was pure kana. The reviewed
  table in data/kanji.tsv maps all 281 prefixed glyphs in the authoritative pointer corpus:
  270 kanji, four symbols and seven named/composite tokens. Invalid continuation-slice codes
  found only in binary false positives stay raw rather than becoming guessed characters.

* Latin codes already exist at 0x0A. Their source semantics are lowercase, but the stock
  glyphs are visually uppercase A-Z. GB1 had to build an alphabet from a partial set.

Design rules carried over from GB1 because they were right there:

* Anything not positively identified becomes a `<XX>` token rather than a guess, so a byte
  we do not understand still survives a decode/encode cycle untouched.
* Control codes become named tokens so they are obvious in a translation file and cannot be
  silently deleted by an editor.

There are two deliberately separate parsers. ``parse`` models bytes after staging, as seen by
the renderer. ``parse_source`` models the ROM-side composer at 0:$312B, where F4-F6 consume
arguments and expand runtime values before the renderer sees them. Conflating those stages
would make an F5 argument byte equal to FF look like a record terminator.

Everything below is evidence-backed; see ``docs/TEXT_REFERENCE.md`` and
``docs/engineering-overview.md`` for the maintained explanation.
"""
import re
import sys
from dataclasses import dataclass
from pathlib import Path

HIRAGANA = 'あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん'
KATAKANA = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン'

# NOTE the order: small tsu comes BEFORE the small ya/yu/yo, which is not GB1's order.
# Settled statistically, not assumed -- 0x63 is preceded by an i-row kana only 4% of the
# time while 0x64/0x65/0x66 are 75%/82%/72%, and their top predecessors are literally
# じゃ/ちゃ/しゃ, しゅ/きゅ/じゅ, じょ/しょ/ちょ.
SMALL_HIRA = 'ぁぃぅぇぉっゃゅょ'
SMALL_KATA = 'ァィゥェォッャュョ'

VOICED_HIRA = 'がぎぐげござじずぜぞだぢづでどばびぶべぼ'
SEMI_HIRA = 'ぱぴぷぺぽ'
VOICED_KATA = 'ガギグゲゴザジズゼゾダヂヅデドバビブベボ'
SEMI_KATA = 'パピプペポ'

# ---- character table -----------------------------------------------------
CHARS = {}
for _i, _c in enumerate('0123456789'):
    CHARS[0x00 + _i] = _c
for _i, _c in enumerate('abcdefghijklmnopqrstuvwxyz'):
    CHARS[0x0A + _i] = _c
CHARS[0x24] = ' '
for _i, _c in enumerate(HIRAGANA):
    CHARS[0x30 + _i] = _c          # 0x30..0x5D
for _i, _c in enumerate(SMALL_HIRA):
    CHARS[0x5E + _i] = _c          # 0x5E..0x66
for _i, _c in enumerate(VOICED_HIRA):
    CHARS[0x67 + _i] = _c          # 0x67..0x7A
for _i, _c in enumerate(SEMI_HIRA):
    CHARS[0x7B + _i] = _c          # 0x7B..0x7F
for _i, _c in enumerate(KATAKANA):
    CHARS[0x80 + _i] = _c          # 0x80..0xAD
for _i, _c in enumerate(SMALL_KATA):
    CHARS[0xAE + _i] = _c          # 0xAE..0xB6
for _i, _c in enumerate(VOICED_KATA):
    CHARS[0xB7 + _i] = _c          # 0xB7..0xCA
for _i, _c in enumerate(SEMI_KATA):
    CHARS[0xCB + _i] = _c          # 0xCB..0xCF

# Punctuation, read off real dialogue and checked against the located font.
# 0xD9 earns its place loudly: モンスター, パワー, ケーブル only decode with it.
CHARS.update({0x2C: '、', 0xD1: '。', 0xD3: '？', 0xD4: '！', 0xD9: 'ー',
              0xDC: '「', 0xDD: '」'})

# ---- kanji ---------------------------------------------------------------
# Two-byte glyph codes. The density census sees 280 pairs, but font width metadata proves
# only 236 are valid glyph starts; the other 44 are width-1..3 continuation slices reached
# only from binary false positives. The reviewed valid set is loaded below.
KANJI_PREFIX = frozenset((0xF0, 0xF1, 0xF2))

# 0xF224 is NOT a kanji. It is an opening speaker quote/separator and sits immediately
# after speaker names. F226 is its closing counterpart. Both stay named tokens because
# the one-byte font also contains Japanese corner quotes and the encodings must not alias.
# English dialogue replaces an unmatched speaker separator with ``: ``; paired tokens may
# still quote an in-game label when that presentation is intentionally retained.
SPEAKER = (0xF2, 0x24)


def _load_kanji_table():
    """Load the reviewed two-byte glyph table and reject ambiguous reverse mappings."""
    path = Path(__file__).resolve().parents[1] / 'data' / 'kanji.tsv'
    lines = path.read_text(encoding='utf-8').splitlines()
    if not lines or lines[0] != 'code\ttext\tkind\tevidence':
        raise ValueError('bad kanji table header in %s' % path)
    table = {}
    kinds = {}
    for line_number, line in enumerate(lines[1:], 2):
        fields = line.split('\t')
        if len(fields) != 4:
            raise ValueError('bad kanji row %d in %s' % (line_number, path))
        code_text, text, kind, _evidence = fields
        try:
            code = bytes.fromhex(code_text)
        except ValueError as exc:
            raise ValueError('bad kanji code on row %d: %s' % (line_number, exc))
        if len(code) != 2 or code[0] not in KANJI_PREFIX:
            raise ValueError('bad prefixed glyph %s on row %d' % (code_text, line_number))
        if code in table:
            raise ValueError('duplicate kanji code %s' % code_text)
        if kind not in ('kanji', 'symbol', 'token'):
            raise ValueError('bad kanji kind %r on row %d' % (kind, line_number))
        if kind == 'token' and not re.fullmatch(r'<[A-Za-z][A-Za-z0-9]*>', text):
            raise ValueError('bad kanji token %r on row %d' % (text, line_number))
        alias = re.fullmatch(r'\{([0-9A-Fa-f]{4})=([^{}])\}', text)
        if alias and alias.group(1).upper() != code_text.upper():
            raise ValueError('kanji alias code does not match row %d' % line_number)
        if kind != 'token' and len(text) != 1 and not (kind == 'kanji' and alias):
            raise ValueError('kanji/symbol must be one character on row %d' % line_number)
        table[code] = text
        kinds[code] = kind
    reverse = {text: code for code, text in table.items()}
    if len(reverse) != len(table):
        raise ValueError('kanji table has ambiguous duplicate text values')
    return table, kinds, reverse


KANJI, KANJI_KIND, _REVKANJI = _load_kanji_table()

# ---- control codes -------------------------------------------------------
# Authoritative: the renderer at 0:$3657 sends F0-FF through the 16-entry table at
# 0:$3671. F0-F2 are two-byte glyph prefixes; F4-F6 take the ordinary one-byte glyph
# path. The remaining entries below are controls. Arity was read from the handlers and
# measured by running a synthetic sequence through the unmodified renderer in PyBoy.
TERMINATOR = 0xFF
CONTROLS = {
    0xF3: 'cF3',           # renderer no-op; source composer soft-wrap checkpoint
    0xF7: 'hspace',        # add one-byte argument to the horizontal pen position
    0xF8: 'cF8',           # renderer no-op
    0xF9: 'cF9',           # pass two-byte little-endian argument to 0:$3A4C
    0xFA: 'delay',         # set the per-character delay counter from one-byte argument
    0xFB: 'page',          # wait/advance at the end of a page
    0xFC: 'box',           # return from this renderer invocation / box boundary
    0xFD: 'br',            # advance one line and reset horizontal position
    0xFE: 'cFE',           # renderer no-op
}
CONTROL_ARITY = {0xF7: 1, 0xF9: 2, 0xFA: 1}

# These bytes enter the regular glyph handler after staging even though their width-table
# entries are zero. They are renderer glyphs, not renderer controls. In ROM source they have
# separate argument-bearing meanings handled by SOURCE_SPECIAL_ARITY below.
SPECIAL_GLYPHS = frozenset((0xF4, 0xF5, 0xF6))

# ROM-source composer semantics, proven from the dispatcher at 0:$3174 and handlers
# F4=$333B, F5=$3306, F6=$335E. The values are argument counts, excluding the code byte.
SOURCE_SPECIAL_ARITY = {0xF4: 3, 0xF5: 1, 0xF6: 3}

DISPATCH_ENTRY = 0x3657
DISPATCH_TABLE = 0x3671


class ParseError(ValueError):
    """A byte record ends inside a glyph pair or control argument."""


@dataclass(frozen=True)
class ScriptToken:
    kind: str
    code: int
    raw: bytes
    args: bytes = b''


_TOKEN = re.compile(
    r'\{([0-9A-Fa-f]{4})(?:=[^{}])?\}'
    r'|<([0-9A-Fa-f]{2})>'
    r'|<([A-Za-z][A-Za-z0-9]*)(?::([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2})*))?>'
)
_REV = {v: k for k, v in CHARS.items()}
_REVCTL = {v: k for k, v in CONTROLS.items()}


def token_size(code):
    """Bytes consumed by `code`, including the code byte itself."""
    if code in KANJI_PREFIX:
        return 2
    return 1 + CONTROL_ARITY.get(code, 0)


def source_token_size(code):
    """Bytes consumed by one ROM-source token before runtime expansion."""
    if code in SOURCE_SPECIAL_ARITY:
        return 1 + SOURCE_SPECIAL_ARITY[code]
    return token_size(code)


def parse(data):
    """Parse one unterminated record into lossless, renderer-aware tokens."""
    data = bytes(data)
    out = []
    i = 0
    while i < len(data):
        code = data[i]
        if code == TERMINATOR:
            raise ParseError('terminator inside record at byte %d' % i)
        size = token_size(code)
        if i + size > len(data):
            role = 'glyph pair' if code in KANJI_PREFIX else 'control'
            raise ParseError('truncated %s %02X at byte %d: needs %d byte(s)'
                             % (role, code, i, size))
        raw = data[i:i + size]
        if code in KANJI_PREFIX:
            kind, args = 'kanji', raw[1:]
        elif code in CONTROLS:
            kind, args = 'control', raw[1:]
        else:
            kind, args = 'glyph', b''
        out.append(ScriptToken(kind=kind, code=code, raw=raw, args=args))
        i += size
    return tuple(out)


def parse_source(data):
    """Parse unterminated ROM source using the 0:$312B composer grammar."""
    data = bytes(data)
    out = []
    i = 0
    while i < len(data):
        code = data[i]
        if code == TERMINATOR:
            raise ParseError('terminator inside source record at byte %d' % i)
        size = source_token_size(code)
        if i + size > len(data):
            raise ParseError(
                'truncated source token %02X at byte %d: needs %d byte(s)'
                % (code, i, size)
            )
        raw = data[i:i + size]
        if code in KANJI_PREFIX:
            kind, args = 'kanji', raw[1:]
        elif code in SOURCE_SPECIAL_ARITY:
            kind, args = 'source_control', raw[1:]
        elif code in CONTROLS:
            kind, args = 'control', raw[1:]
        else:
            kind, args = 'glyph', b''
        out.append(ScriptToken(kind=kind, code=code, raw=raw, args=args))
        i += size
    return tuple(out)


def serialize(tokens):
    """Inverse of parse(): join a token sequence without reinterpretation."""
    return b''.join(token.raw for token in tokens)


def decode(b):
    """Bytes -> readable text; malformed glyph/control tails raise ParseError."""
    out = []
    for token in parse(b):
        if token.kind == 'kanji':
            out.append(KANJI.get(token.raw, '{%02X%02X}' % tuple(token.raw)))
        elif token.kind == 'control':
            suffix = ''.join(':%02X' % arg for arg in token.args)
            out.append('<%s%s>' % (CONTROLS[token.code], suffix))
        elif token.code in CHARS:
            out.append(CHARS[token.code])
        else:
            out.append('<%02X>' % token.code)
    return ''.join(out)


def source_control_text(token):
    if token.code == 0xF4:
        # Legacy spelling retained for extracted-script compatibility: the
        # first argument is an integer byte count, not a text-copy length.
        return '<copy:%s>' % ':'.join('%02X' % arg for arg in token.args)
    if token.code == 0xF5:
        return '<name>' if token.args == b'\xFF' else '<name:%02X>' % token.args[0]
    if token.code == 0xF6:
        mode, low, high = token.args
        if mode == 0x01:
            return '<lookup:%02X:%02X>' % (low, high)
        if mode == 0x03:
            # Legacy spelling: this selects a generic cached runtime string,
            # not necessarily a numeric value.  Script organization will add
            # a clearer backwards-compatible translator-facing alias.
            return '<number:%02X:%02X>' % (low, high)
        return '<sourceF6:%02X:%02X:%02X>' % (mode, low, high)
    raise AssertionError('not a source control: %02X' % token.code)


def decode_source(b):
    """ROM source -> readable, lossless text with named runtime substitutions."""
    out = []
    for token in parse_source(b):
        if token.kind == 'source_control':
            out.append(source_control_text(token))
        elif token.kind == 'kanji':
            out.append(KANJI.get(token.raw, '{%02X%02X}' % tuple(token.raw)))
        elif token.kind == 'control':
            suffix = ''.join(':%02X' % arg for arg in token.args)
            out.append('<%s%s>' % (CONTROLS[token.code], suffix))
        elif token.code in CHARS:
            out.append(CHARS[token.code])
        else:
            out.append('<%02X>' % token.code)
    return ''.join(out)


def encode(s):
    """Inverse of decode(). Round-trips anything decode() produced."""
    out = bytearray()
    i = 0
    while i < len(s):
        m = _TOKEN.match(s, i)
        if m:
            kanji, raw, name, arg_text = m.groups()
            if kanji:
                out += bytes((int(kanji[:2], 16), int(kanji[2:], 16)))
            elif raw:
                out.append(int(raw, 16))
            elif '<%s>' % name in _REVKANJI:
                if arg_text:
                    raise ValueError('<%s> does not take arguments' % name)
                out += _REVKANJI['<%s>' % name]
            else:
                if name not in _REVCTL:
                    raise ValueError('unknown control <%s>' % name)
                code = _REVCTL[name]
                args = bytes(int(value, 16) for value in arg_text.split(':')) \
                    if arg_text else b''
                want = CONTROL_ARITY.get(code, 0)
                if len(args) != want:
                    raise ValueError('<%s> needs %d argument byte(s), got %d'
                                     % (name, want, len(args)))
                out.append(code)
                out += args
            i = m.end()
            continue
        ch = s[i]
        if ch in _REV:
            out.append(_REV[ch])
        elif ch in _REVKANJI:
            out += _REVKANJI[ch]
        else:
            raise ValueError('cannot encode %r at %d' % (ch, i))
        i += 1
    return bytes(out)


def _source_control_bytes(name, arg_text):
    args = bytes(int(value, 16) for value in arg_text.split(':')) if arg_text else b''
    if name == 'copy':
        if len(args) != 3:
            raise ValueError('<copy> needs 3 argument bytes, got %d' % len(args))
        return bytes((0xF4,)) + args
    if name == 'name':
        if not args:
            args = b'\xFF'
        if len(args) != 1:
            raise ValueError('<name> needs zero or one argument byte')
        return bytes((0xF5,)) + args
    if name in ('lookup', 'number'):
        if len(args) != 2:
            raise ValueError('<%s> needs 2 argument bytes, got %d' % (name, len(args)))
        mode = 0x01 if name == 'lookup' else 0x03
        return bytes((0xF6, mode)) + args
    if name == 'sourceF6':
        if len(args) != 3:
            raise ValueError('<sourceF6> needs 3 argument bytes, got %d' % len(args))
        return bytes((0xF6,)) + args
    return None


def encode_source(s):
    """Inverse of decode_source(); preserves swallowed FF argument bytes exactly."""
    out = bytearray()
    i = 0
    while i < len(s):
        m = _TOKEN.match(s, i)
        if m:
            kanji, raw, name, arg_text = m.groups()
            if kanji:
                out += bytes((int(kanji[:2], 16), int(kanji[2:], 16)))
            elif raw:
                out.append(int(raw, 16))
            else:
                special = _source_control_bytes(name, arg_text)
                if special is not None:
                    out += special
                elif '<%s>' % name in _REVKANJI:
                    if arg_text:
                        raise ValueError('<%s> does not take arguments' % name)
                    out += _REVKANJI['<%s>' % name]
                else:
                    if name not in _REVCTL:
                        raise ValueError('unknown source control <%s>' % name)
                    code = _REVCTL[name]
                    args = bytes(int(value, 16) for value in arg_text.split(':')) \
                        if arg_text else b''
                    want = CONTROL_ARITY.get(code, 0)
                    if len(args) != want:
                        raise ValueError(
                            '<%s> needs %d argument byte(s), got %d'
                            % (name, want, len(args))
                        )
                    out.append(code)
                    out += args
            i = m.end()
            continue
        ch = s[i]
        if ch in _REV:
            out.append(_REV[ch])
        elif ch in _REVKANJI:
            out += _REVKANJI[ch]
        else:
            raise ValueError('cannot encode source %r at %d' % (ch, i))
        i += 1
    return bytes(out)


def strings(data, base=0, minlen=1):
    """Split on token-boundary terminators, never on an argument byte equal to FF."""
    data = bytes(data)
    out = []
    start = i = 0
    while i < len(data):
        code = data[i]
        if code == TERMINATOR:
            if i - start >= minlen:
                out.append((base + start, data[start:i]))
            i += 1
            start = i
        else:
            i = min(len(data), i + token_size(code))
    if len(data) - start >= minlen:
        out.append((base + start, data[start:]))
    return out


def _selftest(rom_path):
    """Assert the table against strings whose meaning is known independently."""
    d = open(rom_path, 'rb').read()
    # Anchors are strings whose reading was established independently of the table --
    # by meaning in context, not by decoding with the table we are testing.
    anchors = [
        (0x3003C5, 'どこでもドア'),
        (0x30047F, 'そうこ'),
        (0x3003A5, 'アイテムをひろった'),
        (0x300487, 'かじや'),
    ]
    ok = True
    for off, want in anchors:
        end = d.index(bytes((TERMINATOR,)), off)
        got = decode(d[off:end])
        if want not in got:
            print('FAIL @0x%06X: expected %r in %r' % (off, want, got[:40]))
            ok = False
        else:
            print('ok   @0x%06X  %s' % (off, want))
    # Round-trip every dialogue string in the script banks.
    n = bad = 0
    # Bank 206 is the prefixed font, not script. The initial density scan included it
    # and thereby admitted 122 false records; the renderer trace retired that mistake.
    for bank in range(192, 206):
        for _, s in strings(d[bank * 0x4000:(bank + 1) * 0x4000], 0, 6):
            if sum(1 for x in s if 0x30 <= x < 0xD0) < len(s) * 0.55:
                continue
            n += 1
            if serialize(parse(s)) != s or encode(decode(s)) != s:
                bad += 1
    print('parser + text round-trip: %d/%d script candidates exact' % (n - bad, n))
    return ok and bad == 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit('usage: codec.py <rom.gbc>')
    sys.exit(0 if _selftest(sys.argv[1]) else 1)
