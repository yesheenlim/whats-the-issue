# What's The Issue? — UI

A lightweight web frontend for the agent API. Paste in a GitHub repo URL, enter your token, and get a structured summary of open issues — no setup beyond Docker required.

## Prerequisites

- Docker + Docker Compose
- The agent API running on port `8000` (see the main repo README)
- A GitHub personal access token ([create one here](https://github.com/settings/tokens) — read-only `public_repo` scope is sufficient)

## Usage

Start the UI:

```bash
docker compose up --build
```

Then open [http://localhost:3000](http://localhost:3000).

The API must already be running before you submit a job. The UI proxies all `/api/*` requests through to `http://host.docker.internal:8000`, which resolves to your host machine from inside the container.

## How it works

1. Enter your GitHub token and a repository URL (`https://github.com/owner/repo`)
2. Click **Analyze Issues** — this submits a job to the API and returns a `thread_id`
3. The UI polls for results every 2.5 seconds and displays a live status indicator
4. When complete, the full analysis is rendered with markdown formatting
5. Use the **Copy** button to copy the raw result to your clipboard

Job history is saved in `localStorage` and persists across page reloads. Any jobs that were still running when you closed the tab will resume polling automatically.

## Configuration

If your API runs on a different port, update the `proxy_pass` line in `frontend/nginx.conf`:

```nginx
proxy_pass http://host.docker.internal:YOUR_PORT/;
```

Then rebuild:

```bash
docker compose up --build
```

## Notes

- The GitHub token is only used client-side as a request header — it is never stored on disk or logged
- LLM provider keys live exclusively in the API's `.env` file and are never exposed to the browser
- `host.docker.internal` is Docker's built-in DNS for reaching the host machine; no extra network configuration is needed on Mac or Windows. On Linux, add `extra_hosts: ["host.docker.internal:host-gateway"]` to the `frontend` service in `docker-compose.yml`
