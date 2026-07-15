"""ReportLab PDF builder — professional, enterprise-styled investigation reports.

One templated builder produces Executive / Technical / Compliance reports by including or
excluding sections. Styling resembles SOC documentation rather than an academic paper.
"""
from __future__ import annotations

from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

NAVY = colors.HexColor("#1F2A44")
SLATE = colors.HexColor("#334155")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#CBD5E1")
BG = colors.HexColor("#F1F5F9")
RED = colors.HexColor("#B91C1C")
AMBER = colors.HexColor("#B45309")
GREEN = colors.HexColor("#15803D")

_SEV = {"critical": RED, "high": AMBER, "medium": colors.HexColor("#0369A1"), "low": GREEN}


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("ArgH1", parent=ss["Heading1"], textColor=NAVY, fontSize=15,
                          spaceBefore=14, spaceAfter=6))
    ss.add(ParagraphStyle("ArgH2", parent=ss["Heading2"], textColor=SLATE, fontSize=11.5,
                          spaceBefore=10, spaceAfter=4))
    ss.add(ParagraphStyle("ArgBody", parent=ss["BodyText"], fontSize=9.5, leading=14,
                          textColor=SLATE, alignment=TA_LEFT))
    ss.add(ParagraphStyle("ArgMuted", parent=ss["BodyText"], fontSize=8, leading=11, textColor=MUTED))
    ss.add(ParagraphStyle("ArgCell", parent=ss["BodyText"], fontSize=8.5, leading=12, textColor=SLATE))
    return ss


def _inr(x) -> str:
    x = float(x or 0)
    if x >= 1_00_00_000:
        return f"Rs {x/1_00_00_000:.2f} cr"
    if x >= 1_00_000:
        return f"Rs {x/1_00_000:.2f} L"
    return f"Rs {x:,.0f}"


class _Doc(BaseDocTemplate):
    def __init__(self, path, title, subtitle, **kw):
        super().__init__(path, pagesize=A4, topMargin=28 * mm, bottomMargin=20 * mm,
                         leftMargin=18 * mm, rightMargin=18 * mm, title=title, **kw)
        self.report_title = title
        self.report_subtitle = subtitle
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="body")
        self.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=self._decorate)])

    def _decorate(self, canvas, doc):
        canvas.saveState()
        # Header band
        canvas.setFillColor(NAVY)
        canvas.rect(0, A4[1] - 20 * mm, A4[0], 20 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 13)
        canvas.drawString(18 * mm, A4[1] - 13 * mm, "ARGUS")
        canvas.setFont("Helvetica", 8)
        canvas.drawString(35 * mm, A4[1] - 13 * mm, "AI Cyber Decision Intelligence Platform")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(A4[0] - 18 * mm, A4[1] - 13 * mm, doc.report_subtitle)
        # Footer
        canvas.setStrokeColor(LINE)
        canvas.line(18 * mm, 15 * mm, A4[0] - 18 * mm, 15 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(18 * mm, 11 * mm, "Confidential - Internal Security Operations")
        canvas.drawRightString(A4[0] - 18 * mm, 11 * mm, f"Page {doc.page}")
        canvas.restoreState()


def _kv_table(rows, ss, col1=45 * mm):
    data = [[Paragraph(f"<b>{k}</b>", ss["ArgCell"]), Paragraph(str(v), ss["ArgCell"])] for k, v in rows]
    t = Table(data, colWidths=[col1, None])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), BG),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def build(detail: dict, report_type: str, path: str) -> None:
    ss = _styles()
    d = detail
    bi = d.get("business_impact") or {}
    nar = d.get("ai_narrative") or {}
    subtitle = f"{report_type.title()} Report - {d['code']}"
    doc = _Doc(path, title=f"ARGUS {report_type.title()} Report", subtitle=subtitle)
    story: list = []

    # Title block
    story.append(Paragraph(d["title"], ss["ArgH1"]))
    sev = d["severity"]
    story.append(Paragraph(
        f"<font color='#{_SEV.get(sev, MUTED).hexval()[2:]}'><b>{sev.upper()}</b></font> "
        f"&nbsp;|&nbsp; Confidence {d['confidence']:.0f}% &nbsp;|&nbsp; "
        f"Priority {bi.get('executive_priority','-')} &nbsp;|&nbsp; Engine: {d['originating_engine']}",
        ss["ArgBody"]))
    story.append(Spacer(1, 4))
    story.append(_kv_table([
        ("Case ID", d["code"]),
        ("Status", d["status"]),
        ("Category", d["category"].replace("_", " ").title()),
        ("Detected", (d.get("detected_at") or "")[:19].replace("T", " ")),
        ("Financial Exposure", _inr(bi.get("financial_exposure"))),
        ("Affected Customers", bi.get("affected_customers", 0)),
    ], ss))
    story.append(Spacer(1, 8))

    # 1. Executive summary
    story.append(Paragraph("1. Executive Summary", ss["ArgH2"]))
    story.append(Paragraph(nar.get("executive_summary", d.get("description", "")), ss["ArgBody"]))

    # 2. Business impact
    story.append(Paragraph("2. Business Impact", ss["ArgH2"]))
    story.append(_kv_table([
        ("Estimated Exposure", _inr(bi.get("financial_exposure"))),
        ("Affected Customers", bi.get("affected_customers", 0)),
        ("Data Sensitivity", str(bi.get("data_sensitivity", "-")).replace("_", " ")),
        ("Infrastructure Criticality", bi.get("infrastructure_criticality", "-")),
        ("Operational Disruption", str(bi.get("operational_disruption", "-")).replace("_", " ")),
        ("Executive Priority", bi.get("executive_priority", "-")),
        ("Regulatory Considerations", ", ".join(bi.get("regulatory_flags", []) or ["-"])),
        ("Est. Remediation Cost", _inr(bi.get("estimated_remediation_cost"))),
    ], ss))

    # 3. Timeline
    timeline = d.get("timeline") or (d.get("meta") or {}).get("timeline") or []
    if timeline:
        story.append(Paragraph("3. Investigation Timeline", ss["ArgH2"]))
        story.append(_timeline_table(timeline, ss))

    # 4. Evidence (technical + compliance)
    if report_type in ("technical", "compliance"):
        story.append(Paragraph("4. Supporting Evidence", ss["ArgH2"]))
        for cat, items in (d.get("evidence_by_category") or {}).items():
            story.append(Paragraph(cat.replace("_", " ").title(), ss["ArgBody"]))
            for e in items:
                story.append(Paragraph(f"&bull; <b>{e['title']}</b> — {e['description']}", ss["ArgMuted"]))

    # 5. Confidence breakdown (technical)
    if report_type == "technical" and d.get("confidence_breakdown"):
        story.append(Paragraph("5. Confidence Breakdown", ss["ArgH2"]))
        story.append(Paragraph(nar.get("confidence_explanation", ""), ss["ArgBody"]))

    # 6. Technical narrative (technical)
    if report_type == "technical" and nar.get("technical_summary"):
        story.append(Paragraph("6. Technical Analysis", ss["ArgH2"]))
        for line in nar["technical_summary"].split("\n"):
            story.append(Paragraph(line, ss["ArgBody"]))

    # 7. Recommendations
    recs = d.get("recommendations") or []
    if recs:
        story.append(Paragraph("7. Recommended Actions", ss["ArgH2"]))
        for r in recs:
            story.append(Paragraph(f"&bull; <b>[{r['priority']}] {r['title']}</b> — {r['rationale']}",
                                   ss["ArgMuted"]))

    # 8. Regulatory (compliance)
    if report_type == "compliance":
        story.append(Paragraph("8. Regulatory & Compliance Notes", ss["ArgH2"]))
        story.append(Paragraph(
            "This investigation potentially engages the following obligations: "
            + ", ".join(bi.get("regulatory_flags", []) or ["None identified"]) + ".", ss["ArgBody"]))

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"Generated by ARGUS on {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}. "
        f"All conclusions are grounded in structured investigation evidence.", ss["ArgMuted"]))
    doc.build(story)


def _timeline_table(timeline, ss):
    data = [[Paragraph("<b>Time</b>", ss["ArgCell"]), Paragraph("<b>Event</b>", ss["ArgCell"]),
             Paragraph("<b>Detail</b>", ss["ArgCell"])]]
    for item in timeline[:14]:
        data.append([
            Paragraph((item.get("time", "") or "")[:19].replace("T", " "), ss["ArgCell"]),
            Paragraph(item.get("title", ""), ss["ArgCell"]),
            Paragraph(item.get("description", "")[:120], ss["ArgCell"]),
        ])
    t = Table(data, colWidths=[32 * mm, 45 * mm, None])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t
