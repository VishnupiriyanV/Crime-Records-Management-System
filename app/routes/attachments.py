import re
import secrets
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.requests import Request

from ..auth import is_staff, login_required
from ..db import one
from ..lifecycle import RuleError, is_closed
from ..mongo import clean, mdb, now

router = APIRouter(prefix="/api")

MAX_BYTES = 5 * 1024 * 1024
MAX_PER_COMPLAINT = 5
ALLOWED = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif",
    ".webp": "image/webp", ".pdf": "application/pdf", ".txt": "text/plain",
}


def _owned_complaint(complaint_id, user):
    """The complaint, if this user may see it (404 otherwise, so ids do not leak)."""
    c = one(
        "SELECT c.complaint_id, c.status, u.user_id AS owner_id FROM complaint c"
        " JOIN citizen ct ON ct.citizen_id = c.citizen_id JOIN users u ON u.user_id = ct.user_id"
        " WHERE c.complaint_id = ?",
        complaint_id,
    )
    if c is None or (not is_staff(user) and c["owner_id"] != user["user_id"]):
        raise HTTPException(404, "That complaint does not exist.")
    return c


def list_for(complaint_id):
    return clean(mdb().attachments.find({"complaint_id": complaint_id}, {"stored": 0}).sort("_id", 1))


@router.post("/complaints/{complaint_id}/attachments")
async def upload(complaint_id: int, file: UploadFile, request: Request, user=login_required("citizen")):
    c = _owned_complaint(complaint_id, user)
    case = one('SELECT status FROM crime_case WHERE complaint_id = ?', complaint_id)
    if c["status"] == "Rejected" or (case and is_closed(case["status"])):
        raise RuleError("This complaint is closed to new files.")
    if mdb().attachments.count_documents({"complaint_id": complaint_id}) >= MAX_PER_COMPLAINT:
        raise RuleError(f"A complaint can hold {MAX_PER_COMPLAINT} files at most.")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise RuleError("Upload an image, a PDF or a text file.")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise RuleError("Files must be 5 MB or smaller.")
    if not data:
        raise RuleError("That file is empty.")

    attachment_id = secrets.token_hex(8)
    folder = request.app.state.upload_dir
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{attachment_id}{ext}").write_bytes(data)
    name = re.sub(r"[^\w.\- ]", "_", Path(file.filename).name)[:120]
    mdb().attachments.insert_one({
        "attachment_id": attachment_id, "complaint_id": complaint_id, "filename": name,
        "content_type": ALLOWED[ext], "size": len(data), "stored": f"{attachment_id}{ext}",
        "uploaded_at": now(),
    })
    return {"attachment_id": attachment_id}


@router.get("/attachments/{attachment_id}")
def download(attachment_id: str, request: Request, user=login_required()):
    doc = mdb().attachments.find_one({"attachment_id": attachment_id})
    if doc is None:
        raise HTTPException(404, "That file does not exist.")
    _owned_complaint(doc["complaint_id"], user)
    path = request.app.state.upload_dir / doc["stored"]
    if not path.is_file():
        raise HTTPException(404, "That file is no longer stored.")
    return FileResponse(
        path, media_type=doc["content_type"], filename=doc["filename"],
        headers={"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox"},
    )
