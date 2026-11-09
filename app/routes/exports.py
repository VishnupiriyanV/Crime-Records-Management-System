from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..auth import login_required
from ..constants import with_fir
from ..db import many
from ..exports import case_pdf, to_csv
from ..timeline import case_timeline
from .. import ledger
from ..mongo import clean, mdb
from .cases import CASE_SELECT, SORTS as CASE_SORTS, case_filter, load_case
from .complaints import LIST_SELECT as COMPLAINT_SELECT, SORTS as COMPLAINT_SORTS, complaint_filter
from .criminals import LIST_SELECT as CRIMINAL_SELECT, SORTS as CRIMINAL_SORTS, criminal_filter
from ..fir_export import one_fir, page_of_firs
from ..forms import need_date, order_by, page_number

router = APIRouter(prefix="/api/export")


def _csv(name, text):
    return Response(
        text.encode("utf-8-sig"),  # the BOM lets Excel read accents correctly
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}.csv"'},
    )


@router.get("/complaints.csv")
def complaints(status: str = "", q: str = "", category: str = "", severity: str = "", sort: str = "no",
               dir: str = "desc", user=login_required()):
    clause, args = complaint_filter(user, status, q, category, severity)
    rows = many(f"{COMPLAINT_SELECT} {clause} ORDER BY {order_by(COMPLAINT_SORTS, sort, dir, 'no')}", *args)
    rows = [with_fir(r) for r in rows]
    columns = [
        ("FIR no.", "fir_no"), ("Title", "title"), ("Category", "category"), ("Severity", "severity"), ("Filed by", "citizen_name"), ("Location", "location"),
        ("Incident date", "incident_date"), ("Filed on", "date_filed"), ("Status", "status"), ("Case status", "case_status"),
    ]
    return _csv("complaints", to_csv(columns, rows))


@router.get("/cases.csv")
def cases(status: str = "", q: str = "", mine: str = "", category: str = "", sort: str = "no", dir: str = "desc",
          user=login_required("officer", "admin")):
    clause, args = case_filter(status, q, mine, user, category)
    rows = [with_fir(r) for r in many(f"{CASE_SELECT} {clause} ORDER BY {order_by(CASE_SORTS, sort, dir, 'no')}", *args)]
    columns = [
        ("Case", "case_id"), ("FIR no.", "fir_no"), ("Category", "category"), ("Complaint", "title"), ("Filed by", "citizen_name"), ("Station", "station"),
        ("Officer", "officer_name"), ("Opened", "date_opened"), ("Status", "status"),
    ]
    return _csv("cases", to_csv(columns, rows))


@router.get("/criminals.csv")
def criminals(q: str = "", wanted: str = "", sort: str = "name", dir: str = "asc",
              user=login_required("officer", "admin")):
    clause, args = criminal_filter(q, wanted)
    rows = many(f"{CRIMINAL_SELECT} {clause} ORDER BY {order_by(CRIMINAL_SORTS, sort, dir, 'name')}", *args)
    columns = [("Name", "name"), ("Age", "age"), ("Wanted", "wanted"), ("Cases", "cases"), ("History", "crime_history")]
    return _csv("criminals", to_csv(columns, rows))


@router.get("/cases/{case_id}.pdf")
def case_file(case_id: int, user=login_required("officer", "admin")):
    case = load_case(case_id)
    evidence = clean(mdb().evidence.find({"case_id": case_id}).sort("evidence_no", 1))
    linked = many(
        "SELECT cc.role, cr.name, cr.wanted FROM case_criminal cc JOIN criminal cr ON cr.criminal_id = cc.criminal_id"
        " WHERE cc.case_id = ? ORDER BY cr.name",
        case_id,
    )
    reports = many(
        "SELECT r.*, u.name AS author FROM report r LEFT JOIN officer o ON o.officer_id = r.officer_id"
        " LEFT JOIN users u ON u.user_id = o.user_id WHERE r.case_id = ? ORDER BY r.report_id",
        case_id,
    )
    extra = {
        "statements": clean(mdb().statements.find({"case_id": case_id}).sort("no", 1)),
        "arrests": clean(mdb().arrests.find({"case_id": case_id}).sort("no", 1)),
        "court_dates": clean(mdb().court_dates.find({"case_id": case_id}).sort("date", 1)),
        "chargesheet": (clean(mdb().chargesheets.find({"case_id": case_id})) or [None])[0],
    }
    events = case_timeline(case, reports)
    ledger.ensure(case, events)
    integrity = ledger.verify(case["complaint_id"], events)
    timeline = ledger.annotate(case["complaint_id"], events)
    pdf = case_pdf(with_fir(case), evidence, linked, reports, timeline, extra, integrity, user["name"])
    return Response(
        pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="case-{case_id}.pdf"'},
    )


@router.get("/fir/{complaint_id}")
def fir_json(complaint_id: int, user=login_required("officer", "admin")):
    found = one_fir(complaint_id)
    if found is None:
        raise HTTPException(404, "That complaint does not exist.")
    return found


@router.get("/firs")
def firs_json(since: str = "", page: str = "1", user=login_required("officer", "admin")):
    """Every complaint with its case, newest filings last; `since` is a filing date, YYYY-MM-DD."""
    return page_of_firs(need_date(since, "Since") if since else "", page_number(page))
