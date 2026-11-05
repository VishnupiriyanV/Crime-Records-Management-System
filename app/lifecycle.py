"""Status rules for complaints and cases (FR-07, FR-08, FR-09, FR-12)."""
from .constants import CHARGEABLE
from .db import get_db, many, one, run
from .mongo import mdb, now

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
    who = one("SELECT name FROM users WHERE user_id = ?", user_id)
    mdb().status_log.insert_one({
        "entity": entity, "entity_id": entity_id, "old_status": old, "new_status": new,
        "user_id": user_id, "who": who["name"] if who else None, "changed_at": now(),
    })


def notify(user_id, message, link=None):
    mdb().notifications.insert_one(
        {"user_id": user_id, "message": message, "link": link, "seen": False, "created_at": now()}
    )


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
    if one('SELECT 1 FROM crime_case WHERE complaint_id = ?', complaint_id):
        raise RuleError("This complaint already has a case.")
    if not station_id or not one("SELECT 1 FROM police_station WHERE station_id = ?", station_id):
        raise RuleError("Pick a police station.")
    case_id = run('INSERT INTO crime_case (complaint_id, station_id) VALUES (?, ?)', complaint_id, station_id)
    log_status("case", case_id, None, "Under Investigation", user_id)
    notify(c["owner_id"], f"A case was opened for “{c['title']}”.", f"/complaints/{complaint_id}")
    get_db().commit()
    return case_id


def change_case_status(case_id, new_status, user_id):
    case = one('SELECT * FROM crime_case WHERE case_id = ?', case_id)
    if case is None:
        raise RuleError("Case not found.")
    if new_status not in CASE_TRANSITIONS.get(case["status"], []):
        raise RuleError(f"A case cannot move from “{case['status']}” to “{new_status}”.")
    if new_status == "Chargesheet Filed" and not mdb().chargesheets.find_one({"case_id": case_id}):
        raise RuleError("File the chargesheet first; it records the sections and a summary.")
    run('UPDATE crime_case SET status = ? WHERE case_id = ?', new_status, case_id)
    log_status("case", case_id, case["status"], new_status, user_id)
    owner = _complaint(case["complaint_id"])
    notify(owner["owner_id"], f"Your case is now “{new_status}”.", f"/complaints/{case['complaint_id']}")
    get_db().commit()


def assign_officer(case_id, officer_id, user_id):
    case = one('SELECT * FROM crime_case WHERE case_id = ?', case_id)
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
    run('UPDATE crime_case SET officer_id = ? WHERE case_id = ?', officer_id, case_id)
    log_status("case assignment", case_id, case["officer_id"], officer_id, user_id)
    _tell_officers(case, officer_id)
    get_db().commit()
    return officer["name"]


def _tell_officers(case, new_officer_id):
    """The new officer hears about the case, and the previous one hears it moved."""
    title = _complaint(case["complaint_id"])["title"]
    link = f"/cases/{case['case_id']}"
    if new_officer_id != case["officer_id"]:
        new = one("SELECT user_id FROM officer WHERE officer_id = ?", new_officer_id)
        notify(new["user_id"], f"Case {case['case_id']}, \u201c{title}\u201d, was assigned to you.", link)
    if case["officer_id"] and case["officer_id"] != new_officer_id:
        old = one("SELECT user_id FROM officer WHERE officer_id = ?", case["officer_id"])
        notify(old["user_id"], f"Case {case['case_id']}, \u201c{title}\u201d, was reassigned to another officer.", link)


def file_chargesheet(case_id, sections, summary, user_id):
    """Record the chargesheet and move the case to Chargesheet Filed in one step."""
    case = one('SELECT * FROM crime_case WHERE case_id = ?', case_id)
    if case is None:
        raise RuleError("Case not found.")
    if case["status"] != "Under Investigation":
        raise RuleError("Only a case under investigation can have a chargesheet filed.")
    placeholders = ", ".join("?" for _ in CHARGEABLE)
    charged = many(
        f"SELECT 1 FROM case_criminal WHERE case_id = ? AND role IN ({placeholders})", case_id, *CHARGEABLE
    )
    if not charged:
        raise RuleError("Link at least one suspect or accused person before filing a chargesheet.")
    who = one("SELECT name FROM users WHERE user_id = ?", user_id)
    mdb().chargesheets.insert_one({
        "case_id": case_id, "filed_on": now()[:10], "sections": sections, "summary": summary,
        "filed_by": who["name"] if who else None, "created_at": now(),
    })
    try:
        change_case_status(case_id, "Chargesheet Filed", user_id)
    except Exception:
        mdb().chargesheets.delete_many({"case_id": case_id})
        raise
