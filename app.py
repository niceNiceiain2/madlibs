from flask import Flask, jsonify, render_template, request, session
from flask_cors import CORS
import re
import os
import glob
import json
import hashlib
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from db import get_db, init_db, q, USE_POSTGRES

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "novalib-secret-key-change-in-production")

# Allow the Capacitor mobile app to call this backend with login cookies included.
CORS(app, supports_credentials=True, origins=[
    "capacitor://localhost",
    "http://localhost",
    "https://localhost",
    "ionic://localhost",
])

# Session cookies must be SameSite=None + Secure to flow from the app's webview
app.config.update(
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True,
)

STORIES_DIR = os.path.join(os.path.dirname(__file__), "stories")

# ── Email configuration (set these in Railway as environment variables) ───────
GMAIL_ADDRESS      = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
# The public base URL of the site, used to build reset links
APP_BASE_URL       = os.environ.get("APP_BASE_URL", "https://web-production-ca412.up.railway.app")


def send_reset_email(to_email: str, username: str, reset_link: str) -> bool:
    """Send a password reset email via Gmail SMTP. Returns True on success."""
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        # Email isn't configured — log to console so local dev still works
        print(f"[EMAIL NOT CONFIGURED] Would send reset link to {to_email}: {reset_link}")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Reset your NovaLib password"
    msg["From"]    = f"NovaLib <{GMAIL_ADDRESS}>"
    msg["To"]      = to_email

    text = (f"Hi {username},\n\n"
            f"We received a request to reset your NovaLib password.\n"
            f"Click the link below to choose a new password:\n\n{reset_link}\n\n"
            f"This link expires in 1 hour. If you didn't request this, you can ignore this email.\n\n"
            f"— The NovaLib Team")

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color:#e8132a;">✦ NovaLib ✦</h2>
      <p>Hi <strong>{username}</strong>,</p>
      <p>We received a request to reset your NovaLib password. Click the button below to choose a new one:</p>
      <p style="text-align:center; margin: 28px 0;">
        <a href="{reset_link}" style="background:#ffe438; color:#1a0a00; font-weight:bold;
           padding: 12px 28px; text-decoration:none; border:2px solid #1a0a00; border-radius:4px;">
          Reset My Password
        </a>
      </p>
      <p style="color:#666; font-size:13px;">This link expires in 1 hour. If you didn't request this, you can safely ignore this email.</p>
      <p style="color:#666; font-size:13px;">— The NovaLib Team</p>
    </div>
    """

    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        # timeout prevents the worker from hanging if the SMTP port is blocked
        # (e.g. Railway blocks outbound SMTP on free/hobby plans). Fails cleanly instead.
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send to {to_email}: {e}")
        return False



# ── All achievements ──────────────────────────────────────────────────────────
ACHIEVEMENTS = [
    {"id": "banana",      "emoji": "🍌", "name": "Going Bananas",      "desc": 'Used "banana" as an answer',                "secret": False},
    {"id": "pizza",       "emoji": "🍕", "name": "Pizza Party",         "desc": 'Used "pizza" as an answer',                 "secret": False},
    {"id": "potato",      "emoji": "🥔", "name": "Couch Potato",        "desc": 'Used "potato" as an answer',                "secret": False},
    {"id": "dinosaur",    "emoji": "🦕", "name": "Jurassic Word",       "desc": 'Used "dinosaur" as an answer',              "secret": False},
    {"id": "pickle",      "emoji": "🥒", "name": "In a Pickle",         "desc": 'Used "pickle" as an answer',                "secret": False},
    {"id": "ninja",       "emoji": "🥷", "name": "Ninja Mode",          "desc": 'Used "ninja" as an answer',                 "secret": False},
    {"id": "spaghetti",   "emoji": "🍝", "name": "Spaghetti Western",   "desc": 'Used "spaghetti" as an answer',             "secret": False},
    {"id": "unicorn",     "emoji": "🦄", "name": "Believe in Magic",    "desc": 'Used "unicorn" as an answer',               "secret": False},
    {"id": "butt",        "emoji": "🍑", "name": "Potty Humor",         "desc": 'Used "butt" as an answer',                  "secret": True},
    {"id": "flamingo",    "emoji": "🦩", "name": "Fancy Footwork",      "desc": 'Used "flamingo" as an answer',              "secret": False},
    {"id": "first_story", "emoji": "⭐", "name": "First Story!",        "desc": "Generated your very first NovaLib",         "secret": False},
    {"id": "5_stories",   "emoji": "🌟", "name": "Story Teller",        "desc": "Generated 5 NovaLibs",                      "secret": False},
    {"id": "10_stories",  "emoji": "🏆", "name": "NovaLib Master",      "desc": "Generated 10 NovaLibs",                     "secret": False},
    {"id": "all_stories", "emoji": "📚", "name": "Full Collection",     "desc": "Played every available story",              "secret": False},
    {"id": "food_frenzy", "emoji": "🍔", "name": "Food Frenzy",         "desc": "Used 3+ different food words in one story", "secret": False},
]

FOOD_WORDS = {"banana","pizza","potato","pickle","spaghetti","taco","burger","donut",
              "waffle","sushi","hotdog","meatball","pancake","burrito","cupcake","lasagna"}

ACHIEVEMENT_MAP = {a["id"]: a for a in ACHIEVEMENTS}

init_db()

# ── Password hashing ──────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    salt = secrets.token_hex(32)
    pw_hash = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{pw_hash}"

def verify_password(password: str, stored: str) -> bool:
    try:
        salt, pw_hash = stored.split(":")
        return hashlib.sha256((salt + password).encode()).hexdigest() == pw_hash
    except Exception:
        return False

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
def check_achievements(user_id, answers, slug, conn):
    cur = conn.cursor()
    answers_lower = [a.lower().strip() for a in answers]
    earned = []

    cur.execute(q("SELECT achievement FROM user_achievements WHERE user_id=?"), (user_id,))
    existing = {row["achievement"] for row in cur.fetchall()}

    def award(aid):
        if aid not in existing:
            if USE_POSTGRES:
                cur.execute(q("INSERT INTO user_achievements (user_id, achievement, earned_at) VALUES (?,?,?) ON CONFLICT DO NOTHING"),
                            (user_id, aid, datetime.utcnow().isoformat()))
            else:
                cur.execute(q("INSERT OR IGNORE INTO user_achievements (user_id, achievement, earned_at) VALUES (?,?,?)"),
                            (user_id, aid, datetime.utcnow().isoformat()))
            earned.append(ACHIEVEMENT_MAP[aid])

    word_achievements = {
        "banana": "banana", "pizza": "pizza", "potato": "potato",
        "dinosaur": "dinosaur", "pickle": "pickle", "ninja": "ninja",
        "spaghetti": "spaghetti", "unicorn": "unicorn", "butt": "butt",
        "flamingo": "flamingo",
    }
    for word, aid in word_achievements.items():
        if any(word in ans for ans in answers_lower):
            award(aid)

    foods_used = {a for a in answers_lower if any(f in a for f in FOOD_WORDS)}
    if len(foods_used) >= 3:
        award("food_frenzy")

    cur.execute(q("SELECT stories_played, slugs_played FROM user_stats WHERE user_id=?"), (user_id,))
    stats = cur.fetchone()
    if stats:
        count     = stats["stories_played"] + 1
        slugs_set = set(filter(None, stats["slugs_played"].split(","))) | {slug}
        cur.execute(q("UPDATE user_stats SET stories_played=?, slugs_played=? WHERE user_id=?"),
                    (count, ",".join(slugs_set), user_id))
    else:
        count     = 1
        slugs_set = {slug}
        cur.execute(q("INSERT INTO user_stats (user_id, stories_played, slugs_played) VALUES (?,?,?)"),
                    (user_id, 1, slug))

    if count == 1:  award("first_story")
    if count >= 5:  award("5_stories")
    if count >= 10: award("10_stories")

    all_slugs = {s["slug"] for s in load_stories()}
    if all_slugs and all_slugs <= slugs_set:
        award("all_stories")

    conn.commit()
    cur.close()
    return earned

# ── Page routes ───────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/achievements")
def achievements_page():
    return render_template("achievements.html")

@app.route("/history")
def history_page():
    return render_template("history.html")

@app.route("/leaderboard")
def leaderboard_page():
    return render_template("leaderboard.html")

# ── Auth ──────────────────────────────────────────────────────────────────────
@app.route("/api/register", methods=["POST"])
def api_register():
    data     = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    email    = data.get("email", "").strip().lower()

    if not username or len(username) > 30:
        return jsonify({"error": "Username must be 1-30 characters"}), 400
    if not password or len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if not email or "@" not in email or "." not in email:
        return jsonify({"error": "Please enter a valid email address"}), 400

    pw_hash = hash_password(password)
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(q("SELECT id FROM users WHERE username=?"), (username,))
    if cur.fetchone():
        cur.close(); conn.close()
        return jsonify({"error": "Username already taken"}), 400

    cur.execute(q("INSERT INTO users (username, password, created, email) VALUES (?,?,?,?)"),
                (username, pw_hash, datetime.utcnow().isoformat(), email))
    conn.commit()
    cur.execute(q("SELECT id, username FROM users WHERE username=?"), (username,))
    user = cur.fetchone()
    cur.close(); conn.close()

    session["user_id"]  = user["id"]
    session["username"] = user["username"]
    return jsonify({"id": user["id"], "username": user["username"]})

@app.route("/api/login", methods=["POST"])
def api_login():
    data     = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    conn = get_db()
    cur  = conn.cursor()
    cur.execute(q("SELECT id, username, password, email FROM users WHERE username=?"), (username,))
    user = cur.fetchone()
    cur.close(); conn.close()

    if not user or not verify_password(password, user["password"]):
        return jsonify({"error": "Incorrect username or password"}), 401

    session["user_id"]  = user["id"]
    session["username"] = user["username"]
    needs_email = not user["email"]
    return jsonify({"id": user["id"], "username": user["username"], "needs_email": needs_email})


@app.route("/api/set_email", methods=["POST"])
def api_set_email():
    """Existing users without an email on file must add one after logging in."""
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    data  = request.get_json()
    email = data.get("email", "").strip().lower()
    if not email or "@" not in email or "." not in email:
        return jsonify({"error": "Please enter a valid email address"}), 400

    conn = get_db()
    cur  = conn.cursor()
    cur.execute(q("UPDATE users SET email=? WHERE id=?"), (email, session["user_id"]))
    conn.commit()
    cur.close(); conn.close()
    return jsonify({"ok": True})


@app.route("/api/forgot_password", methods=["POST"])
def api_forgot_password():
    """Generate a reset token and email it to the user."""
    data  = request.get_json()
    email = data.get("email", "").strip().lower()
    if not email:
        return jsonify({"error": "Email required"}), 400

    conn = get_db()
    cur  = conn.cursor()
    cur.execute(q("SELECT id, username, email FROM users WHERE email=?"), (email,))
    user = cur.fetchone()

    # Always return success even if no account — don't reveal which emails exist
    if not user:
        cur.close(); conn.close()
        return jsonify({"ok": True})

    token   = secrets.token_urlsafe(32)
    expires = (datetime.utcnow() + timedelta(hours=1)).isoformat()
    cur.execute(q("UPDATE users SET reset_token=?, reset_expires=? WHERE id=?"),
                (token, expires, user["id"]))
    conn.commit()
    cur.close(); conn.close()

    reset_link = f"{APP_BASE_URL}/reset?token={token}"
    send_reset_email(user["email"], user["username"], reset_link)
    return jsonify({"ok": True})


@app.route("/reset")
def reset_page():
    """Page where the user lands from the email link to set a new password."""
    return render_template("reset.html")


@app.route("/api/reset_password", methods=["POST"])
def api_reset_password():
    """Verify the reset token and set the new password."""
    data         = request.get_json()
    token        = data.get("token", "").strip()
    new_password = data.get("new_password", "").strip()

    if not token or not new_password:
        return jsonify({"error": "Missing token or password"}), 400
    if len(new_password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    conn = get_db()
    cur  = conn.cursor()
    cur.execute(q("SELECT id, reset_expires FROM users WHERE reset_token=?"), (token,))
    user = cur.fetchone()

    if not user:
        cur.close(); conn.close()
        return jsonify({"error": "Invalid or expired reset link"}), 400

    # Check expiry
    try:
        expires = datetime.fromisoformat(user["reset_expires"])
    except Exception:
        expires = datetime.utcnow() - timedelta(seconds=1)
    if datetime.utcnow() > expires:
        cur.close(); conn.close()
        return jsonify({"error": "This reset link has expired. Please request a new one."}), 400

    new_hash = hash_password(new_password)
    cur.execute(q("UPDATE users SET password=?, reset_token=NULL, reset_expires=NULL WHERE id=?"),
                (new_hash, user["id"]))
    conn.commit()
    cur.close(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/api/me")
def api_me():
    if "user_id" not in session:
        return jsonify({"user": None})
    return jsonify({"user": {"id": session["user_id"], "username": session["username"]}})

# ── Stories ───────────────────────────────────────────────────────────────────
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
                conn = get_db()
                new_achievements = check_achievements(session["user_id"], answers, slug, conn)
                cur = conn.cursor()
                cur.execute(q("INSERT INTO completed_stories (user_id, slug, title, answers, completed_story, created_at) VALUES (?,?,?,?,?,?)"),
                            (session["user_id"], slug, s["title"], json.dumps(answers), filled, datetime.utcnow().isoformat()))
                conn.commit()
                cur.close(); conn.close()

            return jsonify({"story": filled, "title": s["title"], "new_achievements": new_achievements})

    return jsonify({"error": "Story not found"}), 404

# ── Achievements ──────────────────────────────────────────────────────────────
@app.route("/api/achievements")
def api_achievements():
    if "user_id" not in session:
        return jsonify({"achievements": ACHIEVEMENTS, "earned": []})
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(q("SELECT achievement, earned_at FROM user_achievements WHERE user_id=? ORDER BY earned_at"),
                (session["user_id"],))
    earned = {row["achievement"]: row["earned_at"] for row in cur.fetchall()}
    cur.close(); conn.close()
    return jsonify({"achievements": ACHIEVEMENTS, "earned": earned})

@app.route("/api/stats")
def api_stats():
    if "user_id" not in session:
        return jsonify({"stories_played": 0})
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(q("SELECT stories_played FROM user_stats WHERE user_id=?"), (session["user_id"],))
    row = cur.fetchone()
    cur.close(); conn.close()
    return jsonify({"stories_played": row["stories_played"] if row else 0})

# ── History ───────────────────────────────────────────────────────────────────
@app.route("/api/history")
def api_history():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(q("SELECT id, slug, title, answers, completed_story, created_at FROM completed_stories WHERE user_id=? ORDER BY created_at DESC"),
                (session["user_id"],))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return jsonify([{
        "id": r["id"], "slug": r["slug"], "title": r["title"],
        "answers": json.loads(r["answers"]), "completed_story": r["completed_story"],
        "created_at": r["created_at"],
    } for r in rows])

@app.route("/api/history/<int:story_id>", methods=["DELETE"])
def api_delete_story(story_id):
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(q("DELETE FROM completed_stories WHERE id=? AND user_id=?"),
                (story_id, session["user_id"]))
    conn.commit()
    cur.close(); conn.close()
    return jsonify({"ok": True})

# ── Leaderboard ───────────────────────────────────────────────────────────────
@app.route("/api/leaderboard")
def api_leaderboard():
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        SELECT u.username,
               COALESCE(s.stories_played, 0) as stories_played,
               COUNT(a.id) as achievements_earned
        FROM users u
        LEFT JOIN user_stats s ON u.id = s.user_id
        LEFT JOIN user_achievements a ON u.id = a.user_id
        GROUP BY u.id, u.username, s.stories_played
        ORDER BY stories_played DESC, achievements_earned DESC
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return jsonify([{
        "rank": i + 1, "username": r["username"],
        "stories_played": r["stories_played"], "achievements_earned": r["achievements_earned"],
    } for i, r in enumerate(rows)])

if __name__ == "__main__":
    app.run(debug=True)
