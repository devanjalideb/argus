"""ReportLab PDF builder — professional, enterprise-styled investigation reports.

The three report types are genuinely distinct documents built from the SAME investigation
record, differing in sections, framing and technical depth:

* Executive  — business impact, financial exposure, customers affected, leadership decisions.
                Short, non-technical; no IOCs / API detail.
* Compliance — RBI / CERT-In references, regulatory obligations, audit trail. Formal and
                reference-heavy.
* Technical  — MITRE ATT&CK mapping, IOCs, affected APIs/endpoints, timeline, evidence,
                confidence breakdown and remediation. Detailed, for a SOC audience.

Currency: the ₹ (Indian Rupee, U+20B9) glyph is missing from ReportLab's built-in Helvetica,
so it renders as a blank box in PDFs. We embed a Unicode TTF font that contains ₹ when one is
available on the host; if none is found we transparently fall back to writing "Rs " inside the
PDF export path only (the web UI keeps ₹). Either way the symbol never renders broken.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
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

_RUPEE = "₹"

# ---------------------------------------------------------------- font embedding
# Resolved once: the family + regular/bold font names to use, and whether ₹ is renderable.
_FONT = {"base": "Helvetica", "bold": "Helvetica-Bold", "unicode": False, "_done": False}
_FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")


def _register_fonts() -> None:
    """Register a Unicode TTF (with a ₹ glyph) as the document font, if one is available.

    Tries a bundled copy first, then common Linux and Windows system locations. On success
    ₹ renders natively; otherwise the ``_txt`` fallback substitutes "Rs " so nothing breaks.
    """
    if _FONT["_done"]:
        return
    _FONT["_done"] = True
    candidates = [
        (os.path.join(_FONTS_DIR, "DejaVuSans.ttf"), os.path.join(_FONTS_DIR, "DejaVuSans-Bold.ttf")),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ]
    for regular, bold in candidates:
        try:
            if not (os.path.exists(regular) and os.path.exists(bold)):
                continue
            face = TTFont("ArgusUni", regular)
            # Skip fonts that don't actually contain the Rupee sign.
            if 0x20B9 not in getattr(face.face, "charToGlyph", {}):
                continue
            pdfmetrics.registerFont(face)
            pdfmetrics.registerFont(TTFont("ArgusUni-Bold", bold))
            pdfmetrics.registerFontFamily("ArgusUni", normal="ArgusUni", bold="ArgusUni-Bold",
                                          italic="ArgusUni", boldItalic="ArgusUni-Bold")
            _FONT.update(base="ArgusUni", bold="ArgusUni-Bold", unicode=True)
            return
        except Exception:  # pragma: no cover - font parsing is best-effort
            continue


def _txt(s) -> str:
    """Sanitize text for the PDF: keep ₹ when the embedded font supports it, else 'Rs '."""
    s = "" if s is None else str(s)
    return s if _FONT["unicode"] else s.replace(_RUPEE, "Rs ")


def _styles():
    ss = getSampleStyleSheet()
    base, bold = _FONT["base"], _FONT["bold"]
    ss.add(ParagraphStyle("ArgH1", parent=ss["Heading1"], textColor=NAVY, fontSize=15,
                          spaceBefore=14, spaceAfter=6, fontName=bold))
    ss.add(ParagraphStyle("ArgH2", parent=ss["Heading2"], textColor=SLATE, fontSize=11.5,
                          spaceBefore=10, spaceAfter=4, fontName=bold))
    ss.add(ParagraphStyle("ArgBody", parent=ss["BodyText"], fontSize=9.5, leading=14,
                          textColor=SLATE, alignment=TA_LEFT, fontName=base))
    ss.add(ParagraphStyle("ArgMuted", parent=ss["BodyText"], fontSize=8, leading=11,
                          textColor=MUTED, fontName=base))
    ss.add(ParagraphStyle("ArgCell", parent=ss["BodyText"], fontSize=8.5, leading=12,
                          textColor=SLATE, fontName=base))
    ss.add(ParagraphStyle("ArgLead", parent=ss["BodyText"], fontSize=10.5, leading=15,
                          textColor=NAVY, fontName=base))
    return ss


def _inr(x) -> str:
    """Mirror the on-screen currency format (₹X.XX Cr / L), sanitized for the PDF font."""
    n = float(x or 0)
    if n >= 1_00_00_000:
        return _txt(f"{_RUPEE}{n / 1_00_00_000:.2f} Cr")
    if n >= 1_00_000:
        return _txt(f"{_RUPEE}{n / 1_00_000:.2f} L")
    return _txt(f"{_RUPEE}{n:,.0f}")


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


# ---------------------------------------------------------------- small helpers
def _P(text, ss, style="ArgBody"):
    return Paragraph(_txt(text), ss[style])


def _kv_table(rows, ss, col1=45 * mm):
    data = [[Paragraph(f"<b>{_txt(k)}</b>", ss["ArgCell"]), Paragraph(_txt(v), ss["ArgCell"])]
            for k, v in rows]
    t = Table(data, colWidths=[col1, None])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), BG),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _grid_table(headers, rows, ss, col_widths=None):
    """Header-banded data table (used by MITRE / IOC / regulatory / audit sections)."""
    data = [[Paragraph(f"<b>{_txt(h)}</b>", ss["ArgCell"]) for h in headers]]
    for r in rows:
        data.append([Paragraph(_txt(c), ss["ArgCell"]) for c in r])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _timeline_table(timeline, ss):
    data = [[Paragraph("<b>Time</b>", ss["ArgCell"]), Paragraph("<b>Event</b>", ss["ArgCell"]),
             Paragraph("<b>Detail</b>", ss["ArgCell"])]]
    for item in timeline[:16]:
        data.append([
            Paragraph((item.get("time", "") or "")[:19].replace("T", " "), ss["ArgCell"]),
            Paragraph(_txt(item.get("title", "")), ss["ArgCell"]),
            Paragraph(_txt(item.get("description", "")[:140]), ss["ArgCell"]),
        ])
    t = Table(data, colWidths=[32 * mm, 45 * mm, None], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


# ---------------------------------------------------------------- derived content
# MITRE ATT&CK techniques keyed by investigation category (grounded in the case category).
_MITRE = {
    "account_takeover": [
        ("Initial Access", "T1078", "Valid Accounts"),
        ("Credential Access", "T1539", "Steal Web Session Cookie"),
        ("Defense Evasion", "T1550", "Use Alternate Authentication Material"),
        ("Impact", "T1565", "Data Manipulation (fraudulent transfer)"),
    ],
    "credential_stuffing": [
        ("Credential Access", "T1110.004", "Brute Force: Credential Stuffing"),
        ("Initial Access", "T1078", "Valid Accounts"),
        ("Reconnaissance", "T1589", "Gather Victim Identity Information"),
    ],
    "insider_misuse": [
        ("Initial Access", "T1078.004", "Valid Accounts: Privileged"),
        ("Collection", "T1213", "Data from Information Repositories"),
        ("Exfiltration", "T1530", "Data from Cloud/Record Storage"),
    ],
    "api_abuse": [
        ("Initial Access", "T1190", "Exploit Public-Facing Application"),
        ("Command & Control", "T1071.001", "Application Layer Protocol: Web"),
        ("Impact", "T1499", "Endpoint Denial of Service (abuse volume)"),
    ],
    "retrospective_exposure": [
        ("Initial Access", "T1190", "Exploit Public-Facing Application"),
        ("Collection", "T1213", "Data from Information Repositories"),
        ("Credential Access", "T1552", "Unsecured Credentials"),
    ],
    "quantum_exposure": [
        ("Collection", "T1557", "Adversary-in-the-Middle (harvest-now)"),
        ("Credential Access", "T1552", "Unsecured Credentials"),
        ("Impact", "T1600", "Weaken Encryption"),
    ],
}
_MITRE_DEFAULT = [("Initial Access", "T1078", "Valid Accounts"),
                  ("Collection", "T1213", "Data from Information Repositories")]

_IOC_LABEL = {"customer": "Customer Account", "device": "Device Fingerprint",
              "ip": "IP Address", "endpoint": "Endpoint", "transaction": "Transaction Ref",
              "vulnerability": "Vulnerability"}


def _mitre_rows(d: dict):
    return _MITRE.get(d.get("category"), _MITRE_DEFAULT)


def _ioc_rows(d: dict):
    """Derive IOCs from the investigation's own entities and evidence source references."""
    seen, rows = set(), []

    def add(kind, value, context):
        value = (value or "").strip()
        key = (kind, value)
        if not value or key in seen:
            return
        seen.add(key)
        rows.append([_IOC_LABEL.get(kind, kind.title()), value, context])

    cust = d.get("primary_customer") or {}
    ep = d.get("primary_endpoint") or {}
    vuln = d.get("vulnerability") or {}
    add("customer", cust.get("ref"), cust.get("name") or "Primary account under investigation")
    add("endpoint", ep.get("ref"), ep.get("name") or "Primary affected endpoint")
    add("vulnerability", vuln.get("ref"), vuln.get("title") or "Associated disclosure")
    ents = (d.get("meta") or {}).get("entities") or {}
    add("ip", ents.get("ip"), "Source IP referenced by the originating engine")
    add("device", ents.get("device"), "Device referenced by the originating engine")
    for e in d.get("evidence", []):
        et = e.get("source_entity_type")
        if et in _IOC_LABEL:
            add(et, e.get("source_entity_id"), e.get("title") or "Evidence-linked indicator")
    return rows


def _endpoint_rows(d: dict):
    ep = d.get("primary_endpoint") or {}
    rows = []
    if ep.get("ref") or ep.get("name"):
        rows.append([ep.get("ref", "-"), ep.get("name", "-"),
                     str(ep.get("criticality", "-")).title()])
    for e in d.get("evidence", []):
        if e.get("category") == "infrastructure" and e.get("source_entity_id"):
            rows.append([e.get("source_entity_id", "-"), e.get("title", "-"), "-"])
    return rows


def _regulatory_rows(d: dict):
    """Applicable regulatory frameworks, selected from the case's data sensitivity/flags."""
    bi = d.get("business_impact") or {}
    sensitivity = str(bi.get("data_sensitivity", "")).lower()
    flags = " ".join(bi.get("regulatory_flags", []) or []).lower()
    cat = d.get("category", "")
    rows = [
        ("CERT-In", "Directions under Sec. 70B(6), IT Act 2000 (28 Apr 2022)",
         "Report the cyber incident to CERT-In within 6 hours of detection."),
        ("RBI", "Cyber Security Framework in Banks; Master Direction on Digital "
                "Payment Security Controls (2021)",
         "Notify the Reserve Bank of India and preserve forensic evidence."),
    ]
    if any(k in sensitivity for k in ("pii", "kyc", "contact")) or "pii" in flags:
        rows.append(("DPDP Act 2023", "Digital Personal Data Protection Act, 2023",
                     "Notify the Data Protection Board and affected data principals of the breach."))
    if "cardholder" in sensitivity or "card" in cat or "pci" in flags:
        rows.append(("PCI-DSS v4.0", "Payment Card Industry Data Security Standard",
                     "Assess cardholder-data exposure; engage the acquirer and card networks."))
    if cat in ("account_takeover", "credential_stuffing") or "fraud" in flags:
        rows.append(("FIU-IND", "Prevention of Money Laundering Act (PMLA)",
                     "File a Suspicious Transaction Report (STR) where fraud is confirmed."))
    return rows


def _audit_rows(d: dict):
    rows = []
    detected = (d.get("detected_at") or "")[:19].replace("T", " ")
    rows.append([detected, d.get("originating_engine", "argus").replace("_", " ").title(),
                 "Investigation created", f"Auto-generated case {d.get('code', '')}"])
    for a in d.get("analyst_actions", []):
        rows.append([(a.get("event_time") or "")[:19].replace("T", " "),
                     a.get("actor", "analyst"),
                     a.get("action", "").replace("_", " ").replace(":", ": "),
                     a.get("detail") or "-"])
    return rows


# ---------------------------------------------------------------- report sections
def _title_block(story, d, ss, tagline):
    story.append(_P(d["title"], ss, "ArgH1"))
    sev = d["severity"]
    bi = d.get("business_impact") or {}
    story.append(Paragraph(
        f"<font color='#{_SEV.get(sev, MUTED).hexval()[2:]}'><b>{sev.upper()}</b></font> "
        f"&nbsp;|&nbsp; Confidence {d['confidence']:.0f}% &nbsp;|&nbsp; "
        f"Priority {bi.get('executive_priority', '-')} &nbsp;|&nbsp; Engine: "
        f"{d['originating_engine'].replace('_', ' ').title()}", ss["ArgBody"]))
    story.append(Paragraph(f"<i>{_txt(tagline)}</i>", ss["ArgMuted"]))
    story.append(Spacer(1, 6))


def _executive(story, d, ss):
    bi = d.get("business_impact") or {}
    nar = d.get("ai_narrative") or {}
    _title_block(story, d, ss,
                 "Executive briefing — business impact and the decisions leadership must make.")
    story.append(_kv_table([
        ("Case ID", d["code"]),
        ("Status", d["status"].replace("_", " ").title()),
        ("Threat Type", d["category"].replace("_", " ").title()),
        ("Detected", (d.get("detected_at") or "")[:19].replace("T", " ")),
        ("Financial Exposure", _inr(bi.get("financial_exposure"))),
        ("Customers Affected", bi.get("affected_customers", 0)),
    ], ss))
    story.append(Spacer(1, 8))

    story.append(_P("Executive Summary", ss, "ArgH2"))
    story.append(_P(nar.get("executive_summary") or d.get("description", ""), ss, "ArgLead"))

    story.append(_P("Business Impact", ss, "ArgH2"))
    story.append(_kv_table([
        ("Estimated Financial Exposure", _inr(bi.get("financial_exposure"))),
        ("Customers Affected", bi.get("affected_customers", 0)),
        ("Data Sensitivity", str(bi.get("data_sensitivity", "-")).replace("_", " ").title()),
        ("Operational Disruption", str(bi.get("operational_disruption", "-")).replace("_", " ").title()),
        ("Executive Priority", bi.get("executive_priority", "-")),
        ("Estimated Remediation Cost", _inr(bi.get("estimated_remediation_cost"))),
    ], ss))

    story.append(_P("Decisions Required from Leadership", ss, "ArgH2"))
    recs = d.get("recommendations") or []
    if recs:
        for r in recs[:5]:
            story.append(_P(f"&bull; <b>{r['title']}</b> — approve and authorise for immediate "
                            f"execution ({r['priority']} priority).", ss, "ArgBody"))
    else:
        story.append(_P("&bull; Confirm containment approach and assign an accountable owner.",
                        ss, "ArgBody"))
    reg = bi.get("regulatory_flags") or []
    if reg:
        story.append(_P(f"&bull; <b>Regulatory decision</b> — authorise disclosure assessment for: "
                        f"{', '.join(reg)}.", ss, "ArgBody"))
    story.append(_P(f"&bull; <b>Financial authorisation</b> — sign off on up to "
                    f"{_inr(bi.get('estimated_remediation_cost'))} of remediation spend.",
                    ss, "ArgBody"))
    story.append(Spacer(1, 8))
    story.append(_P("This is a high-level executive briefing. Technical indicators, evidence and "
                    "remediation detail are available in the Technical report; regulatory "
                    "obligations are detailed in the Compliance report.", ss, "ArgMuted"))


def _compliance(story, d, ss):
    bi = d.get("business_impact") or {}
    _title_block(story, d, ss,
                 "Regulatory & compliance record — obligations, references and audit trail.")
    story.append(_kv_table([
        ("Case ID", d["code"]),
        ("Status", d["status"].replace("_", " ").title()),
        ("Incident Category", d["category"].replace("_", " ").title()),
        ("Detected (IST)", (d.get("detected_at") or "")[:19].replace("T", " ")),
        ("Data Sensitivity", str(bi.get("data_sensitivity", "-")).replace("_", " ").title()),
        ("Regulatory Flags", ", ".join(bi.get("regulatory_flags", []) or ["None identified"])),
    ], ss))
    story.append(Spacer(1, 8))

    story.append(_P("1. Regulatory Overview", ss, "ArgH2"))
    story.append(_P(
        f"This document records the regulatory posture of investigation {d['code']}, an "
        f"incident classified as {d['category'].replace('_', ' ')} with an assessed data "
        f"sensitivity of {str(bi.get('data_sensitivity', 'unknown')).replace('_', ' ')}. The "
        f"obligations below are engaged by the nature of the affected data and the regulated "
        f"banking context. All timelines run from the point of detection recorded above.",
        ss, "ArgBody"))

    story.append(_P("2. Applicable Regulatory References", ss, "ArgH2"))
    story.append(_grid_table(["Authority", "Reference", "Obligation"], _regulatory_rows(d), ss,
                             col_widths=[26 * mm, 60 * mm, None]))

    story.append(_P("3. Regulatory Obligations & Timelines", ss, "ArgH2"))
    for line in [
        "Report the incident to CERT-In within 6 hours of detection (mandatory).",
        "Notify the RBI and the bank's CISO office per the Cyber Security Framework.",
        "Preserve all related logs and forensic evidence for a minimum of 180 days.",
        "Where customer data or funds are affected, notify impacted customers without undue delay.",
    ]:
        story.append(_P(f"&bull; {line}", ss, "ArgBody"))

    story.append(_P("4. Audit Trail", ss, "ArgH2"))
    story.append(_grid_table(["Timestamp", "Actor", "Action", "Detail"], _audit_rows(d), ss,
                             col_widths=[32 * mm, 28 * mm, 34 * mm, None]))

    story.append(_P("5. Evidence Integrity", ss, "ArgH2"))
    story.append(_P(
        "Every generated report is fingerprinted with a SHA-256 integrity hash and recorded "
        "with an immutable version number. Underlying evidence is captured from an append-only "
        "event ledger and is not mutated after creation, supporting the chain-of-custody "
        "requirements of a regulatory review.", ss, "ArgBody"))
    story.append(Spacer(1, 8))
    story.append(_P("Prepared as a formal compliance record. Figures are grounded in the "
                    "structured investigation evidence and are reproducible from the case data.",
                    ss, "ArgMuted"))


def _technical(story, d, ss):
    nar = d.get("ai_narrative") or {}
    _title_block(story, d, ss,
                 "Technical analysis for SOC / security engineering — IOCs, ATT&CK, remediation.")
    story.append(_kv_table([
        ("Case ID", d["code"]),
        ("Originating Engine", d["originating_engine"].replace("_", " ").title()),
        ("Category", d["category"].replace("_", " ").title()),
        ("Severity", d["severity"].title()),
        ("Confidence", f"{d['confidence']:.0f}%"),
        ("Detected", (d.get("detected_at") or "")[:19].replace("T", " ")),
    ], ss))
    story.append(Spacer(1, 8))

    story.append(_P("1. Technical Analysis", ss, "ArgH2"))
    for line in (nar.get("technical_summary") or d.get("description", "")).split("\n"):
        if line.strip():
            story.append(_P(line, ss, "ArgBody"))
    nxt = d.get("predicted_next_step")
    if nxt:
        story.append(_P(f"<b>Predicted next step:</b> {nxt}", ss, "ArgBody"))

    story.append(_P("2. MITRE ATT&CK Mapping", ss, "ArgH2"))
    story.append(_grid_table(["Tactic", "Technique", "Name"],
                             [[t, tid, name] for t, tid, name in _mitre_rows(d)], ss,
                             col_widths=[38 * mm, 28 * mm, None]))

    story.append(_P("3. Indicators of Compromise (IOCs)", ss, "ArgH2"))
    iocs = _ioc_rows(d)
    if iocs:
        story.append(_grid_table(["Type", "Indicator", "Context"], iocs, ss,
                                 col_widths=[34 * mm, 48 * mm, None]))
    else:
        story.append(_P("No discrete indicators were extracted for this investigation.", ss, "ArgMuted"))

    story.append(_P("4. Affected APIs & Endpoints", ss, "ArgH2"))
    eps = _endpoint_rows(d)
    if eps:
        story.append(_grid_table(["Reference", "Name / Description", "Criticality"], eps, ss,
                                 col_widths=[42 * mm, None, 26 * mm]))
    else:
        story.append(_P("No specific endpoint was implicated by the evidence.", ss, "ArgMuted"))

    timeline = d.get("timeline") or (d.get("meta") or {}).get("timeline") or []
    if timeline:
        story.append(_P("5. Investigation Timeline", ss, "ArgH2"))
        story.append(_timeline_table(timeline, ss))

    story.append(_P("6. Supporting Evidence", ss, "ArgH2"))
    for cat, items in (d.get("evidence_by_category") or {}).items():
        story.append(_P(f"<b>{cat.replace('_', ' ').title()}</b>", ss, "ArgBody"))
        for e in items:
            story.append(_P(f"&bull; <b>{e['title']}</b> — {e['description']}", ss, "ArgMuted"))

    if d.get("confidence_breakdown"):
        story.append(_P("7. Confidence Breakdown", ss, "ArgH2"))
        story.append(_grid_table(
            ["Factor", "Weight", "Detail"],
            [[b.get("factor", "-"), f"{int(round(float(b.get('contribution', 0)) * 100))}%",
              b.get("detail", "-")] for b in d["confidence_breakdown"]], ss,
            col_widths=[45 * mm, 18 * mm, None]))

    recs = d.get("recommendations") or []
    if recs:
        story.append(_P("8. Recommended Remediation", ss, "ArgH2"))
        for r in recs:
            story.append(_P(f"&bull; <b>[{r['priority']}] {r['title']}</b> — {r['rationale']}",
                            ss, "ArgMuted"))
    story.append(Spacer(1, 8))
    story.append(_P("Generated for a security-engineering audience. All indicators and figures "
                    "are grounded in the structured investigation evidence.", ss, "ArgMuted"))


_BUILDERS = {"executive": _executive, "compliance": _compliance, "technical": _technical}


def build(detail: dict, report_type: str, path: str) -> None:
    _register_fonts()
    ss = _styles()
    d = detail
    rtype = (report_type or "executive").lower()
    subtitle = f"{rtype.title()} Report - {d['code']}"
    doc = _Doc(path, title=f"ARGUS {rtype.title()} Report", subtitle=subtitle)
    story: list = []

    _BUILDERS.get(rtype, _executive)(story, d, ss)

    story.append(Spacer(1, 10))
    story.append(_P(
        f"Generated by ARGUS on {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}. "
        f"All conclusions are grounded in structured investigation evidence.", ss, "ArgMuted"))
    doc.build(story)
