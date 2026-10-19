"""Strict mypy over talemate.world, run as a regular test so the suite
enforces it. The rest of talemate stays untyped; see the `[tool.mypy]`
section in pyproject.toml.
"""

from pathlib import Path

from mypy import api as mypy_api

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_world_package_typechecks(tmp_path):
    config_file = REPO_ROOT / "pyproject.toml"
    cache_dir = tmp_path / ".mypy_cache"

    stdout, stderr, status = mypy_api.run(
        [
            "--config-file",
            str(config_file),
            "--cache-dir",
            str(cache_dir),
            "-p",
            "talemate.world",
        ]
    )

    assert status == 0, f"mypy found errors:\n{stdout}\n{stderr}"
