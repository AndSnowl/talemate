"""Heritage resolution: lineage, inherited facts with overrides, numbers
and life stage, all read through a `WorldView`."""

from talemate.world.dates import WorldDate
from talemate.world.heritage import (
    Numbers,
    Range,
    effective_facts,
    find_mix,
    inherited,
    life_stage,
    lineage,
    members,
    numbers,
    species_of,
)
from talemate.world.store import Source


def test_lineage_order(world, heritage_world):
    h = heritage_world
    layers = lineage(world.view(), h.brenna)

    assert [layer.thing_id for layer in layers] == [
        h.brenna,
        h.half_orc,
        h.lowlander,
        h.human,
        h.orc,
        h.riverfolk,
    ]
    assert [layer.name for layer in layers] == [
        "Brenna",
        "Half-orc",
        "Lowlander",
        "Human",
        "Orc",
        "Riverfolk",
    ]
    assert [layer.kind for layer in layers] == [
        "character",
        "mix",
        "race",
        "species",
        "species",
        "culture",
    ]
    depths = [layer.depth for layer in layers]
    assert depths[0] == 0
    assert depths == sorted(set(depths))


def test_lineage_survives_a_parent_cycle(world, heritage_world):
    h = heritage_world
    with world.revision(Source.manual()) as rev:
        mix_a = rev.create_thing("mix", fields={"name": "A"})
        mix_b = rev.create_thing("mix", fields={"name": "B", "parents": [mix_a, h.orc]})
        rev.set_field(mix_a, "parents", [mix_b, h.human], None)

    view = world.view()
    ids = [layer.thing_id for layer in lineage(view, mix_a)]

    assert ids == [mix_a, mix_b, h.orc, h.human]
    assert len(ids) == len(set(ids))
    # numbers resolve through the cycle too: B has Orc's 60 and A averages
    # B with Human's 75
    assert numbers(view, mix_a).lifespan == 67.5


def test_lineage_follows_dated_heritage(world, heritage_world):
    h = heritage_world
    with world.revision(Source.manual()) as rev:
        barred = rev.create_thing(
            "race", fields={"name": "Barred", "species": h.owl_folk}
        )
        rev.set_field(h.vasha, "heritage", barred, WorldDate.of(400))

    before = [
        layer.thing_id for layer in lineage(world.view(WorldDate.of(350)), h.vasha)
    ]
    after = [
        layer.thing_id for layer in lineage(world.view(WorldDate.of(450)), h.vasha)
    ]

    assert before == [h.vasha, h.snowy, h.owl_folk]
    assert after == [h.vasha, barred, h.owl_folk]


def test_inherited_marks_overrides(world, heritage_world):
    h = heritage_world
    with world.revision(Source.manual()) as rev:
        blue = rev.add_fact(
            h.vasha, "appearance", "Blue eyes.", overrides=[h.yellow_eyes]
        )

    view = world.view()
    by_id = {item.fact.fact_id: item for item in inherited(view, h.vasha)}

    assert by_id[h.yellow_eyes].overridden_by == blue
    assert by_id[h.yellow_eyes].source_id == h.snowy
    assert by_id[h.yellow_eyes].source_kind == "race"
    assert by_id[h.yellow_eyes].source_name == "Snowy"
    assert by_id[h.wings].overridden_by is None
    assert by_id[h.wings].source_name == "Owl-folk"

    effective = effective_facts(view, h.vasha)
    ids = [fact.fact_id for fact, _ in effective]
    assert ids == [blue, h.wings]
    assert [layer.name for _, layer in effective] == ["Vasha", "Owl-folk"]


def test_mix_override_hides_parent_fact_for_members(world, heritage_world):
    h = heritage_world
    with world.revision(Source.manual()) as rev:
        half_owl = rev.create_thing(
            "mix", fields={"name": "Half-owl", "parents": [h.owl_folk, h.human]}
        )
        arms = rev.add_fact(
            half_owl, "physical", "Arms with feathered forearms.", overrides=[h.wings]
        )
        pell = rev.create_thing(
            "character", fields={"name": "Pell", "heritage": half_owl}
        )

    view = world.view()
    ids = [fact.fact_id for fact, _ in effective_facts(view, pell)]

    assert arms in ids
    assert h.wings not in ids
    hidden = [item for item in inherited(view, pell) if item.fact.fact_id == h.wings]
    assert hidden[0].overridden_by == arms


def test_inherited_skips_deleted_layer(world, heritage_world):
    h = heritage_world
    with world.revision(Source.manual()) as rev:
        rev.add_fact(h.lowlander, "variation", "Broad shoulders.")
        rev.add_fact(h.human, "physical", "Hairless hands.")
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(h.lowlander)

    view = world.view()
    ids = [layer.thing_id for layer in lineage(view, h.brenna)]
    assert ids == [h.brenna, h.half_orc, h.orc, h.riverfolk]
    sources = {item.source_id for item in inherited(view, h.brenna)}
    assert h.lowlander not in sources
    assert h.human not in sources
    assert numbers(view, h.brenna).lifespan == 60


def test_override_of_removed_fact_is_harmless(world, heritage_world):
    h = heritage_world
    with world.revision(Source.manual()) as rev:
        blue = rev.add_fact(
            h.vasha, "appearance", "Blue eyes.", overrides=[h.yellow_eyes]
        )
    with world.revision(Source.manual()) as rev:
        rev.remove_fact(h.yellow_eyes)

    view = world.view()
    ids = [fact.fact_id for fact, _ in effective_facts(view, h.vasha)]

    assert ids == [blue, h.wings]
    assert all(item.overridden_by is None for item in inherited(view, h.vasha))


def test_dated_species_fact_reaches_only_later_views(world, heritage_world):
    h = heritage_world
    with world.revision(Source.manual()) as rev:
        molt = rev.add_fact(
            h.owl_folk, "physical", "Molt each spring.", valid_from=WorldDate.of(500)
        )

    def inherited_ids(year):
        return {
            item.fact.fact_id
            for item in inherited(world.view(WorldDate.of(year)), h.vasha)
        }

    assert molt in inherited_ids(501)
    assert molt not in inherited_ids(499)


def test_numbers_fall_back_and_average(world, heritage_world):
    h = heritage_world
    view = world.view()

    snowy = numbers(view, h.snowy)
    assert snowy.measures["wingspan"] == Range(min=8.5, max=9, unit="ft")
    assert snowy.measures["height"] == Range(min=4, max=5, unit="ft")
    assert snowy.lifespan == 70
    assert snowy.adult_age == 12

    half_orc = numbers(view, h.half_orc)
    assert half_orc.lifespan == 67.5
    assert half_orc.adult_age == 16
    assert half_orc.measures["height"] == Range(min=5.5, max=7, unit="ft")

    # a character resolves through its heritage
    assert numbers(view, h.brenna) == half_orc
    assert numbers(view, h.vasha) == snowy


def test_numbers_mix_with_one_parent_value(world, heritage_world):
    h = heritage_world
    with world.revision(Source.manual()) as rev:
        owl_orc = rev.create_thing(
            "mix", fields={"name": "Owl-orc", "parents": [h.owl_folk, h.orc]}
        )

    result = numbers(world.view(), owl_orc)
    # only Owl-folk has a wingspan, so the mix takes it as is
    assert result.measures["wingspan"] == Range(min=7, max=9, unit="ft")


def test_life_stage_bounds():
    nums = Numbers(lifespan=70, adult_age=12, measures={})

    assert life_stage(8, nums) == ("child", False)
    assert life_stage(9, nums) == ("adolescent", False)
    assert life_stage(12, nums) == ("adult", False)
    assert life_stage(55, nums) == ("adult", False)
    assert life_stage(56, nums) == ("elder", False)
    assert life_stage(70, nums) == ("elder", False)
    assert life_stage(71, nums) == ("elder", True)

    empty = Numbers(lifespan=None, adult_age=None, measures={})
    assert life_stage(30, empty) == (None, False)


def test_members_and_species_of(world, heritage_world):
    h = heritage_world
    view = world.view()

    assert members(view, h.owl_folk) == [h.vasha]
    assert members(view, h.human) == [h.brenna]
    assert members(view, h.riverfolk) == [h.brenna]
    assert species_of(view, h.half_orc) == [h.human, h.orc]
    assert species_of(view, h.snowy) == [h.owl_folk]
    assert species_of(view, h.orc) == [h.orc]


def test_find_mix_either_order(world, heritage_world):
    h = heritage_world
    view = world.view()

    assert find_mix(view, h.lowlander, h.orc) == h.half_orc
    assert find_mix(view, h.orc, h.lowlander) == h.half_orc
    assert find_mix(view, h.snowy, h.orc) is None


def test_numbers_mix_of_two_races_of_one_species(world, heritage_world):
    h = heritage_world
    with world.revision(Source.manual()) as rev:
        highlander = rev.create_thing(
            "race", fields={"name": "Highlander", "species": h.human, "lifespan": 85}
        )
        mixed = rev.create_thing(
            "mix", fields={"name": "Mixed", "parents": [h.lowlander, highlander]}
        )

    result = numbers(world.view(), mixed)
    # both parents reach Human's numbers, though lineage lists Human once
    assert result.lifespan == 80
    assert result.adult_age == 18


def test_shared_species_override_ignores_parent_order(world, heritage_world):
    h = heritage_world
    with world.revision(Source.manual()) as rev:
        hands = rev.add_fact(h.human, "physical", "Five-fingered hands.")
        highlander = rev.create_thing(
            "race", fields={"name": "Highlander", "species": h.human}
        )
        six = rev.add_fact(
            highlander, "variation", "Six-fingered hands.", overrides=[hands]
        )
        mixed = rev.create_thing(
            "mix", fields={"name": "Mixed", "parents": [h.lowlander, highlander]}
        )
        reversed_mix = rev.create_thing(
            "mix", fields={"name": "Mixed-r", "parents": [highlander, h.lowlander]}
        )
        ivo = rev.create_thing(
            "character", fields={"name": "Ivo", "heritage": highlander}
        )

    view = world.view()
    # Human is listed once, under Lowlander, so it comes before Highlander
    assert [layer.thing_id for layer in lineage(view, mixed)] == [
        mixed,
        h.lowlander,
        h.human,
        highlander,
    ]
    # either order, the mix reaches Human through Lowlander as well, so
    # Highlander's override doesn't settle the blend
    for mix in (mixed, reversed_mix):
        by_id = {item.fact.fact_id: item for item in inherited(view, mix)}
        assert by_id[hands].overridden_by is None
    # a Highlander character reaches Human only through Highlander
    by_id = {item.fact.fact_id: item for item in inherited(view, ivo)}
    assert by_id[hands].overridden_by == six


def test_sibling_parent_does_not_override(world, heritage_world):
    h = heritage_world
    with world.revision(Source.manual()) as rev:
        tusks = rev.add_fact(h.orc, "physical", "Tusks.")
        rev.add_fact(h.lowlander, "variation", "No tusks.", overrides=[tusks])

    # Lowlander doesn't inherit from Orc, so its override doesn't reach
    # Orc's fact through the Half-orc mix
    by_id = {item.fact.fact_id: item for item in inherited(world.view(), h.half_orc)}
    assert by_id[tusks].overridden_by is None


def test_override_not_applied_when_target_reachable_another_way(world, heritage_world):
    h = heritage_world
    with world.revision(Source.manual()) as rev:
        olive = rev.add_fact(h.lowlander, "physical", "Olive skin.")
        grey = rev.add_fact(
            h.half_orc, "physical", "Grey-green skin.", overrides=[olive]
        )
        quarter_orc = rev.create_thing(
            "mix", fields={"name": "Quarter-orc", "parents": [h.lowlander, h.half_orc]}
        )
        tam = rev.create_thing(
            "character", fields={"name": "Tam", "heritage": quarter_orc}
        )

    view = world.view()

    # the Quarter-orc reaches Lowlander directly too, so Half-orc's override
    # doesn't settle the blend; the quarter's own facts would
    for thing_id in (quarter_orc, tam):
        by_id = {item.fact.fact_id: item for item in inherited(view, thing_id)}
        assert by_id[olive].overridden_by is None
        ids = [fact.fact_id for fact, _ in effective_facts(view, thing_id)]
        assert olive in ids
        assert grey in ids

    # a plain Half-orc character reaches Lowlander only through Half-orc
    by_id = {item.fact.fact_id: item for item in inherited(view, h.brenna)}
    assert by_id[olive].overridden_by == grey
    assert olive not in [fact.fact_id for fact, _ in effective_facts(view, h.brenna)]


def test_override_applied_when_every_path_passes_through_it(world, heritage_world):
    h = heritage_world
    with world.revision(Source.manual()) as rev:
        hands = rev.add_fact(h.human, "physical", "Five-fingered hands.")
        highlander = rev.create_thing(
            "race", fields={"name": "Highlander", "species": h.human}
        )
        twin = rev.create_thing(
            "mix", fields={"name": "Twin-blood", "parents": [h.lowlander, highlander]}
        )
        six = rev.add_fact(twin, "physical", "Six-fingered hands.", overrides=[hands])
        grand = rev.create_thing(
            "mix", fields={"name": "Grand", "parents": [twin, h.orc]}
        )

    view = world.view()
    # both paths to Human (via Lowlander and via Highlander) go through
    # Twin-blood
    by_id = {item.fact.fact_id: item for item in inherited(view, grand)}
    assert by_id[hands].overridden_by == six
    assert hands not in [fact.fact_id for fact, _ in effective_facts(view, grand)]
