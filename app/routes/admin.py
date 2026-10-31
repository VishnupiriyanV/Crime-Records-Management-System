from fastapi import APIRouter
from pydantic import BaseModel

from ..auth import hash_password, login_required
from ..db import get_db, many, one, run
from ..forms import as_dict, as_dicts, need
from ..lifecycle import RuleError
from ..mongo import mdb

router = APIRouter(prefix="/api")

ROLES = ("citizen", "officer", "admin")


class NewUser(BaseModel):
    name: str = ""
    email: str = ""
    password: str = ""
    role: str = ""
    badge_no: str = ""
    rank: str = ""
    station_id: int | None = None


class RoleChange(BaseModel):
    role: str = ""


@router.get("/reports")
def reports(start: str = "", end: str = "", criminal: str = "", user=login_required("admin")):
    by_status = many("SELECT * FROM v_cases_by_status ORDER BY total DESC")
    by_station = many("SELECT * FROM v_cases_by_station ORDER BY total DESC, station")

    period = None
    if start and end:
        period = {
            "complaints": one(
                "SELECT COUNT(*) AS n FROM complaint WHERE date_filed BETWEEN ? AND ?", start, end
            )["n"],
            "cases": one(
                'SELECT COUNT(*) AS n FROM "case" WHERE date_opened BETWEEN ? AND ?', start, end
            )["n"],
            "closed": len(mdb().status_log.distinct("entity_id", {
                "entity": "case", "new_status": {"$regex": "^Closed"},
                "changed_at": {"$gte": start, "$lte": end + " 23:59:59"},
            })),
        }

    history = None
    if criminal.isdigit():
        person = one("SELECT * FROM criminal WHERE criminal_id = ?", int(criminal))
        if person:
            history = {
                "criminal": dict(person),
                "cases": as_dicts(many(
                    'SELECT cs.case_id, cs.status, cs.date_opened, c.title, cc.role FROM case_criminal cc'
                    ' JOIN "case" cs ON cs.case_id = cc.case_id JOIN complaint c ON c.complaint_id = cs.complaint_id'
                    " WHERE cc.criminal_id = ? ORDER BY cs.date_opened",
                    person["criminal_id"],
                )),
            }
    return {
        "by_status": as_dicts(by_status), "by_station": as_dicts(by_station), "period": period,
        "criminals": as_dicts(many("SELECT criminal_id, name FROM criminal ORDER BY name")),
        "history": history,
    }


@router.get("/users")
def users(user=login_required("admin")):
    rows = many(
        "SELECT u.user_id, u.name, u.email, u.role, u.active, o.badge_no, o.rank, ps.name AS station"
        " FROM users u LEFT JOIN officer o ON o.user_id = u.user_id"
        " LEFT JOIN police_station ps ON ps.station_id = o.station_id ORDER BY u.role, u.name"
    )
    stations = many("SELECT * FROM police_station ORDER BY name")
    return {"rows": as_dicts(rows), "stations": as_dicts(stations), "roles": ROLES}


def _ensure_role_row(body, user_id, role):
    """Create the role-specific row when an account is given a role for the first time."""
    if role == "citizen":
        run("INSERT OR IGNORE INTO citizen (user_id) VALUES (?)", user_id)
    elif role == "admin":
        run("INSERT OR IGNORE INTO admin (user_id) VALUES (?)", user_id)
    elif role == "officer":
        if one("SELECT 1 FROM officer WHERE user_id = ?", user_id):
            return
        badge = need(body.badge_no, "Badge number", 40)
        rank = need(body.rank, "Rank", 60)
        if not body.station_id or not one("SELECT 1 FROM police_station WHERE station_id = ?", body.station_id):
            raise RuleError("Pick a station for the officer.")
        if one("SELECT 1 FROM officer WHERE badge_no = ?", badge):
            raise RuleError("That badge number is already in use.")
        run(
            "INSERT INTO officer (user_id, badge_no, rank, station_id) VALUES (?, ?, ?, ?)",
            user_id, badge, rank, body.station_id,
        )


@router.post("/users")
def create_user(body: NewUser, user=login_required("admin")):
    if body.role not in ROLES:
        raise RuleError("Pick a role.")
    name = need(body.name, "Name", 100)
    email = need(body.email, "Email", 200).lower()
    password = need(body.password, "Password", 200)
    if len(password) < 8:
        raise RuleError("Use at least 8 characters for the password.")
    if one("SELECT 1 FROM users WHERE email = ?", email):
        raise RuleError("An account with that email already exists.")
    user_id = run(
        "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
        name, email, hash_password(password), body.role,
    )
    try:
        _ensure_role_row(body, user_id, body.role)
    except RuleError:
        get_db().rollback()
        raise
    get_db().commit()
    return {"user_id": user_id}


@router.put("/users/{user_id}/role")
def change_role(user_id: int, body: RoleChange, user=login_required("admin")):
    if body.role not in ROLES:
        raise RuleError("Pick a role.")
    if user_id == user["user_id"]:
        raise RuleError("You cannot change your own role.")
    if body.role == "officer" and not one("SELECT 1 FROM officer WHERE user_id = ?", user_id):
        raise RuleError("Create the account as an officer so a badge, rank and station are recorded.")
    if body.role == "citizen":
        run("INSERT OR IGNORE INTO citizen (user_id) VALUES (?)", user_id)
    elif body.role == "admin":
        run("INSERT OR IGNORE INTO admin (user_id) VALUES (?)", user_id)
    run("UPDATE users SET role = ? WHERE user_id = ?", body.role, user_id)
    get_db().commit()
    return {"ok": True}


@router.post("/users/{user_id}/active")
def toggle_active(user_id: int, user=login_required("admin")):
    if user_id == user["user_id"]:
        raise RuleError("You cannot deactivate your own account.")
    run("UPDATE users SET active = 1 - active WHERE user_id = ?", user_id)
    get_db().commit()
    return {"ok": True}
