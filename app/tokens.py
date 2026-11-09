"""API tokens let another system call the API without a browser session. Only a hash of each token is kept."""
import hashlib
import secrets

from .mongo import mdb, now

PREFIX = "crms_"
SCOPES = ("read", "write")


def _hash(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def create(name, scope, user_id):
    """Returns the token text, which is shown once and cannot be read back later."""
    raw = PREFIX + secrets.token_urlsafe(32)
    mdb().api_tokens.insert_one({
        "token_id": secrets.token_hex(6), "name": name, "scope": scope, "hash": _hash(raw),
        "hint": raw[-4:], "user_id": user_id, "active": True, "created_at": now(), "last_used": None,
    })
    return raw


def lookup(raw):
    token = mdb().api_tokens.find_one({"hash": _hash(raw), "active": True})
    if token and (token["last_used"] or "") < now()[:16]:
        # noting the use once a minute is enough, and spares a write on every call
        mdb().api_tokens.update_one({"token_id": token["token_id"]}, {"$set": {"last_used": now()}})
    return token
