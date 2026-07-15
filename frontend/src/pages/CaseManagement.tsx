import { useNavigate } from "react-router-dom";
import { api, when, titleCase } from "../api";
import { Icon, Severity, Priority, Card, Loading, useAsync } from "../ui";

export default function CaseManagement() {
  const nav = useNavigate();
  const { data, loading } = useAsync(() => api.investigations({ page_size: 50 }), []);
  const rows: any[] = (data as any) || [];
  return (
    <div className="page">
      <div className="page-head">
        <h1>Case Management</h1>
        <p>Assign, track, and resolve investigations across their full lifecycle.</p>
      </div>
      <Card title="All Cases" icon="file" pad={false}>
        {loading ? <Loading /> : (
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Case</th><th>Investigation</th><th>Severity</th><th>Status</th><th>Owner</th><th>Priority</th><th>Updated</th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.code} onClick={() => nav(`/investigation/${r.code}`)}>
                    <td className="code-cell">{r.code}</td>
                    <td style={{ color: "var(--text-primary)", fontWeight: 500 }}>{r.title}</td>
                    <td><Severity level={r.severity} /></td>
                    <td>{titleCase(r.status)}</td>
                    <td className="muted">{r.owner || "Unassigned"}</td>
                    <td><Priority p={r.business_priority} /></td>
                    <td className="muted">{when(r.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
