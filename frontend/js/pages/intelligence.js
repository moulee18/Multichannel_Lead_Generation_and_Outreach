import { api } from "../api.js";
import {
  escapeHtml,
  showChannelExplainerModal,
  showLeadEvidencePassportModal,
  showScoreExplainerModal,
  showToast,
  statusBadge,
} from "../components/modals.js";

export async function renderIntelligencePage(container) {
  container.innerHTML = `<div class="loading-state">Loading Ranked Leads & Explainable Scoring...</div>`;
  try {
    const data = await api.getRankedLeads(true);
    const items = data.items || [];

    const rowsHtml = items
      .map(
        (item) => `
      <tr>
        <td><strong>#${item.rank_position || "—"}</strong></td>
        <td>
          <strong>${escapeHtml(item.creator_name)}</strong><br/>
          <small>${escapeHtml(item.category)} &bull; ${escapeHtml(item.country)}</small>
        </td>
        <td>${statusBadge(item.priority_tier)}</td>
        <td>
          <strong style="font-size:15px;color:#0284c7;">${item.total_score}</strong> / 100
          <br/><small>v${escapeHtml(item.scoring_version)}</small>
        </td>
        <td>
          <small>
            Rel: <strong>${item.product_relevance_score}</strong>/30 |
            Need: <strong>${item.need_evidence_score}</strong>/25 |
            Comm: <strong>${item.commercial_readiness_score}</strong>/20 |
            Act: <strong>${item.publishing_activity_score}</strong>/15 |
            Ctc: <strong>${item.contact_quality_score}</strong>/10
          </small>
        </td>
        <td>
          <span class="badge badge-success">${escapeHtml(item.primary_channel || "N/A")}</span>
          ${item.backup_channel ? `<span class="badge badge-info">Backup: ${escapeHtml(item.backup_channel)}</span>` : `<span class="badge badge-warning">No Backup</span>`}
        </td>
        <td>
          ${(item.suitable_capabilities || []).map((c) => `<code>${escapeHtml(c)}</code>`).join(", ") || "—"}
          <br/>
          ${item.hallucination_guard_passed ? '<span class="badge badge-success">AI Guard Passed</span>' : '<span class="badge badge-danger">Guard Flagged</span>'}
        </td>
        <td>
          <div style="display:flex;gap:5px;flex-wrap:wrap;">
            <button class="btn btn-primary btn-sm score-exp-btn" data-id="${escapeHtml(item.creator_id)}">Score Breakdown</button>
            <button class="btn btn-teal btn-sm chan-exp-btn" data-id="${escapeHtml(item.creator_id)}">Channel Explainer</button>
            <button class="btn btn-secondary btn-sm pass-exp-btn" data-id="${escapeHtml(item.creator_id)}">Passport</button>
          </div>
        </td>
      </tr>
    `
      )
      .join("");

    container.innerHTML = `
      <div class="card">
        <div class="card-header">
          <div>
            <span class="card-title">Agent 2 — Ranked Qualified Creators & Priority Classification (${items.length} Scored)</span>
            <p style="font-size:12px;color:#64748b;">
              Project-defined 100-point model: Product Relevance (30), Need Evidence (25), Commercial Readiness (20), Publishing Activity (15), Contact Quality (10). Top 25 eligible leads are classified as Priority A.
            </p>
          </div>
          <button class="btn btn-primary" id="btn-recompute-intel">Recompute Scores & Intelligence</button>
        </div>

        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Creator & Segment</th>
                <th>Priority Tier</th>
                <th>Total Score</th>
                <th>Component Breakdown</th>
                <th>Primary & Backup Channel</th>
                <th>Product Fit & AI Guard</th>
                <th>Explainability Actions</th>
              </tr>
            </thead>
            <tbody>
              ${rowsHtml || '<tr><td colspan="8" class="empty-state">No qualified creators scored yet. Run Discovery or Pipeline first.</td></tr>'}
            </tbody>
          </table>
        </div>
      </div>
    `;

    document.getElementById("btn-recompute-intel")?.addEventListener("click", async (e) => {
      e.target.disabled = true;
      showToast("Recomputing Agent 2 lead scores, channel decisions & intelligence...", "info");
      try {
        const res = await api.runIntelligence({ regenerate_outreach: false });
        showToast(`Scored ${res.total_scored} leads (${res.priority_a_count} Priority A)!`, "success");
        await renderIntelligencePage(container);
      } catch (err) {
        showToast(err.message, "error");
        e.target.disabled = false;
      }
    });

    container.querySelectorAll(".score-exp-btn").forEach((btn) => {
      btn.addEventListener("click", () => showScoreExplainerModal(btn.dataset.id));
    });
    container.querySelectorAll(".chan-exp-btn").forEach((btn) => {
      btn.addEventListener("click", () => showChannelExplainerModal(btn.dataset.id));
    });
    container.querySelectorAll(".pass-exp-btn").forEach((btn) => {
      btn.addEventListener("click", () => showLeadEvidencePassportModal(btn.dataset.id));
    });
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Error loading Lead Intelligence: ${escapeHtml(err.message)}</div>`;
  }
}
