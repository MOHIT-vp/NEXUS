"""
Lab 8 — best-of-N: several roadmap candidates are built in parallel, each with a
different strategy, and a merge/selector keeps the one that best fits the
LOCKED plan. Selection is strictly by plan alignment (never by which reads
"nicest"); every candidate and its score is kept for the audit trail.

Plan alignment (100 points):
- required coverage (40): every required skill gap appears in the roadmap
- ordering (25): required gaps come before preferred / optional ones
- student priorities (15): what the student asked to focus on appears early
- timeline fit (20): total effort fits the plan's timeline at a sustainable pace
A candidate that drops a required gap is never selected while one that covers them all exists.
"""
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional

from app.core.skills import canonical

PRIORITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}
SUSTAINABLE_HOURS_PER_WEEK = 15


def _required(item: Dict[str, Any], required_gaps: set) -> bool:
    return canonical(item.get("addresses_gap") or item.get("skill") or "") in required_gaps


def _gaps_first(items, ctx):
    return sorted(items, key=lambda i: (not _required(i, ctx["required"]), -PRIORITY_RANK.get(i.get("priority"), 1)))


def _priorities_first(items, ctx):
    prio = ctx["priorities"]
    return sorted(items, key=lambda i: (canonical(i.get("skill", "")) not in prio and not i.get("student_priority"),
                                        not _required(i, ctx["required"]), -PRIORITY_RANK.get(i.get("priority"), 1)))


def _quick_wins_first(items, ctx):
    return sorted(items, key=lambda i: (not _required(i, ctx["required"]), i.get("estimated_hours", 10)))


def _fit_timeline(items, ctx):
    """Gaps-first, then drop optional items that don't fit the timeline budget."""
    ordered = _gaps_first(items, ctx)
    if not ctx["weeks"]:
        return ordered
    budget = ctx["weeks"] * SUSTAINABLE_HOURS_PER_WEEK
    kept, used = [], 0
    for i in ordered:
        h = i.get("estimated_hours", 10)
        if _required(i, ctx["required"]) or used + h <= budget:
            kept.append(i)
            used += h
    return kept


STRATEGIES: Dict[str, Callable[[List[Dict[str, Any]], Dict[str, Any]], List[Dict[str, Any]]]] = {
    "gaps_first": _gaps_first,
    "student_priorities_first": _priorities_first,
    "quick_wins_first": _quick_wins_first,
    "fit_timeline": _fit_timeline,
}


def plan_alignment(items: List[Dict[str, Any]], ctx: Dict[str, Any]) -> Dict[str, Any]:
    required = ctx["required"]
    covered = {canonical(i.get("addresses_gap") or i.get("skill") or "") for i in items}
    coverage = len(required & covered) / len(required) if required else 1.0

    flags = [_required(i, required) for i in items]
    pairs = good = 0
    for a in range(len(flags)):
        for b in range(a + 1, len(flags)):
            if flags[a] != flags[b]:
                pairs += 1
                good += flags[a]          # a required item before an optional one
    ordering = good / pairs if pairs else 1.0

    prio = ctx["priorities"]
    if prio and items:
        head = items[: max(1, len(items) // 3)]
        wanted = [i for i in items if canonical(i.get("skill", "")) in prio or i.get("student_priority")]
        priorities = (sum(1 for i in head if i in wanted) / min(len(wanted), len(head))) if wanted else 1.0
    else:
        priorities = 1.0

    hours = sum(i.get("estimated_hours", 0) for i in items)
    if ctx["weeks"]:
        budget = ctx["weeks"] * SUSTAINABLE_HOURS_PER_WEEK
        timeline = 1.0 if hours <= budget else max(0.0, budget / hours)
    else:
        timeline = 1.0

    breakdown = {"required_coverage": round(40 * coverage, 1), "ordering": round(25 * ordering, 1),
                 "student_priorities": round(15 * priorities, 1), "timeline_fit": round(20 * timeline, 1)}
    return {"score": round(sum(breakdown.values()), 1), "breakdown": breakdown,
            "covers_all_required": coverage == 1.0, "total_hours": hours}


def select_best_roadmap(items: List[Dict[str, Any]], gaps: List[Dict[str, Any]], priorities: List[str],
                        weeks: Optional[int]) -> Dict[str, Any]:
    """Build every candidate in parallel, score each against the plan, keep the best."""
    ctx = {
        "required": {canonical(g.get("skill", "")) for g in gaps
                     if g.get("importance", "required") == "required" and g.get("severity") != "none"},
        "priorities": {canonical(p) for p in priorities or []},
        "weeks": weeks,
    }
    with ThreadPoolExecutor(max_workers=len(STRATEGIES)) as pool:
        built = dict(zip(STRATEGIES, pool.map(lambda fn: fn(list(items), ctx), STRATEGIES.values())))

    candidates = []
    for name, cand in built.items():
        candidates.append({"strategy": name, "items": cand, **plan_alignment(cand, ctx)})
    # Never pick a candidate that drops a required gap if another covers them all; ties → less total effort
    candidates.sort(key=lambda c: (c["covers_all_required"], c["score"], -c["total_hours"]), reverse=True)
    best = candidates[0]
    return {
        "items": best["items"],
        "selection": {
            "method": "best_of_n_by_plan_alignment",
            "selected": best["strategy"],
            "score": best["score"],
            "candidates": [{k: v for k, v in c.items() if k != "items"} | {"items": len(c["items"])} for c in candidates],
        },
    }
