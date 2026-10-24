"""Group synopses and group "+ Add" (Filing, Task 8).

`group_synopsis` asks the model for a short summary of one tag group on a
page (probe 3's wording), cached as the page's prose section
`synopsis:<tag>`; `group_add` drafts up to 3 new entries for a group (or,
with no tag, the page's own top-level "+ Add") from the owner's prompt
(probe 6's v2 wording), writing nothing; `accept_group_add` writes the
ticked ones as stubs, filed in the page, in one revision."""

import json

from talemate.world.entries import is_summary_fact
from talemate.world.filing import filed_in
from talemate.world.store import Source
from talemate.worldplay import groups
from talemate.worldplay.groups import GroupAddRow

from conftest import MockClient, MockClientContext, client_responses


def _queue(*responses: str) -> None:
    for response in responses:
        client_responses.get().append(response)


def _seed_rivers(world):
    """Velikoye, with two rivers filed in it (Khorol and Lesnaya) and an
    institution (The Night Court), each with one fact."""

    with world.revision(Source.manual(note="seed")) as rev:
        velikoye = rev.create_thing("place", {"name": "Velikoye", "tag": "capital"})
        khorol = rev.create_thing(
            "place",
            {
                "name": "Khorol River",
                "tag": "river",
                "filings": [{"target": velikoye, "role": None}],
            },
        )
        rev.add_fact(khorol, "description", "A wide, cold river.")
        lesnaya = rev.create_thing(
            "place",
            {
                "name": "Lesnaya River",
                "tag": "river",
                "filings": [{"target": velikoye, "role": None}],
            },
        )
        rev.add_fact(lesnaya, "description", "A smaller tributary.")
        court = rev.create_thing(
            "lore",
            {
                "name": "The Night Court",
                "tag": "institution",
                "filings": [{"target": velikoye, "role": None}],
            },
        )
        rev.add_fact(court, "general", "The nocturnal council.")
    return velikoye, khorol, lesnaya, court


# --- group_synopsis ----------------------------------------------------------


async def test_synopsis_cached_and_stale_on_change(world):
    velikoye, khorol, lesnaya, _court = _seed_rivers(world)
    client = MockClient("test")

    async with MockClientContext():
        _queue(
            json.dumps({"synopsis": "The Khorol and Lesnaya are Velikoye's rivers."})
        )
        first = await groups.group_synopsis(world, velikoye, "river", client)
        assert first == "The Khorol and Lesnaya are Velikoye's rivers."
        assert len(client.prompt_history) == 1
        prompt = str(client.prompt_history[0]["prompt"])
        assert "rivers filed in Velikoye" in prompt
        assert "Khorol River (place, river)" in prompt
        assert "A wide, cold river." in prompt

        # cached: a second call with nothing changed asks the model nothing
        again = await groups.group_synopsis(world, velikoye, "river", client)
        assert again == first
        assert len(client.prompt_history) == 1

        # a member's own fact changes: stale, asked again
        with world.revision(Source.manual(note="edit")) as rev:
            rev.add_fact(khorol, "description", "Frozen solid every winter.")
        _queue(json.dumps({"synopsis": "The Khorol now freezes; Lesnaya feeds it."}))
        changed = await groups.group_synopsis(world, velikoye, "river", client)
        assert changed == "The Khorol now freezes; Lesnaya feeds it."
        assert len(client.prompt_history) == 2

        # cached again at the new content
        same_again = await groups.group_synopsis(world, velikoye, "river", client)
        assert same_again == changed
        assert len(client.prompt_history) == 2

        # a new member filed into the group: stale (a `filings` change,
        # which ordinary prose staleness never reads)
        with world.revision(Source.manual(note="new river")) as rev:
            rev.create_thing(
                "place",
                {
                    "name": "Dusk Creek",
                    "tag": "river",
                    "filings": [{"target": velikoye, "role": None}],
                },
            )
        _queue(json.dumps({"synopsis": "Three rivers now run through Velikoye."}))
        with_new_member = await groups.group_synopsis(world, velikoye, "river", client)
        assert with_new_member == "Three rivers now run through Velikoye."
        assert len(client.prompt_history) == 3

    # a different group's cache is untouched
    assert world.prose().get(velikoye, "synopsis:institution", None) is None


async def test_synopsis_empty_group_and_missing_entry(world):
    velikoye, _khorol, _lesnaya, _court = _seed_rivers(world)
    client = MockClient("test")

    async with MockClientContext():
        # no "guild" group on Velikoye: nothing to summarise, no call made
        empty = await groups.group_synopsis(world, velikoye, "guild", client)
        assert empty == ""
        assert client.prompt_history == []

    try:
        async with MockClientContext():
            await groups.group_synopsis(world, "f" * 32, "river", client)
        raise AssertionError("expected KeyError")
    except KeyError:
        pass


async def test_synopsis_off_when_probe_fallback(world, monkeypatch):
    """`SYNOPSIS_ENABLED` off (the spec's fallback for a probe that
    failed): no model call, nothing cached, "" back."""

    velikoye, _khorol, _lesnaya, _court = _seed_rivers(world)
    monkeypatch.setattr(groups, "SYNOPSIS_ENABLED", False)
    client = MockClient("test")

    async with MockClientContext():
        synopsis = await groups.group_synopsis(world, velikoye, "river", client)

    assert synopsis == ""
    assert client.prompt_history == []
    assert world.prose().get(velikoye, "synopsis:river", None) is None


# --- group_add ---------------------------------------------------------------


async def test_group_add_rows_tagged_and_filed(world):
    velikoye, khorol, _lesnaya, _court = _seed_rivers(world)
    client = MockClient("test")

    reply = json.dumps(
        {
            "entries": [
                {
                    "name": "The Icewrights' Circle",
                    "kind": "lore",
                    # the model's own tag is ignored: the group's tag wins
                    "tag": "trade",
                    "line": "A guild of ice-road pilots who guide sledges"
                    " across the frozen Khorol.",
                }
            ]
        }
    )
    async with MockClientContext():
        _queue(reply)
        rows = await groups.group_add(
            world, khorol, "guild", "a guild of ice-road pilots", client
        )

    assert len(client.prompt_history) == 1
    prompt = str(client.prompt_history[0]["prompt"])
    assert '"guild" group of Khorol River' in prompt
    assert "a guild of ice-road pilots" in prompt

    assert len(rows) == 1
    row = rows[0]
    assert isinstance(row, GroupAddRow)
    assert row.name == "The Icewrights' Circle"
    assert row.kind == "lore"
    assert row.tag == "guild"
    assert row.ticked is True
    assert "ice-road pilots" in row.line


async def test_group_add_caps_at_three_and_drops_titles(world):
    velikoye, khorol, _lesnaya, _court = _seed_rivers(world)
    client = MockClient("test")

    reply = json.dumps(
        {
            "entries": [
                {"name": "A", "kind": "lore", "tag": "guild", "line": "First."},
                {"name": "B", "kind": "lore", "tag": "guild", "line": "Second."},
                {"name": "C", "kind": "lore", "tag": "guild", "line": "Third."},
                {"name": "D", "kind": "lore", "tag": "guild", "line": "Fourth."},
                # ruling F5: a title word as kind or tag is dropped
                {"name": "E", "kind": "office", "tag": "guild", "line": "Fifth."},
                {"name": "F", "kind": "lore", "tag": "title", "line": "Sixth."},
                # no name: dropped
                {"name": "", "kind": "lore", "tag": "guild", "line": "Nameless."},
            ]
        }
    )
    async with MockClientContext():
        _queue(reply)
        rows = await groups.group_add(world, khorol, "guild", "a few guilds", client)

    assert [row.name for row in rows] == ["A", "B", "C"]


async def test_group_add_with_no_tag_keeps_the_models_own_tag(world):
    """`tag=None`: the top-level "+ Add", no tag preset -- the model's own
    tag (cleaned) is kept rather than forced."""

    velikoye, khorol, _lesnaya, _court = _seed_rivers(world)
    client = MockClient("test")

    reply = json.dumps(
        {
            "entries": [
                {
                    "name": "The Frozen Market",
                    "kind": "lore",
                    "tag": "custom",
                    "line": "A winter market.",
                }
            ]
        }
    )
    async with MockClientContext():
        _queue(reply)
        rows = await groups.group_add(world, khorol, None, "a winter custom", client)

    assert len(client.prompt_history) == 1
    prompt = str(client.prompt_history[0]["prompt"])
    # the tag-given wording ("the "X" group of") doesn't appear
    assert "group of Khorol River" not in prompt
    assert len(rows) == 1
    assert rows[0].tag == "custom"


# --- accept_group_add --------------------------------------------------------


async def test_group_add_accept_one_revision(world):
    velikoye, khorol, _lesnaya, _court = _seed_rivers(world)
    head = world.head_rev()

    rows = [
        GroupAddRow(
            name="The Icewrights' Circle",
            kind="lore",
            tag="guild",
            line="A guild of ice-road pilots.",
            ticked=True,
        ),
        GroupAddRow(
            name="The Shivering Lantern Company",
            kind="lore",
            tag="guild",
            line="A trade company that hires pilots.",
            ticked=True,
        ),
        GroupAddRow(
            name="Dropped (unticked)",
            kind="lore",
            tag="guild",
            line="Never written.",
            ticked=False,
        ),
    ]

    ids = groups.accept_group_add(world, khorol, rows)

    assert len(ids) == 2
    assert world.head_rev() == head + 1  # one revision, however many rows

    view = world.view()
    for thing_id, row in zip(ids, rows[:2]):
        state = view.thing(thing_id)
        assert state is not None
        assert state.fields["name"] == row.name
        assert state.fields["tag"] == "guild"
        assert len(state.facts) == 1
        fact = state.facts[0]
        assert fact.text == row.line
        assert is_summary_fact(fact)

    filed_ids = {state.id for state, _filing in filed_in(view, khorol)}
    assert filed_ids == set(ids)
    assert "Dropped" not in [view.name_of(thing_id) for thing_id in ids]


async def test_group_add_accept_checks_again(world):
    """`accept_group_add` never trusts the client's copy: a bad kind, a
    blank name or a title word is dropped even when ticked."""

    velikoye, khorol, _lesnaya, _court = _seed_rivers(world)

    rows = [
        GroupAddRow(name="Good", kind="lore", tag="guild", line="Fine.", ticked=True),
        GroupAddRow(name="", kind="lore", tag="guild", line="Blank name.", ticked=True),
        GroupAddRow(
            name="Bad kind", kind="nonsense", tag="guild", line="x", ticked=True
        ),
        GroupAddRow(name="Title tag", kind="lore", tag="office", line="x", ticked=True),
        GroupAddRow(name="Title kind", kind="rank", tag="guild", line="x", ticked=True),
    ]

    ids = groups.accept_group_add(world, khorol, rows)
    view = world.view()
    assert [view.name_of(thing_id) for thing_id in ids] == ["Good"]


async def test_group_add_accept_missing_page_is_key_error(world):
    rows = [GroupAddRow(name="X", kind="lore", tag="guild", line="x", ticked=True)]
    try:
        groups.accept_group_add(world, "f" * 32, rows)
        raise AssertionError("expected KeyError")
    except KeyError:
        pass
