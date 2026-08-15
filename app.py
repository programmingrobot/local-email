import os
import sqlite3
import uuid
from datetime import UTC, datetime

from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "instance", "mailchat.sqlite3")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {
    "txt",
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "zip",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "csv",
}


app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-me"),
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,
)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            owner_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (owner_id) REFERENCES users (id)
        );

        CREATE TABLE IF NOT EXISTS group_members (
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            joined_at TEXT NOT NULL,
            PRIMARY KEY (group_id, user_id),
            FOREIGN KEY (group_id) REFERENCES groups (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        );

        CREATE TABLE IF NOT EXISTS invites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            invited_email TEXT NOT NULL,
            invited_by INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            UNIQUE (group_id, invited_email),
            FOREIGN KEY (group_id) REFERENCES groups (id),
            FOREIGN KEY (invited_by) REFERENCES users (id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            body TEXT,
            original_filename TEXT,
            stored_filename TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (group_id) REFERENCES groups (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """
    )
    db.commit()


@app.before_request
def ensure_database():
    init_db()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


def utc_now():
    return datetime.now(UTC).isoformat()


def login_required():
    if not current_user():
        flash("Please sign in first.", "warning")
        return False
    return True


def group_for_member(group_id):
    user = current_user()
    if not user:
        return None
    return get_db().execute(
        """
        SELECT g.*, gm.role
        FROM groups g
        JOIN group_members gm ON gm.group_id = g.id
        WHERE g.id = ? AND gm.user_id = ?
        """,
        (group_id, user["id"]),
    ).fetchone()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def accept_pending_invites(user):
    db = get_db()
    invites = db.execute(
        "SELECT * FROM invites WHERE invited_email = ? AND status = 'pending'",
        (user["username"],),
    ).fetchall()
    for invite in invites:
        db.execute(
            """
            INSERT OR IGNORE INTO group_members (group_id, user_id, role, joined_at)
            VALUES (?, ?, 'member', ?)
            """,
            (invite["group_id"], user["id"], utc_now()),
        )
        db.execute("UPDATE invites SET status = 'accepted' WHERE id = ?", (invite["id"],))
    if invites:
        db.commit()


@app.route("/")
def index():
    if current_user():
        return redirect(url_for("inbox"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        display_name = request.form.get("display_name", "").strip() or username
        password = request.form.get("password", "")

        if not username or not password:
            flash("Email and password are required.", "danger")
            return render_template("register.html")

        db = get_db()
        if "@" not in username or " " in username:
            flash("Enter a valid email address as your username.", "danger")
            return render_template("register.html")

        try:
            cursor = db.execute(
                """
                INSERT INTO users (username, display_name, email, password_hash, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    username,
                    display_name,
                    username,
                    generate_password_hash(password),
                    utc_now(),
                ),
            )
            db.commit()
        except sqlite3.IntegrityError:
            flash("That email address is already registered.", "danger")
            return render_template("register.html")

        session.clear()
        session["user_id"] = cursor.lastrowid
        user = current_user()
        accept_pending_invites(user)
        flash("Account created.", "success")
        return redirect(url_for("inbox"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            accept_pending_invites(user)
            flash("Welcome back.", "success")
            return redirect(url_for("inbox"))

        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Signed out.", "success")
    return redirect(url_for("index"))


@app.route("/inbox")
def inbox():
    if not login_required():
        return redirect(url_for("login"))

    user = current_user()
    accept_pending_invites(user)
    db = get_db()
    groups = db.execute(
        """
        SELECT g.*, gm.role,
               (SELECT COUNT(*) FROM messages m WHERE m.group_id = g.id) AS message_count,
               (SELECT MAX(created_at) FROM messages m WHERE m.group_id = g.id) AS last_message_at
        FROM groups g
        JOIN group_members gm ON gm.group_id = g.id
        WHERE gm.user_id = ?
        ORDER BY COALESCE(last_message_at, g.created_at) DESC
        """,
        (user["id"],),
    ).fetchall()
    invites = db.execute(
        """
        SELECT i.*, g.name AS group_name
        FROM invites i
        JOIN groups g ON g.id = i.group_id
        WHERE i.invited_email = ? AND i.status = 'pending'
        ORDER BY i.created_at DESC
        """,
        (user["username"],),
    ).fetchall()
    people = db.execute(
        "SELECT display_name, username FROM users ORDER BY created_at DESC LIMIT 8"
    ).fetchall()
    return render_template("inbox.html", groups=groups, invites=invites, people=people)


@app.route("/groups/new", methods=["GET", "POST"])
def new_group():
    if not login_required():
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        if not name:
            flash("Group name is required.", "danger")
            return render_template("new_group.html")

        user = current_user()
        db = get_db()
        cursor = db.execute(
            "INSERT INTO groups (name, description, owner_id, created_at) VALUES (?, ?, ?, ?)",
            (name, description, user["id"], utc_now()),
        )
        group_id = cursor.lastrowid
        db.execute(
            "INSERT INTO group_members (group_id, user_id, role, joined_at) VALUES (?, ?, 'owner', ?)",
            (group_id, user["id"], utc_now()),
        )
        db.commit()
        flash("Group created.", "success")
        return redirect(url_for("group_chat", group_id=group_id))

    return render_template("new_group.html")


@app.route("/groups/<int:group_id>")
def group_chat(group_id):
    if not login_required():
        return redirect(url_for("login"))

    group = group_for_member(group_id)
    if not group:
        abort(404)

    db = get_db()
    messages = db.execute(
        """
        SELECT m.*, u.display_name, u.username
        FROM messages m
        JOIN users u ON u.id = m.user_id
        WHERE m.group_id = ?
        ORDER BY m.created_at ASC
        """,
        (group_id,),
    ).fetchall()
    members = db.execute(
        """
        SELECT u.display_name, u.username, gm.role
        FROM group_members gm
        JOIN users u ON u.id = gm.user_id
        WHERE gm.group_id = ?
        ORDER BY gm.role DESC, u.display_name ASC
        """,
        (group_id,),
    ).fetchall()
    invites = db.execute(
        "SELECT * FROM invites WHERE group_id = ? ORDER BY created_at DESC",
        (group_id,),
    ).fetchall()
    return render_template(
        "chat.html", group=group, messages=messages, members=members, invites=invites
    )


def messages_for_group(group_id, after_id=0):
    return get_db().execute(
        """
        SELECT m.*, u.display_name, u.username
        FROM messages m
        JOIN users u ON u.id = m.user_id
        WHERE m.group_id = ? AND m.id > ?
        ORDER BY m.created_at ASC
        """,
        (group_id, after_id),
    ).fetchall()


def message_by_id(group_id, message_id):
    return get_db().execute(
        """
        SELECT m.*, u.display_name, u.username
        FROM messages m
        JOIN users u ON u.id = m.user_id
        WHERE m.group_id = ? AND m.id = ?
        """,
        (group_id, message_id),
    ).fetchone()


def message_to_dict(message):
    attachment_url = None
    if message["stored_filename"]:
        attachment_url = url_for("uploaded_file", filename=message["stored_filename"])
    return {
        "id": message["id"],
        "user_id": message["user_id"],
        "display_name": message["display_name"],
        "username": message["username"],
        "body": message["body"] or "",
        "original_filename": message["original_filename"],
        "attachment_url": attachment_url,
        "created_at": message["created_at"],
    }


@app.route("/groups/<int:group_id>/messages")
def group_messages(group_id):
    if not current_user():
        return jsonify({"error": "login_required"}), 401

    if not group_for_member(group_id):
        abort(404)

    after_id = request.args.get("after_id", "0")
    try:
        after_id = int(after_id)
    except ValueError:
        after_id = 0

    messages = messages_for_group(group_id, after_id)
    return jsonify(
        {
            "current_user_id": current_user()["id"],
            "messages": [message_to_dict(message) for message in messages],
        }
    )


@app.route("/groups/<int:group_id>/message", methods=["POST"])
def send_message(group_id):
    if not login_required():
        return redirect(url_for("login"))

    group = group_for_member(group_id)
    if not group:
        abort(404)

    body = request.form.get("body", "").strip()
    upload = request.files.get("attachment")
    original_filename = None
    stored_filename = None

    if upload and upload.filename:
        if not allowed_file(upload.filename):
            if request.headers.get("X-Requested-With") == "fetch":
                return jsonify({"error": "That file type is not allowed."}), 400
            flash("That file type is not allowed.", "danger")
            return redirect(url_for("group_chat", group_id=group_id))
        original_filename = secure_filename(upload.filename)
        stored_filename = f"{uuid.uuid4().hex}_{original_filename}"
        upload.save(os.path.join(app.config["UPLOAD_FOLDER"], stored_filename))

    if not body and not stored_filename:
        if request.headers.get("X-Requested-With") == "fetch":
            return jsonify({"error": "Write a message or attach a file."}), 400
        flash("Write a message or attach a file.", "warning")
        return redirect(url_for("group_chat", group_id=group_id))

    cursor = get_db().execute(
        """
        INSERT INTO messages (group_id, user_id, body, original_filename, stored_filename, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            group_id,
            current_user()["id"],
            body,
            original_filename,
            stored_filename,
            utc_now(),
        ),
    )
    get_db().commit()
    if request.headers.get("X-Requested-With") == "fetch":
        message = message_by_id(group_id, cursor.lastrowid)
        return jsonify({"message": message_to_dict(message)})
    return redirect(url_for("group_chat", group_id=group_id))


@app.route("/groups/<int:group_id>/invite", methods=["POST"])
def invite(group_id):
    if not login_required():
        return redirect(url_for("login"))

    group = group_for_member(group_id)
    if not group:
        abort(404)

    email = request.form.get("email", "").strip().lower()
    if not email:
        flash("Enter an email address to invite.", "warning")
        return redirect(url_for("group_chat", group_id=group_id))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (email,)).fetchone()
    if user:
        db.execute(
            """
            INSERT OR IGNORE INTO group_members (group_id, user_id, role, joined_at)
            VALUES (?, ?, 'member', ?)
            """,
            (group_id, user["id"], utc_now()),
        )
        status = "accepted"
        flash(f"{email} was added to the group.", "success")
    else:
        status = "pending"
        flash(f"Invite saved for {email}. They can join when they register with that email.", "success")

    db.execute(
        """
        INSERT INTO invites (group_id, invited_email, invited_by, status, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(group_id, invited_email) DO UPDATE SET status = excluded.status
        """,
        (group_id, email, current_user()["id"], status, utc_now()),
    )
    db.commit()
    return redirect(url_for("group_chat", group_id=group_id))


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    if not login_required():
        return redirect(url_for("login"))

    message = get_db().execute(
        "SELECT * FROM messages WHERE stored_filename = ?", (filename,)
    ).fetchone()
    if not message or not group_for_member(message["group_id"]):
        abort(404)
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
