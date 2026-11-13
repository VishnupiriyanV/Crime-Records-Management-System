"""One merged, dated list of everything that happened to a case and its complaint."""
from .db import many, one
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


def _file_detail(upload):
    text = f"{upload['content_type']}, {upload['size']} bytes"
    # files from before fingerprints were kept have no hash, so their line stays as it was
    return f"{text}, SHA-256 {upload['sha256'][:16]}" if upload.get("sha256") else text


def _clip(text, size=200):
    text = " ".join(str(text or "").split())
    return text if len(text) <= size else text[: size - 1] + "\u2026"


def case_timeline(case, reports):
    case_id, complaint_id = case["case_id"], case["complaint_id"]
    events = []

    def add(at, kind, text, who=None, detail="", status=None):
        event = {"at": str(at), "kind": kind, "text": text, "who": who, "detail": detail}
        if status:
            event["status"] = status  # a status change also says which status it moved to
        events.append(event)

    filed = one("SELECT reject_reason FROM complaint WHERE complaint_id = ?", complaint_id)
    for entry in clean(mdb().status_log.find({"entity": "complaint", "entity_id": complaint_id})):
        why = f"Reason: {_clip(filed['reject_reason'])}" if entry["new_status"] == "Rejected" and filed and filed["reject_reason"] else ""
        add(entry["changed_at"], "status", _status_text("complaint", entry["old_status"], entry["new_status"]), entry["who"], why, entry["new_status"])
    for entry in clean(mdb().status_log.find({"entity": "complaint edit", "entity_id": complaint_id})):
        was = "; ".join(f"{name} was \u201c{_clip(old, 60)}\u201d" for name, old in (entry.get("before") or {}).items())
        add(entry["changed_at"], "note", "Citizen edited the complaint", entry["who"], was)
    for entry in clean(mdb().status_log.find({"entity": "case", "entity_id": case_id})):
        add(entry["changed_at"], "status", _status_text("case", entry["old_status"], entry["new_status"]), entry["who"], "", entry["new_status"])
    for entry in clean(mdb().status_log.find({"entity": "case assignment", "entity_id": case_id})):
        text = f"Assigned to {_officer_name(entry['new_status'])}"
        if entry["old_status"] is not None:
            text += f" (was {_officer_name(entry['old_status'])})"
        add(entry["changed_at"], "assign", text, entry["who"])

    for item in clean(mdb().evidence.find({"case_id": case_id})):
        # older records only kept the date; those are placed at the end of their day
        when = item.get("created_at") or f"{item['date_collected']} 23:59:59"
        add(when, "evidence", f"Evidence {item['evidence_no']} recorded: {item['type']}", None, _clip(item["description"]))
        # the first custody line is the collection itself, already shown above
        for step in (item.get("custody") or [])[1:]:
            add(step["at"], "evidence", f"Evidence {item['evidence_no']} {step['action']}: {step['where']}", step["by"], _clip(step.get("note")))
    for upload in clean(mdb().attachments.find({"case_id": case_id})):
        add(upload["uploaded_at"], "file", f"File attached to evidence {upload['evidence_no']}: {upload['filename']}", None, _file_detail(upload))
    for item in clean(mdb().statements.find({"case_id": case_id})):
        add(item["recorded_at"], "statement", f"Statement from {item['kind']} {item['person']}", item["recorded_by"], _clip(item["body"]))
    for item in clean(mdb().arrests.find({"case_id": case_id})):
        add(item["recorded_at"], "arrest", f"{item['person']} arrested at {item['place']}", item["recorded_by"], f"Charges: {_clip(item['charges'])}")
    for item in clean(mdb().chargesheets.find({"case_id": case_id})):
        add(item["created_at"], "status", f"Chargesheet filed under {item['sections']}", item["filed_by"], _clip(item["summary"]))
    for item in clean(mdb().court_dates.find({"case_id": case_id})):
        add(item["created_at"], "court", f"Court date set for {item['date']} at {item['court']}", item["set_by"], f"Purpose: {_clip(item['purpose'])}")
        if item.get("outcome_at"):
            add(item["outcome_at"], "court", f"Court outcome for {item['date']}: {_clip(item['outcome'], 80)}", item.get("outcome_by"))
    for report in reports:
        add(f"{report['date_generated']} 23:59:59", "report", "Report written", report["author"], _clip(report["content"]))
    for note in clean(mdb().notes.find({"complaint_id": complaint_id})):
        add(note["created_at"], "note", f"Citizen added a {note['kind']}", None, _clip(note["body"]))
    for upload in clean(mdb().attachments.find({"complaint_id": complaint_id})):
        add(upload["uploaded_at"], "file", f"File attached: {upload['filename']}", None, _file_detail(upload))

    events.sort(key=lambda e: e["at"])
    return events


def events_for(case):
    """The same list, for code that only has a case row and needs the reports too."""
    reports = many(
        "SELECT r.date_generated, r.content, u.name AS author FROM report r LEFT JOIN officer o ON o.officer_id = r.officer_id"
        " LEFT JOIN users u ON u.user_id = o.user_id WHERE r.case_id = ? ORDER BY r.report_id",
        case["case_id"],
    )
    return case_timeline(case, reports)
