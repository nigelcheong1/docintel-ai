import builtins
import os
import sys
from types import SimpleNamespace

import pytest

from app.retrieval.embeddings import FakeEmbeddingProvider, LocalEmbeddingProvider, normalize_embedding_dimension


def test_fake_embedding_provider_returns_stable_dimension():
    provider = FakeEmbeddingProvider(dimension=384)

    vectors = provider.embed_texts(["invoice total", "purchase order"])

    assert len(vectors) == 2
    assert len(vectors[0]) == 384
    assert vectors[0] == provider.embed_texts(["invoice total"])[0]


def test_normalize_embedding_dimension_rejects_wrong_size():
    with pytest.raises(ValueError, match="Expected embedding dimension 384"):
        normalize_embedding_dimension([0.1, 0.2], expected_dimension=384)


def test_local_embedding_provider_uses_cpu_device_by_default(monkeypatch):
    calls = {}

    class FakeSentenceTransformer:
        def __init__(self, model_name, **kwargs):
            calls["model_name"] = model_name
            calls["kwargs"] = kwargs

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )

    LocalEmbeddingProvider("test-model", expected_dimension=384)

    assert calls["model_name"] == "test-model"
    assert calls["kwargs"]["device"] == "cpu"


def test_local_embedder_disables_unused_tensorflow_before_import(monkeypatch):
    monkeypatch.delenv("USE_TF", raising=False)
    original_import = builtins.__import__
    import_environment = []

    def observe_import(name, *args, **kwargs):
        if name == "sentence_transformers":
            import_environment.append(os.environ.get("USE_TF"))
            return SimpleNamespace(SentenceTransformer=lambda *args, **kwargs: object())
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", observe_import)

    LocalEmbeddingProvider("test-model", expected_dimension=384)

    assert import_environment == ["0"]
