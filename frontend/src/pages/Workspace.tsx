import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api, inr, titleCase } from "../api";
import { Icon, Severity, Priority, Card, Bar, Loading, useAsync, useToast } from "../ui";

const AI_TABS = [
  ["executive_summary", "Executive"],
  ["technical_summary", "Technical"],
  ["confidence_explanation", "Confidence"],
  ["evidence_summary", "Evidence"],
  ["recommended_action_summary", "Actions"],
];

export default function Workspace() {
  const { code } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const { data, loading, reload } = useAsync(() => api.investigation(code!), [code]);
  const [tab, setTab] = useState("executive_summary");
  const [busy, setBusy] = useState(false);
  const d: any = data;

  const act = async (fn: () => Promise<any>, msg: string) => {
    setBusy(true);
    try { await fn(); toast.push(msg, "ok"); reload(); }
    catch (e: any) { toast.push(e.message, "err"); }
    finally { setBusy(false); }
  };

  if (loading) return <div className="page"><Loading /></div>;
  if (!d) return <div className="page"><Card><p className="muted">Investigation not found.</p></Card></div>;

  const bi = d.business_impact || {};
  const nar = d.ai_narrative;

  return (
    <div className="page">
      <div className="row" style={{ marginBottom: 12 }}>
        <Link to="/" className="btn sm"><Icon name="arrow" size={14} style={{ transform: "rotate(180deg)" }} /> Queue</Link>
        <span className="muted" style={{ fontSize: 12 }}>{d.code}</span>
      </div>

      <div className="ws-header">
        <div className="ws-title">{d.title}</div>
        <div className="ws-meta">
          <Severity level={d.severity} />
          <span className="chip">Confidence <b style={{ marginLeft: 4 }}>{d.confidence?.toFixed(0)}%</b></span>
          <Priority p={bi.executive_priority || d.business_priority} />
          <span className="pill engine">{titleCase(d.originating_engine)}</span>
          <span className="chip">{titleCase(d.status)}</span>
          <span className="chip">{titleCase(d.category)}</span>
          {d.owner && <span className="chip"><Icon name="user" size={12} /> {d.owner}</span>}
        </div>
        <div className="ws-actions">
          <button className="btn sm" disabled={busy} onClick={() => act(() => api.assign(d.code, "S. Sharma"), "Assigned to you")}><Icon name="user" size={14} /> Assign to me</button>
          <button className="btn sm danger" disabled={busy} onClick={() => act(() => api.escalate(d.code, "Escalated from workspace"), "Escalated to P1")}><Icon name="alert" size={14} /> Escalate</button>
          <button className="btn sm" disabled={busy} onClick={() => act(() => api.aiGenerate(d.code), "AI narrative regenerated")}><Icon name="cpu" size={14} /> Regenerate AI</button>
          <button className="btn sm" onClick={() => nav(`/reports?code=${d.code}`)}><Icon name="download" size={14} /> Reports</button>
          <button className="btn sm primary" disabled={busy} onClick={() => act(() => api.close(d.code, "Reviewed and contained via ARGUS workspace."), "Investigation closed")}><Icon name="check" size={14} /> Close</button>
        </div>
      </div>

      {nar?.executive_summary && (
        <div className="exec-summary">
          <div className="lbl">Executive Summary · AI ({nar.provider})</div>
          <p>{nar.executive_summary}</p>
        </div>
      )}

      <div className="ws-grid">
        <div className="grid" style={{ gap: 18 }}>
          <Card title="Investigation Timeline" icon="clock">
            {(d.timeline?.length || d.meta?.timeline?.length) ? (
              <div className="timeline">
                {(d.timeline?.length ? d.timeline : d.meta.timeline).map((t: any, i: number) => (
                  <div key={i} className={`tl-item ${t.kind === "disclosure" ? "disclosure" : ""} ${t.category === "transaction" ? "crit" : ""}`}>
                    <div className="tl-dot" />
                    <div className="tl-body">
                      <div className="tl-time">{(t.time || "").slice(0, 19).replace("T", " ")}</div>
                      <div className="tl-title">{t.title}</div>
                      <div className="tl-desc">{t.description}</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : <p className="muted">No timeline events.</p>}
          </Card>

          <Card title="Evidence" icon="shield">
            {Object.entries(d.evidence_by_category || {}).map(([cat, items]: any) => (
              <div className="ev-group" key={cat}>
                <div className="ev-group-h">{titleCase(cat)} · {items.length}</div>
                {items.map((e: any) => (
                  <div className="ev-item" key={e.id}>
                    <div className="t">{e.title}
                      {e.confidence_contribution > 0 && <span className="contrib">+{Math.round(e.confidence_contribution * 100)}%</span>}
                    </div>
                    <div className="d">{e.description}</div>
                  </div>
                ))}
              </div>
            ))}
            {!d.evidence_count && <p className="muted">No structured evidence.</p>}
          </Card>

          <Card title="AI Decision" icon="cpu">
            <div className="tabs">
              {AI_TABS.map(([k, label]) => (
                <div key={k} className={`tab ${tab === k ? "active" : ""}`} onClick={() => setTab(k)}>{label}</div>
              ))}
            </div>
            <div className="narrative">{nar ? nar[tab] : "No narrative generated yet."}</div>
          </Card>
        </div>

        <div className="grid" style={{ gap: 18 }}>
          <Card title="Business Impact" icon="activity">
            <div className="impact-grid">
              <div className="impact-cell big"><div className="k">Financial Exposure</div><div className="v tnum">{inr(bi.financial_exposure)}</div></div>
              <div className="impact-cell"><div className="k">Affected Customers</div><div className="v tnum">{bi.affected_customers ?? 0}</div></div>
              <div className="impact-cell"><div className="k">Executive Priority</div><div className="v">{bi.executive_priority || "—"}</div></div>
              <div className="impact-cell"><div className="k">Infra Criticality</div><div className="v" style={{ fontSize: 15 }}>{titleCase(bi.infrastructure_criticality || "—")}</div></div>
              <div className="impact-cell"><div className="k">Data Sensitivity</div><div className="v" style={{ fontSize: 14 }}>{titleCase(bi.data_sensitivity || "—")}</div></div>
              <div className="impact-cell"><div className="k">Remediation Cost</div><div className="v tnum" style={{ fontSize: 15 }}>{inr(bi.estimated_remediation_cost)}</div></div>
            </div>
            {bi.regulatory_flags?.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <div className="ev-group-h">Regulatory</div>
                <div className="row wrap" style={{ gap: 6 }}>
                  {bi.regulatory_flags.map((f: string) => <span key={f} className="chip"><Icon name="lock" size={11} /> {f}</span>)}
                </div>
              </div>
            )}
          </Card>

          <Card title="Confidence Breakdown" icon="activity">
            {(d.confidence_breakdown || []).map((b: any, i: number) => (
              <div key={i} style={{ marginBottom: 12 }}>
                <div className="conf-row">
                  <div className="conf-label">{b.factor}<small>{b.detail}</small></div>
                  <div className="conf-pct">{Math.round((b.contribution || 0) * 100)}%</div>
                </div>
                <Bar pct={(b.contribution || 0) * 100} />
              </div>
            ))}
            {!(d.confidence_breakdown || []).length && <p className="muted">No breakdown available.</p>}
          </Card>

          <Card title="Recommended Actions" icon="check">
            {(d.recommendations || []).map((r: any) => (
              <div className="rec" key={r.id}>
                <div className="rp"><Priority p={r.priority} /></div>
                <div>
                  <div className="rt">{r.title}</div>
                  <div className="rr">{r.rationale}</div>
                </div>
              </div>
            ))}
            {!(d.recommendations || []).length && <p className="muted">No recommendations.</p>}
          </Card>

          <Card title="Knowledge Graph" icon="graph"
                actions={<Link to={`/knowledge-graph?code=${d.code}`} className="btn sm">Open <Icon name="external" size={13} /></Link>}>
            <p className="muted" style={{ fontSize: 12.5 }}>
              Explore the relationships between the customer, devices, IPs, endpoints and
              vulnerabilities involved in this investigation.
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}
