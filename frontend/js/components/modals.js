/**
 * Reusable Modal Drawers (Lead Evidence Passport, Explainable Lead Scoring, Contact Channel Explainer) & Toast Notifications
 */
import { api } from "../api.js";

export function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => {
    el.remove();
  }, 4200);
}

export function openModal(title, htmlContent) {
  const backdrop = document.getElementById("global-modal-backdrop");
  const titleEl = document.getElementById("modal-title");
  const bodyEl = document.getElementById("modal-body");
  if (!backdrop || !titleEl || !bodyEl) return;
  titleEl.textContent = title;
  bodyEl.innerHTML = htmlContent;
  backdrop.classList.remove("hidden");
}

export function closeModal() {
  const backdrop = document.getElementById("global-modal-backdrop");
  if (backdrop) backdrop.classList.add("hidden");
}

export function statusBadge(status) {
  const s = String(status || "").toUpperCase();
  if (s === "QUALIFIED" || s === "PASSED" || s === "COMPLETED" || s === "READY" || s === "APPROVED" || s === "VERIFIED") {
    return `<span class="badge badge-success">${s}</span>`;
  }
  if (s === "NEEDS_REVIEW" || s === "WARNING" || s === "READY_WITH_WARNINGS" || s === "RUNNING" || s === "QUEUED") {
    return `<span class="badge badge-warning">${s}</span>`;
  }
  return `<span class="badge badge-danger">${s || "UNKNOWN"}</span>`;
}

export function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * Feature 1 — Lead Evidence Passport Modal
 */
export async function showLeadEvidencePassportModal(creatorId) {
  openModal("Lead Evidence Passport", `<div class="loading-state">Loading Lead Evidence Passport...</div>`);
  try {
    const data = await api.getCreatorEvidencePassport(creatorId);
    const c = data.creator;
    const v = data.verification;
    const cd = data.channel_decision;
    const sr = data.scoring_rationale;

    const claimsHtml = (data.evidence_claims || [])
      .map(
        (ev) => `
      <div class="evidence-item">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
          <strong>Criterion: <code>${escapeHtml(ev.criterion)}</code></strong>
          <div>
            ${statusBadge(ev.verification_status)}
            ${ev.is_manual_override ? '<span class="badge badge-info">Manual Review Override</span>' : ""}
          </div>
        </div>
        <p style="margin-bottom:6px;">${escapeHtml(ev.excerpt)}</p>
        <div style="font-size:11.5px;color:#475569;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;">
          <span>ID: <code>${escapeHtml(ev.id)}</code> | Checked: ${escapeHtml(ev.checked_at?.slice(0, 19))}</span>
          <a href="${escapeHtml(ev.source_url)}" target="_blank" rel="noopener" class="btn btn-secondary btn-sm">Open Source URL &nearr;</a>
        </div>
      </div>
    `
      )
      .join("");

    const breakdownHtml = (sr.breakdown || [])
      .map(
        (b) => `
      <tr>
        <td><strong>${escapeHtml(b.criterion)}</strong></td>
        <td>${b.awarded_points} / ${b.max_points}</td>
        <td>${escapeHtml(b.reasoning)}</td>
        <td>${b.source_url ? `<a href="${escapeHtml(b.source_url)}" target="_blank" rel="noopener">Source &nearr;</a>` : "—"}</td>
      </tr>
    `
      )
      .join("");

    const reviewsHtml =
      (data.review_history || []).length > 0
        ? data.review_history
            .map(
              (r) => `
          <div class="evidence-item">
            <strong>${escapeHtml(r.reviewer_username)}</strong>: ${escapeHtml(r.previous_status)} &rarr; ${statusBadge(r.new_status)}
            <p>${escapeHtml(r.notes)}</p>
            <small>${escapeHtml(r.created_at)}</small>
          </div>
        `
            )
            .join("")
        : `<p style="color:#64748b;">No manual review overrides recorded.</p>`;

    const html = `
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
          <div>
            <h3 style="font-size:17px;">${escapeHtml(c.name)}</h3>
            <p style="color:#475569;font-size:12.5px;">
              ${escapeHtml(c.category)} &bull; ${escapeHtml(c.country)} &bull; Platform ID: <code>${escapeHtml(c.platform_id)}</code>
            </p>
          </div>
          <div>
            ${statusBadge(c.qualification_status)}
            ${c.is_synthetic ? '<span class="badge badge-synthetic">SYNTHETIC DEMO</span>' : '<span class="badge badge-info">GENUINE SOURCE</span>'}
          </div>
        </div>
        <div style="margin-top:12px;display:flex;gap:10px;flex-wrap:wrap;">
          <a href="${escapeHtml(c.official_url)}" target="_blank" rel="noopener" class="btn btn-primary btn-sm">Official Profile &nearr;</a>
          <span class="badge badge-info">30d Items: ${c.items_30d}</span>
          <span class="badge badge-info">60d Long-Form: ${c.longform_60d}</span>
          <span class="badge badge-info">Score: ${sr.total_score ?? 0} (${escapeHtml(c.priority_tier || "Unranked")})</span>
        </div>
      </div>

      <div class="card">
        <div class="card-header"><span class="card-title">Primary & Backup Business Contacts</span></div>
        <p><strong>Primary Channel:</strong> ${escapeHtml(cd.primary_channel || "None")} — <code>${escapeHtml(cd.primary_contact_value || "N/A")}</code></p>
        <p><strong>Verified Backup Channel:</strong> ${escapeHtml(cd.backup_channel || "None (No guessed backup)")} — <code>${escapeHtml(cd.backup_contact_value || "N/A")}</code></p>
        <p style="margin-top:6px;font-size:12.5px;color:#475569;"><strong>Rationale:</strong> ${escapeHtml(cd.selection_reason || "")}</p>
      </div>

      <div class="card">
        <div class="card-header"><span class="card-title">Verified Evidence Claims (${(data.evidence_claims || []).length})</span></div>
        ${claimsHtml || '<div class="empty-state">No evidence claims stored.</div>'}
      </div>

      <div class="card">
        <div class="card-header"><span class="card-title">Scoring Rationale (Version ${escapeHtml(sr.scoring_version)})</span></div>
        <div class="table-wrapper">
          <table class="data-table">
            <thead><tr><th>Criterion</th><th>Points</th><th>Reasoning</th><th>Evidence</th></tr></thead>
            <tbody>${breakdownHtml}</tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <div class="card-header"><span class="card-title">Reviewer History</span></div>
        ${reviewsHtml}
      </div>
    `;
    openModal(`Lead Evidence Passport — ${c.name}`, html);
  } catch (err) {
    openModal("Error", `<div class="empty-state">${escapeHtml(err.message)}</div>`);
  }
}

/**
 * Feature 2 — Explainable Lead Scoring Modal
 */
export async function showScoreExplainerModal(creatorId) {
  openModal("Explainable Lead Scoring", `<div class="loading-state">Calculating score breakdown...</div>`);
  try {
    const data = await api.getLeadScoreExplainer(creatorId);
    const rows = (data.breakdown || [])
      .map(
        (b) => `
      <tr>
        <td><strong>${escapeHtml(b.criterion)}</strong></td>
        <td><strong>${b.awarded_points}</strong> / ${b.max_points}</td>
        <td>${escapeHtml(b.reasoning)}</td>
        <td><code>${escapeHtml(b.evidence_id || "—")}</code></td>
        <td>${b.source_url ? `<a href="${escapeHtml(b.source_url)}" target="_blank" rel="noopener" class="btn btn-secondary btn-sm">Open &nearr;</a>` : "—"}</td>
      </tr>
    `
      )
      .join("");

    openModal(
      `Explainable Score — ${data.creator_name} (${data.total_score}/100)`,
      `
      <div class="card">
        <p><strong>Creator:</strong> ${escapeHtml(data.creator_name)} | <strong>Tier:</strong> ${statusBadge(data.priority_tier)} | <strong>Rank:</strong> #${data.rank_position || "—"}</p>
        <p style="font-size:12px;color:#475569;margin-top:4px;">Scoring Model Version: <code>${escapeHtml(data.scoring_version)}</code> (Project-defined weights out of 100 points)</p>
      </div>
      <div class="card">
        <div class="table-wrapper">
          <table class="data-table">
            <thead><tr><th>Criterion</th><th>Points</th><th>Explanation</th><th>Evidence ID</th><th>Source</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>
    `
    );
  } catch (err) {
    openModal("Score Explainer Error", `<div class="empty-state">${escapeHtml(err.message)}</div>`);
  }
}

/**
 * Feature 5 — Contact Channel Explainer Modal
 */
export async function showChannelExplainerModal(creatorId) {
  openModal("Contact Channel Explainer", `<div class="loading-state">Loading Contact Channel Explainer...</div>`);
  try {
    const data = await api.getChannelExplainer(creatorId);
    if (!data.has_verified_channel) {
      openModal("Contact Channel Explainer", `<div class="empty-state">${escapeHtml(data.message)}</div>`);
      return;
    }
    const rejectedRows = (data.rejected_channels || [])
      .map(
        (r) => `
      <tr>
        <td><code>${escapeHtml(r.channel_type)}</code></td>
        <td>${escapeHtml(r.handle_or_address)}</td>
        <td>${escapeHtml(r.reason)}</td>
      </tr>
    `
      )
      .join("");

    openModal(
      `Contact Channel Explainer — ${data.creator_name}`,
      `
      <div class="card">
        <div class="card-header"><span class="card-title">Selected Channels</span></div>
        <p><strong>Primary Channel:</strong> <span class="badge badge-success">${escapeHtml(data.primary_channel)}</span> <code>${escapeHtml(data.primary_contact_value)}</code>
          <a href="${escapeHtml(data.primary_contact_url)}" target="_blank" rel="noopener" style="margin-left:8px;">Source &nearr;</a>
        </p>
        <p style="margin-top:8px;"><strong>Verified Backup Channel:</strong>
          ${
            data.backup_channel
              ? `<span class="badge badge-info">${escapeHtml(data.backup_channel)}</span> <code>${escapeHtml(data.backup_contact_value)}</code>`
              : `<span class="badge badge-warning">None Verified (Never Guessed)</span>`
          }
        </p>
        <p style="margin-top:10px;"><strong>Selection Rationale:</strong> ${escapeHtml(data.selection_reason)}</p>
        <p style="margin-top:6px;font-size:12.5px;color:#b45309;"><strong>Channel Restrictions:</strong> ${escapeHtml(data.restrictions)}</p>
      </div>
      <div class="card">
        <div class="card-header"><span class="card-title">Rejected / Unselected Alternative Channels</span></div>
        <div class="table-wrapper">
          <table class="data-table">
            <thead><tr><th>Channel</th><th>Handle / Value</th><th>Reason Not Selected</th></tr></thead>
            <tbody>${rejectedRows}</tbody>
          </table>
        </div>
      </div>
    `
    );
  } catch (err) {
    openModal("Channel Explainer Error", `<div class="empty-state">${escapeHtml(err.message)}</div>`);
  }
}
