import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, when, titleCase } from "../api";
import { Icon, Card, Loading, useAsync, useToast } from "../ui";

function DistChart({ dist, threshold }: { dist: any[]; threshold: number }) {
  const W = 540, H = 190, pad = 26;
  if (!dist?.length) return <div className="empty" style={{ padding: 40 }}><Icon name="activity" size={34} /><h3>No distribution</h3></div>;
  const max = Math.max(1, ...dist.map((d) => d.count));
  const xAt = (x: number) => pad + x * (W - 2 * pad);
  const yAt = (c: number) => H - pad - (c / max) * (H - 2 * pad);
  const line = dist.map((d, i) => `${i ? "L" : "M"}${xAt(d.x).toFixed(1)},${yAt(d.count).toFixed(1)}`).join(" ");
  const area = `${line} L${xAt(dist[dist.length - 1].x)},${H - pad} L${xAt(dist[0].x)},${H - pad} Z`;
  const thrX = xAt(threshold);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: 190 }}>
      <defs>
        <linearGradient id="distFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--accent-violet-bright)" stopOpacity="0.28" />
          <stop offset="100%" stopColor="var(--accent-violet-bright)" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <line key={t} x1={xAt(t)} y1={pad} x2={xAt(t)} y2={H - pad} stroke="rgba(255,255,255,0.04)" />
      ))}
      <path d={area} fill="url(#distFill)" />
      <path d={line} fill="none" stroke="var(--accent-violet-bright)" strokeWidth={2} />
      <line x1={thrX} y1={pad - 4} x2={thrX} y2={H - pad} stroke="var(--critical-text)" strokeWidth={1.4} strokeDasharray="4 4" />
      <circle cx={thrX} cy={pad - 4} r={4} fill="var(--critical-text)" style={{ filter: "drop-shadow(0 0 6px var(--critical-text))" }} />
      <text x={thrX - 6} y={pad + 8} textAnchor="end" fontSize="10.5" fill="var(--text-secondary)">Threshold {threshold}</text>
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <text key={t} x={xAt(t)} y={H - 8} textAnchor="middle" fontSize="10" fill="var(--text-tertiary)">{t}</text>
      ))}
    </svg>
  );
}

const scoreColor = (s: number) => s >= 0.85 ? "var(--critical-text)" : s >= 0.7 ? "var(--high-text)" : "var(--medium-text)";

export default function Watchtower() {
  const nav = useNavigate();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const { data: status, reload: reloadStatus } = useAsync(() => api.watchtowerStatus(), []);
  const { data: det, reload: reloadDet } = useAsync(() => api.watchtowerDetections(), []);
  const st: any = status || {};
  const model = st.model || {};
  const detections: any[] = (det as any)?.detections || [];

  const run = async () => {
    setBusy(true);
    try { await api.watchtowerAnalyze(); toast.push("Behavioural analysis complete", "ok"); reloadStatus(); reloadDet(); }
    catch (e: any) { toast.push(e.message, "err"); } finally { setBusy(false); }
  };

  return (
    <div className="page">
      <div className="page-head between">
        <div>
          <h1>Watchtower</h1>
          <p>Forward-looking behavioural anomaly detection.</p>
        </div>
        <button className="btn primary" onClick={run} disabled={busy}>
          <Icon name="play" size={14} /> {busy ? "Analyzing…" : "Run Analysis"}
        </button>
      </div>

      <div className="stats">
        <div className="kpi"><div className="k">Model</div><div className="v" style={{ fontSize: 18 }}>Isolation Forest</div><div className="sub">scikit-learn · {model.version || "if-v1"}</div></div>
        <div className="kpi"><div className="k">Model Health</div><div className="v tnum" style={{ color: "var(--success-text)" }}>{model.health ? `${model.health}%` : "—"}</div><div className="sub">Excellent</div></div>
        <div className="kpi"><div className="k">Expected Anomaly Rate</div><div className="v tnum">{model.expected_rate ? `${model.expected_rate}%` : "—"}</div><div className="sub">Containment target</div></div>
        <div className="kpi"><div className="k">Active Investigations</div><div className="v tnum">{model.active_investigations ?? "—"}</div><div className="sub">From Watchtower</div></div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: "minmax(0,1.15fr) minmax(0,1fr)", gap: 16, marginBottom: 16 }}>
        <Card title="Anomaly Score Distribution" icon="activity">
          <DistChart dist={model.distribution} threshold={model.threshold ?? 0.76} />
        </Card>
        <Card title="Recent Detections" icon="watchtower" pad={false}>
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Case</th><th>Entity</th><th style={{ textAlign: "right" }}>Anomaly</th><th>Detected</th></tr></thead>
              <tbody>
                {detections.map((d) => (
                  <tr key={d.code} onClick={() => nav(`/investigation/${d.code}`)}>
                    <td className="code-cell">{d.code}</td>
                    <td style={{ color: "var(--text-primary)" }}>{d.entity}<div className="muted" style={{ fontSize: 11 }}>{titleCase(d.category)}</div></td>
                    <td className="num-cell" style={{ color: scoreColor(d.score) }}>{d.score.toFixed(2)}</td>
                    <td className="muted">{when(d.detected_at)}</td>
                  </tr>
                ))}
                {!detections.length && <tr><td colSpan={4} className="muted" style={{ padding: 18 }}>No detections yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <Card title="Top Anomalous Behaviours" icon="alert">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 12 }}>
          {(model.behaviours || []).map((b: any) => (
            <div className="kpi" key={b.name}>
              <div className="k" style={{ fontSize: 10 }}>{b.name}</div>
              <div className="v tnum" style={{ fontSize: 20, marginTop: 5 }}>{b.value}%</div>
              <div className="delta up" style={{ marginTop: 2 }}>▲ contribution</div>
            </div>
          ))}
          {!(model.behaviours || []).length && <p className="muted">Run analysis to compute behaviours.</p>}
        </div>
      </Card>
    </div>
  );
}
