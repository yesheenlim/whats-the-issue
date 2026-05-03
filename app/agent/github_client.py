"""GitHub API client for fetching and preprocessing issues and comments."""

import asyncio
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from app.agent.schemas import IssueComment, RawIssue

logger = logging.getLogger(__name__)

_GITHUB_API_BASE = "https://api.github.com"
_GITHUB_API_VERSION = "2022-11-28"


def parse_repo_url(url: str) -> tuple[str, str]:
    """Parses a GitHub repository URL into owner and repo name.

    Args:
        url: Full GitHub repository URL, e.g. https://github.com/owner/repo.

    Returns:
        A tuple of (owner, repo).

    Raises:
        ValueError: If the URL does not contain exactly two path segments.
    """
    path = urlparse(url).path.strip("/")
    parts = path.split("/")
    if len(parts) != 2:
        raise ValueError(
            f"Expected a URL of the form https://github.com/owner/repo, got: {url}"
        )
    return parts[0], parts[1]


def _build_headers(github_token: str) -> dict[str, str]:
    """Builds the standard GitHub API request headers.

    Args:
        github_token: A GitHub personal access token.

    Returns:
        A dict of HTTP headers.
    """
    return {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": _GITHUB_API_VERSION,
    }


def _preprocess_issue(issue: dict, body_limit: int) -> dict:
    """Extracts and normalises relevant fields from a raw GitHub issue dict.

    Args:
        issue: Raw issue dict as returned by the GitHub REST API.
        body_limit: Maximum number of characters to retain from the body.

    Returns:
        A dict conforming to the RawIssue shape (without recent_comments,
        which is populated separately).
    """
    body = issue.get("body") or ""
    if len(body) > body_limit:
        body = body[:body_limit] + "... [truncated]"

    created_at = issue.get("created_at", "")
    age_days = 0
    if created_at:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - created).days

    reactions = issue.get("reactions", {})
    reaction_count = (
        reactions.get("total_count", 0) if isinstance(reactions, dict) else 0
    )

    return {
        "number": issue["number"],
        "title": issue["title"],
        "body": body,
        "url": issue["html_url"],
        "labels": [label["name"] for label in issue.get("labels", [])],
        "reactions": reaction_count,
        "comment_count": issue.get("comments", 0),
        "recent_comments": [],  # populated by _fetch_comments
        "age_days": age_days,
        "assignees": [a["login"] for a in issue.get("assignees", [])],
        "milestone": issue["milestone"]["title"] if issue.get("milestone") else None,
    }


async def _fetch_raw_issues(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    headers: dict[str, str],
    top_k_issues: int,
) -> list[dict]:
    """Fetches open issues sorted by most recent activity.

    Filters out pull requests, which the GitHub issues endpoint includes.

    Args:
        client: An open httpx.AsyncClient.
        owner: Repository owner.
        repo: Repository name.
        headers: GitHub API headers.
        top_k_issues: Maximum number of issues to return.

    Returns:
        A list of raw issue dicts from the GitHub API.

    Raises:
        httpx.HTTPStatusError: On non-2xx responses from the GitHub API.
    """
    response = await client.get(
        f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/issues",
        headers=headers,
        params={
            "state": "open",
            "sort": "updated",
            "direction": "desc",
            "per_page": min(top_k_issues, 100),
        },
    )
    response.raise_for_status()
    raw = response.json()
    issues_only = [i for i in raw if "pull_request" not in i]
    return issues_only[:top_k_issues]


async def _fetch_comments(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    issue_number: int,
    top_n_comments: int,
    headers: dict[str, str],
) -> list[IssueComment]:
    """Fetches the most recent comments for a single issue.

    GitHub's issue comments API returns comments in ascending creation order.
    This function fetches the first page and takes the last top_n_comments
    entries, which correspond to the most recent activity.

    Args:
        client: An open httpx.AsyncClient.
        owner: Repository owner.
        repo: Repository name.
        issue_number: The issue number to fetch comments for.
        top_n_comments: Maximum number of comments to return.
        headers: GitHub API headers.

    Returns:
        A list of IssueComment dicts with author and body fields.

    Raises:
        httpx.HTTPStatusError: On non-2xx responses from the GitHub API.
    """
    response = await client.get(
        f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}/comments",
        headers=headers,
        params={"per_page": 100},  # fetch up to 100, slice from end
    )
    response.raise_for_status()
    comments = response.json()
    recent = comments[-top_n_comments:] if len(comments) > top_n_comments else comments
    return [
        IssueComment(author=c["user"]["login"], body=c["body"] or "")
        for c in recent
    ]


async def fetch_issues(
    github_url: str,
    github_token: str,
    top_k_issues: int,
    top_n_comments: int,
    body_limit: int,
) -> list[RawIssue]:
    """Fetches, preprocesses, and returns open issues with recent comments.

    Issues are sorted by most recent activity (updated_at). Comments are
    fetched concurrently for all issues after the issue list is retrieved.

    Args:
        github_url: Full URL of the GitHub repository.
        github_token: Personal access token for GitHub API authentication.
        top_k_issues: Maximum number of issues to fetch.
        top_n_comments: Maximum number of recent comments to fetch per issue.
        body_limit: Character limit applied to each issue body before sending
            to the LLM.

    Returns:
        A list of RawIssue dicts ready for the classify node.

    Raises:
        ValueError: If github_url cannot be parsed as a GitHub repository URL.
        httpx.HTTPStatusError: On non-2xx responses from the GitHub API.
    """
    owner, repo = parse_repo_url(github_url)
    headers = _build_headers(github_token)

    async with httpx.AsyncClient() as client:
        raw_issues = await _fetch_raw_issues(
            client, owner, repo, headers, top_k_issues
        )
        logger.info(
            "Fetched %d issues from %s/%s", len(raw_issues), owner, repo
        )

        comment_lists = await asyncio.gather(
            *[
                _fetch_comments(
                    client, owner, repo, issue["number"], top_n_comments, headers
                )
                for issue in raw_issues
            ]
        )
        logger.info("Fetched comments for %d issues", len(raw_issues))

    preprocessed = []
    for issue, comments in zip(raw_issues, comment_lists):
        data = _preprocess_issue(issue, body_limit)
        data["recent_comments"] = comments
        preprocessed.append(data)

    return preprocessed
