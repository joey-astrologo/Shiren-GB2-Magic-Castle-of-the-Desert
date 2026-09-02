#!/usr/bin/env python3
"""English-facing text codec for the Shiren GB2 translation.

The Japanese codec in :mod:`codec` remains authoritative for extracting the original
ROM.  This module defines the deliberately separate post-font-patch code page used by
English text.  Keeping the two tables separate prevents a patched lowercase ``a`` at
code $30 from changing how the original hiragana ``あ`` is decoded.

Controls and named prefixed symbols retain the byte grammar proven by ``codec.py``.
"""
import re

import codec


# Digits and capitals already occupy the natural low-code block.  English frees the
# hiragana tiles, so lowercase and punctuation use one compact range there.  The
# Japanese $D0-$EF symbol block is intentionally untouched: it includes UI shapes and
# item/status marks whose dynamic consumers have not all been classified yet.
ENGLISH_CODES = {str(index): index for index in range(10)}
ENGLISH_CODES.update({chr(ord("A") + index): 0x0A + index for index in range(26)})
ENGLISH_CODES[" "] = 0x24
ENGLISH_CODES.update({chr(ord("a") + index): 0x30 + index for index in range(26)})
ENGLISH_CODES.update(
    {character: 0x4A + index for index, character in enumerate(".,'-?!():/[]+~%\"")}
)

CODE_TO_ENGLISH = {code: character for character, code in ENGLISH_CODES.items()}

_TOKEN = re.compile(
    r"\{[0-9A-Fa-f]{4}(?:=[^{}])?\}"
    r"|<[0-9A-Fa-f]{2}>"
    r"|<[A-Za-z][A-Za-z0-9]*(?::[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2})*)?>"
)


def _encode(text, source):
    out = bytearray()
    position = 0
    encoder = codec.encode_source if source else codec.encode
    native_template_run = False
    while position < len(text):
        token = _TOKEN.match(text, position)
        if token:
            out += encoder(token.group())
            native_template_run = source and token.group() == "<cF8>"
            position = token.end()
            continue
        character = text[position]
        # F8 is a renderer no-op, but event/menu templates use it as an
        # escape before runs of native Latin variable selectors.  Those
        # selector bytes are consumed before ordinary rendering (for example
        # ``<cF8>g`` is Big Moai's dynamic reward-item name).  Re-encoding the
        # visible letter through the English code page changes $10 to $36 and
        # sends the native formatter through an invalid path.  Preserve the
        # original 0-9/a-z selector byte domain until the run ends.
        if source and native_template_run and (
            "0" <= character <= "9" or "a" <= character <= "z"
        ):
            out += codec.encode_source(character)
            position += 1
            continue
        native_template_run = False
        try:
            out.append(ENGLISH_CODES[character])
        except KeyError:
            raise ValueError(
                "cannot encode English character %r at %d" % (character, position)
            ) from None
        position += 1
    return bytes(out)


def encode(text):
    """Encode renderer-stage English, including the native named controls."""
    return _encode(text, source=False)


def encode_source(text):
    """Encode ROM-source English, including runtime substitution controls."""
    return _encode(text, source=True)


def _decode(data, source):
    parser = codec.parse_source if source else codec.parse
    fallback = codec.decode_source if source else codec.decode
    out = []
    native_template_run = False
    for token in parser(data):
        if source and native_template_run and token.kind == "glyph":
            native = codec.decode_source(token.raw)
            if len(native) == 1 and (
                "0" <= native <= "9" or "a" <= native <= "z"
            ):
                out.append(native)
                continue
            native_template_run = False
        if token.kind == "glyph" and token.code in CODE_TO_ENGLISH:
            out.append(CODE_TO_ENGLISH[token.code])
        else:
            out.append(fallback(token.raw))
        native_template_run = source and token.code == 0xF8
    return "".join(out)


def decode(data):
    """Decode renderer-stage bytes with the installed English code page."""
    return _decode(data, source=False)


def decode_source(data):
    """Decode ROM-source bytes with the installed English code page."""
    return _decode(data, source=True)


def text_width(text, advances):
    """Return native VWF pen movement for plain English text."""
    try:
        return sum(advances[character] for character in text)
    except KeyError as exc:
        raise ValueError("text_width accepts plain English glyphs, not %r" % exc.args[0])
