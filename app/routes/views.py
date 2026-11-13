"""Saved filters: a name for a way of looking at the cases or complaints list, kept per person."""
import secrets

from fastapi import APIRouter
from pydantic import BaseModel

from ..auth import login_required
from ..forms import need
from ..lifecycle import RuleError
from ..mongo import clean, mdb, now

router = APIRouter(prefix="/api")

PAGES = ("cases", "complaints")
MAX_PER_PAGE = 20


class NewView(BaseModel):
    page: str = ""
    name: str = ""
    query: str = ""


@router.get("/views")
def list_views(page: str = "", user=login_required()):
    find = {"user_id": user["user_id"]}
    if page in PAGES:
        find["page"] = page
    return {"items": clean(mdb().saved_views.find(find).sort("_id", 1))}


@router.post("/views")
def save_view(body: NewView, user=login_required()):
    if body.page not in PAGES:
        raise RuleError("Pick a list to save a view of.")
    name = need(body.name, "Name", 60)
    query = body.query.strip().lstrip("?")
    if len(query) > 500:
        raise RuleError("That filter is too long to save.")
    mine = {"user_id": user["user_id"], "page": body.page}
    if mdb().saved_views.count_documents(mine) >= MAX_PER_PAGE:
        raise RuleError(f"You can keep {MAX_PER_PAGE} saved views for a list. Delete one first.")
    mdb().saved_views.delete_many({**mine, "name": name})  # saving under a name again replaces it
    view_id = secrets.token_hex(6)
    mdb().saved_views.insert_one({**mine, "view_id": view_id, "name": name, "query": query, "created_at": now()})
    return {"view_id": view_id}


@router.delete("/views/{view_id}")
def delete_view(view_id: str, user=login_required()):
    mdb().saved_views.delete_one({"view_id": view_id, "user_id": user["user_id"]})
    return {"ok": True}
