# What's The Issue?

Point it at a public repository and get a structured summary of what's happening in the open issues.

## Prerequisites

- Docker + Docker Compose, or Python 3.11+
- A GitHub personal access token ([create one here](https://github.com/settings/tokens) — read-only `public_repo` scope is sufficient)
- An API key for your chosen LLM provider

## Setup

```bash
git clone https://github.com/yourname/gh-triage
cd gh-triage
cp .env.example .env
```

Edit `.env`:

```env
LLM_PROVIDER=openai        # openai | gemini | claude
LLM_MODEL=gpt-4o

OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=            # only needed if LLM_PROVIDER=gemini
ANTHROPIC_API_KEY=         # only needed if LLM_PROVIDER=claude
```

## Running

### Docker (recommended)

```bash
docker compose up --build
```

The API will be available at `http://localhost:8000`.

### Locally

```bash
pip install -e .
uvicorn app.main:app --reload
```

## Usage

### 1. Submit a repository for analysis

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Token: ghp_yourtoken" \
  -d '{"github_url": "https://github.com/owner/repo"}'
```

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
    "messages": [
      { "type": "ai", "content": "..." }
    ]
  },
  "error": null
}
```

### Job statuses

| Status | Meaning |
|---|---|
| `pending` | Job accepted, not yet started |
| `running` | Agent is processing |
| `complete` | Analysis finished, results available |
| `failed` | Something went wrong, check the `error` field |

## API Docs

Interactive docs are available at `http://localhost:8000/docs` when the server is running.
