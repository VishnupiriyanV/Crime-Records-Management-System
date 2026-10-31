from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..auth import login_required
from ..db import get_db, many, one, run
from ..forms import as_dict, as_dicts, need, page_number
from ..lifecycle import RuleError

router = APIRouter(prefix="/api")

PAGE_SIZE = 20


class CriminalBody(BaseModel):
    name: str = ""
    age: int | str | None = None
    crime_history: str = ""
    wanted: bool = False


def _age(value):
    if value in (None, ""):
        return None
    if not str(value).isdigit() or not 0 <= int(value) <= 120:
        raise RuleError("Age must be a number between 0 and 120.")
    return int(value)


@router.get("/criminals")
def index(q: str = "", wanted: str = "", page: str = "1", user=login_required("officer", "admin")):
    q = q.strip()
    page = page_number(page)
    where, args = [], []
    if q:
        where.append("(name LIKE ? OR crime_history LIKE ?)")
        args += [f"%{q}%", f"%{q}%"]
    if wanted == "1":
        where.append("wanted = 1")
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    total = one(f"SELECT COUNT(*) AS n FROM criminal {clause}", *args)["n"]
    rows = many(
        f"SELECT cr.*, (SELECT COUNT(*) FROM case_criminal cc WHERE cc.criminal_id = cr.criminal_id) AS cases"
        f" FROM criminal cr {clause} ORDER BY name LIMIT ? OFFSET ?",
        *args, PAGE_SIZE, (page - 1) * PAGE_SIZE,
    )
    return {
        "items": as_dicts(rows), "page": page, "total": total,
        "pages": max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1),
    }


@router.post("/criminals")
def create(body: CriminalBody, user=login_required("officer", "admin")):
    criminal_id = run(
        "INSERT INTO criminal (name, age, crime_history, wanted) VALUES (?, ?, ?, ?)",
        need(body.name, "Name", 120), _age(body.age),
        need(body.crime_history, "Crime history", 2000, required=False), int(body.wanted),
    )
    get_db().commit()
    return {"criminal_id": criminal_id}


@router.get("/criminals/{criminal_id}")
def detail(criminal_id: int, user=login_required("officer", "admin")):
    c = one("SELECT * FROM criminal WHERE criminal_id = ?", criminal_id)
    if c is None:
        raise HTTPException(404, "That record does not exist.")
    cases = many(
        'SELECT cs.case_id, cs.status, cs.date_opened, c.title, cc.role FROM case_criminal cc'
        ' JOIN "case" cs ON cs.case_id = cc.case_id JOIN complaint c ON c.complaint_id = cs.complaint_id'
        " WHERE cc.criminal_id = ? ORDER BY cs.case_id DESC",
        criminal_id,
    )
    return {"criminal": dict(c), "cases": as_dicts(cases)}


@router.put("/criminals/{criminal_id}")
def update(criminal_id: int, body: CriminalBody, user=login_required("officer", "admin")):
    if one("SELECT 1 FROM criminal WHERE criminal_id = ?", criminal_id) is None:
        raise HTTPException(404, "That record does not exist.")
    run(
        "UPDATE criminal SET name = ?, age = ?, crime_history = ?, wanted = ? WHERE criminal_id = ?",
        need(body.name, "Name", 120), _age(body.age),
        need(body.crime_history, "Crime history", 2000, required=False), int(body.wanted), criminal_id,
    )
    get_db().commit()
    return {"ok": True}


@router.get("/records")
def public_records(q: str = "", user=login_required()):
    """What a citizen may search: wanted persons and station contacts, nothing from case files."""
    q = q.strip()
    wanted = many(
        "SELECT name, age FROM criminal WHERE wanted = 1 AND name LIKE ? ORDER BY name LIMIT 50",
        f"%{q}%",
    )
    stations = many(
        "SELECT * FROM police_station WHERE name LIKE ? OR jurisdiction LIKE ? ORDER BY name",
        f"%{q}%", f"%{q}%",
    )
    return {"wanted": as_dicts(wanted), "stations": as_dicts(stations)}
