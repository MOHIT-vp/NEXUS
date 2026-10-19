"""
Connector hub — the single surface agents use to reach data (Lab 5).

Graph nodes are synchronous and run in a worker thread (asyncio.to_thread), so
the API event loop is not blocked. The hub runs each async connector call back
on the API event loop with its own database session. Agents look the hub up
with get_hub(state); tests register an in-memory replacement.
"""
import asyncio
import threading
import uuid
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, List, Optional

CALL_TIMEOUT_SECONDS = 60


class DatabaseConnectorHub:
    def __init__(self, loop: asyncio.AbstractEventLoop, actor_id: str = "system"):
        self.loop = loop
        self.actor_id = actor_id
        self.calls: List[str] = []

    def _run(self, name: str, fn: Callable[[Any], Any]) -> Any:
        from app import database  # resolved at call time so tests can swap the session factory

        async def runner():
            async with database.async_session_factory() as session:
                return await fn(session)

        self.calls.append(name)
        return asyncio.run_coroutine_threadsafe(runner(), self.loop).result(timeout=CALL_TIMEOUT_SECONDS)

    def consent_status(self, student_id: str) -> Dict[str, Dict[str, Any]]:
        from app.connectors.student_connector import StudentConnector
        return self._run("student.consent", lambda db: StudentConnector(db, self.actor_id)
                         .get_consent_status(uuid.UUID(student_id)))

    def coding_platform(self, student_id: str, platform: str, handle: Optional[str]) -> Dict[str, Any]:
        from app.connectors.coding_connector import CodingConnector
        return self._run(f"coding.{platform}", lambda db: CodingConnector(db, self.actor_id)
                         .get_platform_data(uuid.UUID(student_id), platform, handle))

    def role_requirements(self, target_roles: List[str]) -> List[Dict[str, Any]]:
        from app.connectors.role_connector import RoleConnector
        return self._run("roles.requirements", lambda db: RoleConnector(db, self.actor_id).get_role_requirements(target_roles))

    def active_jobs(self) -> List[Dict[str, Any]]:
        from app.connectors.job_connector import JobConnector
        return self._run("jobs.active", lambda db: JobConnector(db, self.actor_id).list_active_jobs())

    def retrieve(self, query: str, *, role_families: Optional[List[str]] = None,
                 doc_types: Optional[List[str]] = None, k: int = 5):
        from app.connectors.knowledge_connector import KnowledgeConnector
        return self._run("knowledge.retrieve", lambda db: KnowledgeConnector(db, self.actor_id).retrieve(
            query, role_families=role_families, doc_types=doc_types, k=k))


    def similar_prior_students(self, student_id: str, query_text: str, k: int = 5) -> List[Dict[str, Any]]:
        from app.connectors.knowledge_connector import KnowledgeConnector
        return self._run("knowledge.similar_students", lambda db: KnowledgeConnector(db, self.actor_id)
                         .similar_prior_students(uuid.UUID(student_id), query_text, k))


_HUBS: Dict[str, Any] = {}
_LOCK = threading.Lock()


class HubUnavailableError(RuntimeError):
    pass


@contextmanager
def registered_hub(run_id: str, hub: Any) -> Iterator[Any]:
    with _LOCK:
        _HUBS[run_id] = hub
    try:
        yield hub
    finally:
        with _LOCK:
            _HUBS.pop(run_id, None)


def get_hub(state: Dict[str, Any]) -> Any:
    with _LOCK:
        hub = _HUBS.get(str(state.get("run_id") or ""))
    if hub is None:
        raise HubUnavailableError("No connector hub registered for this run")
    return hub
