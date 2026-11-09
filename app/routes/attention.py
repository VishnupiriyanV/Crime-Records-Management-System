from datetime import date

from fastapi import APIRouter

from ..auth import login_required
from ..constants import fir_number
from ..db import many
from ..overdue import OPEN, case_flags, complaint_flags, limit

router = APIRouter(prefix="/api")

KINDS = ["unreviewed", "unassigned", "stale", "hearing"]
SHOWN = 12


@router.get("/attention")
def attention(user=login_required("officer", "admin")):
    """Everything that has waited too long, counted by kind with the longest waits listed."""
    today = date.today()
    items = []

    # the shortest wait any flag uses, so the database only returns rows that could possibly qualify
    cutoff = date.fromordinal(today.toordinal() - 1).isoformat()
    for r in many(
        "SELECT complaint_id, title, severity, date_filed, status FROM complaint"
        " WHERE status = 'Filed' AND date_filed <= ? ORDER BY date_filed LIMIT 300", cutoff,
    ):
        for flag in complaint_flags([r], today).get(r["complaint_id"], []):
            items.append({**flag, "title": r["title"], "fir": fir_number(r["complaint_id"], r["date_filed"]),
                          "link": f"/complaints/{r['complaint_id']}"})

    # an officer sees their own cases; an admin sees them all
    mine, args = ("", []) if user["role"] == "admin" else ("AND cs.officer_id = (SELECT officer_id FROM officer WHERE user_id = ?)", [user["user_id"]])
    rows = many(
        "SELECT cs.case_id, cs.status, cs.officer_id, cs.date_opened, c.complaint_id, c.title, c.severity, c.date_filed"
        f" FROM crime_case cs JOIN complaint c ON c.complaint_id = cs.complaint_id"
        f" WHERE cs.status IN ({', '.join('?' * len(OPEN))}) {mine} ORDER BY cs.date_opened LIMIT 500",
        *OPEN, *args,
    )
    by_case = {r["case_id"]: r for r in rows}
    for case_id, flags in case_flags(rows, today).items():
        r = by_case[case_id]
        for flag in flags:
            items.append({**flag, "title": r["title"], "fir": fir_number(r["complaint_id"], r["date_filed"]), "link": f"/cases/{case_id}"})

    counts = {k: sum(1 for i in items if i["kind"] == k) for k in KINDS}
    items.sort(key=lambda i: -i["days"])
    return {"counts": counts, "items": items[:SHOWN], "limits": {k: limit(k, "Medium") for k in ("unreviewed", "unassigned", "stale")}}
