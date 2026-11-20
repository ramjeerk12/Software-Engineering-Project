import os, sqlite3, uuid, mimetypes
from datetime import datetime
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for, flash,
                   session, send_file, abort)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "multimedia.db")
VAULT_DIR = os.path.join(BASE_DIR, "storage", "encrypted")
MAX_FILE_SIZE = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = None  # Allow any file type; filenames are never used as storage paths.

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-this-secret")
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE

def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def init_db():
    os.makedirs(VAULT_DIR, exist_ok=True)
    con = connect()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        failed_attempts INTEGER NOT NULL DEFAULT 0,
        is_locked INTEGER NOT NULL DEFAULT 0,
        role TEXT NOT NULL DEFAULT 'user',
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL REFERENCES users(id),
        original_name TEXT NOT NULL,
        stored_name TEXT NOT NULL UNIQUE,
        salt BLOB NOT NULL,
        mime_type TEXT,
        size_bytes INTEGER NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS security_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id),
        document_id INTEGER,
        operation TEXT NOT NULL,
        result TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)
    admin = con.execute("SELECT id FROM users WHERE email=?", ("admin@multimedia.local",)).fetchone()
    if not admin:
        con.execute("""INSERT INTO users(name,email,password_hash,role,created_at)
                       VALUES(?,?,?,?,?)""",
                    ("Administrator", "admin@multimedia.local",
                     generate_password_hash("Admin@12345"), "admin",
                     datetime.now().isoformat(timespec="seconds")))
    con.commit()
    con.close()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def current_user(con):
    return con.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()

def add_log(con, user_id, doc_id, operation, result):
    con.execute("""INSERT INTO security_logs(user_id,document_id,operation,result,created_at)
                   VALUES(?,?,?,?,?)""",
                (user_id, doc_id, operation, result, datetime.now().isoformat(timespec="seconds")))

def record_failure(con, user, doc_id, operation):
    attempts = user["failed_attempts"] + 1
    locked = 1 if attempts >= 3 else 0
    con.execute("UPDATE users SET failed_attempts=?, is_locked=? WHERE id=?",
                (attempts, locked, user["id"]))
    add_log(con, user["id"], doc_id, operation, "FAILED")
    con.commit()
    if locked:
        flash("Account locked after 3 failed document-operation password attempts. Contact the administrator.", "danger")
    else:
        flash(f"Incorrect password. {3-attempts} attempt(s) remaining before account lock.", "danger")

def verify_operation_password(con, user, password, doc_id, operation):
    if user["is_locked"]:
        flash("Your account is locked. Contact the administrator.", "danger")
        return False
    if not check_password_hash(user["password_hash"], password):
        record_failure(con, user, doc_id, operation)
        return False
    con.execute("UPDATE users SET failed_attempts=0 WHERE id=?", (user["id"],))
    add_log(con, user["id"], doc_id, operation, "SUCCESS")
    con.commit()
    return True

def derive_key(password, salt):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600000)
    return kdf.derive(password.encode("utf-8"))

def get_owned_document(con, doc_id):
    return con.execute("SELECT * FROM documents WHERE id=? AND owner_id=?",
                       (doc_id, session["user_id"])).fetchone()

@app.errorhandler(413)
def too_large(_):
    flash("File is too large. Maximum upload size is 50 MB.", "danger")
    return redirect(url_for("vault"))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or len(password) < 8:
            flash("Enter your name and a password with at least 8 characters.", "danger")
            return render_template("register.html")
        con = connect()
        try:
            con.execute("""INSERT INTO users(name,email,password_hash,created_at)
                           VALUES(?,?,?,?)""",
                        (name, email, generate_password_hash(password),
                         datetime.now().isoformat(timespec="seconds")))
            con.commit()
            flash("Account created. Log in to start protecting files.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That email is already registered.", "danger")
        finally:
            con.close()
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        con = connect()
        user = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        con.close()
        if user and user["is_locked"]:
            flash("This account is locked. Contact the administrator.", "danger")
        elif user and check_password_hash(user["password_hash"], password):
            session.clear()
            session.update(user_id=user["id"], name=user["name"], role=user["role"])
            return redirect(url_for("vault"))
        else:
            flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("index"))

@app.route("/vault")
@login_required
def vault():
    con = connect()
    user = current_user(con)
    docs = con.execute("SELECT * FROM documents WHERE owner_id=? ORDER BY id DESC",
                       (session["user_id"],)).fetchall()
    con.close()
    return render_template("vault.html", docs=docs, user=user)

@app.route("/encrypt", methods=["POST"])
@login_required
def encrypt_document():
    upload = request.files.get("document")
    if not upload or not upload.filename:
        flash("Choose a file to encrypt.", "danger")
        return redirect(url_for("vault"))
    original_name = secure_filename(upload.filename)
    if not original_name:
        flash("Invalid filename.", "danger")
        return redirect(url_for("vault"))
    raw = upload.read(MAX_FILE_SIZE + 1)
    if len(raw) > MAX_FILE_SIZE:
        flash("File exceeds the 50 MB limit.", "danger")
        return redirect(url_for("vault"))
    if not raw:
        flash("Empty files cannot be protected.", "danger")
        return redirect(url_for("vault"))

    con = connect()
    user = current_user(con)
    if user["is_locked"]:
        con.close()
        flash("Your account is locked. Contact the administrator.", "danger")
        return redirect(url_for("vault"))
    # Encryption uses the authenticated account password, requested again here.
    password = request.form.get("password", "")
    if not check_password_hash(user["password_hash"], password):
        record_failure(con, user, None, "ENCRYPT")
        con.close()
        return redirect(url_for("vault"))

    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = derive_key(password, salt)
    encrypted = nonce + AESGCM(key).encrypt(nonce, raw, None)
    stored_name = uuid.uuid4().hex + ".bin"
    path = os.path.join(VAULT_DIR, stored_name)
    with open(path, "wb") as f:
        f.write(encrypted)
    mime = mimetypes.guess_type(original_name)[0] or "application/octet-stream"
    con.execute("""INSERT INTO documents(owner_id,original_name,stored_name,salt,mime_type,size_bytes,created_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (user["id"], original_name, stored_name, salt, mime, len(raw),
                 datetime.now().isoformat(timespec="seconds")))
    add_log(con, user["id"], None, "ENCRYPT", "SUCCESS")
    con.commit()
    con.close()
    flash("File encrypted and added to your protected vault.", "success")
    return redirect(url_for("vault"))

def authenticated_document_action(doc_id, operation, mode):
    con = connect()
    user = current_user(con)
    doc = get_owned_document(con, doc_id)
    if not doc:
        con.close()
        abort(404)
    if user["is_locked"]:
        con.close()
        flash("Your account is locked. Contact the administrator.", "danger")
        return redirect(url_for("vault"))
    password = request.form.get("password", "")
    if not verify_operation_password(con, user, password, doc_id, operation):
        con.close()
        return redirect(url_for("vault"))
    path = os.path.join(VAULT_DIR, doc["stored_name"])
    try:
        with open(path, "rb") as f:
            blob = f.read()
        nonce, ciphertext = blob[:12], blob[12:]
        key = derive_key(password, doc["salt"])
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
    except (OSError, InvalidTag, ValueError):
        add_log(con, user["id"], doc_id, operation, "DECRYPTION_ERROR")
        con.commit()
        con.close()
        flash("Could not decrypt this file. It may be damaged or its key is invalid.", "danger")
        return redirect(url_for("vault"))
    con.close()
    import io
    # Always send as an attachment to avoid rendering untrusted HTML/script files in the app origin.
    return send_file(io.BytesIO(plaintext), mimetype="application/octet-stream",
                     as_attachment=True, download_name=doc["original_name"])

@app.route("/document/<int:doc_id>/open", methods=["POST"])
@login_required
def open_document(doc_id):
    return authenticated_document_action(doc_id, "OPEN", "open")

@app.route("/document/<int:doc_id>/decrypt", methods=["POST"])
@login_required
def decrypt_document(doc_id):
    return authenticated_document_action(doc_id, "DECRYPT", "decrypt")

@app.route("/document/<int:doc_id>/copy", methods=["POST"])
@login_required
def copy_document(doc_id):
    con = connect()
    user = current_user(con)
    doc = get_owned_document(con, doc_id)
    if not doc:
        con.close()
        abort(404)
    if not verify_operation_password(con, user, request.form.get("password", ""), doc_id, "COPY"):
        con.close()
        return redirect(url_for("vault"))
    source = os.path.join(VAULT_DIR, doc["stored_name"])
    new_name = uuid.uuid4().hex + ".bin"
    target = os.path.join(VAULT_DIR, new_name)
    try:
        with open(source, "rb") as src, open(target, "wb") as dst:
            dst.write(src.read())
        con.execute("""INSERT INTO documents(owner_id,original_name,stored_name,salt,mime_type,size_bytes,created_at)
                       VALUES(?,?,?,?,?,?,?)""",
                    (user["id"], doc["original_name"], new_name, doc["salt"],
                     doc["mime_type"], doc["size_bytes"], datetime.now().isoformat(timespec="seconds")))
        add_log(con, user["id"], doc_id, "COPY", "SUCCESS")
        con.commit()
        flash("Encrypted copy created in your vault.", "success")
    except OSError:
        if os.path.exists(target):
            os.remove(target)
        con.rollback()
        flash("Copy operation failed.", "danger")
    con.close()
    return redirect(url_for("vault"))

@app.route("/document/<int:doc_id>/delete", methods=["POST"])
@login_required
def delete_document(doc_id):
    con = connect()
    user = current_user(con)
    doc = get_owned_document(con, doc_id)
    if not doc:
        con.close()
        abort(404)
    if not verify_operation_password(con, user, request.form.get("password", ""), doc_id, "DELETE"):
        con.close()
        return redirect(url_for("vault"))
    path = os.path.join(VAULT_DIR, doc["stored_name"])
    try:
        if os.path.exists(path):
            os.remove(path)
        con.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        add_log(con, user["id"], doc_id, "DELETE", "SUCCESS")
        con.commit()
        flash("Protected document deleted.", "success")
    except OSError:
        con.rollback()
        flash("Could not delete the protected file.", "danger")
    con.close()
    return redirect(url_for("vault"))

@app.route("/admin")
@login_required
def admin():
    if session.get("role") != "admin":
        abort(403)
    con = connect()
    users = con.execute("SELECT id,name,email,failed_attempts,is_locked,role,created_at FROM users ORDER BY id").fetchall()
    logs = con.execute("""SELECT l.*,u.email FROM security_logs l JOIN users u ON u.id=l.user_id
                          ORDER BY l.id DESC LIMIT 100""").fetchall()
    con.close()
    return render_template("admin.html", users=users, logs=logs)

@app.route("/admin/unlock/<int:user_id>", methods=["POST"])
@login_required
def unlock_user(user_id):
    if session.get("role") != "admin":
        abort(403)
    con = connect()
    con.execute("UPDATE users SET failed_attempts=0,is_locked=0 WHERE id=? AND role='user'", (user_id,))
    con.commit()
    con.close()
    flash("Account unlocked (if it was a user account).", "success")
    return redirect(url_for("admin"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
