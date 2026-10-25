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


def test_unknown_phrases_probe_noise(world):
    """The noise Task 3's probe found in the code rule's suggestions."""

    view = world.view(None)

    def texts(text: str) -> list[str]:
        return [u.text for u in unknown_proper_phrases(view, text)]

    # more sentence openers ("Some", "On", ...) drop off a sentence's first phrase
    assert texts("Some Lakewardens fish at night.") == ["Lakewardens"]
    assert texts("On the Night of Feathers they woke.") == ["Night of Feathers"]
    assert texts("Every Lakewood village floats. In Moscavia it snows.") == [
        "Lakewood",
        "Moscavia",
    ]
    # a run goes on across an inner possessive into another capitalised word
    assert texts("She was born at Cairn's Bend.") == ["Cairn's Bend"]
    assert texts("He sat on the Bishops' Council for years.") == ["Bishops' Council"]
    found = unknown_proper_phrases(view, "rest at Yelena's Rest tonight")
    assert [(u.text, u.start, u.end) for u in found] == [("Yelena's Rest", 8, 21)]
    # ...but a possessive in front of a lowercase word still ends the run
    assert texts("It was Yelena's boat.") == ["Yelena"]
    # AM and PM are never names
    assert texts("the bells ring at 6 AM and 9 PM daily") == []
    assert texts("at 6 AM Vasha Brin left") == ["Vasha Brin"]
    # "St." stays inside a run
    assert texts("they prayed in the Cathedral of St. Sophia.") == [
        "Cathedral of St. Sophia"
    ]


def test_title_words_are_no_first_name(world):
    """A leading title isn't a character's first name: "Tsar Alexei II" is
    "Alexei" on his own, never "Tsar", so "the tsar" links nothing."""

    with world.revision(Source.manual(note="setup")) as rev:
        tsar = rev.create_thing("character", fields={"name": "Tsar Alexei II"})
        prince = rev.create_thing("character", fields={"name": "Grand Prince Dmitri I"})
    view = world.view(None)

    assert find_names(view, "The tsar spoke; the Tsar's court; Grand words") == []
    matches = find_names(view, "Alexei met Dmitri.")
    assert [(m.text, m.candidates[0].id, m.suggested) for m in matches] == [
        ("Alexei", tsar, False),
        ("Dmitri", prince, False),
    ]
    # a title word isn't suggested on its own either
    assert find_names(view, "The Prince waited.") == []


def test_adjective_forms_link_like_other_names(world):
    """A capitalised adjective form of a place's, sphere's, species' or
    race's name or other name ("Moscavian", "Kalmaran") links to it, via
    "adjective"; lowercase it doesn't, and a short name ("Uz") makes
    none."""

    with world.revision(Source.manual(note="setup")) as rev:
        moscavia = rev.create_thing("place", fields={"name": "Moscavia"})
        kalmar = rev.create_thing(
            "place",
            fields={"name": "Realm of the Isles", "aka": [_aka("Kalmara")]},
        )
        rev.create_thing("place", fields={"name": "Uz"})
        rev.create_thing("place", fields={"name": "Velm", "stub": {"ignored": True}})
        rev.create_thing("place", fields={"name": "Hume"})
    view = world.view(None)

    (match,) = find_names(view, "Moscavian merchants came.")
    assert match.text == "Moscavian"
    assert match.suggested is False
    assert [(c.id, c.via) for c in match.candidates] == [(moscavia, "adjective")]

    (match,) = find_names(view, "The Kalmaran fleet sailed.")
    assert match.text == "Kalmaran"
    assert [c.id for c in match.candidates] == [kalmar]

    assert find_names(view, "moscavian merchants came.") == []
    assert find_names(view, "Uzian traders came.") == []
    # "Hum" + "an": a capital is needed, so "human" stays plain
    assert find_names(view, "a human trader came.") == []
    # an ignored stub makes no adjective either
    assert find_names(view, "Velmish traders came.") == []


def test_adjective_forms_only_for_peoples_and_places(world):
    """A character, item or lore entry makes no adjective forms: "Julian"
    never means Julia."""

    with world.revision(Source.manual(note="setup")) as rev:
        rev.create_thing("character", fields={"name": "Julia"})
        rev.create_thing("item", fields={"name": "Drago"})
        rev.create_thing("lore", fields={"name": "Vesta"})
        magi = rev.create_thing("place", fields={"name": "Magi"})
        owls = rev.create_thing("species", fields={"name": "Strix"})
    view = world.view(None)

    assert find_names(view, "Julian, Dragon and Vestan came.") == []
    assert [c.id for c in find_names(view, "A Magian came.")[0].candidates] == [magi]
    assert [c.id for c in find_names(view, "A Strixian came.")[0].candidates] == [owls]


def test_other_name_beats_adjective_form(world):
    """An entry's other name that's also another's adjective form means
    that entry first."""

    with world.revision(Source.manual(note="setup")) as rev:
        rev.create_thing("place", fields={"name": "Moscavia"})
        people = rev.create_thing(
            "race", fields={"name": "Moscavian folk", "aka": [_aka("Moscavians")]}
        )
        tongue = rev.create_thing(
            "lore", fields={"name": "Old tongue", "aka": [_aka("Moscavian")]}
        )
    view = world.view(None)

    (match,) = find_names(view, "Moscavian is spoken.")
    # the other name, then the adjective, then the partial suggestion
    assert [(c.id, c.via) for c in match.candidates][0] == (tongue, "aka")
    assert [c.via for c in match.candidates] == ["aka", "adjective", "partial"]
    assert match.candidates[2].id == people


def test_a_lowercase_led_name_matches_as_written(world):
    """A name stored with a lowercase first word ("river Vilya") can't
    meet the capital rule: it matches where the text writes it exactly as
    stored, for a main name and an other name alike; written in any other
    case it's left alone (a stub's "Vilya" stays only a suggestion)."""

    with world.revision(Source.manual()) as rev:
        vilya = rev.create_thing(
            "place",
            fields={
                "name": "river Vilya",
                "aka": [_aka("old Vilya water")],
                "stub": {"ignored": False},
            },
        )
    view = world.view(None)

    (match,) = find_names(view, "overlooking the frozen river Vilya")
    assert match.text == "river Vilya"
    assert match.suggested is False
    assert [(c.id, c.via) for c in match.candidates] == [(vilya, "name")]

    (match,) = find_names(view, "they drank old Vilya water")
    assert match.text == "old Vilya water"
    assert [(c.id, c.via) for c in match.candidates] == [(vilya, "aka")]

    # any other case still needs the capital the rule asks for
    assert find_names(view, "the river vilya") == []
    assert find_names(view, "they drank old vilya water") == []
    (match,) = find_names(view, "the river vilya and Vilya")
    assert (match.text, match.suggested) == ("Vilya", True)
