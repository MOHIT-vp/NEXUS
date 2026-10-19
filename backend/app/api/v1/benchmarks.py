"""
Skill benchmark library — the Placement Cell's editable source of truth for
what each target role requires (doc §9.12: "keep skill benchmarks current").

The Skill Gap Agent reads these rows on every run, so an edit applies to the
next analysis. Every change is audited with its before/after values.
"""
import uuid
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, require_role
from app.core.roles import ROLE_CATALOG
from app.models.company import SkillBenchmark
from app.models.user import User
from app.models.workflow import AuditLog
from app.services.reference_data import get_or_create_skill

router = APIRouter(prefix="/benchmarks", tags=["Skill Benchmarks"])

LEVELS = ("beginner", "intermediate", "advanced", "expert")
IMPORTANCE_WEIGHT = {"required": 1.0, "preferred": 0.5}


def _row(b: SkillBenchmark) -> Dict[str, Any]:
    return {"id": str(b.id), "skill": b.skill.name if b.skill else "?", "expected_level": b.expected_level,
            "importance": "required" if float(b.weight or 1) >= 1 else "preferred", "source": b.source,
            "updated_at": (b.updated_at or b.created_at).isoformat() if (b.updated_at or b.created_at) else None}


class BenchmarkIn(BaseModel):
    skill: str = Field(..., min_length=1, max_length=100)
    expected_level: str = "intermediate"
    importance: str = "required"
    source: Optional[str] = Field(None, max_length=100)

    @field_validator("expected_level")
    @classmethod
    def _level(cls, v: str) -> str:
        if v.lower() not in LEVELS:
            raise ValueError(f"Level must be one of {', '.join(LEVELS)}")
        return v.lower()

    @field_validator("importance")
    @classmethod
    def _importance(cls, v: str) -> str:
        if v.lower() not in IMPORTANCE_WEIGHT:
            raise ValueError("Importance must be 'required' or 'preferred'")
        return v.lower()


class BenchmarkPatch(BaseModel):
    expected_level: Optional[str] = None
    importance: Optional[str] = None
    source: Optional[str] = Field(None, max_length=100)

    _level = field_validator("expected_level")(lambda cls, v: BenchmarkIn._level(v) if v else v)
    _importance = field_validator("importance")(lambda cls, v: BenchmarkIn._importance(v) if v else v)


def _default_source(officer: User) -> str:
    return f"Placement Cell ({officer.full_name}), {date.today().isoformat()}"[:100]


def _audit(db: AsyncSession, officer: User, action: str, b_id: uuid.UUID, details: Dict[str, Any]) -> None:
    db.add(AuditLog(actor_id=officer.id, actor_type="placement_officer", action=action, entity_type="skill_benchmark",
                    entity_id=b_id, correlation_id=uuid.uuid4(), details=details))


@router.get("", response_model=List[Dict[str, Any]])
async def list_benchmarks(officer: User = Depends(require_role("placement_officer", "admin")),
                          db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(SkillBenchmark).options(selectinload(SkillBenchmark.skill)))).scalars().all()
    by_role: Dict[str, List[Dict[str, Any]]] = {}
    for b in rows:
        by_role.setdefault(b.role_family, []).append(_row(b))
    order = {"required": 0, "preferred": 1}
    return [{"role_key": key, "title": meta["title"],
             "skills": sorted(by_role.get(key, []), key=lambda r: (order[r["importance"]], r["skill"].lower()))}
            for key, meta in ROLE_CATALOG.items()]


@router.post("/{role_key}", status_code=201)
async def add_benchmark(role_key: str, body: BenchmarkIn, officer: User = Depends(require_role("placement_officer")),
                        db: AsyncSession = Depends(get_db)):
    if role_key not in ROLE_CATALOG:
        raise HTTPException(status_code=404, detail="Unknown role.")
    skill = await get_or_create_skill(db, body.skill.strip())
    exists = (await db.execute(select(SkillBenchmark).where(
        SkillBenchmark.role_family == role_key, SkillBenchmark.skill_id == skill.id))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail=f"{skill.name} is already in this role's benchmark — edit it instead.")
    b = SkillBenchmark(role_family=role_key, skill_id=skill.id, expected_level=body.expected_level,
                       weight=IMPORTANCE_WEIGHT[body.importance], source=(body.source or _default_source(officer)))
    db.add(b)
    await db.flush()
    _audit(db, officer, "BENCHMARK_ADDED", b.id, {"role": role_key, "skill": skill.name,
                                                  "expected_level": body.expected_level, "importance": body.importance})
    await db.commit()
    b = (await db.execute(select(SkillBenchmark).options(selectinload(SkillBenchmark.skill))
                          .where(SkillBenchmark.id == b.id))).scalar_one()
    return _row(b)


async def _get(db: AsyncSession, item_id: uuid.UUID) -> SkillBenchmark:
    b = (await db.execute(select(SkillBenchmark).options(selectinload(SkillBenchmark.skill))
                          .where(SkillBenchmark.id == item_id))).scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=404, detail="Benchmark not found.")
    return b


@router.patch("/item/{item_id}")
async def update_benchmark(item_id: uuid.UUID, body: BenchmarkPatch,
                           officer: User = Depends(require_role("placement_officer")), db: AsyncSession = Depends(get_db)):
    b = await _get(db, item_id)
    before = _row(b)
    if body.expected_level:
        b.expected_level = body.expected_level
    if body.importance:
        b.weight = IMPORTANCE_WEIGHT[body.importance]
    b.source = body.source.strip() if body.source and body.source.strip() else _default_source(officer)
    after = {**before, "expected_level": b.expected_level,
             "importance": "required" if float(b.weight) >= 1 else "preferred", "source": b.source}
    _audit(db, officer, "BENCHMARK_UPDATED", b.id, {"role": b.role_family, "skill": before["skill"],
                                                    "before": {k: before[k] for k in ("expected_level", "importance", "source")},
                                                    "after": {k: after[k] for k in ("expected_level", "importance", "source")}})
    await db.commit()
    return _row(await _get(db, item_id))


@router.delete("/item/{item_id}", status_code=204)
async def remove_benchmark(item_id: uuid.UUID, officer: User = Depends(require_role("placement_officer")),
                           db: AsyncSession = Depends(get_db)):
    b = await _get(db, item_id)
    _audit(db, officer, "BENCHMARK_REMOVED", b.id, {"role": b.role_family, **_row(b)})
    await db.delete(b)
    await db.commit()
    return None
