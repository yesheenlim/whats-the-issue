"""Prompt templates for the issue triage agent.

All prompts use inspect.cleandoc so they can be indented naturally
alongside surrounding code without sending leading whitespace to the LLM.
"""

from inspect import cleandoc

_COMMENT_BODY_LIMIT = 300

CLASSIFY_SYSTEM = cleandoc("""
    You are a GitHub issue triage assistant. Classify a single GitHub issue.

    Classify the type and urgency using these definitions:

    issue_type:
    - bug: something is broken or not working as expected
    - feature_request: a new capability being requested
    - question: user asking for help or clarification
    - documentation: docs are missing, wrong, or unclear
    - regression: something that used to work and no longer does
    - performance: slowness, memory, or resource usage issues
    - other: does not fit any of the above

    urgency:
    - critical: security vulnerabilities, data loss, complete breakage blocking all users
    - high: significant breakage affecting many users, no workaround available
    - medium: bugs with workarounds, meaningful feature requests with community demand
    - low: minor improvements, cosmetic issues, low-demand requests, general questions
""")

SUMMARIZE_SYSTEM = cleandoc("""
    You are a GitHub issue triage assistant. Summarize a GitHub issue for a maintainer.

    The summary must:
    - Be 1-2 sentences, under 60 words
    - State the core problem or request clearly
    - Mention impact or scope if evident
    - Be immediately useful to a maintainer skimming their backlog
""")

REPO_SUMMARY_SYSTEM = cleandoc("""
    You are a GitHub issue triage assistant. Write a brief prose summary of the overall
    state of a repository's open issues for a maintainer.

    2-3 sentences, plain text only.

    Highlight dominant issue types, urgency distribution, and any notable patterns such
    as clusters of regressions, security concerns, or many unanswered questions suggesting
    documentation gaps.
""")


def _format_comments(comments: list[dict]) -> str:
    """Formats a list of comments into a readable block for LLM prompts.

    Args:
        comments: A list of IssueComment dicts with author and body fields.

    Returns:
        A formatted string of comments, or a placeholder if the list is empty.
    """
    if not comments:
        return "(no comments)"
    parts = []
    for comment in comments:
        body = comment["body"]
        if len(body) > _COMMENT_BODY_LIMIT:
            body = body[:_COMMENT_BODY_LIMIT] + "... [truncated]"
        parts.append(f"  [{comment['author']}]: {body}")
    return "\n".join(parts)


def classify_prompt(issue: dict, body_limit: int) -> str:
    """Builds the user-turn prompt for issue classification.

    Args:
        issue: A RawIssue dict.
        body_limit: Maximum characters of issue body to include.

    Returns:
        A formatted prompt string.
    """
    body = (issue["body"] or "")[:body_limit] or "(no body provided)"
    labels = ", ".join(issue["labels"]) or "none"
    assignees = ", ".join(issue["assignees"]) or "none"
    comments = _format_comments(issue.get("recent_comments", []))

    return cleandoc(f"""
        Classify the following GitHub issue:

        Title: {issue["title"]}
        Labels: {labels}
        Reactions: {issue["reactions"]}
        Comment count: {issue["comment_count"]}
        Age (days): {issue["age_days"]}
        Assignees: {assignees}
        Milestone: {issue["milestone"] or "none"}

        Body:
        {body}

        Recent comments:
        {comments}
    """)


def summarize_prompt(issue: dict) -> str:
    """Builds the user-turn prompt for issue summarization.

    Args:
        issue: A ClassifiedIssue dict.

    Returns:
        A formatted prompt string.
    """
    labels = ", ".join(issue["labels"]) or "none"
    body = issue["body"] or "(no body provided)"
    comments = _format_comments(issue.get("recent_comments", []))

    return cleandoc(f"""
        Summarize the following GitHub issue:

        Title: {issue["title"]}
        Labels: {labels}
        Reactions: {issue["reactions"]}
        Comment count: {issue["comment_count"]}
        Age (days): {issue["age_days"]}

        Body:
        {body}

        Recent comments:
        {comments}
    """)


def repo_summary_prompt(
    repo: str,
    counts: dict[str, int],
    critical_titles: list[str],
    high_titles: list[str],
) -> str:
    """Builds the user-turn prompt for the repository-level summary.

    Args:
        repo: Repository name in owner/repo format.
        counts: Issue counts keyed by urgency level.
        critical_titles: Titles of all critical issues.
        high_titles: Titles of all high-priority issues.

    Returns:
        A formatted prompt string.
    """
    critical_list = "\n".join(f"- {t}" for t in critical_titles) or "none"
    high_list = "\n".join(f"- {t}" for t in high_titles) or "none"

    return cleandoc(f"""
        Repository: {repo}

        Issue counts by urgency:
        - Critical: {counts.get("critical", 0)}
        - High: {counts.get("high", 0)}
        - Medium: {counts.get("medium", 0)}
        - Low: {counts.get("low", 0)}

        Critical issues:
        {critical_list}

        High priority issues:
        {high_list}

        Write a brief summary of the current state of this repository's open issues.
    """)
