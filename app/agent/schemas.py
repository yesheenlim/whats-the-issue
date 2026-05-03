from typing import Literal, Optional

from pydantic import BaseModel


class ClassifyOutput(BaseModel):
    type: Literal["bug", "feature_request", "question", "documentation", "regression", "performance", "other"]
    urgency: Literal["critical", "high", "medium", "low"]


class SummarizeOutput(BaseModel):
    summary: str


class IssueOutput(BaseModel):
    number: int
    title: str
    url: str
    type: str
    urgency: str
    labels: list[str]
    reactions: int
    comments: int
    age_days: int
    assignees: list[str]
    summary: Optional[str] = None


class TriageReport(BaseModel):
    repository: str
    generated_at: str
    issues_analyzed: int
    repo_summary: str
    sections: dict[str, list[IssueOutput]]
