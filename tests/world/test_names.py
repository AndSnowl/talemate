"""The shared name index: names, other names, first names, stubs, partial
suggestions and unknown proper phrases."""

from talemate.world.names import everyday_name, find_names, unknown_proper_phrases
from talemate.world.store import Source


def _aka(name: str, tag: str = "common", everyday: bool = False) -> dict:
    return {"name": name, "tag": tag, "everyday": everyday}


def _moscavia_world(world):
    """The Owl-folk (other name "Moscavian Owls") and the Tsardom of
    Moscavia. Returns their ids."""

    with world.revision(Source.manual(note="setup")) as rev:
        owls = rev.create_thing(
            "species",
            fields={
                "name": "Owl-folk",
                "aka": [_aka("Moscavian Owls", tag="proper")],
            },
        )
        tsardom = rev.create_thing("place", fields={"name": "Tsardom of Moscavia"})
    return owls, tsardom


def _texts(matches) -> list[str]:
    return [m.text for m in matches]


def test_aka_names_match(world):
    owls, _tsardom = _moscavia_world(world)

    matches = find_names(world.view(None), "The Moscavian Owls' nests, Owl-folk's eggs")

    assert _texts(matches) == ["Moscavian Owls", "Owl-folk"]
    first, second = matches
    assert [(c.id, c.via) for c in first.candidates] == [(owls, "aka")]
    assert first.candidates[0].name == "Owl-folk"
    assert first.candidates[0].kind == "species"
    assert first.candidates[0].stub is False
    assert first.suggested is False
    assert [(c.id, c.via) for c in second.candidates] == [(owls, "name")]
    # longest first: the other name wins over the partial "Moscavian"
    assert (first.start, first.end) == (4, 18)


def test_partial_is_only_suggested(world):
    _owls, tsardom = _moscavia_world(world)
    view = world.view(None)

    (match,) = find_names(view, "Rumours from Moscavia spread")
    assert match.text == "Moscavia"
    assert match.suggested is True
    assert [(c.id, c.via) for c in match.candidates] == [(tsardom, "partial")]

    # the full name is a real match, not a suggestion
    (match,) = find_names(view, "the Tsardom of Moscavia's border")
    assert match.text == "Tsardom of Moscavia"
    assert match.suggested is False
    assert match.candidates[0].via == "name"

    # short words and lowercase mentions are never suggested
    assert find_names(view, "rumours from moscavia") == []
    with world.revision(Source.manual()) as rev:
        rev.create_thing("place", fields={"name": "Isle of Ash"})
    assert find_names(world.view(None), "Ash fell on the Isle") == []

    # a real name beats a partial on the same words, which is offered last
    with world.revision(Source.manual()) as rev:
        city = rev.create_thing("place", fields={"name": "Moscavia"})
    (match,) = find_names(world.view(None), "Rumours from Moscavia spread")
    assert match.suggested is False
    assert [(c.id, c.via) for c in match.candidates] == [
        (city, "name"),
        (tsardom, "partial"),
    ]


def test_common_word_name_needs_a_capital(world):
    with world.revision(Source.manual()) as rev:
        hope = rev.create_thing(
            "place", fields={"name": "Hope", "stub": {"ignored": False}}
        )
        stag = rev.create_thing(
            "place", fields={"name": "The Drowned Stag", "stub": {"ignored": False}}
        )
        river = rev.create_thing("place", fields={"name": "River"})
    view = world.view(None)

    (match,) = find_names(view, "They sailed to Hope.")
    assert match.text == "Hope"
    assert [(c.id, c.stub) for c in match.candidates] == [(hope, True)]
    assert find_names(view, "I hope so") == []
    # a leading article may stay lowercase
    assert _texts(find_names(view, "at the Drowned Stag")) == ["the Drowned Stag"]
    assert find_names(view, "at the drowned stag") == []
    assert find_names(view, "at the Drowned Stag")[0].candidates[0].id == stag
    # an entry that isn't a stub keeps matching in any case
    assert [m.candidates[0].id for m in find_names(view, "down the river")] == [river]


def test_other_names_need_a_capital(world):
    with world.revision(Source.manual()) as rev:
        pier = rev.create_thing(
            "place", fields={"name": "Grey Pier", "aka": [_aka("the Pier")]}
        )
    view = world.view(None)

    assert find_names(view, "walked to the pier") == []
    (match,) = find_names(view, "walked to the Pier")
    assert match.text == "the Pier"
    assert [(c.id, c.via) for c in match.candidates] == [(pier, "aka")]
    # the main name still matches in any case
    assert _texts(find_names(view, "walked to grey pier")) == ["grey pier"]


def test_ignored_stub_not_matched(world):
    with world.revision(Source.manual()) as rev:
        rev.create_thing(
            "lore",
            fields={
                "name": "Night of Feathers",
                "aka": [_aka("the Feathering")],
                "stub": {"ignored": True},
            },
        )
        live = rev.create_thing(
            "lore", fields={"name": "Frosthollow", "stub": {"ignored": False}}
        )
    view = world.view(None)

    assert find_names(view, "Since the Night of Feathers, the Feathering") == []
    # not even suggested
    assert find_names(view, "Feathers everywhere") == []
    (match,) = find_names(view, "Frosthollow")
    assert match.candidates[0].id == live
    assert match.candidates[0].stub is True


def test_first_names_and_ranking(world):
    with world.revision(Source.manual()) as rev:
        vos = rev.create_thing("character", fields={"name": "Maren Vos"})
        holt = rev.create_thing("character", fields={"name": "Maren Holt"})

    (match,) = find_names(world.view(None), "Maren Vos's boat")
    assert match.text == "Maren Vos"
    assert [(c.id, c.via) for c in match.candidates] == [
        (vos, "name"),
        (holt, "first_name"),
    ]
    (match,) = find_names(world.view(None), "maren's boat")
    assert {(c.id, c.via) for c in match.candidates} == {
        (vos, "first_name"),
        (holt, "first_name"),
    }


def test_unknown_phrases(world):
    view = world.view(None)

    found = unknown_proper_phrases(view, "his mother Yelena and the Night of Feathers")
    assert [u.text for u in found] == ["Yelena", "Night of Feathers"]
    assert [(u.start, u.end) for u in found] == [(11, 17), (26, 43)]

    assert unknown_proper_phrases(view, "The postmaster said") == []
    assert unknown_proper_phrases(view, "Then I said no. She left. He hid") == []
    assert [u.text for u in unknown_proper_phrases(view, "Yelena's boat sank")] == []
    assert [
        u.text
        for u in unknown_proper_phrases(view, "It was Yelena's boat, by the Grey Pier.")
    ] == ["Yelena", "Grey Pier"]
    assert [
        u.text for u in unknown_proper_phrases(view, "The Drowned Stag stood empty")
    ] == ["Drowned Stag"]
    # a sentence's opening word isn't part of the name after it
    assert [u.text for u in unknown_proper_phrases(view, "Then Yelena went home.")] == [
        "Yelena"
    ]
    assert [u.text for u in unknown_proper_phrases(view, "But Vasha said no.")] == [
        "Vasha"
    ]
    # contractions of "I", days and months are never names
    assert unknown_proper_phrases(view, "she said I'm fine and I'll go") == []
    assert unknown_proper_phrases(view, "she said I’d go") == []
    assert unknown_proper_phrases(view, "on Monday in March") == []
    assert [
        u.text for u in unknown_proper_phrases(view, "since Monday Vasha Brin waited")
    ] == ["Vasha Brin"]


def test_unknown_phrases_skip_matches(world):
    _moscavia_world(world)
    view = world.view(None)

    found = unknown_proper_phrases(
        view, "her aunt from the Tsardom of Moscavia met Moscavian Owls and Vasha Brin"
    )
    assert [u.text for u in found] == ["Vasha Brin"]
    # a suggested (partial) match is covered too
    assert unknown_proper_phrases(view, "rumours from Moscavia") == []


def test_everyday_name(world):
    with world.revision(Source.manual()) as rev:
        tsardom = rev.create_thing(
            "place",
            fields={
                "name": "Tsardom of Moscavia",
                "aka": [
                    _aka("the Tsardom", tag="proper"),
                    _aka("Moscavia", everyday=True),
                ],
            },
        )
        plain = rev.create_thing(
            "place", fields={"name": "Grey Pier", "aka": [_aka("the Pier")]}
        )
        bare = rev.create_thing("place", fields={"name": "Hope"})
    view = world.view(None)

    assert everyday_name(view.thing(tsardom)) == "Moscavia"
    assert everyday_name(view.thing(plain)) is None
    assert everyday_name(view.thing(bare)) is None
