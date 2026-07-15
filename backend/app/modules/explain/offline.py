"""Grounded offline narrator.

Composes the five narrative layers deterministically from an investigation's structured
evidence. Every sentence is built from real figures produced by earlier engines, so the
output is faithful by construction — the ideal "explain, never invent" behaviour, and it
needs no network access.
"""
from __future__ import annotations


def _inr(x: float | int | None) -> str:
    if not x:
        return "₹0"
    x = float(x)
    if x >= 1_00_00_000:
        return f"₹{x / 1_00_00_000:.2f} crore"
    if x >= 1_00_000:
        return f"₹{x / 1_00_000:.2f} lakh"
    return f"₹{x:,.0f}"


def _bi(d: dict) -> dict:
    return d.get("business_impact") or {}


def executive_summary(d: dict) -> str:
    bi = _bi(d)
    exposure = _inr(bi.get("financial_exposure"))
    cust = bi.get("affected_customers", 0)
    prio = bi.get("executive_priority", "P3")
    cat = d["category"].replace("_", " ")
    if d["originating_engine"] == "blast_radius":
        recon = (d.get("meta") or {}).get("reconstruction", {})
        ep = (d.get("primary_endpoint") or {}).get("name", "an endpoint")
        cls = recon.get("classification", "confirmed_exposure").replace("_", " ")
        return (f"Following a disclosure affecting {ep}, ARGUS reconstructed the historical "
                f"exposure and found {cls}: approximately {recon.get('exposed_records', 0):,} events "
                f"and {exposure} of activity across {cust} customers traversed the affected "
                f"infrastructure while the weakness was live. This is an executive priority {prio} "
                f"matter requiring immediate containment and regulatory assessment.")
    who = (d.get("primary_customer") or {}).get("ref", "a customer account")
    art = "an" if cat[:1].lower() in "aeiou" else "a"
    return (f"ARGUS detected {art} {cat} incident with {d['confidence']:.0f}% confidence involving {who}. "
            f"Estimated financial exposure is {exposure} across {cust} affected customer(s). "
            f"The investigation is executive priority {prio}; the recommended response is to contain "
            f"the incident immediately and confirm impact before loss is realised.")


def technical_summary(d: dict) -> str:
    parts = []
    if d["originating_engine"] == "watchtower":
        parts.append(f"Watchtower produced this investigation from correlated behavioural deviations "
                     f"rather than a single alert. Category: {d['category'].replace('_',' ')}; "
                     f"severity {d['severity']}; confidence {d['confidence']:.0f}%.")
        for e in d.get("evidence", [])[:6]:
            parts.append(f"• {e['title']} — {e['description']}")
        nxt = d.get("predicted_next_step")
        if nxt:
            parts.append(f"Predicted next step in the attack chain: {nxt}")
    else:
        recon = (d.get("meta") or {}).get("reconstruction", {})
        ep = d.get("primary_endpoint") or {}
        vuln = d.get("vulnerability") or {}
        parts.append(f"Blast Radius reconstructed exposure deterministically by replaying the immutable "
                     f"event ledger over the disclosure window for {vuln.get('ref','the disclosure')} "
                     f"({vuln.get('type','')}). Affected infrastructure: {ep.get('name','')} "
                     f"({ep.get('ref','')}).")
        parts.append(f"Reconstruction: {recon.get('exposed_records',0):,} events, "
                     f"{recon.get('exposed_customers',0)} customers, "
                     f"{recon.get('exposed_accounts',0)} accounts, total {_inr(recon.get('total_amount'))}. "
                     f"Window {recon.get('window_start','')[:10]} to {recon.get('window_end','')[:10]}.")
        for tc in recon.get("top_customers", [])[:3]:
            parts.append(f"• {tc['ref']} ({tc.get('type','')}) — {_inr(tc.get('exposed_amount'))} exposed.")
    return "\n".join(parts)


def confidence_explanation(d: dict) -> str:
    lines = [f"The {d['confidence']:.0f}% confidence is decomposed into independent contributing factors:"]
    for b in d.get("confidence_breakdown", []):
        pct = int(round(float(b.get("contribution", 0)) * 100))
        lines.append(f"• {b['factor']} ({pct}%): {b['detail']}")
    if len(lines) == 1:
        lines.append("• Confidence derives from correlated evidence and Risk Memory context.")
    return "\n".join(lines)


def evidence_summary(d: dict) -> str:
    by_cat = d.get("evidence_by_category", {})
    if not by_cat:
        return "No structured evidence is attached to this investigation."
    lines = ["The investigation is supported by the following categories of evidence:"]
    for cat, items in by_cat.items():
        titles = "; ".join(i["title"] for i in items[:3])
        lines.append(f"• {cat.replace('_',' ').title()} ({len(items)}): {titles}")
    return "\n".join(lines)


def recommended_action_summary(d: dict) -> str:
    recs = d.get("recommendations", [])
    if not recs:
        return "No automated recommendations were generated; route to an analyst for triage."
    lines = ["Recommended next-best-actions (deterministic, evidence-driven):"]
    for r in recs:
        lines.append(f"• [{r['priority']}] {r['title']} — {r['rationale']}")
    return "\n".join(lines)


def generate_all(d: dict) -> dict:
    return {
        "executive_summary": executive_summary(d),
        "technical_summary": technical_summary(d),
        "confidence_explanation": confidence_explanation(d),
        "evidence_summary": evidence_summary(d),
        "recommended_action_summary": recommended_action_summary(d),
    }
