"""LangGraph node classes for the issue triage pipeline.

Each node is implemented as a callable class, making dependencies explicit
and instances independently testable. Nodes are wired into the graph in
manager.py.
"""

import asyncio
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

from langchain_core.language_models import BaseChatModel

from app.agent.github_client import fetch_issues
from app.agent.llm_adapter import build_messages, extract_text, with_structure
from app.agent.prompts import (
    CLASSIFY_SYSTEM,
    REPO_SUMMARY_SYSTEM,
    SUMMARIZE_SYSTEM,
    classify_prompt,
    repo_summary_prompt,
    summarize_prompt,
)
from app.agent.schemas import (
    ClassifiedIssue,
    ClassifyOutput,
    IssueOutput,
    RawIssue,
    SummarizeOutput,
    SummarizedIssue,
    TriageReport,
)
from app.config import LLMProvider, Settings

logger = logging.getLogger(__name__)

_URGENCY_LEVELS = ["critical", "high", "medium", "low"]
_NEEDS_SUMMARY = frozenset({"critical", "high"})


class FetchNode:
    """Fetches open issues and their recent comments from GitHub."""

    def __init__(self, settings: Settings) -> None:
        """Initialises FetchNode.

        Args:
            settings: Application settings used for body truncation limits.
        """
        self._settings = settings

    async def __call__(self, state: dict) -> dict[str, list[RawIssue]]:
        """Fetches issues from GitHub and returns them as raw issue dicts.

        Args:
            state: The current AgentState.

        Returns:
            A partial state update with raw_issues populated.
        """
        issues = await fetch_issues(
            github_url=state["github_url"],
            github_token=state["github_token"],
            top_k_issues=state["top_k_issues"],
            top_n_comments=state["top_n_comments"],
            body_limit=self._settings.BODY_TRUNCATION_SUMMARIZE,
        )
        logger.info("Fetch node complete: %d issues retrieved", len(issues))
        return {"raw_issues": issues}


class ClassifyNode:
    """Classifies each issue by type and urgency using the LLM."""

    def __init__(
        self, llm: BaseChatModel, provider: LLMProvider, settings: Settings
    ) -> None:
        """Initialises ClassifyNode.

        Args:
            llm: The base language model.
            provider: The active LLM provider, used to build compatible messages.
            settings: Application settings used for body truncation limits.
        """
        self._structured_llm = with_structure(llm, ClassifyOutput)
        self._provider = provider
        self._settings = settings

    async def _classify_single(self, issue: RawIssue) -> ClassifiedIssue:
        """Classifies a single issue by type and urgency.

        Falls back to (other, medium) if the LLM call fails or returns None.

        Args:
            issue: A raw issue dict to classify.

        Returns:
            The issue dict extended with issue_type and urgency fields.
        """
        messages = build_messages(
            CLASSIFY_SYSTEM,
            classify_prompt(issue, self._settings.BODY_TRUNCATION_CLASSIFY),
            self._provider,
        )
        try:
            result: ClassifyOutput | None = await self._structured_llm.ainvoke(
                messages
            )
            if result is None:
                raise ValueError("Structured output returned None")
            return {**issue, "issue_type": result.issue_type, "urgency": result.urgency}
        except Exception as exc:  # pylint: disable=broad-except
            # Broad catch is intentional: any LLM or parsing failure should
            # degrade gracefully rather than fail the entire batch.
            logger.warning(
                "Classification failed for issue #%d, applying defaults. Error: %s",
                issue["number"],
                exc,
            )
            return {**issue, "issue_type": "other", "urgency": "medium"}

    async def __call__(self, state: dict) -> dict[str, list[ClassifiedIssue]]:
        """Classifies all raw issues concurrently.

        Args:
            state: The current AgentState.

        Returns:
            A partial state update with classified_issues populated.
        """
        classified = await asyncio.gather(
            *[self._classify_single(issue) for issue in state["raw_issues"]]
        )
        logger.info("Classify node complete: %d issues classified", len(classified))
        return {"classified_issues": list(classified)}


class SummarizeNode:
    """Generates AI summaries for critical and high urgency issues."""

    def __init__(self, llm: BaseChatModel, provider: LLMProvider) -> None:
        """Initialises SummarizeNode.

        Args:
            llm: The base language model.
            provider: The active LLM provider, used to build compatible messages.
        """
        self._structured_llm = with_structure(llm, SummarizeOutput)
        self._provider = provider

    async def _summarize_single(self, issue: ClassifiedIssue) -> SummarizedIssue:
        """Generates a summary for a single issue.

        Falls back to an empty string if the LLM call fails or returns None.

        Args:
            issue: A classified issue dict to summarize.

        Returns:
            The issue dict extended with a summary field.
        """
        messages = build_messages(
            SUMMARIZE_SYSTEM, summarize_prompt(issue), self._provider
        )
        try:
            result: SummarizeOutput | None = await self._structured_llm.ainvoke(
                messages
            )
            if result is None:
                raise ValueError("Structured output returned None")
            return {**issue, "summary": result.summary}
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "Summarization failed for issue #%d. Error: %s",
                issue["number"],
                exc,
            )
            return {**issue, "summary": None}

    async def __call__(self, state: dict) -> dict[str, list[SummarizedIssue]]:
        """Summarizes critical and high urgency issues concurrently.

        Medium and low urgency issues are passed through without a summary.

        Args:
            state: The current AgentState.

        Returns:
            A partial state update with summarized_issues populated.
        """
        to_summarize = [
            i
            for i in state["classified_issues"]
            if i.get("urgency") in _NEEDS_SUMMARY
        ]
        rest = [
            {**i, "summary": None}
            for i in state["classified_issues"]
            if i.get("urgency") not in _NEEDS_SUMMARY
        ]
        summarized = await asyncio.gather(
            *[self._summarize_single(i) for i in to_summarize]
        )
        logger.info(
            "Summarize node complete: %d issues summarized", len(to_summarize)
        )
        return {"summarized_issues": list(summarized) + rest}


class RepoSummaryNode:
    """Generates a prose overview of the repository's issue landscape."""

    def __init__(self, llm: BaseChatModel, provider: LLMProvider) -> None:
        """Initialises RepoSummaryNode.

        Args:
            llm: The base language model.
            provider: The active LLM provider, used to build compatible messages.
        """
        self._llm = llm
        self._provider = provider

    async def __call__(self, state: dict) -> dict[str, str]:
        """Generates a short prose summary of the repository's open issues.

        Args:
            state: The current AgentState.

        Returns:
            A partial state update with repo_summary populated.
        """
        issues = state["summarized_issues"]
        counts: dict[str, int] = {k: 0 for k in _URGENCY_LEVELS}
        critical_titles: list[str] = []
        high_titles: list[str] = []

        for issue in issues:
            urgency = issue.get("urgency", "medium")
            counts[urgency] = counts.get(urgency, 0) + 1
            if urgency == "critical":
                critical_titles.append(issue["title"])
            elif urgency == "high":
                high_titles.append(issue["title"])

        repo = urlparse(state["github_url"]).path.strip("/")
        prompt = repo_summary_prompt(repo, counts, critical_titles, high_titles)
        messages = build_messages(REPO_SUMMARY_SYSTEM, prompt, self._provider)
        response = await self._llm.ainvoke(messages)
        summary = extract_text(response).strip()
        logger.info("Repo summary node complete")
        return {"repo_summary": summary}


class FormatNode:
    """Assembles the final TriageReport from summarized issues."""

    def __call__(self, state: dict) -> dict[str, dict]:
        """Builds and serializes the TriageReport.

        Args:
            state: The current AgentState.

        Returns:
            A partial state update with output populated.
        """
        repo = urlparse(state["github_url"]).path.strip("/")
        sections: dict[str, list] = {k: [] for k in _URGENCY_LEVELS}

        for issue in state["summarized_issues"]:
            urgency = issue.get("urgency", "medium")
            if urgency not in sections:
                urgency = "medium"

            output = IssueOutput(
                number=issue["number"],
                title=issue["title"],
                url=issue["url"],
                issue_type=issue.get("issue_type", "other"),
                urgency=urgency,
                labels=issue.get("labels", []),
                reactions=issue.get("reactions", 0),
                comment_count=issue.get("comment_count", 0),
                age_days=issue.get("age_days", 0),
                assignees=issue.get("assignees", []),
                summary=issue.get("summary"),
            )
            sections[urgency].append(output.model_dump())

        report = TriageReport(
            repository=repo,
            generated_at=datetime.now(timezone.utc).isoformat(),
            issues_analyzed=len(state["summarized_issues"]),
            repo_summary=state.get("repo_summary", ""),
            sections=sections,
        )
        logger.info(
            "Format node complete: report generated for %s", repo
        )
        return {"output": report.model_dump()}
