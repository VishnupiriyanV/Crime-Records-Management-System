from datetime import date, datetime

from .lifecycle import RuleError


def need(value, label, limit=2000, required=True):
    """Trim and length-limit a text field; raise a user-facing error when a required one is empty."""
    text = (value or "").strip()[:limit]
    if required and not text:
        raise RuleError(f"{label} is required.")
    return text


def page_number(raw):
    try:
        return max(int(raw), 1)
    except (TypeError, ValueError):
        return 1


def as_dicts(rows):
    return [dict(r) for r in rows]


def as_dict(row):
    return dict(row) if row is not None else None


def order_by(options, key, direction, default):
    """ORDER BY text for a sort the user picked. Only keys in `options` ever reach the SQL."""
    column = options.get(key) or options[default]
    way = "ASC" if direction == "asc" else "DESC"
    return f"{column} {way}, {options[default]} DESC"


def need_date(value, label, allow_future=True):
    """A YYYY-MM-DD date, or an error the user can read."""
    try:
        day = datetime.strptime((value or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        raise RuleError(f"{label} must be a date.") from None
    if not allow_future and day > date.today():
        raise RuleError(f"{label} cannot be in the future.")
    return day.isoformat()
