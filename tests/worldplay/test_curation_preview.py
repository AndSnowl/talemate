"""Curation in previews (Task 5): the create and Fill replies' "elsewhere"
list -- facts about other entries, offered as additions to them and
written on accept -- and repeats, facts the world already holds, flagged
with their match.

The MockClient replies are raw Skyfall output from the curation probe
(docs/superpowers/probes/raw/2026-10-22-curation.json, probe 1), copied
verbatim; the worlds are small copies of the probe's."""

import json
from typing import NamedTuple

import pytest

from talemate.world import spheres
from talemate.world.curation import CurationSettings
from talemate.world.dates import WorldDate
from talemate.world.kinds import KINDS, get_kind
from talemate.world.refs import parse_refs, ref
from talemate.world.store import Source
from talemate.worldplay import prose_gen
from talemate.worldplay.create import (
    ElsewhereFact,
    accept_preview,
    default_category,
    preview_thing,
)
from talemate.worldplay.spheres import (
    SUMMARY_ORIGIN,
    FillPreview,
    accept_fill,
    fill_drawer,
)

from conftest import MockClient, MockClientContext, client_responses


def _queue(*responses: str) -> None:
    for response in responses:
        client_responses.get().append(response)


# create, Divine Right, r1 run 0
CREATE_DIVINE_RIGHT = '{ "name": "The Divine Right of the Tsar", "aka": [{"name": "Divine Right", "tag": "common", "everyday": true}], "facts": [{"category": "general", "text": "The Tsar of Moscavia rules by the grace of the Eternal Light, serving as the earthly steward of the Tsardom.", "since": null, "held_by": null}, {"category": "general", "text": "The Church of the Eternal Light bestows divine legitimacy upon the Tsar, asserting that the Eternal Light chose the ruling dynasty to govern Moscavia.", "held_by": "Church of the Eternal Light"}, {"category": "general", "text": "The doctrine holds that the Tsar\'s authority is not merely political but sacred, rooted in a covenant between the ruling house and the Eternal Light itself.", "held_by": "Church of the Eternal Light"}, {"category": "general", "text": "This divine right was established alongside the founding of the Tsardom in the early centuries before the current reckoning.", "since": null, "held_by": null}, {"category": "general", "text": "The Blinding Transformation of 994 did not diminish the Tsar\'s divine mandate; the Church reinterpreted the event as the Eternal Light\'s ultimate revelation, confirming the Tsar\'s holy stewardship over the Owl-folk.", "since": 994, "held_by": "Church of the Eternal Light"}, {"category": "general", "text": "The Tsar presides over the Tsardom from a throne scaled to accommodate the wingspans of the Owl-folk, a physical symbol of governance adapted to the transformed realm.", "since": null, "held_by": null}, {"category": "general", "text": "The Zakonnik, the Tsardom\'s legal code revised after the Transformation, operates under the overarching framework of the Tsar\'s divine authority.", "since": null, "held_by": null}, {"category": "general", "text": "The Church\'s hierarchy, from parish priests to the highest clergy, serves to reinforce the divine right doctrine through sermon, sacrament, and canonical teaching.", "held_by": "Church of the Eternal Light"}, {"category": "general", "text": "Baptism by candlelight, the rite of passage for young Owl-folk entering the Church, includes prayers for the Tsar\'s long reign and the prosperity of the realm.", "held_by": "Church of the Eternal Light"}, {"category": "general", "text": "The Tsar\'s military—regiments such as the White Talon and the Frosted Wing—defends the realm in the name of the Eternal Light and the divine right of the crown.", "since": null, "held_by": null}, {"category": "general", "text": "Diplomatic envoys from neighboring kingdoms are received by the Tsar with full ceremony, and the divine right doctrine is presented as the foundation of Moscavia\'s sovereignty in all foreign affairs.", "since": null, "held_by": null}], "names": [{"name": "Tsar", "kind": "lore", "aka": []}, {"name": "Tsardom of Moscavia", "kind": "place", "aka": [{"name": "Moscavia", "tag": "common", "everyday": true}]}, {"name": "Church of the Eternal Light", "kind": "sphere", "aka": [{"name": "The Church", "tag": "common", "everyday": true}], "template": "religion"}, {"name": "Eternal Light", "kind": "lore", "aka": []}, {"name": "Zakonnik", "kind": "item", "aka": []}, {"name": "White Talon", "kind": "lore", "aka": []}, {"name": "Frosted Wing", "kind": "lore", "aka": []}, {"name": "Moskov", "kind": "place", "aka": []}, {"name": "Volga", "kind": "place", "aka": []}, {"name": "Moskva", "kind": "place", "aka": []}, {"name": "Owl-folk", "kind": "species", "aka": []}, {"name": "Snowy Owl-folk", "kind": "species", "aka": []}, {"name": "Valdmark", "kind": "place", "aka": []}, {"name": "Keshra", "kind": "place", "aka": []}, {"name": "Free Cities of the Southern Reach", "kind": "place", "aka": []}, {"name": "Eared Owl-folk", "kind": "species", "aka": []}, {"name": "Great Synod of Moskov", "kind": "event", "aka": []}, {"name": "Blinding Transformation", "kind": "event", "aka": []}], "elsewhere": [{"entry": "Tsardom of Moscavia", "text": "The Tsardom of Moscavia, governed under the Divine Right doctrine, maintains its sovereignty through a centralized monarchy blessed by the Church of the Eternal Light.", "held_by": null}, {"entry": "Church of the Eternal Light", "text": "The Church of the Eternal Light interprets the Blinding Transformation of 994 as divine confirmation of the Tsar\'s sacred authority, weaving the event into the theological foundation of the state.", "held_by": null}, {"entry": "Tsar", "text": "The Tsar is both the political and spiritual head of Moscavia, reigning as steward of the realm by the grace and blessing of the Eternal Light.", "held_by": null}], "part_of": {"entry": "Church of the Eternal Light", "drawer": "Doctrines"} }'

# create, Divine Right, r1 run 1 (its elsewhere items are added to run 0's for grouping)
CREATE_DIVINE_RIGHT_2 = '{ "name": "The Divine Right of the Tsar", "aka": [{"name": "Divine Right of the Tsar", "tag": "common", "everyday": true}], "facts": [{"category": "general", "text": "The Tsar of Moscavia rules by divine right, his authority derived from the blessing of the Eternal Light and administered through the Church of the Eternal Light.", "since": "early centuries before 994", "held_by": null}, {"category": "general", "text": "The Church of the Eternal Light interprets the Blinding Transformation of 994 as proof that the Eternal Light has chosen the Tsardom of Moscavia as its earthly stewardship, and that the Tsar\'s rule is therefore sanctified by holy decree.", "since": "994", "held_by": "Church of the Eternal Light"}, {"category": "general", "text": "The Divine Right of the Tsar is not merely political authority but a theological mandate: the Church teaches that to resist the Tsar is to resist the Light itself, and that obedience to the Tsar\'s law is an act of worship.", "since": "994", "held_by": "Church of the Eternal Light"}, {"category": "general", "text": "The first Tsar of Moscavia, who also founded the Church of the Eternal Light, established the precedent that the Tsar\'s right to rule is confirmed at coronation through a ritual blessing performed by the Patriarch of the Church, known as the Illumination Rite.", "since": "early centuries before 994", "held_by": null}, {"category": "general", "text": "The Illumination Rite involves the anointing of the Tsar with consecrated oil and the placement of a crown upon his head beneath the light of a thousand candles, symbolizing the Eternal Light\'s descent upon the monarch.", "since": "early centuries before 994", "held_by": "Church of the Eternal Light"}, {"category": "general", "text": "In practice, the Divine Right of the Tsar functions as the constitutional foundation of Moscavian governance: no law passed by the Duma (the Tsardom\'s advisory council) can supersede the Tsar\'s decree, and the Tsar alone may declare war or make peace.", "since": "early centuries before 994", "held_by": null}, {"category": "general", "text": "The Church maintains that the Tsar\'s power is limited only by his duty to govern justly in accordance with the Light; a tyrannical Tsar who rules without regard for the Church\'s moral teachings may be subject to ecclesiastical censure, though the Church has never attempted to depose a sitting Tsar.", "since": "994", "held_by": "Church of the Eternal Light"}, {"category": "general", "text": "The Divine Right doctrine was reaffirmed following the Blinding Transformation of 994, when the newly transformed Owl-folk leadership convened the Second Synod of Moskov to clarify that the transformation did not alter the covenant between the Eternal Light, the Tsar, and the people.", "since": "997", "held_by": null}, {"category": "general", "text": "The Zakonnik, the Tsardom\'s legal code, codifies the Divine Right of the Tsar in its opening articles, declaring that \'the authority of the Tsar flows from the Eternal Light and is bounded only by the Light\'s commandments as interpreted by the Holy Church.\'", "since": "997", "held_by": null}, {"category": "general", "text": "The Divine Right of the Tsar is taught to young Owl-folk from the moment of their Baptism by Candlelight, and reinforced throughout their education in parish schools and the Church\'s seminaries.", "since": "997", "held_by": "Church of the Eternal Light"}, {"category": "general", "text": "No Tsar or Tsarina has ever voluntarily abdicated the throne in Moscavia\'s history; the Divine Right doctrine holds that to relinquish the stewardship is to reject the Light\'s calling, an act considered both politically treasonous and spiritually damning.", "since": "early centuries before 994", "held_by": "Church of the Eternal Light"}], "names": [{"name": "Moscavia", "kind": "place", "aka": [], "part_of": null}, {"name": "Tsardom of Moscavia", "kind": "place", "aka": [{"name": "Moscavia", "tag": "common", "everyday": true}], "part_of": null}, {"name": "Church of the Eternal Light", "kind": "sphere", "aka": [{"name": "The Church", "tag": "common", "everyday": true}], "part_of": null, "template": "religion"}, {"name": "Eternal Light", "kind": "sphere", "aka": [], "part_of": null, "template": "religion"}, {"name": "Tsar", "kind": "lore", "aka": []}, {"name": "Tsarina", "kind": "lore", "aka": []}, {"name": "Blinding Transformation", "kind": "event", "aka": []}, {"name": "Duma", "kind": "item", "aka": []}, {"name": "Illumination Rite", "kind": "rite", "aka": []}, {"name": "Patriarch", "kind": "lore", "aka": []}, {"name": "Second Synod of Moskov", "kind": "event", "aka": []}, {"name": "Zakonnik", "kind": "item", "aka": []}, {"name": "Valdmark", "kind": "place", "aka": []}, {"name": "Keshra", "kind": "place", "aka": []}, {"name": "Free Cities of the Southern Reach", "kind": "place", "aka": []}, {"name": "Moskov", "kind": "place", "aka": []}, {"name": "Volga River", "kind": "place", "aka": []}, {"name": "Moskva River", "kind": "place", "aka": []}], "elsewhere": [{"entry": "Church of the Eternal Light", "text": "The Church of the Eternal Light maintains that the Divine Right of the Tsar is the cornerstone of Moscavian theology, and that the Tsar serves as the Eternal Light\'s visible representative on earth—a \'lamp among lamps\' who illuminates the path for all Owl-folk.", "held_by": "Church of the Eternal Light"}, {"entry": "Tsardom of Moscavia", "text": "The Tsardom of Moscavia is governed under the principle that the Tsar\'s authority is both absolute and sacred, with no appeal beyond the Tsar\'s judgment save the Church\'s moral counsel.", "held_by": null}], "part_of": {"entry": "Church of the Eternal Light", "drawer": "Doctrines"} }'

# create v3, Divine Right, r2 run 1: cut off at 2049 tokens inside its elsewhere list
CREATE_CUT_OFF = '{ "name": "The Divine Right of the Tsar",  "aka": [],  "facts": [    {      "category": "general",      "text": "The Tsar of Moscavia rules as the earthly steward of the Eternal Light, his authority derived not from the consent of the governed but from a direct divine blessing bestowed by the Church of the Eternal Light.",      "since": null      },    {      "category": "general",      "text": "This doctrine holds that the Eternal Light, as the supreme creator and sustainer of all things, chose the house of Moscavia to govern its people and that this choice is irrevocable so long as the ruling dynasty remains faithful to the Light.",      "since": null      },    {      "category": "general",      "text": "The foundation of the doctrine rests on the original covenant established when the first Tsar of Moscavia declared the Eternal Light the patron deity of the realm in the early centuries before the current reckoning.",      "since": null      },    {      "category": "general",      "text": "The Church of the Eternal Light serves as the intermediary between the Tsar and the divine, confirming each successor\'s right to rule through ritual anointing and the blessing of the Patriarch.",      "since": null      },    {      "category": "general",      "text": "The Blinding Transformation of 994, which converted every person of Moscavian bloodline into an Owl-folk, was interpreted by the Church as the Eternal Light\'s ultimate validation of the Tsar\'s holy mandate, raising the entire nation to a higher state of being.",      "since": 994      },    {      "category": "general",      "text": "Under the doctrine, the Tsar\'s authority extends over all matters temporal and spiritual within the borders of Moscavia, including the administration of the Zakonnik, the regulation of roosting rights, and the oversight of nighttime commerce.",      "since": null      },    {      "category": "general",      "text": "The Tsar is considered answerable only to the Eternal Light itself and not to any earthly council, parliament, or assembly, though the Synod of Lanterns may advise on matters of doctrine that touch upon governance.",      "since": null      },    {      "category": "general",      "text": "Pure-line Moscavians—the snowy Owl-folk whose bloodline is unbroken for four generations—are considered the most faithful vessels of the Tsar\'s authority, their white plumage a visible sign of their close alignment with the divine Light.",      "since": 994      },    {      "category": "general",      "text": "The doctrine has been instrumental in maintaining the unity of Moscavia through periods of external threat, as neighboring realms like Valdmark and Keshra have found it difficult to challenge a ruler who claims to act under direct divine mandate.",      "since": null      },    {      "category": "general",      "text": "Critics and foreign diplomats have sometimes dismissed the Divine Right of the Tsar as a convenient fiction, but within Moscavia it is treated as an article of unquestionable faith, woven into every aspect of daily life from the candlelit baptisms of owlets to the grand processions through the streets of Moskov.",      "since": null      }  ],  "names": [    {      "name": "Tsar",      "kind": "lore",      "aka": [],      "part_of": {        "entry": "The Divine Right of the Tsar",        "drawer": null      }    },    {      "name": "Tsardom of Moscavia",      "kind": "place",      "aka": [        {          "name": "Moscavia",          "tag": "common",          "everyday": true        }      ]    },    {      "name": "Church of the Eternal Light",      "kind": "sphere",      "aka": [        {          "name": "The Church",          "tag": "common",          "everyday": true        }      ],      "template": "religion"    },    {      "name": "Eternal Light",      "kind": "lore",      "aka": [],      "part_of": {        "entry": "Church of the Eternal Light",        "drawer": "Doctrines"      }    },    {      "name": "Patriarch of Moscavia",      "kind": "lore",      "aka": [],      "part_of": {        "entry": "Church of the Eternal Light",        "drawer": "Hierarchy"      }    },    {      "name": "Synod of Lanterns",      "kind": "lore",      "aka": [],      "part_of": {        "entry": "Church of the Eternal Light",        "drawer": "Hierarchy"      }    },    {      "name": "Moskov",      "kind": "place",      "aka": [],      "part_of": {        "entry": "Tsardom of Moscavia",        "drawer": null      }    },    {      "name": "Volga River",      "kind": "place",      "aka": []    },    {      "name": "Moskva River",      "kind": "place",      "aka": []    },    {      "name": "Zakonnik",      "kind": "lore",      "aka": [],      "part_of": {        "entry": "Tsardom of Moscavia",        "drawer": null      }    },    {      "name": "Pure-line Moscavian",      "kind": "lore",      "aka": [],      "part_of": {        "entry": "Moscavian Owl-folk",        "drawer": null      }    },    {      "name": "Snowy Owl-folk",      "kind": "species",      "aka": [],      "part_of": {        "entry": "Moscavian Owl-folk",        "drawer": null      }    },    {      "name": "Valdmark",      "kind": "place",      "aka": []    },    {      "name": "Keshra",      "kind": "place",      "aka": []    },    {      "name": "Free Cities of the Southern Reach",      "kind": "place",      "aka": []    },    {      "name": "Owl-folk",      "kind": "species",      "aka": [],      "part_of": {        "entry": "Moscavian Owl-folk",        "drawer": null      }    }  ],  "elsewhere": [    {      "entry": "Church of the Eternal Light",      "text": "The Church of the Eternal Light formalized the Divine Right of the Tsar as a core doctrine during the Great Synod of Moskov, establishing that the Tsar\'s authority is divinely ordained and that the Church itself serves as the conduit of that divine will.",      "held_by": null    },    {      "entry": "The Illumination",      "text": "The Illumination of 994 is regarded by the Church as the Eternal Light\'s greatest act, and it is taught that the Owl-folk transformation was not a punishment but a blessed ascension—a raising up of the Moscavian people to better perceive the Light.",      "held_by": "Church of the Eternal Light"    },    {      "entry": "The Patriarch of Moscavia",      "text": "The Patriarch is appointed by the Tsar from among the senior clergy of the Church and serves as the chief ecclesiastical authority in matters pertaining to the Divine Right, including the coronation rites and the periodic reaffirmation of the Tsar\'s mandate.",      "held_by": null    },    {      "entry": "The Synod of Lanterns",      "text": "The Synod of Lanterns, composed of twelve senior bishops, has the authority to interpret how the Divine Right applies to specific governance questions, though its rulings are advisory rather than binding on the Tsar himself.",      "held_by": null    },    {      "entry": "Moscavian Owl-folk",      "text": "The transformation of 994 did not diminish the Tsardom but rather reaffirmed the Divine Right, as the Church taught that the Owl-folk form was the Eternal Light\'s chosen vessel for its stewards and subjects alike.",      "held_by": "Church of the Eternal Light"    },    {      "entry": "Moskov",      "text": "Moskov, the capital of Moscavia, serves as the seat of the Tsar\'s palace and the Cathedral of the Eternal Light, both of which have been redesigned with wider doorways, taller ceilings, and roosting platforms to accommodate the Owl-folk who now inhabit them.",      "held_by": null    },    {      "entry": "The Dawn Vigil",      "text": "The Dawn Vigil, held at first light in the cathedral chapels of every parish, includes prayers specifically devoted to the Eternal Light\'s continued blessing upon the Tsar and the Tsardom.",      "held_by": null    },    {      "entry": "The Festival of'

# Fill, the Church's Hierarchy, r1 run 0
FILL_HIERARCHY = '{ "new_items": [    {"name": "The Diaconate", "text": "Deacons assist parish priests in liturgical duties and tend to the material needs of church properties.", "kind": "lore"},    {"name": "Provincial Archbishops", "text": "Archbishops oversee clusters of parishes within each of Moscavia\'s five administrative regions, bridging local and national Church governance.", "kind": "lore"},    {"name": "The Order of the Radiant Eye", "text": "An elite clerical order dedicated to scholarly study and the preservation of canonical texts, stationed at the Cathedral of the Eternal Light.", "kind": "lore"},    {"text": "Clergy candidates undergo a minimum of seven years of training, beginning with novitiate service and culminating in examination before the Synod of Lanterns."}  ],  "names": [    {"name": "The Diaconate", "kind": "order", "aka": []},    {"name": "Provincial Archbishops", "kind": "office", "aka": []},    {"name": "The Order of the Radiant Eye", "kind": "order", "aka": []}  ],  "elsewhere": [    {"entry": "The Patriarch of Moscavia", "text": "The Patriarch serves as the spiritual head of the Church and the senior member of the Synod of Lanterns by right of office.", "held_by": null},    {"entry": "The Synod of Lanterns", "text": "The Synod convenes at least twice annually in Moskov, with extraordinary sessions called by the Patriarch or Tsar as needed.", "held_by": null},    {"entry": "The Shrine of First Dawn", "text": "Pilgrimages to the Shrine of First Dawn are considered especially meritorious during the weeks leading up to the Festival of the Solstice Flame.", "held_by": "Church of the Eternal Light"}  ]}'

# Fill, Runeweaving's Sites, r2 run 1
FILL_SITES = '{ "new_items": [ { "name": "The Pale Root", "text": "A root system beneath Ashenmere that glows faintly and hums at a low frequency, believed to have been shaped by ancient cave-inscribers into a living rune lattice.", "kind": "place" }, { "name": "Keth\'s Workshop", "text": "A small stone building in Stonehold\'s outer ward where Master Weaver Keth of Ashenmere conducts private research into the third resonance law.", "kind": "place" }, { "name": "The Shattered Index", "text": "A fragmentary manuscript surviving from the Greyholm Archive, containing cross-referenced entries on rune combinations that no longer correspond to any known text.", "kind": "item" }, { "text": "The Conclave maintains a quarantine ward in Stonehold for materials that have absorbed corrupted runes, preventing their contamination of other inscriptions." } ], "names": [ { "name": "The Pale Root", "kind": "place", "aka": [] }, { "name": "Keth\'s Workshop", "kind": "place", "aka": [] }, { "name": "The Shattered Index", "kind": "item", "aka": [] }, { "name": "Master Weaver Keth", "kind": "character", "aka": [] } ], "elsewhere": [ { "entry": "The Ashenmere Caves", "text": "The Pale Root extends for at least two miles beneath the northern chambers of Ashenmere, and weavers believe it may connect to chambers that have never been mapped.", "held_by": null }, { "entry": "Stonehold", "text": "Keth\'s Workshop sits adjacent to the outer wall of Stonehold\'s inner citadel, accessible only through a rune-locked gate.", "held_by": null }, { "entry": "The Greyholm Archive", "text": "The Shattered Index is one of only three known documents that can be definitively traced to the Greyholm Archive\'s original collection.", "held_by": null }, { "entry": "Ashenmere rune dialect", "text": "Keth of Ashenmere is the foremost living scholar of the Ashenmere dialect and has published three treatises arguing that the third resonance law is not a contradiction of Aelberth but an expansion.", "held_by": null } ] }'


# --- the world ---------------------------------------------------------------

DOCTRINES, RITES, SITES, HIERARCHY = "d0c70001", "a17e0001", "5173e001", "41e7a001"

# the Divine Right reply's sixth fact, word for word, already on the Tsardom
THRONE = (
    "The Tsar presides over the Tsardom from a throne scaled to accommodate the "
    "wingspans of the Owl-folk, a physical symbol of governance adapted to the "
    "transformed realm."
)
# half of the reply's Zakonnik fact: a repeat, but no copy
ZAKONNIK = "The Zakonnik is the Tsardom's legal code, revised after the Transformation."
# the Hierarchy reply's statement, word for word, on Moskov
TRAINING = (
    "Clergy candidates undergo a minimum of seven years of training, beginning "
    "with novitiate service and culminating in examination before the Synod of "
    "Lanterns."
)


class Eternal(NamedTuple):
    church: str
    tsardom: str
    moskov: str
    divine: str
    patriarch: str
    shrine: str
    guild: str
    throne: str
    zakonnik: str


@pytest.fixture
def eternal(world):
    """The probe's world, small, present year 1000: the Church of the
    Eternal Light (a religion sphere, everyday "The Church") with its
    four drawers; the Tsardom of Moscavia, whose law names the Divine
    Right; Moskov, its capital, named in the Church's summary; the Divine
    Right of the Tsar, a lore stub in the Church's Doctrines; the
    Patriarch and the Shrine of First Dawn, stubs in the Hierarchy and
    Holy Sites; and the Iron Guild, linked to nothing."""

    world.set_present(WorldDate.of(1000))
    with world.revision(Source.manual(note="eternal")) as rev:
        church = rev.create_thing(
            "sphere",
            {
                "name": "Church of the Eternal Light",
                "template": "religion",
                "aka": [{"name": "The Church", "tag": "common", "everyday": True}],
                "drawers": [
                    {"id": DOCTRINES, "type": "beliefs", "title": "Doctrines"},
                    {"id": RITES, "type": "practices", "title": "Rites and Ceremonies"},
                    {"id": SITES, "type": "places", "title": "Holy Sites"},
                    {"id": HIERARCHY, "type": "structure", "title": "Hierarchy"},
                ],
            },
        )
        tsardom = rev.create_thing(
            "place",
            {
                "name": "Tsardom of Moscavia",
                "kind": "country",
                "aka": [{"name": "Moscavia", "tag": "common", "everyday": True}],
            },
        )
        moskov = rev.create_thing(
            "place", {"name": "Moskov", "kind": "city", "parent": tsardom}
        )
        divine = rev.create_thing(
            "lore",
            {
                "name": "The Divine Right of the Tsar",
                "stub": {"ignored": False},
                "part_of": {"sphere": church, "drawer": DOCTRINES},
            },
        )
        patriarch = rev.create_thing(
            "lore",
            {
                "name": "The Patriarch of Moscavia",
                "stub": {"ignored": False},
                "part_of": {"sphere": church, "drawer": HIERARCHY},
            },
        )
        rev.add_fact(
            patriarch,
            "general",
            "The supreme head of the Church, appointed by the Tsar from among "
            "the senior clergy Owl-folk.",
        )
        shrine = rev.create_thing(
            "place",
            {
                "name": "The Shrine of First Dawn",
                "stub": {"ignored": False},
                "part_of": {"sphere": church, "drawer": SITES},
            },
        )
        guild = rev.create_thing("lore", {"name": "Iron Guild"})
        rev.add_fact(guild, "general", "The Iron Guild forges the Tsardom's bells.")
        rev.add_fact(
            church,
            "about",
            f"The Church of the Eternal Light is the state religion of "
            f"{ref(tsardom, 'the Tsardom of Moscavia')}, claiming divine right for "
            f"the Tsar and Tsarina; its cathedral stands in {ref(moskov, 'Moskov')}.",
            origin=SUMMARY_ORIGIN,
        )
        rev.add_fact(
            tsardom,
            "description",
            "The Tsardom of Moscavia is a vast northern kingdom stretching across "
            "rolling forests, frozen rivers, and rolling steppe.",
        )
        rev.add_fact(
            tsardom,
            "law",
            f"The Tsar rules by {ref(divine, 'the Divine Right of the Tsar')}.",
        )
        throne = rev.add_fact(tsardom, "history", THRONE)
        zakonnik = rev.add_fact(tsardom, "law", ZAKONNIK)
        rev.add_fact(moskov, "history", f"In Moskov, c{TRAINING[1:]}")
    return Eternal(
        church=church,
        tsardom=tsardom,
        moskov=moskov,
        divine=divine,
        patriarch=patriarch,
        shrine=shrine,
        guild=guild,
        throne=throne,
        zakonnik=zakonnik,
    )


def _grouped_reply() -> str:
    """Run 0's reply with run 1's two elsewhere items added at the end, so
    two entries each get two items, apart."""

    reply = json.loads(CREATE_DIVINE_RIGHT)
    reply["elsewhere"] += json.loads(CREATE_DIVINE_RIGHT_2)["elsewhere"]
    return json.dumps(reply)


async def _divine_preview(world, eternal, reply: str = CREATE_DIVINE_RIGHT):
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply)
        preview = await preview_thing(
            world,
            "lore",
            "The Divine Right of the Tsar: The Tsar rules by the grace of the "
            "Eternal Light, chosen to govern Moscavia as its earthly steward.",
            {},
            client,
            stub_id=eternal.divine,
        )
    return preview, client


def _named(view, name):
    return [t for t in view.things() if view.name_of(t.id) == name]


def _texts(view, thing_id):
    state = view.thing(thing_id)
    return [view.render(fact.text) for fact in state.facts] if state else []


# --- create ------------------------------------------------------------------


async def test_elsewhere_facts_parsed_and_grouped(world, eternal):
    preview, client = await _divine_preview(world, eternal, _grouped_reply())

    assert client.prompt_history[0]["kind"] == "creative_instruction_3072"
    prompt = str(client.prompt_history[0]["prompt"])
    assert '"elsewhere": [{"entry": "<an entry\'s name>"' in prompt
    assert "Entries near this one in the world:" in prompt

    # grouped by entry, in the order each entry first comes
    assert [e.target_name for e in preview.elsewhere] == [
        "Tsardom of Moscavia",
        "Tsardom of Moscavia",
        "Church of the Eternal Light",
        "Church of the Eternal Light",
        "Tsar",
    ]
    tsardom, _, church, church_held, tsar = preview.elsewhere
    assert isinstance(tsardom, ElsewhereFact)
    assert tsardom.target_id == eternal.tsardom and tsardom.new is None
    assert tsardom.category == "general"
    assert church.target_id == eternal.church and church.category == "about"
    # run 1's Church item names who holds it
    assert church_held.held_by == eternal.church
    assert church.held_by is None
    # the Tsar is no entry yet: a stub to make, its kind as "names" lists it
    assert tsar.target_id is None
    assert tsar.new is not None and (tsar.new.name, tsar.new.kind) == ("Tsar", "lore")
    assert tsar.category == "general"
    assert all(e.ticked for e in preview.elsewhere)
    # never read as the entry's own facts
    own = {fact.text for fact in preview.facts}
    assert not own & {e.text for e in preview.elsewhere}


async def test_cut_off_reply_keeps_complete_elsewhere_items(world, eternal):
    """The v3 run cut off at 2049 tokens inside its elsewhere list: every
    complete item is kept, the broken last one dropped, and none is read
    as a fact."""

    preview, _client = await _divine_preview(world, eternal, CREATE_CUT_OFF)
    assert preview.facts
    own = {fact.text for fact in preview.facts}
    assert not own & {e.text for e in preview.elsewhere}
    names = [e.target_name for e in preview.elsewhere]
    assert "Church of the Eternal Light" in names
    assert names[-1] == "The Dawn Vigil"
    assert "The Festival of" not in " ".join(names)


async def test_accept_writes_elsewhere_to_targets_one_revision(world, eternal):
    preview, _client = await _divine_preview(world, eternal, _grouped_reply())
    head = world.head_rev()

    thing_id = accept_preview(world, preview)

    assert thing_id == eternal.divine
    assert world.head_rev() == head + 1
    view = world.view()
    tsardom_items = [e for e in preview.elsewhere if e.target_id == eternal.tsardom]
    for item in tsardom_items:
        assert item.text in _texts(view, eternal.tsardom)
    church = view.thing(eternal.church)
    written = {view.render(f.text): f for f in church.facts}
    for item in preview.elsewhere:
        if item.target_id == eternal.church:
            assert written[item.text].category == "about"
            # not there before the accept's revision
            assert item.text not in _texts(world.view(rev=head), eternal.church)
    held = next(e for e in preview.elsewhere if e.held_by is not None)
    fact = written[held.text]
    assert spheres.held_by(view, fact, church) == eternal.church
    # the elsewhere text is linked like any fact: the Divine Right by name
    tsardom = view.thing(eternal.tsardom)
    linked = [f for f in tsardom.facts if view.render(f.text) == tsardom_items[0].text]
    assert eternal.church in parse_refs(linked[0].text)


async def test_elsewhere_new_target_makes_stub(world, eternal):
    preview, _client = await _divine_preview(world, eternal)
    accept_preview(world, preview)

    view = world.view()
    tsars = _named(view, "Tsar")
    # one stub, though the facts' names and the elsewhere list both make it
    assert len(tsars) == 1
    tsar = tsars[0]
    assert tsar.is_stub and tsar.kind == "lore"
    tsar_item = next(e for e in preview.elsewhere if e.new is not None)
    assert [f.category for f in tsar.facts] == ["general"]
    assert view.render(tsar.facts[0].text) == tsar_item.text


async def test_repeat_starts_unticked_and_is_not_written(world, eternal):
    preview, _client = await _divine_preview(world, eternal)
    by_text = {fact.text: fact for fact in preview.facts}
    throne = next(f for f in preview.facts if f.text.startswith("The Tsar presides"))
    # a copy: shown with its match, unticked
    assert throne.repeat_of is not None
    assert throne.repeat_of["fact_id"] == eternal.throne
    assert throne.repeat_of["owner_id"] == eternal.tsardom
    assert throne.repeat_of["owner_name"] == "Tsardom of Moscavia"
    assert throne.repeat_of["text"] == THRONE
    assert throne.repeat_of["score"] >= 0.7
    assert throne.ticked is False
    # a repeat under the untick threshold is shown, and stays ticked
    zakonnik = next(f for f in preview.facts if f.text.startswith("The Zakonnik"))
    assert zakonnik.repeat_of is not None
    assert zakonnik.repeat_of["fact_id"] == eternal.zakonnik
    assert 0.4 <= zakonnik.repeat_of["score"] < 0.7
    assert zakonnik.ticked is True
    assert len(by_text) == len(preview.facts)

    accept_preview(world, preview)
    view = world.view()
    texts = _texts(view, eternal.divine)
    assert throne.text not in texts
    assert zakonnik.text in texts
    # the copy it repeats stays where it was, once
    assert _texts(view, eternal.tsardom).count(THRONE) == 1


async def test_ticked_repeat_is_written(world, eternal):
    preview, _client = await _divine_preview(world, eternal)
    throne = next(f for f in preview.facts if f.text.startswith("The Tsar presides"))
    assert throne.ticked is False
    throne.ticked = True
    # and an own fact the owner unticks isn't
    dropped = next(f for f in preview.facts if f.text.startswith("Diplomatic envoys"))
    dropped.ticked = False

    accept_preview(world, preview)
    texts = _texts(world.view(), eternal.divine)
    assert throne.text in texts
    assert dropped.text not in texts


def test_default_category_never_heritage():
    assert default_category("sphere", False) == "about"
    assert default_category("sphere", True) == "timeline"
    assert default_category("place", False) == "general"
    assert default_category("place", True) == "history"
    for kind in ("lore", "event", "item", "being", "species", "race", "mix"):
        assert default_category(kind, False) == "general"
        assert default_category(kind, True) == "general"
    # what heritage passes down to members a section at a time (a
    # species' physical facts, a culture's dress), and a sphere's
    # statements, which its members hold: never given by default
    passed: set[str] = {"statement"}
    for section in prose_gen.sections_for("character"):
        for categories in prose_gen.inherited_categories(section).values():
            passed.update(categories)
    for kind in KINDS:
        for dated in (False, True):
            category = default_category(kind, dated)
            assert category not in passed, (kind, dated, category)
            # a category the kind has, so it can be written
            assert category in get_kind(kind).categories, (kind, category)


async def test_elsewhere_target_deleted_before_accept(world, eternal):
    preview, _client = await _divine_preview(world, eternal)
    with world.revision(Source.manual(note="gone")) as rev:
        rev.remove_thing(eternal.tsardom)

    notes: list[str] = []
    thing_id = accept_preview(world, preview, notes=notes)

    view = world.view()
    assert view.thing(eternal.tsardom) is None
    assert any("Tsardom of Moscavia" in note for note in notes)
    # the rest is written
    church_item = next(e for e in preview.elsewhere if e.target_id == eternal.church)
    assert church_item.text in _texts(view, eternal.church)
    assert view.thing(thing_id) is not None


async def test_candidates_come_from_nearness(world, eternal):
    preview, client = await _divine_preview(world, eternal)
    prompt = str(client.prompt_history[0]["prompt"])
    block = prompt.split("Entries near this one in the world:", 1)[1]
    block = block.split("The world's calendar", 1)[0]
    lines = [line[2:] for line in block.strip().splitlines()]
    # today's context first: its sphere, then what mentions it
    # no drawer titles at all (rulings C29, C30): the curation flow
    # probe's facts took them up ("the Frontier drawer of Runeweaving")
    assert lines[0].startswith(
        "Church of the Eternal Light (sphere: religion; usually called The Church): "
        "The Church of the Eternal Light is the state religion"
    )
    assert not [line for line in lines if "drawer" in line.split("):", 1)[0]]
    assert lines[1].startswith(
        "Tsardom of Moscavia (place; usually called Moscavia): The Tsardom of "
        "Moscavia is a vast northern kingdom"
    )
    # reach 1 by default: one step out, so not its siblings in the Church
    # nor Moskov (two steps), never the stub itself or the Iron Guild
    names = [line.split(" (", 1)[0] for line in lines]
    assert names == ["Church of the Eternal Light", "Tsardom of Moscavia"]
    assert all(len(line.split("): ", 1)[1]) <= 130 for line in lines)

    def listed(prompt):
        block = prompt.split("Entries near this one in the world:", 1)[1]
        block = block.split("The world's calendar", 1)[0]
        return [line[2:] for line in block.strip().splitlines()]

    # further out: its siblings and Moskov, still never the Iron Guild
    world.set_curation(CurationSettings(reach=2))
    preview, client = await _divine_preview(world, eternal)
    lines = listed(str(client.prompt_history[0]["prompt"]))
    names = [line.split(" (", 1)[0] for line in lines]
    assert names[:2] == ["Church of the Eternal Light", "Tsardom of Moscavia"]
    assert set(names[2:]) == {
        "The Patriarch of Moscavia",
        "The Shrine of First Dawn",
        "Moskov",
    }
    patriarch = next(line for line in lines if line.startswith("The Patriarch"))
    # ruling C29: "part of Y" only, no drawer title (the curation flow
    # probe's facts said "the Techniques drawer of Runeweaving")
    assert patriarch.startswith(
        "The Patriarch of Moscavia (lore; part of Church of the Eternal Light; "
        "stub): The supreme head of the Church"
    )

    # and capped at the world's `entries`
    world.set_curation(CurationSettings(reach=2, entries=3))
    preview, client = await _divine_preview(world, eternal)
    names = [
        line.split(" (", 1)[0]
        for line in listed(str(client.prompt_history[0]["prompt"]))
    ]
    assert names == [
        "Church of the Eternal Light",
        "Tsardom of Moscavia",
        "The Patriarch of Moscavia",
    ]


async def test_undo_then_redo_elsewhere_accept(world, eternal):
    preview, _client = await _divine_preview(world, eternal)
    before = {
        thing: _texts(world.view(), thing)
        for thing in (eternal.tsardom, eternal.church)
    }
    accept_preview(world, preview)
    rev = world.head_rev()
    after = {
        thing: _texts(world.view(), thing)
        for thing in (eternal.tsardom, eternal.church)
    }
    assert after != before

    undone = world.undo([rev])
    assert undone.conflicts == []
    view = world.view()
    assert {thing: _texts(view, thing) for thing in before} == before
    assert not _named(view, "Tsar")
    assert view.thing(eternal.divine).is_stub

    redone = world.undo([undone.undo_rev])
    assert redone.conflicts == []
    view = world.view()
    assert {thing: _texts(view, thing) for thing in after} == after
    assert len(_named(view, "Tsar")) == 1


# --- Fill --------------------------------------------------------------------


async def _fill(world, sphere_id, drawer_id, reply):
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply)
        filled = await fill_drawer(world, sphere_id, drawer_id, client)
    return filled, client


async def test_fill_elsewhere_and_repeats(world, eternal):
    filled, client = await _fill(world, eternal.church, HIERARCHY, FILL_HIERARCHY)

    assert isinstance(filled, FillPreview)
    prompt = str(client.prompt_history[0]["prompt"])
    assert "Entries near this one in the world:" in prompt
    assert '"elsewhere": [{"entry"' in prompt
    assert client.prompt_history[0]["kind"] == "creative_instruction_1024"

    items = {item["name"] or item["text"][:20]: item for item in filled.items}
    # the training statement is a copy of a line on Moskov: unticked
    training = items[TRAINING[:20]]
    assert training["repeat_of"]["owner_id"] == eternal.moskov
    assert training["ticked"] is False
    fresh = items["The Diaconate"]
    assert fresh["repeat_of"] is None and fresh["ticked"] is True

    targets = [(e.target_name, e.target_id) for e in filled.elsewhere]
    assert targets[0] == ("The Patriarch of Moscavia", eternal.patriarch)
    assert targets[1][0] == "The Synod of Lanterns" and targets[1][1] is None
    assert targets[2] == ("The Shrine of First Dawn", eternal.shrine)
    shrine = filled.elsewhere[2]
    assert shrine.held_by == eternal.church
    assert shrine.category == "general"

    head = world.head_rev()
    notes: list[str] = []
    accept_fill(
        world,
        eternal.church,
        HIERARCHY,
        filled.items,
        filled.elsewhere,
        notes=notes,
    )
    assert world.head_rev() == head + 1
    assert notes == []
    view = world.view()
    held = spheres.items(view, eternal.church)
    texts = {item.text for item in held} | {item.name for item in held}
    assert "The Diaconate" in texts
    assert TRAINING not in texts
    assert filled.elsewhere[0].text in _texts(view, eternal.patriarch)
    synod = _named(view, "Synod of Lanterns") or _named(view, "The Synod of Lanterns")
    assert len(synod) == 1 and synod[0].is_stub
    assert filled.elsewhere[1].text in _texts(view, synod[0].id)
    shrine_state = view.thing(eternal.shrine)
    fact = next(f for f in shrine_state.facts if view.render(f.text) == shrine.text)
    assert spheres.held_by(view, fact, shrine_state) == eternal.church


class Runes(NamedTuple):
    runeweaving: str
    caves: str
    stonehold: str
    greyholm: str


@pytest.fixture
def runes(world):
    """Runeweaving, a field sphere, with the Ashenmere Caves, Stonehold and
    the Greyholm Archive in its Sites drawer."""

    with world.revision(Source.manual(note="runes")) as rev:
        runeweaving = rev.create_thing(
            "sphere",
            {
                "name": "Runeweaving",
                "template": "field",
                "drawers": [{"id": SITES, "type": "places", "title": "Sites"}],
            },
        )
        rev.add_fact(
            runeweaving,
            "about",
            "Runeweaving is the art of inscribing runes of power.",
            origin=SUMMARY_ORIGIN,
        )
        part_of = {"sphere": runeweaving, "drawer": SITES}
        caves = rev.create_thing(
            "place", {"name": "The Ashenmere Caves", "part_of": part_of}
        )
        rev.add_fact(
            caves,
            "description",
            "Cave system containing the oldest known runic inscriptions.",
        )
        stonehold = rev.create_thing(
            "place",
            {"name": "Stonehold", "stub": {"ignored": False}, "part_of": part_of},
        )
        greyholm = rev.create_thing(
            "place",
            {
                "name": "The Greyholm Archive",
                "stub": {"ignored": False},
                "part_of": part_of,
            },
        )
    return Runes(runeweaving, caves, stonehold, greyholm)


async def test_fill_drops_elsewhere_about_its_new_items(world, runes):
    """Ruling C1's Fill filter: an elsewhere item whose text opens with the
    name of one of the reply's new items is about that item, so it's
    dropped (three of this run's four); the fourth names no new item."""

    filled, _client = await _fill(world, runes.runeweaving, SITES, FILL_SITES)
    assert [e.text[:20] for e in filled.elsewhere] == ["Keth of Ashenmere is"]
    dialect = filled.elsewhere[0]
    assert dialect.target_id is None
    assert dialect.new is not None and dialect.new.name == "Ashenmere rune dialect"


# --- fix round 1 ---------------------------------------------------------------


async def test_unticked_fact_leaves_the_prose_stale(world, eternal):
    """Prose written from every fact describes one never written when a
    fact is left unticked: it's cached as of before the accept, so the
    section reads stale and is written again from what's there."""

    preview, _client = await _divine_preview(world, eternal)
    assert any(not fact.ticked for fact in preview.facts)
    preview.prose = {section: "Old prose." for section in preview.prose} or {
        "description": "Old prose."
    }
    thing_id = accept_preview(world, preview)
    cache = world.prose()
    for section in preview.prose:
        assert cache.stale(thing_id, section, None) is True

    # every fact ticked: the prose is current
    with world.revision(Source.manual(note="again")) as rev:
        stub = rev.create_thing(
            "lore",
            {
                "name": "The Divine Right of the Tsarina",
                "stub": {"ignored": False},
                "part_of": {"sphere": eternal.church, "drawer": DOCTRINES},
            },
        )
    preview, _client = await _divine_preview(world, eternal._replace(divine=stub))
    for fact in preview.facts:
        fact.ticked = True
    preview.prose = {"description": "Prose."}
    thing_id = accept_preview(world, preview)
    assert world.prose().stale(thing_id, "description", None) is False


async def test_unticked_core_item_leaves_the_summary_stale(world, eternal):
    from talemate.worldplay.spheres import accept_sphere, preview_sphere

    core = json.dumps(
        {
            "name": "The Iron Order",
            "summary": "An order of smiths.",
            "aka": [],
            "timeline": [{"year": 990, "text": "The order is founded."}],
            "drawers": [{"type": "practices", "title": "Rites"}],
            "items": [
                {"drawer": "Rites", "name": "", "text": "Smiths sing at the forge."},
                {"drawer": "Rites", "name": "", "text": "Bells are rung at dawn."},
            ],
            "names": [],
        }
    )
    preview = await preview_sphere(
        world, "order", "an order of smiths", {}, None, reply=core
    )
    preview.items[0]["ticked"] = False
    sphere_id = accept_sphere(world, preview)
    view = world.view()
    texts = [view.render(f.text) for f in view.thing(sphere_id).facts]
    assert "Smiths sing at the forge." not in texts
    assert world.prose().stale(sphere_id, "description", None) is True


async def test_fill_flags_repeats_of_the_drawers_items(world, eternal):
    """Goal 3: nothing is dropped silently. A Fill item repeating one the
    sphere holds arrives unticked, pointing at the item it repeats."""

    with world.revision(Source.manual(note="deacons")) as rev:
        deacons = rev.add_fact(
            eternal.church,
            "statement",
            "Deacons assist parish priests in liturgical duties and tend to the "
            "material needs of church properties.",
            origin={"drawer": HIERARCHY},
        )
    filled, _client = await _fill(world, eternal.church, HIERARCHY, FILL_HIERARCHY)
    diaconate = next(i for i in filled.items if i["name"] == "The Diaconate")
    assert diaconate["ticked"] is False
    assert diaconate["repeat_of"]["fact_id"] == deacons
    assert diaconate["repeat_of"]["owner_id"] == eternal.church
    assert diaconate["repeat_of"]["score"] >= 0.75

    accept_fill(world, eternal.church, HIERARCHY, filled.items)
    names = {item.name for item in spheres.items(world.view(), eternal.church)}
    assert "The Diaconate" not in names


async def test_ignored_stub_gets_candidates_from_its_sphere(world, eternal):
    with world.revision(Source.manual(note="ignore")) as rev:
        rev.set_field(eternal.divine, "stub", {"ignored": True}, None)
    _preview, client = await _divine_preview(world, eternal)
    prompt = str(client.prompt_history[0]["prompt"])
    block = prompt.split("Entries near this one in the world:", 1)[1]
    block = block.split("The world's calendar", 1)[0]
    names = [line[2:].split(" (", 1)[0] for line in block.strip().splitlines()]
    assert names[0] == "Church of the Eternal Light"
    # what's near the sphere: its parts
    assert "The Patriarch of Moscavia" in names
    assert "The Divine Right of the Tsar" not in names


def test_short_repeat_is_flagged_but_stays_ticked(world, eternal):
    from talemate.worldplay.create import repeat_flags

    with world.revision(Source.manual(note="pines")) as rev:
        rev.add_fact(eternal.guild, "general", "Pine forests and frozen rivers.")
    settings = CurationSettings()
    flags = repeat_flags(
        world.view(),
        ["Pine forests.", "Pine forests and frozen rivers."],
        [eternal.guild],
        settings,
    )
    (short, short_ticked), (long, long_ticked) = flags
    # two content words: shown with its match, but left ticked
    assert short is not None and short["score"] == 1.0 and short_ticked is True
    assert long is not None and long_ticked is False


async def test_unlinked_names_retry_keeps_elsewhere_stubs(world, eternal):
    """The `_UnlinkedNames` retry with elsewhere facts: a name no text
    uses is dropped and the write made again; a new name only an
    elsewhere fact uses is kept, and an elsewhere target the facts also
    name is one stub, linked from the facts."""

    from talemate.worldplay.links import NewName

    preview, _client = await _divine_preview(world, eternal)
    preview.new_names = [
        *preview.new_names,
        NewName(name="Ghost Hall", kind="place"),
        NewName(name="Volga Shrine", kind="place"),
    ]
    tsardom_item = next(e for e in preview.elsewhere if e.target_id == eternal.tsardom)
    tsardom_item.text += " Its oldest altar is the Volga Shrine."
    head = world.head_rev()

    accept_preview(world, preview)

    view = world.view()
    # one revision written, after the rolled-back try
    assert world.head_rev() == head + 1
    assert not _named(view, "Ghost Hall")
    [shrine] = _named(view, "Volga Shrine")
    tsardom = view.thing(eternal.tsardom)
    linked = next(f for f in tsardom.facts if view.render(f.text) == tsardom_item.text)
    assert shrine.id in parse_refs(linked.text)
    [tsar] = _named(view, "Tsar")
    own = view.thing(eternal.divine)
    assert any(tsar.id in parse_refs(f.text) for f in own.facts)
    assert len(tsar.facts) == 1
