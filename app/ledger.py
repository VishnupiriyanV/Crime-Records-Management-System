"""A tamper-evident record of what happened to a case.

Every event on a case (status changes, evidence, custody steps, statements, arrests, the chargesheet, court dates,
reports) is sealed into a chain. Each entry carries a keyed hash (HMAC-SHA256) of the entry before it, so changing,
removing or reordering any entry breaks every hash after it, and nobody who can write to the database but does not
hold the server secret can repair the chain. The chain head is also kept apart, which exposes entries cut off the end.

The ledger seals what the case records say. Verifying compares the two again: a record that was edited or deleted
after it was sealed no longer matches its entry, and a record that appeared without being sealed is reported.
"""
import hashlib
import hmac
import json
from datetime import datetime

from pymongo.errors import DuplicateKeyError

from .mongo import clean, mdb, now
from .db import one
from . import timeline

_secret = b"crms"
LATE_SECONDS = 300  # a record sealed much later than the time it claims is worth a second look


def configure(secret):
    global _secret
    _secret = str(secret).encode()


def key_of(event):
    body = {k: event.get(k) or "" for k in ("at", "kind", "text", "who", "detail")}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]


def _digest(prev, row):
    body = {k: row[k] for k in ("seq", "key", "event", "sealed_at", "sealed_by", "imported")}
    text = prev + "|" + json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hmac.new(_secret, text.encode(), hashlib.sha256).hexdigest()


def _event_body(event):
    return {k: event.get(k) or "" for k in ("at", "kind", "text", "who", "detail", "status")}


def entries(complaint_id):
    return clean(mdb().ledger.find({"complaint_id": complaint_id}).sort("seq", 1))


def seal(complaint_id, events, by, imported=False):
    """Add an entry for every event the ledger has not sealed yet; returns how many were added."""
    sealed = {row["key"] for row in mdb().ledger.find({"complaint_id": complaint_id}, {"key": 1})}
    added = 0
    for event in sorted(events, key=lambda e: e["at"]):
        key = key_of(event)
        if key in sealed:
            continue
        for _ in range(5):
            head = mdb().ledger_heads.find_one({"complaint_id": complaint_id}) or {"seq": 0, "hash": ""}
            row = {
                "complaint_id": complaint_id, "seq": head["seq"] + 1, "key": key, "event": _event_body(event),
                "sealed_at": now(), "sealed_by": by or "system", "imported": imported,
            }
            row["hash"] = _digest(head["hash"], row)
            try:
                mdb().ledger.insert_one(row)
            except DuplicateKeyError:
                continue  # another request sealed an entry at the same moment; take the next number
            mdb().ledger_heads.update_one(
                {"complaint_id": complaint_id}, {"$set": {"seq": row["seq"], "hash": row["hash"]}}, upsert=True
            )
            sealed.add(key)
            added += 1
            break
    return added


def seal_case(case_id, by):
    """Called after a change to a case; it must never break the change that was just saved."""
    try:
        case = one("SELECT case_id, complaint_id FROM crime_case WHERE case_id = ?", case_id)
        if case:
            seal(case["complaint_id"], timeline.events_for(case), by)
    except Exception:
        pass  # whatever is left unsealed is reported by verify, so it is not lost


def seal_complaint(complaint_id, by):
    case = one("SELECT case_id FROM crime_case WHERE complaint_id = ?", complaint_id)
    if case:
        seal_case(case["case_id"], by)


def ensure(case, events):
    """The first time a case is looked at with no ledger, seal what it already holds, marked as imported."""
    if not mdb().ledger_heads.find_one({"complaint_id": case["complaint_id"]}):
        seal(case["complaint_id"], events, "system", imported=True)


def _seconds_between(earlier, later):
    try:
        return (datetime.strptime(later[:19], "%Y-%m-%d %H:%M:%S") - datetime.strptime(earlier[:19], "%Y-%m-%d %H:%M:%S")).total_seconds()
    except ValueError:
        return 0


def _file_problems(complaint_id):
    """Uploaded files are fingerprinted when stored; a file whose bytes no longer match is reported."""
    case = one("SELECT case_id FROM crime_case WHERE complaint_id = ?", complaint_id)
    owners = [{"complaint_id": complaint_id}] + ([{"case_id": case["case_id"]}] if case else [])
    problems = []
    for doc in mdb().attachments.find({"$or": owners}):
        if not doc.get("sha256"):
            continue
        stored = mdb().attachment_files.find_one({"attachment_id": doc.get("attachment_id")})
        if stored is None or hashlib.sha256(bytes(stored["data"])).hexdigest() != doc["sha256"]:
            problems.append(f"The file {doc.get('filename', 'an upload')} no longer matches the fingerprint taken when it was uploaded.")
    return problems


def verify(complaint_id, events):
    rows = entries(complaint_id)
    problems, prev = [], ""
    for position, row in enumerate(rows, 1):
        if row["seq"] != position:
            problems.append(f"Entry {position} is missing or out of order.")
            break
        if _digest(prev, row) != row["hash"]:
            problems.append(f"Entry {row['seq']} was altered: {row['event']['text']}.")
        prev = row["hash"]

    head = mdb().ledger_heads.find_one({"complaint_id": complaint_id})
    if head and (not rows or head["seq"] != rows[-1]["seq"] or head["hash"] != rows[-1]["hash"]):
        problems.append("Entries were removed from the end of the ledger.")
    chain_ok = not problems

    current = {key_of(e): e for e in events}
    sealed_keys = {row["key"] for row in rows}
    for row in rows:
        if row["key"] not in current:
            problems.append(f"Entry {row['seq']} no longer matches its record: {row['event']['text']}.")
    unsealed = [e for e in events if key_of(e) not in sealed_keys]
    if unsealed:
        problems.append(f"{len(unsealed)} recorded event{'s are' if len(unsealed) != 1 else ' is'} not covered by the seal.")
    try:
        problems.extend(_file_problems(complaint_id))
    except Exception:  # one odd file record must not stop the rest of the check from answering
        problems.append("The uploaded files could not be checked.")
    late = [
        row["seq"] for row in rows
        if not row["imported"] and _seconds_between(row["event"]["at"], row["sealed_at"]) > LATE_SECONDS
    ]
    return {
        "ok": not problems, "chain_ok": chain_ok, "entries": len(rows), "head": rows[-1]["hash"] if rows else "",
        "imported": sum(1 for r in rows if r["imported"]), "late": late, "problems": problems, "checked_at": now(),
    }


def annotate(complaint_id, events):
    """The events with the seal each one carries, for showing on the timeline."""
    by_key = {row["key"]: row for row in entries(complaint_id)}
    out = []
    for event in events:
        row = by_key.get(key_of(event))
        seal_info = None
        if row:
            seal_info = {"seq": row["seq"], "hash": row["hash"][:8], "imported": row["imported"], "sealed_at": row["sealed_at"], "sealed_by": row["sealed_by"]}
        out.append({**event, "seal": seal_info})
    return out
