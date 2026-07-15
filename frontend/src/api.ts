// Centralized API client. Every component talks to the backend only through here.
const BASE = "/api/v1";

async function req<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  let body: any = null;
  try { body = await res.json(); } catch { /* non-json */ }
  if (!res.ok || (body && body.success === false)) {
    const msg = body?.error?.message || `Request failed (${res.status})`;
    throw new Error(msg);
  }
  return (body?.data ?? body) as T;
}

const post = (p: string, b?: any) =>
  req(p, { method: "POST", body: b ? JSON.stringify(b) : undefined });

export const api = {
  // system
  info: () => req("/system/info"),
  ready: () => req("/system/ready"),

  // investigations
  investigations: (q: Record<string, any> = {}) =>
    req(`/investigations?${new URLSearchParams(q as any)}`),
  summary: () => req("/investigations/summary"),
  commandCenter: () => req("/investigations/command-center"),
  investigation: (code: string) => req(`/investigations/${code}`),
  assign: (code: string, analyst: string) => post(`/investigations/${code}/assign`, { analyst }),
  setStatus: (code: string, status: string, note?: string) =>
    post(`/investigations/${code}/status`, { status, note }),
  escalate: (code: string, note?: string) => post(`/investigations/${code}/escalate`, { note }),
  close: (code: string, resolution: string) => post(`/investigations/${code}/close`, { resolution }),

  // watchtower
  watchtowerStatus: () => req("/watchtower/status"),
  watchtowerDetections: () => req("/watchtower/detections"),
  watchtowerAnalyze: () => post("/watchtower/analyze"),

  // blast radius
  disclosures: () => req("/blast-radius/disclosures"),
  blastInvestigations: () => req("/blast-radius/investigations"),
  reconstruct: (ref: string) => post(`/blast-radius/reconstruct/${ref}`),

  // risk memory
  riskSearch: (q: string) => req(`/risk-memory/search?q=${encodeURIComponent(q)}`),
  riskCustomer: (ref: string) => req(`/risk-memory/customer/${ref}`),
  riskRecompute: () => post("/risk-memory/recompute"),

  // business impact + ai + graph
  impact: (code: string) => req(`/business-impact/${code}`),
  aiStatus: () => req("/ai/status"),
  aiGenerate: (code: string) => post(`/ai/${code}/generate`),
  graph: (code: string) => req(`/knowledge-graph/investigation/${code}`),
  nodeContext: (t: string, id: string) => req(`/knowledge-graph/node/${t}/${id}`),

  // reports
  reports: (code?: string) => req(`/reports${code ? `?code=${code}` : ""}`),
  generateReport: (code: string, report_type: string, export_format: string) =>
    post(`/reports/${code}/generate`, { report_type, export_format }),
  downloadUrl: (id: number) => `${BASE}/reports/${id}/download`,

  // events + synthetic
  events: (q: Record<string, any> = {}) => req(`/events?${new URLSearchParams(q as any)}`),
  synthStatus: () => req("/synthetic/status"),
  rebuild: () => post("/synthetic/rebuild"),
  runPipeline: () => post("/synthetic/pipeline", { enrich: true }),
  reseed: () => post("/synthetic/seed", {}),
};

// ---- formatting helpers ----
export const inr = (x: number | null | undefined): string => {
  const n = Number(x || 0);
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`;
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(2)} L`;
  return `₹${n.toLocaleString("en-IN")}`;
};
export const when = (iso?: string | null): string => {
  if (!iso) return "—";
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
};
export const titleCase = (s: string) =>
  (s || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
