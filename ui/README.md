# What's The Issue? — UI

A lightweight web frontend for the agent API. Paste in a GitHub repo URL, enter your token, and get a structured summary of open issues — no setup beyond Docker required.

## Prerequisites

- Docker + Docker Compose
- The agent API running on port `8000` (see the main repo README)
- A GitHub personal access token ([create one here](https://github.com/settings/tokens) — read-only `public_repo` scope is sufficient)

## Usage

**Windows / Linux:**
```bash
docker compose up --build
```

**Mac:**
```bash
docker compose -f docker-compose.mac.yml up --build
```

Then open [http://localhost:3000](http://localhost:3000).

The API must already be running before you submit a job. The UI proxies all `/api/*` requests through to `http://host.docker.internal:8000`, which resolves to your host machine from inside the container.

## How it works

1. Enter your GitHub token and a repository URL (`https://github.com/owner/repo`)
2. Optionally set **Max Issues** (defaults to 50) and **Max Comments per Issue** to limit what the agent analyses
3. Click **Analyze Issues** — this submits a job to the API and returns a `thread_id`
4. The UI polls for results every 2.5 seconds and displays a live status indicator
5. When complete, results are shown in two tabs:
   - **Summary** — issues grouped by urgency (Critical / High / Medium / Low), each with title, type, age, comment count, and a written summary where available
   - **Raw JSON** — the full response payload, pretty-printed
6. Use the **Copy** button to copy the raw result to your clipboard

Job history is saved in your browser's `localStorage` and persists across page reloads. Any jobs still running when you closed the tab will resume polling automatically.

## Configuration

**API port** — if your API runs on a different port, update the `proxy_pass` line in `frontend/nginx.conf` (Windows/Linux) or `frontend/nginx.mac.conf` (Mac):

```nginx
proxy_pass http://host.docker.internal:YOUR_PORT/;
```

After any config change, rebuild using the appropriate command for your platform above.
