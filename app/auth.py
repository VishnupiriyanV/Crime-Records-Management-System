import secrets
from functools import wraps

from flask import abort, flash, g, redirect, request, session, url_for

from .db import one


def load_user():
    user_id = session.get("user_id")
    g.user = None
    if user_id:
        user = one("SELECT user_id, name, email, role, active FROM users WHERE user_id = ?", user_id)
        if user and user["active"]:
            g.user = user
        else:
            session.clear()


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def check_csrf():
    if request.method == "POST":
        sent = request.form.get("csrf", "")
        if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
            abort(400, "The form expired. Go back and try again.")


def login_required(*roles):
    """Require a signed-in user, optionally limited to the given roles."""
    def wrap(view):
        @wraps(view)
        def inner(*args, **kwargs):
            if g.user is None:
                flash("Sign in to continue.", "error")
                return redirect(url_for("account.login", next=request.path))
            if roles and g.user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)
        return inner
    return wrap


def is_staff():
    return g.user is not None and g.user["role"] in ("officer", "admin")
