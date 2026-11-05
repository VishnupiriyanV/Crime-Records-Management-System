import re

from fastapi import APIRouter

from ..auth import login_required
from ..db import one
from ..forms import page_number
from ..mongo import clean, mdb

router = APIRouter(prefix="/api")

PAGE_SIZE = 30


def _officer(officer_id):
    if officer_id is None:
        return "nobody"
    row = one(
        "SELECT u.name FROM officer o JOIN users u ON u.user_id = o.user_id WHERE o.officer_id = ?",
        officer_id,
    )
    return row["name"] if row else f"officer {officer_id}"


@router.get("/audit")
def audit(entity: str = "", q: str = "", page: str = "1", user=login_required("admin")):
    page = page_number(page)
    find = {}
    if entity:
        find["entity"] = entity
    if q.strip():
        find["$or"] = [
            {"who": {"$regex": re.escape(q.strip()), "$options": "i"}},
            {"new_status": {"$regex": re.escape(q.strip()), "$options": "i"}},
        ]
    total = mdb().status_log.count_documents(find)
    rows = clean(mdb().status_log.find(find).sort("_id", -1).skip((page - 1) * PAGE_SIZE).limit(PAGE_SIZE))
    for row in rows:
        # assignments store officer ids, which mean nothing to a reader
        if row["entity"] == "case assignment":
            row["old_status"] = _officer(row["old_status"]) if row["old_status"] is not None else None
            row["new_status"] = _officer(row["new_status"])
    return {
        "items": rows, "page": page, "total": total, "pages": max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1),
        "entities": sorted(mdb().status_log.distinct("entity")),
    }
