import pytest

from app.retrieval.embeddings import FakeEmbeddingProvider, normalize_embedding_dimension


def test_fake_embedding_provider_returns_stable_dimension():
    provider = FakeEmbeddingProvider(dimension=384)

    vectors = provider.embed_texts(["invoice total", "purchase order"])

    assert len(vectors) == 2
    assert len(vectors[0]) == 384
    assert vectors[0] == provider.embed_texts(["invoice total"])[0]


def test_normalize_embedding_dimension_rejects_wrong_size():
    with pytest.raises(ValueError, match="Expected embedding dimension 384"):
        normalize_embedding_dimension([0.1, 0.2], expected_dimension=384)
