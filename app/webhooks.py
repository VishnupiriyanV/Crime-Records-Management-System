"""Tell other systems when something changes. Each call is signed so the receiver can check it came from here."""
import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
import threading
import time
import urllib.request
from urllib.parse import urlparse

from .constants import fir_number
from .db import one
from .main_config import production
from .mongo import mdb, now

EVENTS = [
    "complaint.filed", "complaint.status_changed", "case.opened", "case.status_changed", "case.assigned",
]
ASYNC = True  # the tests switch this off so a delivery has finished when the call returns
_cache = {"at": 0, "hooks": []}


def check_url(url):
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("Give a full web address starting with https://")
    if production() and parts.scheme != "https":
        raise ValueError("Use an https:// address.")
    if production():
        # an address that only this server can reach would let a webhook probe the host's own network
        try:
            found = {item[4][0] for item in socket.getaddrinfo(parts.hostname, parts.port or 443)}
        except OSError:
            raise ValueError("That address could not be found.") from None
        for text in found:
            ip = ipaddress.ip_address(text)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError("Use an address that is reachable from the internet.")
    return url


def create(url, events, user_id):
    hook = {
        "webhook_id": secrets.token_hex(6), "url": check_url(url), "events": events,
        "secret": secrets.token_hex(24), "active": True, "created_by": user_id,
        "created_at": now(), "last_status": None, "last_at": None,
    }
    mdb().webhooks.insert_one(hook)
    forget()
    return hook


def forget():
    _cache["at"] = 0


def _active():
    # webhooks rarely change, so asking the database on every status change would only add delay
    if time.time() - _cache["at"] > 30:
        _cache["hooks"] = list(mdb().webhooks.find({"active": True}))
        _cache["at"] = time.time()
    return _cache["hooks"]


def _describe(entity, entity_id):
    if entity == "complaint":
        row = one("SELECT complaint_id, date_filed, category, severity FROM complaint WHERE complaint_id = ?", entity_id)
    else:
        row = one(
            "SELECT c.complaint_id, c.date_filed, c.category, c.severity FROM crime_case cs"
            " JOIN complaint c ON c.complaint_id = cs.complaint_id WHERE cs.case_id = ?", entity_id,
        )
    if row is None:
        return {}
    return {"fir": fir_number(row["complaint_id"], row["date_filed"]), "category": row["category"], "severity": row["severity"]}


def event_for(entity, old):
    if entity == "complaint":
        return "complaint.filed" if old is None else "complaint.status_changed"
    if entity == "case":
        return "case.opened" if old is None else "case.status_changed"
    if entity == "case assignment":
        return "case.assigned"
    return None


def emit(entity, entity_id, old, new):
    """Called for every logged change; it never lets a webhook problem break the action itself."""
    try:
        event = event_for(entity, old)
        hooks = [h for h in _active() if event and (not h["events"] or event in h["events"])]
        if not hooks:
            return
        # only ids, status and category go out; the receiver asks the API for anything more
        body = json.dumps({
            "event": event, "at": now(), "id": entity_id, "from": old, "to": new, **_describe(entity, entity_id),
        }).encode()
        for hook in hooks:
            if ASYNC:
                threading.Thread(target=deliver, args=(hook, event, body), daemon=True).start()
            else:
                deliver(hook, event, body)
    except Exception:
        pass


def deliver(hook, event, body, tries=3):
    signature = hmac.new(hook["secret"].encode(), body, hashlib.sha256).hexdigest()
    request = urllib.request.Request(hook["url"], data=body, method="POST", headers={
        "Content-Type": "application/json", "User-Agent": "CRMS-webhook",
        "X-CRMS-Event": event, "X-CRMS-Delivery": secrets.token_hex(8), "X-CRMS-Signature": f"sha256={signature}",
    })
    status = "failed"
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=5) as reply:
                status = str(reply.status)
            break
        except Exception as err:
            status = f"failed: {str(err)[:80]}"
            if attempt < tries - 1:
                time.sleep(2 ** attempt)
    mdb().webhooks.update_one({"webhook_id": hook["webhook_id"]}, {"$set": {"last_status": status, "last_at": now()}})
    return status
