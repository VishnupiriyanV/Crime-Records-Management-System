from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.requests import Request

from ..auth import current_user, hash_password, login_required, verify_password
from ..db import get_db, many, one, run
from ..forms import as_dict, as_dicts, need
from ..lifecycle import RuleError
from ..mongo import clean, mdb

router = APIRouter(prefix="/api")


class Login(BaseModel):
    email: str = ""
    password: str = ""


class Register(Login):
    name: str = ""


class Profile(BaseModel):
    name: str = ""
    address: str = ""
    phone: str = ""
    password: str = ""


def session_payload(user):
    if user is None:
        return {"user": None, "unread": 0}
    unread = mdb().notifications.count_documents({"user_id": user["user_id"], "seen": False})
    return {"user": {k: user[k] for k in ("user_id", "name", "email", "role")}, "unread": unread}


@router.get("/auth/me")
def me(request: Request):
    return session_payload(current_user(request))


@router.post("/auth/login")
def login(body: Login, request: Request):
    user = one("SELECT * FROM users WHERE email = ?", body.email.strip().lower())
    if not (user and user["active"] and verify_password(body.password, user["password"])):
        raise HTTPException(400, "Email or password is wrong.")
    request.session.clear()
    request.session["user_id"] = user["user_id"]
    request.state.user = user
    return session_payload(user)


@router.post("/auth/register")
def register(body: Register, request: Request):
    name = need(body.name, "Name", 100)
    email = need(body.email, "Email", 200).lower()
    password = need(body.password, "Password", 200)
    if "@" not in email:
        raise RuleError("Enter a valid email address.")
    if len(password) < 8:
        raise RuleError("Use at least 8 characters for the password.")
    if one("SELECT 1 FROM users WHERE email = ?", email):
        raise RuleError("An account with that email already exists.")
    user_id = run(
        "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, 'citizen')",
        name, email, hash_password(password),
    )
    run("INSERT INTO citizen (user_id) VALUES (?)", user_id)
    get_db().commit()
    request.session.clear()
    request.session["user_id"] = user_id
    request.state.user = one("SELECT * FROM users WHERE user_id = ?", user_id)
    return session_payload(request.state.user)


@router.post("/auth/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/profile")
def get_profile(user=login_required()):
    extra = None
    if user["role"] == "citizen":
        extra = as_dict(one("SELECT address, phone FROM citizen WHERE user_id = ?", user["user_id"]))
    return {"extra": extra}


@router.put("/profile")
def update_profile(body: Profile, request: Request, user=login_required()):
    uid = user["user_id"]
    name = need(body.name, "Name", 100)
    if body.password and len(body.password) < 8:
        raise RuleError("Use at least 8 characters for the password.")
    run("UPDATE users SET name = ? WHERE user_id = ?", name, uid)
    if user["role"] == "citizen":
        run(
            "UPDATE citizen SET address = ?, phone = ? WHERE user_id = ?",
            need(body.address, "Address", 300, required=False),
            need(body.phone, "Phone", 40, required=False),
            uid,
        )
    if body.password:
        run("UPDATE users SET password = ? WHERE user_id = ?", hash_password(body.password), uid)
    get_db().commit()
    del request.state.user  # reload so the new name shows up
    return session_payload(current_user(request))


@router.get("/notifications")
def notifications(user=login_required()):
    uid = user["user_id"]
    items = clean(mdb().notifications.find({"user_id": uid}).sort("_id", -1).limit(100))
    mdb().notifications.update_many({"user_id": uid, "seen": False}, {"$set": {"seen": True}})
    return {"items": items}
