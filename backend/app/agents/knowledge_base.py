"""
RAG Knowledge Base (Lab 4) — job descriptions, role guides and learning resources.

Storage is the application's PostgreSQL database. Two retrieval backends:

- ``postgres_fts`` (default): chunks live in ``knowledge_documents``; tag
  filters (doc type, role family) plus PostgreSQL full-text search pick the
  candidates, which are re-ranked by embedding similarity (local hashed
  embeddings, ``app.services.similarity``). If no words match, the closest
  documents by similarity alone are returned. Needs no extensions or credentials.
- ``pgvector``: the original LangChain PGVector + Bedrock embeddings path. Only
  usable when the ``vector`` extension and AWS credentials are available; set
  ``KB_BACKEND=pgvector``.

Retrieval never fabricates content: an empty corpus returns status ``empty``
and a backend failure returns ``unavailable`` with the reason. Retrieved text
is untrusted data — it is cited in reports, never executed as instructions.
"""
import os
import re
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.workflow import KnowledgeDocument

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

_STOPWORDS = {
    "the", "and", "for", "with", "what", "are", "how", "into", "from", "that", "this", "your",
    "skills", "skill", "requirements", "role", "roles", "a", "an", "of", "to", "in", "on", "is",
    # every resource says "learning resource", so these words would outrank the skill itself
    "learning", "resource", "resources",
}


class RetrievedChunk(BaseModel):
    document_id: str
    title: str
    excerpt: str
    source: str
    url: Optional[str] = None
    doc_type: str
    role_family: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    score: float = 0.0


class RetrievalResult(BaseModel):
    status: str  # ok | empty | unavailable
    backend: str
    query: str
    items: List[RetrievedChunk] = Field(default_factory=list)
    error: Optional[str] = None


def _split(text_: str) -> List[str]:
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP, separators=["\n\n", "\n", ".", " "]
        )
        return [c for c in splitter.split_text(text_) if c.strip()]
    except ImportError:  # pragma: no cover - splitter ships with requirements
        return [text_[i:i + CHUNK_SIZE] for i in range(0, len(text_), CHUNK_SIZE - CHUNK_OVERLAP)]


def _or_query(query: str) -> Optional[str]:
    words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 1 and w not in _STOPWORDS]
    if not words:
        return None
    return " | ".join(sorted(set(words)))


class CareerKnowledgeBase:
    """Knowledge base facade used by agents (through the KnowledgeConnector) and ingestion scripts."""

    def __init__(self, backend: Optional[str] = None):
        self.backend = (backend or settings.KB_BACKEND or "postgres_fts").lower()
        self._vector_store = None

    # ---------------------------- ingestion ----------------------------

    async def ingest(
        self,
        db: AsyncSession,
        *,
        doc_type: str,
        title: str,
        content: str,
        source: str,
        url: Optional[str] = None,
        role_family: Optional[str] = None,
        tags: Optional[List[str]] = None,
        replace_existing: bool = True,
    ) -> int:
        """Chunk and store a document. Returns the number of chunks stored."""
        if not content or not content.strip():
            return 0
        if replace_existing:
            await db.execute(delete(KnowledgeDocument).where(
                KnowledgeDocument.title == title, KnowledgeDocument.source == source))
        chunks = _split(content.strip())
        for i, chunk in enumerate(chunks):
            db.add(KnowledgeDocument(
                doc_type=doc_type,
                title=title if len(chunks) == 1 else f"{title} (part {i + 1})",
                content=chunk,
                source=source,
                url=url,
                role_family=role_family,
                tags=tags or [],
            ))
        await db.flush()
        if self.backend == "pgvector":
            self._pgvector_add(doc_type, title, content, source, role_family)
        return len(chunks)

    async def ingest_job_description(self, db: AsyncSession, role_title: str, company: str, raw_text: str,
                                     role_family: Optional[str] = None, url: Optional[str] = None) -> int:
        return await self.ingest(
            db, doc_type="job_description", title=f"{company} — {role_title}", content=raw_text,
            source=f"{company} job description", url=url, role_family=role_family,
            tags=["job_description", role_family or "general"],
        )

    # ---------------------------- retrieval ----------------------------

    async def retrieve(
        self,
        db: AsyncSession,
        query: str,
        *,
        role_families: Optional[List[str]] = None,
        doc_types: Optional[List[str]] = None,
        k: int = 5,
    ) -> RetrievalResult:
        if self.backend == "pgvector":
            return self._pgvector_retrieve(query, k)
        tsq = _or_query(query)   # None for names keyword search can't handle (e.g. "C", "C++")
        try:
            conditions = ["search_vector @@ to_tsquery('english', :q)"]
            params: Dict[str, Any] = {"q": tsq, "k": k}
            if role_families:
                conditions.append("(role_family = ANY(:families) OR role_family IS NULL)")
                params["families"] = role_families
            if doc_types:
                conditions.append("doc_type = ANY(:types)")
                params["types"] = doc_types
            params["k"] = k * 4    # candidates for the similarity re-rank
            sql = text(f"""
                SELECT id, title, content, source, url, doc_type, role_family, tags,
                       ts_rank(search_vector, to_tsquery('english', :q)) AS score
                FROM knowledge_documents
                WHERE {' AND '.join(conditions)}
                ORDER BY score DESC
                LIMIT :k
            """)
            rows = (await db.execute(sql, params)).fetchall() if tsq else []
            if not rows:   # no keyword overlap: nearest documents by similarity within the tag filters
                params["k"] = 500
                sql = text(f"""
                    SELECT id, title, content, source, url, doc_type, role_family, tags, 0.0 AS score
                    FROM knowledge_documents
                    WHERE {' AND '.join(conditions[1:]) or 'TRUE'}
                    LIMIT :k
                """)
                rows = (await db.execute(sql, params)).fetchall()
        except Exception as exc:
            return RetrievalResult(status="unavailable", backend=self.backend, query=query,
                                   error=f"Knowledge base query failed: {exc.__class__.__name__}")
        from app.services.similarity import backend_name, cosine, embed, related_threshold
        q_vec = embed(query)
        threshold = related_threshold()
        # Blend keyword rank (normalised) with meaning-based similarity; with no keyword hits, keep only related docs
        top = max((float(r.score) for r in rows), default=0.0) or 1.0
        scored = []
        for r in rows:
            sim = cosine(q_vec, embed(f"{r.title} {r.content}"))
            if float(r.score) > 0 or sim >= threshold:
                scored.append((round(0.6 * float(r.score) / top + 0.4 * sim, 4), float(r.score), r))
        ranked = sorted(scored, key=lambda x: x[0], reverse=True)[:k]
        if not ranked:
            return RetrievalResult(status="empty", backend=self.backend, query=query)
        return RetrievalResult(
            status="ok", backend=f"{self.backend}+{backend_name()}", query=query,
            items=[RetrievedChunk(
                document_id=str(r.id), title=r.title, excerpt=r.content[:600], source=r.source, url=r.url,
                doc_type=r.doc_type, role_family=r.role_family, tags=list(r.tags or []),
                score=sim,
            ) for sim, _, r in ranked],
        )

    async def corpus_size(self, db: AsyncSession) -> int:
        from sqlalchemy import func
        return (await db.execute(select(func.count(KnowledgeDocument.id)))).scalar() or 0

    # ---------------------------- pgvector (optional) ----------------------------

    def _get_vector_store(self):
        if self._vector_store is None:
            from langchain_aws import BedrockEmbeddings
            from langchain_community.vectorstores import PGVector
            embeddings = BedrockEmbeddings(model_id="amazon.titan-embed-text-v2:0",
                                           region_name=os.getenv("AWS_REGION", "us-east-1"))
            self._vector_store = PGVector(
                connection_string=settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql"),
                embedding_function=embeddings, collection_name="career_resources", use_jsonb=True,
            )
        return self._vector_store

    def _pgvector_add(self, doc_type, title, content, source, role_family) -> None:
        from langchain_core.documents import Document
        store = self._get_vector_store()
        store.add_documents([
            Document(page_content=c, metadata={"title": title, "source": source, "type": doc_type, "role_family": role_family})
            for c in _split(content)
        ])

    def _pgvector_retrieve(self, query: str, k: int) -> RetrievalResult:
        try:
            results = self._get_vector_store().similarity_search_with_score(query=query, k=k)
        except Exception as exc:
            return RetrievalResult(status="unavailable", backend="pgvector", query=query,
                                   error=f"pgvector retrieval failed: {exc.__class__.__name__}")
        if not results:
            return RetrievalResult(status="empty", backend="pgvector", query=query)
        return RetrievalResult(status="ok", backend="pgvector", query=query, items=[
            RetrievedChunk(document_id=str(i), title=d.metadata.get("title", "Document"), excerpt=d.page_content[:600],
                           source=d.metadata.get("source", "knowledge base"), doc_type=d.metadata.get("type", "document"),
                           role_family=d.metadata.get("role_family"), score=round(float(s), 4))
            for i, (d, s) in enumerate(results)
        ])


# Singleton instance (no I/O at import time)
kb = CareerKnowledgeBase()
