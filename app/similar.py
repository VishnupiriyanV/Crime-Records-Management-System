"""Finds complaints that may describe the same incident, from the wording, the place and the date."""
import math
import re
from datetime import datetime

STOP = {
    "the", "and", "was", "were", "has", "have", "had", "for", "with", "that", "this", "from", "into", "near", "when",
    "while", "then", "they", "them", "his", "her", "our", "but", "not", "are", "been", "found", "some", "someone",
}
FLOOR = 0.5


def words(text):
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 2 and w not in STOP}


def overlap(a, b):
    both = a | b
    return len(a & b) / len(both) if both else 0


def metres(lat1, lng1, lat2, lng2):
    a = math.sin(math.radians(lat2 - lat1) / 2) ** 2 + (
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    )
    return 6371000 * 2 * math.asin(math.sqrt(a))


def days_apart(a, b):
    try:
        return abs((datetime.strptime(str(a)[:10], "%Y-%m-%d") - datetime.strptime(str(b)[:10], "%Y-%m-%d")).days)
    except ValueError:
        return None


def compare(a, b):
    """A score from 0 to 1 and the reasons behind it, for two complaints given as dicts."""
    reasons = []
    text = overlap(words(f"{a['title']} {a['description']}"), words(f"{b['title']} {b['description']}"))
    if text >= 0.3:
        reasons.append("similar wording")

    place = 0
    if None not in (a.get("latitude"), a.get("longitude"), b.get("latitude"), b.get("longitude")):
        away = metres(a["latitude"], a["longitude"], b["latitude"], b["longitude"])
        place = 1 if away <= 300 else 0.5 if away <= 1000 else 0
    else:
        place = overlap(words(a["location"]), words(b["location"]))
    if place >= 0.5:
        reasons.append("same place")

    gap = days_apart(a["incident_date"], b["incident_date"])
    when = 0 if gap is None else 1 if gap <= 1 else 0.6 if gap <= 7 else 0.2 if gap <= 30 else 0
    if when >= 0.6:
        reasons.append("within 1 day" if gap <= 1 else f"within {gap} days")

    same = a["category"] == b["category"]
    if same:
        reasons.append("same category")
    score = 0.45 * text + 0.25 * place + 0.2 * when + 0.1 * same
    return score, reasons


def find(draft, candidates, limit=5):
    """The candidates that look like the draft, closest first."""
    found = []
    for c in candidates:
        score, reasons = compare(draft, c)
        # a shared category and a nearby date alone are not enough; the text or the place must agree too
        if score >= FLOOR and ("similar wording" in reasons or "same place" in reasons):
            found.append({**c, "score": round(score, 2), "reasons": reasons})
    return sorted(found, key=lambda x: -x["score"])[:limit]
