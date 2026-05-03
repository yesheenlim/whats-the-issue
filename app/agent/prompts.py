from inspect import cleandoc

CLASSIFY_SYSTEM = cleandoc("""
    You are a GitHub issue triage assistant. Classify a single GitHub issue.

    Classify the type and urgency using these definitions:

    type:
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


def classify_prompt(issue: dict, body_limit: int) -> str:
    body = (issue["body"] or "")[:body_limit] or "(no body provided)"
    labels = ", ".join(issue["labels"]) or "none"
    assignees = ", ".join(issue["assignees"]) or "none"

    return cleandoc(f"""
        Classify the following GitHub issue:

        Title: {issue["title"]}
        Labels: {labels}
        Reactions: {issue["reactions"]}
        Comments: {issue["comments"]}
        Age (days): {issue["age_days"]}
        Assignees: {assignees}
        Milestone: {issue["milestone"] or "none"}

        Body:
        {body}
    """)


def summarize_prompt(issue: dict) -> str:
    labels = ", ".join(issue["labels"]) or "none"
    body = issue["body"] or "(no body provided)"

    return cleandoc(f"""
        Summarize the following GitHub issue:

        Title: {issue["title"]}
        Labels: {labels}
        Reactions: {issue["reactions"]}
        Comments: {issue["comments"]}
        Age (days): {issue["age_days"]}

        Body:
        {body}
    """)


def repo_summary_prompt(
    repo: str,
    counts: dict[str, int],
    critical_titles: list[str],
    high_titles: list[str],
) -> str:
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
