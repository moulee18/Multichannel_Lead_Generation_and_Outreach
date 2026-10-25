import { api } from "../api.js";
import { escapeHtml, showToast, statusBadge } from "../components/modals.js";

export async function renderSettingsPage(container) {
  container.innerHTML = `<div class="loading-state">Loading System Settings & Product Registry...</div>`;
  try {
    const cfg = await api.getConfigStatus();
    const w = cfg.scoring?.weights || {};
    const caps = cfg.product_capabilities || [];
    const usages = cfg.recent_api_usage || [];

    const integrationRows = Object.entries(cfg.integrations || {})
      .map(
        ([k, v]) => `
      <tr>
        <td><strong><code>${escapeHtml(k)}</code></strong></td>
        <td>${v.configured ? '<span class="badge badge-success">CONFIGURED</span>' : '<span class="badge badge-warning">NOT CONFIGURED</span>'}</td>
        <td>${escapeHtml(v.status)}</td>
      </tr>
    `
      )
      .join("");

    const capRows = caps
      .map(
        (c) => `
      <tr>
        <td><code>${escapeHtml(c.capability_key)}</code></td>
        <td><strong>${escapeHtml(c.feature_name)}</strong><br/><small>${escapeHtml(c.description)}</small></td>
        <td><small>${escapeHtml(c.source_evidence)}</small></td>
        <td>${c.confirmed ? '<span class="badge badge-success">CONFIRMED</span>' : '<span class="badge badge-warning">UNCONFIRMED</span>'}</td>
      </tr>
    `
      )
      .join("");

    const usageRows = usages
      .map(
        (u) => `
      <tr>
        <td><code>${escapeHtml(u.provider)}</code></td>
        <td>${escapeHtml(u.operation)} (<code>${escapeHtml(u.endpoint)}</code>)</td>
        <td>${u.status_code} (${u.success ? "OK" : "ERR"})</td>
        <td>${u.latency_ms} ms</td>
        <td><small>${escapeHtml(u.error_detail || "—")}</small></td>
        <td><small>${escapeHtml(u.recorded_at?.slice(0, 19))}</small></td>
      </tr>
    `
      )
      .join("");

    container.innerHTML = `
      <div class="grid-2">
        <div class="card">
          <div class="card-header">
            <span class="card-title">External Data Source & Template Status</span>
          </div>
          <div class="table-wrapper">
            <table class="data-table">
              <thead><tr><th>Integration</th><th>State</th><th>Details</th></tr></thead>
              <tbody>${integrationRows}</tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <span class="card-title">Shared LLM Interface & Sender Identity</span>
          </div>
          <p><strong>Selected LLM Provider:</strong> <code>${escapeHtml(cfg.llm?.selected_provider)}</code> (${escapeHtml(cfg.llm?.selected_model)})</p>
          <p><strong>Supported Providers:</strong> <code>${escapeHtml((cfg.llm?.supported_providers || []).join(", "))}</code></p>
          <p style="margin-top:8px;"><strong>Sender Name:</strong> ${escapeHtml(cfg.sender_identity?.sender_name)}</p>
          <p><strong>Sender Role:</strong> ${escapeHtml(cfg.sender_identity?.sender_role)}</p>
          <p><strong>Outbound Test Mode:</strong> <span class="badge badge-info">${escapeHtml(cfg.sender_identity?.outbound_test_mode)}</span></p>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">Configurable 100-Point Lead Scoring Model (Project-Defined Weights)</span>
        </div>
        <form id="scoring-weights-form">
          <div class="form-grid">
            <div class="form-group">
              <label>Product Relevance</label>
              <input type="number" step="1" id="w-rel" class="form-control" value="${w.product_relevance ?? 30}" />
            </div>
            <div class="form-group">
              <label>Strength of Need Evidence</label>
              <input type="number" step="1" id="w-need" class="form-control" value="${w.need_evidence_strength ?? 25}" />
            </div>
            <div class="form-group">
              <label>Commercial Readiness</label>
              <input type="number" step="1" id="w-comm" class="form-control" value="${w.commercial_readiness ?? 20}" />
            </div>
            <div class="form-group">
              <label>Publishing Activity</label>
              <input type="number" step="1" id="w-act" class="form-control" value="${w.publishing_activity ?? 15}" />
            </div>
            <div class="form-group">
              <label>Contact-Channel Quality</label>
              <input type="number" step="1" id="w-ctc" class="form-control" value="${w.contact_channel_quality ?? 10}" />
            </div>
          </div>
          <button type="submit" class="btn btn-primary btn-sm">Save Scoring Weights</button>
        </form>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">Confirmed IncuBrix Product Capability Registry (Enforced by AI Hallucination Guard)</span>
        </div>
        <div class="table-wrapper">
          <table class="data-table">
            <thead><tr><th>Key</th><th>Feature & Description</th><th>Source Evidence</th><th>Status</th></tr></thead>
            <tbody>${capRows}</tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">API Usage, Quota & Error Telemetry Log</span>
        </div>
        <div class="table-wrapper">
          <table class="data-table">
            <thead><tr><th>Provider</th><th>Operation</th><th>Status</th><th>Latency</th><th>Error</th><th>Timestamp</th></tr></thead>
            <tbody>${usageRows || '<tr><td colspan="6" class="empty-state">No external API calls logged yet.</td></tr>'}</tbody>
          </table>
        </div>
      </div>
    `;

    document.getElementById("scoring-weights-form")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await api.updateScoring({
          product_relevance: parseFloat(document.getElementById("w-rel").value),
          need_evidence_strength: parseFloat(document.getElementById("w-need").value),
          commercial_readiness: parseFloat(document.getElementById("w-comm").value),
          publishing_activity: parseFloat(document.getElementById("w-act").value),
          contact_channel_quality: parseFloat(document.getElementById("w-ctc").value),
        });
        showToast("Updated scoring weights in config/scoring.json!", "success");
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Error loading Settings: ${escapeHtml(err.message)}</div>`;
  }
}
