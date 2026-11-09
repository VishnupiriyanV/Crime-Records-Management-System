import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import tokens, webhooks
from ..auth import login_required
from ..forms import need
from ..lifecycle import RuleError, log_status
from ..mongo import clean, mdb, now

router = APIRouter(prefix="/api")


class TokenBody(BaseModel):
    name: str = ""
    scope: str = "read"


class HookBody(BaseModel):
    url: str = ""
    events: list[str] = []


@router.get("/tokens")
def list_tokens(user=login_required("admin")):
    rows = clean(mdb().api_tokens.find({}, {"hash": 0}).sort("_id", -1))
    return {"items": rows, "scopes": list(tokens.SCOPES)}


@router.post("/tokens")
def make_token(body: TokenBody, user=login_required("admin")):
    name = need(body.name, "Name", 80)
    if body.scope not in tokens.SCOPES:
        raise RuleError("Pick read or write.")
    raw = tokens.create(name, body.scope, user["user_id"])
    log_status("api token", 0, None, f"Created {body.scope} token {name}", user["user_id"])
    return {"token": raw}


@router.delete("/tokens/{token_id}")
def revoke_token(token_id: str, user=login_required("admin")):
    done = mdb().api_tokens.update_one({"token_id": token_id, "active": True}, {"$set": {"active": False}})
    if not done.matched_count:
        raise HTTPException(404, "That token does not exist.")
    log_status("api token", 0, None, f"Revoked token {token_id}", user["user_id"])
    return {"ok": True}


@router.get("/webhooks")
def list_hooks(user=login_required("admin")):
    return {"items": clean(mdb().webhooks.find({}, {"secret": 0}).sort("_id", -1)), "events": webhooks.EVENTS}


@router.post("/webhooks")
def make_hook(body: HookBody, user=login_required("admin")):
    if any(e not in webhooks.EVENTS for e in body.events):
        raise RuleError("One of those events does not exist.")
    try:
        hook = webhooks.create(need(body.url, "Address", 300), body.events, user["user_id"])
    except ValueError as err:
        raise RuleError(str(err)) from None
    log_status("webhook", 0, None, f"Added {hook['url']}", user["user_id"])
    # the signing secret is shown now and never again
    return {"webhook_id": hook["webhook_id"], "secret": hook["secret"]}


@router.delete("/webhooks/{webhook_id}")
def remove_hook(webhook_id: str, user=login_required("admin")):
    done = mdb().webhooks.delete_one({"webhook_id": webhook_id})
    webhooks.forget()
    if not done.deleted_count:
        raise HTTPException(404, "That webhook does not exist.")
    log_status("webhook", 0, None, f"Removed {webhook_id}", user["user_id"])
    return {"ok": True}


@router.post("/webhooks/{webhook_id}/test")
def test_hook(webhook_id: str, user=login_required("admin")):
    hook = mdb().webhooks.find_one({"webhook_id": webhook_id})
    if hook is None:
        raise HTTPException(404, "That webhook does not exist.")
    body = json.dumps({"event": "ping", "at": now()}).encode()
    return {"status": webhooks.deliver(hook, "ping", body, tries=1)}
