import os, sqlite3
from functools import wraps
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-development-secret")
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(app.instance_path, "transport.db"))
os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(_=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL,
      email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'student', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS buses (
      id INTEGER PRIMARY KEY AUTOINCREMENT, bus_number TEXT NOT NULL UNIQUE,
      capacity INTEGER NOT NULL CHECK(capacity > 0), active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS routes (
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
      start_point TEXT NOT NULL, end_point TEXT NOT NULL, stops TEXT NOT NULL DEFAULT '',
      active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS trips (
      id INTEGER PRIMARY KEY AUTOINCREMENT, bus_id INTEGER NOT NULL REFERENCES buses(id),
      route_id INTEGER NOT NULL REFERENCES routes(id), travel_date TEXT NOT NULL,
      departure_time TEXT NOT NULL, arrival_time TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS bookings (
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id),
      trip_id INTEGER NOT NULL REFERENCES trips(id), seat_number INTEGER NOT NULL,
      status TEXT NOT NULL DEFAULT 'Confirmed', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      CHECK(seat_number > 0)
    );
    CREATE UNIQUE INDEX IF NOT EXISTS uq_active_trip_seat ON bookings(trip_id, seat_number) WHERE status='Confirmed';
    """)
    # Seed demo routes/trips and an admin account for local coursework demonstration.
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        conn.execute("INSERT INTO users(full_name,email,password_hash,role) VALUES(?,?,?,?)",
                     ("System Administrator", "admin@college.edu", generate_password_hash("Admin123!"), "admin"))
    if conn.execute("SELECT COUNT(*) FROM buses").fetchone()[0] == 0:
        conn.execute("INSERT INTO buses(bus_number,capacity) VALUES('COLLEGE-01',40)")
        conn.execute("INSERT INTO buses(bus_number,capacity) VALUES('COLLEGE-02',32)")
    if conn.execute("SELECT COUNT(*) FROM routes").fetchone()[0] == 0:
        conn.execute("INSERT INTO routes(name,start_point,end_point,stops) VALUES(?,?,?,?)",
                     ("North Route", "North Gate", "College Campus", "Central Junction, Library Stop"))
        conn.execute("INSERT INTO routes(name,start_point,end_point,stops) VALUES(?,?,?,?)",
                     ("South Route", "South Bus Stand", "College Campus", "Market Road, Lake View"))
    if conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0] == 0:
        buses = conn.execute("SELECT id FROM buses ORDER BY id").fetchall()
        routes = conn.execute("SELECT id FROM routes ORDER BY id").fetchall()
        tomorrow = date.today().isoformat()
        for i, (b, r) in enumerate(zip(buses, routes)):
            conn.execute("INSERT INTO trips(bus_id,route_id,travel_date,departure_time,arrival_time) VALUES(?,?,?,?,?)",
                         (b["id"], r["id"], tomorrow, "08:00", "08:45"))
    conn.commit()
    conn.close()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Administrator access is required.", "danger")
            return redirect(url_for("index"))
        return fn(*args, **kwargs)
    return wrapper

@app.context_processor
def common_context():
    return {"current_user": session.get("name"), "current_role": session.get("role"), "today": date.today().isoformat()}

@app.route("/")
def index():
    today = date.today().isoformat()
    trips = db().execute("""
      SELECT t.*, b.bus_number, b.capacity, r.name route_name, r.start_point, r.end_point, r.stops,
      (SELECT COUNT(*) FROM bookings bk WHERE bk.trip_id=t.id AND bk.status='Confirmed') booked
      FROM trips t JOIN buses b ON b.id=t.bus_id JOIN routes r ON r.id=t.route_id
      WHERE t.active=1 AND b.active=1 AND r.active=1 AND t.travel_date>=?
      ORDER BY t.travel_date,t.departure_time
    """, (today,)).fetchall()
    return render_template("index.html", trips=trips)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name = request.form.get("full_name","").strip()
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        if not name or not email or len(password) < 8:
            flash("Enter your name, email, and a password of at least 8 characters.", "danger")
            return render_template("register.html")
        if not email.endswith("@college.edu"):
            flash("Use your college email address (demo rule: @college.edu).", "danger")
            return render_template("register.html")
        try:
            db().execute("INSERT INTO users(full_name,email,password_hash,role) VALUES(?,?,?,'student')",
                         (name,email,generate_password_hash(password)))
            db().commit()
            flash("Account created. You can now log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("An account with that email already exists.", "danger")
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        user = db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"], session["name"], session["role"] = user["id"], user["full_name"], user["role"]
            flash("Welcome back!", "success")
            return redirect(url_for("admin" if user["role"] == "admin" else "index"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have logged out.", "success")
    return redirect(url_for("index"))

@app.route("/book/<int:trip_id>", methods=["GET","POST"])
@login_required
def book(trip_id):
    trip = db().execute("""
      SELECT t.*,b.bus_number,b.capacity,r.name route_name,r.start_point,r.end_point
      FROM trips t JOIN buses b ON b.id=t.bus_id JOIN routes r ON r.id=t.route_id
      WHERE t.id=? AND t.active=1 AND b.active=1 AND r.active=1
    """,(trip_id,)).fetchone()
    if not trip:
        flash("Trip not found or unavailable.", "danger"); return redirect(url_for("index"))
    occupied = {row["seat_number"] for row in db().execute(
        "SELECT seat_number FROM bookings WHERE trip_id=? AND status='Confirmed'",(trip_id,)).fetchall()}
    if request.method == "POST":
        try: seat = int(request.form.get("seat_number","0"))
        except ValueError: seat = 0
        if seat < 1 or seat > trip["capacity"]:
            flash("Choose a valid seat number.", "danger")
        else:
            try:
                db().execute("INSERT INTO bookings(user_id,trip_id,seat_number) VALUES(?,?,?)",
                             (session["user_id"],trip_id,seat))
                db().commit()
                flash(f"Booking confirmed! Your booking ID is #{db().execute('SELECT last_insert_rowid()').fetchone()[0]}.","success")
                return redirect(url_for("my_bookings"))
            except sqlite3.IntegrityError:
                db().rollback()
                flash("That seat was just booked by someone else. Please select another seat.", "danger")
        occupied = {row["seat_number"] for row in db().execute(
            "SELECT seat_number FROM bookings WHERE trip_id=? AND status='Confirmed'",(trip_id,)).fetchall()}
    return render_template("book.html", trip=trip, occupied=occupied)

@app.route("/my-bookings")
@login_required
def my_bookings():
    rows = db().execute("""
      SELECT bk.*,t.travel_date,t.departure_time,t.arrival_time,b.bus_number,r.name route_name,
      r.start_point,r.end_point FROM bookings bk JOIN trips t ON t.id=bk.trip_id
      JOIN buses b ON b.id=t.bus_id JOIN routes r ON r.id=t.route_id
      WHERE bk.user_id=? ORDER BY bk.created_at DESC
    """,(session["user_id"],)).fetchall()
    return render_template("my_bookings.html", bookings=rows)

@app.route("/cancel/<int:booking_id>", methods=["POST"])
@login_required
def cancel(booking_id):
    booking = db().execute("SELECT * FROM bookings WHERE id=? AND user_id=?",
                           (booking_id,session["user_id"])).fetchone()
    if not booking:
        flash("Booking not found.", "danger")
    elif booking["status"] != "Confirmed":
        flash("Only confirmed bookings can be cancelled.", "warning")
    else:
        db().execute("UPDATE bookings SET status='Cancelled' WHERE id=?",(booking_id,))
        db().commit()
        flash("Booking cancelled. The seat is now available.", "success")
    return redirect(url_for("my_bookings"))

@app.route("/admin")
@login_required
@admin_required
def admin():
    conn=db()
    buses=conn.execute("SELECT * FROM buses ORDER BY bus_number").fetchall()
    routes=conn.execute("SELECT * FROM routes ORDER BY name").fetchall()
    trips=conn.execute("""SELECT t.*,b.bus_number,r.name route_name FROM trips t JOIN buses b ON b.id=t.bus_id
                          JOIN routes r ON r.id=t.route_id ORDER BY t.travel_date,t.departure_time""").fetchall()
    bookings=conn.execute("""SELECT bk.*,u.full_name,u.email,t.travel_date,t.departure_time,b.bus_number,r.name route_name
      FROM bookings bk JOIN users u ON u.id=bk.user_id JOIN trips t ON t.id=bk.trip_id
      JOIN buses b ON b.id=t.bus_id JOIN routes r ON r.id=t.route_id ORDER BY bk.created_at DESC""").fetchall()
    return render_template("admin.html",buses=buses,routes=routes,trips=trips,bookings=bookings)

@app.route("/admin/bus", methods=["POST"])
@login_required
@admin_required
def add_bus():
    number=request.form.get("bus_number","").strip()
    try: capacity=int(request.form.get("capacity","0"))
    except ValueError: capacity=0
    if not number or capacity < 1:
        flash("Enter a bus number and positive capacity.","danger")
    else:
        try:
            db().execute("INSERT INTO buses(bus_number,capacity) VALUES(?,?)",(number,capacity)); db().commit()
            flash("Bus added.","success")
        except sqlite3.IntegrityError: flash("That bus number already exists.","danger")
    return redirect(url_for("admin"))

@app.route("/admin/route", methods=["POST"])
@login_required
@admin_required
def add_route():
    name=request.form.get("name","").strip(); start=request.form.get("start_point","").strip()
    end=request.form.get("end_point","").strip(); stops=request.form.get("stops","").strip()
    if not name or not start or not end: flash("Route name, start, and destination are required.","danger")
    else:
        db().execute("INSERT INTO routes(name,start_point,end_point,stops) VALUES(?,?,?,?)",(name,start,end,stops))
        db().commit(); flash("Route added.","success")
    return redirect(url_for("admin"))

@app.route("/admin/trip", methods=["POST"])
@login_required
@admin_required
def add_trip():
    try:
        bus_id=int(request.form["bus_id"]); route_id=int(request.form["route_id"])
        travel_date=request.form["travel_date"]; departure=request.form["departure_time"]; arrival=request.form["arrival_time"]
        if travel_date < date.today().isoformat(): raise ValueError()
        db().execute("INSERT INTO trips(bus_id,route_id,travel_date,departure_time,arrival_time) VALUES(?,?,?,?,?)",
                     (bus_id,route_id,travel_date,departure,arrival)); db().commit()
        flash("Trip scheduled.","success")
    except (ValueError,KeyError,sqlite3.IntegrityError):
        db().rollback(); flash("Please enter valid trip details and a non-past date.","danger")
    return redirect(url_for("admin"))

@app.route("/admin/report.csv")
@login_required
@admin_required
def report():
    import csv, io
    output=io.StringIO()
    writer=csv.writer(output)
    writer.writerow(["Booking ID","Student","Email","Bus","Route","Travel Date","Departure","Seat","Status","Created"])
    rows=db().execute("""SELECT bk.id,u.full_name,u.email,b.bus_number,r.name,t.travel_date,t.departure_time,
       bk.seat_number,bk.status,bk.created_at FROM bookings bk JOIN users u ON u.id=bk.user_id
       JOIN trips t ON t.id=bk.trip_id JOIN buses b ON b.id=t.bus_id JOIN routes r ON r.id=t.route_id
       ORDER BY bk.created_at DESC""").fetchall()
    writer.writerows([tuple(r) for r in rows])
    from flask import Response
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition":"attachment; filename=booking-report.csv"})

@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", message="The page you requested was not found."),404

@app.errorhandler(500)
def server_error(_):
    db().rollback()
    return render_template("error.html", message="Something went wrong. Please try again."),500

init_db()
if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", host="0.0.0.0", port=int(os.environ.get("PORT","5000")))
