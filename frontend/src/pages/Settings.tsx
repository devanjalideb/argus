import { api, titleCase } from "../api";
import { Card, Icon, useAsync } from "../ui";

const PLATFORM_SECURITY = [
  ["Role-Based Access Control", "Analyst, security-manager and CISO roles gate every action and view."],
  ["Encrypted Investigation Storage", "Investigations and their evidence are held in encrypted storage at rest."],
  ["Immutable Audit Trail", "Every analyst decision is appended to a tamper-evident action ledger."],
  ["Evidence Integrity Verification", "Generated reports carry SHA-256 integrity hashes; evidence is append-only."],
  ["Secure AI Narration (Grounded Responses Only)", "The AI explains structured evidence only — it never fabricates facts."],
];

export default function Settings() {
  const { data: info } = useAsync(() => api.info(), []);
  const i: any = info || {};

  const Row = ({ k, v }: any) => (
    <div className="between" style={{ padding: "9px 0", borderBottom: "1px solid var(--border)" }}>
      <span className="muted">{k}</span><b style={{ fontSize: 13 }}>{v}</b>
    </div>
  );

  return (
    <div className="page">
      <div className="page-head">
        <h1>Settings</h1>
        <p>Application configuration and environment.</p>
      </div>

      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 18, alignItems: "start" }}>
        <Card title="Application" icon="settings">
          <Row k="Platform" v={i.app || "ARGUS"} />
          <Row k="Version" v={i.version || "1.0.0"} />
          <Row k="Environment" v={titleCase(i.environment || "development")} />
          <Row k="API prefix" v={i.api_prefix || "/api/v1"} />
        </Card>

        <Card title="AI Decision Layer" icon="cpu">
          <Row k="Provider" v={i.ai?.provider === "gemini" ? "Google Gemini" : titleCase(i.ai?.provider || "offline fallback")} />
          <Row k="Model" v={i.ai?.model || "—"} />
          <Row k="Live" v={i.ai?.live ? "Yes" : "Offline grounded narrator"} />
          <Row k="Grounding" v="Strict — explains evidence only" />
        </Card>

        <Card title="Database" icon="risk">
          <Row k="Engine" v={(i.database?.engine || "mysql").toUpperCase()} />
          <Row k="Host" v={i.database?.host || "localhost"} />
          <Row k="Database" v={i.database?.database || "argus"} />
          <Row k="Connected" v={i.database?.connected ? "Yes" : "No"} />
        </Card>

        <Card title="About" icon="shield">
          <p style={{ fontSize: 13.5, lineHeight: 1.7, color: "var(--text-2)" }}>
            <b>ARGUS</b> transforms fragmented banking cybersecurity data into explainable,
            evidence-driven business decisions — combining behavioural intelligence
            (Watchtower), historical exposure reconstruction (Blast Radius), executive impact
            analysis and AI-powered explainability within a unified investigation platform.
          </p>
          <p className="tagline" style={{ marginTop: 12 }}>"We don't generate alerts. We generate decisions."</p>
        </Card>

        <div style={{ gridColumn: "1 / -1" }}>
          <Card title="Platform Security" icon="lock">
            <p className="muted" style={{ fontSize: 12.5, marginBottom: 14 }}>
              ARGUS's own security posture — the controls that protect investigation data and
              keep AI-generated conclusions trustworthy.
            </p>
            <div className="why-list">
              {PLATFORM_SECURITY.map(([label, detail]) => (
                <div className="why-item" key={label}>
                  <span className="ic"><Icon name="check" size={15} /></span>
                  <div>
                    <div className="wt">{label}</div>
                    <div className="wd">{detail}</div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
