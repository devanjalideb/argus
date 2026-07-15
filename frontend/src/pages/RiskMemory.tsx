import { useEffect, useState } from "react";
import { api, inr, when, titleCase } from "../api";
import { Icon, Card, Loading, useToast } from "../ui";

function Donut({ pct, color, children }: { pct: number; color: string; children: any }) {
  const size = 128, stroke = 9, r = (size - stroke) / 2 - 2, c = 2 * Math.PI * r;
  return (
    <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--border-hairline)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke}
                strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - pct / 100)}
                transform={`rotate(-90 ${size / 2} ${size / 2})`}
                style={{ filter: `drop-shadow(0 0 6px ${color}55)`, transition: "stroke-dashoffset .6s" }} />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        {children}
      </div>
    </div>
  );
}

function HoursHeatmap({ hours }: { hours: number[] }) {
  const set = new Set(hours || []);
  return (
    <div>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 40 }}>
        {Array.from({ length: 24 }, (_, h) => {
          const on = set.has(h);
          return <div key={h} title={`${h}:00`} style={{ flex: 1, height: on ? "100%" : "22%",
            background: on ? "var(--accent-violet-bright)" : "var(--bg-panel-alt)",
            borderRadius: "3px 3px 0 0", boxShadow: on ? "0 0 8px rgba(139,124,246,.4)" : "none" }} />;
        })}
      </div>
      <div className="between" style={{ marginTop: 4, fontSize: 9.5, color: "var(--text-tertiary)" }}>
        <span>12AM</span><span>6AM</span><span>12PM</span><span>6PM</span><span>11PM</span>
      </div>
    </div>
  );
}

const level = (t: number) => t >= 0.75 ? ["High", "var(--success-text)"] : t >= 0.45 ? ["Medium", "var(--high-text)"] : ["Low", "var(--critical-text)"];

export default function RiskMemory() {
  const toast = useToast();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [ref, setRef] = useState<string>("");
  const [detail, setDetail] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const search = async (query: string, autoselect = false) => {
    try {
      const d: any = await api.riskSearch(query);
      setResults(d.customers || []);
      if (autoselect && d.customers?.[0]) setRef(d.customers[0].ref);
    } catch (e: any) { toast.push(e.message, "err"); }
  };
  useEffect(() => { search("CUST-000", true); }, []);
  useEffect(() => {
    if (!ref) return;
    setLoading(true);
    api.riskCustomer(ref).then(setDetail).catch((e: any) => toast.push(e.message, "err")).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ref]);

  const c = detail?.customer, p = detail?.profile || {}, stats = detail?.stats || {};
  const [lvl, lvlColor] = level(p.trust_score ?? 0);

  return (
    <div className="page">
      <div className="page-head">
        <h1>Risk Memory</h1>
        <p>Evolving behavioural profiles — every entity compared against its own history.</p>
      </div>

      <form onSubmit={(e) => { e.preventDefault(); search(q, true); }} className="row" style={{ marginBottom: 16, maxWidth: 480 }}>
        <div className="search" style={{ flex: 1, maxWidth: "none" }}>
          <Icon name="search" size={15} />
          <input placeholder="Search customer / entity…" value={q} onChange={(e) => setQ(e.target.value)} style={{ paddingRight: 12 }} />
        </div>
        <button className="btn primary" type="submit">Search</button>
      </form>

      <div className="grid" style={{ gridTemplateColumns: "270px 1fr", gap: 16 }}>
        <Card title="Profiles" icon="user" pad={false}>
          <div style={{ padding: 8, maxHeight: 560, overflowY: "auto" }}>
            {results.map((r) => (
              <div key={r.id} className={`cmdk-item ${ref === r.ref ? "sel" : ""}`} onClick={() => setRef(r.ref)}>
                <div><div style={{ fontWeight: 600, color: "var(--text-primary)" }}>{r.ref}</div>
                  <div className="muted" style={{ fontSize: 12 }}>{r.name} · {titleCase(r.type)}</div></div>
              </div>
            ))}
          </div>
        </Card>

        {loading || !detail ? <Card><Loading /></Card> : (
          <div className="grid" style={{ gap: 16 }}>
            <div className="card card-pad">
              <div className="between" style={{ marginBottom: 16 }}>
                <div>
                  <div style={{ fontSize: 16, fontWeight: 700 }}>{c.ref} · {c.name}</div>
                  <div className="muted" style={{ fontSize: 12.5 }}>{titleCase(c.type)} · onboarded {when(c.onboarding_date)}</div>
                </div>
                <span className="chip">Argus Ready</span>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "auto 1fr 1fr", gap: 20, alignItems: "center" }}>
                <Donut pct={(p.trust_score ?? 0) * 100} color={lvlColor as string}>
                  <span style={{ fontSize: 15, fontWeight: 700, lineHeight: 1.1 }}>{inr(stats.total_volume)}</span>
                  <span style={{ fontSize: 10, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: ".06em", marginTop: 2 }}>Asset Score</span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: lvlColor as string }}>{lvl}</span>
                </Donut>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                  <div><div className="k" style={{ fontSize: 10.5, color: "var(--text-microlabel)", textTransform: "uppercase", letterSpacing: ".06em" }}>Behavioural Confidence</div><div className="v tnum" style={{ fontSize: 22, fontWeight: 700, color: "var(--success-text)" }}>{Math.round((p.behavioural_confidence ?? 0) * 100)}%</div></div>
                  <div><div className="k" style={{ fontSize: 10.5, color: "var(--text-microlabel)", textTransform: "uppercase", letterSpacing: ".06em" }}>Auth Success</div><div className="v tnum" style={{ fontSize: 22, fontWeight: 700 }}>{Math.round((p.auth_success_rate ?? 1) * 100)}%</div></div>
                  <div><div className="k" style={{ fontSize: 10.5, color: "var(--text-microlabel)", textTransform: "uppercase", letterSpacing: ".06em" }}>Avg Transaction</div><div className="v tnum" style={{ fontSize: 18, fontWeight: 700 }}>{inr(p.amt_mean)}</div></div>
                  <div><div className="k" style={{ fontSize: 10.5, color: "var(--text-microlabel)", textTransform: "uppercase", letterSpacing: ".06em" }}>Max Transaction</div><div className="v tnum" style={{ fontSize: 18, fontWeight: 700 }}>{inr(p.amt_max)}</div></div>
                  <div><div className="k" style={{ fontSize: 10.5, color: "var(--text-microlabel)", textTransform: "uppercase", letterSpacing: ".06em" }}>Observations</div><div className="v tnum" style={{ fontSize: 18, fontWeight: 700 }}>{p.observation_count ?? 0}</div></div>
                  <div><div className="k" style={{ fontSize: 10.5, color: "var(--text-microlabel)", textTransform: "uppercase", letterSpacing: ".06em" }}>Transactions</div><div className="v tnum" style={{ fontSize: 18, fontWeight: 700 }}>{stats.txn_count ?? 0}</div></div>
                </div>

                <div style={{ display: "grid", gap: 12 }}>
                  <div>
                    <div className="ev-group-h">Known Devices</div>
                    {(detail.devices || []).slice(0, 3).map((d: any, i: number) => (
                      <div key={i} className="between" style={{ padding: "4px 0", fontSize: 12.5 }}>
                        <span style={{ color: "var(--text-primary)" }}><Icon name="cpu" size={12} /> {d.name}</span>
                        <span className="muted" style={{ fontSize: 11 }}>{when(d.last_seen)}</span>
                      </div>
                    ))}
                    {!(detail.devices || []).length && <div className="muted" style={{ fontSize: 12 }}>—</div>}
                  </div>
                  <div>
                    <div className="ev-group-h">Known Regions</div>
                    <div className="row wrap" style={{ gap: 5 }}>
                      {(detail.regions || []).map((r: string) => <span key={r} className="chip">{r}</span>)}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <Card title="Behavioural Identity" icon="activity">
              <div className="ev-group-h" style={{ marginTop: 0 }}>Preferred Login Hours</div>
              <HoursHeatmap hours={p.preferred_hours || []} />
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
