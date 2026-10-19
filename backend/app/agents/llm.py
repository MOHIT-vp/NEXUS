"""
Shared LLM factory for narration-only agent steps.

LLMs are never used for scores, eligibility, consent or validation. When no
real key is configured (``settings.llm_enabled`` is False) this returns None and
agents use their deterministic paths, labelled as such in the output.
"""
import os
from typing import Optional

from app.config import settings


def get_chat_model(temperature: float = 0.2) -> Optional[object]:
    if not settings.llm_enabled and settings.LLM_PROVIDER.lower() != "bedrock":
        return None
    provider = settings.LLM_PROVIDER.lower()
    if provider == "bedrock":
        if not os.getenv("AWS_ACCESS_KEY_ID"):
            return None
        from langchain_aws import ChatBedrockConverse
        return ChatBedrockConverse(model_id=settings.LLM_MODEL, temperature=temperature,
                                   region_name=os.getenv("AWS_REGION", "us-east-1"))
    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(model=settings.LLM_MODEL, temperature=temperature, api_key=settings.LLM_API_KEY)
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=settings.LLM_MODEL, temperature=temperature, api_key=settings.LLM_API_KEY)
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=settings.LLM_MODEL, temperature=temperature,
                                  google_api_key=settings.LLM_API_KEY)
