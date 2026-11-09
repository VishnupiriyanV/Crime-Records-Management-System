from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..auth import is_staff, login_required
from ..constants import CATEGORIES, SEVERITIES, parse_fir, with_fir
from ..dictation import read_complaint
from ..db import get_db, many, one, run
from ..forms import as_dict, as_dicts, need, order_by, page_number
from ..lifecycle import RuleError, is_closed, log_status, register_case, reject_complaint, verify_complaint
from ..mongo import clean, mdb, now
from .attachments import list_for

router = APIRouter(prefix="/api")

PAGE_SIZE = 20

SORTS = {
    "no": "c.complaint_id", "title": "c.title", "by": "u.name", "location": "c.location",
    "filed": "c.date_filed", "status": "c.status", "case": "cs.status",
    "category": "c.category", "severity": "c.severity",
}


class NewComplaint(BaseModel):
    title: str = ""
    description: str = ""
    location: str = ""
    incident_date: str = ""
    category: str = "Other"
    latitude: float | None = None
    longitude: float | None = None


class Classify(BaseModel):
    category: str = ""
    severity: str = ""


class Note(BaseModel):
    kind: str = ""
    body: str = ""


class Reject(BaseModel):
    reason: str = ""


class OpenCase(BaseModel):
    station_id: int | None = None


def _citizen_id(user):
    return one("SELECT citizen_id FROM citizen WHERE user_id = ?", user["user_id"])["citizen_id"]


def _load(complaint_id, user):
    """Fetch a complaint the current user is allowed to see."""
    c = one(
        "SELECT c.*, u.name AS citizen_name, u.user_id AS owner_id FROM complaint c"
        " JOIN citizen ct ON ct.citizen_id = c.citizen_id"
        " JOIN users u ON u.user_id = ct.user_id WHERE c.complaint_id = ?",
        complaint_id,
    )
    # a citizen should not learn that other people's complaints exist
    if c is None or (not is_staff(user) and c["owner_id"] != user["user_id"]):
        raise HTTPException(404, "That complaint does not exist.")
    return c


def complaint_filter(user, status, q, category="", severity=""):
    """WHERE clause and arguments shared by the list and the CSV export."""
    where, args = [], []
    if user["role"] == "citizen":
        where.append("c.citizen_id = ?")
        args.append(_citizen_id(user))
    if status in ("Filed", "Verified", "Rejected"):
        where.append("c.status = ?")
        args.append(status)
    if category in CATEGORIES:
        where.append("c.category = ?")
        args.append(category)
    if severity in SEVERITIES:
        where.append("c.severity = ?")
        args.append(severity)
    if q.strip():
        serial = parse_fir(q)
        if serial is not None:
            where.append("c.complaint_id = ?")
            args.append(serial)
        else:
            where.append("(c.title LIKE ? OR c.location LIKE ?)")
            args += [f"%{q.strip()}%", f"%{q.strip()}%"]
    return ("WHERE " + " AND ".join(where)) if where else "", args


LIST_SELECT = (
    "SELECT c.*, u.name AS citizen_name, cs.case_id, cs.status AS case_status"
    " FROM complaint c JOIN citizen ct ON ct.citizen_id = c.citizen_id"
    " JOIN users u ON u.user_id = ct.user_id"
    " LEFT JOIN crime_case cs ON cs.complaint_id = c.complaint_id"
)


@router.get("/complaints")
def index(
    status: str = "", q: str = "", category: str = "", severity: str = "", page: str = "1",
    sort: str = "no", dir: str = "desc", user=login_required(),
):
    page = page_number(page)
    clause, args = complaint_filter(user, status, q, category, severity)
    total = one(f"SELECT COUNT(*) AS n FROM complaint c {clause}", *args)["n"]
    rows = many(
        f"{LIST_SELECT} {clause} ORDER BY {order_by(SORTS, sort, dir, 'no')} LIMIT ? OFFSET ?",
        *args, PAGE_SIZE, (page - 1) * PAGE_SIZE,
    )
    return {
        "items": [with_fir(r) for r in rows], "page": page, "total": total,
        "pages": max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1),
        "categories": CATEGORIES, "severities": SEVERITIES,
    }


class Spoken(BaseModel):
    text: str = ""


@router.post("/complaints/dictation")
def from_speech(body: Spoken, user=login_required()):
    """Suggest the form fields for a spoken account; nothing is saved."""
    return read_complaint(body.text[:4000])


@router.get("/meta")
def meta(user=login_required()):
    """The fixed lists the forms offer."""
    return {"categories": CATEGORIES, "severities": SEVERITIES}


def _coordinate(value, low, high, label):
    if value is None:
        return None
    if not low <= value <= high:
        raise RuleError(f"{label} is outside the valid range.")
    return round(value, 6)


@router.post("/complaints")
def create(body: NewComplaint, user=login_required("citizen")):
    values = (
        need(body.title, "Title", 120),
        need(body.description, "Description", 4000),
        need(body.location, "Location", 200),
        need(body.incident_date, "Incident date", 10),
    )
    if body.category not in CATEGORIES:
        raise RuleError("Pick a crime category.")
    if (body.latitude is None) != (body.longitude is None):
        raise RuleError("Give both a latitude and a longitude, or neither.")
    lat = _coordinate(body.latitude, -90, 90, "Latitude")
    lng = _coordinate(body.longitude, -180, 180, "Longitude")
    citizen_id = _citizen_id(user)
    # a double click sends the same form twice; answer with the complaint that is already there
    last = one(
        "SELECT complaint_id, title, description, location, incident_date, date_filed FROM complaint"
        " WHERE citizen_id = ? ORDER BY complaint_id DESC LIMIT 1", citizen_id,
    )
    if last and str(last["date_filed"]) == date.today().isoformat() and (
        last["title"], last["description"], last["location"], str(last["incident_date"]),
    ) == values:
        return {"complaint_id": last["complaint_id"]}
    complaint_id = run(
        "INSERT INTO complaint (citizen_id, title, description, location, incident_date, category, latitude, longitude)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        citizen_id, *values, body.category, lat, lng,
    )
    get_db().commit()
    log_status("complaint", complaint_id, None, "Filed", user["user_id"])
    return {"complaint_id": complaint_id}


@router.get("/complaints/{complaint_id}")
def detail(complaint_id: int, user=login_required()):
    c = _load(complaint_id, user)
    case = one(
        'SELECT cs.*, ps.name AS station, u.name AS officer_name FROM crime_case cs'
        " JOIN police_station ps ON ps.station_id = cs.station_id"
        " LEFT JOIN officer o ON o.officer_id = cs.officer_id"
        " LEFT JOIN users u ON u.user_id = o.user_id WHERE cs.complaint_id = ?",
        complaint_id,
    )
    notes = clean(mdb().notes.find({"complaint_id": complaint_id}).sort("_id", 1))
    history = clean(mdb().status_log.find({"entity": "complaint", "entity_id": complaint_id}).sort("_id", 1))
    stations = many("SELECT * FROM police_station ORDER BY name") if is_staff(user) else []
    can_add_note = (
        user["user_id"] == c["owner_id"]
        and c["status"] != "Rejected"
        and not (case and is_closed(case["status"]))
    )
    return {
        "complaint": with_fir(c), "case": as_dict(case), "notes": notes,
        "history": history, "attachments": list_for(complaint_id), "stations": as_dicts(stations), "can_add_note": can_add_note,
        "categories": CATEGORIES, "severities": SEVERITIES,
    }


@router.post("/complaints/{complaint_id}/classify")
def classify(complaint_id: int, body: Classify, user=login_required("officer", "admin")):
    c = _load(complaint_id, user)
    if body.category not in CATEGORIES:
        raise RuleError("Pick a crime category.")
    if body.severity not in SEVERITIES:
        raise RuleError("Pick a severity.")
    run("UPDATE complaint SET category = ?, severity = ? WHERE complaint_id = ?", body.category, body.severity, complaint_id)
    get_db().commit()
    before, after = f"{c['category']}, {c['severity']}", f"{body.category}, {body.severity}"
    if before != after:
        log_status("complaint classification", complaint_id, before, after, user["user_id"])
    return {"ok": True}


@router.post("/complaints/{complaint_id}/notes")
def add_note(complaint_id: int, body: Note, user=login_required("citizen")):
    c = _load(complaint_id, user)
    case = one('SELECT status FROM crime_case WHERE complaint_id = ?', complaint_id)
    if c["status"] == "Rejected" or (case and is_closed(case["status"])):
        raise RuleError("This complaint is closed to new notes.")
    if body.kind not in ("statement", "evidence"):
        raise RuleError("Pick statement or evidence.")
    mdb().notes.insert_one({
        "complaint_id": complaint_id, "kind": body.kind,
        "body": need(body.body, "Note", 4000), "created_at": now(),
    })
    return {"ok": True}


@router.post("/complaints/{complaint_id}/verify")
def verify(complaint_id: int, user=login_required("officer", "admin")):
    verify_complaint(complaint_id, user["user_id"])
    return {"ok": True}


@router.post("/complaints/{complaint_id}/reject")
def reject(complaint_id: int, body: Reject, user=login_required("officer", "admin")):
    reject_complaint(complaint_id, need(body.reason, "A reason", 500, required=False), user["user_id"])
    return {"ok": True}


@router.post("/complaints/{complaint_id}/register-case")
def open_case(complaint_id: int, body: OpenCase, user=login_required("officer", "admin")):
    return {"case_id": register_case(complaint_id, body.station_id, user["user_id"])}
