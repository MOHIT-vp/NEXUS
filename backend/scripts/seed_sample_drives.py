"""
Seed the five SAMPLE recruitment drives into the database (idempotent).

These are example companies for a demo/dev database — the placement cell adds
real drives from the Drives page. Dates are moved forward relative to today so
the samples are open and get matched.

    cd backend && venv/bin/python -m scripts.seed_sample_drives
"""
import asyncio
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, select  # noqa: E402

from app.database import async_session_factory  # noqa: E402
from app.models.company import Company, Job  # noqa: E402
from app.schemas.company import CompanyCreate  # noqa: E402
from app.services.drive_repository import create_drive  # noqa: E402
from scripts._sample_drives import SAMPLE_DRIVES  # noqa: E402

FIELDS = set(CompanyCreate.model_fields)


async def seed(db) -> int:
    created = 0
    for i, d in enumerate(SAMPLE_DRIVES):
        exists = (await db.execute(
            select(Job.id).join(Company, Company.id == Job.company_id)
            .where(func.lower(Company.name) == d["company_name"].lower(), Job.title == d["role_title"], Job.is_active.is_(True))
        )).first()
        if exists:
            continue
        drive_day = date.today() + timedelta(days=21 + 7 * i)
        data = {k: v for k, v in d.items() if k in FIELDS}
        data.update(name=d["company_name"], description=f"[Sample company] {d.get('description', '')}",
                    drive_date=drive_day.isoformat(), deadline=(drive_day - timedelta(days=7)).isoformat(),
                    status="upcoming" if d.get("status") != "active" else "active")
        await create_drive(db, CompanyCreate(**data))
        created += 1
    return created


async def _run() -> None:
    async with async_session_factory() as db:
        print(f"Sample drives created: {await seed(db)}")


if __name__ == "__main__":
    asyncio.run(_run())
