from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import date

app = Flask(__name__)
app.secret_key = "your_secret_key"

FACTORS = {"car_km":0.171, "bus_km":0.104, "electricity_kwh":0.82, "veg_meal":1.0, "nonveg_meal":3.0,"waste_kg": 1.8}

# Initialize the database
with sqlite3.connect("users.db") as conn:
    conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tracker (
            id INTEGER PRIMARY KEY,
            username TEXT,
            date TEXT,
            total REAL,
            breakdown TEXT,
            FOREIGN KEY (username) REFERENCES users (username)
        )
    """)
    conn.commit()

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])
        with sqlite3.connect("users.db") as conn:
            try:
                conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
                conn.commit()
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                return "User already exists!"
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        with sqlite3.connect("users.db") as conn:
            user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if user and check_password_hash(user[2], password):
                session["user"] = username
                return redirect(url_for("index"))
        return "Invalid credentials!"
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return render_template("logout.html")

@app.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("index.html")

@app.route("/calculate", methods=["POST"])
def calculate():
    if "user" not in session:
        return redirect(url_for("login"))

    car = float(request.form.get("car_km", 0)) * FACTORS["car_km"]
    bus = float(request.form.get("bus_km", 0)) * FACTORS["bus_km"]
    elec = float(request.form.get("electricity_kwh", 0)) * FACTORS["electricity_kwh"]
    waste = float(request.form.get("waste_kg", 0)) * FACTORS["waste_kg"]

    veg_meal_choice = request.form.get("veg_meal_choice", "salad")
    veg_meal_factor = {"salad": 0.8, "pasta": 1.2, "tofu": 1.5}
    veg_meal_footprint = float(request.form.get("veg_meals", 0)) * veg_meal_factor.get(veg_meal_choice, 1.0)

    food = veg_meal_footprint + (float(request.form.get("nonveg_meals", 0)) * FACTORS["nonveg_meal"])
    total = round(car + bus + elec + food + waste, 2)
    breakdown = {
        "Car": car,
        "Bus": bus,
        "Electricity": elec,
        "Vegetarian Meals": veg_meal_footprint,
        "Non-Vegetarian Meals": float(request.form.get("nonveg_meals", 0)) * FACTORS["nonveg_meal"],
        "Waste": waste
    }

    # Store the result in the tracker table
    with sqlite3.connect("users.db") as conn:
        conn.execute(
            "INSERT INTO tracker (username, date, total, breakdown) VALUES (?, ?, ?, ?)",
            (session["user"], date.today().isoformat(), total, str(breakdown))
        )
        conn.commit()

    return render_template("results.html", total=total, breakdown=breakdown)

@app.route("/tracker")
def tracker():
    if "user" not in session:
        return redirect(url_for("login"))

    with sqlite3.connect("users.db") as conn:
        rows = conn.execute(
            "SELECT date, SUM(total) as daily_total FROM tracker WHERE username = ? GROUP BY date ORDER BY date DESC",
            (session["user"],)
        ).fetchall()

        avg_emission = conn.execute(
            "SELECT AVG(total) FROM tracker"
        ).fetchone()[0] or 0

    return render_template("tracker.html", rows=rows, avg_emission=avg_emission)

if __name__ == "__main__":
    app.run(debug=True)