from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from ..auth import login_required
from ..db import get_db, many, one, run
from ..forms import field, int_field
from ..lifecycle import RuleError

bp = Blueprint("admin", __name__)

ROLES = ("citizen", "officer", "admin")


@bp.get("/reports")
@login_required("admin")
def reports():
    start = request.args.get("start", "")
    end = request.args.get("end", "")
    criminal_id = request.args.get("criminal", type=int)

    by_status = many("SELECT * FROM v_cases_by_status ORDER BY total DESC")
    by_station = many("SELECT * FROM v_cases_by_station ORDER BY total DESC, station")

    period = None
    if start and end:
        period = {
            "complaints": one(
                "SELECT COUNT(*) AS n FROM complaint WHERE date_filed BETWEEN ? AND ?", start, end
            )["n"],
            "cases": one(
                'SELECT COUNT(*) AS n FROM "case" WHERE date_opened BETWEEN ? AND ?', start, end
            )["n"],
            "closed": one(
                "SELECT COUNT(DISTINCT entity_id) AS n FROM status_log"
                " WHERE entity = 'case' AND new_status LIKE 'Closed%' AND date(changed_at) BETWEEN ? AND ?",
                start, end,
            )["n"],
        }

    history = None
    criminals = many("SELECT criminal_id, name FROM criminal ORDER BY name")
    if criminal_id:
        history = {
            "criminal": one("SELECT * FROM criminal WHERE criminal_id = ?", criminal_id),
            "cases": many(
                'SELECT cs.case_id, cs.status, cs.date_opened, c.title, cc.role FROM case_criminal cc'
                ' JOIN "case" cs ON cs.case_id = cc.case_id JOIN complaint c ON c.complaint_id = cs.complaint_id'
                " WHERE cc.criminal_id = ? ORDER BY cs.date_opened",
                criminal_id,
            ),
        }
    return render_template(
        "reports.html", title="Reports", by_status=by_status, by_station=by_station,
        start=start, end=end, period=period, criminals=criminals, history=history,
    )


@bp.get("/users")
@login_required("admin")
def users():
    rows = many(
        "SELECT u.*, o.badge_no, o.rank, ps.name AS station FROM users u"
        " LEFT JOIN officer o ON o.user_id = u.user_id"
        " LEFT JOIN police_station ps ON ps.station_id = o.station_id ORDER BY u.role, u.name"
    )
    stations = many("SELECT * FROM police_station ORDER BY name")
    return render_template("users.html", title="Users", rows=rows, stations=stations, roles=ROLES)


def _ensure_role_row(user_id, role):
    """Create the role-specific row when an account is given a role for the first time."""
    if role == "citizen":
        run("INSERT OR IGNORE INTO citizen (user_id) VALUES (?)", user_id)
    elif role == "admin":
        run("INSERT OR IGNORE INTO admin (user_id) VALUES (?)", user_id)
    elif role == "officer":
        if one("SELECT 1 FROM officer WHERE user_id = ?", user_id):
            return
        badge = field("badge_no", "Badge number", 40)
        rank = field("rank", "Rank", 60)
        station_id = int_field("station_id")
        if not station_id or not one("SELECT 1 FROM police_station WHERE station_id = ?", station_id):
            raise RuleError("Pick a station for the officer.")
        if one("SELECT 1 FROM officer WHERE badge_no = ?", badge):
            raise RuleError("That badge number is already in use.")
        run("INSERT INTO officer (user_id, badge_no, rank, station_id) VALUES (?, ?, ?, ?)", user_id, badge, rank, station_id)


@bp.post("/users")
@login_required("admin")
def create_user():
    role = request.form.get("role")
    if role not in ROLES:
        raise RuleError("Pick a role.")
    email = field("email", "Email", 200).lower()
    password = field("password", "Password", 200)
    if len(password) < 8:
        raise RuleError("Use at least 8 characters for the password.")
    if one("SELECT 1 FROM users WHERE email = ?", email):
        raise RuleError("An account with that email already exists.")
    user_id = run(
        "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
        field("name", "Name", 100), email, generate_password_hash(password), role,
    )
    _ensure_role_row(user_id, role)
    get_db().commit()
    flash("Account created.", "ok")
    return redirect(url_for("admin.users"))


@bp.post("/users/<int:user_id>/role")
@login_required("admin")
def change_role(user_id):
    role = request.form.get("role")
    if role not in ROLES:
        raise RuleError("Pick a role.")
    if user_id == g.user["user_id"]:
        raise RuleError("You cannot change your own role.")
    if role == "officer" and not one("SELECT 1 FROM officer WHERE user_id = ?", user_id):
        raise RuleError("Create the account as an officer so a badge, rank and station are recorded.")
    _ensure_role_row(user_id, role)
    run("UPDATE users SET role = ? WHERE user_id = ?", role, user_id)
    get_db().commit()
    flash("Role updated.", "ok")
    return redirect(url_for("admin.users"))


@bp.post("/users/<int:user_id>/active")
@login_required("admin")
def toggle_active(user_id):
    if user_id == g.user["user_id"]:
        raise RuleError("You cannot deactivate your own account.")
    run("UPDATE users SET active = 1 - active WHERE user_id = ?", user_id)
    get_db().commit()
    flash("Account updated.", "ok")
    return redirect(url_for("admin.users"))
