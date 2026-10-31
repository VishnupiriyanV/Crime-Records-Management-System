from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from ..auth import is_staff, login_required
from ..db import get_db, many, one, run
from ..forms import field, int_field
from ..lifecycle import (
    RuleError, is_closed, register_case, reject_complaint, verify_complaint,
)

bp = Blueprint("complaints", __name__)

PAGE_SIZE = 20


def _citizen_id():
    row = one("SELECT citizen_id FROM citizen WHERE user_id = ?", g.user["user_id"])
    return row["citizen_id"]


def _load(complaint_id):
    """Fetch a complaint the current user is allowed to see."""
    c = one(
        "SELECT c.*, u.name AS citizen_name, u.user_id AS owner_id FROM complaint c"
        " JOIN citizen ct ON ct.citizen_id = c.citizen_id"
        " JOIN users u ON u.user_id = ct.user_id WHERE c.complaint_id = ?",
        complaint_id,
    )
    if c is None:
        abort(404)
    if not is_staff() and c["owner_id"] != g.user["user_id"]:
        abort(404)  # a citizen should not learn that other complaints exist
    return c


@bp.get("/complaints")
@login_required()
def index():
    status = request.args.get("status", "")
    q = request.args.get("q", "").strip()
    page = max(int_field_arg("page") or 1, 1)

    where, args = [], []
    if g.user["role"] == "citizen":
        where.append("c.citizen_id = ?")
        args.append(_citizen_id())
    if status in ("Filed", "Verified", "Rejected"):
        where.append("c.status = ?")
        args.append(status)
    if q:
        where.append("(c.title LIKE ? OR c.location LIKE ?)")
        args += [f"%{q}%", f"%{q}%"]
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    total = one(f"SELECT COUNT(*) AS n FROM complaint c {clause}", *args)["n"]
    rows = many(
        f"SELECT c.*, u.name AS citizen_name, cs.case_id, cs.status AS case_status"
        f" FROM complaint c JOIN citizen ct ON ct.citizen_id = c.citizen_id"
        f" JOIN users u ON u.user_id = ct.user_id"
        f" LEFT JOIN \"case\" cs ON cs.complaint_id = c.complaint_id {clause}"
        f" ORDER BY c.complaint_id DESC LIMIT ? OFFSET ?",
        *args, PAGE_SIZE, (page - 1) * PAGE_SIZE,
    )
    return render_template(
        "complaints.html", title="Complaints", rows=rows, status=status, q=q,
        page=page, pages=max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1), total=total,
    )


def int_field_arg(name):
    try:
        return int(request.args.get(name, ""))
    except ValueError:
        return None


@bp.route("/complaints/new", methods=["GET", "POST"])
@login_required("citizen")
def new():
    if request.method == "POST":
        try:
            values = (
                field("title", "Title", 120),
                field("description", "Description", 4000),
                field("location", "Location", 200),
                field("incident_date", "Incident date", 10),
            )
        except RuleError as err:
            flash(str(err), "error")
            return render_template("complaint_new.html", title="File a complaint", form=request.form), 400
        complaint_id = run(
            "INSERT INTO complaint (citizen_id, title, description, location, incident_date)"
            " VALUES (?, ?, ?, ?, ?)",
            _citizen_id(), *values,
        )
        run(
            "INSERT INTO status_log (entity, entity_id, old_status, new_status, user_id)"
            " VALUES ('complaint', ?, NULL, 'Filed', ?)",
            complaint_id, g.user["user_id"],
        )
        get_db().commit()
        flash("Complaint filed. You will be notified when it is reviewed.", "ok")
        return redirect(url_for("complaints.detail", complaint_id=complaint_id))
    return render_template("complaint_new.html", title="File a complaint", form={})


@bp.get("/complaints/<int:complaint_id>")
@login_required()
def detail(complaint_id):
    c = _load(complaint_id)
    case = one(
        'SELECT cs.*, ps.name AS station, u.name AS officer_name FROM "case" cs'
        " JOIN police_station ps ON ps.station_id = cs.station_id"
        " LEFT JOIN officer o ON o.officer_id = cs.officer_id"
        " LEFT JOIN users u ON u.user_id = o.user_id WHERE cs.complaint_id = ?",
        complaint_id,
    )
    notes = many("SELECT * FROM complaint_note WHERE complaint_id = ? ORDER BY note_id", complaint_id)
    history = many(
        "SELECT l.*, u.name AS who FROM status_log l LEFT JOIN users u ON u.user_id = l.user_id"
        " WHERE l.entity = 'complaint' AND l.entity_id = ? ORDER BY l.log_id",
        complaint_id,
    )
    stations = many("SELECT * FROM police_station ORDER BY name") if is_staff() else []
    can_add_note = (
        g.user["user_id"] == c["owner_id"]
        and c["status"] != "Rejected"
        and not (case and is_closed(case["status"]))
    )
    return render_template(
        "complaint.html", title=c["title"], c=c, case=case, notes=notes,
        history=history, stations=stations, can_add_note=can_add_note,
    )


@bp.post("/complaints/<int:complaint_id>/notes")
@login_required("citizen")
def add_note(complaint_id):
    c = _load(complaint_id)
    case = one('SELECT status FROM "case" WHERE complaint_id = ?', complaint_id)
    if c["status"] == "Rejected" or (case and is_closed(case["status"])):
        raise RuleError("This complaint is closed to new notes.")
    kind = request.form.get("kind")
    if kind not in ("statement", "evidence"):
        raise RuleError("Pick statement or evidence.")
    run(
        "INSERT INTO complaint_note (complaint_id, kind, body) VALUES (?, ?, ?)",
        complaint_id, kind, field("body", "Note", 4000),
    )
    get_db().commit()
    flash("Added to your complaint.", "ok")
    return redirect(url_for("complaints.detail", complaint_id=complaint_id))


@bp.post("/complaints/<int:complaint_id>/verify")
@login_required("officer", "admin")
def verify(complaint_id):
    verify_complaint(complaint_id, g.user["user_id"])
    flash("Complaint verified.", "ok")
    return redirect(url_for("complaints.detail", complaint_id=complaint_id))


@bp.post("/complaints/<int:complaint_id>/reject")
@login_required("officer", "admin")
def reject(complaint_id):
    reject_complaint(complaint_id, field("reason", "A reason", 500, required=False), g.user["user_id"])
    flash("Complaint rejected.", "ok")
    return redirect(url_for("complaints.detail", complaint_id=complaint_id))


@bp.post("/complaints/<int:complaint_id>/register-case")
@login_required("officer", "admin")
def open_case(complaint_id):
    case_id = register_case(complaint_id, int_field("station_id"), g.user["user_id"])
    flash("Case registered.", "ok")
    return redirect(url_for("cases.detail", case_id=case_id))
