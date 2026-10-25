"""A fact draft ("+ Add facts" on a saved page) settles its repeat
choices as a page draft does (`create.write_repeat_choices`): "Keep new"
writes the draft's fact and removes the one it repeats, "Move existing
here" moves the world's fact onto the page instead, both in the accept's
one revision."""

import pytest

from talemate.world.dates import WorldDate
from talemate.world.store import Source
from talemate.worldplay import facts
from talemate.worldplay.create import MoveHereFact, PreviewFact

EXISTING = "The Khorol freezes solid in winter."


@pytest.fixture
def river(world):
    """Velikoye (a place) whose fact says the Khorol freezes, and the
    Khorol River (a place) with a fact of its own."""

    world.set_present(WorldDate.of(1004))
    with world.revision(Source.manual(note="seed")) as rev:
        velikoye = rev.create_thing("place", {"name": "Velikoye", "tag": "city"})
        world.freeze = rev.add_fact(velikoye, "general", EXISTING)
        world.bells = rev.add_fact(velikoye, "general", "Velikoye has many bells.")
        khorol = rev.create_thing("place", {"name": "Khorol River", "tag": "river"})
        rev.add_fact(khorol, "general", "A wide, slow river.")
    world.velikoye, world.khorol = velikoye, khorol
    return world


def _repeat(world) -> dict:
    return {
        "fact_id": world.freeze,
        "owner_id": world.velikoye,
        "owner_name": "Velikoye",
        "text": EXISTING,
        "score": 0.9,
    }


def _texts(world, thing_id) -> list[str]:
    return [f.text for f in world.view().thing(thing_id).facts]


def test_accept_facts_keep_new_replaces_repeat(river):
    draft = facts.FactDraft(
        thing_id=river.khorol,
        prompt="winter",
        facts=[
            PreviewFact(
                category="general",
                text="It freezes over every winter.",
                repeat_of=_repeat(river),
                ticked=True,
                replaces_repeat=True,
            )
        ],
    )
    head = river.head_rev()
    notes: list[str] = []
    prose: list[str] = []
    written = facts.accept_facts(river, draft, notes, prose)
    assert river.head_rev() == head + 1
    assert len(written) == 1
    # the page the repeat was removed from; nothing moved onto this one
    assert prose == [river.velikoye]
    assert "It freezes over every winter." in _texts(river, river.khorol)
    assert EXISTING not in _texts(river, river.velikoye)
    assert "Velikoye has many bells." in _texts(river, river.velikoye)
    assert notes == []


def test_accept_facts_move_existing_here(river):
    draft = facts.FactDraft(
        thing_id=river.khorol,
        prompt="winter",
        facts=[
            PreviewFact(
                category="general",
                text="It freezes over every winter.",
                repeat_of=_repeat(river),
                ticked=False,
            )
        ],
        move_here=[
            MoveHereFact(
                fact_id=river.freeze,
                from_id=river.velikoye,
                text=EXISTING,
                ticked=True,
                repeat=True,
            )
        ],
    )
    head = river.head_rev()
    notes: list[str] = []
    prose: list[str] = []
    facts.accept_facts(river, draft, notes, prose)
    assert river.head_rev() == head + 1
    # the page it left and the page it moved onto read it
    assert sorted(prose) == sorted([river.velikoye, river.khorol])
    texts = _texts(river, river.khorol)
    assert EXISTING in texts
    assert "It freezes over every winter." not in texts
    assert EXISTING not in _texts(river, river.velikoye)
    assert notes == []


def test_accept_facts_move_needs_a_row_that_repeats_it(river):
    """A `repeat` move row no draft fact says it repeats moves nothing,
    with today's note."""

    draft = facts.FactDraft(
        thing_id=river.khorol,
        prompt="winter",
        facts=[
            PreviewFact(
                category="general",
                text="It freezes over every winter.",
                repeat_of=_repeat(river),
                ticked=False,
            )
        ],
        move_here=[
            MoveHereFact(
                fact_id=river.bells,
                from_id=river.velikoye,
                text="Velikoye has many bells.",
                ticked=True,
                repeat=True,
            )
        ],
    )
    head = river.head_rev()
    notes: list[str] = []
    facts.accept_facts(river, draft, notes)
    assert river.head_rev() == head
    assert "Velikoye has many bells." in _texts(river, river.velikoye)
    assert any("isn't one this draft repeats" in note for note in notes)


def test_accept_facts_keep_new_existing_gone_since(river):
    with river.revision(Source.manual(note="gone")) as rev:
        rev.remove_fact(river.freeze)
    draft = facts.FactDraft(
        thing_id=river.khorol,
        prompt="winter",
        facts=[
            PreviewFact(
                category="general",
                text="It freezes over every winter.",
                repeat_of=_repeat(river),
                ticked=True,
                replaces_repeat=True,
            )
        ],
    )
    before = {f.fact_id for t in river.view().things() for f in t.facts}
    head = river.head_rev()
    notes: list[str] = []
    written = facts.accept_facts(river, draft, notes)
    assert river.head_rev() == head + 1
    after = {f.fact_id for t in river.view().things() for f in t.facts}
    # the new fact is written, and nothing else is removed
    assert after == before | set(written)
    assert "It freezes over every winter." in _texts(river, river.khorol)
    assert any("was moved or removed since the preview" in note for note in notes)
