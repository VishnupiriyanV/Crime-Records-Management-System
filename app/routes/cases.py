from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from ..auth import login_required
from ..constants import CATEGORIES, CHARGEABLE, CUSTODY_ACTIONS, PERSON_ROLES, SEVERITIES, with_fir
from ..db import get_db, many, one, run
from ..forms import as_dict, as_dicts, need, need_date, order_by, page_number
from ..lifecycle import (
    CASE_STATUSES, CASE_TRANSITIONS, RuleError, assign_officer, change_case_status, file_chargesheet, is_closed, notify,
)
from ..mongo import clean, mdb, now
from ..overdue import case_flags
from .. import ledger
from ..stats import monthly_complaints
from ..timeline import case_timeline, events_for
from .attachments import list_for, save_upload

router = APIRouter(prefix="/api")

PAGE_SIZE = 20

SORTS = {
    "no": "cs.case_id", "title": "c.title", "station": "ps.name", "officer": "ou.name",
    "opened": "cs.date_opened", "status": "cs.status",
}

CASE_SELECT = (
    'SELECT cs.*, c.title, c.location, c.description, c.incident_date, c.complaint_id, c.date_filed,'
    " c.category, c.severity, c.latitude, c.longitude,"
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


class StatementBody(BaseModel):
    kind: str = ""
    person: str = ""
    body: str = ""


class ArrestBody(BaseModel):
    criminal_id: int | None = None
    arrested_on: str = ""
    place: str = ""
    charges: str = ""


class ChargesheetBody(BaseModel):
    sections: str = ""
    summary: str = ""


class CourtDateBody(BaseModel):
    date: str = ""
    court: str = ""
    purpose: str = ""


class OutcomeBody(BaseModel):
    outcome: str = ""


class CustodyBody(BaseModel):
    action: str = ""
    where: str = ""
    note: str = ""


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


def upcoming_hearings(limit=6):
    """The next court dates on cases that are still open."""
    today = now()[:10]
    found = clean(mdb().court_dates.find({"date": {"$gte": today}, "outcome": ""}).sort("date", 1).limit(60))
    if not found:
        return []
    ids = sorted({item["case_id"] for item in found})
    # one query for all of them; asking per hearing costs a round trip each on a hosted database
    rows = many(
        "SELECT cs.case_id, cs.status, c.title FROM crime_case cs JOIN complaint c ON c.complaint_id = cs.complaint_id"
        f" WHERE cs.case_id IN ({', '.join('?' * len(ids))})",
        *ids,
    )
    cases = {row["case_id"]: row for row in rows}
    hearings = []
    for item in found:
        case = cases.get(item["case_id"])
        if case and not is_closed(case["status"]):
            hearings.append({**item, "title": case["title"]})
        if len(hearings) == limit:
            break
    return hearings


@router.get("/dashboard")
def dashboard(user=login_required("officer", "admin")):
    mine = my_officer_id(user)
    open_states = "('Under Investigation', 'Chargesheet Filed')"
    row = one(
        "SELECT"
        " (SELECT COUNT(*) FROM complaint WHERE status = 'Filed') AS awaiting,"
        f" SUM(CASE WHEN status IN {open_states} THEN 1 ELSE 0 END) AS open_cases,"
        f" SUM(CASE WHEN officer_id = ? AND status IN {open_states} THEN 1 ELSE 0 END) AS mine,"
        " SUM(CASE WHEN status LIKE 'Closed%' THEN 1 ELSE 0 END) AS closed"
        " FROM crime_case",
        mine or 0,
    )
    counts = {
        "awaiting": int(row["awaiting"] or 0), "open": int(row["open_cases"] or 0),
        "mine": int(row["mine"] or 0) if mine else 0, "closed": int(row["closed"] or 0),
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
        "by_status": as_dicts(many("SELECT * FROM v_cases_by_status ORDER BY total DESC")),
        "by_category": as_dicts(many(
            "SELECT category, COUNT(*) AS total FROM complaint GROUP BY category ORDER BY total DESC, category"
        )),
        "monthly": monthly_complaints(),
        "hearings": upcoming_hearings(),
    }


def case_filter(status, q, mine, user, category=""):
    """WHERE clause and arguments shared by the list and the CSV export."""
    where, args = [], []
    if status in CASE_STATUSES:
        where.append("cs.status = ?")
        args.append(status)
    if mine == "1":
        where.append("cs.officer_id = ?")
        args.append(my_officer_id(user))
    if category in CATEGORIES:
        where.append("c.category = ?")
        args.append(category)
    if q.strip():
        where.append("(c.title LIKE ? OR cu.name LIKE ? OR c.location LIKE ?)")
        args += [f"%{q.strip()}%"] * 3
    return ("WHERE " + " AND ".join(where)) if where else "", args


@router.get("/cases")
def index(
    status: str = "", q: str = "", mine: str = "", category: str = "", page: str = "1",
    sort: str = "no", dir: str = "desc", user=login_required("officer", "admin"),
):
    page = page_number(page)
    clause, args = case_filter(status, q, mine, user, category)
    total = one(
        'SELECT COUNT(*) AS n FROM crime_case cs JOIN complaint c ON c.complaint_id = cs.complaint_id'
        " JOIN citizen ct ON ct.citizen_id = c.citizen_id JOIN users cu ON cu.user_id = ct.user_id " + clause,
        *args,
    )["n"]
    rows = many(
        CASE_SELECT + f" {clause} ORDER BY {order_by(SORTS, sort, dir, 'no')} LIMIT ? OFFSET ?",
        *args, PAGE_SIZE, (page - 1) * PAGE_SIZE,
    )
    flags = case_flags(rows)
    return {
        "items": [{**with_fir(r), "flags": flags.get(r["case_id"], [])} for r in rows], "statuses": CASE_STATUSES, "categories": CATEGORIES,
        "page": page, "total": total,
        "pages": max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1),
    }


@router.get("/cases/{case_id}/integrity")
def integrity_check(case_id: int, user=login_required("officer", "admin")):
    """Check the case ledger again, now: the chain, the records it sealed, and anything not sealed."""
    case = load_case(case_id)
    return ledger.verify(case["complaint_id"], events_for(case))


@router.get("/cases/{case_id}")
def detail(case_id: int, user=login_required("officer", "admin")):
    case = load_case(case_id)
    evidence = clean(mdb().evidence.find({"case_id": case_id}).sort("evidence_no", 1))
    for item in evidence:
        item.setdefault("custody", [])
        item["files"] = clean(mdb().attachments.find({"case_id": case_id, "evidence_no": item["evidence_no"]}).sort("_id", 1))
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
    events = case_timeline(case, reports)
    ledger.ensure(case, events)
    timeline = ledger.annotate(case["complaint_id"], events)
    integrity = ledger.verify(case["complaint_id"], events)
    attachments = list_for(case["complaint_id"])
    officers = many(
        "SELECT o.officer_id, u.name, o.officer_rank FROM officer o JOIN users u ON u.user_id = o.user_id"
        " WHERE u.active = 1 ORDER BY u.name"
    ) if user["role"] == "admin" else []
    return {
        "case": with_fir(case), "evidence": evidence, "linked": as_dicts(linked),
        "statements": clean(mdb().statements.find({"case_id": case_id}).sort("no", 1)),
        "arrests": clean(mdb().arrests.find({"case_id": case_id}).sort("no", 1)),
        "court_dates": clean(mdb().court_dates.find({"case_id": case_id}).sort("date", 1)),
        "chargesheet": (clean(mdb().chargesheets.find({"case_id": case_id})) or [None])[0],
        "custody_actions": CUSTODY_ACTIONS,
        "available": as_dicts(available), "reports": as_dicts(reports), "notes": notes,
        "history": history, "timeline": timeline, "integrity": integrity, "attachments": attachments, "officers": as_dicts(officers),
        "editable": can_edit(case, user), "next_states": CASE_TRANSITIONS[case["status"]],
        "flags": case_flags([case]).get(case_id, []),
    }


@router.post("/cases/{case_id}/status")
def status(case_id: int, body: Status, user=login_required("officer", "admin")):
    require_edit(case_id, user)
    change_case_status(case_id, body.status, user["user_id"])
    ledger.seal_case(case_id, user["name"])
    return {"ok": True}


@router.post("/cases/{case_id}/assign")
def assign(case_id: int, body: Assign, user=login_required("admin")):
    officer = assign_officer(case_id, body.officer_id, user["user_id"])
    ledger.seal_case(case_id, user["name"])
    return {"officer": officer}


@router.post("/cases/{case_id}/evidence")
def add_evidence(case_id: int, body: Evidence, user=login_required("officer", "admin")):
    require_edit(case_id, user)
    kind = need(body.type, "Evidence type", 60)
    description = need(body.description, "Description", 1000)
    last = mdb().evidence.find_one({"case_id": case_id}, sort=[("evidence_no", -1)])
    next_no = (last["evidence_no"] if last else 0) + 1
    mdb().evidence.insert_one({
        "case_id": case_id, "evidence_no": next_no, "type": kind,
        "description": description, "date_collected": now()[:10], "created_at": now(),
        "custody": [{"at": now(), "action": "collected", "by": user["name"], "where": "", "note": ""}],
    })
    ledger.seal_case(case_id, user["name"])
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
    ledger.seal_case(case_id, user["name"])
    return {"ok": True}


def _next_no(collection, case_id):
    last = mdb()[collection].find_one({"case_id": case_id}, sort=[("no", -1)])
    return (last["no"] if last else 0) + 1


def _evidence_item(case_id, evidence_no):
    item = mdb().evidence.find_one({"case_id": case_id, "evidence_no": evidence_no})
    if item is None:
        raise HTTPException(404, "That evidence item does not exist.")
    return item


@router.post("/cases/{case_id}/evidence/{evidence_no}/custody")
def add_custody(case_id: int, evidence_no: int, body: CustodyBody, user=login_required("officer", "admin")):
    require_edit(case_id, user)
    item = _evidence_item(case_id, evidence_no)
    if body.action not in CUSTODY_ACTIONS:
        raise RuleError("Pick what happened to the item.")
    where = need(body.where, "Where it is now", 120)
    if (item.get("custody") or [{}])[-1].get("action") in ("released", "destroyed"):
        raise RuleError("This item has already left custody.")
    mdb().evidence.update_one(
        {"case_id": case_id, "evidence_no": evidence_no},
        {"$push": {"custody": {
            "at": now(), "action": body.action, "by": user["name"], "where": where,
            "note": need(body.note, "Note", 500, required=False),
        }}},
    )
    ledger.seal_case(case_id, user["name"])
    return {"ok": True}


@router.post("/cases/{case_id}/evidence/{evidence_no}/files")
async def add_evidence_file(case_id: int, evidence_no: int, file: UploadFile, user=login_required("officer", "admin")):
    require_edit(case_id, user)
    _evidence_item(case_id, evidence_no)
    if mdb().attachments.count_documents({"case_id": case_id, "evidence_no": evidence_no}) >= 5:
        raise RuleError("An evidence item can hold 5 files at most.")
    attachment_id = await save_upload(file, {"case_id": case_id, "evidence_no": evidence_no})
    ledger.seal_case(case_id, user["name"])
    return {"attachment_id": attachment_id}


@router.post("/cases/{case_id}/statements")
def add_statement(case_id: int, body: StatementBody, user=login_required("officer", "admin")):
    require_edit(case_id, user)
    if body.kind not in PERSON_ROLES:
        raise RuleError("Pick whose statement this is.")
    no = _next_no("statements", case_id)
    mdb().statements.insert_one({
        "case_id": case_id, "no": no, "kind": body.kind, "person": need(body.person, "Name", 120),
        "body": need(body.body, "Statement", 4000), "recorded_by": user["name"], "recorded_at": now(),
    })
    ledger.seal_case(case_id, user["name"])
    return {"no": no}


@router.post("/cases/{case_id}/arrests")
def add_arrest(case_id: int, body: ArrestBody, user=login_required("officer", "admin")):
    require_edit(case_id, user)
    link = one("SELECT cr.name, cc.role FROM case_criminal cc JOIN criminal cr ON cr.criminal_id = cc.criminal_id"
               " WHERE cc.case_id = ? AND cc.criminal_id = ?", case_id, body.criminal_id)
    if link is None or link["role"] not in CHARGEABLE:
        raise RuleError("Only a suspect or accused person linked to this case can be arrested.")
    no = _next_no("arrests", case_id)
    mdb().arrests.insert_one({
        "case_id": case_id, "no": no, "criminal_id": body.criminal_id, "person": link["name"],
        "arrested_on": need_date(body.arrested_on, "Arrest date", allow_future=False),
        "place": need(body.place, "Place", 200), "charges": need(body.charges, "Charges", 500),
        "recorded_by": user["name"], "recorded_at": now(),
    })
    ledger.seal_case(case_id, user["name"])
    return {"no": no}


@router.post("/cases/{case_id}/chargesheet")
def chargesheet(case_id: int, body: ChargesheetBody, user=login_required("officer", "admin")):
    require_edit(case_id, user)
    file_chargesheet(
        case_id, need(body.sections, "Sections", 300), need(body.summary, "Summary", 4000), user["user_id"],
    )
    ledger.seal_case(case_id, user["name"])
    return {"ok": True}


@router.post("/cases/{case_id}/court-dates")
def add_court_date(case_id: int, body: CourtDateBody, user=login_required("officer", "admin")):
    case = require_edit(case_id, user)
    if not mdb().chargesheets.find_one({"case_id": case_id}):
        raise RuleError("A court date can be set once the chargesheet is filed.")
    day = need_date(body.date, "Court date")
    no = _next_no("court_dates", case_id)
    mdb().court_dates.insert_one({
        "case_id": case_id, "no": no, "date": day, "court": need(body.court, "Court", 150),
        "purpose": need(body.purpose, "Purpose", 200), "outcome": "", "set_by": user["name"], "created_at": now(),
    })
    owner = one("SELECT u.user_id FROM complaint c JOIN citizen ct ON ct.citizen_id = c.citizen_id"
                " JOIN users u ON u.user_id = ct.user_id WHERE c.complaint_id = ?", case["complaint_id"])
    notify(owner["user_id"], f"A court date was set for your case on {day}.", f"/complaints/{case['complaint_id']}")
    ledger.seal_case(case_id, user["name"])
    return {"no": no}


@router.post("/cases/{case_id}/court-dates/{no}/outcome")
def court_outcome(case_id: int, no: int, body: OutcomeBody, user=login_required("officer", "admin")):
    require_edit(case_id, user)
    result = mdb().court_dates.update_one(
        {"case_id": case_id, "no": no}, {"$set": {"outcome": need(body.outcome, "Outcome", 500), "outcome_at": now(), "outcome_by": user["name"]}}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "That court date does not exist.")
    ledger.seal_case(case_id, user["name"])
    return {"ok": True}
