from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3, os
from datetime import datetime
from pathlib import Path

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
DB = Path(__file__).with_name("delivery.db")

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS couriers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            locality TEXT NOT NULL,
            service_name TEXT NOT NULL,
            price REAL NOT NULL CHECK(price >= 0),
            available INTEGER NOT NULL DEFAULT 1,
            rating REAL NOT NULL DEFAULT 3.0,
            completed INTEGER NOT NULL DEFAULT 0,
            rewards REAL NOT NULL DEFAULT 0,
            penalties REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_code TEXT UNIQUE NOT NULL,
            sender_name TEXT NOT NULL,
            receiver_name TEXT NOT NULL,
            source TEXT NOT NULL,
            destination TEXT NOT NULL,
            package_details TEXT NOT NULL,
            courier_id INTEGER,
            price REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'Booked',
            scheduled_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(courier_id) REFERENCES couriers(id)
        );
        """)
        count = con.execute("SELECT COUNT(*) FROM couriers").fetchone()[0]
        if count == 0:
            con.executemany("""INSERT INTO couriers
                (name, locality, service_name, price, available, rating)
                VALUES (?, ?, ?, ?, 1, ?)""", [
                ("Aarav Express", "Bhagalpur", "Same Day", 95, 4.8),
                ("QuickKart Logistics", "Bhagalpur", "Standard", 60, 4.5),
                ("Bihar Parcel Co.", "Patna", "Standard", 75, 4.2),
                ("SpeedyShip", "Bhagalpur", "Priority", 125, 4.9),
            ])

def choose_courier(con, destination):
    # Prefer available couriers serving the destination locality.
    rows = con.execute("""SELECT * FROM couriers
        WHERE available=1 AND lower(locality)=lower(?)""", (destination.strip(),)).fetchall()
    if not rows:
        rows = con.execute("SELECT * FROM couriers WHERE available=1").fetchall()
    if not rows:
        return None
    # Lowest price is primary; rating breaks close ties.
    return sorted(rows, key=lambda c: (float(c["price"]), -float(c["rating"])))[0]

def tracking_code(delivery_id):
    return f"DAS{datetime.now().strftime('%y%m%d')}{delivery_id:04d}"

@app.route("/")
def index():
    with db() as con:
        stats = {
            "total": con.execute("SELECT COUNT(*) FROM deliveries WHERE archived=0").fetchone()[0],
            "active": con.execute("SELECT COUNT(*) FROM deliveries WHERE archived=0 AND status NOT IN ('Delivered','Cancelled')").fetchone()[0],
            "couriers": con.execute("SELECT COUNT(*) FROM couriers").fetchone()[0],
            "available": con.execute("SELECT COUNT(*) FROM couriers WHERE available=1").fetchone()[0],
        }
        deliveries = con.execute("""SELECT d.*, c.name AS courier_name FROM deliveries d
            LEFT JOIN couriers c ON c.id=d.courier_id
            WHERE d.archived=0 ORDER BY d.id DESC LIMIT 8""").fetchall()
    return render_template("index.html", stats=stats, deliveries=deliveries)

@app.route("/book", methods=["GET", "POST"])
def book():
    if request.method == "POST":
        data = {k: request.form.get(k, "").strip() for k in
                ["sender_name","receiver_name","source","destination","package_details","scheduled_at"]}
        if not all(data.values()):
            flash("Please complete every field.", "error")
            return render_template("book.html", data=data)
        with db() as con:
            courier = choose_courier(con, data["destination"])
            if not courier:
                flash("No courier is currently available. Add or enable a courier first.", "error")
                return render_template("book.html", data=data)
            now = datetime.now().isoformat(timespec="minutes")
            cur = con.execute("""INSERT INTO deliveries
                (tracking_code,sender_name,receiver_name,source,destination,package_details,
                 courier_id,price,status,scheduled_at,created_at,updated_at)
                VALUES ('PENDING',?,?,?,?,?,?,?,?,?,?,?)""",
                (data["sender_name"],data["receiver_name"],data["source"],data["destination"],
                 data["package_details"],courier["id"],courier["price"],"Booked",
                 data["scheduled_at"],now,now))
            code = tracking_code(cur.lastrowid)
            con.execute("UPDATE deliveries SET tracking_code=? WHERE id=?", (code,cur.lastrowid))
        flash(f"Booking confirmed! Tracking ID: {code}. Assigned to {courier['name']}.", "success")
        return redirect(url_for("delivery_detail", delivery_id=cur.lastrowid))
    return render_template("book.html", data={})

@app.route("/deliveries")
def deliveries():
    q = request.args.get("q","").strip()
    with db() as con:
        rows = con.execute("""SELECT d.*, c.name AS courier_name FROM deliveries d
            LEFT JOIN couriers c ON c.id=d.courier_id
            WHERE d.archived=0 AND (d.tracking_code LIKE ? OR d.receiver_name LIKE ? OR d.destination LIKE ?)
            ORDER BY d.id DESC""", (f"%{q}%",f"%{q}%",f"%{q}%")).fetchall()
    return render_template("deliveries.html", deliveries=rows, q=q)

@app.route("/delivery/<int:delivery_id>")
def delivery_detail(delivery_id):
    with db() as con:
        d = con.execute("""SELECT d.*, c.name AS courier_name, c.service_name
            FROM deliveries d LEFT JOIN couriers c ON c.id=d.courier_id WHERE d.id=?""",
            (delivery_id,)).fetchone()
    if not d:
        flash("Delivery not found.", "error")
        return redirect(url_for("deliveries"))
    return render_template("detail.html", d=d)

@app.route("/delivery/<int:delivery_id>/status", methods=["POST"])
def update_status(delivery_id):
    status = request.form.get("status")
    allowed = ["Booked","Picked Up","In Transit","Out for Delivery","Delivered"]
    if status not in allowed:
        flash("Invalid status.", "error")
        return redirect(url_for("delivery_detail", delivery_id=delivery_id))
    with db() as con:
        d = con.execute("SELECT * FROM deliveries WHERE id=?", (delivery_id,)).fetchone()
        if not d or d["status"] in ("Cancelled","Delivered"):
            flash("This delivery can no longer be updated.", "error")
        else:
            con.execute("UPDATE deliveries SET status=?,updated_at=? WHERE id=?",
                        (status,datetime.now().isoformat(timespec="minutes"),delivery_id))
            if status == "Delivered":
                con.execute("UPDATE couriers SET completed=completed+1,rewards=rewards+50,available=1 WHERE id=?",
                            (d["courier_id"],))
            flash("Delivery status updated.", "success")
    return redirect(url_for("delivery_detail", delivery_id=delivery_id))

@app.route("/delivery/<int:delivery_id>/cancel", methods=["POST"])
def cancel_delivery(delivery_id):
    with db() as con:
        d = con.execute("SELECT * FROM deliveries WHERE id=?", (delivery_id,)).fetchone()
        if not d or d["status"] in ("Delivered","Cancelled"):
            flash("This delivery cannot be cancelled.", "error")
        else:
            con.execute("UPDATE deliveries SET status='Cancelled',updated_at=? WHERE id=?",
                        (datetime.now().isoformat(timespec="minutes"),delivery_id))
            # Cancellation after pickup/in transit incurs a configurable demo penalty.
            if d["status"] in ("Picked Up","In Transit","Out for Delivery") and d["courier_id"]:
                con.execute("UPDATE couriers SET penalties=penalties+25 WHERE id=?", (d["courier_id"],))
            flash("Booking cancelled.", "success")
    return redirect(url_for("delivery_detail", delivery_id=delivery_id))

@app.route("/delivery/<int:delivery_id>/reschedule", methods=["POST"])
def reschedule_delivery(delivery_id):
    scheduled = request.form.get("scheduled_at","").strip()
    with db() as con:
        d = con.execute("SELECT * FROM deliveries WHERE id=?", (delivery_id,)).fetchone()
        if not d or d["status"] in ("Delivered","Cancelled") or not scheduled:
            flash("Rescheduling is not possible. Check the date and delivery status.", "error")
        else:
            con.execute("UPDATE deliveries SET scheduled_at=?,updated_at=? WHERE id=?",
                        (scheduled,datetime.now().isoformat(timespec="minutes"),delivery_id))
            flash("Delivery rescheduled.", "success")
    return redirect(url_for("delivery_detail", delivery_id=delivery_id))

@app.route("/couriers", methods=["GET","POST"])
def couriers():
    if request.method == "POST":
        name=request.form.get("name","").strip()
        locality=request.form.get("locality","").strip()
        service=request.form.get("service_name","").strip()
        try: price=float(request.form.get("price",""))
        except ValueError: price=-1
        try: rating=float(request.form.get("rating","3"))
        except ValueError: rating=3
        if not name or not locality or not service or price < 0 or not 0 <= rating <= 5:
            flash("Enter valid courier details (rating 0–5 and non-negative price).","error")
        else:
            with db() as con:
                con.execute("""INSERT INTO couriers(name,locality,service_name,price,rating)
                    VALUES(?,?,?,?,?)""",(name,locality,service,price,rating))
            flash("Courier added.","success")
        return redirect(url_for("couriers"))
    with db() as con:
        rows=con.execute("SELECT * FROM couriers ORDER BY locality,name").fetchall()
    return render_template("couriers.html", couriers=rows)

@app.route("/courier/<int:courier_id>/availability", methods=["POST"])
def toggle_courier(courier_id):
    with db() as con:
        con.execute("UPDATE couriers SET available=1-available WHERE id=?", (courier_id,))
    flash("Courier availability changed.","success")
    return redirect(url_for("couriers"))

@app.route("/courier/<int:courier_id>/history")
def courier_history(courier_id):
    with db() as con:
        courier=con.execute("SELECT * FROM couriers WHERE id=?",(courier_id,)).fetchone()
        rows=con.execute("SELECT * FROM deliveries WHERE courier_id=? ORDER BY id DESC",(courier_id,)).fetchall()
    if not courier:
        flash("Courier not found.","error")
        return redirect(url_for("couriers"))
    return render_template("history.html",courier=courier,deliveries=rows)

@app.route("/archive", methods=["GET","POST"])
def archive():
    if request.method == "POST":
        did=request.form.get("delivery_id")
        with db() as con:
            con.execute("UPDATE deliveries SET archived=1 WHERE id=? AND status IN ('Delivered','Cancelled')",(did,))
        flash("Eligible delivery archived.","success")
        return redirect(url_for("archive"))
    with db() as con:
        rows=con.execute("""SELECT d.*,c.name AS courier_name FROM deliveries d
            LEFT JOIN couriers c ON c.id=d.courier_id
            WHERE d.archived=0 AND d.status IN ('Delivered','Cancelled') ORDER BY d.id DESC""").fetchall()
        archived=con.execute("""SELECT d.*,c.name AS courier_name FROM deliveries d
            LEFT JOIN couriers c ON c.id=d.courier_id WHERE d.archived=1 ORDER BY d.id DESC""").fetchall()
    return render_template("archive.html", rows=rows, archived=archived)

@app.route("/api/track/<code>")
def api_track(code):
    with db() as con:
        d=con.execute("""SELECT d.tracking_code,d.status,d.source,d.destination,d.scheduled_at,
            d.updated_at,c.name AS courier FROM deliveries d LEFT JOIN couriers c ON c.id=d.courier_id
            WHERE d.tracking_code=?""",(code,)).fetchone()
    if not d: return jsonify({"error":"Tracking ID not found"}),404
    return jsonify(dict(d))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
