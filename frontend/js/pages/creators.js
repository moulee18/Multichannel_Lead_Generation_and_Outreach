import { api } from "../api.js";
import {
  escapeHtml,
  showLeadEvidencePassportModal,
  statusBadge,
} from "../components/modals.js";

let currentFilters = {
  search: "",
  status: "",
  country: "",
  category: "",
  is_synthetic: "",
  sort_by: "rank",
  page: 1,
  page_size: 20,
};

export async function renderCreatorsPage(container) {
  container.innerHTML = `<div class="loading-state">Loading Creator Database...</div>`;
  try {
    const data = await api.listCreators(currentFilters);
    const totalPages = Math.max(1, Math.ceil((data.total || 0) / currentFilters.page_size));

    const rowsHtml = (data.items || [])
      .map(
        (c) => `
      <tr>
        <td>${c.rank_position ? `#${c.rank_position}` : "—"}</td>
        <td>
          <strong>${escapeHtml(c.name)}</strong><br/>
          <small><a href="${escapeHtml(c.official_url)}" target="_blank" rel="noopener">${escapeHtml(c.platform_id)} &nearr;</a></small>
        </td>
        <td>${escapeHtml(c.category)}<br/><small style="color:#64748b;">${escapeHtml(c.niche || "")}</small></td>
        <td>${escapeHtml(c.country)}</td>
        <td>30d: <strong>${c.items_30d}</strong> | 60d LF: <strong>${c.longform_60d}</strong></td>
        <td>${statusBadge(c.qualification_status)}</td>
        <td>${c.lead_score != null ? `<strong>${c.lead_score}</strong> (${escapeHtml(c.priority_tier || "")})` : "—"}</td>
        <td>
          ${c.primary_channel ? `<span class="badge badge-info">${escapeHtml(c.primary_channel)}</span>` : "—"}
          ${c.backup_channel ? `<br/><small>Backup: ${escapeHtml(c.backup_channel)}</small>` : ""}
        </td>
        <td>${c.is_synthetic ? '<span class="badge badge-synthetic">SYNTHETIC</span>' : '<span class="badge badge-success">GENUINE</span>'}</td>
        <td>
          <button class="btn btn-primary btn-sm passport-btn" data-id="${escapeHtml(c.id)}">Evidence Passport</button>
        </td>
      </tr>
    `
      )
      .join("");

    container.innerHTML = `
      <div class="card">
        <div class="card-header">
          <span class="card-title">Search & Filter Creators (${data.total} Records)</span>
        </div>
        <form id="creators-filter-form" class="form-grid">
          <div class="form-group">
            <label>Search Name / ID / Niche</label>
            <input type="text" id="flt-search" class="form-control" value="${escapeHtml(currentFilters.search)}" placeholder="Search creator..." />
          </div>
          <div class="form-group">
            <label>Qualification Status</label>
            <select id="flt-status" class="form-control">
              <option value="">All Statuses</option>
              <option value="QUALIFIED" ${currentFilters.status === "QUALIFIED" ? "selected" : ""}>QUALIFIED</option>
              <option value="NEEDS_REVIEW" ${currentFilters.status === "NEEDS_REVIEW" ? "selected" : ""}>NEEDS_REVIEW</option>
              <option value="REJECTED" ${currentFilters.status === "REJECTED" ? "selected" : ""}>REJECTED</option>
            </select>
          </div>
          <div class="form-group">
            <label>Data Origin</label>
            <select id="flt-synthetic" class="form-control">
              <option value="">All (Genuine + Demo)</option>
              <option value="false" ${currentFilters.is_synthetic === "false" ? "selected" : ""}>Genuine Only</option>
              <option value="true" ${currentFilters.is_synthetic === "true" ? "selected" : ""}>Synthetic Demo Only</option>
            </select>
          </div>
          <div class="form-group">
            <label>Sort By</label>
            <select id="flt-sort" class="form-control">
              <option value="rank" ${currentFilters.sort_by === "rank" ? "selected" : ""}>Rank / Priority</option>
              <option value="name" ${currentFilters.sort_by === "name" ? "selected" : ""}>Creator Name</option>
              <option value="country" ${currentFilters.sort_by === "country" ? "selected" : ""}>Country</option>
              <option value="items_30d" ${currentFilters.sort_by === "items_30d" ? "selected" : ""}>30-Day Activity</option>
            </select>
          </div>
          <div class="form-group" style="justify-content:flex-end;">
            <button type="submit" class="btn btn-primary">Apply Filters</button>
          </div>
        </form>
      </div>

      <div class="card">
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Creator & Official Profile</th>
                <th>Category & Niche</th>
                <th>Country</th>
                <th>Activity</th>
                <th>Status</th>
                <th>Score & Tier</th>
                <th>Channels</th>
                <th>Origin</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              ${rowsHtml || '<tr><td colspan="10" class="empty-state">No creators match the current filter criteria.</td></tr>'}
            </tbody>
          </table>
        </div>

        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:14px;">
          <span>Page ${data.page} of ${totalPages} (${data.total} total creators)</span>
          <div style="display:flex;gap:8px;">
            <button class="btn btn-secondary btn-sm" id="btn-prev-page" ${data.page <= 1 ? "disabled" : ""}>&larr; Previous</button>
            <button class="btn btn-secondary btn-sm" id="btn-next-page" ${data.page >= totalPages ? "disabled" : ""}>Next &rarr;</button>
          </div>
        </div>
      </div>
    `;

    document.getElementById("creators-filter-form")?.addEventListener("submit", (e) => {
      e.preventDefault();
      currentFilters.search = document.getElementById("flt-search").value.trim();
      currentFilters.status = document.getElementById("flt-status").value;
      currentFilters.is_synthetic = document.getElementById("flt-synthetic").value;
      currentFilters.sort_by = document.getElementById("flt-sort").value;
      currentFilters.page = 1;
      renderCreatorsPage(container);
    });

    document.getElementById("btn-prev-page")?.addEventListener("click", () => {
      if (currentFilters.page > 1) {
        currentFilters.page -= 1;
        renderCreatorsPage(container);
      }
    });

    document.getElementById("btn-next-page")?.addEventListener("click", () => {
      if (currentFilters.page < totalPages) {
        currentFilters.page += 1;
        renderCreatorsPage(container);
      }
    });

    container.querySelectorAll(".passport-btn").forEach((btn) => {
      btn.addEventListener("click", () => showLeadEvidencePassportModal(btn.dataset.id));
    });
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Error loading creators: ${escapeHtml(err.message)}</div>`;
  }
}
