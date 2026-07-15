import React, { useEffect, useState, useCallback } from "react";
import { NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { Icon, ToastProvider, useToast, useAsync } from "./ui";
import { api } from "./api";

import Queue from "./pages/Queue";
import Workspace from "./pages/Workspace";
import Watchtower from "./pages/Watchtower";
import BlastRadius from "./pages/BlastRadius";
import RiskMemory from "./pages/RiskMemory";
import KnowledgeGraphPage from "./pages/KnowledgeGraph";
import Reports from "./pages/Reports";
import Integrations from "./pages/Integrations";
import Settings from "./pages/Settings";

const NAV = [
  { to: "/", icon: "queue", label: "Investigation Queue", end: true },
  { to: "/watchtower", icon: "watchtower", label: "Watchtower" },
  { to: "/blast-radius", icon: "blast", label: "Blast Radius" },
  { to: "/risk-memory", icon: "risk", label: "Risk Memory" },
  { to: "/knowledge-graph", icon: "graph", label: "Knowledge Graph" },
  { to: "/reports", icon: "reports", label: "Reports" },
  { to: "/integrations", icon: "integrations", label: "Integrations" },
  { to: "/settings", icon: "settings", label: "Settings" },
];

function useTheme(): [string, () => void] {
  const [theme, setTheme] = useState(() => localStorage.getItem("argus-theme") || "dark");
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("argus-theme", theme);
  }, [theme]);
  return [theme, () => setTheme((t) => (t === "dark" ? "light" : "dark"))];
}

function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const nav = useNavigate();
  useEffect(() => {
    if (!open) { setQ(""); setResults([]); return; }
    const t = setTimeout(async () => {
      if (q.trim().length < 1) { setResults([]); return; }
      try { const d: any = await api.investigations({ search: q, page_size: 6 }); setResults(d); }
      catch { setResults([]); }
    }, 180);
    return () => clearTimeout(t);
  }, [q, open]);
  if (!open) return null;
  const go = (path: string) => { onClose(); nav(path); };
  return (
    <div className="cmdk-overlay" onClick={onClose}>
      <div className="cmdk" onClick={(e) => e.stopPropagation()}>
        <input autoFocus placeholder="Search investigations, or jump to a page…" value={q}
               onChange={(e) => setQ(e.target.value)}
               onKeyDown={(e) => e.key === "Escape" && onClose()} />
        <div className="cmdk-list">
          {results.map((r) => (
            <div key={r.code} className="cmdk-item" onClick={() => go(`/investigation/${r.code}`)}>
              <span className="c">{r.code}</span>
              <span>{r.title}</span>
            </div>
          ))}
          {results.length === 0 && NAV.map((n) => (
            <div key={n.to} className="cmdk-item" onClick={() => go(n.to)}>
              <Icon name={n.icon} size={15} /> {n.label}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Shell() {
  const [theme, toggle] = useTheme();
  const [cmd, setCmd] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);
  const nav = useNavigate();
  const toast = useToast();
  const { data: summary, reload: reloadSummary } = useAsync(() => api.summary(), []);
  const { data: ready } = useAsync(() => api.ready(), []);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setCmd((v) => !v); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  const rebuild = useCallback(async () => {
    if (rebuilding) return;
    setRebuilding(true);
    toast.push("Rebuilding demo: seeding ecosystem + running engines…", "info");
    try { await api.rebuild(); toast.push("Demo rebuilt. Investigations regenerated.", "ok"); reloadSummary(); nav("/"); }
    catch (e: any) { toast.push(e.message, "err"); }
    finally { setRebuilding(false); }
  }, [rebuilding]);

  const active = (ready as any)?.ready;
  const crit = (summary as any)?.critical || 0;

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="logo">A</div>
          <div className="name">ARGUS<small>Decision Intelligence</small></div>
        </div>
        <nav className="nav">
          <div className="nav-label">Investigate</div>
          {NAV.slice(0, 5).map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end}
                     className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
              <Icon name={n.icon} size={17} /> {n.label}
              {n.to === "/" && crit > 0 && <span className="badge-count">{crit}</span>}
            </NavLink>
          ))}
          <div className="nav-label">Platform</div>
          {NAV.slice(5).map((n) => (
            <NavLink key={n.to} to={n.to}
                     className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
              <Icon name={n.icon} size={17} /> {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="tagline">"We don't generate alerts.<br />We generate decisions."</div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="search" onClick={() => setCmd(true)}>
            <Icon name="search" size={16} />
            <input placeholder="Search investigations, customers, endpoints…" readOnly />
            <span className="kbd">⌘K</span>
          </div>
          <div className="topbar-actions">
            <button className="btn sm primary" onClick={rebuild} disabled={rebuilding}>
              <Icon name="refresh" size={14} /> {rebuilding ? "Rebuilding…" : "Rebuild demo"}
            </button>
            <span className={`status-dot ${active ? "" : "down"}`}>
              <i /> {active ? "Operational" : "DB offline"}
            </span>
            <button className="icon-btn" onClick={toggle} title="Toggle theme">
              <Icon name={theme === "dark" ? "sun" : "moon"} size={16} />
            </button>
            <button className="icon-btn" title="Notifications"><Icon name="bell" size={16} /></button>
            <div className="avatar">SA</div>
          </div>
        </header>

        <Routes>
          <Route path="/" element={<Queue />} />
          <Route path="/investigation/:code" element={<Workspace />} />
          <Route path="/watchtower" element={<Watchtower />} />
          <Route path="/blast-radius" element={<BlastRadius />} />
          <Route path="/risk-memory" element={<RiskMemory />} />
          <Route path="/knowledge-graph" element={<KnowledgeGraphPage />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/integrations" element={<Integrations />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </div>
      <CommandPalette open={cmd} onClose={() => setCmd(false)} />
    </div>
  );
}

export default function App() {
  return <ToastProvider><Shell /></ToastProvider>;
}
