"""
Shared LLM factory with per-agent API key, provider, and model routing.

LLMs are never used for scores, eligibility, consent or validation.
Each agent can have its own dedicated API key, provider, and model configured
via environment variables (e.g. RESUME_AGENT_API_KEY, INTERVIEW_AGENT_API_KEY,
or LLM_API_KEYS pool) to prevent shared rate limits and quotas from blocking execution.
When no real key is configured for an agent, it returns None and falls back to
the deterministic path, labelled as such in the output.
"""
import os
import logging
from typing import Optional, Dict, Any, List

from app.config import settings

logger = logging.getLogger(__name__)

# Key rotation tracking for comma-separated multi-key agent configs
_agent_key_counters: Dict[str, int] = {}


def _detect_caller_agent() -> Optional[str]:
    """Inspect call stack to automatically detect which agent invoked get_chat_model."""
    try:
        import inspect
        stack = inspect.stack()
        for frame_info in stack[1:6]:
            fname = os.path.basename(frame_info.filename).lower()
            func = frame_info.function.lower()
            if "resume" in fname or "resume" in func:
                return "resume_agent"
            if "coding" in fname or "coding" in func:
                return "coding_analytics_agent"
            if "skill_gap" in fname or "skill_gap" in func:
                return "skill_gap_agent"
            if "job_matching" in fname or "matching" in func:
                return "job_matching_agent"
            if "interview" in fname or "interview" in func:
                if "mock" in fname or "mock" in func:
                    return "mock_interview"
                return "interview_agent"
            if "coordinator" in fname or "coordinator" in func or "planner" in fname:
                return "coordinator"
            if "practice" in fname or "practice" in func:
                return "mock_practice"
            if "chat" in fname or "chat" in func:
                return "chat"
    except Exception:
        pass
    return None


def _get_active_key(agent_name: str, key_string: str) -> str:
    """If comma-separated keys are provided for an agent, rotate through them across invocations."""
    if not key_string or "," not in key_string:
        return key_string.strip() if key_string else ""
    keys = [k.strip() for k in key_string.split(",") if settings._is_valid_key(k.strip())]
    if not keys:
        return key_string.strip()
    idx = _agent_key_counters.get(agent_name, 0)
    _agent_key_counters[agent_name] = idx + 1
    return keys[idx % len(keys)]


def get_agent_credentials(agent_name: Optional[str] = None) -> Dict[str, str]:
    """Return resolved credentials (provider, model, api_key, agent_name) for an agent."""
    resolved_name = agent_name or _detect_caller_agent() or "default"
    return settings.get_agent_llm_config(resolved_name)


def is_llm_enabled(agent_name: Optional[str] = None) -> bool:
    """Check whether LLM is enabled for an agent."""
    resolved_name = agent_name or _detect_caller_agent() or "default"
    return settings.is_agent_llm_enabled(resolved_name)


def get_chat_model(
    temperature: float = 0.2,
    agent_name: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Optional[object]:
    """
    Return a LangChain ChatModel instance configured for the specified agent.
    
    Resolution order:
    1. Explicit function arguments (`provider`, `model`, `api_key`)
    2. Agent-specific environment variables (e.g. RESUME_AGENT_API_KEY, RESUME_AGENT_PROVIDER)
    3. LLM_API_KEYS pool assignment
    4. Global defaults (LLM_API_KEY, LLM_PROVIDER, LLM_MODEL)
    
    Returns None if no valid API key is configured, triggering deterministic fallback.
    """
    resolved_agent = agent_name or _detect_caller_agent() or "default"
    cfg = settings.get_agent_llm_config(resolved_agent)

    p = (provider if provider is not None else (cfg.get("provider") or settings.LLM_PROVIDER or "google")).lower().strip()
    m = (model if model is not None else (cfg.get("model") or settings.LLM_MODEL or "")).strip()
    raw_key = api_key if api_key is not None else (cfg.get("api_key") or settings.LLM_API_KEY or "")
    k = _get_active_key(resolved_agent, raw_key)

    # Bedrock Converse requires AWS credentials rather than an API key
    if p == "bedrock":
        if not os.getenv("AWS_ACCESS_KEY_ID"):
            return None
        from langchain_aws import ChatBedrockConverse
        logger.info(f"[{resolved_agent}] Initialized Bedrock model '{m}' (temp={temperature})")
        return ChatBedrockConverse(
            model_id=m or "anthropic.claude-3-sonnet-20240229-v1:0",
            temperature=temperature,
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )

    # For all other providers, a valid key is required
    if not settings._is_valid_key(k):
        return None

    # Handle model name remapping if a non-existent or deprecated model is provided
    if p == "groq":
        # Map deprecated or invalid models to active Groq flagship model
        if not m or m in ("groq-compound", "default", "gemini-2.0-flash", "llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "llama-3.1-8b-instant", "llama3-70b-8192", "llama3-8b-8192"):
            m = "openai/gpt-oss-120b"
        from langchain_groq import ChatGroq
        masked = f"...{k[-4:]}" if len(k) >= 8 else "***"
        logger.info(f"[{resolved_agent}] Initialized Groq model='{m}', key='{masked}' (temp={temperature})")
        return ChatGroq(model=m, temperature=temperature, api_key=k)

    if p == "openai":
        if not m or m in ("default", "gemini-2.0-flash", "llama-3.3-70b-versatile"):
            m = "gpt-4o-mini"
        from langchain_openai import ChatOpenAI
        masked = f"...{k[-4:]}" if len(k) >= 8 else "***"
        logger.info(f"[{resolved_agent}] Initialized OpenAI model='{m}', key='{masked}' (temp={temperature})")
        return ChatOpenAI(model=m, temperature=temperature, api_key=k)

    if p in ("anthropic", "claude"):
        if not m or m in ("default", "gemini-2.0-flash"):
            m = "claude-3-5-sonnet-20241022"
        from langchain_anthropic import ChatAnthropic
        masked = f"...{k[-4:]}" if len(k) >= 8 else "***"
        logger.info(f"[{resolved_agent}] Initialized Anthropic model='{m}', key='{masked}' (temp={temperature})")
        return ChatAnthropic(model=m, temperature=temperature, api_key=k)

    # Default provider: Google Generative AI
    if not m or m in ("default", "llama-3.3-70b-versatile", "gpt-4o-mini"):
        m = "gemini-2.0-flash"
    from langchain_google_genai import ChatGoogleGenerativeAI
    masked = f"...{k[-4:]}" if len(k) >= 8 else "***"
    logger.info(f"[{resolved_agent}] Initialized Google model='{m}', key='{masked}' (temp={temperature})")
    return ChatGoogleGenerativeAI(model=m, temperature=temperature, google_api_key=k)
