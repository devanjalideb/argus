import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, inr, when, titleCase } from "../api";
import { Icon, Card, Loading, useToast } from "../ui";

const TABS = ["Overview", "Transactions", "Logins", "Devices", "Graph"];

function Donut({ pct }: { pct: number }) {
  const size = 118, stroke = 9, r = (size - stroke) / 2 - 2, c = 2 * Math.PI * r;
  return (
    <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--border-hairline)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--accent-violet-bright)" strokeWidth={stroke}
                strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - pct / 100)}
                transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ filter: "drop-shadow(0 0 6px rgba(139,124,246,.4))" }} />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", flexDirection: "column" }}>
        <span style={{ fontSize: 26, fontWeight: 700 }}>{pct}%</span>
        <span style={{ fontSize: 10, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: ".06em" }}>Trust</span>
      </div>
    </div>
  );
}

function LineChart({ data }: { data: any[] }) {
  const W = 560, H = 150, pad = 22;
  if (!data?.length) return <p className="muted" style={{ padding: 20 }}>No transaction history in the last 30 days.</p>;
  const max = Math.max(1, ...data.map((d) => d.amount));
  const n = data.length;
  const xAt = (i: number) => pad + (i / Math.max(1, n - 1)) * (W - 2 * pad);
  const yAt = (v: number) => H - pad - (v / max) * (H - 2 * pad);
  const line = data.map((d, i) => `${i ? "L" : "M"}${xAt(i).toFixed(1)},${yAt(d.amount).toFixed(1)}`).join(" ");
  const area = `${line} L${xAt(n - 1)},${H - pad} L${xAt(0)},${H - pad} Z`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: 150 }}>
      <defs><linearGradient id="entFill" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor="var(--accent-blue)" stopOpacity="0.25" />
        <stop offset="100%" stopColor="var(--accent-blue)" stopOpacity="0" />
      </linearGradient></defs>
      <path d={area} fill="url(#entFill)" />
      <path d={line} fill="none" stroke="var(--accent-blue)" strokeWidth={2} />
    </svg>
  );
}

export default function EntityExplorer() {
  const toast = useToast();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [ref, setRef] = useState("");
  const [data, setData] = useState<any>(null);
  const [tab, setTab] = useState("Overview");
  const [loading, setLoading] = useState(false);

  const search = async (query: string, auto = false) => {
    try { const d: any = await api.riskSearch(query); setResults(d.customers || []); if (auto && d.customers?.[0]) setRef(d.customers[0].ref); }
    catch (e: any) { toast.push(e.message, "err"); }
  };
  useEffect(() => { search("CUST-000", true); }, []);
  useEffect(() => {
    if (!ref) return;
    setLoading(true);
    api.entityCustomer(ref).then(setData).catch((e: any) => toast.push(e.message, "err")).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ref]);

  const c = data?.customer, s = data?.stats || {}, p = data?.profile || {};

  return (
    <div className="page">
      <div className="page-head">
        <h1>Entity Explorer</h1>
        <p>Search and explore any entity — customers, accounts, devices, IPs.</p>
      </div>

      <form onSubmit={(e) => { e.preventDefault(); search(q, true); }} className="row" style={{ marginBottom: 16, maxWidth: 480 }}>
        <div className="search" style={{ flex: 1, maxWidth: "none" }}>
          <Icon name="search" size={15} />
          <input placeholder="Search any entity (e.g. CUST-00030)" value={q} onChange={(e) => setQ(e.target.value)} style={{ paddingRight: 12 }} />
        </div>
        <button className="btn primary" type="submit">Search</button>
      </form>

      <div className="grid" style={{ gridTemplateColumns: "260px 1fr", gap: 16 }}>
        <Card title="Entities" icon="user" pad={false}>
          <div style={{ padding: 8, maxHeight: 560, overflowY: "auto" }}>
            {results.map((r) => (
              <div key={r.id} className={`cmdk-item ${ref === r.ref ? "sel" : ""}`} onClick={() => setRef(r.ref)}>
                <div><div style={{ fontWeight: 600, color: "var(--text-primary)" }}>{r.ref}</div>
                  <div className="muted" style={{ fontSize: 12 }}>{r.name} · {titleCase(r.type)}</div></div>
              </div>
            ))}
          </div>
        </Card>

        {loading || !data ? <Card><Loading /></Card> : (
          <div className="card">
            <div className="card-head">
              <h3><Icon name="user" size={15} /> {c.ref} · {c.name} <span className="chip" style={{ marginLeft: 6 }}>{titleCase(c.type)}</span></h3>
            </div>
            <div className="card-pad" style={{ paddingBottom: 8 }}>
              <div className="tabs">
                {TABS.map((t) => <div key={t} className={`tab ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}>{t}</div>)}
              </div>

              {tab === "Overview" && (
                <div className="grid" style={{ gap: 16 }}>
                  <div style={{ display: "grid", gridTemplateColumns: "auto 1fr 1.2fr", gap: 20, alignItems: "center" }}>
                    <Donut pct={Math.round((p.trust_score ?? 0) * 100)} />
                    <div>
                      <div className="k" style={{ fontSize: 10.5, color: "var(--text-microlabel)", textTransform: "uppercase", letterSpacing: ".06em" }}>Total Transactions</div>
                      <div className="v tnum" style={{ fontSize: 26, fontWeight: 700 }}>{inr(s.total)}</div>
                      <div className="sub" style={{ marginTop: 4 }}>{s.count} txns · avg {inr(s.avg)}</div>
                    </div>
                    <div>
                      <div className="ev-group-h">Top Endpoints (by volume)</div>
                      {(data.top_endpoints || []).map((e: any) => (
                        <div key={e.ref} className="between" style={{ padding: "3px 0", fontSize: 12.5 }}>
                          <span style={{ color: "var(--text-primary)" }}>{e.ref}</span>
                          <span className="tnum muted">{inr(e.amount)}</span>
                        </div>
                      ))}
                      {!(data.top_endpoints || []).length && <div className="muted" style={{ fontSize: 12 }}>—</div>}
                    </div>
                  </div>
                  <div>
                    <div className="ev-group-h">Transaction History (30 days)</div>
                    <LineChart data={data.history} />
                  </div>
                </div>
              )}

              {tab === "Transactions" && (
                <div className="table-wrap"><table className="data">
                  <thead><tr><th>Ref</th><th>Category</th><th>Channel</th><th style={{ textAlign: "right" }}>Amount</th><th>Status</th><th>When</th></tr></thead>
                  <tbody>{(data.recent || []).map((t: any) => (
                    <tr key={t.ref} style={{ cursor: "default" }}><td className="code-cell">{t.ref}</td><td>{titleCase(t.category)}</td><td className="muted">{t.channel}</td>
                      <td className="num-cell">{inr(t.amount)}</td><td>{titleCase(t.status)}</td><td className="muted">{when(t.time)}</td></tr>
                  ))}</tbody></table></div>
              )}

              {tab === "Logins" && (
                <div className="table-wrap"><table className="data">
                  <thead><tr><th>Result</th><th>Method</th><th>Browser</th><th>When</th></tr></thead>
                  <tbody>{(data.logins || []).map((l: any, i: number) => (
                    <tr key={i} style={{ cursor: "default" }}><td style={{ color: l.result === "success" ? "var(--success-text)" : "var(--critical-text)" }}>{titleCase(l.result)}</td>
                      <td>{titleCase(l.method)}</td><td className="muted">{l.browser || "—"}</td><td className="muted">{when(l.time)}</td></tr>
                  ))}</tbody></table></div>
              )}

              {tab === "Devices" && (
                <div className="grid" style={{ gridTemplateColumns: "repeat(3,1fr)", gap: 12 }}>
                  {(data.devices || []).map((d: any, i: number) => (
                    <div className="kpi" key={i}><div className="k">{d.category}</div><div className="v" style={{ fontSize: 15 }}>{d.name}</div>
                      <div className="sub">{d.detail} · trust {d.trust}</div><div className="sub">seen {when(d.last_seen)}</div></div>
                  ))}
                  {!(data.devices || []).length && <p className="muted">No trusted devices.</p>}
                </div>
              )}

              {tab === "Graph" && (
                <p className="muted" style={{ fontSize: 13 }}>
                  Explore this entity's relationships in the <Link to="/knowledge-graph" style={{ color: "var(--accent-blue)" }}>Knowledge Graph</Link>.
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
