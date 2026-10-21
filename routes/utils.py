import random
from functools import wraps
from flask import session, redirect, flash


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue")
            return redirect("/login")
        return view(*args, **kwargs)
    return wrapped


def generate_account_number(cursor):
    """Generate a unique 10-digit account number, checking against existing ones."""
    while True:
        account_no = random.randint(1000000000, 9999999999)
        cursor.execute("SELECT id FROM accounts WHERE account_no=%s", (account_no,))
        if cursor.fetchone() is None:
            return account_no