from fastapi import APIRouter
from fastapi.responses import Response

from ..auth import login_required
from ..db import many
from ..exports import case_pdf, to_csv
from ..timeline import case_timeline
from ..mongo import clean, mdb
from .cases import CASE_SELECT, SORTS as CASE_SORTS, case_filter, load_case
from .complaints import LIST_SELECT as COMPLAINT_SELECT, SORTS as COMPLAINT_SORTS, complaint_filter
from .criminals import LIST_SELECT as CRIMINAL_SELECT, SORTS as CRIMINAL_SORTS, criminal_filter
from ..forms import order_by

router = APIRouter(prefix="/api/export")


def _csv(name, text):
    return Response(
        text.encode("utf-8-sig"),  # the BOM lets Excel read accents correctly
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}.csv"'},
    )


@router.get("/complaints.csv")
def complaints(status: str = "", q: str = "", sort: str = "no", dir: str = "desc", user=login_required()):
    clause, args = complaint_filter(user, status, q)
    rows = many(f"{COMPLAINT_SELECT} {clause} ORDER BY {order_by(COMPLAINT_SORTS, sort, dir, 'no')}", *args)
    columns = [
        ("No.", "complaint_id"), ("Title", "title"), ("Filed by", "citizen_name"), ("Location", "location"),
        ("Incident date", "incident_date"), ("Filed on", "date_filed"), ("Status", "status"), ("Case status", "case_status"),
    ]
    return _csv("complaints", to_csv(columns, rows))


@router.get("/cases.csv")
def cases(status: str = "", q: str = "", mine: str = "", sort: str = "no", dir: str = "desc",
          user=login_required("officer", "admin")):
    clause, args = case_filter(status, q, mine, user)
    rows = many(f"{CASE_SELECT} {clause} ORDER BY {order_by(CASE_SORTS, sort, dir, 'no')}", *args)
    columns = [
        ("Case", "case_id"), ("Complaint", "title"), ("Filed by", "citizen_name"), ("Station", "station"),
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
    pdf = case_pdf(case, evidence, linked, reports, case_timeline(case, reports))
    return Response(
        pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="case-{case_id}.pdf"'},
    )
