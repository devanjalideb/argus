import { useState } from "react";
import { api, inr, titleCase } from "../api";
import { Icon, Card, Bar, Empty, useToast } from "../ui";

// Initial version wired to Risk Memory search; full tabbed explorer (Transactions /
// Logins / Devices / Graph / Top Counterparties) is built in the Entity Explorer screen turn.
export default function EntityExplorer() {
  const toast = useToast();
  const [q, setQ] = useState("");
  const [res, setRes] = useState<any[]>([]);
  const [sel, setSel] = useState<any>(null);

  const search = async (e?: any) => {
    e?.preventDefault();
    if (!q.trim()) return;
    try { const d: any = await api.riskSearch(q); setRes(d.customers || []); if (d.customers?.[0]) setSel(d.customers[0]); }
    catch (err: any) { toast.push(err.message, "err"); }
  };
  const p = sel?.profile || {};

  return (
    <div className="page">
      <div className="page-head">
        <h1>Entity Explorer</h1>
        <p>Search and explore any entity — customers, accounts, devices, IP addresses.</p>
      </div>

      <form onSubmit={search} className="row" style={{ marginBottom: 18, maxWidth: 520 }}>
        <div className="search" style={{ flex: 1, maxWidth: "none" }}>
          <Icon name="search" size={15} />
          <input placeholder="Search any entity (e.g. CUST-00030)" value={q}
                 onChange={(e) => setQ(e.target.value)} style={{ paddingRight: 12 }} />
        </div>
        <button className="btn primary" type="submit">Search</button>
      </form>

      <div className="grid" style={{ gridTemplateColumns: "300px 1fr", gap: 16 }}>
        <Card title="Results" icon="user" pad={false}>
          <div style={{ padding: 8 }}>
            {res.map((r) => (
              <div key={r.id} className={`cmdk-item ${sel?.id === r.id ? "sel" : ""}`} onClick={() => setSel(r)}>
                <div><div style={{ fontWeight: 600, color: "var(--text-primary)" }}>{r.ref}</div>
                  <div className="muted" style={{ fontSize: 12 }}>{r.name} · {titleCase(r.type)}</div></div>
              </div>
            ))}
            {!res.length && <p className="muted" style={{ padding: 16, fontSize: 13 }}>Search to explore an entity.</p>}
          </div>
        </Card>

        {sel ? (
          <div className="grid" style={{ gap: 16 }}>
            <Card title={`${sel.ref} · ${sel.name}`} icon="user">
              <div className="impact-grid">
                <div className="impact-cell"><div className="k">Type</div><div className="v" style={{ fontSize: 15 }}>{titleCase(sel.type)}</div></div>
                <div className="impact-cell"><div className="k">Trust Score</div><div className="v tnum">{(p.trust_score ?? 0).toFixed(2)}</div></div>
                <div className="impact-cell"><div className="k">Avg Transaction</div><div className="v tnum" style={{ fontSize: 16 }}>{inr(p.amt_mean)}</div></div>
                <div className="impact-cell"><div className="k">Observations</div><div className="v tnum">{p.observation_count ?? 0}</div></div>
              </div>
              <div style={{ marginTop: 14 }}>
                <div className="conf-row"><div className="conf-label">Behavioural confidence</div><div className="conf-pct">{Math.round((p.behavioural_confidence ?? 0) * 100)}%</div></div>
                <Bar pct={(p.behavioural_confidence ?? 0) * 100} />
              </div>
            </Card>
          </div>
        ) : <Empty title="No entity selected" hint="Search and select an entity to explore." icon="user" />}
      </div>
    </div>
  );
}
