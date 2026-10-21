from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, flash, session
import bcrypt

from db import get_db_connection, close_connection
from routes.utils import generate_account_number
from config import MAX_LOGIN_ATTEMPTS, LOCKOUT_MINUTES, INITIAL_BALANCE

auth_bp = Blueprint("auth", __name__)


# ------------------------
# Register Page
# ------------------------
@auth_bp.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        pin = request.form.get("pin", "")

        # ---- Basic server-side validation ----
        if not all([full_name, email, phone, password, pin]):
            flash("All fields are required")
            return redirect("/register")

        if len(password) < 8:
            flash("Password must be at least 8 characters")
            return redirect("/register")

        if not (pin.isdigit() and len(pin) == 4):
            flash("PIN must be exactly 4 digits")
            return redirect("/register")

        conn = get_db_connection()
        if conn is None:
            flash("Database connection error, please try again later")
            return redirect("/register")

        try:
            cursor = conn.cursor(dictionary=True)

            # Check email
            cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
            if cursor.fetchone():
                flash("Email already exists")
                return redirect("/register")

            # Check phone
            cursor.execute("SELECT id FROM users WHERE phone=%s", (phone,))
            if cursor.fetchone():
                flash("Phone already exists")
                return redirect("/register")

            # Hash password and PIN separately (never store either in plain text)
            password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            pin_hash = bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()

            cursor.execute(
                """
                INSERT INTO users (full_name, email, phone, password, pin)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (full_name, email, phone, password_hash, pin_hash),
            )
            conn.commit()
            user_id = cursor.lastrowid

            account_no = generate_account_number(cursor)

            cursor.execute(
                """
                INSERT INTO accounts (account_no, user_id, balance, status)
                VALUES (%s, %s, %s, %s)
                """,
                (account_no, user_id, INITIAL_BALANCE, "ACTIVE"),
            )
            conn.commit()

            flash(f"Registration successful! Your account number is {account_no}")
            return redirect("/login")

        finally:
            cursor.close()
            close_connection(conn)

    return render_template("register.html")


# ------------------------
# Login Page
# ------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db_connection()
        if conn is None:
            flash("Database connection error, please try again later")
            return redirect("/login")

        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
            user = cursor.fetchone()

            # Same generic error whether email doesn't exist or password is wrong,
            # so we don't leak which emails are registered.
            generic_error = "Invalid email or password"

            if not user:
                flash(generic_error)
                return redirect("/login")

            # ---- Account lockout check ----
            if user["locked_until"] and user["locked_until"] > datetime.now():
                minutes_left = int((user["locked_until"] - datetime.now()).total_seconds() // 60) + 1
                flash(f"Account locked. Try again in {minutes_left} minute(s).")
                return redirect("/login")

            # ---- Password check ----
            if not bcrypt.checkpw(password.encode(), user["password"].encode()):
                attempts = user["failed_attempts"] + 1

                if attempts >= MAX_LOGIN_ATTEMPTS:
                    locked_until = datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)
                    cursor.execute(
                        "UPDATE users SET failed_attempts=%s, locked_until=%s WHERE id=%s",
                        (attempts, locked_until, user["id"]),
                    )
                    conn.commit()
                    flash(f"Too many failed attempts. Account locked for {LOCKOUT_MINUTES} minutes.")
                else:
                    cursor.execute(
                        "UPDATE users SET failed_attempts=%s WHERE id=%s",
                        (attempts, user["id"]),
                    )
                    conn.commit()
                    flash(generic_error)

                return redirect("/login")

            # ---- Success: reset attempts, start session ----
            cursor.execute(
                "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE id=%s",
                (user["id"],),
            )
            conn.commit()

            session.clear()
            session["user_id"] = user["id"]
            session["full_name"] = user["full_name"]
            session.permanent = True

            return redirect("/dashboard")

        finally:
            cursor.close()
            close_connection(conn)

    return render_template("login.html")


# ------------------------
# Logout
# ------------------------
@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out")
    return redirect("/login")