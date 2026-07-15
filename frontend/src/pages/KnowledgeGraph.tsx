import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, titleCase } from "../api";
import { Icon, Card, Loading, useToast } from "../ui";

const COLORS: Record<string, string> = {
  investigation: "#6d4bd8", customer: "#2f5bd6", endpoint: "#d97706", vulnerability: "#dc2626",
  device: "#0891b2", ip: "#7c3aed", transaction: "#16a34a", account: "#0ea5e9",
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

  const px = (x: number) => W / 2 + x * (W / 2 - 90);
  const py = (y: number) => H / 2 + y * (H / 2 - 70);

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
          <p>Interactive investigation network — customers, devices, infrastructure and vulnerabilities.</p>
        </div>
        <select className="select-inline" style={{ height: 36, minWidth: 260 }} value={code} onChange={(e) => setCode(e.target.value)}>
          {invs.map((i) => <option key={i.code} value={i.code}>{i.code} · {i.title.slice(0, 40)}</option>)}
        </select>
      </div>

      {loading ? <Card><Loading /></Card> : graph ? (
        <div className="graph-wrap">
          <svg className="graph-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">
            {graph.edges.map((e: any, i: number) => {
              const s = graph.nodes.find((n: any) => n.id === e.source);
              const t = graph.nodes.find((n: any) => n.id === e.target);
              if (!s || !t) return null;
              return <line key={i} className="g-edge" x1={px(s.x)} y1={py(s.y)} x2={px(t.x)} y2={py(t.y)} />;
            })}
            {graph.nodes.map((n: any) => {
              const r = n.is_root ? 15 : 8 + Math.min(n.degree, 4) * 1.5;
              return (
                <g className="g-node" key={n.id} onClick={() => clickNode(n)}>
                  <circle cx={px(n.x)} cy={py(n.y)} r={r} fill={COLORS[n.type] || "#64748b"}
                          stroke="var(--surface)" strokeWidth={2} />
                  <text x={px(n.x)} y={py(n.y) + r + 12} textAnchor="middle">{n.label}</text>
                </g>
              );
            })}
          </svg>
          <div className="g-legend">
            {types.map((t) => <div key={t} className="li"><i style={{ background: COLORS[t] || "#64748b" }} /> {titleCase(t)}</div>)}
          </div>
          {node && (
            <div className="node-panel">
              <div className="between" style={{ marginBottom: 8 }}>
                <span className="chip" style={{ textTransform: "capitalize" }}>{node.type}</span>
                <button className="icon-btn" style={{ width: 26, height: 26 }} onClick={() => setNode(null)}><Icon name="x" size={13} /></button>
              </div>
              <div style={{ fontWeight: 700, marginBottom: 8 }}>{node.label}</div>
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
