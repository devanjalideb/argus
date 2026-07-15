import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, titleCase, when } from "../api";
import { Icon, Card, Loading, useToast } from "../ui";

export default function Reports() {
  const [sp] = useSearchParams();
  const toast = useToast();
  const [invs, setInvs] = useState<any[]>([]);
  const [code, setCode] = useState(sp.get("code") || "");
  const [rtype, setRtype] = useState("executive");
  const [fmt, setFmt] = useState("pdf");
  const [reports, setReports] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = () => api.reports().then((d: any) => setReports(d)).finally(() => setLoading(false));
  useEffect(() => {
    api.investigations({ page_size: 50 }).then((d: any) => { setInvs(d); if (!code && d[0]) setCode(d[0].code); }).catch(() => {});
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const gen = async () => {
    if (!code) return;
    setBusy(true);
    try { await api.generateReport(code, rtype, fmt); toast.push(`${titleCase(rtype)} ${fmt.toUpperCase()} generated`, "ok"); load(); }
    catch (e: any) { toast.push(e.message, "err"); } finally { setBusy(false); }
  };

  return (
    <div className="page">
      <div className="page-head">
        <h1>Reports</h1>
        <p>Professional, evidence-based investigation documents for executives, auditors and compliance.</p>
      </div>

      <div className="grid" style={{ gridTemplateColumns: "320px 1fr", gap: 18 }}>
        <Card title="Generate Report" icon="file">
          <div className="field"><label>Investigation</label>
            <select value={code} onChange={(e) => setCode(e.target.value)}>
              {invs.map((i) => <option key={i.code} value={i.code}>{i.code}</option>)}
            </select></div>
          <div className="field"><label>Report Type</label>
            <select value={rtype} onChange={(e) => setRtype(e.target.value)}>
              <option value="executive">Executive</option>
              <option value="technical">Technical</option>
              <option value="compliance">Compliance</option>
            </select></div>
          <div className="field"><label>Format</label>
            <select value={fmt} onChange={(e) => setFmt(e.target.value)}>
              <option value="pdf">PDF</option><option value="json">JSON</option><option value="csv">CSV</option>
            </select></div>
          <button className="btn primary" style={{ width: "100%" }} onClick={gen} disabled={busy}>
            <Icon name="file" size={15} /> {busy ? "Generating…" : "Generate report"}
          </button>
        </Card>

        <Card title="Generated Reports" icon="reports" pad={false}>
          {loading ? <Loading /> : (
            <div className="table-wrap">
              <table className="data">
                <thead><tr><th>Report</th><th>Case</th><th>Type</th><th>Format</th><th>v</th><th>Generated</th><th></th></tr></thead>
                <tbody>
                  {reports.map((r) => (
                    <tr key={r.id} style={{ cursor: "default" }}>
                      <td>{r.title}</td>
                      <td className="code-cell">{r.investigation}</td>
                      <td>{titleCase(r.report_type)}</td>
                      <td><span className="chip">{r.export_format.toUpperCase()}</span></td>
                      <td className="tnum">{r.version}</td>
                      <td className="muted">{when(r.created_at)}</td>
                      <td><a className="btn sm" href={api.downloadUrl(r.id)} target="_blank" rel="noreferrer"><Icon name="download" size={13} /> Download</a></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!reports.length && <p className="muted" style={{ padding: 16 }}>No reports generated yet.</p>}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
