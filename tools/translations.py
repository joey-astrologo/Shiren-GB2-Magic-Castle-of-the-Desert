#!/usr/bin/env python3
"""Load stable-ID English overrides for the GB2 relocated build.

Both the full extractor TSV and compact ``id<TAB>english`` files are accepted. A
directory emitted by ``organize.py`` or ``overlays.py`` is accepted as well; its
category TSVs are loaded in filename order. A blank English cell means untranslated
and is ignored; the explicit sentinel ``<empty>`` is required to replace a record
with zero bytes.
"""
import csv
from dataclasses import dataclass
from pathlib import Path

import english


EMPTY_SENTINEL = "<empty>"


class TranslationError(ValueError):
    """A translation file is stale, ambiguous, or cannot be encoded."""


@dataclass(frozen=True)
class Translation:
    record_id: str
    source_bank: int
    source_address: int
    text: str
    encoded: bytes
    explicit_empty: bool

    @property
    def source_key(self):
        return self.source_bank, self.source_address


def load_tsv(path, records):
    """Return ``source key -> Translation`` after validating the source contract."""
    path = Path(path)
    by_id = {record.id: record for record in records}
    out = {}
    seen_ids = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = set(reader.fieldnames or ())
        missing = {"id", "english"} - fields
        if missing:
            raise TranslationError(
                "%s is missing required column(s): %s"
                % (path, ", ".join(sorted(missing)))
            )
        for line_number, row in enumerate(reader, 2):
            if None in row or row.get("id") is None or row.get("english") is None:
                raise TranslationError(
                    "%s:%d has the wrong number of TSV columns" % (path, line_number)
                )
            record_id = row["id"]
            if not record_id or record_id.startswith("#"):
                continue
            if record_id in seen_ids:
                raise TranslationError(
                    "%s:%d duplicates record ID %s" % (path, line_number, record_id)
                )
            seen_ids.add(record_id)
            try:
                record = by_id[record_id]
            except KeyError:
                raise TranslationError(
                    "%s:%d names unknown record ID %s" % (path, line_number, record_id)
                ) from None

            if "length" in fields and row["length"]:
                try:
                    declared_length = int(row["length"])
                except ValueError:
                    raise TranslationError(
                        "%s:%d has invalid source length %r"
                        % (path, line_number, row["length"])
                    ) from None
                if declared_length != len(record.raw):
                    raise TranslationError(
                        "%s:%d source length changed for %s" % (path, line_number, record_id)
                    )
            if "original_hex" in fields and row["original_hex"]:
                if row["original_hex"].upper() != record.raw.hex().upper():
                    raise TranslationError(
                        "%s:%d original bytes changed for %s" % (path, line_number, record_id)
                    )
            if "japanese" in fields and row["japanese"]:
                if row["japanese"] != record.source:
                    raise TranslationError(
                        "%s:%d Japanese source changed for %s" % (path, line_number, record_id)
                    )

            text = row["english"]
            if text == "":
                continue
            explicit_empty = text == EMPTY_SENTINEL
            try:
                encoded = b"" if explicit_empty else english.encode_source(text)
            except ValueError as exc:
                raise TranslationError(
                    "%s:%d cannot encode %s: %s" % (path, line_number, record_id, exc)
                ) from exc
            translation = Translation(
                record_id=record_id,
                source_bank=record.bank,
                source_address=record.address,
                text="" if explicit_empty else text,
                encoded=encoded,
                explicit_empty=explicit_empty,
            )
            out[translation.source_key] = translation
    return out


def load_mapping(english_by_id, records):
    """Encode an authoritative ``stable ID -> English`` mapping.

    This is the in-memory counterpart to :func:`load_tsv`.  Generated editing
    tools use it to prove their complete merged workspace before rewriting any
    catalogs, without first creating a temporary translation file.
    """
    by_id = {record.id: record for record in records}
    unknown = sorted(set(english_by_id) - set(by_id))
    if unknown:
        raise TranslationError("English mapping names unknown record ID %s" % unknown[0])

    out = {}
    for record_id, text in english_by_id.items():
        if not isinstance(text, str):
            raise TranslationError(
                "English mapping for %s must be text" % record_id
            )
        if text == "":
            continue
        record = by_id[record_id]
        explicit_empty = text == EMPTY_SENTINEL
        try:
            encoded = b"" if explicit_empty else english.encode_source(text)
        except ValueError as exc:
            raise TranslationError(
                "English mapping cannot encode %s: %s" % (record_id, exc)
            ) from exc
        translation = Translation(
            record_id=record.id,
            source_bank=record.bank,
            source_address=record.address,
            text="" if explicit_empty else text,
            encoded=encoded,
            explicit_empty=explicit_empty,
        )
        out[translation.source_key] = translation
    return out


def load_path(path, records):
    """Load one TSV or merge every category TSV in a translation directory."""
    path = Path(path)
    if not path.is_dir():
        return load_tsv(path, records)

    paths = tuple(sorted(path.glob("*.tsv")))
    if not paths:
        raise TranslationError("%s contains no TSV files" % path)
    out = {}
    owners = {}
    for tsv_path in paths:
        loaded = load_tsv(tsv_path, records)
        for key, translation in loaded.items():
            if key in out:
                raise TranslationError(
                    "%s duplicates translated record ID %s from %s"
                    % (tsv_path, translation.record_id, owners[key])
                )
            out[key] = translation
            owners[key] = tsv_path
    return out


def encoded_overrides(translations):
    """Return the allocator-facing ``source key -> bytes`` mapping."""
    return {key: translation.encoded for key, translation in translations.items()}
