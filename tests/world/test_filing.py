"""Tags and filings: an entry's one `tag` and its dated `filings` into other
entries, read through a `WorldView` (filings of a thing, what's filed in
one, its Connected groups by tag, mentions that aren't filings, tags in
use)."""

import pytest

from talemate.world.dates import WorldDate
from talemate.world.filing import (
    Filing,
    connected,
    filed_in,
    filings_of,
    mentioned_in,
    sits_in,
    tag_heading,
    tags_in_use,
)
from talemate.world.refs import ref
from talemate.world.store import Source


def _filing(target, role=None, since=None, until=None, within=None, exceptions=None):
    return {
        "target": target,
        "role": role,
        "since": since.model_dump(mode="json") if since else None,
        "until": until.model_dump(mode="json") if until else None,
        "within": within,
        "exceptions": exceptions or [],
    }


def _thing(rev, kind, name, tag=None, filings=None):
    fields: dict[str, object] = {"name": name}
    if tag is not None:
        fields["tag"] = tag
    if filings is not None:
        fields["filings"] = filings
    return rev.create_thing(kind, fields=fields)


def test_filings_round_trip_dated(world):
    with world.revision(Source.manual()) as rev:
        velikoye = _thing(rev, "place", "Velikoye", tag="city")
        kerensky = _thing(rev, "place", "Kerensky", tag="city")
        dance = _thing(
            rev,
            "lore",
            "The Feather Dance",
            tag="  Custom ",
            filings=[
                _filing(velikoye, since=WorldDate.of(900), until=WorldDate.of(1015)),
                _filing(kerensky, role="danced at midsummer", since=WorldDate.of(1012)),
            ],
        )

    state = world.view().thing(dance)
    # the tag is stored lowercased and stripped
    assert state.fields["tag"] == "custom"

    stored = filings_of(world.view(), dance, live=False)
    assert stored == [
        Filing(
            target=velikoye,
            role=None,
            since=WorldDate.of(900),
            until=WorldDate.of(1015),
            within=None,
            exceptions=[],
        ),
        Filing(
            target=kerensky,
            role="danced at midsummer",
            since=WorldDate.of(1012),
            until=None,
            within=None,
            exceptions=[],
        ),
    ]

    # live: each filing only over its own dates
    assert [f.target for f in filings_of(world.view(WorldDate.of(950)), dance)] == [
        velikoye
    ]
    assert [f.target for f in filings_of(world.view(WorldDate.of(1013)), dance)] == [
        velikoye,
        kerensky,
    ]
    assert [f.target for f in filings_of(world.view(WorldDate.of(1020)), dance)] == [
        kerensky
    ]
    # the latest telling: what hasn't ended
    assert [f.target for f in filings_of(world.view(), dance)] == [kerensky]
    assert filings_of(world.view(WorldDate.of(800)), dance) == []

    # a comma-joined tag keeps its first part (ruling F8)
    with world.revision(Source.manual()) as rev:
        rev.set_field(dance, "tag", "Ritual, custom", None)
    assert world.view().thing(dance).fields["tag"] == "ritual"


def test_filing_validation_rules(world):
    with world.revision(Source.manual()) as rev:
        velikoye = _thing(rev, "place", "Velikoye")
        dance = _thing(rev, "lore", "The Feather Dance")

    with pytest.raises(ValueError):
        with world.revision(Source.manual()) as rev:
            rev.set_field(
                dance, "filings", [_filing(velikoye), _filing(velikoye)], None
            )
    with pytest.raises(ValueError):
        with world.revision(Source.manual()) as rev:
            rev.set_field(dance, "filings", [_filing(dance)], None)
    with pytest.raises(ValueError):
        with world.revision(Source.manual()) as rev:
            rev.set_field(dance, "filings", [{"target": "nope"}], None)
    with pytest.raises(ValueError):
        with world.revision(Source.manual()) as rev:
            rev.set_field(dance, "tag", 3, None)


def test_connected_groups_by_tag(world):
    with world.revision(Source.manual()) as rev:
        velikoye = _thing(rev, "place", "Velikoye", tag="city")
        tsar = _thing(
            rev,
            "character",
            "Tsar Ivo",
            tag="ruler",
            filings=[_filing(velikoye, role="rules")],
        )
        neva = _thing(
            rev,
            "place",
            "The Neva",
            tag="river",
            filings=[_filing(velikoye, role="flows through")],
        )
        oka = _thing(
            rev,
            "place",
            "The Oka",
            tag="river",
            filings=[_filing(velikoye, role="flows through")],
        )
        dance = _thing(
            rev,
            "lore",
            "The Feather Dance",
            tag="custom",
            filings=[_filing(velikoye, since=WorldDate.of(900))],
        )
        # filed elsewhere: not in Velikoye's groups
        _thing(rev, "place", "Vosgrad", tag="city")

    groups = connected(world.view(), velikoye)
    assert [(g.tag, g.heading) for g in groups] == [
        ("river", "Rivers"),
        ("custom", "Customs"),
        ("ruler", "Rulers"),
    ]
    assert [thing_id for thing_id, _ in groups[0].rows] == [neva, oka]
    assert groups[0].rows[0][1].role == "flows through"
    assert [thing_id for thing_id, _ in groups[1].rows] == [dance]
    assert [thing_id for thing_id, _ in groups[2].rows] == [tsar]

    # changing an entry's tag moves it to the matching group
    with world.revision(Source.manual()) as rev:
        rev.set_field(oka, "tag", "custom", None)
    groups = connected(world.view(), velikoye)
    assert [(g.heading, len(g.rows)) for g in groups] == [
        ("Customs", 2),
        ("Rivers", 1),
        ("Rulers", 1),
    ]


def test_untagged_goes_to_other(world):
    with world.revision(Source.manual()) as rev:
        velikoye = _thing(rev, "place", "Velikoye", tag="city")
        bell = _thing(rev, "item", "The Great Bell", filings=[_filing(velikoye)])
        neva = _thing(
            rev, "place", "The Neva", tag="river", filings=[_filing(velikoye)]
        )

    groups = connected(world.view(), velikoye)
    assert [(g.tag, g.heading) for g in groups] == [
        (None, "Other"),
        ("river", "Rivers"),
    ]
    assert [thing_id for thing_id, _ in groups[0].rows] == [bell]
    assert [thing_id for thing_id, _ in groups[1].rows] == [neva]


def test_within_lists_person_under_both(world):
    with world.revision(Source.manual()) as rev:
        army = _thing(rev, "lore", "The Tsar's Army", tag="army")
        talon = _thing(
            rev, "lore", "The White Talon", tag="regiment", filings=[_filing(army)]
        )
        vasha = _thing(
            rev,
            "character",
            "Vasha",
            tag="soldier",
            filings=[_filing(army, role="captain", within=talon)],
        )

    in_army = filed_in(world.view(), army)
    assert [(state.id, f.within) for state, f in in_army] == [
        (talon, None),
        (vasha, talon),
    ]
    in_talon = filed_in(world.view(), talon)
    assert [(state.id, f.role) for state, f in in_talon] == [(vasha, "captain")]

    # `within` must sit in the target
    with world.revision(Source.manual()) as rev:
        stray = _thing(rev, "lore", "The Stray Company")
    with pytest.raises(ValueError):
        with world.revision(Source.manual()) as rev:
            rev.set_field(vasha, "filings", [_filing(army, within=stray)], None)


def test_filing_cycle_refused(world):
    with world.revision(Source.manual()) as rev:
        realm = _thing(rev, "place", "The Realm")
        province = _thing(rev, "place", "The Province", filings=[_filing(realm)])
        town = _thing(rev, "place", "The Town", filings=[_filing(province)])

    view = world.view()
    assert sits_in(view, town, realm)
    assert sits_in(view, town, town)
    assert not sits_in(view, realm, town)

    with pytest.raises(ValueError):
        with world.revision(Source.manual()) as rev:
            rev.set_field(realm, "filings", [_filing(town)], None)
    assert filings_of(world.view(), realm) == []


def test_filing_to_deleted_target_hidden_then_back(world):
    with world.revision(Source.manual()) as rev:
        velikoye = _thing(rev, "place", "Velikoye", tag="city")
        dance = _thing(
            rev,
            "lore",
            "The Feather Dance",
            tag="custom",
            filings=[_filing(velikoye)],
        )

    with world.revision(Source.manual()) as rev:
        rev.remove_thing(velikoye)
        removed = rev.rev

    assert filings_of(world.view(), dance) == []
    # still stored, only hidden
    assert [f.target for f in filings_of(world.view(), dance, live=False)] == [velikoye]

    world.undo([removed])
    assert [f.target for f in filings_of(world.view(), dance)] == [velikoye]
    assert [state.id for state, _ in filed_in(world.view(), velikoye)] == [dance]


def test_mentioned_in_excludes_filed(world):
    with world.revision(Source.manual()) as rev:
        velikoye = _thing(rev, "place", "Velikoye", tag="city")
        dance = _thing(rev, "lore", "The Feather Dance", filings=[_filing(velikoye)])
        rev.add_fact(dance, "general", f"First danced in {ref(velikoye)}.")
        vasha = _thing(rev, "character", "Vasha")
        rev.add_fact(vasha, "background", f"Grew up in {ref(velikoye)}.")
        oskar = _thing(rev, "character", "Oskar")
        rev.add_fact(
            oskar,
            "background",
            f"Left {ref(velikoye)} in 1010.",
            valid_until=WorldDate.of(1010),
        )
        rev.add_fact(velikoye, "history", f"Home of {ref(velikoye)}'s bells.")

    # Oskar's fact has ended at the latest telling; Velikoye never mentions
    # itself; the dance is filed in it
    assert mentioned_in(world.view(), velikoye) == [vasha]
    assert mentioned_in(world.view(WorldDate.of(1000)), velikoye) == [vasha, oskar]


def test_tags_in_use_counts(world):
    with world.revision(Source.manual()) as rev:
        _thing(rev, "place", "The Neva", tag="river")
        _thing(rev, "place", "The Oka", tag="River")
        _thing(rev, "lore", "The Feather Dance", tag="custom")
        _thing(rev, "place", "Velikoye", tag="city")
        _thing(rev, "item", "The Great Bell")
        gone = _thing(rev, "lore", "The Lost Rite", tag="custom")
        _thing(rev, "lore", "The Spring Fast", tag="custom")
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(gone)

    assert tags_in_use(world.view()) == [
        ("custom", 2),
        ("river", 2),
        ("city", 1),
    ]


def test_tag_heading_plurals():
    assert tag_heading("river") == "Rivers"
    assert tag_heading("custom") == "Customs"
    assert tag_heading("capital") == "Capitals"
    assert tag_heading("church") == "Churches"
    assert tag_heading("city") == "Cities"
    assert tag_heading("holy site") == "Holy sites"
