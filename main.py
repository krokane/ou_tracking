"""
MLB Over/Under Bet Tracker — Flask backend.
Run: uv run python main.py
"""

import json
import os
import sys
from functools import wraps
from pathlib import Path

from flask import (Flask, jsonify, redirect, render_template,
                   render_template_string, request, session, url_for)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "bets.db"
STANDINGS_PATH = DATA_DIR / "standings.json"

app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-secret-change-in-prod")
APP_PASSWORD   = os.environ.get("APP_PASSWORD", "changeme")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>MLB O/U Tracker — Login</title>
  <style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{background:#0d1117;color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         display:flex;align-items:center;justify-content:center;min-height:100vh}
    .card{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:36px;width:100%;max-width:360px;margin:16px}
    h1{font-size:20px;font-weight:700;margin-bottom:20px;display:flex;align-items:center;gap:8px}
    .btn-public{display:block;background:#1c2128;border:1px solid #30363d;border-radius:6px;
                padding:12px;text-align:center;text-decoration:none;color:#e6edf3;
                font-size:14px;font-weight:600;transition:background .15s}
    .btn-public:hover{background:#262d36}
    .public-sub{font-size:12px;color:#7d8590;text-align:center;margin-top:6px;margin-bottom:20px}
    .divider{display:flex;align-items:center;gap:10px;margin-bottom:20px}
    .divider::before,.divider::after{content:'';flex:1;height:1px;background:#30363d}
    .divider span{font-size:11px;color:#7d8590;white-space:nowrap}
    label{display:block;font-size:11px;font-weight:600;color:#7d8590;text-transform:uppercase;letter-spacing:.04em;margin-bottom:5px}
    input[type=password]{width:100%;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#e6edf3;
                         padding:9px 12px;font-size:14px;font-family:inherit;margin-bottom:16px}
    input[type=password]:focus{outline:none;border-color:#2f81f7}
    button{width:100%;background:#2f81f7;color:#fff;border:none;border-radius:6px;padding:10px;
           font-size:14px;font-weight:600;cursor:pointer;font-family:inherit}
    button:hover{background:#1a6ed8}
    .error{background:rgba(248,81,73,.15);color:#f85149;border:1px solid rgba(248,81,73,.3);
           border-radius:6px;padding:10px 14px;font-size:13px;margin-bottom:16px}
  </style>
</head>
<body>
  <div class="card">
    <h1>⚾ MLB O/U Tracker</h1>
    <a href="/public" class="btn-public">View Dashboard</a>
    <p class="public-sub">Read-only · No login required</p>
    <div class="divider"><span>or sign in for full access</span></div>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="post">
      <label for="pw">Password</label>
      <input id="pw" name="password" type="password" autofocus autocomplete="current-password"/>
      <button type="submit">Sign in</button>
    </form>
  </div>
</body>
</html>
"""

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        if request.form.get("password") == APP_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        error = "Incorrect password."
    return render_template_string(LOGIN_HTML, error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_db():
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DATA_DIR.mkdir(exist_ok=True)
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            team        TEXT    NOT NULL,
            bettor      TEXT    NOT NULL,
            over_under  TEXT    NOT NULL CHECK(over_under IN ('over','under')),
            ou_number   REAL    NOT NULL DEFAULT 0,
            line        REAL    NOT NULL,
            amount      REAL    NOT NULL DEFAULT 0,
            bet_type    TEXT    NOT NULL DEFAULT 'win_total',
            designation TEXT,
            result      TEXT    NOT NULL DEFAULT 'pending'
                        CHECK(result IN ('pending','win','loss','push')),
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    # Migrations for existing databases
    for stmt in [
        "ALTER TABLE bets ADD COLUMN amount REAL NOT NULL DEFAULT 0",
        "ALTER TABLE bets ADD COLUMN bet_type TEXT NOT NULL DEFAULT 'win_total'",
        "ALTER TABLE bets ADD COLUMN designation TEXT",
    ]:
        try:
            conn.execute(stmt)
        except Exception:
            pass  # column already exists
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Result logic
# ---------------------------------------------------------------------------

def calculate_win_total_result(over_under: str, ou_number: float, wins: int, games_played: int) -> str:
    games_remaining = max(0, 162 - games_played)
    is_half_line = (ou_number % 1 != 0)

    if over_under == "over":
        if wins > ou_number:
            return "win"
        if games_remaining == 0:
            return "push" if (not is_half_line and wins == ou_number) else "loss"
        if wins + games_remaining < ou_number:
            return "loss"
        if wins + games_remaining == ou_number and is_half_line:
            return "loss"
        return "pending"
    else:
        if wins > ou_number:
            return "loss"
        if games_remaining == 0:
            return "push" if (not is_half_line and wins == ou_number) else "win"
        if wins + games_remaining < ou_number:
            return "win"
        return "pending"


def compute_playoff_picture(standings: list) -> tuple:
    """Returns (div_winner_ids, all_playoff_ids) as sets of team_ids."""
    al_divs = {"American League East", "American League Central", "American League West"}
    nl_divs = {"National League East", "National League Central", "National League West"}

    div_winner_ids = set()
    playoff_ids = set()

    for league_divs in [al_divs, nl_divs]:
        by_div = {}
        for t in standings:
            if t["division"] in league_divs:
                by_div.setdefault(t["division"], []).append(t)

        others = []
        for div_teams in by_div.values():
            if div_teams:
                div_winner_ids.add(div_teams[0]["team_id"])
                playoff_ids.add(div_teams[0]["team_id"])
                others.extend(div_teams[1:])

        others.sort(key=lambda t: t["wins"] / max(t["wins"] + t["losses"], 1), reverse=True)
        for t in others[:3]:
            playoff_ids.add(t["team_id"])

    return div_winner_ids, playoff_ids


def update_bet_results(standings: list) -> list:
    team_map = {t["team"]: t for t in standings}
    div_winner_ids, playoff_ids = compute_playoff_picture(standings)

    conn = get_db()
    pending = conn.execute("SELECT * FROM bets WHERE result = 'pending'").fetchall()
    updated = []

    for row in pending:
        bet = dict(row)
        team_data = team_map.get(bet["team"])
        if not team_data:
            continue

        bet_type = bet.get("bet_type") or "win_total"

        if bet_type == "win_total":
            new_result = calculate_win_total_result(
                bet["over_under"], bet["ou_number"],
                team_data["wins"], team_data["games_played"],
            )
        else:  # playoff bet — settle only when team's season is over
            games_remaining = max(0, 162 - team_data.get("games_played", 0))
            if games_remaining > 0:
                new_result = "pending"
            else:
                tid = team_data["team_id"]
                desig = bet.get("designation")
                ou = bet.get("over_under", "over")
                if desig == "wins_division":
                    achieved = tid in div_winner_ids
                elif desig == "makes_playoffs":
                    achieved = tid in playoff_ids
                else:
                    new_result = "pending"
                    achieved = None
                if achieved is not None:
                    if ou == "under":
                        new_result = "loss" if achieved else "win"
                    else:
                        new_result = "win" if achieved else "loss"

        if new_result != "pending":
            conn.execute("UPDATE bets SET result = ? WHERE id = ?", (new_result, bet["id"]))
            updated.append(bet["id"])

    conn.commit()
    conn.close()
    return updated


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
@login_required
def index():
    return render_template("index.html", readonly=False)


@app.route("/public")
def public_view():
    return render_template("index.html", readonly=True)


@app.route("/api/bets", methods=["GET"])
def list_bets():
    conn = get_db()
    rows = conn.execute("SELECT * FROM bets ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/bets", methods=["POST"])
@login_required
def create_bet():
    data = request.get_json(force=True)
    bet_type = data.get("bet_type", "win_total")

    if bet_type == "win_total":
        required = ["team", "bettor", "over_under", "ou_number", "line", "amount"]
    else:
        required = ["team", "bettor", "designation", "line", "amount"]

    for field in required:
        if data.get(field) is None or data.get(field) == "":
            return jsonify({"error": f"Missing required field: {field}"}), 400

    conn = get_db()
    cur = conn.execute(
        """INSERT INTO bets (team, bettor, over_under, ou_number, line, amount, bet_type, designation)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["team"],
            data["bettor"],
            data.get("over_under", "over"),  # dummy for playoff bets
            float(data.get("ou_number", 0)),
            float(data["line"]),
            float(data.get("amount", 0)),
            bet_type,
            data.get("designation"),
        ),
    )
    bet_id = cur.lastrowid
    conn.commit()
    bet = dict(conn.execute("SELECT * FROM bets WHERE id = ?", (bet_id,)).fetchone())
    conn.close()
    return jsonify(bet), 201


@app.route("/api/bets/<int:bet_id>", methods=["PATCH"])
@login_required
def update_bet(bet_id):
    data = request.get_json(force=True)
    allowed = {"team", "bettor", "over_under", "ou_number", "line", "amount", "designation"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": "No valid fields to update"}), 400
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn = get_db()
    conn.execute(
        f"UPDATE bets SET {set_clause} WHERE id = ?",
        list(updates.values()) + [bet_id],
    )
    conn.commit()
    row = conn.execute("SELECT * FROM bets WHERE id = ?", (bet_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(dict(row))


@app.route("/api/bets/<int:bet_id>", methods=["DELETE"])
@login_required
def delete_bet(bet_id):
    conn = get_db()
    conn.execute("DELETE FROM bets WHERE id = ?", (bet_id,))
    conn.commit()
    conn.close()
    return "", 204


@app.route("/api/standings")
def get_standings():
    if STANDINGS_PATH.exists():
        with open(STANDINGS_PATH) as f:
            return jsonify(json.load(f))
    return jsonify({"last_updated": None, "standings": []})


@app.route("/api/refresh", methods=["POST"])
@login_required
def trigger_refresh():
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    from refresh import fetch_standings  # noqa: PLC0415

    result = fetch_standings()
    if result is None:
        return jsonify({"error": "Failed to fetch standings from MLB API"}), 502

    updated_ids = update_bet_results(result["standings"])
    result["bets_updated"] = updated_ids
    return jsonify(result)


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=False, host="0.0.0.0", port=port)
