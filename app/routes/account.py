from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..auth import login_required
from ..db import get_db, many, one, run
from ..forms import field
from ..lifecycle import RuleError

bp = Blueprint("account", __name__)


def home_for(user):
    return url_for("complaints.index") if user["role"] == "citizen" else url_for("cases.dashboard")


@bp.get("/")
def index():
    if g.user is None:
        return redirect(url_for("account.login"))
    return redirect(home_for(g.user))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = one("SELECT * FROM users WHERE email = ?", email)
        if user and user["active"] and check_password_hash(user["password"], request.form.get("password", "")):
            session.clear()
            session["user_id"] = user["user_id"]
            target = request.args.get("next", "")
            return redirect(target if target.startswith("/") and not target.startswith("//") else home_for(user))
        flash("Email or password is wrong.", "error")
    return render_template("login.html", title="Sign in")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            name = field("name", "Name", 100)
            email = field("email", "Email", 200).lower()
            password = field("password", "Password", 200)
            if "@" not in email:
                raise RuleError("Enter a valid email address.")
            if len(password) < 8:
                raise RuleError("Use at least 8 characters for the password.")
            if one("SELECT 1 FROM users WHERE email = ?", email):
                raise RuleError("An account with that email already exists.")
        except RuleError as err:
            flash(str(err), "error")
            return render_template("register.html", title="Create account", form=request.form), 400
        user_id = run(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, 'citizen')",
            name, email, generate_password_hash(password),
        )
        run("INSERT INTO citizen (user_id) VALUES (?)", user_id)
        get_db().commit()
        session.clear()
        session["user_id"] = user_id
        flash("Your account is ready.", "ok")
        return redirect(url_for("complaints.index"))
    return render_template("register.html", title="Create account", form={})


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("account.login"))


@bp.route("/profile", methods=["GET", "POST"])
@login_required()
def profile():
    uid = g.user["user_id"]
    if request.method == "POST":
        try:
            name = field("name", "Name", 100)
        except RuleError as err:
            flash(str(err), "error")
            return redirect(url_for("account.profile"))
        run("UPDATE users SET name = ? WHERE user_id = ?", name, uid)
        if g.user["role"] == "citizen":
            run(
                "UPDATE citizen SET address = ?, phone = ? WHERE user_id = ?",
                field("address", "Address", 300, required=False),
                field("phone", "Phone", 40, required=False),
                uid,
            )
        new_password = request.form.get("password", "")
        if new_password:
            if len(new_password) < 8:
                flash("Use at least 8 characters for the password.", "error")
                return redirect(url_for("account.profile"))
            run("UPDATE users SET password = ? WHERE user_id = ?", generate_password_hash(new_password), uid)
        get_db().commit()
        flash("Profile saved.", "ok")
        return redirect(url_for("account.profile"))
    extra = one("SELECT address, phone FROM citizen WHERE user_id = ?", uid) if g.user["role"] == "citizen" else None
    return render_template("profile.html", title="Profile", extra=extra)


@bp.get("/notifications")
@login_required()
def notifications():
    uid = g.user["user_id"]
    items = many("SELECT * FROM notification WHERE user_id = ? ORDER BY notification_id DESC LIMIT 100", uid)
    run("UPDATE notification SET seen = 1 WHERE user_id = ?", uid)
    get_db().commit()
    return render_template("notifications.html", title="Notifications", items=items)
