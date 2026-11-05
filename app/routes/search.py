from fastapi import APIRouter

from ..auth import is_staff, login_required
from ..db import many
from ..forms import as_dicts
from .complaints import _citizen_id

router = APIRouter(prefix="/api")

LIMIT = 8


@router.get("/search")
def search(q: str = "", user=login_required()):
    q = q.strip()
    if len(q) < 2:
        return {"complaints": [], "cases": [], "criminals": []}
    like = f"%{q}%"

    # a citizen only ever searches their own complaints
    if is_staff(user):
        complaints = many(
            "SELECT c.complaint_id, c.title, c.location, c.status FROM complaint c"
            " WHERE c.title LIKE ? OR c.location LIKE ? ORDER BY c.complaint_id DESC LIMIT ?",
            like, like, LIMIT,
        )
    else:
        complaints = many(
            "SELECT c.complaint_id, c.title, c.location, c.status FROM complaint c"
            " WHERE c.citizen_id = ? AND (c.title LIKE ? OR c.location LIKE ?)"
            " ORDER BY c.complaint_id DESC LIMIT ?",
            _citizen_id(user), like, like, LIMIT,
        )
    result = {"complaints": as_dicts(complaints), "cases": [], "criminals": []}

    if is_staff(user):
        result["cases"] = as_dicts(many(
            "SELECT cs.case_id, cs.status, c.title, c.location FROM crime_case cs"
            " JOIN complaint c ON c.complaint_id = cs.complaint_id"
            " WHERE c.title LIKE ? OR c.location LIKE ? ORDER BY cs.case_id DESC LIMIT ?",
            like, like, LIMIT,
        ))
        result["criminals"] = as_dicts(many(
            "SELECT criminal_id, name, wanted FROM criminal WHERE name LIKE ? ORDER BY name LIMIT ?",
            like, LIMIT,
        ))
    return result
