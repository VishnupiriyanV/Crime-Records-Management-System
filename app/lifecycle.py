"""Status rules for complaints and cases (FR-07, FR-08, FR-09, FR-12)."""
from .db import get_db, one, run

# the only moves a case may make
CASE_TRANSITIONS = {
    "Under Investigation": ["Chargesheet Filed", "Closed (Unresolved)"],
    "Chargesheet Filed": ["Closed (Resolved)"],
    "Closed (Resolved)": [],
    "Closed (Unresolved)": [],
}
CASE_STATUSES = list(CASE_TRANSITIONS)


class RuleError(Exception):
    """A request that breaks a business rule; the message is shown to the user."""


def is_closed(status):
    return not CASE_TRANSITIONS[status]


def log_status(entity, entity_id, old, new, user_id):
    run(
        "INSERT INTO status_log (entity, entity_id, old_status, new_status, user_id)"
        " VALUES (?, ?, ?, ?, ?)",
        entity, entity_id, old, new, user_id,
    )


def notify(user_id, message, link=None):
    run("INSERT INTO notification (user_id, message, link) VALUES (?, ?, ?)", user_id, message, link)


def _complaint(complaint_id):
    row = one(
        "SELECT c.*, u.user_id AS owner_id FROM complaint c"
        " JOIN citizen ct ON ct.citizen_id = c.citizen_id"
        " JOIN users u ON u.user_id = ct.user_id WHERE c.complaint_id = ?",
        complaint_id,
    )
    if row is None:
        raise RuleError("Complaint not found.")
    return row


def verify_complaint(complaint_id, user_id):
    c = _complaint(complaint_id)
    if c["status"] != "Filed":
        raise RuleError("Only a filed complaint can be verified.")
    run("UPDATE complaint SET status = 'Verified' WHERE complaint_id = ?", complaint_id)
    log_status("complaint", complaint_id, c["status"], "Verified", user_id)
    notify(c["owner_id"], f"Your complaint “{c['title']}” was verified.", f"/complaints/{complaint_id}")
    get_db().commit()


def reject_complaint(complaint_id, reason, user_id):
    c = _complaint(complaint_id)
    if c["status"] != "Filed":
        raise RuleError("Only a filed complaint can be rejected.")
    if not reason:
        raise RuleError("A rejection needs a reason.")
    run(
        "UPDATE complaint SET status = 'Rejected', reject_reason = ? WHERE complaint_id = ?",
        reason, complaint_id,
    )
    log_status("complaint", complaint_id, c["status"], "Rejected", user_id)
    notify(c["owner_id"], f"Your complaint “{c['title']}” was rejected.", f"/complaints/{complaint_id}")
    get_db().commit()


def register_case(complaint_id, station_id, user_id):
    c = _complaint(complaint_id)
    if c["status"] != "Verified":
        raise RuleError("Only a verified complaint can become a case.")
    if one('SELECT 1 FROM "case" WHERE complaint_id = ?', complaint_id):
        raise RuleError("This complaint already has a case.")
    if not station_id or not one("SELECT 1 FROM police_station WHERE station_id = ?", station_id):
        raise RuleError("Pick a police station.")
    case_id = run('INSERT INTO "case" (complaint_id, station_id) VALUES (?, ?)', complaint_id, station_id)
    log_status("case", case_id, None, "Under Investigation", user_id)
    notify(c["owner_id"], f"A case was opened for “{c['title']}”.", f"/complaints/{complaint_id}")
    get_db().commit()
    return case_id


def change_case_status(case_id, new_status, user_id):
    case = one('SELECT * FROM "case" WHERE case_id = ?', case_id)
    if case is None:
        raise RuleError("Case not found.")
    if new_status not in CASE_TRANSITIONS.get(case["status"], []):
        raise RuleError(f"A case cannot move from “{case['status']}” to “{new_status}”.")
    run('UPDATE "case" SET status = ? WHERE case_id = ?', new_status, case_id)
    log_status("case", case_id, case["status"], new_status, user_id)
    owner = _complaint(case["complaint_id"])
    notify(owner["owner_id"], f"Your case is now “{new_status}”.", f"/complaints/{case['complaint_id']}")
    get_db().commit()


def assign_officer(case_id, officer_id, user_id):
    case = one('SELECT * FROM "case" WHERE case_id = ?', case_id)
    if case is None:
        raise RuleError("Case not found.")
    if is_closed(case["status"]):
        raise RuleError("A closed case cannot be reassigned.")
    officer = one(
        "SELECT o.officer_id, u.name FROM officer o JOIN users u ON u.user_id = o.user_id"
        " WHERE o.officer_id = ? AND u.active = 1",
        officer_id,
    )
    if officer is None:
        raise RuleError("Pick an active officer.")
    run('UPDATE "case" SET officer_id = ? WHERE case_id = ?', officer_id, case_id)
    log_status("case assignment", case_id, case["officer_id"], officer_id, user_id)
    get_db().commit()
    return officer["name"]
