import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { api, inr, titleCase } from "../api";
import { Icon, Severity, Card, Loading, useAsync, useToast } from "../ui";

export default function BlastRadius() {
  const nav = useNavigate();
  const toast = useToast();
  const [busy, setBusy] = useState("");
  const { data: disc, loading: dl } = useAsync(() => api.disclosures(), []);
  const { data: inv, loading: il, reload } = useAsync(() => api.blastInvestigations(), []);
  const disclosures: any[] = (disc as any) || [];
  const recon: any[] = (inv as any)?.reconstructions || [];

  const run = async (ref: string) => {
    setBusy(ref);
    try { await api.reconstruct(ref); toast.push(`Reconstructed ${ref}`, "ok"); reload(); }
    catch (e: any) { toast.push(e.message, "err"); } finally { setBusy(""); }
  };

  return (
    <div className="page">
      <div className="page-head">
        <h1>Blast Radius</h1>
        <p>Retrospective exposure reconstruction — deterministic replay of the immutable event ledger after a disclosure.</p>
      </div>

      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 18 }}>
        <Card title="Disclosure Events" icon="alert" pad={false}>
          {dl ? <Loading /> : (
            <div style={{ padding: 8 }}>
              {disclosures.map((v) => (
                <div key={v.vuln_ref} className="ev-item" style={{ margin: 8 }}>
                  <div className="t">
                    <span>{v.vuln_ref}</span>
                    <Severity level={v.severity} />
                  </div>
                  <div className="d" style={{ marginBottom: 8 }}>{v.title}</div>
                  <div className="row wrap" style={{ gap: 6, marginBottom: 8 }}>
                    <span className="chip">{titleCase(v.disclosure_type)}</span>
                    <span className="chip">{v.affected_endpoint}</span>
                    {v.affected_algorithm && <span className="chip">{v.affected_algorithm}</span>}
                    {v.cvss && <span className="chip">CVSS {v.cvss}</span>}
                  </div>
                  <button className="btn sm primary" disabled={!!busy} onClick={() => run(v.vuln_ref)}>
                    <Icon name="blast" size={13} /> {busy === v.vuln_ref ? "Reconstructing…" : "Reconstruct exposure"}
                  </button>
                </div>
              ))}
              {!disclosures.length && <p className="muted" style={{ padding: 16 }}>No disclosures.</p>}
            </div>
          )}
        </Card>

        <Card title="Reconstructions" icon="blast" pad={false}>
          {il ? <Loading /> : (
            <div className="table-wrap">
              <table className="data">
                <thead><tr><th>Case</th><th>Exposure</th><th>Customers</th><th>Severity</th></tr></thead>
                <tbody>
                  {recon.map((r) => (
                    <tr key={r.code} onClick={() => nav(`/investigation/${r.code}`)}>
                      <td className="code-cell">{r.code}</td>
                      <td className="tnum" style={{ fontWeight: 600 }}>{inr(r.financial_exposure)}</td>
                      <td className="tnum">{r.affected_customers}</td>
                      <td><Severity level={r.severity} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!recon.length && <p className="muted" style={{ padding: 16 }}>No reconstructions yet — trigger one from a disclosure.</p>}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
