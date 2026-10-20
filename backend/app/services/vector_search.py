"""Vector search capabilities using pgvector and embeddings."""
import json
from typing import List, Dict, Any
from pgvector.sqlalchemy import Vector
from sqlalchemy import select, asc, text
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.config import settings

def get_embedder():
    """Configure the standard embedding model for the system."""
    key = settings.LLM_API_KEY
    if not settings._is_valid_key(key):
        pool = settings.get_pool_keys()
        if pool:
            key = pool[0]
        else:
            for ag in ("resume_agent", "job_matching_agent", "skill_gap_agent", "interview_agent"):
                cand = settings.get_agent_llm_config(ag).get("api_key")
                if settings._is_valid_key(cand):
                    key = cand
                    break
    return GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=key if settings._is_valid_key(key) else "dummy",
    )

async def generate_embedding(text: str) -> List[float]:
    """Generate a vector embedding for a piece of text (e.g. parsed resume or job spec)."""
    embedder = get_embedder()
    try:
        # In a real environment, you'd batch this, but for agents one-by-one is fine
        vector = await embedder.aembed_query(text)
        return vector
    except Exception as e:
        raise ValueError(f"Failed to generate embedding: {str(e)}")

async def search_similar_roles(db: AsyncSession, profile_vector: List[float], limit: int = 3) -> List[Dict[str, Any]]:
    """
    Lab 4: Similarity Retrieval.
    Performs a math-based cosine similarity search to find roles matching a student.
    We assume the `jobs` table has an `embedding` Vector column.
    """
    # Note: In Postgres, '<=>' is cosine distance for pgvector
    # Order by distance ASC (closest first).
    # Since we dynamically add embeddings, we'll write raw SQL for the search in this MVP
    # to avoid complex SQLAlchemy mapping for the dynamic column.
    
    query = text("""
        SELECT id, title, company_id, 1 - (embedding <=> :vector) as similarity
        FROM jobs
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> :vector ASC
        LIMIT :limit
    """)
    
    result = await db.execute(query, {"vector": str(profile_vector), "limit": limit})
    rows = result.fetchall()
    
    matches = []
    for row in rows:
        matches.append({
            "job_id": str(row.id),
            "title": row.title,
            "company_id": str(row.company_id),
            "similarity_score": round(float(row.similarity), 3)
        })
        
    return matches
