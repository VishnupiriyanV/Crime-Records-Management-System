"""CSV and PDF output for the lists and the case file."""
import csv
import io

from fpdf import FPDF


def _safe(value):
    """A spreadsheet runs text that starts with these characters as a formula, so defuse it."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


def to_csv(columns, rows):
    """columns is a list of (heading, key) pairs; rows are dict-like."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([heading for heading, _ in columns])
    for row in rows:
        writer.writerow([_safe(row[key]) for _, key in columns])
    return out.getvalue()


def _latin(text):
    # the built-in PDF fonts only cover latin-1, so swap anything else for a plain character
    text = (text or "").replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    return text.encode("latin-1", "replace").decode("latin-1")


def case_pdf(case, evidence, linked, reports, timeline, extra=None):
    extra = extra or {}
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    def heading(text):
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, _latin(text), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(150, 150, 150)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(2)

    def line(text, bold=False):
        pdf.set_font("Helvetica", "B" if bold else "", 10)
        pdf.multi_cell(0, 5.5, _latin(text), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 9, _latin(f"Case {case['case_id']}: {case['title']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _latin(f"{case['fir_no']}  |  {case['category']}, {case['severity']} severity"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _latin(f"{case['status']}, opened {case['date_opened']} at {case['station']}"), new_x="LMARGIN", new_y="NEXT")

    heading("Complaint")
    line(f"Filed by: {case['citizen_name']}")
    line(f"Where: {case['location']}")
    line(f"Incident date: {case['incident_date']}")
    line(f"Officer: {case['officer_name'] or 'Unassigned'}")
    line(case["description"])

    heading("People linked to the case")
    if not linked:
        line("Nobody is linked.")
    for person in linked:
        line(f"{person['name']} ({person['role']})" + (", wanted" if person["wanted"] else ""))

    heading("Evidence")
    if not evidence:
        line("No evidence recorded.")
    for item in evidence:
        line(f"{item['evidence_no']}. {item['type']} ({item['date_collected']}): {item['description']}")
        for step in item.get("custody", []):
            where = f" - {step['where']}" if step["where"] else ""
            line(f"      {step['at'][:16]}  {step['action']}{where} ({step['by']})")

    chargesheet = extra.get("chargesheet")
    if chargesheet:
        heading("Chargesheet")
        line(f"Filed {chargesheet['filed_on']} by {chargesheet['filed_by']}", bold=True)
        line(f"Sections: {chargesheet['sections']}")
        line(chargesheet["summary"])
    if extra.get("statements"):
        heading("Statements")
        for item in extra["statements"]:
            line(f"{item['kind'].capitalize()} {item['person']} ({item['recorded_at'][:10]})", bold=True)
            line(item["body"])
    if extra.get("arrests"):
        heading("Arrests")
        for item in extra["arrests"]:
            line(f"{item['person']}, {item['arrested_on']}, {item['place']}. Charges: {item['charges']}")
    if extra.get("court_dates"):
        heading("Court dates")
        for item in extra["court_dates"]:
            line(f"{item['date']}  {item['court']}: {item['purpose']}" + (f" (outcome: {item['outcome']})" if item["outcome"] else ""))

    heading("Reports")
    if not reports:
        line("No reports written.")
    for report in reports:
        line(f"{report['date_generated']}" + (f", {report['author']}" if report["author"] else ""), bold=True)
        line(report["content"])

    heading("Timeline")
    for event in timeline:
        who = f" ({event['who']})" if event["who"] else ""
        line(f"{event['at'][:16]}  {event['text']}{who}")

    return bytes(pdf.output())
