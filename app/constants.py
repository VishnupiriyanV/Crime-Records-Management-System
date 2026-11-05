"""Fixed lists and small helpers shared by several routes."""
import re

CATEGORIES = [
    "Theft", "Burglary", "Assault", "Fraud", "Cybercrime", "Vandalism",
    "Missing person", "Domestic violence", "Traffic", "Other",
]
SEVERITIES = ["Low", "Medium", "High"]

# what a person can be to a case, and which of those can be arrested or charged
PERSON_ROLES = ("suspect", "accused", "witness", "victim")
CHARGEABLE = ("suspect", "accused")

CUSTODY_ACTIONS = ("stored", "transferred", "sent for analysis", "returned from analysis", "released", "destroyed")

_FIR = re.compile(r"^FIR/(\d{4})/(\d+)$", re.IGNORECASE)


def fir_number(complaint_id, date_filed):
    """The reference printed on paperwork: FIR/<year filed>/<serial>."""
    return f"FIR/{str(date_filed)[:4]}/{complaint_id:04d}"


def with_fir(row):
    """A copy of a complaint row (as a dict) with its fir_no filled in."""
    out = dict(row)
    out["fir_no"] = fir_number(out["complaint_id"], out["date_filed"])
    return out


def parse_fir(text):
    """The complaint id inside a typed FIR number, or None when the text is something else."""
    match = _FIR.match(text.strip())
    return int(match.group(2)) if match else None
