"""
Chat API endpoint — NEXUS AI Assistant.
"""
from typing import List, Optional
import json
import logging
import uuid
import traceback
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.api.deps import get_current_student
from app.database import get_db
from app.models.user import Student
from app.models.workflow import WorkflowRun
from app.config import settings
from app.agents.llm import get_chat_model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    run_id: Optional[str] = None
    message: str
    history: List[ChatMessage] = []

class ChatResponse(BaseModel):
    response: str

def get_llm():
    """Returns the chat LLM instance configured for the chat assistant."""
    llm = get_chat_model(temperature=0.7, agent_name="chat")
    if llm is None:
        raise HTTPException(
            status_code=503,
            detail="NEXUS AI Assistant is currently unavailable (no active API key configured)."
        )
    return llm

SYSTEM_PROMPT_TEMPLATE = """
You are NEXUS AI, the intelligent placement and career assistant for the NEXUS platform.
Your job is to guide students and answer their questions about their placement readiness, skills, coding performance, companies, skill gaps, roadmap, and placement process.

Formatting Rules:
1. Be encouraging, professional, and clear.
2. Structure your answers with clean bold headings, bullet points, and actionable next steps.
3. Do NOT output raw HTML tags (like `<br>` or `<div>`). Use standard Markdown only.
4. Keep tables concise (maximum 3-4 columns) or prefer structured bullet lists so content reads cleanly in the chat panel.
5. If provided with the student's assessment context, use it directly to provide specific, personalized answers (e.g. citing their specific gaps, coding analytics, or roadmap).
6. Keep answers concise, practical, and readable. Never dump raw JSON.

{assessment_context}
"""

def build_compact_assessment_context(snapshot: dict) -> str:
    """
    Extracts a dense, token-efficient summary of the student's assessment.
    Replaces 80KB+ raw JSON dumps with a ~500-token structured briefing,
    preventing 413 TPM token limit errors on LLM providers like Groq.
    """
    if not snapshot:
        return "No assessment data available."

    sections = []

    # 1. Student Profile
    prof = snapshot.get("student_profile") or {}
    profile_lines = []
    edu = prof.get("education") or {}
    degree = edu.get("degree") or ""
    inst = edu.get("institution") or ""
    gpa = edu.get("gpa")
    edu_parts = [p for p in [degree, inst] if p]
    edu_str = " at ".join(edu_parts)
    if gpa is not None:
        edu_str += f" (GPA: {gpa})"
    if edu_str:
        profile_lines.append(f"- **Education**: {edu_str}")

    skills = [s.get("name") if isinstance(s, dict) else str(s) for s in prof.get("skills", [])]
    skills = [s for s in skills if s]
    if skills:
        profile_lines.append(f"- **Claimed Skills ({len(skills)})**: {', '.join(skills[:25])}")

    projects = prof.get("projects") or []
    if projects:
        proj_list = []
        for p in projects[:3]:
            t = p.get("title", "Project")
            tech = p.get("technologies", [])[:3]
            proj_list.append(f"{t} ({', '.join(tech)})" if tech else t)
        profile_lines.append(f"- **Projects**: {'; '.join(proj_list)}")

    if profile_lines:
        sections.append("### Student Background\n" + "\n".join(profile_lines))

    # 2. Skill Gap Analysis
    gap_rep = snapshot.get("skill_gap_report") or {}
    if gap_rep:
        gap_lines = []
        cov = gap_rep.get("overall_coverage", 0)
        status = gap_rep.get("overall_assessment", "unknown")
        target_roles = gap_rep.get("target_roles") or snapshot.get("target_roles") or []
        gap_lines.append(f"- **Readiness**: Coverage: {cov}%, Assessment Tier: {status}")
        if target_roles:
            gap_lines.append(f"- **Target Roles**: {', '.join(target_roles)}")

        gaps = gap_rep.get("gaps") or []
        if gaps:
            gap_lines.append("- **Identified Gaps**:")
            for g in gaps[:8]:
                skill = g.get("skill", "Unknown")
                sev = (g.get("severity") or "medium").upper()
                curr = g.get("current_level", "missing")
                req = g.get("required_level", "intermediate")
                gap_lines.append(f"  * [{sev}] {skill}: current {curr} -> required {req}")

        strengths = gap_rep.get("strengths") or []
        if strengths:
            s_names = [s.get("skill", "") for s in strengths[:5] if s.get("skill")]
            if s_names:
                gap_lines.append(f"- **Key Strengths**: {', '.join(s_names)}")

        sections.append("### Skill Gap Analysis\n" + "\n".join(gap_lines))

    # 3. Coding Analytics
    coding = snapshot.get("coding_analytics") or {}
    coding_summary = coding.get("summary") or {}
    if coding_summary:
        c_lines = []
        if coding_summary.get("primary_language"):
            c_lines.append(f"- **Primary Language**: {coding_summary.get('primary_language')}")
        gh = coding_summary.get("github") or {}
        if gh:
            c_lines.append(f"- **GitHub**: {gh.get('public_repos', 0)} repos ({gh.get('recently_active_repos', 0)} active), Languages: {', '.join(gh.get('top_languages', [])[:4])}")
        lc = coding_summary.get("leetcode") or {}
        if lc:
            c_lines.append(f"- **LeetCode**: {lc.get('total_solved', 0)} solved (Easy: {lc.get('easy_solved', 0)}, Med: {lc.get('medium_solved', 0)}, Hard: {lc.get('hard_solved', 0)})")
        if c_lines:
            sections.append("### Coding Analytics\n" + "\n".join(c_lines))

    # 4. Job Matches
    matching = snapshot.get("matching_result") or {}
    matches = matching.get("matches") or []
    if matches:
        m_lines = []
        for m in matches[:4]:
            role = m.get("role_title") or m.get("role") or "Role"
            comp = m.get("company_name") or m.get("company") or ""
            fit = m.get("match_score") or m.get("fit_score") or m.get("score")
            label = f"{role} at {comp}" if comp else role
            fit_str = f" ({fit}% match)" if fit is not None else ""
            m_lines.append(f"- {label}{fit_str}")
        if m_lines:
            sections.append("### Matched Opportunities\n" + "\n".join(m_lines))

    # 5. Roadmap Priorities
    roadmap = snapshot.get("roadmap") or {}
    items = roadmap.get("items") or []
    if items:
        r_lines = []
        for it in items[:5]:
            title = it.get("title") or it.get("milestone") or "Goal"
            prio = it.get("priority", "medium")
            r_lines.append(f"- {title} (Priority: {prio})")
        sections.append("### Action Roadmap\n" + "\n".join(r_lines))

    # 6. Resume Perfection
    perf = snapshot.get("resume_perfection") or {}
    eval_ = perf.get("evaluation") or {}
    if eval_:
        p_lines = [
            f"- **Score**: {eval_.get('overall_score', 0)}% ({eval_.get('tier_label', 'Evaluated')})",
        ]
        recs = eval_.get("recommendations") or []
        if recs:
            p_lines.append(f"- **Interviewer Prep Tip**: {recs[0]}")
        sections.append("### Resume Perfection\n" + "\n".join(p_lines))

    compact_text = "\n\n".join(sections)
    # Hard cap at 3,500 characters (~850 tokens) to guarantee safety
    if len(compact_text) > 3500:
        compact_text = compact_text[:3500] + "\n...(summary truncated for length)"
    return compact_text


@router.post("", response_model=ChatResponse)
async def chat_with_nexus_ai(
    request: ChatRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Career assistant for the signed-in student. Sees the student's published plan in a token-efficient summary."""
    assessment_context = ""

    if request.run_id:
        try:
            run_uuid = uuid.UUID(request.run_id)
            
            # Retrieve the workflow run
            stmt = select(WorkflowRun).where(WorkflowRun.id == run_uuid)
            result = await db.execute(stmt)
            run = result.scalar_one_or_none()
            
            if run and run.student_id != student.id:
                run = None  # another student's run: ignore it, never use its data
            if run:
                if run.status not in ("published", "approved", "completed"):
                    return ChatResponse(
                        response="Your assessment is currently under placement-cell review. Once it is approved and published, I'll be able to help you interpret your results."
                    )
                elif run.result_snapshot:
                    # Build dense, token-efficient summary (replaces 80KB+ raw JSON)
                    compact_summary = build_compact_assessment_context(run.result_snapshot)
                    assessment_context = f"\nStudent's Verified Assessment Summary:\n{compact_summary}"
        except Exception as e:
            logger.warning(f"Error retrieving context for run {request.run_id}: {e}")
            pass
    
    if not assessment_context:
        assessment_context = "\nNote: No active assessment data is available for this student right now. Give general career and placement advice."

    system_prompt = SYSTEM_PROMPT_TEMPLATE.replace("{assessment_context}", assessment_context)
    
    messages = [SystemMessage(content=system_prompt)]
    
    # Append history (keep last 6 messages and limit length to prevent token overflow)
    for msg in request.history[-6:]:
        content = msg.content[:600] if len(msg.content) > 600 else msg.content
        if msg.role == "user":
            messages.append(HumanMessage(content=content))
        elif msg.role == "assistant":
            messages.append(AIMessage(content=content))
            
    # Append current message (capped at 1000 characters)
    user_msg = request.message[:1000] if len(request.message) > 1000 else request.message
    messages.append(HumanMessage(content=user_msg))
    
    try:
        llm = get_llm()
        ai_response = await llm.ainvoke(messages)
        return ChatResponse(response=ai_response.content)
    except Exception as e:
        logger.error(f"Error invoking chat LLM: {e}", exc_info=True)
        # Attempt fallback without detailed context if it was a rate limit / length error
        err_msg = str(e).lower()
        if "413" in err_msg or "rate_limit" in err_msg or "too large" in err_msg:
            try:
                minimal_messages = [
                    SystemMessage(content=(
                        "You are NEXUS AI, the student placement assistant. "
                        "Provide a concise, direct, helpful answer to the student's question."
                    )),
                    HumanMessage(content=user_msg),
                ]
                fallback_resp = await llm.ainvoke(minimal_messages)
                return ChatResponse(response=fallback_resp.content)
            except Exception as fallback_err:
                logger.error(f"Fallback chat LLM also failed: {fallback_err}")
        raise HTTPException(status_code=500, detail="Failed to generate AI response. Please try again.")
