"""The language file's JSON schema, generated from `LanguageFile` and
committed beside it (`language.schema.json`) for the language-design skill
and outside assistants. `tests/languages/test_models.py` keeps the two in
step; regenerate with::

    python -c "import json; from talemate.languages.schema import *; \\
        SCHEMA_PATH.write_text(json.dumps(language_file_schema(), indent=2) + '\\n')"
"""

from pathlib import Path

from talemate.languages.models import LanguageFile

__all__ = ["SCHEMA_PATH", "language_file_schema"]

SCHEMA_PATH = Path(__file__).resolve().parent / "language.schema.json"


def language_file_schema() -> dict:
    """The JSON schema of a language file."""
    return LanguageFile.model_json_schema()
