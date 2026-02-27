from flask import Flask, jsonify, render_template, request, session
import re
import os
import glob
import sqlite3
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = "madlibs-secret-key-change-in-production"

STORIES_DIR = os.path.join(os.path.dirname(__file__), "stories")
DB_PATH     = os.path.join(os.path.dirname(__file__), "madlibs.db")

# ── All achievements ──────────────────────────────────────────────────────────
ACHIEVEMENTS = [
    # Word-choice based
    {"id": "banana",      "emoji": "🍌", "name": "Going Bananas",      "desc": 'Used "banana" as an answer',           "secret": False},
    {"id": "pizza",       "emoji": "🍕", "name": "Pizza Party",         "desc": 'Used "pizza" as an answer',            "secret": False},
    {"id": "potato",      "emoji": "🥔", "name": "Couch Potato",        "desc": 'Used "potato" as an answer',           "secret": False},
    {"id": "dinosaur",    "emoji": "🦕", "name": "Jurassic Word",       "desc": 'Used "dinosaur" as an answer',         "secret": False},
    {"id": "pickle",      "emoji": "🥒", "name": "In a Pickle",         "desc": 'Used "pickle" as an answer',           "secret": False},
    {"id": "ninja",       "emoji": "🥷", "name": "Ninja Mode",          "desc": 'Used "ninja" as an answer',            "secret": False},
    {"id": "spaghetti",   "emoji": "🍝", "name": "Spaghetti Western",   "desc": 'Used "spaghetti" as an answer',        "secret": False},
    {"id": "unicorn",     "emoji": "🦄", "name": "Believe in Magic",    "desc": 'Used "unicorn" as an answer',          "secret": False},
    {"id": "butt",        "emoji": "🍑", "name": "Potty Humor",         "desc": 'Used "butt" as an answer',             "secret": True},
    {"id": "flamingo",    "emoji": "🦩", "name": "Fancy Footwork",      "desc": 'Used "flamingo" as an answer',         "secret": False},
    # Story completion milestones
    {"id": "first_story", "emoji": "⭐", "name": "First Story!",        "desc": "Generated your very first Mad Lib",    "secret": False},
    {"id": "5_stories",   "emoji": "🌟", "name": "Story Teller",        "desc": "Generated 5 Mad Libs",                 "secret": False},
    {"id": "10_stories",  "emoji": "🏆", "name": "Mad Lib Master",      "desc": "Generated 10 Mad Libs",                "secret": False},
    # Variety
    {"id": "all_stories", "emoji": "📚", "name": "Full Collection",     "desc": "Played every available story",         "secret": False},
    # Silly combos
    {"id": "food_frenzy", "emoji": "🍔", "name": "Food Frenzy",         "desc": "Used 3+ different food words in one story", "secret": False},
]

FOOD_WORDS = {"banana","pizza","potato","pickle","spaghetti","taco","burger","donut",
              "waffle","sushi","hotdog","meatball","pancake","burrito","cupcake","lasagna"}

ACHIEVEMENT_MAP = {a["id"]: a for a in ACHIEVEMENTS}

# ── DB setup ──────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                username  TEXT UNIQUE NOT NULL,
                created   TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_achievements (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                achievement  TEXT NOT NULL,
                earned_at    TEXT NOT NULL,
                UNIQUE(user_id, achievement)
            );
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id        INTEGER PRIMARY KEY,
                stories_played INTEGER DEFAULT 0,
                slugs_played   TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS completed_stories (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id          INTEGER,
                slug             TEXT NOT NULL,
                title            TEXT NOT NULL,
                answers          TEXT NOT NULL,
                completed_story  TEXT NOT NULL,
                created_at       TEXT NOT NULL
            );
        """)

init_db()

# ── Story helpers ─────────────────────────────────────────────────────────────
def load_stories():
    stories = []
    for path in sorted(glob.glob(os.path.join(STORIES_DIR, "*.txt"))):
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        title_match = re.search(r"^title:\s*(.+)$", raw, re.MULTILINE)
        body_start  = raw.find("---\n")
        title = title_match.group(1).strip() if title_match else os.path.basename(path)
        body  = raw[body_start + 4:].strip() if body_start != -1 else raw.strip()
        slug  = os.path.splitext(os.path.basename(path))[0]
        stories.append({"slug": slug, "title": title, "template": body})
    return stories

def extract_blanks(template):
    return re.findall(r"\{([^}]+)\}", template)

def fill_template(template, answers):
    result = template
    for placeholder, answer in zip(extract_blanks(template), answers):
        result = result.replace("{" + placeholder + "}", answer, 1)
    return result

# ── Achievement checker ───────────────────────────────────────────────────────
def check_achievements(user_id, answers, slug, db):
    answers_lower = [a.lower().strip() for a in answers]
    earned = []

    # Existing achievements
    existing = {r["achievement"] for r in
                db.execute("SELECT achievement FROM user_achievements WHERE user_id=?", (user_id,))}

    def award(aid):
        if aid not in existing:
            db.execute("INSERT OR IGNORE INTO user_achievements (user_id, achievement, earned_at) VALUES (?,?,?)",
                       (user_id, aid, datetime.utcnow().isoformat()))
            earned.append(ACHIEVEMENT_MAP[aid])

    # Word-choice achievements
    word_achievements = {
        "banana": "banana", "pizza": "pizza", "potato": "potato",
        "dinosaur": "dinosaur", "pickle": "pickle", "ninja": "ninja",
        "spaghetti": "spaghetti", "unicorn": "unicorn", "butt": "butt",
        "flamingo": "flamingo",
    }
    for word, aid in word_achievements.items():
        if any(word in ans for ans in answers_lower):
            award(aid)

    # Food frenzy
    foods_used = {a for a in answers_lower if any(f in a for f in FOOD_WORDS)}
    if len(foods_used) >= 3:
        award("food_frenzy")

    # Story count milestones
    stats = db.execute("SELECT stories_played, slugs_played FROM user_stats WHERE user_id=?",
                       (user_id,)).fetchone()
    if stats:
        count     = stats["stories_played"] + 1
        slugs_set = set(filter(None, stats["slugs_played"].split(","))) | {slug}
        db.execute("UPDATE user_stats SET stories_played=?, slugs_played=? WHERE user_id=?",
                   (count, ",".join(slugs_set), user_id))
    else:
        count     = 1
        slugs_set = {slug}
        db.execute("INSERT INTO user_stats (user_id, stories_played, slugs_played) VALUES (?,?,?)",
                   (user_id, 1, slug))

    if count == 1:  award("first_story")
    if count >= 5:  award("5_stories")
    if count >= 10: award("10_stories")

    # All stories
    all_slugs = {s["slug"] for s in load_stories()}
    if all_slugs and all_slugs <= slugs_set:
        award("all_stories")

    db.commit()
    return earned

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/achievements")
def achievements_page():
    return render_template("achievements.html")

# User
@app.route("/api/login", methods=["POST"])
def api_login():
    username = request.get_json().get("username", "").strip()
    if not username or len(username) > 30:
        return jsonify({"error": "Invalid username"}), 400
    with get_db() as db:
        db.execute("INSERT OR IGNORE INTO users (username, created) VALUES (?,?)",
                   (username, datetime.utcnow().isoformat()))
        user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        db.commit()
    session["user_id"]  = user["id"]
    session["username"] = user["username"]
    return jsonify({"id": user["id"], "username": user["username"]})

@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/api/me")
def api_me():
    if "user_id" not in session:
        return jsonify({"user": None})
    return jsonify({"user": {"id": session["user_id"], "username": session["username"]}})

# Stories
@app.route("/api/stories")
def api_stories():
    return jsonify([{"slug": s["slug"], "title": s["title"]} for s in load_stories()])

@app.route("/api/stories/<slug>")
def api_story(slug):
    for s in load_stories():
        if s["slug"] == slug:
            return jsonify({"slug": s["slug"], "title": s["title"],
                            "blanks": extract_blanks(s["template"]), "template": s["template"]})
    return jsonify({"error": "Not found"}), 404

@app.route("/api/generate", methods=["POST"])
def api_generate():
    data    = request.get_json()
    slug    = data.get("slug")
    answers = data.get("answers", [])

    for s in load_stories():
        if s["slug"] == slug:
            blanks = extract_blanks(s["template"])
            if len(answers) != len(blanks):
                return jsonify({"error": "Wrong number of answers"}), 400
            filled = fill_template(s["template"], answers)

            new_achievements = []
            if "user_id" in session:
                with get_db() as db:
                    new_achievements = check_achievements(session["user_id"], answers, slug, db)
                    db.execute(
                        "INSERT INTO completed_stories (user_id, slug, title, answers, completed_story, created_at) VALUES (?,?,?,?,?,?)",
                        (session["user_id"], slug, s["title"], json.dumps(answers), filled, datetime.utcnow().isoformat())
                    )
                    db.commit()

            return jsonify({"story": filled, "title": s["title"],
                            "new_achievements": new_achievements})

    return jsonify({"error": "Story not found"}), 404

# Achievements
@app.route("/api/achievements")
def api_achievements():
    if "user_id" not in session:
        return jsonify({"achievements": ACHIEVEMENTS, "earned": []})
    with get_db() as db:
        rows = db.execute(
            "SELECT achievement, earned_at FROM user_achievements WHERE user_id=? ORDER BY earned_at",
            (session["user_id"],)).fetchall()
    earned = {r["achievement"]: r["earned_at"] for r in rows}
    return jsonify({"achievements": ACHIEVEMENTS, "earned": earned})

@app.route("/api/stats")
def api_stats():
    if "user_id" not in session:
        return jsonify({"stories_played": 0})
    with get_db() as db:
        row = db.execute("SELECT stories_played FROM user_stats WHERE user_id=?",
                         (session["user_id"],)).fetchone()
    return jsonify({"stories_played": row["stories_played"] if row else 0})

# History
@app.route("/history")
def history_page():
    return render_template("history.html")

@app.route("/api/history")
def api_history():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    with get_db() as db:
        rows = db.execute(
            "SELECT id, slug, title, answers, completed_story, created_at FROM completed_stories WHERE user_id=? ORDER BY created_at DESC",
            (session["user_id"],)).fetchall()
    return jsonify([{
        "id":              r["id"],
        "slug":            r["slug"],
        "title":           r["title"],
        "answers":         json.loads(r["answers"]),
        "completed_story": r["completed_story"],
        "created_at":      r["created_at"],
    } for r in rows])

@app.route("/api/history/<int:story_id>", methods=["DELETE"])
def api_delete_story(story_id):
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    with get_db() as db:
        db.execute("DELETE FROM completed_stories WHERE id=? AND user_id=?",
                   (story_id, session["user_id"]))
        db.commit()
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(debug=True)
