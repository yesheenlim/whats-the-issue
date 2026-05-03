"""Utilities for normalising LLM input and output across providers.

Different providers have incompatible expectations around message structure
and response content types. This module isolates all provider-specific
handling so that node logic remains provider-agnostic.
"""

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.config import LLMProvider

logger = logging.getLogger(__name__)


def build_messages(
    system: str, human: str, provider: LLMProvider
) -> list[HumanMessage | SystemMessage]:
    """Builds a message list compatible with the given LLM provider.

    Gemini does not handle SystemMessage reliably and requires all content
    to be passed as a single HumanMessage. OpenAI and Claude both support
    the system/human split natively.

    Args:
        system: The system prompt text.
        human: The user turn text.
        provider: The active LLM provider.

    Returns:
        A list of LangChain message objects.
    """
    if provider == LLMProvider.GEMINI:
        return [HumanMessage(content=f"{system}\n\n{human}")]
    return [SystemMessage(content=system), HumanMessage(content=human)]


def extract_text(message: Any) -> str:
    """Extracts plain text from an LLM response message.

    Handles the three different content shapes returned by supported providers:
    - OpenAI and Gemini: content is a plain str.
    - Claude: content can be list[{"type": "text", "text": "..."}].

    Args:
        message: A LangChain AI message object.

    Returns:
        The message content as a plain string.
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
    """Wraps an LLM with structured output enforcement for a Pydantic schema.

    Uses native function calling on OpenAI and Claude, and JSON schema mode
    on Gemini. The returned chain will raise or return None on schema
    violations depending on the provider — callers should guard against None.

    Args:
        llm: The base LangChain chat model.
        schema: A Pydantic BaseModel class defining the expected output shape.

    Returns:
        A LangChain runnable that returns instances of schema.
    """
    return llm.with_structured_output(schema)
