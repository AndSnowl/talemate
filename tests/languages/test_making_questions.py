"""Plain questions before a language is made (languages 3b-1, Task 3)."""

from talemate.languages.making import ask_questions

from conftest import MockClient, MockClientContext, client_responses


async def test_questions_are_parsed_from_a_numbered_reply():
    reply = "1. How Russian should it sound?\n2. Grand or earthy?\n\n3) Old or modern?"
    assert await ask_questions(None, "x", reply=reply) == [
        "How Russian should it sound?",
        "Grand or earthy?",
        "Old or modern?",
    ]


async def test_at_most_four_questions():
    reply = "\n".join(f"{n}. Question {n}?" for n in range(1, 7))
    assert len(await ask_questions(None, "x", reply=reply)) == 4


async def test_no_client_means_no_questions():
    assert await ask_questions(None, "x") == []


async def test_the_model_is_asked_for_plain_questions():
    client = MockClient("test")
    async with MockClientContext():
        client_responses.get().append("1. Grand or earthy?")
        got = await ask_questions(client, "a unique but recognizably Russian language")
    assert got == ["Grand or earthy?"]
