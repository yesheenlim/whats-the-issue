"""TypedDicts and Pydantic models for the issue triage pipeline.

Defines three layers:
  - TypedDicts for data flowing between LangGraph nodes (RawIssue,
    ClassifiedIssue, SummarizedIssue).
  - Pydantic BaseModels for LLM structured output (ClassifyOutput,
    SummarizeOutput).
  - Pydantic BaseModels for API output (IssueOutput, TriageReport).
"""

from typing import Literal, TypedDict

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Pipeline TypedDicts
# ---------------------------------------------------------------------------


class IssueComment(TypedDict):
    """A single comment fetched from a GitHub issue."""

    author: str
    body: str


class RawIssue(TypedDict):
    """A preprocessed GitHub issue as returned by the fetch node."""

    number: int
    title: str
    body: str
    url: str
    labels: list[str]
    reactions: int
    comment_count: int
    recent_comments: list[IssueComment]
    age_days: int
    assignees: list[str]
    milestone: str | None


class ClassifiedIssue(RawIssue):
    """A RawIssue with LLM-assigned type and urgency."""

    issue_type: str
    urgency: str


class SummarizedIssue(ClassifiedIssue):
    """A ClassifiedIssue with an optional AI-generated summary."""

    summary: str | None


# ---------------------------------------------------------------------------
# LLM structured output schemas
# ---------------------------------------------------------------------------


class ClassifyOutput(BaseModel):
    """Structured output schema for the classification LLM call."""

    issue_type: Literal[
        "bug",
        "feature_request",
        "question",
        "documentation",
        "regression",
        "performance",
        "other",
    ]
    urgency: Literal["critical", "high", "medium", "low"]


class SummarizeOutput(BaseModel):
    """Structured output schema for the summarization LLM call."""

    summary: str


# ---------------------------------------------------------------------------
# API output schemas
# ---------------------------------------------------------------------------


class IssueOutput(BaseModel):
    """A fully processed issue included in the triage report."""

    number: int
    title: str
    url: str
    issue_type: str
    urgency: str
    labels: list[str]
    reactions: int
    comment_count: int
    age_days: int
    assignees: list[str]
    summary: str | None = None


class TriageReport(BaseModel):
    """The complete triage report returned to the caller."""

    repository: str
    generated_at: str
    issues_analyzed: int
    repo_summary: str
    sections: dict[str, list[IssueOutput]]
