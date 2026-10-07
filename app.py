from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import date, datetime

app = Flask(__name__)
app.secret_key = "student-planner-secret-key-change-this"

DATABASE = "database.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            task_date TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'Low',
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if not name or not email or not password:
            flash("All fields are required.", "danger")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return render_template("register.html")

        conn = get_db()

        try:
            conn.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password))
            )

            conn.commit()

            flash(
                "Account created successfully. Please login.",
                "success"
            )

            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash("Email is already registered.", "danger")
            return render_template("register.html")

        finally:
            conn.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_db()

        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(user["password"], password):

            session.clear()

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():

    conn = get_db()

    user_id = session["user_id"]

    # ---------------------------------------
    # ALL TASKS
    # ---------------------------------------

    tasks = conn.execute("""
        SELECT * FROM tasks
        WHERE user_id = ?
        ORDER BY
            CASE WHEN status = 'Pending' THEN 0 ELSE 1 END,
            task_date ASC,
            CASE priority
                WHEN 'High' THEN 0
                WHEN 'Medium' THEN 1
                ELSE 2
            END
    """, (user_id,)).fetchall()


    # ---------------------------------------
    # TOTAL TASKS
    # ---------------------------------------

    total = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE user_id = ?",
        (user_id,)
    ).fetchone()[0]


    # ---------------------------------------
    # PENDING TASKS
    # ---------------------------------------

    pending = conn.execute(
        """
        SELECT COUNT(*)
        FROM tasks
        WHERE user_id = ?
        AND status = 'Pending'
        """,
        (user_id,)
    ).fetchone()[0]


    # ---------------------------------------
    # COMPLETED TASKS
    # ---------------------------------------

    completed = conn.execute(
        """
        SELECT COUNT(*)
        FROM tasks
        WHERE user_id = ?
        AND status = 'Completed'
        """,
        (user_id,)
    ).fetchone()[0]


    # ---------------------------------------
    # TODAY'S DATE
    # ---------------------------------------

    today = date.today().isoformat()


    # ---------------------------------------
    # TODAY'S TASKS
    # ---------------------------------------

    today_total = conn.execute(
        """
        SELECT COUNT(*)
        FROM tasks
        WHERE user_id = ?
        AND task_date = ?
        """,
        (user_id, today)
    ).fetchone()[0]


    # ---------------------------------------
    # TODAY'S COMPLETED TASKS
    # ---------------------------------------

    today_completed = conn.execute(
        """
        SELECT COUNT(*)
        FROM tasks
        WHERE user_id = ?
        AND task_date = ?
        AND status = 'Completed'
        """,
        (user_id, today)
    ).fetchone()[0]


    # ---------------------------------------
    # TODAY'S PROGRESS PERCENTAGE
    # ---------------------------------------

    today_progress = 0

    if today_total > 0:
        today_progress = round(
            (today_completed / today_total) * 100
        )


    # ---------------------------------------
    # UPCOMING TASKS
    # ---------------------------------------

    upcoming = conn.execute("""
        SELECT * FROM tasks
        WHERE user_id = ?
        AND status = 'Pending'
        AND task_date >= ?
        ORDER BY task_date ASC
        LIMIT 5
    """, (user_id, today)).fetchall()


    # ---------------------------------------
    # SUBJECTS
    # ---------------------------------------

    subjects = conn.execute("""
        SELECT subject, COUNT(*) AS count
        FROM tasks
        WHERE user_id = ?
        GROUP BY subject
        ORDER BY count DESC
    """, (user_id,)).fetchall()


    conn.close()


    # ---------------------------------------
    # SEND DATA TO DASHBOARD
    # ---------------------------------------

    return render_template(
        "dashboard.html",

        tasks=tasks,

        total=total,

        pending=pending,

        completed=completed,

        upcoming=upcoming,

        subjects=subjects,

        today=today,

        today_total=today_total,

        today_completed=today_completed,

        today_progress=today_progress
    )


@app.route("/tasks")
@login_required
def tasks_page():

    conn = get_db()

    rows = conn.execute("""
        SELECT * FROM tasks
        WHERE user_id = ?
        ORDER BY task_date ASC, id DESC
    """, (session["user_id"],)).fetchall()

    conn.close()

    return render_template(
        "tasks.html",
        tasks=rows,
        today=date.today().isoformat()
    )


@app.route("/add-task", methods=["GET", "POST"])
@login_required
def add_task():

    if request.method == "POST":

        title = request.form["title"].strip()
        subject = request.form["subject"].strip()
        task_date = request.form["task_date"]
        priority = request.form["priority"]

        if not title or not subject or not task_date:

            flash(
                "Please fill all task fields.",
                "danger"
            )

            return render_template(
                "add_task.html",
                today=date.today().isoformat()
            )


        conn = get_db()

        conn.execute("""
            INSERT INTO tasks
            (user_id, title, subject, task_date, priority)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            title,
            subject,
            task_date,
            priority
        ))

        conn.commit()

        conn.close()

        flash(
            "Task added successfully.",
            "success"
        )

        return redirect(url_for("dashboard"))


    return render_template(
        "add_task.html",
        today=date.today().isoformat()
    )


@app.route("/edit-task/<int:task_id>", methods=["GET", "POST"])
@login_required
def edit_task(task_id):

    conn = get_db()

    task = conn.execute(
        """
        SELECT *
        FROM tasks
        WHERE id = ?
        AND user_id = ?
        """,
        (task_id, session["user_id"])
    ).fetchone()


    if not task:

        conn.close()

        flash(
            "Task not found.",
            "danger"
        )

        return redirect(url_for("dashboard"))


    if request.method == "POST":

        title = request.form["title"].strip()
        subject = request.form["subject"].strip()
        task_date = request.form["task_date"]
        priority = request.form["priority"]


        conn.execute("""
            UPDATE tasks

            SET
                title = ?,
                subject = ?,
                task_date = ?,
                priority = ?

            WHERE id = ?
            AND user_id = ?
        """, (
            title,
            subject,
            task_date,
            priority,
            task_id,
            session["user_id"]
        ))


        conn.commit()

        conn.close()


        flash(
            "Task updated successfully.",
            "success"
        )

        return redirect(url_for("dashboard"))


    conn.close()

    return render_template(
        "edit_task.html",
        task=task
    )


@app.post("/complete-task/<int:task_id>")
@login_required
def complete_task(task_id):

    conn = get_db()

    conn.execute("""
        UPDATE tasks

        SET status =
            CASE
                WHEN status = 'Pending'
                THEN 'Completed'

                ELSE 'Pending'
            END

        WHERE id = ?
        AND user_id = ?
    """, (
        task_id,
        session["user_id"]
    ))

    conn.commit()

    conn.close()

    flash(
        "Task status updated.",
        "success"
    )

    return redirect(
        request.referrer or url_for("dashboard")
    )


@app.post("/delete-task/<int:task_id>")
@login_required
def delete_task(task_id):

    conn = get_db()

    conn.execute(
        """
        DELETE FROM tasks
        WHERE id = ?
        AND user_id = ?
        """,
        (
            task_id,
            session["user_id"]
        )
    )

    conn.commit()

    conn.close()

    flash(
        "Task deleted successfully.",
        "success"
    )

    return redirect(
        request.referrer or url_for("dashboard")
    )


@app.route("/logout")
def logout():

    session.clear()

    return render_template(
        "logout.html"
    )


if __name__ == "__main__":

    init_db()

    app.run(debug=True)