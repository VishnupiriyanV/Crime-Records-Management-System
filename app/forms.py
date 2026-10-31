from flask import request

from .lifecycle import RuleError


def field(name, label, limit=2000, required=True):
    value = request.form.get(name, "").strip()[:limit]
    if required and not value:
        raise RuleError(f"{label} is required.")
    return value


def int_field(name):
    try:
        value = int(request.form.get(name, ""))
    except ValueError:
        return None
    return value if value > 0 else None
