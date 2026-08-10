"""json_store: default on missing, atomic save, the keep-nonempty merge rule."""

from __future__ import annotations

import json

import pytest

from pycommons import load_or_default, merge_keep_nonempty, save_atomic


# --- load_or_default --------------------------------------------------------

def test_missing_file_returns_default(tmp_path):
    assert load_or_default(tmp_path / "nope.json", []) == []
    assert load_or_default(tmp_path / "nope.json") is None


def test_reads_json(tmp_path):
    p = tmp_path / "d.json"
    p.write_text('[{"name": "Стоматология"}]', encoding="utf-8")
    assert load_or_default(p, []) == [{"name": "Стоматология"}]


def test_corrupt_file_raises_rather_than_returning_default(tmp_path):
    p = tmp_path / "d.json"
    p.write_text('[{"name": "half', encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_or_default(p, [])


# --- save_atomic ------------------------------------------------------------

def test_roundtrip_and_no_tmp_leftovers(tmp_path):
    data = [{"name": "Стоматология", "rating": 4.8}]
    path = save_atomic(tmp_path / "out.json", data)

    assert path == tmp_path / "out.json"
    assert load_or_default(path) == data
    assert [p.name for p in tmp_path.iterdir()] == ["out.json"]


def test_writes_unescaped_utf8_and_indents(tmp_path):
    p = save_atomic(tmp_path / "out.json", {"city": "Алматы"})
    text = p.read_text(encoding="utf-8")
    assert "Алматы" in text and "\\u" not in text
    assert text.startswith("{\n  ")


def test_indent_none_is_compact(tmp_path):
    p = save_atomic(tmp_path / "out.json", {"a": 1, "b": 2}, indent=None)
    assert p.read_text(encoding="utf-8") == '{"a": 1, "b": 2}'


def test_creates_parent_dirs(tmp_path):
    p = save_atomic(tmp_path / "a" / "b" / "out.json", {"ok": True})
    assert p.exists()


def test_overwrite_replaces_content_entirely(tmp_path):
    path = tmp_path / "out.json"
    save_atomic(path, {"long": "x" * 500})
    save_atomic(path, {"n": 1})
    assert load_or_default(path) == {"n": 1}


def test_failed_serialisation_leaves_original_intact_and_no_tmp(tmp_path):
    path = tmp_path / "out.json"
    save_atomic(path, {"keep": "me"})

    with pytest.raises(TypeError):
        save_atomic(path, {"bad": object()})

    assert load_or_default(path) == {"keep": "me"}
    assert [p.name for p in tmp_path.iterdir()] == ["out.json"]


# --- merge_keep_nonempty ----------------------------------------------------

def test_fills_blank_fields_from_new():
    old = {"name": "Clinic", "link_insta": ""}
    assert merge_keep_nonempty(old, {"link_insta": "https://ig/x"})["link_insta"] == "https://ig/x"


def test_does_not_overwrite_nonempty_with_nonempty():
    """A hand-edited value survives a re-scrape."""
    old = {"link_whatsapp": "https://wa.me/7700"}
    merged = merge_keep_nonempty(old, {"link_whatsapp": "https://wa.me/OTHER"})
    assert merged["link_whatsapp"] == "https://wa.me/7700"


def test_does_not_overwrite_nonempty_with_empty():
    old = {"address": "Abay 10"}
    for empty in ("", None, 0, [], {}):
        assert merge_keep_nonempty(old, {"address": empty})["address"] == "Abay 10"


def test_empty_new_value_does_not_create_the_key():
    assert merge_keep_nonempty({}, {"address": ""}) == {}


def test_always_fields_are_refreshed_when_truthy():
    old = {"rating": 4.1, "review_count": 10, "name": "Clinic"}
    merged = merge_keep_nonempty(
        old, {"rating": 4.9, "review_count": 55, "name": "Other"},
        always=("rating", "review_count"),
    )
    assert merged["rating"] == 4.9
    assert merged["review_count"] == 55
    assert merged["name"] == "Clinic"   # not in `always`


def test_always_field_with_empty_value_is_still_skipped():
    merged = merge_keep_nonempty({"rating": 4.1}, {"rating": 0}, always=("rating",))
    assert merged["rating"] == 4.1


def test_keys_only_in_old_are_preserved():
    assert merge_keep_nonempty({"manual_note": "call first"}, {}) == {"manual_note": "call first"}


def test_inputs_are_not_mutated():
    old, new = {"a": ""}, {"a": "x"}
    merge_keep_nonempty(old, new)
    assert old == {"a": ""} and new == {"a": "x"}
