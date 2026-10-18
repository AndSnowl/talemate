"""Tests for the `culture` field on Character and the glossary `doesnt_fit` flag."""

import pytest

from talemate.character import Character
from talemate.cultures import CharacterCulture, GlossaryEntry, GlossaryOrigin
from talemate.shared_context import SharedContext


def test_character_culture_round_trip():
    c = Character(name="Kethrun", culture={"culture_id": "taelrik", "unsure": True})
    assert isinstance(c.culture, CharacterCulture)
    assert c.culture.culture_id == "taelrik"
    assert c.culture.unsure is True

    c2 = Character(**c.model_dump())
    assert c2.culture == c.culture


def test_update_validates_culture_dict():
    c = Character(name="Kethrun")
    c.update(culture={"culture_id": "elsiri", "set_by": "owner"})
    assert isinstance(c.culture, CharacterCulture)
    assert c.culture.set_by == "owner"

    c.update(culture=None)
    assert c.culture is None


@pytest.mark.asyncio
async def test_apply_shared_context_copies_culture():
    other = Character(name="Kethrun", culture={"culture_id": "taelrik"})
    local = Character(name="Kethrun")

    await local.apply_shared_context(other)

    assert local.culture.culture_id == "taelrik"
    assert local.culture is not other.culture

    other_no_culture = Character(name="Kethrun", culture=None)
    local_with_culture = Character(name="Kethrun", culture={"culture_id": "elsiri"})

    await local_with_culture.apply_shared_context(other_no_culture)

    assert local_with_culture.culture is None


@pytest.mark.asyncio
async def test_shared_context_file_restores_culture(tmp_path):
    filepath = tmp_path / "w.json"

    character = Character(
        name="Kethrun", shared=True, culture={"culture_id": "taelrik"}
    )

    shared_context = SharedContext(filepath=filepath)
    shared_context.character_data["Kethrun"] = character
    await shared_context.write_to_file()

    restored = SharedContext(filepath=filepath)
    await restored.init_from_file()

    restored_character = restored.character_data["Kethrun"]
    assert isinstance(restored_character.culture, CharacterCulture)
    assert restored_character.culture.culture_id == "taelrik"


def test_glossary_entry_doesnt_fit_defaults_false():
    entry = GlossaryEntry(
        id="e1",
        text="Kethrun",
        language="taelrik",
        kind="person",
        origin=GlossaryOrigin(by="ai"),
    )
    assert entry.doesnt_fit is False
