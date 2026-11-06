"""MongoDB holds the document-shaped data: evidence, citizen notes, notifications and the status trail.

The relational core (users, complaints, cases, criminals) stays in SQLite and is linked by id.
"""
from datetime import datetime, timezone

import re

from pymongo import ASCENDING, MongoClient
from pymongo.errors import PyMongoError

_db = None


def configure(url=None, name="crms", client=None):
    global _db
    if client is None:
        client = MongoClient(url, serverSelectionTimeoutMS=15000)
        try:
            client.admin.command("ping")
        except PyMongoError as err:
            shown = re.sub(r"//[^@/]*@", "//", url or "")  # never print the password
            reason = str(err).replace(url or "", shown)[:300]
            raise RuntimeError(f"Cannot reach MongoDB at {shown}. Start it, or set MONGO_URL. ({reason})") from None
    _db = client[name]
    _db.evidence.create_index([("case_id", ASCENDING), ("evidence_no", ASCENDING)], unique=True)
    _db.notes.create_index("complaint_id")
    _db.login_failures.create_index("key")
    _db.attachments.create_index("complaint_id")
    _db.attachments.create_index("attachment_id", unique=True)
    _db.attachment_files.create_index("attachment_id", unique=True)
    for name in ("statements", "arrests", "court_dates", "chargesheets"):
        _db[name].create_index("case_id")
    _db.officer_photos.create_index("officer_id", unique=True)
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
