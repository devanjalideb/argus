import { useState } from "react";
import { api, inr, titleCase } from "../api";
import { Icon, Card, Bar, Empty, useToast } from "../ui";

export default function RiskMemory() {
  const toast = useToast();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [sel, setSel] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const search = async (e?: any) => {
    e?.preventDefault();
    if (!q.trim()) return;
    setLoading(true);
    try { const d: any = await api.riskSearch(q); setResults(d.customers || []); if (d.customers?.[0]) setSel(d.customers[0]); }
    catch (err: any) { toast.push(err.message, "err"); } finally { setLoading(false); }
  };

  const p = sel?.profile || {};

  return (
    <div className="page">
      <div className="page-head">
        <h1>Risk Memory</h1>
        <p>Evolving behavioural profiles — every entity is compared against its own history, not the population.</p>
      </div>

      <form onSubmit={search} className="row" style={{ marginBottom: 18, maxWidth: 520 }}>
        <div className="search" style={{ flex: 1, maxWidth: "none" }}>
          <Icon name="search" size={16} />
          <input placeholder="Search customers by ref or name (e.g. CUST-00030)" value={q}
                 onChange={(e) => setQ(e.target.value)} style={{ paddingRight: 12 }} />
        </div>
        <button className="btn primary" type="submit">Search</button>
      </form>

      <div className="grid" style={{ gridTemplateColumns: "300px 1fr", gap: 18 }}>
        <Card title="Results" icon="user" pad={false}>
          <div style={{ padding: 8 }}>
            {results.map((r) => (
              <div key={r.id} className={`cmdk-item ${sel?.id === r.id ? "sel" : ""}`} onClick={() => setSel(r)}>
                <div><div style={{ fontWeight: 600 }}>{r.ref}</div><div className="muted" style={{ fontSize: 12 }}>{r.name} · {titleCase(r.type)}</div></div>
              </div>
            ))}
            {!results.length && !loading && <p className="muted" style={{ padding: 16, fontSize: 13 }}>Search to inspect a behavioural profile.</p>}
          </div>
        </Card>

        {sel ? (
          <div className="grid" style={{ gap: 18 }}>
            <Card title={`${sel.ref} · ${sel.name}`} icon="risk">
              <div className="impact-grid">
                <div className="impact-cell"><div className="k">Trust Score</div><div className="v tnum">{(p.trust_score ?? 0).toFixed(2)}</div></div>
                <div className="impact-cell"><div className="k">Behavioural Confidence</div><div className="v tnum">{(p.behavioural_confidence ?? 0).toFixed(2)}</div></div>
                <div className="impact-cell"><div className="k">Avg Transaction</div><div className="v tnum" style={{ fontSize: 16 }}>{inr(p.amt_mean)}</div></div>
                <div className="impact-cell"><div className="k">Max Transaction</div><div className="v tnum" style={{ fontSize: 16 }}>{inr(p.amt_max)}</div></div>
                <div className="impact-cell"><div className="k">Observations</div><div className="v tnum">{p.observation_count ?? 0}</div></div>
                <div className="impact-cell"><div className="k">Auth Success</div><div className="v tnum">{((p.auth_success_rate ?? 1) * 100).toFixed(0)}%</div></div>
              </div>
              <div style={{ marginTop: 14 }}>
                <div className="conf-row"><div className="conf-label">Trust</div><div className="conf-pct">{Math.round((p.trust_score ?? 0) * 100)}%</div></div>
                <Bar pct={(p.trust_score ?? 0) * 100} />
              </div>
            </Card>
            <Card title="Behavioural Identity" icon="activity">
              <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                <div><div className="ev-group-h">Preferred Login Hours</div><div className="row wrap" style={{ gap: 5 }}>{(p.preferred_hours || []).map((h: number) => <span key={h} className="chip">{h}:00</span>)}</div></div>
                <div><div className="ev-group-h">Normal Regions</div><div className="row wrap" style={{ gap: 5 }}>{(p.normal_countries || []).map((c: string) => <span key={c} className="chip">{c}</span>)}</div></div>
                <div><div className="ev-group-h">Trusted Devices</div><div className="chip">{(p.preferred_devices || []).length} device(s)</div></div>
                <div><div className="ev-group-h">Txn Frequency</div><div className="chip">{(p.txn_frequency_daily ?? 0).toFixed(2)} / day</div></div>
              </div>
            </Card>
          </div>
        ) : <Empty title="No profile selected" hint="Search and select a customer." icon="risk" />}
      </div>
    </div>
  );
}
