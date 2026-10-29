"""Shared helpers for the languages tests (languages 3a)."""

from talemate.world.dates import WorldDate


def _lang_fields(name: str) -> dict:
    return {
        "name": name,
        "depth": "naming",
        "rules": {
            "categories": {"C": "k v r s", "V": "a o e"},
            "generators": [
                {
                    "id": "people",
                    "name": "People",
                    "use": "people",
                    "patterns": ["CVC"],
                },
                {
                    "id": "places",
                    "name": "Places",
                    "use": "places",
                    "patterns": ["CVCV"],
                },
            ],
        },
    }


def _row(lang, role, share=None, fluency=None, since=None, until=None):
    row = {"language": lang, "role": role}
    if share is not None:
        row["share"] = share
    if fluency is not None:
        row["fluency"] = fluency
    if since is not None:
        row["since"] = WorldDate.of(since)
    if until is not None:
        row["until"] = WorldDate.of(until)
    return row
