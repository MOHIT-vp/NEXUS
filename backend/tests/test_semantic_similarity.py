"""Meaning-based similarity with the local embedding model (skipped if the model can't be loaded)."""
import os

import pytest

MODEL_CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "models")


@pytest.fixture
def model_backend(monkeypatch):
    from app.config import settings
    from app.services import similarity
    monkeypatch.setattr(settings, "EMBEDDING_BACKEND", "model")
    monkeypatch.setattr(settings, "EMBEDDING_CACHE_DIR", MODEL_CACHE)
    monkeypatch.setattr(similarity, "_model_failed", False)
    if similarity.backend_name() == "hashed":
        pytest.skip("embedding model not available offline")
    yield similarity
    similarity._model_vector.cache_clear()


def test_model_matches_meaning_not_just_words(model_backend):
    s = model_backend
    q = s.embed("database design and writing queries")
    related = s.cosine(q, s.embed("SQL schemas, joins and normalisation"))
    unrelated = s.cosine(q, s.embed("Mechanical CAD modelling in SolidWorks"))
    assert related >= s.related_threshold() > unrelated
    assert s.cosine(s._hashed("database design and writing queries"), s._hashed("SQL schemas, joins and normalisation")) == 0.0


async def test_retrieval_finds_resources_by_meaning(model_backend, db_factory, reference_data):
    from app.agents.knowledge_base import kb
    async with db_factory() as db:
        res = await kb.retrieve(db, "how relational databases store and query tables", doc_types=["learning_resource"], k=3)
    assert res.status == "ok" and res.backend.startswith("postgres_fts+model:")
    assert any("sql" in i.title.lower() or "database" in i.title.lower() or "dbms" in i.title.lower() for i in res.items)
