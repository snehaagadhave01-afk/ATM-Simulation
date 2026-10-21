from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, request, redirect, flash, session
import bcrypt

from db import get_db_connection, close_connection
from routes.utils import login_required
from config import MAX_WITHDRAWAL_PER_TXN
from extensions import socketio

account_bp = Blueprint("account", __name__)


def _get_account_for_user(cursor, user_id):
    cursor.execute("SELECT * FROM accounts WHERE user_id=%s", (user_id,))
    return cursor.fetchone()


def _parse_amount(raw):
    """Safely parse a form amount into a positive Decimal, or None if invalid."""
    try:
        amount = Decimal(raw)
    except (InvalidOperation, TypeError):
        return None
    if amount <= 0:
        return None
    return amount.quantize(Decimal("0.01"))


def _verify_pin(cursor, user_id, pin):
    cursor.execute("SELECT pin FROM users WHERE id=%s", (user_id,))
    row = cursor.fetchone()
    return row and bcrypt.checkpw(pin.encode(), row["pin"].encode())


def _push_update(user_id, new_balance, txn_type, amount, note):
    """Broadcast a live balance/transaction update to all of this user's open tabs."""
    socketio.emit(
        "balance_update",
        {
            "balance": str(new_balance),
            "type": txn_type,
            "amount": str(amount),
            "note": note,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        room=f"user_{user_id}",
    )


# ------------------------
# Dashboard
# ------------------------
@account_bp.route("/dashboard")
@login_required
def dashboard():
    conn = get_db_connection()
    if conn is None:
        flash("Database connection error")
        return redirect("/login")

    try:
        cursor = conn.cursor(dictionary=True)
        acc = _get_account_for_user(cursor, session["user_id"])

        cursor.execute(
            "SELECT * FROM transactions WHERE account_id=%s ORDER BY created_at DESC LIMIT 10",
            (acc["id"],),
        )
        recent_txns = cursor.fetchall()

        return render_template(
            "dashboard.html",
            full_name=session.get("full_name"),
            account=acc,
            transactions=recent_txns,
        )
    finally:
        cursor.close()
        close_connection(conn)


# ------------------------
# Deposit
# ------------------------
@account_bp.route("/deposit", methods=["POST"])
@login_required
def deposit():
    amount = _parse_amount(request.form.get("amount"))
    if amount is None:
        flash("Enter a valid deposit amount")
        return redirect("/dashboard")

    conn = get_db_connection()
    if conn is None:
        flash("Database connection error")
        return redirect("/dashboard")

    try:
        cursor = conn.cursor(dictionary=True)
        acc = _get_account_for_user(cursor, session["user_id"])

        new_balance = Decimal(acc["balance"]) + amount
        cursor.execute("UPDATE accounts SET balance=%s WHERE id=%s", (new_balance, acc["id"]))
        cursor.execute(
            """INSERT INTO transactions (account_id, type, amount, balance_after, note)
               VALUES (%s, 'DEPOSIT', %s, %s, 'Cash deposit')""",
            (acc["id"], amount, new_balance),
        )
        conn.commit()

        _push_update(session["user_id"], new_balance, "DEPOSIT", amount, "Cash deposit")

        flash(f"Deposited ${amount}. New balance: ${new_balance}")
        return redirect("/dashboard")
    finally:
        cursor.close()
        close_connection(conn)


# ------------------------
# Withdraw (PIN required)
# ------------------------
@account_bp.route("/withdraw", methods=["POST"])
@login_required
def withdraw():
    amount = _parse_amount(request.form.get("amount"))
    pin = request.form.get("pin", "")

    if amount is None:
        flash("Enter a valid withdrawal amount")
        return redirect("/dashboard")

    if amount > MAX_WITHDRAWAL_PER_TXN:
        flash(f"Withdrawal limit per transaction is ${MAX_WITHDRAWAL_PER_TXN}")
        return redirect("/dashboard")

    conn = get_db_connection()
    if conn is None:
        flash("Database connection error")
        return redirect("/dashboard")

    try:
        cursor = conn.cursor(dictionary=True)

        if not _verify_pin(cursor, session["user_id"], pin):
            flash("Incorrect PIN")
            return redirect("/dashboard")

        acc = _get_account_for_user(cursor, session["user_id"])
        balance = Decimal(acc["balance"])

        if amount > balance:
            flash("Insufficient balance")
            return redirect("/dashboard")

        new_balance = balance - amount
        cursor.execute("UPDATE accounts SET balance=%s WHERE id=%s", (new_balance, acc["id"]))
        cursor.execute(
            """INSERT INTO transactions (account_id, type, amount, balance_after, note)
               VALUES (%s, 'WITHDRAW', %s, %s, 'Cash withdrawal')""",
            (acc["id"], amount, new_balance),
        )
        conn.commit()

        _push_update(session["user_id"], new_balance, "WITHDRAW", amount, "Cash withdrawal")

        flash(f"Withdrew ${amount}. New balance: ${new_balance}")
        return redirect("/dashboard")
    finally:
        cursor.close()
        close_connection(conn)


# ------------------------
# Transfer (PIN required)
# ------------------------
@account_bp.route("/transfer", methods=["POST"])
@login_required
def transfer():
    amount = _parse_amount(request.form.get("amount"))
    pin = request.form.get("pin", "")
    to_account_no = request.form.get("to_account", "").strip()

    if amount is None:
        flash("Enter a valid transfer amount")
        return redirect("/dashboard")

    if not to_account_no.isdigit():
        flash("Enter a valid destination account number")
        return redirect("/dashboard")

    conn = get_db_connection()
    if conn is None:
        flash("Database connection error")
        return redirect("/dashboard")

    try:
        cursor = conn.cursor(dictionary=True)

        if not _verify_pin(cursor, session["user_id"], pin):
            flash("Incorrect PIN")
            return redirect("/dashboard")

        sender = _get_account_for_user(cursor, session["user_id"])

        cursor.execute("SELECT * FROM accounts WHERE account_no=%s", (to_account_no,))
        receiver = cursor.fetchone()

        if not receiver:
            flash("Destination account not found")
            return redirect("/dashboard")

        if receiver["id"] == sender["id"]:
            flash("Cannot transfer to your own account")
            return redirect("/dashboard")

        sender_balance = Decimal(sender["balance"])
        if amount > sender_balance:
            flash("Insufficient balance")
            return redirect("/dashboard")

        new_sender_balance = sender_balance - amount
        new_receiver_balance = Decimal(receiver["balance"]) + amount

        cursor.execute("UPDATE accounts SET balance=%s WHERE id=%s", (new_sender_balance, sender["id"]))
        cursor.execute("UPDATE accounts SET balance=%s WHERE id=%s", (new_receiver_balance, receiver["id"]))

        cursor.execute(
            """INSERT INTO transactions (account_id, type, amount, balance_after, note)
               VALUES (%s, 'TRANSFER_OUT', %s, %s, %s)""",
            (sender["id"], amount, new_sender_balance, f"To account {to_account_no}"),
        )
        cursor.execute(
            """INSERT INTO transactions (account_id, type, amount, balance_after, note)
               VALUES (%s, 'TRANSFER_IN', %s, %s, %s)""",
            (receiver["id"], amount, new_receiver_balance, f"From account {sender['account_no']}"),
        )

        conn.commit()

        _push_update(session["user_id"], new_sender_balance, "TRANSFER_OUT", amount, f"To account {to_account_no}")
        _push_update(receiver["user_id"], new_receiver_balance, "TRANSFER_IN", amount, f"From account {sender['account_no']}")

        flash(f"Transferred ${amount} to account {to_account_no}")
        return redirect("/dashboard")

    except Exception:
        conn.rollback()
        flash("Transfer failed, please try again")
        return redirect("/dashboard")
    finally:
        cursor.close()
        close_connection(conn)