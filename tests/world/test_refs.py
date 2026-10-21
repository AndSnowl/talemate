"""References that keep their written text: `[[thing:<id>|<shown>]]`."""

import pytest

from talemate.world.dates import WorldDate
from talemate.world.refs import REF_PATTERN, parse_refs, ref
from talemate.world.store import Source
from talemate.world.view import UNKNOWN_NAME, Segment


def test_ref_with_shown_text_roundtrip():
    a = "a" * 32
    token = ref(a, "Moscavia")
    assert token == f"[[thing:{a}|Moscavia]]"
    assert parse_refs(token) == [a]
    assert parse_refs(f"{ref(a)} and {token}") == [a]

    match = REF_PATTERN.fullmatch(token)
    assert match is not None
    assert match.group(1) == a
    assert match.group(2) == "Moscavia"
    assert REF_PATTERN.fullmatch(ref(a)).group(2) is None


def test_ref_rejects_shown_text_that_cant_round_trip():
    a = "a" * 32
    for shown in ("", "a]]b", "ends]", "two\nlines"):
        with pytest.raises(ValueError):
            ref(a, shown)


def _moscavia(world):
    with world.revision(Source.manual()) as rev:
        tsardom = rev.create_thing("place", fields={"name": "Tsardom of Moscavia"})
        vasha = rev.create_thing("character", fields={"name": "Vasha"})
    return tsardom, vasha


def test_render_shown_text(world):
    t, _ = _moscavia(world)
    view = world.view()
    assert view.render(f"Born in [[thing:{t}|Moscavia]].") == "Born in Moscavia."
    # no shown text: as before, the name
    assert view.render(f"Born in {ref(t)}.") == "Born in Tsardom of Moscavia."


def test_rename_updates_full_name_links_only(world):
    t, _ = _moscavia(world)
    full = ref(t, "Tsardom of Moscavia")
    short = ref(t, "Moscavia")
    lower = ref(t, "tsardom of moscavia")
    with world.revision(Source.manual()) as rev:
        rev.set_field(t, "name", "Moscavian Empire", WorldDate.of(1020))

    latest = world.view()
    assert latest.render(full) == "Moscavian Empire"
    assert latest.render(lower) == "Moscavian Empire"
    assert latest.render(short) == "Moscavia"

    # before the rename, the full-name link reads the name of that date
    earlier = world.view(at=WorldDate.of(1000))
    assert earlier.render(full) == "Tsardom of Moscavia"
    assert earlier.render(ref(t, "Moscavian Empire")) == "Tsardom of Moscavia"
    assert earlier.render(short) == "Moscavia"


def test_deleted_target_renders_shown_text(world):
    t, _ = _moscavia(world)
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(t)

    view = world.view()
    assert view.render(ref(t, "Tsardom of Moscavia")) == "Tsardom of Moscavia"
    assert view.render(ref(t, "Moscavia")) == "Moscavia"
    assert view.render(ref(t)) == UNKNOWN_NAME
    assert view.segments(f"In {ref(t, 'Moscavia')}.") == [
        Segment(text="In Moscavia.", ref=None)
    ]


def test_segments_split_links(world):
    t, v = _moscavia(world)
    view = world.view()
    text = f"{ref(v)} left [[thing:{t}|Moscavia]] and {ref(t)}"
    assert view.segments(text) == [
        Segment(text="Vasha", ref=v),
        Segment(text=" left ", ref=None),
        Segment(text="Moscavia", ref=t),
        Segment(text=" and ", ref=None),
        Segment(text="Tsardom of Moscavia", ref=t),
    ]
    assert "".join(s.text for s in view.segments(text)) == view.render(text)
    assert view.segments("plain") == [Segment(text="plain", ref=None)]
    assert view.segments("") == []


def test_store_accepts_shown_text_refs(world):
    t, v = _moscavia(world)
    with world.revision(Source.manual()) as rev:
        rev.add_fact(v, "background", f"Born in {ref(t, 'Moscavia')}.")
    view = world.view()
    [(owner, fact)] = view.referencing(t)
    assert owner == v
    assert fact.refs == [t]

    with pytest.raises(ValueError):
        with world.revision(Source.manual()) as rev:
            rev.add_fact(v, "background", ref("0" * 32, "Nowhere"))
