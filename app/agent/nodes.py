import asyncio
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
    ClassifyOutput,
    IssueOutput,
    SummarizeOutput,
    TriageReport,
)
from app.config import LLMProvider, Settings

URGENCY_LEVELS = ["critical", "high", "medium", "low"]
NEEDS_SUMMARY = {"critical", "high"}


def make_fetch_node(settings: Settings):
    async def fetch_node(state: dict) -> dict:
        issues = await fetch_issues(
            github_url=state["github_url"],
            github_token=state["github_token"],
            top_k=state["top_k"],
            body_limit=settings.BODY_TRUNCATION_SUMMARIZE,
        )
        return {"raw_issues": issues}

    return fetch_node


def make_classify_node(llm: BaseChatModel, provider: LLMProvider, settings: Settings):
    structured_llm = with_structure(llm, ClassifyOutput)

    async def classify_single(issue: dict) -> dict:
        messages = build_messages(
            CLASSIFY_SYSTEM,
            classify_prompt(issue, settings.BODY_TRUNCATION_CLASSIFY),
            provider,
        )
        try:
            result: ClassifyOutput = await structured_llm.ainvoke(messages)
            return {**issue, "type": result.type, "urgency": result.urgency}
        except Exception:
            return {**issue, "type": "other", "urgency": "medium"}

    async def classify_node(state: dict) -> dict:
        classified = await asyncio.gather(*[classify_single(issue) for issue in state["raw_issues"]])
        return {"classified_issues": list(classified)}

    return classify_node


def make_summarize_node(llm: BaseChatModel, provider: LLMProvider):
    structured_llm = with_structure(llm, SummarizeOutput)

    async def summarize_single(issue: dict) -> dict:
        messages = build_messages(SUMMARIZE_SYSTEM, summarize_prompt(issue), provider)
        try:
            result: SummarizeOutput = await structured_llm.ainvoke(messages)
            return {**issue, "summary": result.summary}
        except Exception:
            return {**issue, "summary": ""}

    async def summarize_node(state: dict) -> dict:
        to_summarize = [i for i in state["classified_issues"] if i.get("urgency") in NEEDS_SUMMARY]
        rest = [i for i in state["classified_issues"] if i.get("urgency") not in NEEDS_SUMMARY]
        summarized = await asyncio.gather(*[summarize_single(i) for i in to_summarize])
        return {"summarized_issues": list(summarized) + rest}

    return summarize_node


def make_repo_summary_node(llm: BaseChatModel, provider: LLMProvider):
    async def repo_summary_node(state: dict) -> dict:
        issues = state["summarized_issues"]
        counts: dict[str, int] = {k: 0 for k in URGENCY_LEVELS}
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
        messages = build_messages(REPO_SUMMARY_SYSTEM, prompt, provider)
        response = await llm.ainvoke(messages)
        return {"repo_summary": extract_text(response).strip()}

    return repo_summary_node


def make_format_node():
    def format_node(state: dict) -> dict:
        repo = urlparse(state["github_url"]).path.strip("/")
        sections: dict[str, list] = {k: [] for k in URGENCY_LEVELS}

        for issue in state["summarized_issues"]:
            urgency = issue.get("urgency", "medium")
            if urgency not in sections:
                urgency = "medium"

            output = IssueOutput(
                number=issue["number"],
                title=issue["title"],
                url=issue["url"],
                type=issue.get("type", "other"),
                urgency=urgency,
                labels=issue.get("labels", []),
                reactions=issue.get("reactions", 0),
                comments=issue.get("comments", 0),
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
        return {"output": report.model_dump()}

    return format_node
