"""Prompt templates for the issue triage agent.

All prompts use inspect.cleandoc so they can be indented naturally
alongside surrounding code without sending leading whitespace to the LLM.
"""

from inspect import cleandoc

_COMMENT_BODY_LIMIT = 300
_FIRST_COMMENT_BODY_LIMIT = 1000


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

    Examples:
    - "App crashes on startup after latest update" → regression, critical
    - "Add support for dark mode" → feature_request, low
    - "How do I configure X?" → question, low
    - "Memory usage grows unbounded over time" → performance, high
    - "Login fails for all SSO users, no workaround exists" → bug, critical
    - "Typo in README installation section" → documentation, low
    - "Occasional stutter during video playback on slow connections" → performance, medium
    - "Feature X behaviour changed silently in v2.1, breaking integrations" → regression, high
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
    state of a repository's most recently active open issues for a maintainer.

    Rules:
    - 2-3 sentences, plain text only
    - Do not include a title, heading, or label of any kind — start directly with the summary
    - Do not open with the repository name or a restatement of what this is
    - Begin with the most important signal: what is the dominant pattern or concern right now?
    - Reference that this reflects recent activity, not the full issue history
    - Highlight urgency distribution and notable patterns such as clusters of regressions,
      security concerns, or many unanswered questions suggesting documentation gaps
""")


def _format_first_comment(comment: dict) -> str:
    """Formats the first comment with a higher character limit.

    The first comment is frequently a maintainer reproducing the issue or
    providing triage context, making it the highest-signal comment in the
    thread. It is given a larger character budget than subsequent comments.

    Args:
        comment: An IssueComment dict with author and body fields.

    Returns:
        A formatted string for the first comment.
    """
    body = comment["body"]
    if len(body) > _FIRST_COMMENT_BODY_LIMIT:
        body = body[:_FIRST_COMMENT_BODY_LIMIT] + "... [truncated]"
    return f"  [{comment['author']}]: {body}"


def _format_remaining_comments(comments: list[dict]) -> str:
    """Formats all comments after the first with a standard character limit.

    Args:
        comments: A list of IssueComment dicts with author and body fields.

    Returns:
        A formatted string of comments.
    """
    parts = []
    for comment in comments:
        body = comment["body"]
        if len(body) > _COMMENT_BODY_LIMIT:
            body = body[:_COMMENT_BODY_LIMIT] + "... [truncated]"
        parts.append(f"  [{comment['author']}]: {body}")
    return "\n".join(parts)


def _format_comments(comments: list[dict]) -> str:
    """Formats a list of comments into a readable block for LLM prompts.

    The first comment receives a higher character limit than subsequent ones,
    as it most often contains the highest-signal context for classification.

    Args:
        comments: A list of IssueComment dicts with author and body fields.

    Returns:
        A formatted string of comments, or a placeholder if the list is empty.
    """
    if not comments:
        return "(no comments)"

    parts = [_format_first_comment(comments[0])]
    if len(comments) > 1:
        remaining = _format_remaining_comments(comments[1:])
        if remaining:
            parts.append(remaining)
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
