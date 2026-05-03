# What's The Issue?

Agentic GitHub issue analysis API. Point it at a public repository and get a structured,
prioritized summary of open issues, organized by urgency so you know what to look at first.

## Prerequisites

- Docker + Docker Compose, or Python 3.11+
- A GitHub personal access token ([create one here](https://github.com/settings/tokens) — read-only `public_repo` scope is sufficient)
- An API key for your chosen LLM provider

## Setup

```bash
git clone https://github.com/yesheenlim/whats-the-issue.git
cd whats-the-issue
cp .env.example .env
```

Edit `.env`:
- Setup LLM endpoint:
  - Here you want to set up `LLM_PROVIDER`, `LLM_MODEL` and the API keys.
  - Currently we only support `gemini`, `claude` and `openai`.
- Then you may also want to setup the number of characters in the GH issue
body to truncate for the classification and summarization step,
to control token costs.

## Running

### Docker (recommended)

```bash
docker compose up --build
```

The API will be available at `http://localhost:8000`.

### Locally (not tested)

```bash
pip install -e .
uvicorn app.main:app --reload
```

## LLMs

Currently we support Gemini, OpenAI and Claude endpoints.

This repo has been tested on:

`openai`:
- `gpt-4o`

`claude`:
- `claude-sonnet-4-20250514`
- `claude-haiku-4-5-20251001`
- `claude-sonnet-4-6`

## Frontend UI (optional)

A frontend UI for interacting with the API is available in the `./ui` folder.
It runs as a separate Docker Compose service and connects to the API running on `localhost:8000`.

```bash
cd ui
docker compose up --build
```

Refer to `./ui/README.md` for setup details.

## Usage

You submit a repository URL and get back a thread ID, then poll until the result is ready.

### 1. Submit a repository for analysis

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Token: ghp_yourtoken" \
  -d '{
    "github_url": "https://github.com/owner/repo",
    "top_k_issues": 25,
    "top_n_comments": 5
  }'
```

- `top_k_issues` — how many issues to analyse, sorted by most recent activity. Defaults to 50.
- `top_n_comments` — how many recent comments to include per issue. Defaults to 5.

Response:

```json
{
  "thread_id": "3f91a847-...",
  "status": "pending"
}
```

### 2. Poll for results using the thread ID

```bash
curl http://localhost:8000/analyze/3f91a847-...
```

Response while running:

```json
{
  "thread_id": "3f91a847-...",
  "status": "running",
  "result": null,
  "error": null
}
```

Response when complete:

```json
{
  "thread_id": "3f91a847-...",
  "status": "complete",
  "result": {
    "repository": "owner/repo",
    "generated_at": "2026-05-03T09:00:00+00:00",
    "issues_analyzed": 25,
    "repo_summary": "The repository has 2 critical security issues requiring immediate attention, alongside several high-priority regressions with no known workarounds. A large volume of unanswered questions suggests gaps in the documentation.",
    "sections": {
      "critical": [
        {
          "number": 1234,
          "title": "Auth tokens leaked in logs on failed login",
          "url": "https://github.com/owner/repo/issues/1234",
          "issue_type": "bug",
          "urgency": "critical",
          "summary": "Authentication tokens are exposed in plaintext logs when login fails, affecting all self-hosted deployments running v2.3+.",
          "labels": ["bug", "security"],
          "reactions": 14,
          "comment_count": 8,
          "age_days": 3,
          "assignees": []
        }
      ],
      "high": [...],
      "medium": [
        {
          "number": 1201,
          "title": "Add dark mode support",
          "url": "https://github.com/owner/repo/issues/1201",
          "issue_type": "feature_request",
          "urgency": "medium",
          "summary": null,
          "labels": ["enhancement"],
          "reactions": 4,
          "comment_count": 2,
          "age_days": 30,
          "assignees": []
        }
      ],
      "low": [...]
    }
  }
}
```

### Output structure

| Field | Description |
|---|---|
| `repo_summary` | 2-3 sentence prose overview of the repository's issue landscape |
| `sections.critical` | Security issues, data loss, complete breakage — includes AI summary |
| `sections.high` | Significant breakage with no workaround — includes AI summary |
| `sections.medium` | Bugs with workarounds, popular feature requests — metadata only |
| `sections.low` | Minor improvements, questions, cosmetic issues — metadata only |

### Issue fields

| Field | Description |
|---|---|
| `number` | GitHub issue number |
| `title` | Original issue title |
| `url` | Link to the issue on GitHub |
| `issue_type` | `bug` `feature_request` `question` `documentation` `regression` `performance` `other` |
| `urgency` | `critical` `high` `medium` `low` |
| `summary` | AI-generated summary (critical and high only) |
| `labels` | GitHub labels attached to the issue |
| `reactions` | Total reaction count (proxy for community demand) |
| `comment_count` | Number of comments on the issue |
| `age_days` | Days since the issue was opened |
| `assignees` | GitHub usernames assigned to the issue |

### Job statuses

| Status | Meaning |
|---|---|
| `pending` | Job accepted, not yet started |
| `running` | Agent is processing |
| `complete` | Analysis finished, result available |
| `failed` | Something went wrong, check the `error` field |

## API Docs

Interactive docs are available at `http://localhost:8000/docs` when the server is running.
