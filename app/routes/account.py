import hashlib
import secrets
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.requests import Request

from ..auth import current_user, hash_password, login_required, verify_password
from ..db import get_db, many, one, run
from ..forms import as_dict, as_dicts, need
from .. import throttle
from ..lifecycle import RuleError, log_status
from ..main_config import production
from .. import mailer
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
    current_password: str = ""
    email_alerts: bool | None = None


class Forgot(BaseModel):
    email: str = ""


class Reset(BaseModel):
    token: str = ""
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
    email = body.email.strip().lower()
    ip = request.client.host if request.client else "unknown"
    throttle.check(email, ip)
    user = one("SELECT * FROM users WHERE email = ?", email)
    if not (user and user["active"] and verify_password(body.password, user["password"])):
        throttle.fail(email, ip)
        raise HTTPException(400, "Email or password is wrong.")
    throttle.clear(email, ip)
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


RESET_SECONDS = 3600


def _fingerprint(token):
    return hashlib.sha256(token.encode()).hexdigest()


@router.post("/auth/forgot")
def forgot(body: Forgot, request: Request):
    """Mail a reset link. The answer is the same whether or not the address has an account."""
    reply = {"ok": True}
    asked = body.email.strip().lower()
    mailer.log.info("Password reset asked for %s (e-mail set up: %s, CRMS_BASE_URL set: %s).", asked, mailer.configured(), bool(mailer.base_url()))
    user = one("SELECT user_id, name, email FROM users WHERE email = ? AND active = 1", asked)
    if user is None:
        mailer.log.info("Password reset for %s: no active account has that address, so nothing is sent.", asked)
        return reply
    if mdb().password_resets.count_documents({"user_id": user["user_id"], "created": {"$gt": time.time() - RESET_SECONDS}}) >= 3:
        mailer.log.warning("Password reset for %s skipped: three links were already asked for in the last hour.", asked)
        return reply  # three a hour is plenty; more is someone else's mailbox being flooded
    # the link must point at our own address, never at whatever Host header the request came with
    base = mailer.base_url() or ("" if production() else str(request.base_url).rstrip("/"))
    if not base:
        mailer.log.warning("Password reset asked for %s but CRMS_BASE_URL is not set, so no link can be built.", user["email"])
        return reply
    token = secrets.token_urlsafe(32)
    fingerprint = _fingerprint(token)
    mdb().password_resets.insert_one({
        "hash": fingerprint, "user_id": user["user_id"], "created": time.time(), "expires": time.time() + RESET_SECONDS,
    })
    handed = mailer.send(
        user["email"], "CRMS: reset your password",
        f"Hello {user['name']},\n\nSomeone asked to reset the password for your CRMS account. "
        f"Open this link within an hour to choose a new one:\n\n{base}/reset?token={token}\n\n"
        "If this was not you, ignore this e-mail; your password has not changed.",
        # a link that never left the server must not use up one of the three an hour, or an outage would lock people out
        on_fail=lambda: mdb().password_resets.delete_one({"hash": fingerprint}),
    )
    mailer.log.info("Password reset link for %s %s.", user["email"], "queued for sending" if handed else "was made but could not be sent (see the line above)")
    return reply


@router.post("/auth/reset")
def reset(body: Reset):
    if len(body.password) < 8:
        raise RuleError("Use at least 8 characters for the password.")
    row = mdb().password_resets.find_one({"hash": _fingerprint(body.token)}) if body.token else None
    if row is None or row["expires"] < time.time():
        raise RuleError("This reset link has expired or was already used. Ask for a new one.")
    run("UPDATE users SET password = ? WHERE user_id = ?", hash_password(body.password), row["user_id"])
    get_db().commit()
    mdb().password_resets.delete_many({"user_id": row["user_id"]})
    log_status("user", row["user_id"], None, "Password reset by e-mail link", row["user_id"])
    return {"ok": True}


@router.post("/auth/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/profile")
def get_profile(user=login_required()):
    extra = None
    if user["role"] == "citizen":
        extra = as_dict(one("SELECT address, phone FROM citizen WHERE user_id = ?", user["user_id"]))
    return {"extra": extra, "email_alerts": bool(user["email_alerts"]), "email_possible": mailer.alerts_enabled()}


@router.put("/profile")
def update_profile(body: Profile, request: Request, user=login_required()):
    uid = user["user_id"]
    name = need(body.name, "Name", 100)
    if body.password:
        if len(body.password) < 8:
            raise RuleError("Use at least 8 characters for the password.")
        stored = one("SELECT password FROM users WHERE user_id = ?", uid)["password"]
        if not verify_password(body.current_password, stored):
            raise RuleError("Enter your current password to set a new one.")
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
    if body.email_alerts is not None:
        run("UPDATE users SET email_alerts = ? WHERE user_id = ?", 1 if body.email_alerts else 0, uid)
    get_db().commit()
    del request.state.user  # reload so the new name shows up
    return session_payload(current_user(request))


@router.get("/notifications")
def notifications(user=login_required()):
    uid = user["user_id"]
    items = clean(mdb().notifications.find({"user_id": uid}).sort("_id", -1).limit(100))
    mdb().notifications.update_many({"user_id": uid, "seen": False}, {"$set": {"seen": True}})
    return {"items": items}

