"""Numbers for the charts on the dashboard and the reports page."""
from datetime import date

from .db import many


def _last_months(count):
    today = date.today()
    year, month = today.year, today.month
    months = []
    for _ in range(count):
        months.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return months[::-1]


def monthly_complaints(count=12):
    """Complaints filed per month for the last `count` months, oldest first, empty months as zero."""
    months = _last_months(count)
    totals = dict.fromkeys(months, 0)
    # the date columns are plain text, so grouping by month is easiest done here
    for row in many("SELECT date_filed FROM complaint WHERE date_filed >= ?", months[0] + "-01"):
        key = str(row["date_filed"])[:7]
        if key in totals:
            totals[key] += 1
    return [{"month": m, "total": totals[m]} for m in months]


def by_category():
    return [dict(r) for r in many(
        "SELECT category, COUNT(*) AS total FROM complaint GROUP BY category ORDER BY total DESC, category"
    )]


def by_severity():
    order = {"High": 0, "Medium": 1, "Low": 2}
    rows = [dict(r) for r in many("SELECT severity, COUNT(*) AS total FROM complaint GROUP BY severity")]
    return sorted(rows, key=lambda r: order.get(r["severity"], 9))
