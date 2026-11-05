"""One merged, dated list of everything that happened to a case and its complaint."""
from .db import one
from .mongo import clean, mdb


def _officer_name(officer_id):
    if officer_id is None:
        return "nobody"
    row = one(
        "SELECT u.name FROM officer o JOIN users u ON u.user_id = o.user_id WHERE o.officer_id = ?",
        officer_id,
    )
    return row["name"] if row else "a removed officer"


def _status_text(entity, old, new):
    if entity == "complaint":
        return "Complaint filed" if old is None else f"Complaint {new.lower()}"
    if old is None:
        return "Case opened"
    return f"Case moved to {new}"


def case_timeline(case, reports):
    case_id, complaint_id = case["case_id"], case["complaint_id"]
    events = []

    for entry in clean(mdb().status_log.find({"entity": "complaint", "entity_id": complaint_id})):
        events.append((entry["changed_at"], "status", _status_text("complaint", entry["old_status"], entry["new_status"]), entry["who"]))
    for entry in clean(mdb().status_log.find({"entity": "case", "entity_id": case_id})):
        events.append((entry["changed_at"], "status", _status_text("case", entry["old_status"], entry["new_status"]), entry["who"]))
    for entry in clean(mdb().status_log.find({"entity": "case assignment", "entity_id": case_id})):
        text = f"Assigned to {_officer_name(entry['new_status'])}"
        if entry["old_status"] is not None:
            text += f" (was {_officer_name(entry['old_status'])})"
        events.append((entry["changed_at"], "assign", text, entry["who"]))

    for item in clean(mdb().evidence.find({"case_id": case_id})):
        # older records only kept the date; those are placed at the end of their day
        when = item.get("created_at") or f"{item['date_collected']} 23:59:59"
        events.append((when, "evidence", f"Evidence {item['evidence_no']} recorded: {item['type']}", None))
    for entry in clean(mdb().evidence.find({"case_id": case_id})):
        # the first custody line is the collection itself, already shown above
        for step in (entry.get("custody") or [])[1:]:
            events.append((step["at"], "evidence", f"Evidence {entry['evidence_no']} {step['action']}: {step['where']}", step["by"]))
    for item in clean(mdb().statements.find({"case_id": case_id})):
        events.append((item["recorded_at"], "statement", f"Statement from {item['kind']} {item['person']}", item["recorded_by"]))
    for item in clean(mdb().arrests.find({"case_id": case_id})):
        events.append((item["recorded_at"], "arrest", f"{item['person']} arrested at {item['place']}", item["recorded_by"]))
    for item in clean(mdb().chargesheets.find({"case_id": case_id})):
        events.append((item["created_at"], "status", f"Chargesheet filed under {item['sections']}", item["filed_by"]))
    for item in clean(mdb().court_dates.find({"case_id": case_id})):
        events.append((item["created_at"], "court", f"Court date set for {item['date']} at {item['court']}", item["set_by"]))
    for report in reports:
        events.append((f"{report['date_generated']} 23:59:59", "report", "Report written", report["author"]))
    for note in clean(mdb().notes.find({"complaint_id": complaint_id})):
        events.append((note["created_at"], "note", f"Citizen added a {note['kind']}", None))
    for upload in clean(mdb().attachments.find({"complaint_id": complaint_id})):
        events.append((upload["uploaded_at"], "file", f"File attached: {upload['filename']}", None))

    events.sort(key=lambda e: e[0])
    return [{"at": at, "kind": kind, "text": text, "who": who} for at, kind, text, who in events]
