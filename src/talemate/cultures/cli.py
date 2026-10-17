"""Command-line interface for culture files.

Used by the culture-design skill (Task 7) to validate a culture file before
handing it to Talemate's importer, and to preview the names its generators
roll. Run as ``python -m talemate.cultures.cli <command>``.
"""

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from talemate.cultures.exchange import CultureFile
from talemate.cultures.generator import GeneratorError, fits, roll, validate_language


def cmd_validate(args: argparse.Namespace) -> int:
    path = Path(args.file)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        file = CultureFile.model_validate(data)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"Invalid culture file: {exc}", file=sys.stderr)
        return 1

    try:
        validate_language(file.culture.language)
    except GeneratorError as exc:
        print(f"Invalid culture file: {exc}", file=sys.stderr)
        return 1

    print(f"OK: {path}")
    return 0


def cmd_sample(args: argparse.Namespace) -> int:
    path = Path(args.file)
    data = json.loads(path.read_text(encoding="utf-8"))
    file = CultureFile.model_validate(data)
    language = file.culture.language

    generators = language.generators
    if args.generator:
        generators = [gen for gen in generators if gen.id == args.generator]
        if not generators:
            print(f"Unknown generator id: {args.generator}", file=sys.stderr)
            return 1

    for gen in generators:
        print(f"{gen.name} ({gen.id}):")
        for name in roll(language, gen.id, count=args.count):
            mark = "✓" if fits(language, name) else "✗"
            print(f"  {mark} {name}")
    return 0


def cmd_schema(args: argparse.Namespace) -> int:
    print(json.dumps(CultureFile.model_json_schema(), indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m talemate.cultures.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate", help="validate a culture file against the schema"
    )
    validate_parser.add_argument("file")
    validate_parser.set_defaults(func=cmd_validate)

    sample_parser = subparsers.add_parser(
        "sample", help="roll sample names from a culture file's generators"
    )
    sample_parser.add_argument("file")
    sample_parser.add_argument(
        "--generator", default=None, help="a single generator id"
    )
    sample_parser.add_argument("--count", type=int, default=10)
    sample_parser.set_defaults(func=cmd_sample)

    schema_parser = subparsers.add_parser(
        "schema", help="print the culture file JSON schema"
    )
    schema_parser.set_defaults(func=cmd_schema)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
