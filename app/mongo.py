"""MongoDB holds the document-shaped data: evidence, citizen notes, notifications and the status trail.

The relational core (users, complaints, cases, criminals) stays in SQLite and is linked by id.
"""
from datetime import datetime, timezone

from pymongo import ASCENDING, MongoClient

_db = None


def configure(url=None, name="crms", client=None):
    global _db
    client = client or MongoClient(url, serverSelectionTimeoutMS=3000)
    _db = client[name]
    _db.evidence.create_index([("case_id", ASCENDING), ("evidence_no", ASCENDING)], unique=True)
    _db.notes.create_index("complaint_id")
    _db.login_failures.create_index("key")
    _db.attachments.create_index("complaint_id")
    _db.attachments.create_index("attachment_id", unique=True)
    _db.notifications.create_index([("user_id", ASCENDING), ("seen", ASCENDING)])
    _db.status_log.create_index([("entity", ASCENDING), ("entity_id", ASCENDING)])
    return _db


def mdb():
    return _db


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def clean(cursor):
    """Drop Mongo's _id so documents can go straight into a JSON response."""
    out = []
    for doc in cursor:
        doc.pop("_id", None)
        out.append(doc)
    return out
