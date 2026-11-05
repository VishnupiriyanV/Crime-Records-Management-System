
from bson import Binary
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import Response

from ..auth import login_required
from ..db import many, one
from ..forms import as_dicts
from ..lifecycle import RuleError
from ..mongo import mdb, now

router = APIRouter(prefix="/api")

PHOTO_BYTES = 1024 * 1024
PHOTO_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}

OPEN = "cs.status NOT LIKE 'Closed%'"


def _caseload(officer_id):
    """Open, resolved and unresolved case counts for one officer."""
    rows = many("SELECT status, COUNT(*) AS n FROM crime_case WHERE officer_id = ? GROUP BY status", officer_id)
    counts = {r["status"]: r["n"] for r in rows}
    resolved = counts.get("Closed (Resolved)", 0)
    unresolved = counts.get("Closed (Unresolved)", 0)
    open_cases = counts.get("Under Investigation", 0) + counts.get("Chargesheet Filed", 0)
    closed = resolved + unresolved
    return {
        "open": open_cases, "resolved": resolved, "unresolved": unresolved,
        "resolution_rate": round(100 * resolved / closed) if closed else None,
    }


def _officers_of(station_id):
    rows = many(
        "SELECT o.officer_id, o.badge_no, o.officer_rank, u.name FROM officer o"
        " JOIN users u ON u.user_id = o.user_id WHERE o.station_id = ? AND u.active = 1 ORDER BY u.name",
        station_id,
    )
    photos = set(mdb().officer_photos.distinct("officer_id"))
    return [{**dict(r), **_caseload(r["officer_id"]), "has_photo": r["officer_id"] in photos} for r in rows]


@router.get("/stations")
def stations(user=login_required("officer", "admin")):
    rows = many(
        "SELECT ps.*,"
        " (SELECT COUNT(*) FROM officer o WHERE o.station_id = ps.station_id) AS officers,"
        " (SELECT COUNT(*) FROM crime_case cs WHERE cs.station_id = ps.station_id) AS cases,"
        f" (SELECT COUNT(*) FROM crime_case cs WHERE cs.station_id = ps.station_id AND {OPEN}) AS open_cases"
        " FROM police_station ps ORDER BY ps.name"
    )
    return {"items": as_dicts(rows)}


@router.get("/stations/{station_id}")
def station(station_id: int, user=login_required("officer", "admin")):
    st = one("SELECT * FROM police_station WHERE station_id = ?", station_id)
    if st is None:
        raise HTTPException(404, "That station does not exist.")
    by_status = many(
        "SELECT status, COUNT(*) AS total FROM crime_case WHERE station_id = ? GROUP BY status ORDER BY total DESC",
        station_id,
    )
    by_category = many(
        "SELECT c.category, COUNT(*) AS total FROM crime_case cs JOIN complaint c ON c.complaint_id = cs.complaint_id"
        " WHERE cs.station_id = ? GROUP BY c.category ORDER BY total DESC, c.category",
        station_id,
    )
    recent = many(
        "SELECT cs.case_id, cs.status, cs.date_opened, c.title, c.category, c.severity, u.name AS officer_name"
        " FROM crime_case cs JOIN complaint c ON c.complaint_id = cs.complaint_id"
        " LEFT JOIN officer o ON o.officer_id = cs.officer_id LEFT JOIN users u ON u.user_id = o.user_id"
        " WHERE cs.station_id = ? ORDER BY cs.case_id DESC LIMIT 8",
        station_id,
    )
    unassigned = one(
        f"SELECT COUNT(*) AS n FROM crime_case cs WHERE cs.station_id = ? AND cs.officer_id IS NULL AND {OPEN}",
        station_id,
    )["n"]
    return {
        "station": dict(st), "by_status": as_dicts(by_status), "by_category": as_dicts(by_category),
        "officers": _officers_of(station_id), "recent": as_dicts(recent), "unassigned": unassigned,
    }


@router.get("/officers/{officer_id}")
def officer(officer_id: int, user=login_required("officer", "admin")):
    o = one(
        "SELECT o.officer_id, o.user_id, o.badge_no, o.officer_rank, u.name, u.email, u.active,"
        " ps.station_id, ps.name AS station FROM officer o JOIN users u ON u.user_id = o.user_id"
        " JOIN police_station ps ON ps.station_id = o.station_id WHERE o.officer_id = ?",
        officer_id,
    )
    if o is None:
        raise HTTPException(404, "That officer does not exist.")
    open_cases = many(
        "SELECT cs.case_id, cs.status, cs.date_opened, c.title, c.category, c.severity FROM crime_case cs"
        f" JOIN complaint c ON c.complaint_id = cs.complaint_id WHERE cs.officer_id = ? AND {OPEN}"
        " ORDER BY cs.case_id DESC",
        officer_id,
    )
    closed_cases = many(
        "SELECT cs.case_id, cs.status, cs.date_opened, c.title, c.category FROM crime_case cs"
        " JOIN complaint c ON c.complaint_id = cs.complaint_id WHERE cs.officer_id = ? AND cs.status LIKE 'Closed%'"
        " ORDER BY cs.case_id DESC LIMIT 8",
        officer_id,
    )
    can_edit_photo = user["role"] == "admin" or user["user_id"] == o["user_id"]
    return {
        "officer": {**dict(o), **_caseload(officer_id), "has_photo": mdb().officer_photos.count_documents({"officer_id": officer_id}) > 0},
        "open_cases": as_dicts(open_cases), "closed_cases": as_dicts(closed_cases), "can_edit_photo": can_edit_photo,
    }


@router.post("/officers/{officer_id}/photo")
async def set_photo(officer_id: int, file: UploadFile, user=login_required("officer", "admin")):
    o = one("SELECT user_id FROM officer WHERE officer_id = ?", officer_id)
    if o is None:
        raise HTTPException(404, "That officer does not exist.")
    if user["role"] != "admin" and user["user_id"] != o["user_id"]:
        raise RuleError("Only that officer or an admin can change this photo.")
    ext = "." + (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in PHOTO_TYPES:
        raise RuleError("Use a JPG, PNG or WebP image.")
    data = await file.read(PHOTO_BYTES + 1)
    if len(data) > PHOTO_BYTES:
        raise RuleError("The photo must be 1 MB or smaller.")
    if not data:
        raise RuleError("That file is empty.")
    mdb().officer_photos.replace_one(
        {"officer_id": officer_id},
        {"officer_id": officer_id, "data": Binary(data), "content_type": PHOTO_TYPES[ext], "updated_at": now()},
        upsert=True,
    )
    return {"ok": True}


@router.get("/officers/{officer_id}/photo")
def get_photo(officer_id: int, user=login_required("officer", "admin")):
    doc = mdb().officer_photos.find_one({"officer_id": officer_id})
    if doc is None:
        raise HTTPException(404, "No photo.")
    return Response(
        bytes(doc["data"]), media_type=doc["content_type"],
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=300"},
    )
