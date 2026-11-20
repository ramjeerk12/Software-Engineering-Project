from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3, os, uuid
from datetime import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
DB = os.path.join(os.path.dirname(__file__), "railway.db")

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user'
    );
    CREATE TABLE IF NOT EXISTS routes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL, destination TEXT NOT NULL,
        service_type TEXT NOT NULL CHECK(service_type IN ('Normal','Express')),
        departure TEXT NOT NULL, arrival TEXT NOT NULL,
        rate_per_ton REAL NOT NULL CHECK(rate_per_ton >= 0),
        capacity_tons REAL NOT NULL CHECK(capacity_tons > 0),
        UNIQUE(source, destination, departure, service_type)
    );
    CREATE TABLE IF NOT EXISTS bookings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_code TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL REFERENCES users(id),
        route_id INTEGER NOT NULL REFERENCES routes(id),
        travel_date TEXT NOT NULL,
        commodity TEXT NOT NULL,
        weight REAL NOT NULL CHECK(weight > 0),
        total_cost REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'Confirmed',
        created_at TEXT NOT NULL
    );
    """)
    if not con.execute("SELECT id FROM users WHERE email='admin@railway.com'").fetchone():
        con.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                    ("Administrator","admin@railway.com",generate_password_hash("admin123"),"admin"))
    if con.execute("SELECT COUNT(*) n FROM routes").fetchone()["n"] == 0:
        samples = [
            ("Bhagalpur","Patna","Normal","08:00","16:00",1200,40),
            ("Bhagalpur","Patna","Express","20:00","02:00",1600,25),
            ("Patna","Kolkata","Normal","07:30","21:00",1800,50),
            ("Patna","Delhi","Express","18:00","10:00",2500,30),
            ("Kolkata","Patna","Normal","06:00","20:00",1750,45),
        ]
        con.executemany("""INSERT INTO routes(source,destination,service_type,departure,arrival,rate_per_ton,capacity_tons)
                           VALUES(?,?,?,?,?,?,?)""", samples)
    con.commit()
    con.close()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Administrator access required.", "danger")
            return redirect(url_for("index"))
        return fn(*args, **kwargs)
    return wrapper

def remaining_capacity(con, route_id, travel_date):
    route = con.execute("SELECT capacity_tons FROM routes WHERE id=?", (route_id,)).fetchone()
    booked = con.execute("""SELECT COALESCE(SUM(weight),0) total FROM bookings
                            WHERE route_id=? AND travel_date=? AND status='Confirmed'""",
                         (route_id, travel_date)).fetchone()["total"]
    return route["capacity_tons"] - booked

@app.route("/")
def index():
    con = db()
    routes = con.execute("SELECT * FROM routes ORDER BY source,destination").fetchall()
    con.close()
    return render_template("index.html", routes=routes)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name, email = request.form["name"].strip(), request.form["email"].strip().lower()
        password = request.form["password"]
        if not name or len(password) < 6:
            flash("Enter your name and a password of at least 6 characters.", "danger")
            return render_template("register.html")
        con = db()
        try:
            con.execute("INSERT INTO users(name,email,password) VALUES(?,?,?)",
                        (name,email,generate_password_hash(password)))
            con.commit()
            flash("Registration successful. Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That email address is already registered.", "danger")
        finally:
            con.close()
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        con = db()
        user = con.execute("SELECT * FROM users WHERE email=?", (request.form["email"].lower(),)).fetchone()
        con.close()
        if user and check_password_hash(user["password"], request.form["password"]):
            session.update(user_id=user["id"], name=user["name"], role=user["role"])
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    con = db()
    stats = {
        "total": con.execute("SELECT COUNT(*) n FROM bookings WHERE user_id=?", (session["user_id"],)).fetchone()["n"],
        "active": con.execute("SELECT COUNT(*) n FROM bookings WHERE user_id=? AND status='Confirmed'", (session["user_id"],)).fetchone()["n"],
        "cancelled": con.execute("SELECT COUNT(*) n FROM bookings WHERE user_id=? AND status='Cancelled'", (session["user_id"],)).fetchone()["n"]
    }
    bookings = con.execute("""SELECT b.*,r.source,r.destination,r.service_type,r.departure
                              FROM bookings b JOIN routes r ON r.id=b.route_id
                              WHERE b.user_id=? ORDER BY b.id DESC""", (session["user_id"],)).fetchall()
    con.close()
    return render_template("dashboard.html", stats=stats, bookings=bookings)

@app.route("/availability", methods=["GET","POST"])
def availability():
    results, travel_date = [], request.values.get("travel_date","")
    source, destination = request.values.get("source",""), request.values.get("destination","")
    if request.method == "POST":
        if not travel_date:
            flash("Please select a travel date.", "danger")
        else:
            con = db()
            query = "SELECT * FROM routes WHERE 1=1"
            params = []
            if source: query += " AND source=?"; params.append(source)
            if destination: query += " AND destination=?"; params.append(destination)
            for r in con.execute(query, params).fetchall():
                results.append(dict(r) | {"remaining": remaining_capacity(con,r["id"],travel_date)})
            con.close()
    con = db()
    stations = sorted({r["source"] for r in con.execute("SELECT source FROM routes")} |
                      {r["destination"] for r in con.execute("SELECT destination FROM routes")})
    con.close()
    return render_template("availability.html", results=results, travel_date=travel_date,
                           source=source, destination=destination, stations=stations)

@app.route("/book/<int:route_id>", methods=["GET","POST"])
@login_required
def book(route_id):
    con = db()
    route = con.execute("SELECT * FROM routes WHERE id=?", (route_id,)).fetchone()
    if not route:
        con.close(); flash("Route not found.", "danger"); return redirect(url_for("availability"))
    if request.method == "POST":
        travel_date, commodity = request.form["travel_date"], request.form["commodity"].strip()
        try: weight = float(request.form["weight"])
        except ValueError: weight = 0
        if not travel_date or datetime.strptime(travel_date,"%Y-%m-%d").date() < datetime.today().date():
            flash("Choose today or a future travel date.", "danger")
        elif not commodity or weight <= 0:
            flash("Enter a commodity and a valid weight.", "danger")
        else:
            # BEGIN IMMEDIATE serializes capacity checks to prevent overbooking.
            con.execute("BEGIN IMMEDIATE")
            remaining = remaining_capacity(con, route_id, travel_date)
            if weight > remaining:
                con.rollback()
                flash(f"Insufficient capacity. Only {remaining:.2f} tonnes remain.", "danger")
            else:
                code = "RC-" + uuid.uuid4().hex[:10].upper()
                cost = weight * route["rate_per_ton"]
                con.execute("""INSERT INTO bookings(booking_code,user_id,route_id,travel_date,commodity,weight,total_cost,status,created_at)
                               VALUES(?,?,?,?,?,?,?,'Confirmed',?)""",
                            (code,session["user_id"],route_id,travel_date,commodity,weight,cost,datetime.now().isoformat(timespec="seconds")))
                con.commit()
                con.close()
                flash(f"Booking confirmed! Your booking ID is {code}.", "success")
                return redirect(url_for("dashboard"))
    con.close()
    return render_template("book.html", route=route)

@app.route("/cancel/<int:booking_id>", methods=["POST"])
@login_required
def cancel(booking_id):
    con = db()
    booking = con.execute("SELECT * FROM bookings WHERE id=? AND user_id=?",
                          (booking_id,session["user_id"])).fetchone()
    if not booking:
        flash("Booking not found or you are not allowed to cancel it.", "danger")
    elif booking["status"] != "Confirmed":
        flash("This booking is already cancelled.", "warning")
    elif booking["travel_date"] < datetime.today().strftime("%Y-%m-%d"):
        flash("Past bookings cannot be cancelled.", "danger")
    else:
        con.execute("UPDATE bookings SET status='Cancelled' WHERE id=?", (booking_id,))
        con.commit()
        flash(f"Booking {booking['booking_code']} cancelled successfully. Capacity has been released.", "success")
    con.close()
    return redirect(url_for("dashboard"))

@app.route("/admin")
@login_required
@admin_required
def admin():
    con = db()
    routes = con.execute("SELECT * FROM routes ORDER BY id DESC").fetchall()
    bookings = con.execute("""SELECT b.*,u.name,r.source,r.destination FROM bookings b
                              JOIN users u ON u.id=b.user_id JOIN routes r ON r.id=b.route_id
                              ORDER BY b.id DESC LIMIT 30""").fetchall()
    con.close()
    return render_template("admin.html", routes=routes, bookings=bookings)

@app.route("/admin/routes", methods=["POST"])
@login_required
@admin_required
def add_route():
    try:
        data = (request.form["source"].strip(),request.form["destination"].strip(),
                request.form["service_type"],request.form["departure"],request.form["arrival"],
                float(request.form["rate_per_ton"]),float(request.form["capacity_tons"]))
        if not data[0] or not data[1] or data[0] == data[1] or data[5] < 0 or data[6] <= 0:
            raise ValueError()
        con = db()
        con.execute("""INSERT INTO routes(source,destination,service_type,departure,arrival,rate_per_ton,capacity_tons)
                       VALUES(?,?,?,?,?,?,?)""", data)
        con.commit(); con.close()
        flash("Route added successfully.", "success")
    except (ValueError, sqlite3.IntegrityError, KeyError):
        flash("Invalid route details or duplicate schedule.", "danger")
    return redirect(url_for("admin"))

@app.route("/admin/routes/delete/<int:route_id>", methods=["POST"])
@login_required
@admin_required
def delete_route(route_id):
    con = db()
    used = con.execute("SELECT COUNT(*) n FROM bookings WHERE route_id=?", (route_id,)).fetchone()["n"]
    if used:
        flash("This route has booking history and cannot be deleted.", "danger")
    else:
        con.execute("DELETE FROM routes WHERE id=?", (route_id,)); con.commit()
        flash("Route deleted.", "success")
    con.close()
    return redirect(url_for("admin"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
