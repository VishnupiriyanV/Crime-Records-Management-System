"""Slow down password guessing: five wrong tries for one email from one address locks it for 15 minutes."""
import time

from fastapi import HTTPException

from .mongo import mdb

LIMIT = 5
WINDOW = 15 * 60


def _key(email, ip):
    return f"{email.strip().lower()}|{ip}"


def check(email, ip):
    now = time.time()
    failures = mdb().login_failures
    failures.delete_many({"at": {"$lt": now - WINDOW}})
    recent = list(failures.find({"key": _key(email, ip)}).sort("at", 1))
    if len(recent) >= LIMIT:
        wait = max(1, int((recent[0]["at"] + WINDOW - now) // 60) + 1)
        raise HTTPException(429, f"Too many failed attempts. Try again in {wait} minute{'s' if wait != 1 else ''}.")


def fail(email, ip):
    mdb().login_failures.insert_one({"key": _key(email, ip), "at": time.time()})


def clear(email, ip):
    mdb().login_failures.delete_many({"key": _key(email, ip)})
