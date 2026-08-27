from app.documents import router


def test_embedding_provider_is_cached_by_model_settings(monkeypatch):
    created = []

    class StubEmbeddingProvider:
        def __init__(self, model_name: str, dimension: int) -> None:
            created.append((model_name, dimension))

    monkeypatch.setattr(router, "LocalEmbeddingProvider", StubEmbeddingProvider)
    router.get_cached_embedding_provider.cache_clear()

    try:
        first = router.get_cached_embedding_provider("BAAI/bge-small-en-v1.5", 384)
        second = router.get_cached_embedding_provider("BAAI/bge-small-en-v1.5", 384)
    finally:
        router.get_cached_embedding_provider.cache_clear()

    assert first is second
    assert created == [("BAAI/bge-small-en-v1.5", 384)]
