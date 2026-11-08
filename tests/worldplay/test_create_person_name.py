"""A drafted person's name built from their language (languages 4b-2,
Task 5): the draft call's `person` block, the name built with the parts
inherited from the parent they're filed under, the draft renamed and
marked, titles and pet names offered, a missing parent offered unticked,
and the owner's own name never rebuilt."""

import pytest

import talemate.config.state as config_state
from _people_names_helpers import DRASSONAIS
from talemate.languages.entry import fields_of
from talemate.world.store import Source
from talemate.worldplay.cleaning import clean_preview
from talemate.worldplay.create import (
    CreatePreview,
    PreviewFact,
    PreviewFiling,
    accept_preview,
    parse_person_block,
)


@pytest.fixture(autouse=True)
def shipped_lists():
    saved = config_state.get_config().name_lists
    config_state.get_config().name_lists = None
    yield
    config_state.get_config().name_lists = saved


@pytest.fixture
def test3(world):
    """Drassonais, spoken in the Duchy of Drassone; Eilhaud of Drassone,
    filed in the duchy, his name in parts."""

    with world.revision(Source.manual()) as rev:
        lang = rev.create_thing(
            "language", {"name": "Drassonais", **fields_of(DRASSONAIS)}
        )
        duchy = rev.create_thing(
            "place",
            {
                "name": "Duchy of Drassone",
                "languages": [{"language": lang, "role": "official"}],
            },
        )
        eilhaud = rev.create_thing(
            "character",
            {
                "name": "Eilhaud of Drassone",
                "filings": [{"target": duchy, "role": "duke"}],
                "name_parts": {
                    "language": lang,
                    "rule": "noble-men",
                    "shape": 0,
                    "built_as": {"sex": "man", "rank": "noble"},
                    "parts": [
                        {"label": "given", "text": "Eilhaud", "source": "rolled"},
                        {"label": "of", "text": "di", "source": "word"},
                        {"label": "house", "text": "Drassone", "source": "typed"},
                    ],
                },
            },
        )
    world.ids = {"lang": lang, "duchy": duchy, "eilhaud": eilhaud}
    return world


def _preview(world, prompt, *, name="Elise", filings=(), person=None) -> CreatePreview:
    rows = [
        PreviewFiling(
            target_id=target,
            target_name=world.view().name_of(target),
            role=role,
            ticked=True,
        )
        for target, role in filings
    ]
    if not filings:
        rows = [
            PreviewFiling(
                target_id=world.ids["duchy"],
                target_name="Duchy of Drassone",
                role="lives in",
                ticked=True,
            )
        ]
    return CreatePreview(
        kind="character",
        prompt=prompt,
        name=name,
        facts=[
            PreviewFact(category="background", text=f"{name} grew up at court."),
            PreviewFact(category="personality", text=f"{name} is quiet and watchful."),
        ],
        prose={},
        filings=rows,
        person=person or {},
    )


def test_person_block_parses_and_tolerates_absence():
    reply = '{"name": "X", "person": {"sex": "woman", "rank": "noble", "name_meaning": "", "title": " Lady "}, "facts": []}'
    assert parse_person_block(reply) == {
        "sex": "woman",
        "rank": "noble",
        "name_meaning": "",
        "title": "Lady",
    }
    assert parse_person_block('{"name": "X", "facts": []}') == {}
    assert parse_person_block('{"name": "X", "person": "a woman", "facts": []}') == {}


async def test_a_drafted_person_keeps_the_models_name_marked_for_name_it(test3):
    """Owner, 2026-11-06: drafts only mark; the name a person's rules would
    build waits in Name it. The draft keeps who it's built as and the
    model's title."""

    ids = test3.ids
    preview = await clean_preview(
        test3,
        _preview(
            test3,
            "a daughter of Eilhaud of Drassone",
            filings=[(ids["eilhaud"], "daughter of"), (ids["duchy"], "lives in")],
            person={"sex": "woman", "rank": "noble", "title": "Lady"},
        ),
        None,
    )
    assert preview.name == "Elise"
    assert preview.facts[0].text.startswith("Elise")
    stored = preview.fields["name_parts"]
    assert stored == {
        "language": ids["lang"],
        "rule": "",
        "shape": 0,
        "built_as": {"sex": "woman", "rank": "noble"},
        "parts": [],
    }
    mark = next(m for m in preview.marks if m.name == "Elise")
    assert "Name it" in mark.why and mark.language_id == ids["lang"]
    assert mark.entry_kind == "character"
    titles = [a for a in preview.aka if a.get("kind") == "title"]
    assert titles == [
        {
            "name": "Lady",
            "tag": "proper",
            "everyday": False,
            "kind": "title",
            "shown": "before",
        }
    ]
    assert not any(a.get("kind") == "pet" for a in preview.aka)
    assert not any(f.new_name for f in preview.filings)


async def test_a_name_from_the_prompt_is_never_rebuilt(test3):
    ids = test3.ids
    preview = await clean_preview(
        test3,
        _preview(
            test3,
            "Ysolde, daughter of Eilhaud",
            name="Ysolde",
            filings=[(ids["eilhaud"], "daughter of"), (ids["duchy"], "lives in")],
            person={"sex": "woman", "rank": "noble"},
        ),
        None,
    )
    assert preview.name == "Ysolde"
    assert "name_parts" not in preview.fields


async def test_a_missing_or_unknown_person_block_uses_defaults(test3):
    preview = await clean_preview(
        test3,
        _preview(test3, "someone of the duchy", person={"sex": "female", "rank": "??"}),
        None,
    )
    assert preview.fields["name_parts"]["built_as"] == {"sex": "man", "rank": "common"}
    bare = await clean_preview(
        test3, _preview(test3, "someone else of the duchy"), None
    )
    assert bare.fields["name_parts"]["built_as"] == {"sex": "man", "rank": "common"}


async def test_a_world_without_people_rules_is_left_alone(world):
    from _people_names_helpers import VAROVNI

    plain = VAROVNI.model_copy(update={"generators": VAROVNI.generators[:3]})
    with world.revision(Source.manual()) as rev:
        lang = rev.create_thing("language", {"name": "Varovni", **fields_of(plain)})
        eyrie = rev.create_thing(
            "place",
            {"name": "Eyrie", "languages": [{"language": lang, "role": "official"}]},
        )
    preview = CreatePreview(
        kind="character",
        prompt="a hunter",
        name="Dorvak",
        facts=[PreviewFact(category="background", text="Dorvak hunts.")],
        prose={},
        filings=[
            PreviewFiling(
                target_id=eyrie, target_name="Eyrie", role="lives in", ticked=True
            )
        ],
        person={"sex": "man"},
    )
    cleaned = await clean_preview(world, preview, None)
    assert cleaned.name == "Dorvak" and "name_parts" not in cleaned.fields


async def test_accept_keeps_who_a_drafted_person_is_built_as(test3):
    ids = test3.ids
    preview = await clean_preview(
        test3,
        _preview(
            test3,
            "a daughter of Eilhaud",
            filings=[(ids["eilhaud"], "daughter of"), (ids["duchy"], "lives in")],
            person={"sex": "woman", "rank": "noble"},
        ),
        None,
    )
    made = accept_preview(test3, preview)
    stored = test3.view().thing(made).fields["name_parts"]
    assert stored["parts"] == [] and stored["built_as"] == {
        "sex": "woman",
        "rank": "noble",
    }


def test_person_block_parses_without_the_opening_brace():
    """The draft call's reply comes without its first "{" (the prompt
    primes it): the block is still read (probe 4b-2)."""

    reply = '  "name": "Seraine of Drassone",  "age": 22,  "person": {    "sex": "woman",    "rank": "noble",    "name_meaning": "of the stars",    "title": "Lady"  },  "aka": [ { "name": "Seraine", "tag": "common", "everyday": true } ], "facts": []}'
    assert parse_person_block(reply) == {
        "sex": "woman",
        "rank": "noble",
        "name_meaning": "of the stars",
        "title": "Lady",
    }


async def test_a_person_with_only_a_parent_row_is_named_in_the_parents_language(test3):
    ids = test3.ids
    preview = CreatePreview(
        kind="character",
        prompt="a daughter of Eilhaud",
        name="Elise",
        facts=[PreviewFact(category="background", text="Elise grew up at court.")],
        prose={},
        filings=[
            PreviewFiling(
                target_id=ids["eilhaud"],
                target_name="Eilhaud of Drassone",
                role="daughter of",
                ticked=False,
            )
        ],
        person={"sex": "woman", "rank": "noble"},
    )
    cleaned = await clean_preview(test3, preview, None)
    assert cleaned.fields["name_parts"]["language"] == ids["lang"]
    assert cleaned.name == "Elise"


# --- final review fixes ------------------------------------------------------


async def test_a_stub_or_a_decided_name_is_never_rebuilt(test3):
    """Final review C1: expanding a stub (or a name set in the fields)
    keeps that name."""

    ids = test3.ids
    with test3.revision(Source.manual()) as rev:
        stub = rev.create_thing(
            "character", {"name": "Borodey", "stub": {"ignored": False}}
        )
    from_stub = _preview(
        test3, "a blacksmith of the duchy", name="Borodey", person={"sex": "man"}
    )
    from_stub = from_stub.model_copy(update={"stub_id": stub})
    assert (await clean_preview(test3, from_stub, None)).name == "Borodey"
    decided = _preview(
        test3, "a blacksmith of the duchy", name="Borodey", person={"sex": "man"}
    )
    decided = decided.model_copy(update={"fields": {"name": "Borodey"}})
    cleaned = await clean_preview(test3, decided, None)
    assert cleaned.name == "Borodey" and "name_parts" not in cleaned.fields
    assert ids


async def test_an_owners_rename_on_the_draft_survives_cleaning_again(test3):
    """Final review C2: once built, a draft renamed by the owner keeps its
    name when cleaned again (a Languages change); the parts go."""

    ids = test3.ids
    first = await clean_preview(
        test3,
        _preview(
            test3,
            "a daughter of Eilhaud",
            filings=[(ids["eilhaud"], "daughter of"), (ids["duchy"], "lives in")],
            person={"sex": "woman", "rank": "noble"},
        ),
        None,
    )
    renamed = first.model_copy(update={"name": "Joan"})
    again = await clean_preview(test3, renamed, None)
    assert again.name == "Joan"
    assert again.fields["name_parts"]["built_as"] == {"sex": "woman", "rank": "noble"}


async def test_the_owners_given_name_is_kept_when_the_model_adds_to_it(test3):
    """Final review I1: "Ysolde, daughter of Eilhaud" drafted as "Ysolde of
    Drassone" stays so."""

    ids = test3.ids
    cleaned = await clean_preview(
        test3,
        _preview(
            test3,
            "Ysolde, daughter of Eilhaud",
            name="Ysolde of Drassone",
            filings=[(ids["eilhaud"], "daughter of")],
            person={"sex": "woman", "rank": "noble"},
        ),
        None,
    )
    assert cleaned.name == "Ysolde of Drassone"


async def test_a_person_only_placed_by_the_model_is_named_in_that_places_language(
    test3,
):
    """Acceptance 4b-2 run 3: a hunter the model put in the duchy (an
    unticked row, no parent) is still named in its language."""

    ids = test3.ids
    preview = CreatePreview(
        kind="character",
        prompt="a hunter who watches the stars",
        name="Velesk",
        facts=[PreviewFact(category="background", text="Velesk hunts by night.")],
        prose={},
        filings=[
            PreviewFiling(
                target_id=ids["duchy"],
                target_name="Duchy of Drassone",
                role="noble hunter",
                ticked=False,
            )
        ],
        person={"sex": "man", "rank": "noble"},
    )
    cleaned = await clean_preview(test3, preview, None)
    assert cleaned.fields["name_parts"]["language"] == ids["lang"]


async def test_a_drafted_persons_mark_is_the_proper_part_once(test3):
    """Final review C1/I2: "Tsar Aleksi III" is marked "Aleksi" (narrator
    words left for Name it to keep), and one mark only."""

    from talemate.languages.cleaning.marks import Mark

    preview = _preview(test3, "a ruler", name="Tsar Aleksi III", person={"sex": "man"})
    preview = preview.model_copy(
        update={
            "marks": [Mark(id="x", name="Aleksi", part="Aleksi", why="a real name")]
        }
    )
    from talemate.worldplay.cleaning import name_person

    out = name_person(test3.view(), preview, test3.ids["lang"])
    assert [(m.name, m.part) for m in out.marks] == [("Aleksi", "Aleksi")]
