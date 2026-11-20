from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from pathlib import Path
import sqlite3
from datetime import datetime

app=Flask(__name__)
app.secret_key="replace-this-with-a-long-random-secret"
DB=Path(__file__).with_name("social_network.db")

def get_db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); return c

def init_db():
    with get_db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
          password_hash TEXT NOT NULL, dob TEXT DEFAULT '', address TEXT DEFAULT '',
          phone TEXT DEFAULT '', education TEXT DEFAULT '', photo_url TEXT DEFAULT '',
          professional_info TEXT DEFAULT '', hobbies TEXT DEFAULT '',
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS friendships(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          requester_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','rejected')),
          created_at TEXT NOT NULL,
          UNIQUE(requester_id,receiver_id), CHECK(requester_id <> receiver_id)
        );
        CREATE TABLE IF NOT EXISTS messages(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          body TEXT NOT NULL CHECK(length(body) BETWEEN 1 AND 2000),
          sent_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_messages_pair ON messages(sender_id,receiver_id,sent_at);
        """)
        # Optional demo users only on a fresh database; passwords are demo123.
        if c.execute("SELECT COUNT(*) FROM users").fetchone()[0]==0:
            now=datetime.now().isoformat(timespec="seconds")
            demo=[("Aarav Sharma","aarav@example.com"),("Diya Verma","diya@example.com"),("Kabir Singh","kabir@example.com")]
            for name,email in demo:
                c.execute("INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",
                          (name,email,generate_password_hash("demo123"),now))

def login_required(f):
    @wraps(f)
    def wrapper(*a,**kw):
        if "user_id" not in session:
            flash("Please log in to continue.","error"); return redirect(url_for("login"))
        return f(*a,**kw)
    return wrapper

def me():
    with get_db() as c: return c.execute("SELECT * FROM users WHERE id=?",(session["user_id"],)).fetchone()

def are_friends(c,a,b):
    row=c.execute("""SELECT 1 FROM friendships WHERE status='accepted'
       AND ((requester_id=? AND receiver_id=?) OR (requester_id=? AND receiver_id=?))""",(a,b,b,a)).fetchone()
    return row is not None

@app.route("/")
def index():
    if "user_id" not in session: return render_template("welcome.html")
    with get_db() as c:
        friends=c.execute("""SELECT u.id,u.name,u.photo_url FROM users u JOIN friendships f
          ON ((f.requester_id=u.id AND f.receiver_id=?) OR (f.receiver_id=u.id AND f.requester_id=?))
          WHERE f.status='accepted' ORDER BY u.name""",(session["user_id"],session["user_id"])).fetchall()
        pending=c.execute("""SELECT f.id,u.id AS user_id,u.name,u.email FROM friendships f
          JOIN users u ON u.id=f.requester_id WHERE f.receiver_id=? AND f.status='pending'""",(session["user_id"],)).fetchall()
        recent=c.execute("""SELECT m.*,u.name AS sender_name FROM messages m JOIN users u ON u.id=m.sender_id
          WHERE m.receiver_id=? ORDER BY m.id DESC LIMIT 5""",(session["user_id"],)).fetchall()
    return render_template("dashboard.html",user=me(),friends=friends,pending=pending,recent=recent)

@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        name=request.form.get("name","").strip(); email=request.form.get("email","").strip().lower()
        password=request.form.get("password","")
        if not name or not email or len(password)<8:
            flash("Enter your name/email and a password of at least 8 characters.","error")
        else:
            try:
                with get_db() as c:
                    cur=c.execute("INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",
                      (name,email,generate_password_hash(password),datetime.now().isoformat(timespec="seconds")))
                    session.clear(); session["user_id"]=cur.lastrowid
                flash("Account created. Complete your profile!","success"); return redirect(url_for("profile"))
            except sqlite3.IntegrityError: flash("That email address is already registered.","error")
    return render_template("register.html")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form.get("email","").strip().lower(); password=request.form.get("password","")
        with get_db() as c: user=c.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
        if user and check_password_hash(user["password_hash"],password):
            session.clear(); session["user_id"]=user["id"]; return redirect(url_for("index"))
        flash("Invalid email or password.","error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("index"))

@app.route("/profile",methods=["GET","POST"])
@login_required
def profile():
    if request.method=="POST":
        fields=["name","dob","address","phone","education","photo_url","professional_info","hobbies"]
        values=[request.form.get(k,"").strip() for k in fields]
        if not values[0]: flash("Name cannot be empty.","error")
        else:
            with get_db() as c:
                c.execute("""UPDATE users SET name=?,dob=?,address=?,phone=?,education=?,
                  photo_url=?,professional_info=?,hobbies=? WHERE id=?""",(*values,session["user_id"]))
            flash("Profile updated.","success"); return redirect(url_for("profile"))
    return render_template("profile.html",user=me())

@app.route("/people")
@login_required
def people():
    q=request.args.get("q","").strip()
    with get_db() as c:
        users=c.execute("""SELECT u.id,u.name,u.email,u.photo_url,
          (SELECT status FROM friendships f WHERE
           (f.requester_id=? AND f.receiver_id=u.id) OR (f.requester_id=u.id AND f.receiver_id=u.id)) AS ignored
          FROM users u WHERE u.id<>? AND (u.name LIKE ? OR u.email LIKE ?) ORDER BY u.name""",
          (session["user_id"],session["user_id"],f"%{q}%",f"%{q}%")).fetchall()
        relations={}
        for u in users:
            f=c.execute("""SELECT requester_id,receiver_id,status FROM friendships
              WHERE (requester_id=? AND receiver_id=?) OR (requester_id=? AND receiver_id=?)""",
              (session["user_id"],u["id"],u["id"],session["user_id"])).fetchone()
            relations[u["id"]]=f
    return render_template("people.html",users=users,relations=relations,q=q)

@app.route("/friend/request/<int:user_id>",methods=["POST"])
@login_required
def friend_request(user_id):
    if user_id==session["user_id"]: abort(400)
    with get_db() as c:
        target=c.execute("SELECT id FROM users WHERE id=?",(user_id,)).fetchone()
        if not target: abort(404)
        existing=c.execute("""SELECT * FROM friendships WHERE
          (requester_id=? AND receiver_id=?) OR (requester_id=? AND receiver_id=?)""",
          (session["user_id"],user_id,user_id,session["user_id"])).fetchone()
        if existing:
            flash("A friend request or connection already exists.","error")
        else:
            c.execute("INSERT INTO friendships(requester_id,receiver_id,created_at) VALUES(?,?,?)",
              (session["user_id"],user_id,datetime.now().isoformat(timespec="seconds")))
            flash("Friend request sent.","success")
    return redirect(url_for("people"))

@app.route("/friend/<int:friendship_id>/<action>",methods=["POST"])
@login_required
def handle_request(friendship_id,action):
    if action not in ("accept","reject"): abort(400)
    with get_db() as c:
        f=c.execute("SELECT * FROM friendships WHERE id=? AND receiver_id=? AND status='pending'",
                    (friendship_id,session["user_id"])).fetchone()
        if not f: abort(404)
        c.execute("UPDATE friendships SET status=? WHERE id=?",
                  ("accepted" if action=="accept" else "rejected",friendship_id))
    flash("Friend request "+("accepted." if action=="accept" else "rejected."),"success")
    return redirect(url_for("index"))

@app.route("/person/<int:user_id>")
@login_required
def person(user_id):
    with get_db() as c:
        u=c.execute("SELECT id,name,dob,address,education,photo_url,professional_info,hobbies FROM users WHERE id=?",(user_id,)).fetchone()
        if not u: abort(404)
        friend=are_friends(c,session["user_id"],user_id)
    return render_template("person.html",person=u,is_friend=friend)

@app.route("/messages")
@login_required
def messages():
    with get_db() as c:
        friends=c.execute("""SELECT u.id,u.name FROM users u JOIN friendships f
          ON ((f.requester_id=u.id AND f.receiver_id=?) OR (f.receiver_id=u.id AND f.requester_id=?))
          WHERE f.status='accepted' ORDER BY u.name""",(session["user_id"],session["user_id"])).fetchall()
    selected=request.args.get("with",type=int)
    return render_template("messages.html",friends=friends,selected=selected,conversation=[])

@app.route("/messages/<int:user_id>",methods=["GET","POST"])
@login_required
def conversation(user_id):
    with get_db() as c:
        if not are_friends(c,session["user_id"],user_id): abort(403)
        other=c.execute("SELECT id,name FROM users WHERE id=?",(user_id,)).fetchone()
        if not other: abort(404)
        if request.method=="POST":
            body=request.form.get("body","").strip()
            if not body or len(body)>2000: flash("Message must contain 1–2000 characters.","error")
            else:
                c.execute("INSERT INTO messages(sender_id,receiver_id,body,sent_at) VALUES(?,?,?,?)",
                  (session["user_id"],user_id,body,datetime.now().isoformat(timespec="seconds")))
                return redirect(url_for("conversation",user_id=user_id))
        msgs=c.execute("""SELECT m.*,u.name AS sender_name FROM messages m JOIN users u ON u.id=m.sender_id
          WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)
          ORDER BY m.id""",(session["user_id"],user_id,user_id,session["user_id"])).fetchall()
    return render_template("conversation.html",other=other,messages=msgs)

if __name__=="__main__":
    init_db()
    app.run(debug=True)
