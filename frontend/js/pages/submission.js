import { api } from "../api.js";
import { escapeHtml, showToast, statusBadge } from "../components/modals.js";

export async function renderSubmissionPage(container) {
  container.innerHTML = `<div class="loading-state">Loading Submission Readiness Centre & Exporter...</div>`;
  try {
    const [exportsData, cfgData] = await Promise.all([
      api.listExports(),
      api.getConfigStatus(),
    ]);
    const readiness = exportsData.readiness;
    const artifacts = exportsData.artifacts || [];
    const insights = cfgData.product_insights || [];

    const checklistRows = (readiness.checklist || [])
      .map(
        (item) => `
      <tr>
        <td><strong>${escapeHtml(item.title)}</strong></td>
        <td><code>${escapeHtml(item.category)}</code></td>
        <td>${statusBadge(item.status)}</td>
        <td>
          Impl: ${item.implemented ? "✓" : "✗"} |
          Tested: ${item.tested ? "✓" : "✗"} |
          Real-Data: ${item.real_data_satisfied ? "✓" : "✗"}
        </td>
        <td>${escapeHtml(item.detail)}</td>
      </tr>
    `
      )
      .join("");

    const artifactRows = artifacts
      .map(
        (a) => `
      <tr>
        <td><strong>${escapeHtml(a.artifact_type)}</strong></td>
        <td><code>${escapeHtml(a.file_name)}</code></td>
        <td>${a.record_count}</td>
        <td>${a.contains_synthetic_data ? '<span class="badge badge-synthetic">INCLUDES SYNTHETIC</span>' : '<span class="badge badge-success">GENUINE / REPORT</span>'}</td>
        <td><small><code>${escapeHtml(a.checksum_sha256?.slice(0, 16) || "—")}...</code></small></td>
        <td>
          <a href="${escapeHtml(a.download_url)}" class="btn btn-primary btn-sm" download>Download &darr;</a>
        </td>
      </tr>
    `
      )
      .join("");

    const insightsHtml = insights
      .map(
        (ins) => `
      <form class="insight-form evidence-item" data-id="${escapeHtml(ins.id)}">
        <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
          <strong>[${escapeHtml(ins.insight_type)} #${ins.item_number}]</strong>
          <label style="font-size:12px;">
            <input type="checkbox" class="ins-verified" ${ins.is_verified_product_test ? "checked" : ""} />
            Verified Live Product Session Attached
          </label>
        </div>
        <div class="form-grid">
          <div class="form-group">
            <label>Title</label>
            <input type="text" class="form-control ins-title" value="${escapeHtml(ins.title)}" required />
          </div>
          <div class="form-group">
            <label>Evidence Reference / Screenshot Path</label>
            <input type="text" class="form-control ins-ref" value="${escapeHtml(ins.evidence_reference)}" required />
          </div>
        </div>
        <div class="form-group" style="margin-bottom:8px;">
          <label>Detailed Observation / Opportunity</label>
          <textarea class="form-control ins-detail" rows="2" required>${escapeHtml(ins.detail)}</textarea>
        </div>
        <button type="submit" class="btn btn-secondary btn-sm">Save Insight</button>
      </form>
    `
      )
      .join("");

    container.innerHTML = `
      <div class="card">
        <div class="card-header">
          <div>
            <span class="card-title">Feature 8 — Submission Readiness Centre</span>
            <p style="font-size:12.5px;color:#475569;margin-top:4px;">${escapeHtml(readiness.explanation)}</p>
          </div>
          <div style="display:flex;gap:10px;align-items:center;">
            ${statusBadge(readiness.overall_status)}
            <button class="btn btn-primary" id="btn-generate-submission">Generate / Refresh Full Submission Package</button>
          </div>
        </div>

        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>Official Assessment Requirement</th>
                <th>Classification</th>
                <th>Status</th>
                <th>Verification Matrix</th>
                <th>Evidence & Explanation</th>
              </tr>
            </thead>
            <tbody>
              ${checklistRows}
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">Generated Submission Artifacts & Downloadable Files (${artifacts.length})</span>
        </div>
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>Artifact Type</th>
                <th>File Name</th>
                <th>Records</th>
                <th>Data Label</th>
                <th>SHA-256 Checksum</th>
                <th>Download</th>
              </tr>
            </thead>
            <tbody>
              ${artifactRows || '<tr><td colspan="6" class="empty-state">Click "Generate / Refresh Full Submission Package" above to build all deliverables.</td></tr>'}
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">Product & Market Insight Recorder (5 Observations + 3 Growth Opportunities)</span>
        </div>
        ${insightsHtml}
      </div>
    `;

    document.getElementById("btn-generate-submission")?.addEventListener("click", async (e) => {
      e.target.disabled = true;
      showToast("Generating leads.csv, outreach sequences, audit reports, 30-day launch kit & ZIP bundle...", "info");
      try {
        const res = await api.generateExports({ include_synthetic: true });
        showToast(`Generated ${res.artifact_count} submission artifacts (Batch ${res.export_batch_id})!`, "success");
        await renderSubmissionPage(container);
      } catch (err) {
        showToast(err.message, "error");
        e.target.disabled = false;
      }
    });

    container.querySelectorAll(".insight-form").forEach((form) => {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        try {
          await api.updateInsight({
            id: form.dataset.id,
            title: form.querySelector(".ins-title").value,
            detail: form.querySelector(".ins-detail").value,
            evidence_reference: form.querySelector(".ins-ref").value,
            is_verified_product_test: form.querySelector(".ins-verified").checked,
          });
          showToast("Updated Product/Market Insight!", "success");
          await renderSubmissionPage(container);
        } catch (err) {
          showToast(err.message, "error");
        }
      });
    });
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Error loading Submission Centre: ${escapeHtml(err.message)}</div>`;
  }
}
