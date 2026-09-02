#!/usr/bin/env python3
"""Create and verify deterministic same-size IPS release patches."""


HEADER = b"PATCH"
END = b"EOF"
EOF_OFFSET = int.from_bytes(END, "big")
MAX_RECORD_SIZE = 0xFFFF
MAX_ROM_SIZE = 0x1000000


class IpsError(ValueError):
    """Raised when an IPS patch cannot be created or decoded safely."""


def _release_bytes(value, label):
    if not isinstance(value, bytes):
        raise TypeError("%s is not bytes" % label)
    return value


def create_patch(source, target):
    """Return a deterministic IPS patch from one same-size ROM to another."""
    source = _release_bytes(source, "source ROM")
    target = _release_bytes(target, "target ROM")
    if len(source) != len(target):
        raise IpsError("IPS release ROMs must be the same size")
    if len(target) > MAX_ROM_SIZE:
        raise IpsError("IPS release ROM exceeds the 24-bit address space")

    patch = bytearray(HEADER)
    cursor = 0
    while cursor < len(source):
        while cursor < len(source) and source[cursor] == target[cursor]:
            cursor += 1
        if cursor == len(source):
            break

        end = cursor + 1
        while end < len(source) and source[end] != target[end]:
            end += 1

        while cursor < end:
            record_at = cursor
            # A record beginning at $454F46 spells the IPS terminator "EOF".
            # Include the preceding target byte so that no record can be
            # mistaken for the end marker. Overlapping a prior record is legal.
            if record_at == EOF_OFFSET:
                record_at -= 1
            record_end = min(end, record_at + MAX_RECORD_SIZE)
            payload = target[record_at:record_end]
            patch.extend(record_at.to_bytes(3, "big"))
            patch.extend(len(payload).to_bytes(2, "big"))
            patch.extend(payload)
            cursor = record_end

    patch.extend(END)
    return bytes(patch)


def _parse(patch):
    patch = _release_bytes(patch, "IPS patch")
    if not patch.startswith(HEADER):
        raise IpsError("IPS patch is missing the PATCH header")

    records = []
    cursor = len(HEADER)
    while True:
        if cursor + 3 > len(patch):
            raise IpsError("IPS patch is missing the EOF marker")
        marker = patch[cursor:cursor + 3]
        cursor += 3
        if marker == END:
            trailing = len(patch) - cursor
            if trailing not in (0, 3):
                raise IpsError("IPS patch has invalid data after EOF")
            truncate_to = (
                int.from_bytes(patch[cursor:cursor + 3], "big")
                if trailing == 3
                else None
            )
            return records, truncate_to

        offset = int.from_bytes(marker, "big")
        if cursor + 2 > len(patch):
            raise IpsError("IPS record is missing its size")
        size = int.from_bytes(patch[cursor:cursor + 2], "big")
        cursor += 2
        if size:
            if cursor + size > len(patch):
                raise IpsError("IPS record is truncated")
            payload = patch[cursor:cursor + size]
            cursor += size
        else:
            if cursor + 3 > len(patch):
                raise IpsError("IPS RLE record is truncated")
            run = int.from_bytes(patch[cursor:cursor + 2], "big")
            value = patch[cursor + 2]
            cursor += 3
            if run == 0:
                raise IpsError("IPS RLE record has zero length")
            payload = bytes([value]) * run
        records.append((offset, payload))


def apply_patch(source, patch):
    """Apply raw or RLE IPS records and return the reconstructed bytes."""
    source = _release_bytes(source, "source ROM")
    records, truncate_to = _parse(patch)
    output = bytearray(source)
    for offset, payload in records:
        end = offset + len(payload)
        if end > len(output):
            output.extend(bytes(end - len(output)))
        output[offset:end] = payload
    if truncate_to is not None:
        if truncate_to < len(output):
            del output[truncate_to:]
        elif truncate_to > len(output):
            output.extend(bytes(truncate_to - len(output)))
    return bytes(output)


def record_count(patch):
    """Return the number of data records in a valid IPS patch."""
    records, _truncate_to = _parse(patch)
    return len(records)
