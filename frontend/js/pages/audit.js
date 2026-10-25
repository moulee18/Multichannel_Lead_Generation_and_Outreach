import { api } from "../api.js";
import {
  escapeHtml,
  showLeadEvidencePassportModal,
  showToast,
  statusBadge,
} from "../components/modals.js";

let currentSeed = 42;
let includeSyntheticAudit = true;

export async function renderAuditPage(container) {
  container.innerHTML = `<div class="loading-state">Running independent qualification, geographic & random 20-lead audit...</div>`;
  try {
    const data = await api.getAuditsOverview(includeSyntheticAudit, currentSeed);
    const qa = data.qualification_audit;
    const geo = data.geographic_audit;
    const oa = data.outreach_audit;
    const ra = data.random_audit;

    const sampleRows = (ra.sampled_leads || [])
      .map(
        (s, idx) => `
      <tr>
        <td>${idx + 1}</td>
        <td>
          <strong>${escapeHtml(s.name)}</strong><br/>
          <small><code>${escapeHtml(s.creator_id)}</code> &bull; ${escapeHtml(s.country)}</small>
        </td>
        <td>${s.passed_all ? '<span class="badge badge-success">QUALIFIED PASS</span>' : '<span class="badge badge-danger">FAIL</span>'}</td>
        <td>${s.contact_accurate ? '<span class="badge badge-success">VALID CONTACT</span>' : '<span class="badge badge-danger">INVALID</span>'}</td>
        <td>
          <small>
            Seg: ${s.checks.segment_valid ? "✓" : "✗"} |
            Act: ${s.checks.recent_activity ? "✓" : "✗"} |
            Comm: ${s.checks.commercial_activity ? "✓" : "✗"} |
            Need: ${s.checks.workflow_needs ? "✓" : "✗"} |
            Fresh30d: ${s.checks.evidence_fresh_30d ? "✓" : "✗"} |
            Unique: ${s.checks.unique_record ? "✓" : "✗"}
          </small>
        </td>
        <td>${s.failed_rules.length ? `<span style="color:#b91c1c;">${escapeHtml(s.failed_rules.join(", "))}</span>` : "None"}</td>
        <td>
          <button class="btn btn-secondary btn-sm audit-pass-btn" data-id="${escapeHtml(s.creator_id)}">Evidence (${s.evidence_count})</button>
        </td>
      </tr>
    `
      )
      .join("");

    const countryDistBadges = Object.entries(geo.country_distribution || {})
      .map(([c, cnt]) => `<span class="badge badge-info" style="margin:3px;">${escapeHtml(c)}: ${cnt}</span>`)
      .join("");

    container.innerHTML = `
      <div class="grid-kpi">
        <div class="kpi-card teal">
          <div class="kpi-label">Random 20 Qualification Rate</div>
          <div class="kpi-value">${ra.qualification_pass_rate}%</div>
          <div class="kpi-sub">Min Target: 85% | Exceptional: 90%</div>
        </div>
        <div class="kpi-card teal">
          <div class="kpi-label">Random 20 Contact Accuracy</div>
          <div class="kpi-value">${ra.contact_accuracy_rate}%</div>
          <div class="kpi-sub">Min Target: 90% | Exceptional: 95%</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Duplicate Creators</div>
          <div class="kpi-value">${qa.duplicate_count}</div>
          <div class="kpi-sub">Target: 0% Duplicates</div>
        </div>
        <div class="kpi-card ${geo.compliant ? "teal" : "warning"}">
          <div class="kpi-label">Approved 7-Market Share</div>
          <div class="kpi-value">${geo.approved_market_pct}%</div>
          <div class="kpi-sub">Min: 80% | Countries: ${geo.represented_countries_count} (&ge;3)</div>
        </div>
        <div class="kpi-card ${geo.max_single_country_pct <= 60 ? "teal" : "danger"}">
          <div class="kpi-label">Largest Single Country</div>
          <div class="kpi-value">${geo.max_single_country_pct}%</div>
          <div class="kpi-sub">Max Allowed: 60%</div>
        </div>
      </div>

      <div class="grid-2">
        <div class="card">
          <div class="card-header">
            <span class="card-title">Geographic Compliance Audit</span>
            ${geo.compliant ? '<span class="badge badge-success">COMPLIANT</span>' : '<span class="badge badge-danger">NON-COMPLIANT</span>'}
          </div>
          <p><strong>Approved Markets Share:</strong> ${geo.approved_market_pct}% (US, CA, UK, IE, AU, NZ, SG)</p>
          <p><strong>Represented Countries:</strong> ${geo.represented_countries_count} (Requires &ge; 3)</p>
          <p><strong>Largest Single-Country Share:</strong> ${geo.max_single_country_pct}% (Requires &le; 60%)</p>
          <p><strong>Missing Country Evidence:</strong> ${geo.missing_country_evidence_count}</p>
          <div style="margin-top:8px;">${countryDistBadges}</div>
          ${
            geo.failures && geo.failures.length
              ? `<div style="margin-top:8px;color:#b91c1c;font-size:12px;">${geo.failures.map(escapeHtml).join("<br/>")}</div>`
              : ""
          }
        </div>

        <div class="card">
          <div class="card-header">
            <span class="card-title">Outreach & Sequence Audit</span>
            ${oa.compliant ? '<span class="badge badge-success">COMPLIANT</span>' : '<span class="badge badge-warning">INCOMPLETE</span>'}
          </div>
          <p><strong>Priority A Total:</strong> ${oa.priority_a_total}</p>
          <p><strong>Priority A with Complete 3-Step Sequences:</strong> ${oa.priority_a_with_complete_sequences}</p>
          <p><strong>Channels Covered (Need Email + 2 others):</strong> <code>${escapeHtml((oa.channels_covered || []).join(", "))}</code></p>
          <p><strong>Messages Failing Hallucination/Policy Guard:</strong> ${oa.invalid_messages_count} / ${oa.total_messages_checked}</p>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <div>
            <span class="card-title">Feature 6 — Random Audit Simulator (20-Lead Sample)</span>
            <p style="font-size:12px;color:#64748b;">${escapeHtml(ra.audit_label)}</p>
          </div>
          <form id="random-seed-form" style="display:flex;gap:8px;align-items:center;">
            <label style="font-size:12px;font-weight:600;">Seed:</label>
            <input type="number" id="audit-seed-input" class="form-control" style="width:90px;" value="${currentSeed}" />
            <label style="font-size:12px;display:flex;align-items:center;gap:4px;">
              <input type="checkbox" id="audit-inc-synth" ${includeSyntheticAudit ? "checked" : ""} /> Include Demo
            </label>
            <button type="submit" class="btn btn-primary btn-sm">Run Sample Audit</button>
          </form>
        </div>

        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Sampled Lead</th>
                <th>Qualification</th>
                <th>Contact Check</th>
                <th>Criterion Breakdown</th>
                <th>Failed Rules</th>
                <th>Inspect Evidence</th>
              </tr>
            </thead>
            <tbody>
              ${sampleRows || '<tr><td colspan="7" class="empty-state">No qualified leads available to sample.</td></tr>'}
            </tbody>
          </table>
        </div>
      </div>
    `;

    document.getElementById("random-seed-form")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      currentSeed = parseInt(document.getElementById("audit-seed-input").value, 10) || 42;
      includeSyntheticAudit = document.getElementById("audit-inc-synth").checked;
      showToast(`Running reproducible 20-lead audit with seed=${currentSeed}...`, "info");
      await api.runAudit({
        random_seed: currentSeed,
        sample_size: 20,
        include_synthetic: includeSyntheticAudit,
      });
      await renderAuditPage(container);
    });

    container.querySelectorAll(".audit-pass-btn").forEach((btn) => {
      btn.addEventListener("click", () => showLeadEvidencePassportModal(btn.dataset.id));
    });
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Error loading Quality Audit: ${escapeHtml(err.message)}</div>`;
  }
}
