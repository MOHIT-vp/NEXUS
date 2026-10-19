"""
Chat API endpoint — NEXUS AI Assistant.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.api.deps import get_current_student
from app.database import get_db
from app.models.user import Student
from app.models.workflow import WorkflowRun
from app.config import settings

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
    if settings.LLM_PROVIDER.lower() == "google":
        return ChatGoogleGenerativeAI(
            model=settings.LLM_MODEL, 
            api_key=settings.LLM_API_KEY, 
            temperature=0.7
        )
    else:
        return ChatOpenAI(
            model=settings.LLM_MODEL, 
            api_key=settings.LLM_API_KEY, 
            temperature=0.7
        )

SYSTEM_PROMPT_TEMPLATE = """
You are NEXUS AI, the intelligent placement and career assistant for the NEXUS platform.
Your job is to guide students and answer their questions about their placement readiness, skills, coding performance, companies, skill gaps, roadmap, and placement process.

Rules:
1. Be encouraging, professional, and clear. Use markdown formatting to make your responses readable.
2. If you are provided with the student's assessment context, USE IT to give personalized answers.
3. DO NOT hallucinate or invent data. If you don't know something or it's missing from the context, say so.
4. If the user asks general career questions, provide helpful guidance.
5. If the user asks non-career questions, politely redirect them to placement/career topics.
6. Keep your answers concise and readable. Do not dump raw JSON.

{assessment_context}
"""

@router.post("", response_model=ChatResponse)
async def chat_with_nexus_ai(
    request: ChatRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Career assistant for the signed-in student. It only ever sees that student's own published plan."""
    assessment_context = ""

    if request.run_id:
        try:
            import uuid
            # Ensure it's a valid UUID
            run_uuid = uuid.UUID(request.run_id)
            
            # Retrieve the workflow run to check status
            stmt = select(WorkflowRun).where(WorkflowRun.id == run_uuid)
            result = await db.execute(stmt)
            run = result.scalar_one_or_none()
            
            if run and run.student_id != student.id:
                run = None  # another student's run: ignore it, never use its data
            if run:
                if run.status not in ("published", "approved"):
                    # The run is not yet published/approved.
                    return ChatResponse(response="Your assessment is currently under placement-cell review. Once it is approved and published, I'll be able to help you interpret your results.")
                elif run.result_snapshot:
                    # Add snapshot to context
                    import json
                    assessment_context = f"\nStudent's Assessment Data (JSON):\n{json.dumps(run.result_snapshot, indent=2)}"
        except Exception as e:
            print(f"Error retrieving context for run {request.run_id}: {e}")
            pass
    
    if not assessment_context:
        assessment_context = "\nNote: No active assessment data is available for this student right now. Give general advice."

    system_prompt = SYSTEM_PROMPT_TEMPLATE.replace("{assessment_context}", assessment_context)
    
    messages = [SystemMessage(content=system_prompt)]
    
    # Append history
    for msg in request.history:
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            messages.append(AIMessage(content=msg.content))
            
    # Append current message
    messages.append(HumanMessage(content=request.message))
    
    try:
        llm = get_llm()
        ai_response = await llm.ainvoke(messages)
        return ChatResponse(response=ai_response.content)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to generate AI response.")
