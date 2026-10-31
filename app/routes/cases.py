from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from ..auth import login_required
from ..db import get_db, many, one, run
from ..forms import field, int_field
from ..lifecycle import (
    CASE_STATUSES, CASE_TRANSITIONS, RuleError, assign_officer, change_case_status, is_closed,
)

bp = Blueprint("cases", __name__)

PAGE_SIZE = 20

CASE_SELECT = (
    'SELECT cs.*, c.title, c.location, c.description, c.incident_date, c.complaint_id,'
    " cu.name AS citizen_name, ps.name AS station, ou.name AS officer_name"
    ' FROM "case" cs JOIN complaint c ON c.complaint_id = cs.complaint_id'
    " JOIN citizen ct ON ct.citizen_id = c.citizen_id JOIN users cu ON cu.user_id = ct.user_id"
    " JOIN police_station ps ON ps.station_id = cs.station_id"
    " LEFT JOIN officer o ON o.officer_id = cs.officer_id LEFT JOIN users ou ON ou.user_id = o.user_id"
)


def my_officer_id():
    row = one("SELECT officer_id FROM officer WHERE user_id = ?", g.user["user_id"])
    return row["officer_id"] if row else None


def can_edit(case):
    if is_closed(case["status"]):
        return False
    return g.user["role"] == "admin" or (case["officer_id"] is not None and case["officer_id"] == my_officer_id())


def load_case(case_id):
    case = one(CASE_SELECT + " WHERE cs.case_id = ?", case_id)
    if case is None:
        abort(404)
    return case


def require_edit(case_id):
    case = load_case(case_id)
    if not can_edit(case):
        raise RuleError("Only the assigned officer or an admin can change an open case.")
    return case


@bp.get("/dashboard")
@login_required("officer", "admin")
def dashboard():
    mine = my_officer_id()
    counts = {
        "awaiting": one("SELECT COUNT(*) AS n FROM complaint WHERE status = 'Filed'")["n"],
        "open": one('SELECT COUNT(*) AS n FROM "case" WHERE status IN (\'Under Investigation\', \'Chargesheet Filed\')')["n"],
        "mine": one(
            "SELECT COUNT(*) AS n FROM \"case\" WHERE officer_id = ? AND status IN ('Under Investigation', 'Chargesheet Filed')",
            mine,
        )["n"] if mine else 0,
        "closed": one('SELECT COUNT(*) AS n FROM "case" WHERE status LIKE \'Closed%\'')["n"],
    }
    queue = many(
        "SELECT c.*, u.name AS citizen_name FROM complaint c"
        " JOIN citizen ct ON ct.citizen_id = c.citizen_id JOIN users u ON u.user_id = ct.user_id"
        " WHERE c.status = 'Filed' ORDER BY c.complaint_id LIMIT 8"
    )
    unassigned = many(CASE_SELECT + " WHERE cs.officer_id IS NULL AND cs.status NOT LIKE 'Closed%' ORDER BY cs.case_id LIMIT 8")
    mine_rows = many(
        CASE_SELECT + " WHERE cs.officer_id = ? AND cs.status NOT LIKE 'Closed%' ORDER BY cs.case_id DESC LIMIT 8",
        mine,
    ) if mine else []
    return render_template(
        "dashboard.html", title="Dashboard", counts=counts, queue=queue,
        unassigned=unassigned, mine_rows=mine_rows,
    )


@bp.get("/cases")
@login_required("officer", "admin")
def index():
    status = request.args.get("status", "")
    q = request.args.get("q", "").strip()
    only_mine = request.args.get("mine") == "1"
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page = 1

    where, args = [], []
    if status in CASE_STATUSES:
        where.append("cs.status = ?")
        args.append(status)
    if only_mine:
        where.append("cs.officer_id = ?")
        args.append(my_officer_id())
    if q:
        where.append("(c.title LIKE ? OR cu.name LIKE ? OR c.location LIKE ?)")
        args += [f"%{q}%"] * 3
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    total = one(
        'SELECT COUNT(*) AS n FROM "case" cs JOIN complaint c ON c.complaint_id = cs.complaint_id'
        " JOIN citizen ct ON ct.citizen_id = c.citizen_id JOIN users cu ON cu.user_id = ct.user_id " + clause,
        *args,
    )["n"]
    rows = many(
        CASE_SELECT + f" {clause} ORDER BY cs.case_id DESC LIMIT ? OFFSET ?",
        *args, PAGE_SIZE, (page - 1) * PAGE_SIZE,
    )
    return render_template(
        "cases.html", title="Cases", rows=rows, status=status, q=q, mine=only_mine,
        statuses=CASE_STATUSES, page=page, pages=max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1), total=total,
    )


@bp.get("/cases/<int:case_id>")
@login_required("officer", "admin")
def detail(case_id):
    case = load_case(case_id)
    evidence = many("SELECT * FROM evidence WHERE case_id = ? ORDER BY evidence_no", case_id)
    linked = many(
        "SELECT cc.role, cr.* FROM case_criminal cc JOIN criminal cr ON cr.criminal_id = cc.criminal_id"
        " WHERE cc.case_id = ? ORDER BY cr.name",
        case_id,
    )
    available = many(
        "SELECT criminal_id, name FROM criminal WHERE criminal_id NOT IN"
        " (SELECT criminal_id FROM case_criminal WHERE case_id = ?) ORDER BY name",
        case_id,
    )
    reports = many(
        "SELECT r.*, u.name AS author FROM report r LEFT JOIN officer o ON o.officer_id = r.officer_id"
        " LEFT JOIN users u ON u.user_id = o.user_id WHERE r.case_id = ? ORDER BY r.report_id DESC",
        case_id,
    )
    notes = many("SELECT * FROM complaint_note WHERE complaint_id = ? ORDER BY note_id", case["complaint_id"])
    history = many(
        "SELECT l.*, u.name AS who FROM status_log l LEFT JOIN users u ON u.user_id = l.user_id"
        " WHERE l.entity = 'case' AND l.entity_id = ? ORDER BY l.log_id",
        case_id,
    )
    officers = many(
        "SELECT o.officer_id, u.name, o.rank FROM officer o JOIN users u ON u.user_id = o.user_id"
        " WHERE u.active = 1 ORDER BY u.name"
    ) if g.user["role"] == "admin" else []
    return render_template(
        "case.html", title=f"Case {case_id}", case=case, evidence=evidence, linked=linked,
        available=available, reports=reports, notes=notes, history=history, officers=officers,
        editable=can_edit(case), next_states=CASE_TRANSITIONS[case["status"]],
    )


@bp.post("/cases/<int:case_id>/status")
@login_required("officer", "admin")
def status(case_id):
    require_edit(case_id)
    change_case_status(case_id, request.form.get("status", ""), g.user["user_id"])
    flash("Case status updated.", "ok")
    return redirect(url_for("cases.detail", case_id=case_id))


@bp.post("/cases/<int:case_id>/assign")
@login_required("admin")
def assign(case_id):
    name = assign_officer(case_id, int_field("officer_id"), g.user["user_id"])
    flash(f"Assigned to {name}.", "ok")
    return redirect(url_for("cases.detail", case_id=case_id))


@bp.post("/cases/<int:case_id>/evidence")
@login_required("officer", "admin")
def add_evidence(case_id):
    require_edit(case_id)
    kind = field("type", "Evidence type", 60)
    description = field("description", "Description", 1000)
    next_no = one("SELECT COALESCE(MAX(evidence_no), 0) + 1 AS n FROM evidence WHERE case_id = ?", case_id)["n"]
    run(
        "INSERT INTO evidence (case_id, evidence_no, type, description) VALUES (?, ?, ?, ?)",
        case_id, next_no, kind, description,
    )
    get_db().commit()
    flash(f"Evidence {next_no} recorded.", "ok")
    return redirect(url_for("cases.detail", case_id=case_id))


@bp.post("/cases/<int:case_id>/criminals")
@login_required("officer", "admin")
def link_criminal(case_id):
    require_edit(case_id)
    criminal_id = int_field("criminal_id")
    if not criminal_id or not one("SELECT 1 FROM criminal WHERE criminal_id = ?", criminal_id):
        raise RuleError("Pick a criminal record.")
    role = request.form.get("role")
    if role not in ("suspect", "accused", "witness", "victim"):
        raise RuleError("Pick a role.")
    run(
        "INSERT OR REPLACE INTO case_criminal (case_id, criminal_id, role) VALUES (?, ?, ?)",
        case_id, criminal_id, role,
    )
    get_db().commit()
    flash("Linked to the case.", "ok")
    return redirect(url_for("cases.detail", case_id=case_id))


@bp.post("/cases/<int:case_id>/criminals/<int:criminal_id>/unlink")
@login_required("officer", "admin")
def unlink_criminal(case_id, criminal_id):
    require_edit(case_id)
    run("DELETE FROM case_criminal WHERE case_id = ? AND criminal_id = ?", case_id, criminal_id)
    get_db().commit()
    flash("Removed from the case.", "ok")
    return redirect(url_for("cases.detail", case_id=case_id))


@bp.post("/cases/<int:case_id>/reports")
@login_required("officer", "admin")
def add_report(case_id):
    require_edit(case_id)
    run(
        "INSERT INTO report (case_id, officer_id, content) VALUES (?, ?, ?)",
        case_id, my_officer_id(), field("content", "Report", 6000),
    )
    get_db().commit()
    flash("Report saved.", "ok")
    return redirect(url_for("cases.detail", case_id=case_id))
