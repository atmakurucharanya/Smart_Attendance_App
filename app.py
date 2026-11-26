
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
import sqlite3
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = "smart_attendance_demo_secret_2026"

USERNAME = "admin"
PASSWORD = "admin123"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "attendance.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_table():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            roll TEXT UNIQUE NOT NULL,
            class_name TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE(student_id, date)
        )
    """)

    conn.commit()
    conn.close()


def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("home"))
        return function(*args, **kwargs)
    return wrapper


# PWA SERVICE WORKER ROUTE
@app.route("/service-worker.js")
def service_worker():
    response = send_from_directory(
        os.path.join(BASE_DIR, "static"),
        "service-worker.js"
    )
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@app.route("/")
def home():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if username == USERNAME and password == PASSWORD:
        session["logged_in"] = True
        return redirect(url_for("dashboard"))

    return render_template(
        "login.html",
        error="Invalid username or password"
    )


@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()

    total = conn.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    present = conn.execute("""
        SELECT COUNT(*) FROM attendance
        WHERE status = 'Present'
    """).fetchone()[0]

    absent = conn.execute("""
        SELECT COUNT(*) FROM attendance
        WHERE status = 'Absent'
    """).fetchone()[0]

    total_marked = present + absent

    percentage = (
        round((present / total_marked) * 100, 2)
        if total_marked else 0
    )

    conn.close()

    return render_template(
        "dashboard.html",
        total_students=total,
        present_count=present,
        absent_count=absent,
        percentage=percentage
    )


@app.route("/add_student", methods=["GET", "POST"])
@login_required
def add_student():
    error = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        roll = request.form.get("roll", "").strip()
        class_name = request.form.get("class_name", "").strip()

        if not name or not roll or not class_name:
            error = "Please fill all fields."
        else:
            conn = get_db()

            try:
                conn.execute("""
                    INSERT INTO students (name, roll, class_name)
                    VALUES (?, ?, ?)
                """, (name, roll, class_name))

                conn.commit()
                conn.close()
                return redirect(url_for("view_students"))

            except sqlite3.IntegrityError:
                conn.close()
                error = "This Roll Number already exists."

    return render_template("add_student.html", error=error)


@app.route("/students")
@login_required
def view_students():
    conn = get_db()

    students = conn.execute("""
        SELECT * FROM students ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template("students.html", students=students)


@app.route("/edit_student/<int:id>", methods=["GET", "POST"])
@login_required
def edit_student(id):
    conn = get_db()

    student = conn.execute(
        "SELECT * FROM students WHERE id = ?", (id,)
    ).fetchone()

    if student is None:
        conn.close()
        return "Student not found"

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        roll = request.form.get("roll", "").strip()
        class_name = request.form.get("class_name", "").strip()

        if not name or not roll or not class_name:
            conn.close()
            return "Please fill all fields"

        try:
            conn.execute("""
                UPDATE students
                SET name=?, roll=?, class_name=?
                WHERE id=?
            """, (name, roll, class_name, id))

            conn.commit()
            conn.close()
            return redirect(url_for("view_students"))

        except sqlite3.IntegrityError:
            conn.close()
            return "Roll number already exists"

    conn.close()
    return render_template("edit_student.html", student=student)


@app.route("/delete_student/<int:id>", methods=["POST"])
@login_required
def delete_student(id):
    conn = get_db()

    conn.execute(
        "DELETE FROM attendance WHERE student_id = ?", (id,)
    )
    conn.execute(
        "DELETE FROM students WHERE id = ?", (id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("view_students"))


@app.route("/attendance")
@login_required
def attendance():
    conn = get_db()

    students = conn.execute("""
        SELECT id, name, roll, class_name
        FROM students
        ORDER BY name COLLATE NOCASE
    """).fetchall()

    conn.close()

    return render_template("attendance.html", students=students)


@app.route("/mark_attendance", methods=["POST"])
@login_required
def mark_attendance():
    student_id = request.form.get("student_id")
    date = request.form.get("date")
    status = request.form.get("status")

    if not student_id or not date or status not in ["Present", "Absent"]:
        return "Please select student, date and status."

    conn = get_db()

    student = conn.execute(
        "SELECT id FROM students WHERE id = ?",
        (student_id,)
    ).fetchone()

    if student is None:
        conn.close()
        return "Student not found."

    try:
        conn.execute("""
            INSERT INTO attendance (student_id, date, status)
            VALUES (?, ?, ?)
        """, (student_id, date, status))

        conn.commit()
        conn.close()

        return redirect(url_for("view_attendance"))

    except sqlite3.IntegrityError:
        conn.close()
        return "Attendance already marked for this student on this date."


@app.route("/view_attendance")
@login_required
def view_attendance():
    conn = get_db()

    records = conn.execute("""
        SELECT
            attendance.id,
            students.name,
            students.roll,
            students.class_name,
            attendance.date,
            attendance.status
        FROM attendance
        JOIN students
        ON attendance.student_id = students.id
        ORDER BY attendance.date DESC
    """).fetchall()

    conn.close()

    return render_template(
        "view_attendance.html",
        records=records
    )


@app.route("/date_report")
@login_required
def date_report():
    selected_date = request.args.get("date", "")

    conn = get_db()

    if selected_date:
        records = conn.execute("""
            SELECT
                students.name,
                students.roll,
                students.class_name,
                attendance.date,
                attendance.status
            FROM attendance
            JOIN students
            ON attendance.student_id = students.id
            WHERE attendance.date = ?
            ORDER BY students.name
        """, (selected_date,)).fetchall()
    else:
        records = []

    conn.close()

    present_count = sum(
        1 for record in records if record["status"] == "Present"
    )

    absent_count = sum(
        1 for record in records if record["status"] == "Absent"
    )

    return render_template(
        "date_report.html",
        records=records,
        selected_date=selected_date,
        present_count=present_count,
        absent_count=absent_count
    )


if __name__ == "__main__":
    create_table()
    app.run(host="0.0.0.0", port=5000, debug=False)
