import hashlib
import random
from collections.abc import Sequence
from typing import Protocol


class EmbeddingProvider(Protocol):
    model_name: str
    dimension: int

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        ...


def normalize_embedding_dimension(vector: Sequence[float], expected_dimension: int) -> list[float]:
    if len(vector) != expected_dimension:
        raise ValueError(f"Expected embedding dimension {expected_dimension}, got {len(vector)}.")
    return [float(value) for value in vector]


class LocalEmbeddingProvider:
    def __init__(self, model_name: str, expected_dimension: int) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.dimension = expected_dimension
        self._model = SentenceTransformer(model_name)

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        embeddings = self._model.encode(list(texts), normalize_embeddings=True)
        return [normalize_embedding_dimension(vector.tolist(), self.dimension) for vector in embeddings]


class FakeEmbeddingProvider:
    model_name = "fake-local-embedding"

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
        rng = random.Random(seed)
        return [rng.uniform(-1.0, 1.0) for _ in range(self.dimension)]
