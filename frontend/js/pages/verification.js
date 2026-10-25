import { api } from "../api.js";
import {
  escapeHtml,
  showLeadEvidencePassportModal,
  showToast,
  statusBadge,
} from "../components/modals.js";

export async function renderVerificationPage(container) {
  container.innerHTML = `<div class="loading-state">Loading Verification Queue...</div>`;
  try {
    const data = await api.listCreators({ status: "NEEDS_REVIEW", page_size: 50 });
    const items = data.items || [];

    const cardsHtml = items
      .map(
        (c) => `
      <div class="card">
        <div class="card-header">
          <div>
            <span class="card-title">${escapeHtml(c.name)}</span>
            <small style="margin-left:8px;color:#64748b;">(${escapeHtml(c.category)} &bull; ${escapeHtml(c.country)})</small>
          </div>
          <div>
            ${statusBadge(c.qualification_status)}
            <button class="btn btn-secondary btn-sm vp-passport-btn" data-id="${escapeHtml(c.id)}">Inspect Passport</button>
          </div>
        </div>
        <p style="margin-bottom:10px;font-size:13px;">
          <strong>Unresolved Criteria Requiring Review:</strong>
          ${(c.uncertain_criteria || []).map((u) => `<span class="badge badge-warning" style="margin-right:4px;">${escapeHtml(u)}</span>`).join("") || "None"}
        </p>

        <form class="review-form" data-id="${escapeHtml(c.id)}">
          <div class="form-grid">
            <div class="form-group">
              <label>Decision Status</label>
              <select class="form-control rev-status" required>
                <option value="QUALIFIED">Approve as QUALIFIED (Requires Evidence Below)</option>
                <option value="NEEDS_REVIEW" selected>Keep in NEEDS_REVIEW</option>
                <option value="REJECTED">Mark as REJECTED</option>
              </select>
            </div>
            <div class="form-group">
              <label>Verified Country Override (if UNKNOWN)</label>
              <input type="text" class="form-control rev-country" value="${escapeHtml(c.country !== "UNKNOWN" ? c.country : "")}" placeholder="e.g. United States" />
            </div>
            <div class="form-group">
              <label>Source Evidence URL</label>
              <input type="url" class="form-control rev-url" value="${escapeHtml(c.official_url)}" required />
            </div>
          </div>
          <div class="form-grid">
            <div class="form-group">
              <label>Commercial Activity Excerpt (if overriding)</label>
              <input type="text" class="form-control rev-comm" placeholder="e.g. Verified sponsor link in episode notes..." />
            </div>
            <div class="form-group">
              <label>Workflow / IncuBrix Need Excerpt (if overriding)</label>
              <input type="text" class="form-control rev-need" placeholder="e.g. Creator hiring video editor for Shorts repurposing..." />
            </div>
            <div class="form-group">
              <label>Reviewer Audit Notes (Required)</label>
              <input type="text" class="form-control rev-notes" placeholder="Document manual verification basis..." required />
            </div>
          </div>
          <button type="submit" class="btn btn-primary btn-sm">Record Audited Review Decision</button>
        </form>
      </div>
    `
      )
      .join("");

    container.innerHTML = `
      <div class="card">
        <div class="card-header">
          <span class="card-title">Unresolved Creator Verification Queue (${items.length} Pending Review)</span>
        </div>
        <p style="color:#475569;">
          Records with uncertain country, commercial monetization, workflow need, or business contact are held in <code>NEEDS_REVIEW</code> and never counted toward the official lead target until verified with working public source evidence.
        </p>
      </div>
      ${cardsHtml || '<div class="empty-state">All candidate records have been resolved! Zero items pending in NEEDS_REVIEW.</div>'}
    `;

    container.querySelectorAll(".vp-passport-btn").forEach((btn) => {
      btn.addEventListener("click", () => showLeadEvidencePassportModal(btn.dataset.id));
    });

    container.querySelectorAll(".review-form").forEach((form) => {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const cid = form.dataset.id;
        const new_status = form.querySelector(".rev-status").value;
        const country_override = form.querySelector(".rev-country").value.trim() || null;
        const evidence_url = form.querySelector(".rev-url").value.trim();
        const comm = form.querySelector(".rev-comm").value.trim();
        const need = form.querySelector(".rev-need").value.trim();
        const notes = form.querySelector(".rev-notes").value.trim();

        const criterion_overrides = {};
        if (comm) criterion_overrides["commercial_activity"] = comm;
        if (need) criterion_overrides["needs_incubrix"] = need;

        try {
          await api.submitCreatorReview(cid, {
            new_status,
            notes,
            evidence_url,
            country_override,
            criterion_overrides,
          });
          showToast(`Saved manual review decision (${new_status}) for creator ${cid}`, "success");
          await renderVerificationPage(container);
        } catch (err) {
          showToast(err.message, "error");
        }
      });
    });
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Error loading Verification Queue: ${escapeHtml(err.message)}</div>`;
  }
}
