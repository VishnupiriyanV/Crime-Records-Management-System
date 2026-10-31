import hashlib
import secrets

from fastapi import Depends, HTTPException
from starlette.requests import Request

from .db import one


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=2**14, r=8, p=1).hex()
    return f"{salt}${digest}"


def verify_password(password, stored):
    salt, _, digest = stored.partition("$")
    given = hashlib.scrypt(password.encode(), salt=salt.encode(), n=2**14, r=8, p=1).hex()
    return secrets.compare_digest(given, digest)


def current_user(request: Request):
    if hasattr(request.state, "user"):
        return request.state.user
    user = None
    user_id = request.session.get("user_id")
    if user_id:
        row = one("SELECT user_id, name, email, role, active FROM users WHERE user_id = ?", user_id)
        if row and row["active"]:
            user = row
        else:
            request.session.clear()
    request.state.user = user
    return user


async def check_csrf(request: Request):
    """Browsers cannot add this header to a cross-site request, so its presence proves the call came from our page."""
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get("x-requested-with") != "crms":
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
