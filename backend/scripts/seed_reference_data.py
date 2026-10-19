"""
Seed the skill-benchmark library and curated knowledge base (idempotent).

    cd backend && venv/bin/python -m scripts.seed_reference_data
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import async_session_factory  # noqa: E402
from app.services.reference_data import seed_reference_data  # noqa: E402


async def _run() -> None:
    async with async_session_factory() as db:
        result = await seed_reference_data(db)
    print(f"Benchmarks created: {result['benchmarks_created']}; knowledge chunks created: {result['knowledge_chunks_created']}")


if __name__ == "__main__":
    asyncio.run(_run())
