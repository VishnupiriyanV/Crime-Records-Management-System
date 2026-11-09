"""Flags for work that has waited too long. A High severity complaint waits half as long."""
from datetime import date, datetime

from .db import many
from .mongo import mdb

# days before each flag appears
LIMITS = {"unreviewed": 2, "unassigned": 3, "stale": 14}
OPEN = ("Under Investigation", "Chargesheet Filed")


def limit(kind, severity):
    days = LIMITS[kind]
    return max(1, days // 2) if severity == "High" else days


def _days_since(text, today):
    try:
        return (today - datetime.strptime(str(text)[:10], "%Y-%m-%d").date()).days
    except ValueError:
        return 0


def last_activity(rows):
    """The latest day anything happened on each open case. One lookup per kind of record, not one per case."""
    ids = [r["case_id"] for r in rows]
    seen = {r["case_id"]: str(r["date_opened"])[:10] for r in rows}
    if not ids:
        return seen

    def bump(case_id, when):
        if when and str(when)[:10] > seen.get(case_id, ""):
            seen[case_id] = str(when)[:10]

    for name, field in (
        ("evidence", "created_at"), ("statements", "recorded_at"), ("arrests", "recorded_at"),
        ("court_dates", "created_at"), ("chargesheets", "created_at"), ("attachments", "uploaded_at"),
    ):
        for found in mdb()[name].aggregate([
            {"$match": {"case_id": {"$in": ids}}}, {"$group": {"_id": "$case_id", "at": {"$max": f"${field}"}}},
        ]):
            bump(found["_id"], found["at"])
    for found in mdb().status_log.aggregate([
        {"$match": {"entity": {"$in": ["case", "case assignment"]}, "entity_id": {"$in": ids}}},
        {"$group": {"_id": "$entity_id", "at": {"$max": "$changed_at"}}},
    ]):
        bump(found["_id"], found["at"])
    marks = ", ".join("?" * len(ids))
    for found in many(f"SELECT case_id, MAX(date_generated) AS at FROM report WHERE case_id IN ({marks}) GROUP BY case_id", *ids):
        bump(found["case_id"], found["at"])
    return seen


def complaint_flags(rows, today=None):
    """{complaint_id: [flags]} for complaints still waiting for a decision."""
    today = today or date.today()
    out = {}
    for r in rows:
        if r["status"] != "Filed":
            continue
        waited = _days_since(r["date_filed"], today)
        if waited >= limit("unreviewed", r["severity"]):
            out[r["complaint_id"]] = [{"kind": "unreviewed", "days": waited, "text": f"Waiting {waited} days for review"}]
    return out


def case_flags(rows, today=None):
    """{case_id: [flags]} for open cases; rows need case_id, status, officer_id, date_opened and severity."""
    today = today or date.today()
    open_rows = [r for r in rows if r["status"] in OPEN]
    out = {}

    def add(case_id, kind, days, text):
        out.setdefault(case_id, []).append({"kind": kind, "days": days, "text": text})

    quiet = [r for r in open_rows if _days_since(r["date_opened"], today) >= limit("stale", r["severity"])]
    latest = last_activity(quiet)
    for r in open_rows:
        age = _days_since(r["date_opened"], today)
        if r["officer_id"] is None and age >= limit("unassigned", r["severity"]):
            add(r["case_id"], "unassigned", age, f"No officer for {age} days")
        if r["case_id"] in latest:
            idle = _days_since(latest[r["case_id"]], today)
            if idle >= limit("stale", r["severity"]):
                add(r["case_id"], "stale", idle, f"No activity for {idle} days")

    ids = [r["case_id"] for r in open_rows]
    if ids:
        names = {r["case_id"]: r for r in open_rows}
        for h in mdb().court_dates.find({"case_id": {"$in": ids}, "date": {"$lt": today.isoformat()}, "outcome": ""}):
            add(h["case_id"], "hearing", _days_since(h["date"], today), f"Hearing on {h['date']} has no outcome")
    return out
