from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.config import LLMProvider


def build_messages(system: str, human: str, provider: LLMProvider) -> list:
    """
    Gemini does not handle SystemMessage reliably — merge into HumanMessage.
    OpenAI and Claude handle the system/human split natively.
    """
    if provider == LLMProvider.GEMINI:
        return [HumanMessage(content=f"{system}\n\n{human}")]
    return [SystemMessage(content=system), HumanMessage(content=human)]


def extract_text(message) -> str:
    """
    Normalize plain text responses across providers.
    Used only for the repo summary node which returns prose, not structured output.
    - OpenAI / Gemini: content is str
    - Claude: content can be list[{"type": "text", "text": "..."}]
    """
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)


def with_structure(llm: BaseChatModel, schema: type[BaseModel]) -> BaseChatModel:
    """
    Wrap an LLM with structured output for a given Pydantic schema.
    Uses native function calling on OpenAI and Claude, JSON mode on Gemini.
    """
    return llm.with_structured_output(schema)
