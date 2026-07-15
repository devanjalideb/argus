import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, titleCase } from "../api";
import { Icon, Card, Loading, useToast } from "../ui";

const COLORS: Record<string, string> = {
  investigation: "#9B7CF6", customer: "#4F8CFF", endpoint: "#2ED9C4", employee: "#F5B94D",
  vulnerability: "#FF5C6C", ip: "#6FC7FF", ip_address: "#6FC7FF", service: "#33C48D",
  device: "#F5B94D", transaction: "#33C48D", account: "#4F8CFF",
};
const ICON: Record<string, string> = {
  investigation: "shield", customer: "user", endpoint: "cpu", employee: "user",
  vulnerability: "alert", ip: "integrations", ip_address: "integrations",
  service: "integrations", device: "cpu", transaction: "check", account: "risk",
};
const W = 1000, H = 600;

export default function KnowledgeGraphPage() {
  const [sp, setSp] = useSearchParams();
  const toast = useToast();
  const [invs, setInvs] = useState<any[]>([]);
  const [code, setCode] = useState(sp.get("code") || "");
  const [graph, setGraph] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [node, setNode] = useState<any>(null);

  useEffect(() => {
    api.investigations({ page_size: 50 }).then((d: any) => {
      setInvs(d); if (!code && d[0]) setCode(d[0].code);
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (!code) return;
    setLoading(true); setNode(null); setSp({ code });
    api.graph(code).then(setGraph).catch((e: any) => toast.push(e.message, "err")).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  const px = (x: number) => W / 2 + x * (W / 2 - 110);
  const py = (y: number) => H / 2 + y * (H / 2 - 90);
  const col = (t: string) => COLORS[t] || "#8b93a8";

  const clickNode = async (n: any) => {
    const [t, ...rest] = n.id.split(":");
    const rawId = rest.join(":");
    if (["customer", "device", "ip", "endpoint"].includes(t)) {
      try { const ctx = await api.nodeContext(t, rawId); setNode({ ...n, ctx }); }
      catch { setNode(n); }
    } else setNode(n);
  };

  const types = graph ? Object.keys(graph.stats.by_type) : [];

  return (
    <div className="page">
      <div className="page-head between">
        <div>
          <h1>Knowledge Graph</h1>
          <p>Interactive investigation network.</p>
        </div>
        <select className="select-inline" style={{ height: 34, minWidth: 260 }} value={code} onChange={(e) => setCode(e.target.value)}>
          {invs.map((i) => <option key={i.code} value={i.code}>{i.code} · {i.title.slice(0, 38)}</option>)}
        </select>
      </div>

      {loading ? <Card><Loading /></Card> : graph ? (
        <div className="graph-wrap">
          <svg className="graph-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">
            {graph.edges.map((e: any, i: number) => {
              const s = graph.nodes.find((n: any) => n.id === e.source);
              const t = graph.nodes.find((n: any) => n.id === e.target);
              if (!s || !t) return null;
              return <line key={i} className="g-edge" x1={px(s.x)} y1={py(s.y)} x2={px(t.x)} y2={py(t.y)}
                           stroke={col(t.type)} strokeOpacity={0.4} />;
            })}
            {graph.nodes.map((n: any) => {
              const c = col(n.type);
              const r = n.is_root ? 30 : 15 + Math.min(n.degree, 4) * 2;
              return (
                <g className="g-node" key={n.id} onClick={() => clickNode(n)} style={{ cursor: "pointer" }}>
                  <circle cx={px(n.x)} cy={py(n.y)} r={r} fill={c} fillOpacity={0.16}
                          stroke={c} strokeWidth={n.is_root ? 2.5 : 1.6}
                          style={{ filter: `drop-shadow(0 0 ${n.is_root ? 22 : 10}px ${c}${n.is_root ? "aa" : "77"})` }} />
                  <foreignObject x={px(n.x) - 10} y={py(n.y) - 10} width={20} height={20} style={{ pointerEvents: "none" }}>
                    <div style={{ width: 20, height: 20, display: "grid", placeItems: "center", color: c }}>
                      <Icon name={ICON[n.type] || "activity"} size={n.is_root ? 16 : 13} />
                    </div>
                  </foreignObject>
                  <text x={px(n.x)} y={py(n.y) + r + 14} textAnchor="middle" fill="var(--text-primary)" fontSize={n.is_root ? 12 : 11} fontWeight={n.is_root ? 700 : 500}>{n.label}</text>
                  <text x={px(n.x)} y={py(n.y) + r + 27} textAnchor="middle" fill="var(--text-tertiary)" fontSize={9.5}>{titleCase(n.type)}</text>
                </g>
              );
            })}
          </svg>
          <div className="g-legend">
            {types.map((t) => <div key={t} className="li"><i style={{ background: col(t), boxShadow: `0 0 6px ${col(t)}` }} /> {titleCase(t)}</div>)}
          </div>
          {node && (
            <div className="node-panel">
              <div className="between" style={{ marginBottom: 8 }}>
                <span className="chip" style={{ textTransform: "capitalize", color: col(node.type) }}>{titleCase(node.type)}</span>
                <button className="icon-btn" style={{ width: 26, height: 26 }} onClick={() => setNode(null)}><Icon name="x" size={13} /></button>
              </div>
              <div style={{ fontWeight: 700, marginBottom: 8, color: "var(--text-primary)" }}>{node.label}</div>
              {node.ctx ? (
                <div style={{ fontSize: 12.5, lineHeight: 1.7 }}>
                  {Object.entries(node.ctx).filter(([k]) => k !== "type" && k !== "risk_memory").map(([k, v]: any) => (
                    <div key={k} className="between"><span className="muted">{titleCase(k)}</span><span style={{ fontWeight: 600 }}>{String(v)}</span></div>
                  ))}
                  {node.ctx.risk_memory && <div className="between"><span className="muted">Trust</span><span style={{ fontWeight: 600 }}>{(node.ctx.risk_memory.trust_score ?? 0).toFixed(2)}</span></div>}
                </div>
              ) : <p className="muted" style={{ fontSize: 12 }}>Node metadata unavailable.</p>}
            </div>
          )}
        </div>
      ) : <Card><p className="muted">Select an investigation to view its graph.</p></Card>}

      {graph && <p className="muted" style={{ fontSize: 12, marginTop: 12 }}>
        {graph.stats.node_count} nodes · {graph.stats.edge_count} relationships · click any node to explore.
      </p>}
    </div>
  );
}
