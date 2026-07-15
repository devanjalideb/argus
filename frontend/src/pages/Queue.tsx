import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, inr, when, titleCase } from "../api";
import { Icon, Severity, Priority, Loading, Empty, useAsync } from "../ui";

const LABEL_COLOR: Record<string, string> = {
  Critical: "var(--critical-text)", High: "var(--high-text)",
  Medium: "var(--medium-text)", Low: "var(--success-text)",
};
const ACTION_ICON: Record<string, string> = {
  freeze_account: "freeze", revoke_session: "lock", block_device: "shield",
  notify_fraud_team: "bell", escalate_investigation: "alert", notify_customer: "bell",
  rotate_credentials: "refresh", patch_endpoint: "shield",
  initiate_regulatory_review: "file", generate_report: "file", close_investigation: "check",
};

function Gauge({ score, label }: { score: number; label: string }) {
  const size = 94, stroke = 8, r = (size - stroke) / 2 - 2, c = 2 * Math.PI * r;
  const col = LABEL_COLOR[label] || "var(--high-text)";
  return (
    <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size}>
        <defs>
          <linearGradient id="gaugeGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--critical-text)" />
            <stop offset="100%" stopColor="var(--high-text)" />
          </linearGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none"
                stroke="var(--border-hairline)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="url(#gaugeGrad)"
                strokeWidth={stroke} strokeLinecap="round" strokeDasharray={c}
                strokeDashoffset={c * (1 - score / 100)}
                transform={`rotate(-90 ${size / 2} ${size / 2})`}
                style={{ filter: `drop-shadow(0 0 6px ${col}66)`, transition: "stroke-dashoffset .6s ease" }} />
      </svg>
      <div className="gauge-center">
        <span className="gauge-val tnum">{score}</span>
        <span className="gauge-max">/100</span>
      </div>
    </div>
  );
}

export default function Queue() {
  const nav = useNavigate();
  const [filter, setFilter] = useState({ severity: "", engine: "", status: "" });
  const { data: cc } = useAsync(() => api.commandCenter(), []);
  const q: any = { page_size: 50 };
  Object.entries(filter).forEach(([k, v]) => v && (q[k] = v));
  const { data, loading } = useAsync(() => api.investigations(q), [JSON.stringify(filter)]);
  const rows: any[] = (data as any) || [];
  const m: any = cc || {};
  const sev = m.severity_counts || { critical: 0, high: 0, medium: 0, low: 0 };
  const total = m.active_total || 0;
  const maxSev = Math.max(1, sev.critical, sev.high, sev.medium, sev.low);
  const tp = m.top_priority;

  const segs = [
    ["critical", "var(--critical-text)"], ["high", "var(--high-text)"],
    ["medium", "var(--medium-text)"], ["low", "var(--success-text)"],
  ] as const;

  return (
    <div className="page">
      <div className="page-head between">
        <div>
          <h1>Investigation Command Center</h1>
          <p>Real-time overview of active threats and business impact.</p>
        </div>
        <span className="chip"><Icon name="clock" size={13} /> Last 24 hours</span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) 316px", gap: 16, marginBottom: 16, alignItems: "start" }}>
        <div className="grid" style={{ gap: 16 }}>
          {/* KPI row */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14 }}>
            <div className="kpi">
              <div className="k">Live Threat Level</div>
              <div className="row" style={{ gap: 12, marginTop: 8 }}>
                <Gauge score={m.threat_level?.score ?? 0} label={m.threat_level?.label ?? "Low"} />
                <div>
                  <div style={{ fontSize: 17, fontWeight: 700, color: LABEL_COLOR[m.threat_level?.label] || "var(--high-text)" }}>
                    {m.threat_level?.label ?? "—"}
                  </div>
                  <div className="sub">threat index</div>
                </div>
              </div>
            </div>

            <div className="kpi">
              <div className="k">Active Investigations</div>
              <div className="v tnum">{total}</div>
              <div className="sub" style={{ marginBottom: 6 }}>
                <span style={{ color: "var(--critical-text)" }}>Critical {sev.critical}</span> ·
                <span style={{ color: "var(--high-text)" }}> High {sev.high}</span> ·
                <span style={{ color: "var(--medium-text)" }}> Med {sev.medium}</span>
              </div>
              <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 30 }}>
                {segs.map(([key, col]) => (
                  <div key={key} title={`${titleCase(key)}: ${sev[key]}`}
                       style={{ flex: 1, height: `${Math.max(4, (sev[key] / maxSev) * 30)}px`,
                                background: col, borderRadius: "3px 3px 0 0", opacity: sev[key] ? 1 : 0.28 }} />
                ))}
              </div>
            </div>

            <div className="kpi">
              <div className="k">Business Risk (₹)</div>
              <div className="v tnum">{inr(m.business_risk)}</div>
              <div className="sub">Potential financial exposure</div>
            </div>

            <div className="kpi">
              <div className="k">Affected Customers</div>
              <div className="v tnum">{(m.affected_customers ?? 0).toLocaleString("en-IN")}</div>
              <div className="sub">Across {total} investigations</div>
            </div>
          </div>

          {/* Active investigations table */}
          <div className="card">
            <div className="card-head">
              <h3><Icon name="queue" size={15} /> Active Investigations</h3>
              <div className="row" style={{ gap: 8 }}>
                <select className="select-inline" value={filter.severity} onChange={(e) => setFilter({ ...filter, severity: e.target.value })}>
                  <option value="">All severity</option><option value="critical">Critical</option>
                  <option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
                </select>
                <select className="select-inline" value={filter.engine} onChange={(e) => setFilter({ ...filter, engine: e.target.value })}>
                  <option value="">All engines</option><option value="watchtower">Watchtower</option><option value="blast_radius">Blast Radius</option>
                </select>
                <select className="select-inline" value={filter.status} onChange={(e) => setFilter({ ...filter, status: e.target.value })}>
                  <option value="">All status</option><option value="open">Open</option><option value="in_progress">In progress</option><option value="closed">Closed</option>
                </select>
              </div>
            </div>
            {loading ? <Loading /> : rows.length === 0 ? (
              <Empty title="No investigations" hint="Run 'Rebuild demo' to generate the scenario set." />
            ) : (
              <div className="table-wrap">
                <table className="data">
                  <thead><tr>
                    <th>Case</th><th>Investigation</th><th>Severity</th><th>Engine</th>
                    <th style={{ textAlign: "right" }}>Exposure</th><th style={{ textAlign: "right" }}>Customers</th>
                    <th>Priority</th><th>Updated</th>
                  </tr></thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.code} onClick={() => nav(`/investigation/${r.code}`)}>
                        <td className="code-cell">{r.code}</td>
                        <td>
                          <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>{r.title}</div>
                          <div className="muted" style={{ fontSize: 12 }}>{titleCase(r.category)}</div>
                        </td>
                        <td><Severity level={r.severity} /></td>
                        <td><span className="pill engine">{titleCase(r.originating_engine)}</span></td>
                        <td className="num-cell">{inr(r.financial_exposure)}</td>
                        <td className="num-cell">{r.affected_customers}</td>
                        <td><Priority p={r.business_priority} /></td>
                        <td className="muted">{when(r.detected_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Command Summary */}
        <div className="card card-pad cmd-summary">
          <h3 style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 15, fontWeight: 600, marginBottom: 16 }}>
            <Icon name="activity" size={15} /> Command Summary
          </h3>
          {tp ? (
            <>
              <div className="block">
                <div className="lbl prio">Top Priority</div>
                <div className="row between" style={{ alignItems: "flex-start", gap: 8 }}>
                  <div style={{ fontWeight: 600, fontSize: 13, color: "var(--text-primary)", lineHeight: 1.35 }}>{tp.title}</div>
                  <Severity level={tp.severity} />
                </div>
                <div className="muted" style={{ fontSize: 12, marginTop: 5 }}>
                  {inr(tp.exposure)} at risk · {tp.affected} customer{tp.affected === 1 ? "" : "s"} affected
                </div>
              </div>
              <div className="block">
                <div className="lbl insight">Key Insight</div>
                <div className="muted" style={{ fontSize: 12.5, lineHeight: 1.55 }}>{m.key_insight}</div>
              </div>
              <div className="block">
                <div className="lbl actions">Suggested Actions</div>
                {(m.suggested_actions || []).map((a: any, i: number) => (
                  <div className="cmd-action" key={i}>
                    <span className="dot"><Icon name={ACTION_ICON[a.rec_type] || "check"} size={12} /></span>
                    {a.label}
                  </div>
                ))}
              </div>
              <button className="btn primary" style={{ width: "100%", justifyContent: "center", marginTop: 4 }}
                      onClick={() => nav(`/investigation/${tp.code}`)}>
                View Full Investigation <Icon name="arrow" size={14} />
              </button>
            </>
          ) : <p className="muted" style={{ fontSize: 13 }}>No active investigations.</p>}
        </div>
      </div>
    </div>
  );
}
