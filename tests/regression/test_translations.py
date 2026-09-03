"""strings.json is the source of truth; translations/en.json must be a
verbatim copy of it, and every other language file must have the exact same
key structure (no missing / extra keys).
"""
from __future__ import annotations

import json
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[2] / "custom_components" / "plum_ecomax"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _key_paths(node, prefix=""):
    out = set()
    if isinstance(node, dict):
        for k, v in node.items():
            p = f"{prefix}.{k}" if prefix else k
            out.add(p)
            out |= _key_paths(v, p)
    return out


def test_en_json_matches_strings_json_exactly():
    strings = _load(COMPONENT / "strings.json")
    en = _load(COMPONENT / "translations" / "en.json")
    assert en == strings, "translations/en.json must be a verbatim copy of strings.json"


def test_every_language_file_has_the_same_keys_as_strings():
    expected = _key_paths(_load(COMPONENT / "strings.json"))
    for lang_file in (COMPONENT / "translations").glob("*.json"):
        got = _key_paths(_load(lang_file))
        assert got == expected, (
            f"{lang_file.name}: key mismatch vs strings.json "
            f"(missing={sorted(expected - got)}, extra={sorted(got - expected)})"
        )
