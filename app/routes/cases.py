from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..auth import login_required
from ..db import get_db, many, one, run
from ..forms import as_dict, as_dicts, need, page_number
from ..lifecycle import (
    CASE_STATUSES, CASE_TRANSITIONS, RuleError, assign_officer, change_case_status, is_closed,
)
from ..mongo import clean, mdb, now
from .attachments import list_for

router = APIRouter(prefix="/api")

PAGE_SIZE = 20

CASE_SELECT = (
    'SELECT cs.*, c.title, c.location, c.description, c.incident_date, c.complaint_id,'
    " cu.name AS citizen_name, ps.name AS station, ou.name AS officer_name"
    ' FROM crime_case cs JOIN complaint c ON c.complaint_id = cs.complaint_id'
    " JOIN citizen ct ON ct.citizen_id = c.citizen_id JOIN users cu ON cu.user_id = ct.user_id"
    " JOIN police_station ps ON ps.station_id = cs.station_id"
    " LEFT JOIN officer o ON o.officer_id = cs.officer_id LEFT JOIN users ou ON ou.user_id = o.user_id"
)


class Status(BaseModel):
    status: str = ""


class Assign(BaseModel):
    officer_id: int | None = None


class Evidence(BaseModel):
    type: str = ""
    description: str = ""


class Link(BaseModel):
    criminal_id: int | None = None
    role: str = ""


class ReportBody(BaseModel):
    content: str = ""


def my_officer_id(user):
    row = one("SELECT officer_id FROM officer WHERE user_id = ?", user["user_id"])
    return row["officer_id"] if row else None


def can_edit(case, user):
    if is_closed(case["status"]):
        return False
    return user["role"] == "admin" or (
        case["officer_id"] is not None and case["officer_id"] == my_officer_id(user)
    )


def load_case(case_id):
    case = one(CASE_SELECT + " WHERE cs.case_id = ?", case_id)
    if case is None:
        raise HTTPException(404, "That case does not exist.")
    return case


def require_edit(case_id, user):
    case = load_case(case_id)
    if not can_edit(case, user):
        raise RuleError("Only the assigned officer or an admin can change an open case.")
    return case


@router.get("/dashboard")
def dashboard(user=login_required("officer", "admin")):
    mine = my_officer_id(user)
    open_states = "('Under Investigation', 'Chargesheet Filed')"
    counts = {
        "awaiting": one("SELECT COUNT(*) AS n FROM complaint WHERE status = 'Filed'")["n"],
        "open": one(f'SELECT COUNT(*) AS n FROM crime_case WHERE status IN {open_states}')["n"],
        "mine": one(
            f'SELECT COUNT(*) AS n FROM crime_case WHERE officer_id = ? AND status IN {open_states}', mine
        )["n"] if mine else 0,
        "closed": one("SELECT COUNT(*) AS n FROM crime_case WHERE status LIKE 'Closed%'")["n"],
    }
    queue = many(
        "SELECT c.*, u.name AS citizen_name FROM complaint c"
        " JOIN citizen ct ON ct.citizen_id = c.citizen_id JOIN users u ON u.user_id = ct.user_id"
        " WHERE c.status = 'Filed' ORDER BY c.complaint_id LIMIT 8"
    )
    unassigned = many(
        CASE_SELECT + " WHERE cs.officer_id IS NULL AND cs.status NOT LIKE 'Closed%' ORDER BY cs.case_id LIMIT 8"
    )
    mine_rows = many(
        CASE_SELECT + " WHERE cs.officer_id = ? AND cs.status NOT LIKE 'Closed%' ORDER BY cs.case_id DESC LIMIT 8",
        mine,
    ) if mine else []
    return {
        "counts": counts, "queue": as_dicts(queue), "unassigned": as_dicts(unassigned),
        "mine_rows": as_dicts(mine_rows),
    }


@router.get("/cases")
def index(
    status: str = "", q: str = "", mine: str = "", page: str = "1",
    user=login_required("officer", "admin"),
):
    q = q.strip()
    page = page_number(page)
    where, args = [], []
    if status in CASE_STATUSES:
        where.append("cs.status = ?")
        args.append(status)
    if mine == "1":
        where.append("cs.officer_id = ?")
        args.append(my_officer_id(user))
    if q:
        where.append("(c.title LIKE ? OR cu.name LIKE ? OR c.location LIKE ?)")
        args += [f"%{q}%"] * 3
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    total = one(
        'SELECT COUNT(*) AS n FROM crime_case cs JOIN complaint c ON c.complaint_id = cs.complaint_id'
        " JOIN citizen ct ON ct.citizen_id = c.citizen_id JOIN users cu ON cu.user_id = ct.user_id " + clause,
        *args,
    )["n"]
    rows = many(
        CASE_SELECT + f" {clause} ORDER BY cs.case_id DESC LIMIT ? OFFSET ?",
        *args, PAGE_SIZE, (page - 1) * PAGE_SIZE,
    )
    return {
        "items": as_dicts(rows), "statuses": CASE_STATUSES, "page": page, "total": total,
        "pages": max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1),
    }


@router.get("/cases/{case_id}")
def detail(case_id: int, user=login_required("officer", "admin")):
    case = load_case(case_id)
    evidence = clean(mdb().evidence.find({"case_id": case_id}).sort("evidence_no", 1))
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
    notes = clean(mdb().notes.find({"complaint_id": case["complaint_id"]}).sort("_id", 1))
    history = clean(mdb().status_log.find({"entity": "case", "entity_id": case_id}).sort("_id", 1))
    attachments = list_for(case["complaint_id"])
    officers = many(
        "SELECT o.officer_id, u.name, o.officer_rank FROM officer o JOIN users u ON u.user_id = o.user_id"
        " WHERE u.active = 1 ORDER BY u.name"
    ) if user["role"] == "admin" else []
    return {
        "case": dict(case), "evidence": evidence, "linked": as_dicts(linked),
        "available": as_dicts(available), "reports": as_dicts(reports), "notes": notes,
        "history": history, "attachments": attachments, "officers": as_dicts(officers),
        "editable": can_edit(case, user), "next_states": CASE_TRANSITIONS[case["status"]],
    }


@router.post("/cases/{case_id}/status")
def status(case_id: int, body: Status, user=login_required("officer", "admin")):
    require_edit(case_id, user)
    change_case_status(case_id, body.status, user["user_id"])
    return {"ok": True}


@router.post("/cases/{case_id}/assign")
def assign(case_id: int, body: Assign, user=login_required("admin")):
    return {"officer": assign_officer(case_id, body.officer_id, user["user_id"])}


@router.post("/cases/{case_id}/evidence")
def add_evidence(case_id: int, body: Evidence, user=login_required("officer", "admin")):
    require_edit(case_id, user)
    kind = need(body.type, "Evidence type", 60)
    description = need(body.description, "Description", 1000)
    last = mdb().evidence.find_one({"case_id": case_id}, sort=[("evidence_no", -1)])
    next_no = (last["evidence_no"] if last else 0) + 1
    mdb().evidence.insert_one({
        "case_id": case_id, "evidence_no": next_no, "type": kind,
        "description": description, "date_collected": now()[:10],
    })
    return {"evidence_no": next_no}


@router.post("/cases/{case_id}/criminals")
def link_criminal(case_id: int, body: Link, user=login_required("officer", "admin")):
    require_edit(case_id, user)
    if not body.criminal_id or not one("SELECT 1 FROM criminal WHERE criminal_id = ?", body.criminal_id):
        raise RuleError("Pick a criminal record.")
    if body.role not in ("suspect", "accused", "witness", "victim"):
        raise RuleError("Pick a role.")
    # relinking someone changes their role, so replace any earlier link
    run("DELETE FROM case_criminal WHERE case_id = ? AND criminal_id = ?", case_id, body.criminal_id)
    run(
        "INSERT INTO case_criminal (case_id, criminal_id, role) VALUES (?, ?, ?)",
        case_id, body.criminal_id, body.role,
    )
    get_db().commit()
    return {"ok": True}


@router.delete("/cases/{case_id}/criminals/{criminal_id}")
def unlink_criminal(case_id: int, criminal_id: int, user=login_required("officer", "admin")):
    require_edit(case_id, user)
    run("DELETE FROM case_criminal WHERE case_id = ? AND criminal_id = ?", case_id, criminal_id)
    get_db().commit()
    return {"ok": True}


@router.post("/cases/{case_id}/reports")
def add_report(case_id: int, body: ReportBody, user=login_required("officer", "admin")):
    require_edit(case_id, user)
    run(
        "INSERT INTO report (case_id, officer_id, content) VALUES (?, ?, ?)",
        case_id, my_officer_id(user), need(body.content, "Report", 6000),
    )
    get_db().commit()
    return {"ok": True}
