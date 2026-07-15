# ARGUS — Judge Demonstration Script

**Goal:** guide judges through *one continuous investigation story*, not a feature tour.
Total time ≈ 6–7 minutes. Speak the business problem first, let each investigation tell itself.

Before you start: click **Rebuild demo** (top-right) so the queue is fresh. Everything is
deterministic — the same scenarios appear every run.

---

## 0. The one-sentence pitch
> "ARGUS transforms fragmented banking cybersecurity data into explainable, evidence-driven
> business decisions — combining behavioural intelligence, historical exposure reconstruction,
> executive impact analysis and AI explainability in one investigation platform."

## 1. Investigation Queue (the homepage)
- Not a dashboard of charts — a prioritized **work queue**. Point out the top metrics
  (active / critical / today).
- Note investigations come from **two engines**: Watchtower (live) and Blast Radius
  (retrospective). Sorted so business impact rises to the top.

## 2. Watchtower — Account Takeover  *(open ARG- account_takeover, ~₹3 Cr, 94%)*
- **Executive Summary** (read it aloud): a trusted customer, new device, foreign country, a
  transfer ~15× their historical average.
- **Timeline** → **Evidence**: emphasize the investigation came from *correlated* deviations,
  not one alert (new device + geo + amount + IP reputation).
- **Confidence Breakdown**: show it's decomposed — Isolation Forest score *plus* interpretable
  factors. "Analysts see exactly why it's 94%, not a black box."
- **Business Impact**: ₹ exposure, executive priority P1, regulatory flags.

## 3. Risk Memory
- Search the affected customer. "ARGUS compares each customer against **their own** history —
  trusted devices, normal regions, typical amounts — which is why false positives stay low."

## 4. Knowledge Graph
- Open the graph for the investigation. Click the customer / attacker device / IP nodes.
  "Relationship context, not decoration."

## 5. Blast Radius — the headline  *(open the Sweet32 retrospective, ~₹25 Cr, 96%)*
- Switch framing: "This isn't live detection. A weak cipher (Sweet32 / 3DES) was just disclosed
  on a legacy payments endpoint. The question executives ask is: *what already went through it?*"
- Show the reconstruction: **~941 transactions, ₹25 crore, 45 customers** — deterministic replay
  of the immutable ledger over the exposure window. **PCI-DSS** flagged automatically.
- Emphasize: **exact, auditable, reproducible** — SQL, not a guess.

## 6. Quantum — Harvest-Now-Decrypt-Later  *(open the quantum_exposure investigation)*
- "RSA-2048 key exchange on the encryption gateway. Under harvest-now-decrypt-later, ciphertext
  captured today is decryptable once quantum is practical." ARGUS reconstructs the **sensitive
  population at risk** and labels it *potential future exposure* (not confirmed) — honest about
  certainty.

## 7. Explainable AI
- On any investigation, flip the **AI Decision** tabs (Executive / Technical / Confidence /
  Evidence / Actions). "The model didn't *detect* anything — every sentence is grounded in the
  structured evidence the engines produced. It explains; it never invents."

## 8. Reports
- Generate an **Executive PDF** from a Blast Radius case and download it. "Evidence-based,
  audit-ready, suitable for executives and regulators without editing."

## 9. Close the loop
- Back on the investigation: **Assign / Escalate / Close** — full audit trail. "ARGUS manages the
  entire lifecycle from ingestion to executive decision in one platform."

---

## Anticipated questions

- **Why Isolation Forest?** We mostly have examples of *legitimate* behaviour, not labelled
  fraud — Isolation Forest finds statistical outliers without needing fraud labels. It's one
  contributor to confidence, never the sole decider.
- **Why does Risk Memory reduce false positives?** Every entity is judged against its own
  baseline, not the population — ₹10L is normal for one customer, alarming for another.
- **Why is Blast Radius reconstruction, not prediction?** Many breaches are only understood after
  disclosure. Reconstruction over an immutable ledger is exact and auditable; prediction is not.
- **Why is the LLM limited to explanation?** Determinism and trust. Detection and business logic
  are deterministic and testable; the LLM only translates evidence into language, with a
  hallucination guard and an offline fallback.
- **Why a modular monolith?** Simplicity that still demonstrates the full vision; every module
  has a clean interface and could be extracted into a service later.
- **Is it really running?** Yes — `pytest` asserts the Blast Radius reconstruction equals the
  ledger ground truth exactly, and the numbers are reproducible on every machine.
