import { useNavigate } from "react-router-dom";
import { api, inr, when, titleCase } from "../api";
import { Icon, Severity, Card, Stat, Loading, useAsync, useToast } from "../ui";
import { useState } from "react";

export default function Watchtower() {
  const nav = useNavigate();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const { data: status } = useAsync(() => api.watchtowerStatus(), []);
  const { data, loading, reload } = useAsync(() => api.watchtowerDetections(), []);
  const st: any = status || {};
  const model = st.model || {};
  const rows: any[] = (data as any)?.detections || [];

  const runAnalyze = async () => {
    setBusy(true);
    try { await api.watchtowerAnalyze(); toast.push("Behavioural analysis complete", "ok"); reload(); }
    catch (e: any) { toast.push(e.message, "err"); } finally { setBusy(false); }
  };

  return (
    <div className="page">
      <div className="page-head between">
        <div>
          <h1>Watchtower</h1>
          <p>Forward-looking behavioural anomaly detection — Isolation Forest scored against each entity's own Risk Memory baseline.</p>
        </div>
        <button className="btn primary" onClick={runAnalyze} disabled={busy}>
          <Icon name="watchtower" size={15} /> {busy ? "Analyzing…" : "Run analysis"}
        </button>
      </div>

      <div className="stats">
        <Stat k="Model" v="Isolation Forest" sub={model.version || "scikit-learn"} accent="blue" />
        <Stat k="Training Samples" v={model.n_samples ?? "—"} sub={`${model.n_features ?? 0} features`} />
        <Stat k="Contamination" v={model.contamination ? `${(model.contamination * 100).toFixed(0)}%` : "—"} sub="expected anomaly rate" />
        <Stat k="Detections" v={rows.length} sub="active investigations" accent="red" />
      </div>

      <Card title="Recent Detections" icon="watchtower" pad={false}>
        {loading ? <Loading /> : (
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Case</th><th>Detection</th><th>Severity</th><th>Confidence</th><th>Exposure</th><th>Detected</th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.code} onClick={() => nav(`/investigation/${r.code}`)}>
                    <td className="code-cell">{r.code}</td>
                    <td><div style={{ fontWeight: 600 }}>{r.title}</div><div className="muted" style={{ fontSize: 12 }}>{titleCase(r.category)}</div></td>
                    <td><Severity level={r.severity} /></td>
                    <td className="tnum" style={{ fontWeight: 600 }}>{r.confidence?.toFixed(0)}%</td>
                    <td className="tnum">{inr(r.financial_exposure)}</td>
                    <td className="muted">{when(r.detected_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <p className="muted" style={{ fontSize: 12, marginTop: 14 }}>
        {st.approach}
      </p>
    </div>
  );
}
