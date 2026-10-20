"""Shared test helpers for anything that builds a `WorldIndex`: a
deterministic, offline embedding function, and a skip marker for when
`chromadb` can't be imported (R7)."""

import hashlib

import pytest

try:
    import chromadb

    _CHROMADB_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - import failure path
    chromadb = None
    _CHROMADB_IMPORT_ERROR = exc

requires_chromadb = pytest.mark.skipif(
    chromadb is None,
    reason=f"chromadb is not importable in this environment: {_CHROMADB_IMPORT_ERROR}",
)


class TrigramEmbeddingFunction:
    """A deterministic, offline stand-in for a real embedding function:
    hashes each character trigram of the input into one of 64 dimensions.
    Implements the parts of chromadb 1.5.9's `EmbeddingFunction` protocol it
    checks, so no deprecation warnings show."""

    DIMS = 64

    def __call__(self, input: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in input]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.DIMS
        padded = f"  {text.lower()}  "
        for i in range(len(padded) - 2):
            digest = hashlib.sha256(padded[i : i + 3].encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self.DIMS
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = sum(v * v for v in vector) ** 0.5
        if norm == 0:
            return vector
        return [v / norm for v in vector]

    def embed_query(self, input: list[str]) -> list[list[float]]:
        return self(input)

    @staticmethod
    def name() -> str:
        return "test-trigram"

    def get_config(self) -> dict:
        return {}

    @staticmethod
    def build_from_config(config: dict) -> "TrigramEmbeddingFunction":
        return TrigramEmbeddingFunction()

    def is_legacy(self) -> bool:
        return False

    def default_space(self) -> str:
        return "cosine"

    def supported_spaces(self) -> list[str]:
        return ["cosine", "l2", "ip"]
