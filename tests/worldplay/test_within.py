"""A person's filing `within` a part of its target (Filing; formerly a
tie within an item of its sphere, curation ruling C12).

The White Talon is a regiment of the Tsar's Army, which is filed in the
Tsardom of Moscavia; the First Squadron is in the White Talon. Ivan is a
trooper of the army within the White Talon. The tests the old
bodies-within-bodies file (`worldplay.bodies`) held for live behaviour,
moved here when the spheres went (Filing, Task 7)."""

from talemate.world.dates import WorldDate
from talemate.world.filing import filings_of
from talemate.world.store import Source
from talemate.worldplay.characters import filing_lines
from talemate.worldplay.create import (
    CreatePreview,
    PreviewFact,
    PreviewFiling,
    accept_preview,
)
from talemate.worldplay.repoint import repoint_stub

ARMY = "The Tsar's Army"


def _army(world):
    """Present 1020. The Tsardom of Moscavia (a place) holds the Frosted
    Wing (a lore stub), the Kremlin Guard and the Tsar's Army; the White
    Talon is in the army and the First Squadron in the White Talon. Ivan
    is a trooper of the army within the White Talon since 1012."""

    world.set_present(WorldDate.of(1020))
    ids = {}
    with world.revision(Source.manual(note="army")) as rev:
        ids["tsardom"] = rev.create_thing("place", {"name": "Tsardom of Moscavia"})
        in_tsardom = [{"target": ids["tsardom"]}]
        ids["frosted"] = rev.create_thing(
            "lore",
            {
                "name": "Frosted Wing",
                "stub": {"ignored": False},
                "filings": in_tsardom,
            },
        )
        ids["guard"] = rev.create_thing(
            "lore", {"name": "Kremlin Guard", "filings": in_tsardom}
        )
        rev.add_fact(ids["guard"], "general", "The Tsar's own guard.")
        ids["army"] = rev.create_thing("lore", {"name": ARMY, "filings": in_tsardom})
        ids["talon"] = rev.create_thing(
            "lore",
            {"name": "The White Talon", "filings": [{"target": ids["army"]}]},
        )
        ids["squadron"] = rev.create_thing(
            "lore",
            {"name": "First Squadron", "filings": [{"target": ids["talon"]}]},
        )
        ids["ivan"] = rev.create_thing(
            "character",
            {
                "name": "Ivan",
                "filings": [
                    {
                        "target": ids["army"],
                        "role": "trooper",
                        "since": WorldDate.of(1012).model_dump(mode="json"),
                        "within": ids["talon"],
                    }
                ],
            },
        )
    return ids


def _row_in(target, name, role, within=None):
    return PreviewFiling(
        target_id=target, target_name=name, role=role, within=within, ticked=True
    )


def test_filing_line_reads_within(world):
    """A filing within a part reads "<Role> in <entry>, within <part>" on
    the sheet (ruling C12); without a part, "<Role> of <entry>"."""

    ids = _army(world)
    with world.revision(Source.manual()) as rev:
        olga = rev.create_thing(
            "character",
            {
                "name": "Olga",
                "filings": [{"target": ids["army"], "role": "quartermaster"}],
            },
        )
    view = world.view(WorldDate.of(1020))
    assert filing_lines(view, world.calendar, ids["ivan"]) == [
        "Trooper in the Tsar's Army, within the White Talon (since 1012)"
    ]
    assert filing_lines(world.view(), world.calendar, olga) == [
        "Quartermaster of the Tsar's Army"
    ]


def test_created_filing_carries_within(world):
    """A ticked "In" row with a `within` (the owner's) is written with it,
    a part further down counting too; one whose part isn't the target's is
    kept, whole."""

    ids = _army(world)
    preview = CreatePreview(
        kind="character",
        prompt="A rider.",
        name="Pyotr",
        facts=[PreviewFact(category="background", text="Pyotr rides.")],
        prose={},
        filings=[
            _row_in(ids["army"], ARMY, "rider", ids["talon"]),
            # the White Talon is within the Tsardom too, through the army
            _row_in(ids["tsardom"], "Tsardom", "subject", ids["talon"]),
            # the Kremlin Guard isn't the Frosted Wing's: kept whole
            _row_in(ids["frosted"], "Frosted Wing", "scout", ids["guard"]),
        ],
    )
    pyotr = accept_preview(world, preview)
    stored = filings_of(world.view(), pyotr, live=False)
    assert [(f.target, f.within) for f in stored] == [
        (ids["army"], ids["talon"]),
        (ids["tsardom"], ids["talon"]),
        (ids["frosted"], None),
    ]


def test_repoint_carries_within(world):
    """Re-pointing a stub a filing is within moves the filing's part to
    the entry, as filings into it are."""

    ids = _army(world)
    with world.revision(Source.manual()) as rev:
        stub = rev.create_thing(
            "lore",
            {
                "name": "Talon Regiment",
                "stub": {"ignored": False},
                "filings": [{"target": ids["army"]}],
            },
        )
        rev.set_field(
            ids["ivan"],
            "filings",
            [{"target": ids["army"], "role": "trooper", "within": stub}],
            None,
        )

    repoint_stub(world, stub, ids["talon"])

    (filing,) = filings_of(world.view(), ids["ivan"])
    assert (filing.target, filing.within) == (ids["army"], ids["talon"])


def test_merge_keeps_within(world):
    """Onto an entry the world has ("Is this X?" -- yes): its ticked "In"
    rows file it too, `within` kept."""

    ids = _army(world)
    with world.revision(Source.manual()) as rev:
        pyotr = rev.create_thing("character", {"name": "Pyotr"})
        rev.add_fact(pyotr, "background", "A rider of the north.")
    preview = CreatePreview(
        kind="character",
        prompt="Pyotr, a rider.",
        name="Pyotr",
        facts=[PreviewFact(category="background", text="Pyotr rides at dawn.")],
        prose={},
        filings=[_row_in(ids["army"], ARMY, "rider", ids["talon"])],
    )
    accept_preview(world, preview, same_target_id=pyotr)
    (filing,) = filings_of(world.view(), pyotr)
    assert (filing.target, filing.within) == (ids["army"], ids["talon"])
