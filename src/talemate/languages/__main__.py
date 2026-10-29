"""`python -m talemate.languages check FILE`: run the shared check on a
language file and print the result in plain words. Exits 1 when something
must be fixed before the language can be imported, else 0. The
language-design skill runs it on its own output."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from talemate.languages.check import CheckReport, check_language, repair_note
from talemate.languages.importer import parse_language_text
from talemate.languages.models import LanguageFile


def _read(path: Path) -> LanguageFile:
    """The language in `path`: a file, or a saved reply with prose around
    it (`parse_language_text`)."""
    return parse_language_text(path.read_text(encoding="utf-8"))


def check_file(path: Path) -> CheckReport:
    """The check on the language in `path`; a file that can't be read as a
    language is a blocking problem."""
    try:
        language_file = _read(path)
    except (OSError, ValueError) as exc:
        return CheckReport(blocking=[f"The file can't be read as a language: {exc}"])
    return check_language(language_file.language)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m talemate.languages")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="check a language file")
    check.add_argument("file", type=Path)
    args = parser.parse_args(argv)

    report = check_file(args.file)
    print(repair_note(report))
    if report.ok:
        for generator_id, names in report.samples.items():
            print(f"\nSample names ({generator_id}): {', '.join(names)}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
