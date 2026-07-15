import { useState } from "react";
import { api, titleCase } from "../api";
import { Icon, Card, Stat, Loading, useAsync, useToast } from "../ui";

export default function Integrations() {
  const toast = useToast();
  const [busy, setBusy] = useState("");
  const { data: info } = useAsync(() => api.info(), []);
  const { data: aiSt } = useAsync(() => api.aiStatus(), []);
  const { data: counts, loading, reload } = useAsync(() => api.synthStatus(), []);
  const i: any = info || {}; const ai: any = aiSt || {}; const c: any = counts || {};

  const run = async (name: string, fn: () => Promise<any>, msg: string) => {
    setBusy(name);
    try { await fn(); toast.push(msg, "ok"); reload(); }
    catch (e: any) { toast.push(e.message, "err"); } finally { setBusy(""); }
  };

  return (
    <div className="page">
      <div className="page-head">
        <h1>Integrations</h1>
        <p>Platform status, data services and demo controls.</p>
      </div>

      {loading ? <Loading /> : (
        <div className="stats">
          <Stat k="Customers" v={c.customers ?? "—"} sub={`${c.accounts ?? 0} accounts`} accent="blue" />
          <Stat k="Ledger Events" v={(c.ledger_events ?? 0).toLocaleString()} sub={`${c.transactions ?? 0} transactions`} />
          <Stat k="Endpoints" v={c.endpoints ?? "—"} sub={`${c.vulnerabilities ?? 0} disclosures`} />
          <Stat k="Investigations" v={c.investigations ?? "—"} sub="active cases" accent="red" />
        </div>
      )}

      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 18 }}>
        <Card title="Services" icon="integrations">
          <div style={{ fontSize: 13.5, lineHeight: 2 }}>
            <div className="between"><span className="muted">Database</span><span className="chip"><i className="status-dot" /> {i.database?.engine?.toUpperCase()} · {i.database?.connected ? "connected" : "offline"}</span></div>
            <div className="between"><span className="muted">Database name</span><b>{i.database?.database}</b></div>
            <div className="between"><span className="muted">AI provider</span><span className="chip">{titleCase(ai.provider || "offline")}</span></div>
            <div className="between"><span className="muted">AI model</span><b style={{ fontSize: 12 }}>{ai.model}</b></div>
            <div className="between"><span className="muted">AI live</span><b>{ai.live ? "Yes (OpenRouter)" : "Offline grounded fallback"}</b></div>
            <div className="between"><span className="muted">Version</span><b>{i.version}</b></div>
            <div className="between"><span className="muted">Environment</span><b>{i.environment}</b></div>
          </div>
        </Card>

        <Card title="Demo Controls" icon="play">
          <p className="muted" style={{ fontSize: 13, marginBottom: 14 }}>
            Regenerate the synthetic banking ecosystem and re-run every intelligence engine end to end.
          </p>
          <div className="grid" style={{ gap: 10 }}>
            <button className="btn primary" disabled={!!busy} onClick={() => run("rebuild", api.rebuild, "Full rebuild complete")}>
              <Icon name="refresh" size={15} /> {busy === "rebuild" ? "Rebuilding…" : "Full rebuild (seed + detect + enrich)"}
            </button>
            <button className="btn" disabled={!!busy} onClick={() => run("pipeline", api.runPipeline, "Detection pipeline complete")}>
              <Icon name="watchtower" size={15} /> {busy === "pipeline" ? "Running…" : "Run detection pipeline"}
            </button>
            <button className="btn" disabled={!!busy} onClick={() => run("seed", api.reseed, "Ecosystem reseeded")}>
              <Icon name="cpu" size={15} /> {busy === "seed" ? "Seeding…" : "Reseed ecosystem only"}
            </button>
          </div>
        </Card>
      </div>
    </div>
  );
}
