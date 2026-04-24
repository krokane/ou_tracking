# MLB O/U Tracker

A personal dashboard for tracking MLB win total and playoff bets across a group. Pulls live standings from the MLB Stats API, auto-resolves bets as the season progresses, and shows per-bettor P&L summaries.

## Live Site

| URL | Access |
|---|---|
| `https://ou-tracking.fly.dev` | Private (password required) |
| `https://ou-tracking.fly.dev/public` | Public read-only |

## Features

- **Two bet types** — win totals (over/under a win number) and playoff bets (will/won't win division or make playoffs)
- **Live standings** — fetches current standings from the MLB Stats API on demand, with division and wild card badges
- **Auto-resolution** — pending bets are automatically marked win/loss/push as the season plays out
- **Per-bettor summaries** — actual P&L, amount at risk, and projected profit based on current pace
- **Pace tracking** — shows each team's current win pace next to the bet
- **Public view** — read-only dashboard at `/public`, no login required
- **Private view** — full add/edit/delete access behind a password at `/`

## Tech Stack

- **Backend** — Python, Flask, SQLite
- **Frontend** — Vanilla JS, plain CSS (no frameworks)
- **Data** — [MLB Stats API](https://statsapi.mlb.com)
- **Package manager** — [uv](https://github.com/astral-sh/uv)

## Running Locally

Install [uv](https://github.com/astral-sh/uv), then:

```bash
uv run python main.py
```

App runs at `http://localhost:5001`. Default password is `changeme` — change it via the `APP_PASSWORD` environment variable before sharing with anyone.

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `APP_PASSWORD` | Password for the private view | `changeme` |
| `SECRET_KEY` | Flask session secret | `dev-only-secret-change-in-prod` |
| `PORT` | Port to listen on | `5001` |

Set them before running:
```bash
APP_PASSWORD=yourpassword SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))') uv run python main.py
```
