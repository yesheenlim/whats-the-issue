from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx


def parse_repo_url(url: str) -> tuple[str, str]:
    path = urlparse(url).path.strip("/")
    parts = path.split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid GitHub repo URL: {url}")
    return parts[0], parts[1]


def preprocess_issue(issue: dict, body_limit: int) -> dict:
    body = issue.get("body") or ""
    if len(body) > body_limit:
        body = body[:body_limit] + "... [truncated]"

    created_at = issue.get("created_at", "")
    age_days = 0
    if created_at:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - created).days

    reactions = issue.get("reactions", {})
    reaction_count = reactions.get("total_count", 0) if isinstance(reactions, dict) else 0

    return {
        "number": issue["number"],
        "title": issue["title"],
        "body": body,
        "url": issue["html_url"],
        "labels": [label["name"] for label in issue.get("labels", [])],
        "reactions": reaction_count,
        "comments": issue.get("comments", 0),
        "age_days": age_days,
        "assignees": [a["login"] for a in issue.get("assignees", [])],
        "milestone": issue["milestone"]["title"] if issue.get("milestone") else None,
    }


async def fetch_issues(
    github_url: str,
    github_token: str,
    top_k: int,
    body_limit: int,
) -> list[dict]:
    owner, repo = parse_repo_url(github_url)

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    params = {
        "state": "open",
        "sort": "updated",
        "direction": "desc",
        "per_page": min(top_k, 100),  # GitHub hard cap
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/issues",
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        raw_issues = response.json()

    # GitHub issues endpoint also returns PRs — filter them out
    issues_only = [i for i in raw_issues if "pull_request" not in i]

    return [preprocess_issue(issue, body_limit) for issue in issues_only[:top_k]]
