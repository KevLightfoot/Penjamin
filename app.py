import json
import os
import threading
from flask import Flask, render_template, jsonify, request
from collections import defaultdict
from datetime import date

app = Flask(__name__)

# Pens & limits
PENS = ["GG5", "Alask Thunder", "Purple Punch", "Crystal OG"]
DAILY_LIMIT = 45
TOTAL_LIMIT = 640

# Where to store data (env var lets you change path later if you add a Render Disk)
DATA_FILE = os.environ.get("DATA_FILE", "data.json")
_lock = threading.Lock()

# --- in-memory state (populated from JSON at startup) ---
total_hits = defaultdict(int)
daily_hits = defaultdict(lambda: defaultdict(int))  # daily_hits[pen][YYYY-MM-DD] -> count


def _to_plain(obj):
    """Convert nested defaultdicts to plain dicts for JSON dumping."""
    if isinstance(obj, defaultdict):
        obj = dict(obj)
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    return obj


def load_data():
    """Load counters from DATA_FILE if it exists."""
    if not os.path.exists(DATA_FILE):
        return
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # totals
        totals = data.get("total_hits", {})
        for pen, val in totals.items():
            total_hits[pen] = int(val)
        # dailies
        dailies = data.get("daily_hits", {})
        for pen, by_day in dailies.items():
            for day, val in by_day.items():
                daily_hits[pen][day] = int(val)
    except Exception as e:
        print(f"[WARN] Failed to load {DATA_FILE}: {e}")


def save_data():
    """Persist counters to DATA_FILE atomically."""
    tmp_path = DATA_FILE + ".tmp"
    payload = {
        "total_hits": _to_plain(total_hits),
        "daily_hits": _to_plain(daily_hits),
    }
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, DATA_FILE)


# Initialize from disk on startup
with _lock:
    load_data()
    # Ensure all pens exist in memory even if file was missing
    today = str(date.today())
    for p in PENS:
        _ = total_hits[p]       # touch
        _ = daily_hits[p][today]


@app.route("/")
def index():
    return render_template(
        "index.html",
        pens=PENS,
        daily_limit=DAILY_LIMIT,
        total_limit=TOTAL_LIMIT
    )


@app.route("/click", methods=["POST"])
def click():
    data = request.get_json(force=True)
    pen = data.get("pen")
    if pen not in PENS:
        return jsonify({"status": "error", "message": "Unknown pen"}), 400
    today = str(date.today())
    with _lock:
        total_hits[pen] += 1
        daily_hits[pen][today] += 1
        save_data()
    return jsonify({"status": "ok"})


@app.route("/adjust", methods=["POST"])
def adjust():
    """
    Body: { pen: str, daily: int (optional), total: int (optional) }
    Sets today's daily hits and/or overall total hits for the pen.
    """
    data = request.get_json(force=True)
    pen = data.get("pen")
    if pen not in PENS:
        return jsonify({"status": "error", "message": "Unknown pen"}), 400

    today = str(date.today())
    with _lock:
        if "daily" in data and data["daily"] is not None:
            try:
                d = max(int(data["daily"]), 0)
            except (TypeError, ValueError):
                return jsonify({"status": "error", "message": "Invalid daily value"}), 400
            daily_hits[pen][today] = d

        if "total" in data and data["total"] is not None:
            try:
                t = max(int(data["total"]), 0)
            except (TypeError, ValueError):
                return jsonify({"status": "error", "message": "Invalid total value"}), 400
            total_hits[pen] = t

        save_data()

    return jsonify({"status": "ok"})


@app.route("/stats")
def stats():
    today = str(date.today())
    with _lock:
        payload = {}
        for pen in PENS:
            d = daily_hits[pen][today]
            t = total_hits[pen]
            payload[pen] = {
                "daily": d,
                "daily_remaining": max(DAILY_LIMIT - d, 0),
                "total": t,
                "total_remaining": max(TOTAL_LIMIT - t, 0),
            }
    return jsonify({
        "limits": {"daily": DAILY_LIMIT, "total": TOTAL_LIMIT},
        "today": today,
        "stats": payload
    })


if __name__ == "__main__":
    # Local dev server; Render will use gunicorn via Procfile
    app.run(host="0.0.0.0", port=5000, debug=True)
