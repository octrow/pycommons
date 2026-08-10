"""safe_filename / slugify: cyrillic, emoji, empties, truncation."""

from __future__ import annotations

import pytest

from pycommons import safe_filename, slugify


# --- safe_filename (dental-parser shape: keeps case and Unicode) ------------

@pytest.mark.parametrize("raw,expected", [
    ("Dental Clinic", "Dental_Clinic"),
    ("Стоматология Люкс", "Стоматология_Люкс"),
    ("Clinic #1 (Almaty)!", "Clinic_1_Almaty"),
    ("Well-Known Clinic", "Well-Known_Clinic"),   # hyphens survive
    ("Dental   Clinic", "Dental_Clinic"),         # \s+ collapses to one sep
    ("Клиника 😁 Улыбка", "Клиника_Улыбка"),       # emoji dropped, the gap it leaves collapses
    ("Tabs\tand\nnewlines", "Tabs_and_newlines"),
    ("  padded  ", "padded"),
])
def test_safe_filename_cases(raw, expected):
    assert safe_filename(raw) == expected


def test_safe_filename_keeps_case():
    assert safe_filename("ABC def") == "ABC_def"


def test_safe_filename_truncates_at_50_by_default():
    out = safe_filename("Стоматология " * 10)
    assert len(out) <= 50


def test_safe_filename_max_len_and_sep():
    assert safe_filename("Some Long Clinic Name", max_len=9) == "Some_Long"
    assert safe_filename("Some Long Name", sep="-") == "Some-Long-Name"


def test_safe_filename_truncation_never_ends_in_a_separator():
    assert safe_filename("Some Long Clinic", max_len=5) == "Some"


@pytest.mark.parametrize("raw", ["", "   ", "###", "😁😁", "!!! ???"])
def test_safe_filename_unusable_input_is_empty(raw):
    assert safe_filename(raw) == ""


def test_safe_filename_is_stable_under_reslugify():
    """processor_ai re-slugifies the name to find the directory it scraped into."""
    name = "Стоматология «Люкс» #1"
    once = safe_filename(name)
    assert safe_filename(once) == once


# --- slugify (dialogue-lens shape: ascii-only url/id slug) ------------------

@pytest.mark.parametrize("raw,expected", [
    ("Ivan P. Sidorov", "ivan-p-sidorov"),
    ("UPPER Case", "upper-case"),
    ("a  --  b", "a-b"),
    ("--leading and trailing--", "leading-and-trailing"),
    ("already-a-slug", "already-a-slug"),
    ("Ivan 2nd", "ivan-2nd"),
])
def test_slugify_cases(raw, expected):
    assert slugify(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "!!!", "Иван Петров", "😁", "日本語"])
def test_slugify_falls_back_when_nothing_ascii_survives(raw):
    assert slugify(raw) == "x"


def test_slugify_custom_fallback():
    assert slugify("", fallback="anon") == "anon"


def test_slugify_mixed_script_keeps_only_ascii():
    assert slugify("Ivan Иванов 42") == "ivan-42"


def test_slugify_sep():
    assert slugify("Ivan P. Sidorov", sep="_") == "ivan_p_sidorov"


def test_slugify_no_truncation_by_default():
    assert len(slugify("word " * 30)) > 50


def test_slugify_max_len_truncates_without_trailing_sep():
    assert slugify("alpha beta gamma", max_len=10) == "alpha-beta"
    assert slugify("alpha beta gamma", max_len=6) == "alpha"


def test_slugify_output_matches_dialogue_lens_name_pattern():
    import re
    assert re.match(r"^[a-z0-9][a-z0-9_-]*$", slugify("Ivan P. Sidorov"))


def test_slugify_is_idempotent():
    once = slugify("Ivan P. Sidorov")
    assert slugify(once) == once
