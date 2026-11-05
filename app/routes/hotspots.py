from collections import Counter
from math import hypot

from fastapi import APIRouter

from ..auth import login_required
from ..constants import CATEGORIES, SEVERITIES, with_fir
from ..db import many
from ..forms import as_dicts

router = APIRouter(prefix="/api")

MAX_POINTS = 3000
CELL_DIGITS = 2  # two decimals is a cell of roughly one kilometre


def _nearest_station(lat, lng, stations):
    best = None
    for s in stations:
        if s["latitude"] is None:
            continue
        gap = hypot(s["latitude"] - lat, s["longitude"] - lng)
        if best is None or gap < best[0]:
            best = (gap, s["name"])
    return best[1] if best else None


@router.get("/map")
def map_data(category: str = "", severity: str = "", user=login_required("officer", "admin")):
    where, args = ["c.latitude IS NOT NULL", "c.longitude IS NOT NULL"], []
    if category in CATEGORIES:
        where.append("c.category = ?")
        args.append(category)
    if severity in SEVERITIES:
        where.append("c.severity = ?")
        args.append(severity)
    rows = many(
        "SELECT c.complaint_id, c.date_filed, c.title, c.category, c.severity, c.status, c.latitude, c.longitude"
        " FROM complaint c WHERE " + " AND ".join(where) + " ORDER BY c.complaint_id DESC LIMIT ?",
        *args, MAX_POINTS,
    )
    stations = as_dicts(many("SELECT station_id, name, latitude, longitude FROM police_station ORDER BY name"))

    cells = {}
    for r in rows:
        key = (round(r["latitude"], CELL_DIGITS), round(r["longitude"], CELL_DIGITS))
        cells.setdefault(key, []).append(r)
    hotspots = []
    for (lat, lng), group in cells.items():
        top = Counter(r["category"] for r in group).most_common(1)[0][0]
        hotspots.append({
            "latitude": lat, "longitude": lng, "total": len(group), "top_category": top,
            "high": sum(1 for r in group if r["severity"] == "High"),
            "station": _nearest_station(lat, lng, stations),
        })
    hotspots.sort(key=lambda h: (-h["total"], -h["high"]))

    return {
        "points": [with_fir(r) for r in rows], "hotspots": hotspots[:12], "stations": stations,
        "categories": CATEGORIES, "severities": SEVERITIES,
    }
