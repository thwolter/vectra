from unittest.mock import create_autospec
from types import SimpleNamespace


def test_get_vectorstore_is_cached(monkeypatch):
    # Arrange: patch ensure compat to avoid psycopg2 and DB calls
    from app.vector import factory as fac

    monkeypatch.setattr(fac, '_ensure_langchain_pg_compat', lambda: None)

    # Use autospecs for external classes that get imported inside the function
    created = []
    returned_instance = object()

    EmbeddingsClass = create_autospec(object, instance=False, name='OpenAIEmbeddings')

    def vs_side_effect(*args, **kwargs):
        created.append(kwargs)
        return returned_instance

    VectorStoreClass = create_autospec(object, instance=False, name='PGVector')
    VectorStoreClass.side_effect = vs_side_effect

    # Patch where the function imports them from (module-level, since imports are inside function)
    monkeypatch.setattr(
        'langchain_openai.OpenAIEmbeddings', EmbeddingsClass, raising=False
    )
    monkeypatch.setattr('langchain_postgres.PGVector', VectorStoreClass, raising=False)

    # Stub settings (both module-level used by compat and function-level via get_settings)
    class DummySecret:
        def get_secret_value(self):
            return 'postgres://localhost/test'

    dummy_settings = SimpleNamespace(
        embedding_model='m',
        pg_vector_url=DummySecret(),
    )

    import app.core.config as core_config

    monkeypatch.setattr(
        core_config, 'get_settings', lambda: dummy_settings, raising=False
    )
    monkeypatch.setattr(fac, 'settings', dummy_settings, raising=True)

    # Act
    vs1 = fac.get_vectorstore('my_collection')
    vs2 = fac.get_vectorstore('my_collection')

    # Assert: same instance returned due to lru_cache and only one PGVector created
    assert vs1 is vs2 is returned_instance
    assert len(created) == 1
    assert created[0]['collection_name'] == 'my_collection'
