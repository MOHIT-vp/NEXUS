"""Evidence records behind a run's plan (Lab 9), with ownership checks."""
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import can_view_run, get_current_user, get_db
from app.models.user import User
from app.models.workflow import WorkflowRun

router = APIRouter(prefix="/evidence", tags=["Evidence"])


class EvidenceResponse(BaseModel):
    run_id: str
    total_records: int
    records: List[Dict[str, Any]]


@router.get("/{run_id}", response_model=EvidenceResponse)
async def get_workflow_evidence(
    run_id: uuid.UUID,
    entity_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Students see evidence only for their own published plan; the Placement Cell for any run."""
    run = (await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))).scalar_one_or_none()
    if run is None or not await can_view_run(db, current_user, run):
        raise HTTPException(status_code=404, detail="Workflow run not found")
    if current_user.role == "student" and run.status not in ("published", "approved"):
        raise HTTPException(status_code=404, detail="Evidence is available once the Placement Cell publishes the plan")
    records = (run.result_snapshot or {}).get("evidence_records", [])
    if entity_type:
        records = [r for r in records if r.get("entity_type") == entity_type]
    return {"run_id": str(run.id), "total_records": len(records), "records": records}
