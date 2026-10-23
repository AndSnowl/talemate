"""Spheres from a prompt in two steps -- the core with its drawer outline,
then Fill per drawer -- plus promotion, adoption of what's already part of
a sphere, child-first "part of", and culture guesses as culture spheres.

The MockClient replies are raw Skyfall output from the spheres probe
(docs/superpowers/probes/raw/2026-10-22-spheres.json), copied verbatim."""

import json
from typing import NamedTuple

import pytest

from talemate.world import spheres
from talemate.world.dates import WorldDate
from talemate.world.kinds import UNSORTED_DRAWER_ID
from talemate.world.refs import parse_refs, ref
from talemate.world.store import Source
from talemate.worldplay import prose_gen
from talemate.worldplay.create import (
    CreatePreview,
    spheres_block,
    PreviewFact,
    accept_preview,
    preview_thing,
)
from talemate.worldplay.spheres import (
    SpherePreview,
    accept_fill,
    accept_sphere,
    end_item,
    fill_drawer,
    preview_branch,
    preview_sphere,
)

from conftest import MockClient, MockClientContext, client_responses


def _queue(*responses: str) -> None:
    for response in responses:
        client_responses.get().append(response)


# core 0: the White Dawn expanded from its stub
CORE_RELIGION = '{ "name": "The White Dawn", "summary": "The White Dawn is the state church of the Tsardom of Moscavia, teaching that the Night of Feathers in 994 was a holy purification that transformed the Moscavian people into owl-folk, and that the Tsar rules by divine right as the living embodiment of dawn\'s light.", "aka": [{"name": "The Church of the White Dawn", "tag": "proper", "everyday": false}, {"name": "the Dawn Church", "tag": "common", "everyday": true}], "timeline": [{"year": 994, "text": "The Night of Feathers transforms nearly all Moscavians into owl-folk; the White Dawn\'s foundational doctrine is born from this event."}, {"year": 996, "text": "The First Synod of Kremova establishes the hierarchical structure of the clergy and codifies the Dawn Liturgy."}, {"year": 1012, "text": "The Grand Patriarch decrees the annual Feast of Purification to commemorate the Night of Feathers."}, {"year": 1020, "text": "The current Grand Patriarch, Seryozha the Illuminated, presides over the Church from the Cathedral of White Wings in Kremova."}], "drawers": [{"type": "beliefs", "title": "Doctrines"}, {"type": "practices", "title": "Rites and Ceremonies"}, {"type": "places", "title": "Holy Sites"}, {"type": "structure", "title": "Hierarchy"}], "items": [{"drawer": "Doctrines", "name": "The Purification Doctrine", "text": "The Night of Feathers was a divine act of cleansing that remade the Moscavian people in the image of the owl, creatures of wisdom and vigilance.", "kind": "lore"}, {"drawer": "Doctrines", "name": "The Dawn Covenant", "text": "The Tsar rules by sacred mandate as the earthly vessel of the White Dawn\'s light, answerable only to the divine order.", "kind": "lore"}, {"drawer": "Doctrines", "name": "The Three Wings", "text": "Truth, Vigilance and Obedience are the three virtues upon which all Dawn teaching rests.", "kind": "lore"}, {"drawer": "Doctrines", "name": "", "text": "All owl-folk bear the mark of grace; those who are not transformed are considered unblessed and subject to the Church\'s oversight.", "kind": "lore"}, {"drawer": "Rites and Ceremonies", "name": "The Dawn Vigil", "text": "The nightly prayer service held at every Dawn chapel, marking the transition from darkness to light.", "kind": "lore"}, {"drawer": "Rites and Ceremonies", "name": "The Feast of Purification", "text": "Held on the anniversary of the Night of Feathers each year, featuring white-robed processions and the blessing of owlets.", "kind": "event"}, {"drawer": "Rites and Ceremonies", "name": "The Rite of First Flight", "text": "A coming-of-age ceremony for young owl-folk at their first molt, marking their entrance into the faith.", "kind": "lore"}, {"drawer": "Rites and Ceremonies", "name": "The Amber Communion", "text": "Worshippers consume blessed amber shavings during high holy days as a symbol of the dawn\'s golden light.", "kind": "lore"}, {"drawer": "Holy Sites", "name": "The Cathedral of White Wings", "text": "The seat of the Grand Patriarch in Kremova, built from pale stone and crowned with a great owl\'s-nest dome.", "kind": "place"}, {"drawer": "Holy Sites", "name": "The Shrine of the First Molt", "text": "A grove of ancient pines outside Kremova where the first owl-folk are said to have taken flight.", "kind": "place"}, {"drawer": "Holy Sites", "name": "The Vesna Sanctum", "text": "A temple on the banks of the river Vesna where pilgrims cast amber offerings into the current.", "kind": "place"}, {"drawer": "Holy Sites", "name": "", "text": "Every city and town in Moscavia hosts at least one Dawn chapel with a roosting gallery for the clergy.", "kind": "lore"}, {"drawer": "Hierarchy", "name": "The Grand Patriarch", "text": "The supreme spiritual authority of the White Dawn, appointed by the Tsar and confirmed by the Synod.", "kind": "lore"}, {"drawer": "Hierarchy", "name": "The Synod of Dawns", "text": "A council of twelve senior clergy who interpret doctrine and advise the Grand Patriarch.", "kind": "lore"}, {"drawer": "Hierarchy", "name": "The Order of Watchful Eyes", "text": "The clergy rank-and-file who serve as priests, healers and teachers throughout Moscavia\'s parishes.", "kind": "lore"}, {"drawer": "Hierarchy", "name": "The Novices of the Pale Feather", "text": "Young acolytes undergoing training, distinguished by white feathered cloaks.", "kind": "lore"}], "names": [{"name": "Tsardom of Moscavia", "kind": "place", "aka": ["Moscavia"]}, {"name": "Kremova", "kind": "place", "aka": []}, {"name": "The Vesna", "kind": "place", "aka": []}, {"name": "The Night of Feathers", "kind": "event", "aka": []}, {"name": "Grand Patriarch Seryozha the Illuminated", "kind": "character", "aka": []}, {"name": "The Synod of Dawns", "kind": "sphere", "aka": [], "template": "order"}, {"name": "The Order of Watchful Eyes", "kind": "sphere", "aka": [], "template": "order"}, {"name": "The Novices of the Pale Feather", "kind": "sphere", "aka": [], "template": "order"}, {"name": "The Cathedral of White Wings", "kind": "place", "aka": []}, {"name": "The Shrine of the First Molt", "kind": "place", "aka": []}, {"name": "The Vesna Sanctum", "kind": "place", "aka": []}, {"name": "The Tsar", "kind": "lore", "aka": []}, {"name": "Owl-folk", "kind": "race", "aka": []}] }'

# core 2: the Tsardom promoted
CORE_NATION = '{ "name": "Tsardom of Moscavia", "summary": "The Tsardom of Moscavia is a northern realm of pine forest, bog, and slow brown rivers, ruled from the towered city of Kremova. Since the Night of Feathers in 994, the White Dawn has taught that the transformation of the Moscavian people into owl-folk was a divine purification.", "aka": [{"name": "Moscavia", "tag": "common", "everyday": true}], "timeline": [{"year": 994, "text": "The Night of Feathers transformed nearly all Moscavians into owl-folk, an event the White Dawn teaches as sacred purification."}, {"year": 1001, "text": "The White Dawn was formally established as the Tsardom\'s state church by decree of the Tsar."}, {"year": 1015, "text": "A trade compact was signed with the southern port cities, formalizing the barge trade in timber, furs, and amber down the Vesna river."}, {"year": 1020, "text": "The current Tsar reigns from Kremova, governing a realm at peace but watchful of its northern borders."}], "drawers": [{"type": "places", "title": "Lands"}, {"type": "practices", "title": "Rites & Customs"}, {"type": "beliefs", "title": "Laws & Doctrine"}, {"type": "structure", "title": "Government"}, {"type": "knowledge", "title": "Learning"}], "items": [{"drawer": "Lands", "name": "Kremova", "text": "The capital and seat of the Tsar, a city of tall stone towers and carved wooden roosting galleries along its riverbanks.", "kind": "place"}, {"drawer": "Lands", "name": "The Vesna", "text": "The great slow brown river that runs south from the northern forests, carrying trade barges to the southern ports.", "kind": "place"}, {"drawer": "Lands", "name": "The Northern Boglands", "text": "Vast peat bogs stretching beyond the treeline, home to rare herbs and dangerous mists, lightly settled by outpost villages.", "kind": "place"}, {"drawer": "Lands", "name": "Velikiy Bor", "text": "The great pine forest covering most of the Tsardom\'s heartland, source of its timber wealth and hunting grounds for the owl-folk.", "kind": "place"}, {"drawer": "Rites & Customs", "name": "The Dawn Vigil", "text": "An annual ceremony held at the first light of the spring equinox, when every household lights a candle and places it in a window.", "kind": "event"}, {"drawer": "Rites & Customs", "name": "Feather-Day", "text": "The anniversary of the Night of Feathers, observed with processions, feasting, and the blessing of young owl-folk at their first moult.", "kind": "event"}, {"drawer": "Rites & Customs", "name": "The Barge Blessing", "text": "Before any trade barge departs Kremova, a White Dawn priest sprinkles it with holy water and speaks the Prayer of Smooth Passage.", "kind": "event"}, {"drawer": "Rites & Customs", "name": "Roosting etiquette", "text": "Nobles and commoners alike observe strict customs of silence during the twilight hours, considered sacred to the owls\' hunting instincts.", "kind": "lore"}, {"drawer": "Laws & Doctrine", "name": "The Doctrine of Purification", "text": "The White Dawn teaches that the Night of Feathers was God\'s cleansing of humanity\'s corruption, and that owl-folk are the blessed new form.", "kind": "lore"}, {"drawer": "Laws & Doctrine", "name": "The First Law of Kremova", "text": "The Tsar\'s word is absolute law, but must be proclaimed publicly and recorded in the Amber Ledgers.", "kind": "lore"}, {"drawer": "Laws & Doctrine", "name": "The Church\'s prohibition", "text": "White Dawn doctrine forbids any attempt to reverse or alter the owl-form; such efforts are heresy punishable by exile.", "kind": "lore"}, {"drawer": "Laws & Doctrine", "name": "Trade tariffs", "text": "All goods entering or leaving the Tsardom are subject to a tithe of one-tenth, collected at river crossings and border posts.", "kind": "lore"}, {"drawer": "Government", "name": "The Tsar", "text": "The supreme ruler of the Tsardom, head of state and commander of its armies, chosen by hereditary succession.", "kind": "lore"}, {"drawer": "Government", "name": "The Amber Council", "text": "An advisory body of twelve nobles and twelve church elders who deliberate on matters of law and taxation.", "kind": "lore"}, {"drawer": "Government", "name": "The Veche of Kremova", "text": "A town assembly of merchant guilds and roosting-house elders that governs the capital\'s daily affairs.", "kind": "lore"}, {"drawer": "Government", "name": "The Fur Wardens", "text": "A royal corps tasked with patrolling the northern forests, managing game herds, and collecting the annual fur levy.", "kind": "lore"}, {"drawer": "Learning", "name": "The Amber Ledgers", "text": "The Tsardom\'s official record of laws, treaties, and decrees, kept in bound volumes of pressed amber pages in the Kremova archives.", "kind": "item"}, {"drawer": "Learning", "name": "Owl-scholars of the Northern Pine", "text": "An informal network of owl-folk who study the old pre-Feathers world through salvaged texts and oral histories.", "kind": "lore"}], "names": [{"name": "The White Dawn", "kind": "sphere", "aka": [], "template": "religion"}, {"name": "The Night of Feathers", "kind": "event", "aka": []}, {"name": "The Vesna River", "kind": "place", "aka": []}, {"name": "The Amber Ledgers", "kind": "item", "aka": []}, {"name": "Moscavian", "kind": "race", "aka": []}, {"name": "Owl-folk", "kind": "species", "aka": []}, {"name": "Kremova", "kind": "place", "aka": []}] }'

# core 4: the Imperial Academy of Runecraft
CORE_ORDER = '{ "name": "Imperial Academy of Runecraft", "summary": "The preeminent institution of runic magic in the Tsardom of Moscavia, seated in the capital city of Kremova, where owl-folk scholars study the art and science of runes.", "aka": [{"name": "Runic Academy", "tag": "common", "everyday": true}], "timeline": [{"year": 996, "text": "The Imperial Academy of Runecraft was founded by decree of Tsar Alexei II, two years after the Night of Feathers transformed all of Moscavia\'s people into owl-folk."}, {"year": 1003, "text": "The Academy completed construction of the Spire of Inscriptions, its central tower of carved stone runework rising above the Vesna river district."}, {"year": 1012, "text": "The Grand Archivist Veleska codified the First Lexicon of Known Runes, standardizing the Academy\'s curriculum for all five branches of study."}, {"year": 1020, "text": "The Academy currently enrolls 247 scholars and maintains exchange correspondences with three foreign institutions, including the Arcanum of Lúthien."}], "drawers": [{"type": "structure", "title": "Ranks and Offices"}, {"type": "knowledge", "title": "Fields of Study"}, {"type": "practices", "title": "Rites and Customs"}, {"type": "places", "title": "Sites and Territory"}], "items": [{"drawer": "Ranks and Offices", "name": "Grand Archivist", "text": "The highest-ranking scholar, appointed by the Tsar for life, who oversees all curriculum and research.", "kind": "lore"}, {"drawer": "Ranks and Offices", "name": "Dean of Wings", "text": "Each of the five study halls is led by a Dean of Wings, who manages faculty and student affairs within their branch.", "kind": "lore"}, {"drawer": "Ranks and Offices", "name": "Rune-Scribe Apprentice", "text": "The entry-level rank for new students, who spend two years mastering basic glyphs before advancing.", "kind": "lore"}, {"drawer": "Ranks and Offices", "name": "The Oversight Council", "text": "A body of seven senior scholars elected by faculty who adjudicate disputes and approve major research proposals.", "kind": "lore"}, {"drawer": "Fields of Study", "name": "Luminous Runes", "text": "The study of light-manipulating glyphs used in communication, illumination, and signaling across distances.", "kind": "lore"}, {"drawer": "Fields of Study", "name": "Earthen Runes", "text": "The study of glyphs that interact with stone, soil, and mineral, used in architecture and geomancy.", "kind": "lore"}, {"drawer": "Fields of Study", "name": "Vital Runes", "text": "The study of glyphs affecting living creatures, including healing sigils and wardings against disease.", "kind": "lore"}, {"drawer": "Fields of Study", "name": "Temporal Runes", "text": "The study of glyphs that influence the flow of time, the most restricted and dangerous branch.", "kind": "lore"}, {"drawer": "Fields of Study", "name": "Void Runes", "text": "The study of glyphs that interface with the spaces between, used in teleportation theory and dimensional study.", "kind": "lore"}, {"drawer": "Rites and Customs", "name": "The Dusk Bell", "text": "Every evening at sunset, the Academy\'s great bell is rung and all scholars observe a minute of stillness and silence.", "kind": "event"}, {"drawer": "Rites and Customs", "name": "The Feathering Ceremony", "text": "New students receive their first academic talisman during a dawn ceremony in the Spire\'s upper gallery.", "kind": "event"}, {"drawer": "Rites and Customs", "name": "The Night of Feathers Remembrance", "text": "On October 1st each year, the Academy holds a solemn vigil commemorating the transformation of all Moscavians.", "kind": "event"}, {"drawer": "Rites and Customs", "name": "The Rune-Tasting", "text": "Senior students must demonstrate mastery by inscribing a complex glyph from memory while blindfolded, judged by the Oversight Council.", "kind": "event"}, {"drawer": "Sites and Territory", "name": "Spire of Inscriptions", "text": "The Academy\'s central tower, carved from pale Kremovan limestone and covered in functioning runic script.", "kind": "place"}, {"drawer": "Sites and Territory", "name": "The Roosting Galleries", "text": "A network of wooden nesting platforms and sleeping alcoves built into the Academy\'s outer walls for owl-folk scholars.", "kind": "place"}, {"drawer": "Sites and Territory", "name": "The Vesna Campus", "text": "The Academy occupies a quarter-mile stretch along the south bank of the Vesna river, connected by stone bridges.", "kind": "place"}, {"drawer": "Sites and Territory", "name": "The Deep Archive", "text": "A subterranean vault beneath the Spire containing the oldest known runic texts, sealed with perpetual wards.", "kind": "place"}], "names": [{"name": "Kremova", "kind": "place", "aka": []}, {"name": "Tsardom of Moscavia", "kind": "place", "aka": []}, {"name": "Vesna", "kind": "place", "aka": []}, {"name": "Owl-folk", "kind": "species", "aka": []}, {"name": "Night of Feathers", "kind": "event", "aka": []}, {"name": "Tsar Alexei II", "kind": "character", "aka": []}, {"name": "Grand Archivist Veleska", "kind": "character", "aka": []}, {"name": "Arcanum of Lúthien", "kind": "place", "aka": []}] }'

# fill 4: the White Dawn expanded after the Council of Elders was made part of it
CORE_AFTER_COUNCIL = '{ "name": "The White Dawn", "summary": "The White Dawn is the state church of the Tsardom of Moscavia, teaching that the Night of Feathers was a divine purification that transformed the people of the north.", "aka": [{"name": "White Dawn Church", "tag": "common", "everyday": true}], "timeline": [{"year": 994, "text": "The Night of Feathers transforms nearly all Moscavians into owl-folk, and the White Dawn is founded to interpret this as divine will."}, {"year": 1001, "text": "The Council of Elders is established in Kremova to govern doctrine and settle matters of faith."}, {"year": 1015, "text": "The White Dawn declares that the owl-form is the image of humanity\'s purified soul, and rejects pre-Feathers traditions as corruption."}], "drawers": [{"type": "beliefs", "title": "Doctrines"}, {"type": "practices", "title": "Rites and Ceremonies"}, {"type": "places", "title": "Holy Sites"}, {"type": "structure", "title": "Hierarchy"}], "items": [{"drawer": "Doctrines", "name": "The Purification", "text": "The Night of Feathers was a holy act by which the old corruption was burned away.", "kind": "lore"}, {"drawer": "Doctrines", "name": "", "text": "Owl-form is the natural and sacred state of the purified soul.", "kind": "lore"}, {"drawer": "Doctrines", "name": "The Threefold Truth", "text": "Silence, Sight, and Stillness are the virtues by which the faithful approach the divine.", "kind": "lore"}, {"drawer": "Rites and Ceremonies", "name": "The Dawn Vigil", "text": "Each morning at first light, the faithful stand in silence until the sun clears the horizon.", "kind": "rite"}, {"drawer": "Rites and Ceremonies", "name": "The Feast of White Wings", "text": "Held on the winter solstice, it commemorates the Night of Feathers with feasting and hymns.", "kind": "event"}, {"drawer": "Rites and Ceremonies", "name": "The Quieting", "text": "Before sleep each night, the faithful fold their hands and recite the Prayer of Soft Eyes.", "kind": "rite"}, {"drawer": "Holy Sites", "name": "Kremova", "text": "The holy city where the Council of Elders meets and the Tsar rules from white stone towers.", "kind": "place"}, {"drawer": "Holy Sites", "name": "The Roosting Galleries", "text": "Tower balconies in Kremova where the elders perch during council deliberations.", "kind": "place"}, {"drawer": "Hierarchy", "name": "The Council of Elders", "text": "Seven owl-folk elders who meet at each new moon to rule on matters of doctrine.", "kind": "lore"}, {"drawer": "Hierarchy", "name": "The High Seer", "text": "The senior elder who chairs the Council and speaks as the voice of the White Dawn.", "kind": "lore"}], "names": [{"name": "Tsardom of Moscavia", "kind": "place", "aka": []}, {"name": "Moscavia", "kind": "place", "aka": []}, {"name": "Kremova", "kind": "place", "aka": []}, {"name": "Night of Feathers", "kind": "event", "aka": []}, {"name": "Council of Elders", "kind": "sphere", "aka": [], "template": "council"}, {"name": "owl-folk", "kind": "species", "aka": []}, {"name": "Vesna", "kind": "place", "aka": []}, {"name": "Tsar", "kind": "lore", "aka": []}, {"name": "The Threefold Truth", "kind": "lore", "aka": []}, {"name": "Dawn Vigil", "kind": "rite", "aka": []}, {"name": "Feast of White Wings", "kind": "event", "aka": []}, {"name": "The Quieting", "kind": "rite", "aka": []}, {"name": "Roosting Galleries", "kind": "place", "aka": []}, {"name": "High Seer", "kind": "lore", "aka": []}] }'

# fill 2: Rites, repeating both of the drawer's items
FILL_RITES_REPEATS = '{ "items":  [\n    {"name": "The Feathering", "text": "On the anniversary of the Night of Feathers, every believer offers a moulted feather to the altar flame.", "kind": "event"},\n    {"name": "The Dawn Vigil", "text": "At every dawn the faithful gather in silence on high galleries to watch the first light.", "kind": "event"},\n    {"name": "The Pale Spire Pilgrimage", "text": "Once every three years each parish sends two walkers on a pilgrimage to the Pale Spire in Kremova.", "kind": "event"},\n    {"name": "The First Frost Rite", "text": "When the first frost whitewashes the northern forests, the faithful leave small offerings of amber and pine at their roosting galleries.", "kind": "event"},\n    {"name": "The Separation Covenant", "text": "Upon reaching maturity, every owl-folk takes a vow before their Dawn-priest to honor the Doctrine of Separation for life.", "kind": "lore"}\n  ],  "names":  [\n    {"name": "The Night of Feathers", "kind": "event", "aka": []},\n    {"name": "The Pale Spire", "kind": "place", "aka": []},\n    {"name": "Kremova", "kind": "place", "aka": []},\n    {"name": "Moscavia", "kind": "place", "aka": []},\n    {"name": "Dawn-priest", "kind": "lore", "aka": []},\n    {"name": "The Council of Elders", "kind": "lore", "aka": []}\n  ]}'

# fill 8: Rites with the new_items key; month names in its names
FILL_RITES_NEW_ITEMS = '{ "new_items": [ {"name": "The Feathering", "text": "Each spring, the faithful collect their moulted feathers over a full moon cycle and bring them to their parish altar on the first day of May.", "kind": "lore"}, {"name": "The Long Silence of November", "text": "During November, all singing and spoken worship ceases; the faithful observe a month of wordless contemplation on the galleries.", "kind": "lore"}, {"name": "First Flight Rite", "text": "When a young owl-folk takes its first flight, the family gathers at the nearest gallery and releases a white lantern into the darkening sky.", "kind": "lore"}, {"text": "Dawn-priests wash their faces in snowmelt each morning before leading the Vigil, symbolizing renewed purity before the light."} ], "names": [ {"name": "May", "kind": "event", "aka": []}, {"name": "November", "kind": "event", "aka": []} ] }'


# --- the world ---------------------------------------------------------------


class Moscavia(NamedTuple):
    tsardom: str
    kremova: str
    owl_folk: str
    dawn: str


@pytest.fixture
def moscavia(world):
    """The probe's fresh world, present year 1020: the Tsardom of Moscavia
    (a place), its capital Kremova, the Owl-folk, and the White Dawn as a
    religion sphere stub the Tsardom's law names."""

    world.set_present(WorldDate.of(1020))
    with world.revision(Source.manual(note="moscavia")) as rev:
        tsardom = rev.create_thing(
            "place",
            {
                "name": "Tsardom of Moscavia",
                "kind": "country",
                "aka": [{"name": "Moscavia", "tag": "common", "everyday": True}],
            },
        )
        kremova = rev.create_thing(
            "place", {"name": "Kremova", "kind": "city", "parent": tsardom}
        )
        owl_folk = rev.create_thing("species", {"name": "Owl-folk"})
        dawn = rev.create_thing(
            "sphere",
            {
                "name": "The White Dawn",
                "template": "religion",
                "stub": {"ignored": False},
            },
        )
        rev.add_fact(
            tsardom,
            "description",
            "The Tsardom of Moscavia is a northern realm of pine forest, bog "
            "and slow brown rivers.",
        )
        rev.add_fact(
            tsardom,
            "law",
            f"{ref(dawn, 'The White Dawn')} is the Tsardom's state church, and "
            "teaches that the Night of Feathers was a purification.",
        )
        rev.add_fact(kremova, "description", "Kremova is the capital of the Tsardom.")
    return Moscavia(tsardom=tsardom, kremova=kremova, owl_folk=owl_folk, dawn=dawn)


def _snapshot(world):
    view = world.view()
    return world.head_rev(), sorted(t.id for t in view.things())


def _drawer_ids(preview: SpherePreview) -> dict[str, str]:
    return {drawer["title"]: drawer["id"] for drawer in preview.drawers}


def _named(view, name: str):
    return [t for t in view.things() if view.name_of(t.id) == name]


async def _dawn_preview(world, dawn: str, reply: str = CORE_RELIGION):
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply)
        preview = await preview_sphere(
            world,
            "religion",
            "The White Dawn: the Tsardom's state church.",
            {},
            client,
            stub_id=dawn,
        )
    return preview, client


# --- the core ----------------------------------------------------------------


async def test_preview_sphere_outline_and_items(moscavia, world):
    before = _snapshot(world)
    preview, client = await _dawn_preview(world, moscavia.dawn)

    # nothing written, and one call: the summary is the description
    assert _snapshot(world) == before
    assert len(client.prompt_history) == 1
    assert client.prompt_history[0]["kind"] == "creative_instruction_2048"
    prompt = str(client.prompt_history[0]["prompt"])
    assert "religion (a faith or church)" in prompt
    # the stub's mentions are its context
    assert "state church" in prompt
    assert "- beliefs: Doctrines" in prompt
    assert '"drawer": "the drawer\'s title"' in prompt

    assert isinstance(preview, SpherePreview)
    assert preview.kind == "sphere"
    assert preview.stub_id == moscavia.dawn
    assert preview.name == "The White Dawn"
    assert (preview.template, preview.agent) == ("religion", True)
    # the reply's drawers, then the ones the app keeps (people, timeline,
    # branches)
    assert [(d["type"], d["title"]) for d in preview.drawers] == [
        ("beliefs", "Doctrines"),
        ("practices", "Rites and Ceremonies"),
        ("places", "Holy Sites"),
        ("structure", "Hierarchy"),
        ("people", "People"),
        ("events", "Timeline"),
        ("branches", "Branches"),
    ]
    assert all(len(d["id"]) == 8 for d in preview.drawers)

    ids = _drawer_ids(preview)
    by_name = {item["name"]: item for item in preview.items}
    assert len(preview.items) == 16
    assert by_name["The Dawn Vigil"] == {
        "drawer_id": ids["Rites and Ceremonies"],
        "name": "The Dawn Vigil",
        "text": "The nightly prayer service held at every Dawn chapel, marking "
        "the transition from darkness to light.",
        "kind": "lore",
        # nothing in the world it could be (ruling C9)
        "same_as": [],
    }
    assert by_name["The Feast of Purification"]["kind"] == "event"
    assert by_name["The Cathedral of White Wings"]["kind"] == "place"
    # the two nameless items are statements
    statements = [item for item in preview.items if not item["name"]]
    assert [item["drawer_id"] for item in statements] == [
        ids["Doctrines"],
        ids["Holy Sites"],
    ]

    # the timeline, dated; the summary is the description prose
    assert [(f.category, f.since) for f in preview.facts] == [
        ("timeline", WorldDate.of(994)),
        ("timeline", WorldDate.of(996)),
        ("timeline", WorldDate.of(1012)),
        ("timeline", WorldDate.of(1020)),
    ]
    assert preview.prose["description"].startswith("The White Dawn is the state church")
    assert {a["name"] for a in preview.aka} == {
        "The Church of the White Dawn",
        "the Dawn Church",
    }
    # names that are items, or already in the world, make no stub
    new = {n.name for n in preview.new_names}
    assert not new & {item["name"] for item in preview.items}
    assert not new & {"Kremova", "Tsardom of Moscavia", "Owl-folk"}


async def test_accept_sphere_makes_item_stubs_part_of(moscavia, world):
    preview, _ = await _dawn_preview(world, moscavia.dawn)
    head = world.head_rev()

    thing_id = accept_sphere(world, preview)

    assert thing_id == moscavia.dawn
    assert world.head_rev() == head + 1
    view = world.view()
    dawn = view.thing(thing_id)
    assert dawn.kind == "sphere"
    assert not dawn.is_stub
    assert dawn.fields["template"] == "religion"
    assert dawn.fields["agent"] is True
    assert dawn.fields["drawers"] == preview.drawers

    ids = _drawer_ids(preview)
    found = spheres.items(view, thing_id)
    assert len(found) == 16
    vigil = next(item for item in found if item.name == "The Dawn Vigil")
    assert vigil.stub and vigil.drawer_id == ids["Rites and Ceremonies"]
    assert vigil.text.startswith("The nightly prayer service")
    vigil_state = view.thing(vigil.thing_id)
    assert vigil_state.kind == "lore"
    assert vigil_state.fields["part_of"] == {
        "sphere": thing_id,
        "drawer": ids["Rites and Ceremonies"],
    }
    cathedral = next(i for i in found if i.name == "The Cathedral of White Wings")
    assert view.thing(cathedral.thing_id).kind == "place"
    assert cathedral.thing_id in spheres.territory(view, thing_id)
    statements = [item for item in found if item.thing_id is None]
    assert [item.drawer_id for item in statements] == [
        ids["Doctrines"],
        ids["Holy Sites"],
    ]

    timeline = spheres.timeline(view, thing_id)
    assert [f.valid_from for f in timeline] == [
        WorldDate.of(year) for year in (994, 996, 1012, 1020)
    ]
    # a timeline fact naming an item links to its stub
    feast = next(i for i in found if i.name == "The Feast of Purification")
    assert any(feast.thing_id in parse_refs(f.text) for f in timeline)
    # the summary is the cached description
    cached = world.prose().get(thing_id, "description", None)
    assert cached is not None and cached.text == preview.prose["description"]


async def test_expand_sphere_adopts_existing_children(moscavia, world):
    with world.revision(Source.manual(note="council")) as rev:
        council = rev.create_thing(
            "lore",
            {
                "name": "Council of Elders",
                "part_of": {"sphere": moscavia.dawn, "drawer": UNSORTED_DRAWER_ID},
            },
        )
        rev.add_fact(
            council,
            "general",
            "Seven snowy owl-folk elders who rule the White Dawn from Kremova.",
        )

    preview, client = await _dawn_preview(world, moscavia.dawn, CORE_AFTER_COUNCIL)

    prompt = str(client.prompt_history[0]["prompt"])
    assert "Already part of it" in prompt
    assert "Seven snowy owl-folk elders" in prompt
    ids = _drawer_ids(preview)
    # relisted as "The Council of Elders": adopted, in that item's drawer
    assert preview.adopted == [{"thing_id": council, "drawer_id": ids["Hierarchy"]}]
    names = [item["name"] for item in preview.items]
    assert "The Council of Elders" not in names
    # an item that's already in the world is no stub: Kremova
    assert "Kremova" not in names
    assert any(
        item["text"].startswith("Kremova") and not item["name"]
        for item in preview.items
    )

    accept_sphere(world, preview)
    view = world.view()
    assert view.thing(council).fields["part_of"] == {
        "sphere": moscavia.dawn,
        "drawer": ids["Hierarchy"],
    }
    hierarchy = [
        item.thing_id
        for item in spheres.items(view, moscavia.dawn)
        if item.drawer_id == ids["Hierarchy"]
    ]
    assert council in hierarchy
    assert len(_named(view, "Council of Elders")) == 1
    assert len(_named(view, "Kremova")) == 1


async def test_expand_item_stub_as_nested_sphere(moscavia, world):
    """An item stub the core made (lore, with its text as a fact) expands
    as a sphere of its own: its fact is kept as "about", and it stays in
    its parent's drawer."""

    preview, _ = await _dawn_preview(world, moscavia.dawn)
    accept_sphere(world, preview)
    view = world.view()
    (synod,) = _named(view, "The Synod of Dawns")
    fact_ids = [f.fact_id for f in synod.facts]

    client = MockClient("test")
    async with MockClientContext():
        _queue(CORE_ORDER)
        nested = await preview_sphere(world, "order", "", {}, client, stub_id=synod.id)
    assert "A council of twelve senior clergy" in str(
        client.prompt_history[0]["prompt"]
    )
    accept_sphere(world, nested)

    state = world.view().thing(synod.id)
    assert state.kind == "sphere" and not state.is_stub
    assert state.fields["name"] == "The Synod of Dawns"
    assert state.fields["part_of"] == synod.fields["part_of"]
    assert [(f.fact_id, f.category) for f in state.facts if f.fact_id in fact_ids] == [
        (fact_ids[0], "about")
    ]


# --- child first -------------------------------------------------------------


LORE_REPLY = json.dumps(
    {
        "name": "Council of Elders",
        "facts": [
            {
                "category": "general",
                "text": "Seven snowy elders who rule the White Dawn from Kremova.",
            }
        ],
    }
)


async def test_child_first_gets_part_of_stub_parent_untouched(moscavia, world):
    with world.revision(Source.manual(note="council stub")) as rev:
        council = rev.create_thing(
            "lore", {"name": "Council of Elders", "stub": {"ignored": False}}
        )
        rev.add_fact(
            moscavia.kremova,
            "description",
            f"The {ref(council, 'Council of Elders')} of "
            f"{ref(moscavia.dawn, 'the White Dawn')} sits in Kremova.",
        )
    dawn_before = world.view().thing(moscavia.dawn)

    client = MockClient("test")
    async with MockClientContext():
        _queue(LORE_REPLY, "Seven elders.")
        preview = await preview_thing(
            world,
            "lore",
            "Council of Elders: The Council of Elders of the White Dawn sits in "
            "Kremova.",
            {},
            client,
            stub_id=council,
        )
    assert preview.part_of == {"sphere": moscavia.dawn, "drawer": UNSORTED_DRAWER_ID}

    accept_preview(world, preview)
    view = world.view()
    assert view.thing(council).fields["part_of"] == preview.part_of
    # the parent was never generated: still a bare stub
    dawn = view.thing(moscavia.dawn)
    assert dawn.is_stub
    assert dawn.fields == dawn_before.fields
    assert dawn.facts == []
    assert [i.thing_id for i in spheres.items(view, moscavia.dawn)] == [council]


async def test_child_first_from_sphere_items_guesses_drawer(moscavia, world):
    preview, _ = await _dawn_preview(world, moscavia.dawn)
    accept_sphere(world, preview)
    ids = _drawer_ids(preview)
    with world.revision(Source.manual(note="spire")) as rev:
        spire = rev.create_thing(
            "place", {"name": "Pale Spire", "stub": {"ignored": False}}
        )
        # mentioned only by a statement of the sphere's Rites drawer
        rev.add_fact(
            moscavia.dawn,
            "statement",
            f"Pilgrims climb the {ref(spire, 'Pale Spire')} at midwinter.",
            origin={"drawer": ids["Rites and Ceremonies"]},
        )

    client = MockClient("test")
    reply = json.dumps(
        {
            "name": "Pale Spire",
            "facts": [{"category": "description", "text": "A white tower."}],
        }
    )
    async with MockClientContext():
        _queue(reply, "A white tower.")
        child = await preview_thing(
            world, "place", "Pale Spire: a white tower.", {}, client, stub_id=spire
        )
    # a place goes to the sphere's places drawer
    assert child.part_of == {"sphere": moscavia.dawn, "drawer": ids["Holy Sites"]}


# --- promotion ---------------------------------------------------------------


async def test_promote_lore_keeps_id_and_facts(moscavia, world):
    with world.revision(Source.manual(note="academy")) as rev:
        academy = rev.create_thing("lore", {"name": "Imperial Academy of Runecraft"})
        undated = rev.add_fact(
            academy, "general", "Owl-folk scholars study runic magic in Kremova."
        )
        dated = rev.add_fact(
            academy,
            "general",
            "The Academy opened its doors.",
            valid_from=WorldDate.of(996),
        )
        rev.add_fact(
            moscavia.kremova,
            "description",
            f"Kremova is home to the {ref(academy, 'Imperial Academy of Runecraft')}.",
        )

    client = MockClient("test")
    async with MockClientContext():
        _queue(CORE_ORDER)
        preview = await preview_sphere(
            world, "order", "", {}, client, promote_id=academy
        )
    prompt = str(client.prompt_history[0]["prompt"])
    assert "Already known about it" in prompt
    assert "Owl-folk scholars study runic magic in Kremova." in prompt
    assert preview.promote_id == academy
    assert preview.kind == "sphere"

    assert accept_sphere(world, preview) == academy
    view = world.view()
    state = view.thing(academy)
    assert state.kind == "sphere"
    assert (state.fields["template"], state.fields["agent"]) == ("order", True)
    assert state.fields["name"] == "Imperial Academy of Runecraft"
    facts = {f.fact_id: f.category for f in state.facts}
    assert facts[undated] == "about"
    assert facts[dated] == "timeline"
    # its own facts, then the core's timeline
    assert len(spheres.timeline(view, academy)) == 1 + 4
    assert moscavia.kremova in {owner for owner, _ in view.referencing(academy)}
    assert len(spheres.items(view, academy)) == 17


async def test_promote_place_keeps_kind(moscavia, world):
    view = world.view()
    facts_before = {f.fact_id for f in view.thing(moscavia.tsardom).facts}

    client = MockClient("test")
    async with MockClientContext():
        _queue(CORE_NATION)
        preview = await preview_sphere(
            world, "nation", "", {}, client, promote_id=moscavia.tsardom
        )
    assert preview.kind == "place"
    accept_sphere(world, preview)

    view = world.view()
    state = view.thing(moscavia.tsardom)
    assert state.kind == "place"
    assert spheres.is_sphere(state)
    assert state.fields["template"] == "nation"
    assert state.fields["agent"] is True
    assert state.fields["aka"] == [
        {"name": "Moscavia", "tag": "common", "everyday": True}
    ]
    assert facts_before <= {f.fact_id for f in state.facts}
    titles = [d["title"] for d in state.fields["drawers"]]
    assert titles[:5] == [
        "Lands",
        "Rites & Customs",
        "Laws & Doctrine",
        "Government",
        "Learning",
    ]
    # Kremova, already in the world, is linked, not made again
    assert len(_named(view, "Kremova")) == 1
    assert moscavia.kremova in spheres.territory(view, moscavia.tsardom)
    # the place's timeline shows (ruling P7)
    assert [f.valid_from for f in spheres.timeline(view, moscavia.tsardom)] == [
        WorldDate.of(year) for year in (994, 1001, 1015, 1020)
    ]


async def test_place_create_prompt_hides_sphere_categories(moscavia, world):
    """A place may hold timeline, about and statement facts as a sphere,
    but a plain place's create prompt never offers them."""

    reply = json.dumps(
        {
            "name": "Vesnagrad",
            "facts": [
                {"category": "description", "text": "A river town."},
                {"category": "timeline", "text": "Founded long ago."},
            ],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "A river town.")
        preview = await preview_thing(world, "place", "a river town", {}, client)
    prompt = str(client.prompt_history[0]["prompt"])
    assert "description, history, law, general." in prompt
    assert "timeline" not in prompt.split("FORMAT")[-1]
    assert [f.category for f in preview.facts] == ["description", "general"]


async def test_create_prompt_names_faiths_and_orders_as_spheres(moscavia, world):
    """A thing's create prompt lists names of kind "sphere" with a template,
    in the core's wording (the spheres Task 10 session: from the old "a
    group, order or faction is lore", the Tsardom's state church came back
    as lore), so the faith a place names becomes a religion sphere stub."""

    reply = json.dumps(
        {
            "name": "Vesnagrad",
            "facts": [
                {
                    "category": "description",
                    "text": "A river town where the Church of the Vesna keeps "
                    "its oldest shrine.",
                }
            ],
            "names": [
                {
                    "name": "Church of the Vesna",
                    "kind": "sphere",
                    "template": "religion",
                    "aka": [],
                }
            ],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "A river town.")
        preview = await preview_thing(world, "place", "a river town", {}, client)
    prompt = str(client.prompt_history[0]["prompt"])
    assert '"kind" one of character, place, species, race, sphere, event' in prompt
    assert (
        "A faith or church, an order, academy, guild or council, a culture, or a "
        'field of knowledge or magic is "sphere", with a "template": religion, '
        "order, culture or field, only these" in prompt
    )
    assert "a group, order or faction is lore" not in prompt
    assert [(n.name, n.kind, n.template) for n in preview.new_names] == [
        ("Church of the Vesna", "sphere", "religion")
    ]


# --- Fill --------------------------------------------------------------------


@pytest.fixture
async def full_dawn(moscavia, world):
    """The White Dawn after its core: the Dawn Vigil is in Rites and
    Ceremonies, plus the feather-offering statement."""

    preview, _ = await _dawn_preview(world, moscavia.dawn)
    accept_sphere(world, preview)
    rites = _drawer_ids(preview)["Rites and Ceremonies"]
    with world.revision(Source.manual(note="offering")) as rev:
        rev.add_fact(
            moscavia.dawn,
            "statement",
            "On each anniversary of the Night of Feathers, every believer "
            "offers a moulted feather to the altar flame.",
            origin={"drawer": rites},
        )
    return rites


async def test_fill_drawer_no_write_until_accept(moscavia, world, full_dawn):
    rites = full_dawn
    before = _snapshot(world)

    client = MockClient("test")
    async with MockClientContext():
        _queue(FILL_RITES_REPEATS)
        items = (await fill_drawer(world, moscavia.dawn, rites, client)).items

    assert _snapshot(world) == before
    assert client.prompt_history[0]["kind"] == "creative_instruction_1024"
    prompt = str(client.prompt_history[0]["prompt"])
    assert '"new_items"' in prompt
    assert "Rites and Ceremonies (practices), the drawer to fill" in prompt
    # the repeats come last, unticked: the Dawn Vigil by name, "The
    # Feathering" by its text (the feather offering, nearly word for word)
    assert [(item["name"], item["ticked"]) for item in items] == [
        ("The Pale Spire Pilgrimage", True),
        ("The First Frost Rite", True),
        ("The Separation Covenant", True),
        ("The Feathering", False),
        ("The Dawn Vigil", False),
    ]
    assert items[4]["repeat_of"]["score"] == 1.0
    assert {item["drawer_id"] for item in items} == {rites}
    # a stray kind ("event" is fine; "rite" would be lore)
    assert items[0]["kind"] == "event"

    accept_fill(world, moscavia.dawn, rites, items)
    view = world.view()
    in_rites = {
        item.name
        for item in spheres.items(view, moscavia.dawn)
        if item.drawer_id == rites
    }
    assert {"The Pale Spire Pilgrimage", "The Separation Covenant"} <= in_rites


async def test_fill_new_items_statements_and_months(moscavia, world, full_dawn):
    rites = full_dawn
    client = MockClient("test")
    async with MockClientContext():
        _queue(FILL_RITES_NEW_ITEMS)
        items = (await fill_drawer(world, moscavia.dawn, rites, client)).items

    assert [item["name"] for item in items] == [
        "The Feathering",
        "The Long Silence of November",
        "First Flight Rite",
        "",
    ]
    accept_fill(world, moscavia.dawn, rites, items)
    view = world.view()
    # month names never become stubs
    assert not _named(view, "May")
    assert not _named(view, "November")
    statement = [
        item
        for item in spheres.items(view, moscavia.dawn)
        if item.thing_id is None and item.text.startswith("Dawn-priests wash")
    ]
    assert [item.drawer_id for item in statement] == [rites]


# --- stub kind guesses -------------------------------------------------------


async def test_culture_guess_becomes_culture_sphere(moscavia, world):
    reply = json.dumps(
        {
            "name": "Vesnagrad",
            "facts": [
                {
                    "category": "description",
                    "text": "Vesnagrad keeps the Moscavian Way and the Rite "
                    "of Amber, and hosts the Guild of Rafters.",
                }
            ],
            "names": [
                {"name": "Moscavian Way", "kind": "culture", "aka": []},
                {"name": "Guild of Rafters", "kind": "sphere", "template": "guild"},
                {"name": "Rite of Amber", "kind": "sphere", "template": "rite"},
            ],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "Vesnagrad on the river.")
        preview = await preview_thing(world, "place", "a river town", {}, client)

    guesses = {n.name: (n.kind, n.template) for n in preview.new_names}
    assert guesses == {
        "Moscavian Way": ("sphere", "culture"),
        "Guild of Rafters": ("sphere", "order"),
        # a template outside the set is dropped, the sphere guess kept
        "Rite of Amber": ("sphere", None),
    }

    accept_preview(world, preview)
    view = world.view()
    (way,) = _named(view, "Moscavian Way")
    assert way.kind == "sphere"
    assert way.is_stub
    assert way.fields["template"] == "culture"
    assert not view.things("culture")


async def test_core_guards(moscavia, world):
    """The probe's guards: drawers of the app's types or repeated titles
    are dropped; an item naming no drawer title goes to the first drawer of
    the type it names, else unsorted; a stray kind is lore; month names
    and items' own names make no stub; a council template is an order."""

    reply = json.dumps(
        {
            "name": "The Amber Road",
            "summary": "The river trade of Moscavia.",
            "timeline": [
                {"year": 1001, "text": "The Rafters' Compact was signed."},
                {"year": 1300, "text": "A year after now."},
            ],
            "drawers": [
                {"type": "practices", "title": "Customs"},
                {"type": "people", "title": "Rafters"},
                {"type": "practices", "title": "customs"},
                {"type": "lore", "title": "Odd"},
            ],
            "items": [
                {
                    "drawer": "Customs",
                    "name": "The Barge Blessing",
                    "text": "Every barge is blessed before it leaves.",
                    "kind": "ceremony",
                },
                {
                    "drawer": "practices",
                    "name": "The Toll Song",
                    "text": "Rafters sing at every toll.",
                    "kind": "custom",
                },
                {"drawer": "Nowhere", "text": "Amber is weighed in May."},
            ],
            "names": [
                {"name": "May", "kind": "event"},
                {"name": "Rafters' Compact", "kind": "sphere", "template": "council"},
                {"name": "The Barge Blessing", "kind": "rite"},
            ],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply)
        preview = await preview_sphere(
            world, "other", "The Amber Road: the river trade.", {}, client
        )

    assert preview.agent is False
    assert [(d["type"], d["title"]) for d in preview.drawers] == [
        ("practices", "Customs"),
        ("events", "Timeline"),
    ]
    customs = preview.drawers[0]["id"]
    assert [(i["name"], i["drawer_id"], i["kind"]) for i in preview.items] == [
        ("The Barge Blessing", customs, "lore"),
        ("The Toll Song", customs, "lore"),
        ("", UNSORTED_DRAWER_ID, ""),
    ]
    # a year after now is no date: that entry is filed as "about"
    assert [(f.category, f.since) for f in preview.facts] == [
        ("timeline", WorldDate.of(1001)),
        ("about", None),
    ]
    assert [(n.name, n.kind, n.template) for n in preview.new_names] == [
        ("Rafters' Compact", "sphere", "order")
    ]

    thing_id = accept_sphere(world, preview)
    view = world.view()
    unsorted = [
        item
        for item in spheres.items(view, thing_id)
        if item.drawer_id == spheres.UNSORTED.id
    ]
    assert [item.text for item in unsorted] == ["Amber is weighed in May."]
    (compact,) = _named(view, "Rafters' Compact")
    assert (compact.kind, compact.fields["template"]) == ("sphere", "order")


async def test_character_stub_named_as_item_is_not_drawn_in(moscavia, world):
    """A character stub sharing an item's name stays out of the drawer:
    people come only from ties. The item is a statement linking it."""

    with world.revision(Source.manual(note="patriarch")) as rev:
        patriarch = rev.create_thing(
            "character", {"name": "The Grand Patriarch", "stub": {"ignored": False}}
        )
    preview, _ = await _dawn_preview(world, moscavia.dawn)
    assert "The Grand Patriarch" not in [item["name"] for item in preview.items]
    statement = [i for i in preview.items if i["text"].startswith("The Grand")]
    assert statement and not statement[0]["name"]

    accept_sphere(world, preview)
    view = world.view()
    assert view.thing(patriarch).fields.get("part_of") is None
    assert view.thing(patriarch).facts == []


async def test_free_sphere_stub_named_as_item_nests(moscavia, world):
    with world.revision(Source.manual(note="synod")) as rev:
        synod = rev.create_thing(
            "sphere",
            {
                "name": "The Synod of Dawns",
                "template": "order",
                "stub": {"ignored": False},
            },
        )
    preview, _ = await _dawn_preview(world, moscavia.dawn)
    ids = _drawer_ids(preview)
    (item,) = [i for i in preview.items if i.get("thing_id") == synod]
    accept_sphere(world, preview)
    state = world.view().thing(synod)
    assert state.fields["part_of"] == {
        "sphere": moscavia.dawn,
        "drawer": ids["Hierarchy"],
    }
    assert [f.category for f in state.facts] == ["about"]


async def test_child_first_sphere_stub_gets_part_of(moscavia, world):
    """A council guessed as an order sphere, expanded as a sphere while the
    White Dawn is still a stub: its prompt names the White Dawn, so it's
    made part of it (unsorted) and the White Dawn stays a bare stub; then
    the White Dawn's core adopts it. A sphere whose prompt names a stub
    that's already part of it isn't made part of that."""

    with world.revision(Source.manual(note="council stub")) as rev:
        council = rev.create_thing(
            "sphere",
            {
                "name": "Council of Elders",
                "template": "order",
                "stub": {"ignored": False},
            },
        )
        rev.add_fact(
            moscavia.kremova,
            "description",
            f"The {ref(council, 'Council of Elders')} of "
            f"{ref(moscavia.dawn, 'the White Dawn')} sits in Kremova.",
        )
    dawn_before = world.view().thing(moscavia.dawn)

    client = MockClient("test")
    async with MockClientContext():
        _queue(CORE_ORDER)
        preview = await preview_sphere(
            world,
            "order",
            "Council of Elders: The Council of Elders of the White Dawn sits in "
            "Kremova.",
            {},
            client,
            stub_id=council,
        )
    assert preview.part_of == {"sphere": moscavia.dawn, "drawer": UNSORTED_DRAWER_ID}
    accept_sphere(world, preview)
    view = world.view()
    assert view.thing(council).fields["part_of"] == preview.part_of
    dawn = view.thing(moscavia.dawn)
    assert dawn.is_stub and dawn.fields == dawn_before.fields and dawn.facts == []
    assert [i.thing_id for i in spheres.items(view, moscavia.dawn)] == [council]

    # the White Dawn, mentioned by the Tsardom's law (no sphere's item) and
    # naming no sphere stub in its prompt, joins nothing; the council is
    # adopted (the cycle guard: test_child_first_never_joins_its_own_child)
    preview, _ = await _dawn_preview(world, moscavia.dawn, CORE_AFTER_COUNCIL)
    assert preview.part_of is None
    assert [a["thing_id"] for a in preview.adopted] == [council]


async def test_child_first_never_joins_its_own_child(moscavia, world):
    """A sphere stub expanded after a child that's part of it is never made
    part of that child (`create._sits_in`): not when its only mention is a
    statement of the child, an order sphere in its drawers; nor when its
    prompt names a child that's still a stub."""

    with world.revision(Source.manual(note="grey dawn")) as rev:
        grey = rev.create_thing(
            "sphere",
            {
                "name": "The Grey Dawn",
                "template": "religion",
                "stub": {"ignored": False},
            },
        )
        council = rev.create_thing(
            "sphere",
            {
                "name": "Grey Council",
                "template": "order",
                "drawers": [{"id": "0000000b", "type": "structure", "title": "Seats"}],
                "part_of": {"sphere": grey, "drawer": UNSORTED_DRAWER_ID},
            },
        )
        # the Grey Dawn's only mention: a statement of the council
        rev.add_fact(
            council,
            "statement",
            f"Seven seats rule {ref(grey, 'the Grey Dawn')}.",
            origin={"drawer": "0000000b"},
        )
        pale = rev.create_thing(
            "sphere",
            {
                "name": "The Pale Dawn",
                "template": "religion",
                "stub": {"ignored": False},
            },
        )
        rev.create_thing(
            "sphere",
            {
                "name": "Pale Council",
                "template": "order",
                "stub": {"ignored": False},
                "part_of": {"sphere": pale, "drawer": UNSORTED_DRAWER_ID},
            },
        )

    client = MockClient("test")
    for stub, prompt in (
        (grey, "The Grey Dawn: Seven seats rule the Grey Dawn."),
        (pale, "The Pale Dawn: a faith ruled by the Pale Council."),
    ):
        async with MockClientContext():
            _queue(CORE_RELIGION)
            preview = await preview_sphere(
                world, "religion", prompt, {}, client, stub_id=stub
            )
        assert preview.part_of is None, prompt
    assert len(client.prompt_history) == 2


async def test_child_first_character_gets_no_part_of(moscavia, world):
    with world.revision(Source.manual(note="orel")) as rev:
        orel = rev.create_thing(
            "character", {"name": "Orel", "stub": {"ignored": False}}
        )
    reply = json.dumps(
        {
            "name": "Orel",
            "age": 60,
            "facts": [
                {"category": "background", "text": "A hermit of the White Dawn."}
            ],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "A hermit.")
        preview = await preview_thing(
            world,
            "character",
            "Orel, hermit of the White Dawn.",
            {},
            client,
            stub_id=orel,
        )
    assert preview.part_of is None
    # every queued reply used, so none leaks into the next test
    assert len(client.prompt_history) == 2


async def test_item_named_the_makes_no_empty_stub(moscavia, world):
    reply = json.dumps(
        {
            "name": "The Amber Road",
            "summary": "The river trade.",
            "drawers": [{"type": "practices", "title": "Customs"}],
            "items": [
                {
                    "drawer": "Customs",
                    "name": "the",
                    "text": "Barges sail at dawn.",
                    "kind": "lore",
                }
            ],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply)
        preview = await preview_sphere(world, "other", "The Amber Road.", {}, client)
    assert [(i["name"], i["text"]) for i in preview.items] == [
        ("", "Barges sail at dawn.")
    ]
    accept_sphere(world, preview)
    assert not [
        t
        for t in world.view().things()
        if not (world.view().name_of(t.id) or "").strip(" .")
    ]


async def test_item_named_like_a_name_treated_as_new_stays_new(moscavia, world):
    with world.revision(Source.manual(note="vigil")) as rev:
        vigil = rev.create_thing(
            "lore", {"name": "The Dawn Vigil", "stub": {"ignored": False}}
        )
    client = MockClient("test")
    async with MockClientContext():
        _queue(CORE_RELIGION)
        preview = await preview_sphere(
            world,
            "religion",
            "The White Dawn and its Dawn Vigil.",
            {},
            client,
            stub_id=moscavia.dawn,
            new_names=["Dawn Vigil"],
        )
    (item,) = [i for i in preview.items if i["name"] == "The Dawn Vigil"]
    assert "thing_id" not in item
    accept_sphere(world, preview)
    assert world.view().thing(vigil).fields.get("part_of") is None


async def test_fill_targets_drawer_by_id(moscavia, world, full_dawn):
    """Two drawers titled alike stay apart: Fill lists and marks the one
    asked for by id."""

    rites = full_dawn
    view = world.view()
    drawers = view.thing(moscavia.dawn).fields["drawers"]
    twin = {"id": "abcdef01", "type": "practices", "title": "Rites and Ceremonies"}
    with world.revision(Source.manual(note="twin")) as rev:
        rev.set_field(moscavia.dawn, "drawers", [*drawers, twin], None)
        rev.add_fact(
            moscavia.dawn,
            "statement",
            "Twin drawer statement.",
            origin={"drawer": twin["id"]},
        )
    client = MockClient("test")
    async with MockClientContext():
        _queue(FILL_RITES_NEW_ITEMS)
        await fill_drawer(world, moscavia.dawn, twin["id"], client)
    prompt = str(client.prompt_history[0]["prompt"])
    assert prompt.count("the drawer to fill") == 1
    already = prompt.split("Already in Rites and Ceremonies")[1].split("Write 3 to 5")[
        0
    ]
    assert "Twin drawer statement." in already
    assert "Dawn Vigil" not in already
    assert rites != twin["id"]


# --- branches and ending an item ----------------------------------------------

# a branch of the White Dawn, written by hand in the core's flat shape (no
# probe ran branches): it drops the Purification Doctrine (F1), replaces the
# Dawn Vigil (F4) with its own vigil and the mark-of-grace statement (F15)
# with its own; F99 is no label
BRANCH_REPLY = '{ "name": "The Reformed Dawn", "summary": "The Reformed Dawn broke from the White Dawn over the doctrine of purification. It teaches that the unchanged are no less blessed.", "aka": [], "timeline": [{"year": 1019, "text": "The Reformed Dawn breaks with the Synod of Dawns over the Purification Doctrine."}], "drawers": [{"type": "beliefs", "title": "Doctrines"}, {"type": "beliefs", "title": "Reformed Teachings"}], "drops": ["F1", "F99"], "items": [{"drawer": "Doctrines", "text": "The owl-form is a trial, not a mark of grace, and the unchanged are equals in the dawn.", "overrides": ["F15"]}, {"drawer": "Rites and Ceremonies", "name": "The Open Vigil", "text": "A dawn prayer open to the feathered and the unchanged alike.", "kind": "lore", "overrides": ["F4"]}, {"drawer": "Reformed Teachings", "text": "Any soul may approach the dawn, feathered or not."}], "names": [] }'


async def _reformed_preview(world, dawn: str):
    client = MockClient("test")
    async with MockClientContext():
        _queue(BRANCH_REPLY)
        preview = await preview_branch(
            world, dawn, "the Reformed Dawn, who reject the purification", client
        )
    return preview, client


async def test_branch_preview_maps_drops_and_overrides(moscavia, world, full_dawn):
    view = world.view()
    held = {item.name: item for item in spheres.items(view, moscavia.dawn)}
    grace = next(i for i in held.values() if i.text.startswith("All owl-folk bear"))
    before = _snapshot(world)

    preview, client = await _reformed_preview(world, moscavia.dawn)

    # nothing written, one call, the parent's items labelled in the prompt
    assert _snapshot(world) == before
    assert len(client.prompt_history) == 1
    prompt = str(client.prompt_history[0]["prompt"])
    assert "a branch of The White Dawn" in prompt
    assert "- F1 (Doctrines): The Purification Doctrine: " in prompt
    assert "- F4 (Rites and Ceremonies): The Dawn Vigil: " in prompt
    assert "- F15 (Doctrines): All owl-folk bear the mark of grace" in prompt
    assert '"drops": ["F2"]' in prompt

    labels = {row["label"]: row for row in preview.parent_items}
    assert labels["F1"]["thing_id"] == held["The Purification Doctrine"].thing_id
    assert labels["F15"]["fact_id"] == grace.fact_id

    # a branch of its parent, dated now, under its parent's template
    assert preview.fields["parent"] == moscavia.dawn
    assert preview.split == WorldDate.of(1020)
    assert (preview.template, preview.agent) == ("religion", True)
    assert preview.name == "The Reformed Dawn"
    # a drawer titled like the parent's is the parent's; only new ones are
    # its own, and the parent's people and timeline serve it
    parent_drawers = {d.title: d.id for d in spheres.drawers(view, moscavia.dawn)}
    assert [(d["type"], d["title"]) for d in preview.drawers] == [
        ("beliefs", "Reformed Teachings")
    ]
    # dropped: F1, and F4, which the Open Vigil replaces
    assert preview.drops == [
        held["The Purification Doctrine"].thing_id,
        held["The Dawn Vigil"].thing_id,
    ]
    assert preview.rejects == []

    def by_text(start):
        return next(i for i in preview.items if i["text"].startswith(start))

    assert by_text("The owl-form")["overrides"] == [grace.fact_id]
    assert by_text("The owl-form")["drawer_id"] == parent_drawers["Doctrines"]
    vigil = by_text("A dawn prayer")
    assert vigil["name"] == "The Open Vigil"
    assert vigil["drawer_id"] == parent_drawers["Rites and Ceremonies"]
    assert by_text("Any soul")["drawer_id"] == preview.drawers[0]["id"]

    branch = accept_sphere(world, preview)

    view = world.view()
    state = view.thing(branch)
    assert state.fields["parent"] == moscavia.dawn
    assert view.field_since(branch, "parent") == WorldDate.of(1020)
    assert state.fields["drops"] == preview.drops
    found = spheres.items(view, branch)
    names = {item.name for item in found}
    assert "The Purification Doctrine" not in names
    assert "The Dawn Vigil" not in names
    assert {"The Three Wings", "The Open Vigil"} <= names
    texts = {item.text for item in found if item.thing_id is None}
    assert grace.text not in texts
    assert any(text.startswith("The owl-form is a trial") for text in texts)
    # the parent keeps all it had
    assert {"The Purification Doctrine", "The Dawn Vigil"} <= {
        item.name for item in spheres.items(view, moscavia.dawn)
    }


async def test_branch_drops_a_statement_by_rejecting_it(moscavia, world, full_dawn):
    """A dropped statement can't be in `drops` (a thing list), nor can a
    named item override it: the branch rejects it with an `about` fact
    overriding it."""

    view = world.view()
    offering = next(
        i
        for i in spheres.items(view, moscavia.dawn)
        if i.text.startswith("On each anniversary")
    )
    sites = next(
        i
        for i in spheres.items(view, moscavia.dawn)
        if i.text.startswith("Every city and town")
    )
    # F17 dropped outright; F16 replaced by a named item
    reply = BRANCH_REPLY.replace('"drops": ["F1", "F99"]', '"drops": ["F17"]').replace(
        '"overrides": ["F4"]', '"overrides": ["F4", "F16"]'
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply)
        preview = await preview_branch(world, moscavia.dawn, "the Reformed", client)

    assert preview.rejects == [offering.fact_id, sites.fact_id]
    branch = accept_sphere(world, preview)
    view = world.view()
    held = {i.fact_id for i in spheres.items(view, branch)}
    assert not {offering.fact_id, sites.fact_id} & held
    about = [
        view.render(f.text) for f in view.thing(branch).facts if f.category == "about"
    ]
    assert f"Rejects: {offering.text}" in about
    assert offering.fact_id in {i.fact_id for i in spheres.items(view, moscavia.dawn)}


async def test_branch_onto_stub_keeps_split_date(moscavia, world, full_dawn):
    """A branch accepted onto a stub of its name still splits at `split`."""

    with world.revision(Source.manual(note="stub")) as rev:
        stub = rev.create_thing(
            "sphere", {"name": "The Reformed Dawn", "stub": {"ignored": False}}
        )
    preview, _ = await _reformed_preview(world, moscavia.dawn)
    assert preview.matching_stub_id == stub

    branch = accept_sphere(world, preview.model_copy(update={"stub_id": stub}))

    assert branch == stub
    view = world.view()
    assert view.thing(branch).fields["parent"] == moscavia.dawn
    assert view.field_since(branch, "parent") == preview.split == WorldDate.of(1020)


def _synod(world) -> str:
    with world.revision(Source.manual(note="synod")) as rev:
        return rev.create_thing(
            "sphere", {"name": "The Iron Synod", "template": "order"}
        )


async def test_end_item_links_both_sides(moscavia, world, full_dawn):
    rites = full_dawn
    synod = _synod(world)
    view = world.view()
    vigil = next(
        i for i in spheres.items(view, moscavia.dawn) if i.name == "The Dawn Vigil"
    )
    head = world.head_rev()

    end_item(world, moscavia.dawn, vigil, WorldDate.of(1015), synod)

    assert world.head_rev() == head + 1

    def in_rites(at):
        return vigil.thing_id in {
            i.thing_id
            for i in spheres.items(world.view(at), moscavia.dawn)
            if i.drawer_id == rites
        }

    assert in_rites(WorldDate.of(1014))
    assert not in_rites(WorldDate.of(1016))
    assert not in_rites(None)

    view = world.view()
    ended = [
        f
        for f in view.thing(vigil.thing_id).facts
        if view.render(f.text).startswith("Ended in")
    ]
    assert [(f.category, view.render(f.text), f.valid_from) for f in ended] == [
        ("general", "Ended in 1015 by The Iron Synod", WorldDate.of(1015))
    ]
    assert synod in parse_refs(ended[0].text)
    (banned,) = spheres.timeline(view, synod)
    assert banned.valid_from == WorldDate.of(1015)
    assert vigil.thing_id in parse_refs(banned.text)
    assert view.render(banned.text) == "Ended The Dawn Vigil"

    # a statement: its fact ends, and the sphere notes it
    offering = next(
        i
        for i in spheres.items(view, moscavia.dawn)
        if i.text.startswith("On each anniversary")
    )
    end_item(world, moscavia.dawn, offering, WorldDate.of(1016), None)
    view = world.view()
    assert offering.fact_id not in {
        i.fact_id for i in spheres.items(view, moscavia.dawn)
    }
    assert offering.fact_id in {
        i.fact_id for i in spheres.items(world.view(WorldDate.of(1015)), moscavia.dawn)
    }
    about = [
        view.render(f.text)
        for f in view.thing(moscavia.dawn).facts
        if f.category == "about" and not spheres.is_summary_fact(f)
    ]
    assert about == [f"Ended in 1016: {offering.text}"]
    # no `by`, no timeline fact anywhere
    assert len(spheres.timeline(view, synod)) == 1


async def test_end_item_then_undo(moscavia, world, full_dawn):
    """The White Dawn ends its own Dawn Vigil; undoing that puts the Vigil
    back in its drawer, at every date, and the timeline back as it was."""

    rites = full_dawn
    view = world.view()
    vigil = next(
        i for i in spheres.items(view, moscavia.dawn) if i.name == "The Dawn Vigil"
    )
    dates = [f.valid_from for f in spheres.timeline(view, moscavia.dawn)]
    vigil_facts = sorted(f.fact_id for f in view.thing(vigil.thing_id).facts)

    end_item(world, moscavia.dawn, vigil, WorldDate.of(1015), moscavia.dawn)
    ended = [f.valid_from for f in spheres.timeline(world.view(), moscavia.dawn)]
    assert ended == sorted([*dates, WorldDate.of(1015)], key=lambda d: d.instant)
    report = world.undo([world.head_rev()])

    assert report.conflicts == []
    for at in (None, WorldDate.of(1015), WorldDate.of(1020)):
        view = world.view(at)
        held = {i.thing_id: i for i in spheres.items(view, moscavia.dawn)}
        assert held[vigil.thing_id].drawer_id == rites
    view = world.view()
    assert view.thing(vigil.thing_id).fields["part_of"] == {
        "sphere": moscavia.dawn,
        "drawer": rites,
    }
    assert sorted(f.fact_id for f in view.thing(vigil.thing_id).facts) == vigil_facts
    assert [f.valid_from for f in spheres.timeline(view, moscavia.dawn)] == dates


async def test_end_statement_then_undo(moscavia, world, full_dawn):
    view = world.view()
    offering = next(
        i
        for i in spheres.items(view, moscavia.dawn)
        if i.text.startswith("On each anniversary")
    )
    about = [
        f.fact_id for f in view.thing(moscavia.dawn).facts if f.category == "about"
    ]

    end_item(world, moscavia.dawn, offering, WorldDate.of(1016), None)
    report = world.undo([world.head_rev()])

    assert report.conflicts == []
    for at in (None, WorldDate.of(1017)):
        view = world.view(at)
        fact = next(
            f for f in view.thing(moscavia.dawn).facts if f.fact_id == offering.fact_id
        )
        assert fact.valid_until is None
        assert offering.fact_id in {
            i.fact_id for i in spheres.items(view, moscavia.dawn)
        }
    view = world.view()
    assert [
        f.fact_id for f in view.thing(moscavia.dawn).facts if f.category == "about"
    ] == about


async def test_end_item_before_its_part_of_refused(moscavia, world, full_dawn):
    """An item can't end before it joined the sphere: nothing is written."""

    rites = full_dawn
    view = world.view()
    vigil = next(
        i for i in spheres.items(view, moscavia.dawn) if i.name == "The Dawn Vigil"
    )
    with world.revision(Source.manual(note="joined")) as rev:
        rev.set_field(
            vigil.thing_id,
            "part_of",
            {"sphere": moscavia.dawn, "drawer": rites},
            WorldDate.of(1010),
        )
    head = world.head_rev()

    with pytest.raises(ValueError):
        end_item(world, moscavia.dawn, vigil, WorldDate.of(1005), None)

    assert world.head_rev() == head


async def test_branch_statement_overridden_once(moscavia, world, full_dawn):
    """A statement label both dropped and replaced by a statement is only
    replaced: no `about` rejection beside the override."""

    reply = BRANCH_REPLY.replace('"drops": ["F1", "F99"]', '"drops": ["F1", "F15"]')
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply)
        preview = await preview_branch(world, moscavia.dawn, "the Reformed", client)

    view = world.view()
    grace = next(
        i
        for i in spheres.items(view, moscavia.dawn)
        if i.text.startswith("All owl-folk bear")
    )
    assert preview.rejects == []
    overriding = [i for i in preview.items if grace.fact_id in i.get("overrides", [])]
    assert len(overriding) == 1
    branch = accept_sphere(world, preview)
    assert not [
        f
        for f in world.view().thing(branch).facts
        if f.category == "about" and not spheres.is_summary_fact(f)
    ]


async def test_end_inherited_item_refused(moscavia, world, full_dawn):
    preview, _ = await _reformed_preview(world, moscavia.dawn)
    branch = accept_sphere(world, preview)
    view = world.view()
    wings = next(i for i in spheres.items(view, branch) if i.name == "The Three Wings")
    assert wings.inherited

    with pytest.raises(ValueError):
        end_item(world, branch, wings, WorldDate.of(1020), None)


# --- re-filing an ended item ---------------------------------------------------


def _vigil(world, dawn: str) -> spheres.Item:
    return next(
        i for i in spheres.items(world.view(), dawn) if i.name == "The Dawn Vigil"
    )


def _guild_core(drawer: str = "Rites") -> str:
    return json.dumps(
        {
            "name": "The Lamp Guild",
            "summary": "Lamplighters of Kremova.",
            "aka": [],
            "timeline": [],
            "drawers": [{"type": "practices", "title": drawer}],
            "items": [
                {
                    "drawer": drawer,
                    "name": "The Dawn Vigil",
                    "text": "The guild keeps the old vigil.",
                    "kind": "lore",
                }
            ],
            "names": [],
        }
    )


async def test_core_links_an_ended_item_from_now(moscavia, world, full_dawn):
    """An item the White Dawn ended is a free stub again; a new sphere's
    core naming it links it, from now, so the dated end doesn't hide the
    link."""

    vigil = _vigil(world, moscavia.dawn)
    end_item(world, moscavia.dawn, vigil, WorldDate.of(1015), None)

    preview = await preview_sphere(
        world, "order", "the lamplighters", {}, None, reply=_guild_core()
    )
    (item,) = [i for i in preview.items if i["name"] == "The Dawn Vigil"]
    assert item["thing_id"] == vigil.thing_id
    guild = accept_sphere(world, preview)

    view = world.view()
    assert view.thing(vigil.thing_id).fields["part_of"]["sphere"] == guild
    assert view.field_since(vigil.thing_id, "part_of") == WorldDate.of(1020)
    assert vigil.thing_id in {i.thing_id for i in spheres.items(view, guild)}
    # its time out of any sphere stays told
    between = world.view(WorldDate.of(1017))
    assert between.thing(vigil.thing_id).fields.get("part_of") is None


async def test_adoption_files_after_a_dated_link(moscavia, world, full_dawn):
    """An entry part of a stub through a dated link (filed again after an
    end) is adopted into its drawer from now, not behind that link."""

    vigil = _vigil(world, moscavia.dawn)
    end_item(world, moscavia.dawn, vigil, WorldDate.of(1015), None)
    with world.revision(Source.manual(note="guild")) as rev:
        guild = rev.create_thing(
            "sphere",
            {"name": "The Lamp Guild", "template": "order", "stub": {"ignored": False}},
        )
        rev.set_field(
            vigil.thing_id,
            "part_of",
            {"sphere": guild, "drawer": UNSORTED_DRAWER_ID},
            WorldDate.of(1018),
        )

    preview = await preview_sphere(
        world, "order", "", {}, None, stub_id=guild, reply=_guild_core()
    )
    rites = _drawer_ids(preview)["Rites"]
    assert preview.adopted == [{"thing_id": vigil.thing_id, "drawer_id": rites}]
    accept_sphere(world, preview)

    view = world.view()
    assert view.thing(vigil.thing_id).fields["part_of"] == {
        "sphere": guild,
        "drawer": rites,
    }
    assert view.field_since(vigil.thing_id, "part_of") == WorldDate.of(1020)


async def test_accept_preview_files_an_ended_stub_from_now(moscavia, world, full_dawn):
    """Expanding an ended item stub with a child-first `part_of` files it
    from now: the dated end doesn't hide it."""

    rites = full_dawn
    vigil = _vigil(world, moscavia.dawn)
    end_item(world, moscavia.dawn, vigil, WorldDate.of(1015), None)
    preview = CreatePreview(
        kind="lore",
        prompt="the vigil",
        name="The Dawn Vigil",
        facts=[PreviewFact(category="general", text="A vigil kept again.")],
        prose={},
        stub_id=vigil.thing_id,
        part_of={"sphere": moscavia.dawn, "drawer": rites},
    )
    accept_preview(world, preview)

    view = world.view()
    assert view.thing(vigil.thing_id).fields["part_of"] == {
        "sphere": moscavia.dawn,
        "drawer": rites,
    }
    assert view.field_since(vigil.thing_id, "part_of") == WorldDate.of(1020)
    assert vigil.thing_id in {
        i.thing_id for i in spheres.items(view, moscavia.dawn) if i.drawer_id == rites
    }


# --- the summary (ruling P21) ------------------------------------------------


DAWN_SUMMARY_WORDS = "the state church of the Tsardom of Moscavia"


def _summary_facts(world, sphere_id):
    view = world.view()
    return [
        view.render(f.text)
        for f in view.thing(sphere_id).facts
        if spheres.is_summary_fact(f)
    ]


async def test_core_summary_is_a_summary_fact(moscavia, world):
    """The core's summary is written as the sphere's `about` fact marked
    `summary`, and still cached as its description."""

    preview, _ = await _dawn_preview(world, moscavia.dawn)
    accept_sphere(world, preview)

    assert _summary_facts(world, moscavia.dawn) == [preview.prose["description"]]
    assert spheres.summary(world.view(), moscavia.dawn) == preview.prose["description"]
    cached = world.prose().get(moscavia.dawn, "description", None)
    assert cached.text == preview.prose["description"]
    assert not world.prose().stale(
        moscavia.dawn,
        "description",
        None,
        (),
        prose_gen.unread_categories("sphere", "description"),
    )


async def _regenerated_prompt(world, sphere_id) -> str:
    client = MockClient("test")
    async with MockClientContext():
        _queue("The White Dawn is a faith whose priests wear white.")
        await prose_gen.generate_section(world, sphere_id, "description", None, client)
    return str(client.prompt_history[0]["prompt"])


async def test_summary_survives_an_about_fact(moscavia, world):
    """Ruling P21: an about fact added after the core is written into the
    description after the summary, never in its place."""

    preview, _ = await _dawn_preview(world, moscavia.dawn)
    accept_sphere(world, preview)
    with world.revision(Source.manual(note="about")) as rev:
        rev.add_fact(moscavia.dawn, "about", "Its priests wear white.")

    prompt = await _regenerated_prompt(world, moscavia.dawn)
    assert DAWN_SUMMARY_WORDS in prompt
    assert prompt.index(DAWN_SUMMARY_WORDS) < prompt.index("Its priests wear white.")
    assert _summary_facts(world, moscavia.dawn) == [preview.prose["description"]]


async def test_summary_survives_toggling_agent(moscavia, world):
    """The agent flag is no input to prose: toggling it leaves the
    summary fresh, and a regeneration still writes from the summary."""

    preview, _ = await _dawn_preview(world, moscavia.dawn)
    accept_sphere(world, preview)
    with world.revision(Source.manual(note="agent")) as rev:
        rev.set_field(moscavia.dawn, "agent", False, None)

    assert not world.prose().stale(
        moscavia.dawn,
        "description",
        None,
        (),
        prose_gen.unread_categories("sphere", "description"),
    )
    prompt = await _regenerated_prompt(world, moscavia.dawn)
    assert DAWN_SUMMARY_WORDS in prompt
    assert _summary_facts(world, moscavia.dawn) == [preview.prose["description"]]


async def test_summary_survives_ending_a_statement(moscavia, world, full_dawn):
    """ "End this..." on a statement notes the ending as an about fact: the
    summary is regenerated with it, and kept."""

    view = world.view()
    statement = next(
        i
        for i in spheres.items(view, moscavia.dawn)
        if i.thing_id is None and i.text.startswith("On each anniversary")
    )
    end_item(world, moscavia.dawn, statement, WorldDate.of(1018), None)

    prompt = await _regenerated_prompt(world, moscavia.dawn)
    assert DAWN_SUMMARY_WORDS in prompt
    assert "Ended in 1018" in prompt
    assert prompt.index(DAWN_SUMMARY_WORDS) < prompt.index("Ended in 1018")
    assert [
        DAWN_SUMMARY_WORDS in text for text in _summary_facts(world, moscavia.dawn)
    ] == [True]


async def test_ties_block_carries_a_core_made_summary(moscavia, world):
    """A sphere made by the core has no about fact but its summary: the
    character prompt's spheres block carries that summary line."""

    preview, _ = await _dawn_preview(world, moscavia.dawn)
    accept_sphere(world, preview)
    view = world.view()

    (block,), _labels = spheres_block(view, [moscavia.dawn])
    assert block[1] == preview.prose["description"]

    client = MockClient("test")
    async with MockClientContext():
        reply = {
            "name": "Vasha",
            "facts": [{"category": "background", "text": "Carries letters."}],
            "names": [],
        }
        _queue(json.dumps(reply), "Vasha.", "Dry.")
        await preview_thing(
            world,
            "character",
            "Vasha, a courier of the White Dawn",
            {},
            client,
            picks={"White Dawn": moscavia.dawn},
        )
        # the queue is shared by the process's tests: nothing left over
        client_responses.get().clear()
    assert preview.prose["description"] in str(client.prompt_history[0]["prompt"])


# --- filing (P23, minors 5 and 6) ---------------------------------------------


async def test_religion_has_a_branches_drawer(moscavia, world):
    """Ruling P23: a religion made by the core has a Branches drawer, which
    the core is never asked to fill; a place sphere gets none."""

    preview, client = await _dawn_preview(world, moscavia.dawn)
    assert [(d["type"], d["title"]) for d in preview.drawers][-1] == (
        "branches",
        "Branches",
    )
    prompt = str(client.prompt_history[0]["prompt"])
    # never offered to the reply as a drawer to write
    assert "- branches:" not in prompt
    accept_sphere(world, preview)
    shelves = spheres.drawers(world.view(), moscavia.dawn)
    assert [d.type for d in shelves].count("branches") == 1

    client = MockClient("test")
    async with MockClientContext():
        _queue(CORE_NATION)
        promoted = await preview_sphere(
            world, "religion", "", {}, client, promote_id=moscavia.kremova
        )
    assert promoted.kind == "place"
    assert "branches" not in [d["type"] for d in promoted.drawers]


@pytest.mark.parametrize("kind", ["lore", "sphere"])
async def test_adopted_council_not_relisted_lands_in_hierarchy(moscavia, world, kind):
    """A council made first (lore, or an order sphere stub) and adopted by
    a core reply that doesn't relist it is filed by a guess: Hierarchy,
    the first structure drawer -- not Unsorted."""

    fields = {
        "name": "Council of Elders",
        "part_of": {"sphere": moscavia.dawn, "drawer": UNSORTED_DRAWER_ID},
    }
    if kind == "sphere":
        fields.update(template="order", stub={"ignored": False})
    with world.revision(Source.manual(note="council")) as rev:
        council = rev.create_thing(kind, fields)
        if kind == "lore":
            rev.add_fact(council, "general", "Seven elders.")

    preview, _ = await _dawn_preview(world, moscavia.dawn)
    assert "Council of Elders" not in CORE_RELIGION
    ids = _drawer_ids(preview)
    assert preview.adopted == [{"thing_id": council, "drawer_id": ids["Hierarchy"]}]

    accept_sphere(world, preview)
    assert world.view().thing(council).fields["part_of"] == {
        "sphere": moscavia.dawn,
        "drawer": ids["Hierarchy"],
    }


async def test_items_go_in_drawers_they_may(moscavia, world):
    """Creation files items as `set_part_of` would: a place listed under
    Rites goes to Holy Sites, lore under Holy Sites to Unsorted, a
    statement under People to Unsorted -- in the preview and when
    written."""

    core = json.loads(CORE_AFTER_COUNCIL)
    core["items"] = [
        {
            "drawer": "Rites and Ceremonies",
            "name": "Amber Grove",
            "text": "A grove.",
            "kind": "place",
        },
        {
            "drawer": "Holy Sites",
            "name": "The Quiet Rule",
            "text": "Be quiet.",
            "kind": "lore",
        },
        {"drawer": "People", "name": "", "text": "Everyone prays."},
        {"drawer": "Doctrines", "name": "", "text": "Light is pure."},
    ]
    core["names"] = []
    preview, _ = await _dawn_preview(world, moscavia.dawn, json.dumps(core))
    ids = _drawer_ids(preview)
    by_text = {item["text"]: item["drawer_id"] for item in preview.items}
    assert by_text == {
        "A grove.": ids["Holy Sites"],
        "Be quiet.": UNSORTED_DRAWER_ID,
        "Everyone prays.": UNSORTED_DRAWER_ID,
        "Light is pure.": ids["Doctrines"],
    }

    # an owner's preview naming a drawer an entry can't go in is filed
    # right on accept too
    preview.items[0]["drawer_id"] = ids["Rites and Ceremonies"]
    accept_sphere(world, preview)
    view = world.view()
    found = {i.name: i.drawer_id for i in spheres.items(view, moscavia.dawn)}
    assert found["Amber Grove"] == ids["Holy Sites"]
    assert found["The Quiet Rule"] == UNSORTED_DRAWER_ID
    assert found["Everyone prays."] == UNSORTED_DRAWER_ID


def test_written_types_are_the_ones_the_core_writes():
    """The core's and Fill's drawer types (with the probe's glosses) are
    the one set `kinds.WRITTEN_DRAWER_TYPES` names."""

    from talemate.world.kinds import WRITTEN_DRAWER_TYPES
    from talemate.worldplay.spheres import TYPE_HELP

    assert tuple(TYPE_HELP) == WRITTEN_DRAWER_TYPES
