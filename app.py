from flask import Flask, render_template, jsonify, request
from collections import defaultdict
from datetime import date

app = Flask(__name__)

# Pens & limits
PENS = ["GG5", "Alask Thunder", "Purple Punch", "Crystal OG"]
DAILY_LIMIT = 45
TOTAL_LIMIT = 640

# In-memory counters
total_hits = defaultdict(int)
daily_hits = defaultdict(lambda: defaultdict(int))  # daily_hits[pen][YYYY-MM-DD] -> count

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
    total_hits[pen] += 1
    daily_hits[pen][today] += 1
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

    return jsonify({"status": "ok"})

@app.route("/stats")
def stats():
    today = str(date.today())
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
    app.run(debug=True)

