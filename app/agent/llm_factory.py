from langchain_core.language_models import BaseChatModel

from app.config import LLMProvider, Settings


def create_llm(settings: Settings) -> BaseChatModel:
    provider = settings.LLM_PROVIDER

    if provider == LLMProvider.OPENAI:
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=settings.OPENAI_API_KEY,
        )

    if provider == LLMProvider.GEMINI:
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not set")
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.LLM_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
        )

    if provider == LLMProvider.CLAUDE:
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=settings.LLM_MODEL,
            api_key=settings.ANTHROPIC_API_KEY,
        )

    raise ValueError(f"Unsupported LLM provider: {provider}")
