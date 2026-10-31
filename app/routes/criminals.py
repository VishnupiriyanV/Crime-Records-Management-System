from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from ..auth import login_required
from ..db import get_db, many, one, run
from ..forms import field
from ..lifecycle import RuleError

bp = Blueprint("criminals", __name__)

PAGE_SIZE = 20


def _age():
    raw = request.form.get("age", "").strip()
    if not raw:
        return None
    if not raw.isdigit() or not 0 <= int(raw) <= 120:
        raise RuleError("Age must be a number between 0 and 120.")
    return int(raw)


@bp.get("/criminals")
@login_required("officer", "admin")
def index():
    q = request.args.get("q", "").strip()
    wanted = request.args.get("wanted") == "1"
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page = 1
    where, args = [], []
    if q:
        where.append("(name LIKE ? OR crime_history LIKE ?)")
        args += [f"%{q}%", f"%{q}%"]
    if wanted:
        where.append("wanted = 1")
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    total = one(f"SELECT COUNT(*) AS n FROM criminal {clause}", *args)["n"]
    rows = many(
        f"SELECT cr.*, (SELECT COUNT(*) FROM case_criminal cc WHERE cc.criminal_id = cr.criminal_id) AS cases"
        f" FROM criminal cr {clause} ORDER BY name LIMIT ? OFFSET ?",
        *args, PAGE_SIZE, (page - 1) * PAGE_SIZE,
    )
    return render_template(
        "criminals.html", title="Criminal records", rows=rows, q=q, wanted=wanted,
        page=page, pages=max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1), total=total,
    )


@bp.route("/criminals/new", methods=["GET", "POST"])
@login_required("officer", "admin")
def new():
    if request.method == "POST":
        try:
            criminal_id = run(
                "INSERT INTO criminal (name, age, crime_history, wanted) VALUES (?, ?, ?, ?)",
                field("name", "Name", 120), _age(),
                field("crime_history", "Crime history", 2000, required=False),
                1 if request.form.get("wanted") else 0,
            )
        except RuleError as err:
            flash(str(err), "error")
            return render_template("criminal_form.html", title="Add criminal record", c=request.form, is_new=True), 400
        get_db().commit()
        flash("Record added.", "ok")
        return redirect(url_for("criminals.detail", criminal_id=criminal_id))
    return render_template("criminal_form.html", title="Add criminal record", c={}, is_new=True)


@bp.route("/criminals/<int:criminal_id>", methods=["GET", "POST"])
@login_required("officer", "admin")
def detail(criminal_id):
    c = one("SELECT * FROM criminal WHERE criminal_id = ?", criminal_id)
    if c is None:
        abort(404)
    if request.method == "POST":
        try:
            run(
                "UPDATE criminal SET name = ?, age = ?, crime_history = ?, wanted = ? WHERE criminal_id = ?",
                field("name", "Name", 120), _age(),
                field("crime_history", "Crime history", 2000, required=False),
                1 if request.form.get("wanted") else 0, criminal_id,
            )
        except RuleError as err:
            flash(str(err), "error")
            return redirect(url_for("criminals.detail", criminal_id=criminal_id))
        get_db().commit()
        flash("Record updated.", "ok")
        return redirect(url_for("criminals.detail", criminal_id=criminal_id))
    cases = many(
        'SELECT cs.case_id, cs.status, cs.date_opened, c.title, cc.role FROM case_criminal cc'
        ' JOIN "case" cs ON cs.case_id = cc.case_id JOIN complaint c ON c.complaint_id = cs.complaint_id'
        " WHERE cc.criminal_id = ? ORDER BY cs.case_id DESC",
        criminal_id,
    )
    return render_template("criminal_form.html", title=c["name"], c=c, cases=cases, is_new=False)


@bp.get("/records")
@login_required()
def public_records():
    """What a citizen may search: wanted persons and station contacts, nothing from case files."""
    q = request.args.get("q", "").strip()
    wanted = many(
        "SELECT name, age FROM criminal WHERE wanted = 1 AND name LIKE ? ORDER BY name LIMIT 50",
        f"%{q}%",
    )
    stations = many(
        "SELECT * FROM police_station WHERE name LIKE ? OR jurisdiction LIKE ? ORDER BY name",
        f"%{q}%", f"%{q}%",
    )
    return render_template("records.html", title="Public records", q=q, wanted=wanted, stations=stations)
