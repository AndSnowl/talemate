"""Linking names in text (keeping the written words) and making stubs for
the names a generation invents."""

from talemate.world.refs import ref
from talemate.world.store import Source
from talemate.worldplay.links import NewName, link_text, make_stubs


def _aka(name: str, tag: str = "common", everyday: bool = False) -> dict:
    return {"name": name, "tag": tag, "everyday": everyday}


def _moscavia_world(world):
    """The Owl-folk species (other name "Moscavian Owls"), the Tsardom of
    Moscavia (everyday name "Moscavia"), and a lore entry named "Hope".
    Returns their ids."""

    with world.revision(Source.manual(note="setup")) as rev:
        owls = rev.create_thing(
            "species",
            fields={"name": "Owl-folk", "aka": [_aka("Moscavian Owls", tag="proper")]},
        )
        tsardom = rev.create_thing(
            "place",
            fields={
                "name": "Tsardom of Moscavia",
                "aka": [_aka("Moscavia", everyday=True)],
            },
        )
        hope = rev.create_thing(
            "lore", fields={"name": "Hope", "stub": {"ignored": False}}
        )
    return owls, tsardom, hope


def test_link_text_keeps_words(world):
    owls, tsardom, _hope = _moscavia_world(world)
    view = world.view(None)

    linked = link_text(view, "Moscavia's border")
    assert linked == ref(tsardom, "Moscavia's") + " border"
    assert view.render(linked) == "Moscavia's border"

    text = "The Owl-folk of the Tsardom of Moscavia; I hope Moscavian Owls fly."
    linked = link_text(view, text)
    assert linked == (
        f"The {ref(owls, 'Owl-folk')} of the {ref(tsardom, 'Tsardom of Moscavia')}; "
        f"I hope {ref(owls, 'Moscavian Owls')} fly."
    )
    assert view.render(linked) == text


def test_link_text_leaves_references_alone(world):
    owls, tsardom, _hope = _moscavia_world(world)
    view = world.view(None)

    text = f"{ref(tsardom, 'Moscavia')} and {ref(owls)} met the Owl-folk"
    assert link_text(view, text) == (
        f"{ref(tsardom, 'Moscavia')} and {ref(owls)} met the {ref(owls, 'Owl-folk')}"
    )
    # linking twice changes nothing
    assert link_text(view, link_text(view, text)) == link_text(view, text)


def test_link_text_respects_picks_and_skips_suggested(world):
    with world.revision(Source.manual(note="setup")) as rev:
        maren_vos = rev.create_thing("character", fields={"name": "Maren Vos"})
        maren_holt = rev.create_thing("character", fields={"name": "Maren Holt"})
        tsardom = rev.create_thing("place", fields={"name": "Tsardom of Moscavia"})
        frost = rev.create_thing("place", fields={"name": "Frosthollow"})
    view = world.view(None)

    # "Maren" alone means either; the best candidate is the default...
    text = "Maren sailed from Moscavia to Maren Vos and Frosthollow"
    assert link_text(view, text) == (
        f"{ref(maren_holt, 'Maren')} sailed from Moscavia to "
        f"{ref(maren_vos, 'Maren Vos')} and {ref(frost, 'Frosthollow')}"
    )
    # ...the owner's pick wins, a pick links a suggested match, and the full
    # name "Maren Vos" still links to its own entry
    picks = {"Maren": maren_vos, "Moscavia": tsardom, "Frosthollow": maren_holt}
    assert link_text(view, text, picks=picks) == (
        f"{ref(maren_vos, 'Maren')} sailed from {ref(tsardom, 'Moscavia')} to "
        f"{ref(maren_vos, 'Maren Vos')} and {ref(maren_holt, 'Frosthollow')}"
    )


def test_link_text_links_new_names(world):
    _owls, tsardom, _hope = _moscavia_world(world)
    view = world.view(None)
    with world.revision(Source.manual(note="stubs")) as rev:
        stubs = make_stubs(rev, view, [NewName(name="Night of Feathers", kind="event")])
        # the stub isn't in `view` yet: `new_names` links it
        linked = link_text(
            view,
            "On the Night of Feathers, Moscavia woke; the night of feathers ended.",
            new_names=stubs,
        )
    night = stubs["Night of Feathers"]
    assert linked == (
        f"On the {ref(night, 'Night of Feathers')}, {ref(tsardom, 'Moscavia')} "
        "woke; the night of feathers ended."
    )


def test_make_stubs_reuses_existing_name(world):
    """Frosthollow, named by Vasha and later by a place, is one stub with two
    mentions (Review Focus 4)."""

    owls, tsardom, _hope = _moscavia_world(world)
    with world.revision(Source.manual(note="vasha")) as rev:
        first = make_stubs(
            rev,
            world.view(None),
            [NewName(name="Frosthollow", kind="place", aka=[_aka("the Hollow")])],
        )
        frost = first["Frosthollow"]
        assert first == {"Frosthollow": frost, "the Hollow": frost}
        vasha = rev.create_thing("character", fields={"name": "Vasha"})
        rev.add_fact(vasha, "background", f"Born in {ref(frost, 'Frosthollow')}.")

    view = world.view(None)
    stub = view.thing(frost)
    assert stub.kind == "place"
    assert stub.fields == {
        "name": "Frosthollow",
        "aka": [_aka("the Hollow")],
        "stub": {"ignored": False},
    }

    with world.revision(Source.manual(note="place")) as rev:
        second = make_stubs(
            rev,
            view,
            [
                NewName(name=" frosthollow ", kind="place"),
                NewName(name="The Hollow", kind="place"),
                # other names and the main name with its article count too
                NewName(name="Moscavia", kind="culture"),
                NewName(name="The Owl-folk", kind="species"),
                # a name containing an entry's name, as a species or race,
                # is that entry
                NewName(name="Moscavian Owl-folk", kind="species"),
                NewName(name="Moscavian Owls of the North", kind="race"),
                # twice in one call is one stub
                NewName(name="River Sere", kind="place"),
                NewName(name="the River Sere", kind="place"),
            ],
        )
        sere = second["River Sere"]
        assert second == {
            "frosthollow": frost,
            "The Hollow": frost,
            "Moscavia": tsardom,
            "The Owl-folk": owls,
            "Moscavian Owl-folk": owls,
            "Moscavian Owls of the North": owls,
            "River Sere": sere,
            "the River Sere": sere,
        }
        town = rev.create_thing("place", fields={"name": "Icemarch"})
        rev.add_fact(town, "general", f"North of {ref(frost, 'Frosthollow')}.")

    view = world.view(None)
    assert sorted(owner for owner, _fact in view.referencing(frost)) == sorted(
        [vasha, town]
    )
    assert sorted(s.fields["name"] for s in view.things() if s.is_stub) == [
        "Frosthollow",
        "Hope",
        "River Sere",
    ]


def test_make_stubs_containment_needs_a_matching_kind(world):
    owls, tsardom, _hope = _moscavia_world(world)
    with world.revision(Source.manual(note="stubs")) as rev:
        made = make_stubs(
            rev,
            world.view(None),
            [
                # a place containing a place's name is that place
                NewName(name="Moscavia Proper", kind="place"),
                # but an event containing a place's name isn't
                NewName(name="Siege of Moscavia", kind="event"),
                # nor is a species containing a place's name
                NewName(name="Moscavia Owls", kind="species"),
                # and a part of a word doesn't count
                NewName(name="Owl-folkish Kin", kind="species"),
            ],
        )
    assert made["Moscavia Proper"] == tsardom
    new = {made["Siege of Moscavia"], made["Moscavia Owls"], made["Owl-folkish Kin"]}
    assert len(new) == 3 and not new & {owls, tsardom}


def test_make_stubs_unknown_kind_is_lore(world):
    with world.revision(Source.manual(note="stubs")) as rev:
        made = make_stubs(
            rev,
            world.view(None),
            [
                NewName(name="Code of Talons", kind="title"),
                NewName(name="Lake Solnech", kind=" Place "),
                NewName(
                    name="Tsardom of Moscavia",
                    kind="place",
                    aka=[
                        {"name": "Moscavia", "tag": "common", "everyday": True},
                        {"name": "the Old Tsardom", "tag": "former name"},
                        {"name": "Tsardom of Moscavia", "tag": "proper"},
                        {"name": "Moscavia", "tag": "proper"},
                        {"name": "Owl Country", "tag": "common", "everyday": True},
                        {"name": "Lake Solnech", "tag": "common"},
                        {"name": "", "tag": "common"},
                        {"tag": "common"},
                    ],
                ),
                NewName(name="  ", kind="place"),
            ],
        )
    view = world.view(None)
    code = view.thing(made["Code of Talons"])
    assert code.kind == "lore"
    assert code.fields == {
        "name": "Code of Talons",
        "aka": [],
        "stub": {"ignored": False},
    }
    assert view.thing(made["Lake Solnech"]).kind == "place"

    # other names are cleaned up into the shape `aka` holds: an unknown tag
    # is proper, one everyday name, and no repeats of its own or another
    # entry's name
    tsardom = view.thing(made["Tsardom of Moscavia"])
    assert tsardom.fields["aka"] == [
        _aka("Moscavia", everyday=True),
        _aka("the Old Tsardom", tag="proper"),
        _aka("Owl Country"),
    ]
    assert made["Moscavia"] == made["Owl Country"] == tsardom.id
    assert set(made) == {
        "Code of Talons",
        "Lake Solnech",
        "Tsardom of Moscavia",
        "Moscavia",
        "the Old Tsardom",
        "Owl Country",
    }
