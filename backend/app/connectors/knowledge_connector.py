"""Governed connector over the career knowledge base (Lab 4 retrieval through the Lab 5 connector)."""
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from app.agents.knowledge_base import RetrievalResult, kb
from app.connectors.base import BaseConnector


class KnowledgeConnector(BaseConnector):
    async def retrieve(self, query: str, *, role_families: Optional[List[str]] = None,
                       doc_types: Optional[List[str]] = None, k: int = 5) -> RetrievalResult:
        return await kb.retrieve(self.db, query, role_families=role_families, doc_types=doc_types, k=k)

    async def similar_prior_students(self, student_id: uuid.UUID, query_text: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Anonymised history retrieval: other students' PUBLISHED plans closest to this
        student's profile. Returns no names or ids — only similarity, roles, overlap
        and how their plan turned out, for "students like you" insights.
        """
        from app.models.workflow import Version
        from app.services.similarity import cosine, embed, profile_text, related_threshold
        q = embed(query_text)
        rows = (await self.db.execute(select(Version).where(
            Version.entity_type == "readiness_plan", Version.status == "published", Version.student_id != student_id,
        ).order_by(Version.created_at.desc()).limit(500))).scalars().all()
        latest: Dict[Any, Version] = {}
        for v in rows:
            latest.setdefault(v.student_id, v)
        query_skills = {w.lower() for w in query_text.split()}
        scored = []
        for v in latest.values():
            snap = v.snapshot or {}
            skills = [s.get("name", "") for s in (snap.get("student_profile") or {}).get("skills", [])]
            roles = snap.get("target_roles") or []
            if not skills:
                continue
            sim = cosine(q, embed(profile_text(skills, roles)))
            if sim < related_threshold():
                continue
            summary = snap.get("summary") or {}
            scored.append({
                "similarity": sim,
                "target_roles": roles,
                "shared_skills": sorted({s for s in skills if s.lower() in query_skills})[:8],
                "readiness_percentage": summary.get("readiness_percentage"),
                "top_gaps": [g.get("skill") for g in (snap.get("skill_gap_report") or {}).get("required_gaps", [])][:3],
            })
        return sorted(scored, key=lambda x: x["similarity"], reverse=True)[:k]
