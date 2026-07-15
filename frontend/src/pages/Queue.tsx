import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, inr, when, titleCase } from "../api";
import { Icon, Severity, Priority, Stat, Loading, Empty, useAsync } from "../ui";

export default function Queue() {
  const nav = useNavigate();
  const [filter, setFilter] = useState({ severity: "", engine: "", status: "" });
  const { data: summary } = useAsync(() => api.summary(), []);
  const q: any = { page_size: 50 };
  Object.entries(filter).forEach(([k, v]) => v && (q[k] = v));
  const { data, loading } = useAsync(() => api.investigations(q), [JSON.stringify(filter)]);
  const rows: any[] = (data as any) || [];
  const s: any = summary || {};

  return (
    <div className="page">
      <div className="page-head between">
        <div>
          <h1>Investigation Queue</h1>
          <p>Active investigations requiring attention — prioritized by business impact.</p>
        </div>
      </div>

      <div className="stats">
        <Stat k="Active Investigations" v={s.active ?? "—"} sub="requiring attention" accent="blue" />
        <Stat k="Critical" v={s.critical ?? "—"} sub="immediate priority" accent="red" />
        <Stat k="Created Today" v={s.created_today ?? "—"} sub="last 24 hours" />
        <Stat k="Total Cases" v={s.total ?? "—"} sub="all time" />
      </div>

      <div className="card">
        <div className="card-head">
          <h3><Icon name="queue" size={15} /> Investigations</h3>
          <div className="row">
            <select className="select-inline" value={filter.severity}
                    onChange={(e) => setFilter({ ...filter, severity: e.target.value })}>
              <option value="">All severity</option>
              <option value="critical">Critical</option><option value="high">High</option>
              <option value="medium">Medium</option><option value="low">Low</option>
            </select>
            <select className="select-inline" value={filter.engine}
                    onChange={(e) => setFilter({ ...filter, engine: e.target.value })}>
              <option value="">All engines</option>
              <option value="watchtower">Watchtower</option>
              <option value="blast_radius">Blast Radius</option>
            </select>
            <select className="select-inline" value={filter.status}
                    onChange={(e) => setFilter({ ...filter, status: e.target.value })}>
              <option value="">All status</option>
              <option value="open">Open</option><option value="in_progress">In progress</option>
              <option value="closed">Closed</option>
            </select>
          </div>
        </div>
        {loading ? <Loading /> : rows.length === 0 ? (
          <Empty title="No investigations" hint="Run 'Rebuild demo' to generate the scenario set." />
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Case</th><th>Investigation</th><th>Severity</th><th>Confidence</th>
                  <th>Engine</th><th>Exposure</th><th>Customers</th><th>Priority</th><th>Detected</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.code} onClick={() => nav(`/investigation/${r.code}`)}>
                    <td className="code-cell">{r.code}</td>
                    <td>
                      <div style={{ fontWeight: 600 }}>{r.title}</div>
                      <div className="muted" style={{ fontSize: 12 }}>{titleCase(r.category)}</div>
                    </td>
                    <td><Severity level={r.severity} /></td>
                    <td className="tnum" style={{ fontWeight: 600 }}>{r.confidence?.toFixed(0)}%</td>
                    <td><span className="pill engine">{titleCase(r.originating_engine)}</span></td>
                    <td className="tnum" style={{ fontWeight: 600 }}>{inr(r.financial_exposure)}</td>
                    <td className="tnum">{r.affected_customers}</td>
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
  );
}
