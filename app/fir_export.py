"""FIR records as plain JSON, so another system can read them. The layout is ours, versioned in SCHEMA."""
from .constants import fir_number
from .db import many, one
from .mongo import clean, mdb

SCHEMA = "crms.fir/1"
PAGE = 25

SELECT = (
    "SELECT c.complaint_id, c.date_filed, c.incident_date, c.title, c.description, c.location, c.category,"
    " c.severity, c.latitude, c.longitude, c.status, u.name AS complainant,"
    " cs.case_id, cs.status AS case_status, cs.date_opened, ps.name AS station, ou.name AS officer"
    " FROM complaint c JOIN citizen ct ON ct.citizen_id = c.citizen_id JOIN users u ON u.user_id = ct.user_id"
    " LEFT JOIN crime_case cs ON cs.complaint_id = c.complaint_id"
    " LEFT JOIN police_station ps ON ps.station_id = cs.station_id"
    " LEFT JOIN officer o ON o.officer_id = cs.officer_id LEFT JOIN users ou ON ou.user_id = o.user_id"
)


def _documents(rows):
    case_ids = [r["case_id"] for r in rows if r["case_id"]]
    people, sheets, hearings = {}, {}, {}
    if case_ids:
        # three lookups for the whole page rather than three per record
        marks = ", ".join("?" * len(case_ids))
        for p in many(
            f"SELECT cc.case_id, cr.name, cc.role FROM case_criminal cc JOIN criminal cr ON cr.criminal_id = cc.criminal_id"
            f" WHERE cc.case_id IN ({marks})", *case_ids,
        ):
            people.setdefault(p["case_id"], []).append({"name": p["name"], "role": p["role"]})
        for s in clean(mdb().chargesheets.find({"case_id": {"$in": case_ids}})):
            sheets[s["case_id"]] = {"filed_on": s["filed_on"], "sections": s["sections"], "summary": s["summary"]}
        for h in clean(mdb().court_dates.find({"case_id": {"$in": case_ids}}).sort("date", 1)):
            hearings.setdefault(h["case_id"], []).append(
                {"date": h["date"], "court": h["court"], "purpose": h["purpose"], "outcome": h["outcome"]}
            )
    out = []
    for r in rows:
        case = None
        if r["case_id"]:
            case = {
                "status": r["case_status"], "opened_on": str(r["date_opened"]), "station": r["station"],
                "officer": r["officer"], "persons": people.get(r["case_id"], []),
                "chargesheet": sheets.get(r["case_id"]), "court_dates": hearings.get(r["case_id"], []),
            }
        out.append({
            "fir_number": fir_number(r["complaint_id"], r["date_filed"]), "filed_on": str(r["date_filed"]),
            "incident_date": str(r["incident_date"]), "title": r["title"], "description": r["description"],
            "category": r["category"], "severity": r["severity"], "location": r["location"],
            "coordinates": None if r["latitude"] is None else {"lat": r["latitude"], "lng": r["longitude"]},
            "status": r["status"], "complainant": r["complainant"], "case": case,
        })
    return out


def one_fir(complaint_id):
    row = one(f"{SELECT} WHERE c.complaint_id = ?", complaint_id)
    return {"schema": SCHEMA, **_documents([row])[0]} if row else None


def page_of_firs(since, page):
    where, args = ("WHERE c.date_filed >= ?", [since]) if since else ("", [])
    total = one(f"SELECT COUNT(*) AS n FROM complaint c {where}", *args)["n"]
    rows = many(f"{SELECT} {where} ORDER BY c.complaint_id LIMIT {PAGE} OFFSET {(page - 1) * PAGE}", *args)
    return {
        "schema": SCHEMA, "page": page, "pages": max((total + PAGE - 1) // PAGE, 1), "total": total,
        "items": _documents(rows),
    }
