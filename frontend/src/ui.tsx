import React, { createContext, useContext, useState, useCallback } from "react";

// ---------------------------------------------------------------- icons (SVG, no emoji)
const PATHS: Record<string, string> = {
  queue: "M3 5h18M3 12h18M3 19h18",
  workspace: "M4 4h16v6H4zM4 14h7v6H4zM15 14h5v6h-5z",
  watchtower: "M12 5c-5 0-9 4.5-9 7s4 7 9 7 9-4.5 9-7-4-7-9-7zM12 15a3 3 0 100-6 3 3 0 000 6z",
  blast: "M12 2v3M12 19v3M2 12h3M19 12h3M12 8a4 4 0 100 8 4 4 0 000-8zM5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2",
  risk: "M12 2a5 5 0 00-5 5v1a4 4 0 00-2 7 4 4 0 004 4h6a4 4 0 004-4 4 4 0 00-2-7V7a5 5 0 00-5-5z",
  graph: "M6 9a3 3 0 100-6 3 3 0 000 6zM18 9a3 3 0 100-6 3 3 0 000 6zM12 21a3 3 0 100-6 3 3 0 000 6zM7.5 7.5l3 6M16.5 7.5l-3 6",
  reports: "M14 3H6a2 2 0 00-2 2v14a2 2 0 002 2h12a2 2 0 002-2V9zM14 3v6h6M8 13h8M8 17h8M8 9h2",
  integrations: "M9 2v6M15 2v6M6 8h12v3a6 6 0 01-12 0zM12 17v5",
  settings: "M12 15a3 3 0 100-6 3 3 0 000 6zM19 12a7 7 0 00-.1-1l2-1.6-2-3.4-2.4 1a7 7 0 00-1.7-1l-.4-2.5h-4l-.4 2.5a7 7 0 00-1.7 1l-2.4-1-2 3.4 2 1.6a7 7 0 000 2l-2 1.6 2 3.4 2.4-1a7 7 0 001.7 1l.4 2.5h4l.4-2.5a7 7 0 001.7-1l2.4 1 2-3.4-2-1.6a7 7 0 00.1-1z",
  search: "M11 19a8 8 0 100-16 8 8 0 000 16zM21 21l-4.3-4.3",
  bell: "M18 8a6 6 0 00-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 01-3.4 0",
  command: "M9 3a3 3 0 010 6H6a3 3 0 010-6zM15 3a3 3 0 000 6h3a3 3 0 000-6zM9 21a3 3 0 000-6H6a3 3 0 000 6zM15 21a3 3 0 010-6h3a3 3 0 010 6zM9 9h6v6H9z",
  shield: "M12 2l8 3v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V5z",
  alert: "M12 2l10 18H2zM12 9v5M12 17h.01",
  arrow: "M5 12h14M13 6l6 6-6 6",
  download: "M12 3v12M8 11l4 4 4-4M4 21h16",
  refresh: "M21 12a9 9 0 11-3-6.7L21 8M21 3v5h-5",
  check: "M20 6L9 17l-5-5",
  x: "M18 6L6 18M6 6l12 12",
  freeze: "M12 2v20M4 6l16 12M20 6L4 18M2 12h20",
  sun: "M12 7a5 5 0 100 10 5 5 0 000-10zM12 1v2M12 21v2M4 4l1.5 1.5M18.5 18.5L20 20M1 12h2M21 12h2M4 20l1.5-1.5M18.5 5.5L20 4",
  moon: "M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z",
  activity: "M22 12h-4l-3 9L9 3l-3 9H2",
  user: "M20 21a8 8 0 10-16 0M12 11a4 4 0 100-8 4 4 0 000 8z",
  cpu: "M6 6h12v12H6zM9 9h6v6H9zM9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2",
  lock: "M6 11h12v10H6zM8 11V7a4 4 0 018 0v4",
  play: "M6 4l14 8-14 8z",
  clock: "M12 22a10 10 0 100-20 10 10 0 000 20zM12 6v6l4 2",
  file: "M14 3H6a2 2 0 00-2 2v14a2 2 0 002 2h12a2 2 0 002-2V9zM14 3v6h6",
  external: "M15 3h6v6M10 14L21 3M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6",
};

export function Icon({ name, size = 18 }: { name: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <path d={PATHS[name] || ""} />
    </svg>
  );
}

// ---------------------------------------------------------------- badges
export const Severity = ({ level }: { level: string }) => (
  <span className={`badge sev-${level}`}><i />{(level || "").toUpperCase()}</span>
);
export const Priority = ({ p }: { p: string }) => (
  <span className={`pill ${p === "P1" ? "p1" : p === "P2" ? "p2" : ""}`}>{p}</span>
);
export const Chip = ({ children }: { children: React.ReactNode }) => <span className="chip">{children}</span>;

// ---------------------------------------------------------------- primitives
export const Card = ({ title, icon, actions, children, pad = true }: any) => (
  <div className="card">
    {title && (
      <div className="card-head">
        <h3>{icon && <Icon name={icon} size={15} />}{title}</h3>
        {actions}
      </div>
    )}
    <div className={pad ? "card-pad" : ""}>{children}</div>
  </div>
);

export const Stat = ({ k, v, sub, accent }: any) => (
  <div className={`stat ${accent ? `accent-${accent}` : ""}`}>
    <div className="k">{k}</div>
    <div className="v tnum">{v}</div>
    {sub && <div className="sub">{sub}</div>}
  </div>
);

export const Spinner = () => <div className="spinner" />;
export const Loading = () => <div className="loading"><Spinner /></div>;
export const Empty = ({ title, hint, icon = "queue" }: any) => (
  <div className="empty"><Icon name={icon} size={40} /><h3>{title}</h3>{hint && <div>{hint}</div>}</div>
);

export const Bar = ({ pct }: { pct: number }) => (
  <div className="conf-bar"><i style={{ width: `${Math.max(2, Math.min(100, pct))}%` }} /></div>
);

// ---------------------------------------------------------------- toasts
type Toast = { id: number; msg: string; kind: "ok" | "err" | "info" };
const ToastCtx = createContext<{ push: (m: string, k?: Toast["kind"]) => void }>({ push: () => {} });
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((msg: string, kind: Toast["kind"] = "info") => {
    const id = Date.now() + Math.random();
    setItems((s) => [...s, { id, msg, kind }]);
    setTimeout(() => setItems((s) => s.filter((t) => t.id !== id)), 4000);
  }, []);
  return (
    <ToastCtx.Provider value={{ push }}>
      {children}
      <div className="toasts">
        {items.map((t) => <div key={t.id} className={`toast ${t.kind}`}>{t.msg}</div>)}
      </div>
    </ToastCtx.Provider>
  );
}

// ---------------------------------------------------------------- data hook
export function useAsync<T>(fn: () => Promise<T>, deps: any[] = []): {
  data: T | null; loading: boolean; error: string | null; reload: () => void;
} {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  React.useEffect(() => {
    let alive = true;
    setLoading(true); setError(null);
    fn().then((d) => alive && setData(d)).catch((e) => alive && setError(e.message))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { data, loading, error, reload: () => setTick((t) => t + 1) };
}
