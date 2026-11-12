"""Derive every coverage_id from canonical_refs and sort the ledger in place.

Usage: python3 -I coverage_id.py <output-dir>/coverage-ledger.json

Follows RECONNAISSANCE.md: each reference must be NFC with no surrounding
whitespace, is percent-encoded leaving only A-Z a-z 0-9 - . _ ~, and the
surface, boundary, subsystem, attack_class (and lifecycle) parts join with "::".
"""

import json
import sys
import unicodedata
from urllib.parse import quote


def encode(reference: str) -> str:
    if not reference or reference != reference.strip():
        raise ValueError(f"reference has surrounding whitespace or is empty: {reference!r}")
    if reference != unicodedata.normalize("NFC", reference):
        raise ValueError(f"reference is not NFC: {reference!r}")
    return quote(reference.encode("utf-8"), safe="-._~")


def coverage_id(refs: dict[str, str]) -> str:
    keys = ["surface", "boundary", "subsystem", "attack_class"]
    if "lifecycle" in refs:
        keys.append("lifecycle")
    return "::".join(encode(refs[key]) for key in keys)


def main(path: str) -> None:
    with open(path, encoding="utf-8") as handle:
        units = json.load(handle)
    for unit in units:
        unit["coverage_id"] = coverage_id(unit["canonical_refs"])
    units.sort(key=lambda unit: unit["coverage_id"])
    ids = [unit["coverage_id"] for unit in units]
    if len(ids) != len(set(ids)):
        sys.exit("duplicate coverage_id")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(units, handle, indent=1, ensure_ascii=False)
    sys.stdout.write(f"{len(units)} units\n")


if __name__ == "__main__":
    main(sys.argv[1])
