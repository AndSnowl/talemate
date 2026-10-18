from talemate.cultures.words import (
    COMMON_WORDS,
    clean_name,
    is_proper_item_name,
    looks_like_name,
    mid_sentence_occurrence,
)


def test_clean_name_and_looks_like_name():
    assert clean_name("“Tovrin’s”") == "Tovrin"
    assert clean_name("Brannoch.") == "Brannoch"

    assert looks_like_name("Tovrin") is True
    assert looks_like_name("Hadrik Tolvar") is True
    assert looks_like_name("Ilsa of the Birches") is True

    assert looks_like_name("the ferryman") is False
    assert looks_like_name("Innkeeper") is False
    assert looks_like_name("a rusty lantern") is False
    assert looks_like_name("Grey Gull") is False
    assert looks_like_name("") is False


def test_looks_like_name_treats_role_labels_as_descriptions():
    # possessive + plural role labels are descriptions, not names
    assert looks_like_name("Innkeeper's Boy") is False
    assert looks_like_name("Bargemen") is False
    assert looks_like_name("Fishwives") is False
    assert looks_like_name("Stable Hands") is False
    assert looks_like_name("Guards") is False

    # real names keep working, including a possessive one
    assert looks_like_name("Tovrin") is True
    assert looks_like_name("Dhurhith") is True
    assert looks_like_name("Kethrun's") is True


def test_looks_like_name_plain_plural_nouns_stay_names():
    # a bare plural of an ordinary (non-role) noun, that isn't itself a
    # common word, is still a name: only a person/role word's plural or
    # possessive is a description
    assert looks_like_name("Rivers") is True
    assert looks_like_name("Hawks") is True
    assert looks_like_name("Fields") is True

    # but a multi-word phrase still normalises generically
    assert looks_like_name("River Folk") is False


def test_looks_like_name_single_common_word_is_description():
    # R14: a single word that is itself (unnormalised) a common word is a
    # description, even when it isn't a person/role word
    assert looks_like_name("Lantern") is False
    assert looks_like_name("Ferryman") is False
    assert looks_like_name("River") is False
    assert looks_like_name("Tower") is False
    # "woods" is a literal common_words.txt entry on its own (not reached
    # via plural stripping of "wood"), so it's a description too
    assert looks_like_name("Woods") is False


def test_mid_sentence_occurrence():
    assert mid_sentence_occurrence("Grey Gull", "They boarded the Grey Gull at dawn.")
    assert not mid_sentence_occurrence("Grey Gull", "Grey Gull sails tonight.")
    assert not mid_sentence_occurrence("Grey Gull", "He said. Grey Gull…")


def test_is_proper_item_name():
    assert is_proper_item_name("Grey Gull", ["the Grey Gull"])
    assert is_proper_item_name("Saervik", ["He drew Saervik from its sheath."])

    assert not is_proper_item_name("lantern", ["lifted the lantern"])
    assert not is_proper_item_name("Lantern", ["lifted the Lantern"])
    assert not is_proper_item_name("Rusty Sword", ["held a rusty sword"])


def test_common_words_loaded():
    assert {"innkeeper", "lantern", "the"} <= COMMON_WORDS
    assert len(COMMON_WORDS) >= 1000
