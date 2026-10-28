"""Tags and filings: an entry's one `tag` and its dated `filings` into other
entries, read through a `WorldView` (filings of a thing, what's filed in
one, its Connected groups by tag, mentions that aren't filings, tags in
use)."""

import json

import pytest

from talemate.world.dates import WorldDate
from talemate.world.filing import (
    Filing,
    connected,
    filed_in,
    filings_of,
    mentioned_in,
    sits_in,
    roles_in_use,
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
    # polish 5: groups by the earliest kind they hold (the ruler is a
    # character), then by heading
    assert [(g.tag, g.heading) for g in groups] == [
        ("ruler", "Rulers"),
        ("river", "Rivers"),
        ("custom", "Customs"),
    ]
    assert [thing_id for thing_id, _ in groups[1].rows] == [neva, oka]
    assert groups[1].rows[0][1].role == "flows through"
    assert [thing_id for thing_id, _ in groups[2].rows] == [dance]
    assert [thing_id for thing_id, _ in groups[0].rows] == [tsar]

    # changing an entry's tag moves it to the matching group
    with world.revision(Source.manual()) as rev:
        rev.set_field(oka, "tag", "custom", None)
    groups = connected(world.view(), velikoye)
    assert [(g.heading, len(g.rows)) for g in groups] == [
        ("Rulers", 1),
        ("Customs", 2),
        ("Rivers", 1),
    ]


def test_untagged_goes_to_other(world):
    with world.revision(Source.manual()) as rev:
        velikoye = _thing(rev, "place", "Velikoye", tag="city")
        bell = _thing(rev, "item", "The Great Bell", filings=[_filing(velikoye)])
        neva = _thing(
            rev, "place", "The Neva", tag="river", filings=[_filing(velikoye)]
        )

    groups = connected(world.view(), velikoye)
    # polish 5: Other comes last
    assert [(g.tag, g.heading) for g in groups] == [
        ("river", "Rivers"),
        (None, "Other"),
    ]
    assert [thing_id for thing_id, _ in groups[1].rows] == [bell]
    assert [thing_id for thing_id, _ in groups[0].rows] == [neva]


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

    # filed in the Talon directly and within it through the Army: listed
    # once, by the direct filing
    with world.revision(Source.manual()) as rev:
        oleg = _thing(
            rev,
            "character",
            "Oleg",
            filings=[
                _filing(army, role="sergeant", within=talon),
                _filing(talon, role="drummer"),
            ],
        )
    in_talon = filed_in(world.view(), talon)
    assert [(state.id, f.role) for state, f in in_talon] == [
        (vasha, "captain"),
        (oleg, "drummer"),
    ]

    # `within` must sit in the target
    with world.revision(Source.manual()) as rev:
        stray = _thing(rev, "lore", "The Stray Company")
    with pytest.raises(ValueError):
        with world.revision(Source.manual()) as rev:
            rev.set_field(vasha, "filings", [_filing(army, within=stray)], None)

    # a `within` whose part is deleted: still in the target, under nothing
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(talon)
    assert [(state.id, f.within) for state, f in filed_in(world.view(), army)] == [
        (vasha, talon),
        (oleg, talon),
    ]
    assert filed_in(world.view(), talon) == []


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


def test_filing_cycle_through_deleted_refused(world):
    with world.revision(Source.manual()) as rev:
        a = _thing(rev, "place", "A")
        b = _thing(rev, "place", "B", filings=[_filing(a)])
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(b)

    # B is gone, but undoing its removal would close the cycle A -> B -> A
    with pytest.raises(ValueError):
        with world.revision(Source.manual()) as rev:
            rev.set_field(a, "filings", [_filing(b)], None)


def test_filings_stored_in_full_shape_blank_role_none(world):
    with world.revision(Source.manual()) as rev:
        velikoye = _thing(rev, "place", "Velikoye")
        dance = _thing(
            rev,
            "lore",
            "The Feather Dance",
            filings=[{"target": velikoye, "role": "   "}],
        )
    assert world.view().thing(dance).fields["filings"] == [
        {
            "target": velikoye,
            "role": None,
            "since": None,
            "until": None,
            "within": None,
            "exceptions": [],
            "show_under": None,
        }
    ]


def test_connected_rows_role_since_name_order(world):
    with world.revision(Source.manual()) as rev:
        hall = _thing(rev, "place", "The Hall", tag="hall")
        plain = _thing(rev, "lore", "Aa plain", tag="custom", filings=[_filing(hall)])
        b_role = _thing(
            rev, "lore", "Bb", tag="custom", filings=[_filing(hall, role="b")]
        )
        a_late = _thing(
            rev,
            "lore",
            "Aa late",
            tag="custom",
            filings=[_filing(hall, role="a", since=WorldDate.of(1000))],
        )
        a_early = _thing(
            rev,
            "lore",
            "Zz early",
            tag="custom",
            filings=[_filing(hall, role="a", since=WorldDate.of(900))],
        )
        a_undated_z = _thing(
            rev, "lore", "Zz undated", tag="custom", filings=[_filing(hall, role="a")]
        )
        a_undated_m = _thing(
            rev, "lore", "Mm undated", tag="custom", filings=[_filing(hall, role="a")]
        )

    (group,) = connected(world.view(), hall)
    assert [thing_id for thing_id, _ in group.rows] == [
        a_undated_m,
        a_undated_z,
        a_early,
        a_late,
        b_role,
        plain,
    ]


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


def test_within_listing_reads_dates(world):
    """Parked M3 (fixed in Task 3): a person filed `within` a part is
    listed under the part only while the part's own filing into the
    target holds at the view's date."""

    with world.revision(Source.manual()) as rev:
        army = _thing(rev, "lore", "The Tsar's Army")
        talon = _thing(
            rev,
            "lore",
            "The White Talon",
            filings=[_filing(army, since=WorldDate.of(900), until=WorldDate.of(1000))],
        )
        vasha = _thing(rev, "character", "Vasha", filings=[_filing(army, within=talon)])

    def under_talon(year=None):
        view = world.view(WorldDate.of(year) if year is not None else None)
        return [state.id for state, _ in filed_in(view, talon)]

    assert under_talon(950) == [vasha]
    # before the Talon joined the Army, and after it left: in the Army alone
    assert under_talon(850) == []
    assert under_talon(1050) == []
    assert under_talon() == []
    assert [state.id for state, _ in filed_in(world.view(), army)] == [vasha]


def test_include_ended_lists_what_has_ended(world):
    with world.revision(Source.manual()) as rev:
        velikoye = _thing(rev, "place", "Velikoye", tag="city")
        dance = _thing(
            rev,
            "lore",
            "The Feather Dance",
            tag="custom",
            filings=[
                _filing(velikoye, since=WorldDate.of(900), until=WorldDate.of(1015))
            ],
        )
        rev.add_fact(dance, "general", f"Danced in {ref(velikoye, 'Velikoye')}.")
    view = world.view()
    assert connected(view, velikoye) == []
    assert mentioned_in(view, velikoye) == [dance]
    (group,) = connected(view, velikoye, include_ended=True)
    assert [row[0] for row in group.rows] == [dance]
    assert group.rows[0][1].until == WorldDate.of(1015)
    assert [s.id for s, _ in filed_in(view, velikoye, include_ended=True)] == [dance]
    assert mentioned_in(view, velikoye, include_ended=True) == []


def test_tags_in_use_leaves_out_ignored_stubs(world):
    with world.revision(Source.manual()) as rev:
        _thing(rev, "place", "Velikoye", tag="city")
        rev.create_thing(
            "place",
            {"name": "Kerensky", "tag": "city", "stub": {"ignored": True}},
        )
        rev.create_thing(
            "lore", {"name": "Hush", "tag": "secret", "stub": {"ignored": True}}
        )
    assert tags_in_use(world.view()) == [("city", 1)]


def test_retag_reaches_removed_things_and_undoes_exactly(world):
    with world.revision(Source.manual()) as rev:
        kept = _thing(rev, "lore", "Rune School", tag="school")
        gone = _thing(rev, "lore", "Old School", tag="school")
        rev.set_field(kept, "tag", "School", WorldDate.of(900))
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(gone)
    deleted = world.head_rev()
    with world.revision(Source.manual()) as rev:
        assert rev.retag("school", "Academy") == sorted([kept, gone])
    retagged = world.head_rev()
    assert world.view().thing(kept).fields["tag"] == "academy"
    assert world.view(WorldDate.of(950)).thing(kept).fields["tag"] == "academy"
    assert world.view().thing(gone) is None

    world.undo([retagged])
    assert world.view(WorldDate.of(950)).thing(kept).fields["tag"] == "school"
    world.undo([deleted])
    assert world.view().thing(gone).fields["tag"] == "school"


@pytest.mark.parametrize("at", [None, WorldDate.of(950), WorldDate.of(1020)])
def test_one_filing_index_reads_as_filed_index_both_ways(world, at):
    """A page's shared `FilingIndex` (final review I4) gives what
    `filed_index` gives, with ended filings and without, at the latest
    telling and at dates: direct rows, `within` rows (a part that moved
    out of its target), a direct filing that ended beside a live one
    within, and a filing not begun yet."""

    from talemate.world.filing import FilingIndex, filed_index

    with world.revision(Source.manual()) as rev:
        army = _thing(rev, "lore", "The Tsar's Army", tag="army")
        talon = _thing(
            rev,
            "lore",
            "The White Talon",
            tag="regiment",
            filings=[_filing(army, until=WorldDate.of(1000))],
        )
        _thing(
            rev,
            "character",
            "Vasha",
            filings=[
                _filing(army, role="captain", within=talon),
                _filing(talon, role="drummer", until=WorldDate.of(990)),
            ],
        )
        _thing(
            rev,
            "place",
            "Fort",
            filings=[_filing(army, since=WorldDate.of(1010))],
        )
    view = world.view(at)
    index = FilingIndex(view)
    for ended in (False, True):
        assert index.get(ended) == filed_index(view, include_ended=ended)
    assert [s.id for s in index.things] == [s.id for s in view.things()]
    with pytest.raises(ValueError):
        FilingIndex(view, include_ended=(False,)).get(True)


def test_show_under_groups_row(world):
    """A filing's `show_under` (a tag-pool value, normalised) is the
    group the row shows under on the target's page; the entry's own tag
    still groups it on other pages."""

    with world.revision(Source.manual()) as rev:
        ustyug = _thing(rev, "place", "Velikiy Ustyug", tag="city")
        post = _thing(rev, "lore", "Postal HQ", tag="institution")
        vasha = _thing(
            rev,
            "character",
            "Vasha",
            tag="postal worker",
            filings=[
                {**_filing(ustyug, role="native"), "show_under": "  Native, folk "},
                _filing(post, role="carrier owl"),
            ],
        )
        _thing(rev, "character", "Olga", tag="postal worker", filings=[_filing(ustyug)])

    # stored normalised (lowercased, its first comma part)
    stored = world.view().thing(vasha).fields["filings"]
    assert stored[0]["show_under"] == "native"
    assert stored[1]["show_under"] is None

    groups = connected(world.view(), ustyug)
    assert [(g.tag, g.heading) for g in groups] == [
        ("native", "Natives"),
        ("postal worker", "Postal workers"),
    ]
    assert [thing_id for thing_id, _ in groups[0].rows] == [vasha]
    assert groups[0].rows[0][1].show_under == "native"
    # on the HQ's page, the entry's own tag
    assert [g.tag for g in connected(world.view(), post)] == ["postal worker"]
    # a blank one is none
    with world.revision(Source.manual()) as rev:
        rev.set_field(vasha, "filings", [{**_filing(ustyug), "show_under": "  "}], None)
    assert world.view().thing(vasha).fields["filings"][0]["show_under"] is None
    # show_under values count as tags in use, once per entry
    with world.revision(Source.manual()) as rev:
        rev.set_field(
            vasha,
            "filings",
            [
                {**_filing(ustyug), "show_under": "native"},
                {**_filing(post), "show_under": "native"},
            ],
            None,
        )
    assert dict(tags_in_use(world.view()))["native"] == 1
    # but not as a tag an entry carries (I2: the AI's tags in use)
    assert "native" not in dict(tags_in_use(world.view(), show_under=False))
    with pytest.raises(ValueError):
        with world.revision(Source.manual()) as rev:
            rev.set_field(
                vasha, "filings", [{**_filing(ustyug), "show_under": 3}], None
            )


def test_show_under_absent_groups_by_tag(world):
    """A filing stored before `show_under` existed (no key) reads as one
    without: grouped by the entry's tag, exactly as before."""

    with world.revision(Source.manual()) as rev:
        ustyug = _thing(rev, "place", "Velikiy Ustyug", tag="city")
        vasha = _thing(rev, "character", "Vasha", tag="postal worker")
    # the old shape, written straight to the store (no `show_under` key)
    old = _filing(ustyug, role="native")
    with world.revision(Source.manual()) as rev:
        rev.set_field(vasha, "filings", [old], None)
    world._conn.execute(
        "UPDATE field_values SET value_json = ? "
        "WHERE thing_id = ? AND field = 'filings' AND rev_removed IS NULL",
        (json.dumps([old]), vasha),
    )
    assert "show_under" not in world.view().thing(vasha).fields["filings"][0]

    (filing,) = filings_of(world.view(), vasha)
    assert filing.show_under is None
    groups = connected(world.view(), ustyug)
    assert [(g.tag, g.heading) for g in groups] == [("postal worker", "Postal workers")]


def test_rename_tag_reaches_show_under(world):
    """`retag` rewrites `show_under` as it does tags: at every date, on a
    removed entry too, and one undo puts it all back."""

    with world.revision(Source.manual()) as rev:
        ustyug = _thing(rev, "place", "Velikiy Ustyug", tag="city")
        vasha = _thing(
            rev,
            "character",
            "Vasha",
            tag="postal worker",
            filings=[{**_filing(ustyug), "show_under": "native"}],
        )
        rev.set_field(
            vasha,
            "filings",
            [{**_filing(ustyug, role="born here"), "show_under": "native"}],
            WorldDate.of(900),
        )
        gone = _thing(
            rev,
            "character",
            "Pyotr",
            filings=[{**_filing(ustyug), "show_under": "native"}],
        )
        other = _thing(
            rev,
            "character",
            "Olga",
            filings=[{**_filing(ustyug), "show_under": "visitor"}],
        )
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(gone)
    deleted = world.head_rev()
    with world.revision(Source.manual()) as rev:
        assert rev.retag("Native", "local") == sorted([vasha, gone])
    retagged = world.head_rev()

    def under(thing_id, at=None):
        return [f.show_under for f in filings_of(world.view(at), thing_id, live=False)]

    assert under(vasha) == ["local"]
    assert under(vasha, WorldDate.of(950)) == ["local"]
    assert filings_of(world.view(WorldDate.of(950)), vasha)[0].role == "born here"
    assert under(other) == ["visitor"]
    assert [g.tag for g in connected(world.view(), ustyug)] == ["local", "visitor"]

    world.undo([retagged])
    assert under(vasha) == ["native"]
    assert under(vasha, WorldDate.of(950)) == ["native"]
    world.undo([deleted])
    assert under(gone) == ["native"]


def test_roles_in_use_counts(world):
    """Every role the view's filings carry, with how many filings carry
    it, most used first, then by role; an ignored stub's don't count."""

    with world.revision(Source.manual()) as rev:
        ustyug = _thing(rev, "place", "Velikiy Ustyug", tag="city")
        post = _thing(rev, "lore", "Postal HQ", tag="institution")
        _thing(
            rev,
            "character",
            "Vasha",
            filings=[_filing(ustyug, role="native"), _filing(post, role="carrier owl")],
        )
        _thing(rev, "character", "Olga", filings=[_filing(ustyug, role=" native ")])
        _thing(rev, "character", "Pyotr", filings=[_filing(post, role="carrier owl")])
        _thing(
            rev, "place", "Lower Market", filings=[_filing(ustyug, role="branch of")]
        )
        _thing(rev, "place", "Old Gate", filings=[_filing(ustyug)])
        rev.create_thing(
            "place",
            {
                "name": "Hidden Hall",
                "stub": {"ignored": True},
                "filings": [_filing(ustyug, role="secret")],
            },
        )

    assert roles_in_use(world.view()) == [
        ("carrier owl", 2),
        ("native", 2),
        ("branch of", 1),
    ]


def test_connected_groups_and_rows_by_kind(world):
    """Polish 5: Connected's groups run by the earliest kind they hold
    (characters, species, races, mixes, places, events, items, lore,
    beings), then by heading, Other last; a group's rows by kind, then as
    before (role, since, name)."""

    with world.revision(Source.manual()) as rev:
        velikoye = _thing(rev, "place", "Velikoye", tag="city")
        edict = _thing(
            rev, "lore", "Tsar's Edict", tag="noble", filings=[_filing(velikoye)]
        )
        orlov = _thing(
            rev, "character", "Count Orlov", tag="noble", filings=[_filing(velikoye)]
        )
        market = _thing(
            rev, "place", "The Ice Market", tag="market", filings=[_filing(velikoye)]
        )
        ivan = _thing(
            rev, "character", "Ivan", tag="merchant", filings=[_filing(velikoye)]
        )
        song = _thing(rev, "lore", "Old Song", filings=[_filing(velikoye)])

    groups = connected(world.view(), velikoye)
    assert [g.heading for g in groups] == ["Merchants", "Nobles", "Markets", "Other"]
    assert [thing_id for thing_id, _ in groups[1].rows] == [orlov, edict]
    assert [thing_id for thing_id, _ in groups[0].rows] == [ivan]
    assert [thing_id for thing_id, _ in groups[2].rows] == [market]
    assert [thing_id for thing_id, _ in groups[3].rows] == [song]
