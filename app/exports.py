"""CSV and PDF output for the lists and the case file."""
import csv
import io

from fpdf import FPDF
from fpdf.enums import TableCellFillMode
from fpdf.fonts import FontFace

from .mongo import now


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


_SWAPS = {"“": '"', "”": '"', "’": "'", "‘": "'", "…": "...", "–": "-", "—": "-", "•": "*", "→": "->"}
INK, MUTED, BRASS, RED, GREEN = (42, 38, 27), (112, 106, 82), (184, 146, 74), (143, 29, 33), (59, 106, 36)
BAND, SOFT, RULE = (47, 42, 28), (245, 243, 228), (205, 201, 176)


def _latin(text):
    # the built-in PDF fonts only cover latin-1, so swap anything else for a plain character
    text = "" if text is None else str(text)
    for old, new in _SWAPS.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "replace").decode("latin-1")


def _outside_latin(values):
    return any(ch for value in values for ch in str(value or "") if ord(ch) > 255 and ch not in _SWAPS)


class CasePDF(FPDF):
    def __init__(self, fir_no, generated_by):
        super().__init__()
        self.fir_no, self.generated_by = fir_no, generated_by
        self.set_margins(18, 24, 18)
        self.set_auto_page_break(auto=True, margin=22)
        self.set_title(f"Case file {fir_no}")
        self.set_author("Crime Records Management System")
        self.alias_nb_pages()

    def header(self):
        self.set_y(10)
        self.set_font("Helvetica", "B", 7.5)
        self.set_text_color(*MUTED)
        self.cell(self.epw / 2, 5, "CRIME RECORDS MANAGEMENT SYSTEM")
        self.set_font("Courier", "B", 8)
        self.cell(self.epw / 2, 5, _latin(self.fir_no), align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*BRASS)
        self.set_line_width(0.5)
        self.line(self.l_margin, 16.5, self.w - self.r_margin, 16.5)
        self.set_y(self.t_margin)

    def footer(self):
        self.set_y(-15)
        self.set_draw_color(*RULE)
        self.set_line_width(0.2)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1.5)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*MUTED)
        third = self.epw / 3
        self.cell(third, 5, "Confidential. For official use only.")
        self.cell(third, 5, _latin(f"Generated {now()} UTC by {self.generated_by}"), align="C")
        self.cell(third, 5, f"Page {self.page_no()} of {{nb}}", align="R")

    def heading(self, text):
        if self.get_y() > self.h - 50:
            self.add_page()
        self.ln(6)
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(*INK)
        self.cell(0, 6, _latin(text).upper(), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*BRASS)
        self.set_line_width(0.6)
        self.line(self.l_margin, self.get_y(), self.l_margin + 22, self.get_y())
        self.set_draw_color(*RULE)
        self.set_line_width(0.2)
        self.line(self.l_margin + 22, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

    def text_block(self, text, size=9.5, bold=False, color=INK, indent=0, height=5):
        self.set_x(self.l_margin + indent)
        self.set_font("Helvetica", "B" if bold else "", size)
        self.set_text_color(*color)
        self.multi_cell(self.epw - indent, height, _latin(text), new_x="LMARGIN", new_y="NEXT")

    def muted(self, text, size=8.5, indent=0):
        self.text_block(text, size=size, color=MUTED, indent=indent, height=4.4)

    def grid(self, rows):
        """Label and value pairs in two columns, like the top of a printed form."""
        half = self.epw / 2
        for left, right in rows:
            start = self.get_y()
            for index, pair in enumerate((left, right)):
                if pair is None:
                    continue
                self.set_xy(self.l_margin + index * half, start)
                self.set_font("Helvetica", "B", 7)
                self.set_text_color(*MUTED)
                self.cell(half - 4, 4, _latin(pair[0]).upper(), new_x="LEFT", new_y="NEXT")
                self.set_x(self.l_margin + index * half)
                self.set_font("Helvetica", "", 10)
                self.set_text_color(*INK)
                self.multi_cell(half - 6, 5, _latin(pair[1] or "-"), new_x="LEFT", new_y="NEXT")
            self.set_y(max(self.get_y(), start + 11) + 1)

    def simple_table(self, headings, rows, widths, mono=()):
        style = FontFace(emphasis="BOLD", color=INK, fill_color=SOFT, size_pt=8)
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(*INK)
        with self.table(
            col_widths=widths, headings_style=style, borders_layout="HORIZONTAL_LINES", line_height=4.6,
            text_align="LEFT", padding=1.6, first_row_as_headings=True,
            cell_fill_color=(255, 255, 255), cell_fill_mode=TableCellFillMode.ALL,
        ) as table:
            head = table.row()
            for h in headings:
                head.cell(_latin(h))
            for values in rows:
                row = table.row()
                for column, value in enumerate(values):
                    row.cell(_latin(value if value not in (None, "") else "-"))
        self.set_text_color(*INK)


def case_pdf(case, evidence, linked, reports, timeline, extra=None, integrity=None, generated_by="the system"):
    extra = extra or {}
    pdf = CasePDF(case["fir_no"], generated_by)
    pdf.add_page()

    # title block
    top = pdf.get_y()
    pdf.set_fill_color(*BAND)
    pdf.rect(pdf.l_margin, top, pdf.epw, 24, style="F")
    pdf.set_fill_color(*BRASS)
    pdf.rect(pdf.l_margin, top, 2.2, 24, style="F")
    pdf.set_xy(pdf.l_margin + 8, top + 4)
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_text_color(214, 196, 150)
    pdf.cell(60, 4, "CASE FILE", new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(pdf.l_margin + 8, top + 9)
    pdf.set_font("Courier", "B", 17)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(100, 9, _latin(case["fir_no"]))
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_xy(pdf.w - pdf.r_margin - 62, top + 8)
    pdf.set_text_color(*BRASS)
    pdf.cell(58, 7, _latin(case["status"]).upper(), align="R")
    pdf.set_y(top + 28)

    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 8, _latin(case["title"]), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, _latin(f"Case {case['case_id']}  |  {case['category']}, {case['severity']} severity"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.grid([
        (("Station", case["station"]), ("Investigating officer", case["officer_name"] or "Not assigned")),
        (("Case opened", case["date_opened"]), ("Incident date", case["incident_date"])),
        (("Complaint filed by", case["citizen_name"]), ("Location", case["location"])),
    ])

    pdf.heading("Complaint")
    pdf.text_block(case["description"])

    pdf.heading("People linked to the case")
    if linked:
        pdf.simple_table(["Name", "Role", "Wanted"], [(p["name"], p["role"].capitalize(), "Yes" if p["wanted"] else "No") for p in linked], (90, 50, 34))
    else:
        pdf.muted("Nobody is linked.")

    pdf.heading("Evidence and chain of custody")
    if not evidence:
        pdf.muted("No evidence recorded.")
    for item in evidence:
        if pdf.get_y() > pdf.h - 60:
            pdf.add_page()
        pdf.text_block(f"{item['evidence_no']}. {item['type']}", bold=True, size=10)
        pdf.muted(f"Collected {item['date_collected']}", size=8)
        pdf.text_block(item["description"], size=9)
        steps = [(s["at"][:16], s["action"].capitalize(), s["where"], s["by"], s.get("note", "")) for s in item.get("custody", [])]
        if steps:
            pdf.ln(1)
            pdf.simple_table(["Time (UTC)", "Action", "Location", "By", "Note"], steps, (30, 28, 46, 30, 40))
        pdf.ln(3)

    chargesheet = extra.get("chargesheet")
    if chargesheet:
        pdf.heading("Chargesheet")
        pdf.grid([(("Filed on", chargesheet["filed_on"]), ("Filed by", chargesheet["filed_by"])), (("Sections", chargesheet["sections"]), None)])
        pdf.text_block(chargesheet["summary"])
    if extra.get("statements"):
        pdf.heading("Statements")
        for item in extra["statements"]:
            pdf.text_block(f"{item['kind'].capitalize()}: {item['person']}", bold=True)
            pdf.muted(f"Recorded {item['recorded_at'][:16]} UTC by {item['recorded_by']}", size=8)
            pdf.text_block(item["body"], indent=4, size=9)
            pdf.ln(2)
    if extra.get("arrests"):
        pdf.heading("Arrests")
        pdf.simple_table(["Person", "Date", "Place", "Charges"], [(i["person"], i["arrested_on"], i["place"], i["charges"]) for i in extra["arrests"]], (40, 26, 44, 64))
    if extra.get("court_dates"):
        pdf.heading("Court dates")
        pdf.simple_table(["Date", "Court", "Purpose", "Outcome"], [(i["date"], i["court"], i["purpose"], i["outcome"]) for i in extra["court_dates"]], (26, 50, 54, 44))

    pdf.heading("Reports")
    if not reports:
        pdf.muted("No reports written.")
    for report in reports:
        pdf.text_block(f"{report['date_generated']}" + (f", {report['author']}" if report["author"] else ""), bold=True)
        pdf.text_block(report["content"], indent=4, size=9)
        pdf.ln(2)

    pdf.heading("Case ledger")
    pdf.muted("Every event, in the order it happened, with the entry that sealed it into the case ledger.", size=8)
    pdf.ln(1)
    for event in timeline:
        if pdf.get_y() > pdf.h - 42:
            pdf.add_page()
        seal = event.get("seal")
        pdf.set_font("Courier", "", 7.5)
        pdf.set_text_color(*MUTED)
        mark = f"#{seal['seq']}  {seal['hash']}" + ("  (imported)" if seal["imported"] else "") if seal else "not sealed"
        pdf.cell(pdf.epw * 0.55, 4, _latin(f"{event['at'][:19]} UTC"))
        pdf.cell(pdf.epw * 0.45, 4, _latin(mark), align="R", new_x="LMARGIN", new_y="NEXT")
        who = f"   by {event['who']}" if event.get("who") else ""
        pdf.text_block(f"{event['text']}{who}", bold=True, size=9)
        if event.get("detail"):
            pdf.muted(event["detail"], indent=3)
        pdf.set_draw_color(*RULE)
        pdf.set_line_width(0.15)
        pdf.line(pdf.l_margin, pdf.get_y() + 1, pdf.w - pdf.r_margin, pdf.get_y() + 1)
        pdf.ln(2.5)

    # the seal and the signatures close the file
    if pdf.get_y() > pdf.h - 90:
        pdf.add_page()
    pdf.heading("Integrity seal")
    if integrity:
        good = integrity["ok"]
        top = pdf.get_y()
        pdf.set_draw_color(*(GREEN if good else RED))
        pdf.set_line_width(0.5)
        pdf.set_fill_color(*SOFT)
        pdf.rect(pdf.l_margin, top, pdf.epw, 30 + 5 * len(integrity["problems"]), style="DF")
        pdf.set_xy(pdf.l_margin + 4, top + 3)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*(GREEN if good else RED))
        pdf.cell(0, 5, "VERIFIED: the ledger matches the records" if good else "PROBLEM: the ledger does not match the records", new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(pdf.l_margin + 4)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*INK)
        pdf.multi_cell(pdf.epw - 8, 4.4, _latin(f"{integrity['entries']} entries sealed, {integrity['imported']} of them imported from before sealing began. Checked {integrity['checked_at']} UTC."), new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(pdf.l_margin + 4)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 4, "CHAIN HEAD (HMAC-SHA256)", new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(pdf.l_margin + 4)
        pdf.set_font("Courier", "", 8)
        pdf.set_text_color(*INK)
        head = integrity["head"] or "(empty)"
        pdf.cell(0, 4, head[:32], new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(pdf.l_margin + 4)
        pdf.cell(0, 4, head[32:], new_x="LMARGIN", new_y="NEXT")
        for problem in integrity["problems"]:
            pdf.set_x(pdf.l_margin + 4)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*RED)
            pdf.cell(0, 4.6, _latin("- " + problem[:110]), new_x="LMARGIN", new_y="NEXT")
        pdf.set_y(top + 32 + 5 * len(integrity["problems"]))
        pdf.muted("Each entry carries a keyed hash of the entry before it. Changing, removing or reordering any entry changes every hash after it. The Verify integrity button on the case page checks this again at any time.", size=7.5)

    pdf.ln(10)
    base = pdf.get_y()
    half = pdf.epw / 2
    for index, label in enumerate(("Investigating officer", "Station house officer")):
        x = pdf.l_margin + index * half
        pdf.set_draw_color(*INK)
        pdf.set_line_width(0.3)
        pdf.line(x, base + 12, x + half - 12, base + 12)
        pdf.set_xy(x, base + 13)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*MUTED)
        pdf.cell(half - 12, 4, label + ", signature and date")

    watched = [case["title"], case["description"], case["citizen_name"], case["location"]]
    watched += [e["description"] for e in evidence] + [s["body"] for s in extra.get("statements", [])]
    if _outside_latin(watched):
        pdf.set_y(-26)
        pdf.set_font("Helvetica", "I", 7)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 4, "Some text in this file is in a script this PDF cannot print and shows as ?. The case page has the full text.")

    return bytes(pdf.output())
