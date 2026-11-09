"""Turns a spoken or pasted account of an incident into the fields of a complaint.

It only looks for plain English words. Anything it cannot find comes back empty, so the form keeps what the person typed.
"""
import re
from datetime import date, timedelta

from .constants import CATEGORIES

# words that point at a category; the one with the most hits wins. Tamil and Hindi words are matched inside the text,
# since their endings change a word and a whole-word match would miss most of them.
WORDS = {
    "Theft": ["stole", "stolen", "theft", "snatch", "pickpocket", "robbed", "robbery", "missing phone", "lost my wallet",
              "திருட்டு", "திருடி", "திருடப்", "வழிப்பறி", "பறித்", "चोरी", "चुरा", "चोर", "छीन"],
    "Burglary": ["burglary", "break-in", "broke into", "broken into", "house was entered", "lock was broken",
                 "வீடு புகுந்து", "பூட்டை உடைத்து", "सेंध", "घर में घुस", "ताला तोड़"],
    "Assault": ["attacked", "assault", "beat", "beaten", "punched", "slapped", "stabbed", "threatened", "fight",
                "தாக்கி", "தாக்குதல்", "அடித்து", "மிரட்டி", "मारपीट", "हमला", "पीटा", "मारा", "धमकी"],
    "Fraud": ["fraud", "cheated", "scam", "duped", "fake", "forged", "money was taken",
              "மோசடி", "ஏமாற்றி", "ஏமாற்ற", "धोखा", "ठगी", "ठगा", "जालसाजी"],
    "Cybercrime": ["hacked", "phishing", "otp", "online", "cyber", "upi", "social media", "password",
                  "இணையம்", "ஹேக்", "சைபர்", "ஓடிபி", "ஆன்லைன்", "हैक", "साइबर", "ओटीपी", "ऑनलाइन", "फिशिंग"],
    "Vandalism": ["vandal", "damaged", "smashed", "scratched", "set fire", "graffiti",
                  "சேதப்படுத்", "உடைத்து", "தீ வைத்", "तोड़फोड़", "तोड़ दिया", "नुकसान", "आग लगा"],
    "Missing person": ["missing person", "went missing", "has not returned", "disappeared", "kidnap",
                       "காணவில்லை", "காணாமல்", "கடத்த", "लापता", "गुमशुदा", "गुम हो", "अपहरण"],
    "Domestic violence": ["domestic", "husband beat", "in-laws", "dowry", "my husband hits",
                          "குடும்ப வன்முறை", "வரதட்சணை", "கணவர் அடித்", "घरेलू हिंसा", "दहेज", "पति मारता"],
    "Traffic": ["accident", "hit and run", "rash driving", "collision", "drunk driving", "crashed",
                "விபத்து", "மோதி", "வாகனம் மோத", "दुर्घटना", "एक्सीडेंट", "टक्कर"],
}

MONTHS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]
NOT_A_PLACE = re.compile(
    r"^(the )?(morning|afternoon|evening|night|midnight|yesterday|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r"|\d|" + "|".join(MONTHS) + r")",
    re.I,
)
PLACE = re.compile(
    r"\b(?:at|near|outside|opposite|behind|inside|in front of|beside|in|on)\s+"
    r"(.+?)(?=[.,;]|\s+(?:when|while|and|but|because|yesterday|today|last|this|around|at|on)\b|$)",
    re.I,
)


def category_of(text):
    low = text.lower()
    best, top = "Other", 0
    for name, words in WORDS.items():
        hits = sum(low.count(w) for w in words)
        if hits > top:
            best, top = name, hits
    return best if best in CATEGORIES else "Other"


def date_of(text, today=None):
    """The incident date if the speaker gave one, otherwise None."""
    today = today or date.today()
    low = text.lower()
    # short Hindi words are matched as whole words, or "kal" would be found inside "nikla" and the like
    spoken = set(re.split(r"[\s,.।!?]+", low))
    if "day before yesterday" in low or "முந்தாநாள்" in low or "நேற்று முன்தினம்" in low or "परसों" in spoken:
        return (today - timedelta(days=2)).isoformat()
    # in Hindi "kal" can also mean tomorrow, but a complaint is about something that already happened
    if "yesterday" in low or "last night" in low or "நேற்று" in low or "कल" in spoken:
        return (today - timedelta(days=1)).isoformat()
    found = re.search(r"\b(\d{1,2}) days? ago\b", low) or re.search(r"(\d{1,2})\s*(?:நாட்களுக்கு முன்|நாள் முன்பு|दिन पहले)", low)
    if found:
        return (today - timedelta(days=int(found.group(1)))).isoformat()
    if re.search(r"\b(today|this morning|this afternoon|this evening|tonight)\b", low) or "இன்று" in low or "आज" in spoken:
        return today.isoformat()

    # written dates are read the Indian way, day first
    found = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", low)
    if found:
        return _valid(int(found.group(3)), int(found.group(2)), int(found.group(1)))
    found = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(" + "|".join(MONTHS) + r")(?:,?\s+(\d{4}))?", low)
    if found:
        return _valid(int(found.group(3) or today.year), MONTHS.index(found.group(2)) + 1, int(found.group(1)), today)
    found = re.search(r"\b(" + "|".join(MONTHS) + r")\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?", low)
    if found:
        return _valid(int(found.group(3) or today.year), MONTHS.index(found.group(1)) + 1, int(found.group(2)), today)
    return None


def _valid(year, month, day, today=None):
    try:
        when = date(year, month, day)
    except ValueError:
        return None
    # a date without a year that lands in the future must mean last year
    if today and when > today:
        when = date(year - 1, month, day)
    return when.isoformat() if when <= (today or date.today()) else None


def place_of(text):
    for found in PLACE.finditer(text):
        place = found.group(1).strip()
        if place and not NOT_A_PLACE.match(place):
            return place[:200]
    return ""


def read_complaint(text, today=None):
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return {"title": "", "description": "", "category": "", "incident_date": None, "location": ""}
    description = text[0].upper() + text[1:]
    if description[-1] not in ".!?":
        description += "."
    category = category_of(text)
    place = place_of(text)
    if category != "Other" and place:
        title = f"{category} at {place}"
    else:
        title = " ".join(text.split()[:8])
    return {
        "title": title[:120], "description": description[:4000], "category": category,
        "incident_date": date_of(text, today), "location": place,
    }
