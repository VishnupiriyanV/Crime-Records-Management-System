import hashlib
import secrets

from fastapi import Depends, HTTPException
from starlette.requests import Request

from . import tokens
from .db import one


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=2**14, r=8, p=1).hex()
    return f"{salt}${digest}"


def verify_password(password, stored):
    salt, _, digest = stored.partition("$")
    given = hashlib.scrypt(password.encode(), salt=salt.encode(), n=2**14, r=8, p=1).hex()
    return secrets.compare_digest(given, digest)


# what a token may never reach, whatever its scope: managing people, tokens and webhooks
TOKEN_BLOCKED = ("/api/tokens", "/api/webhooks", "/api/users", "/api/auth", "/api/profile")


def token_user(request):
    """The account behind an API token; the token acts as the admin who made it, limited by its scope."""
    token = tokens.lookup(request.headers["authorization"][7:].strip())
    if token is None:
        raise HTTPException(401, "That API token is not valid.")
    if request.url.path.startswith(TOKEN_BLOCKED):
        raise HTTPException(403, "An API token cannot do that.")
    if token["scope"] == "read" and request.method not in ("GET", "HEAD"):
        raise HTTPException(403, "This API token is read-only.")
    owner = one("SELECT user_id, name, email, role, active, email_alerts FROM users WHERE user_id = ?", token["user_id"])
    if not owner or not owner["active"]:
        raise HTTPException(401, "That API token is not valid.")
    return owner


def has_bearer(request):
    return request.headers.get("authorization", "")[:7].lower() == "bearer "


def current_user(request: Request):
    if hasattr(request.state, "user"):
        return request.state.user
    user = None
    if has_bearer(request):
        user = token_user(request)
    else:
        user_id = request.session.get("user_id")
        if user_id:
            row = one("SELECT user_id, name, email, role, active, email_alerts FROM users WHERE user_id = ?", user_id)
            if row and row["active"]:
                user = row
            else:
                request.session.clear()
    request.state.user = user
    return user


async def check_csrf(request: Request):
    """Browsers cannot add these headers to a cross-site request, so one of them proves the call came from us or from a client with a token.
    A bearer header alone does not sign anyone in; current_user still checks the token."""
    if request.method in ("GET", "HEAD", "OPTIONS") or has_bearer(request):
        return
    if request.headers.get("x-requested-with") != "crms":
        raise HTTPException(400, "Missing request header.")


def login_required(*roles):
    """Dependency that needs a signed-in user, optionally limited to the given roles."""
    def dependency(request: Request):
        user = current_user(request)
        if user is None:
            raise HTTPException(401, "Sign in to continue.")
        if roles and user["role"] not in roles:
            raise HTTPException(403)
        return user
    return Depends(dependency)


def is_staff(user):
    return user is not None and user["role"] in ("officer", "admin")
