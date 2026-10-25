import { api } from "../api.js";
import { escapeHtml, showToast, statusBadge } from "../components/modals.js";

export async function renderAgentsPage(container) {
  container.innerHTML = `<div class="loading-state">Loading Live Agent Monitor & Pipeline Jobs...</div>`;
  try {
    const data = await api.listPipelineRuns();
    const jobs = data.jobs || [];
    const refreshes = data.refresh_history || [];
    const latestJob = jobs[0] || null;

    const jobsRows = jobs
      .map(
        (j) => `
      <tr>
        <td><code>${escapeHtml(j.id)}</code></td>
        <td><strong>${escapeHtml(j.job_type)}</strong><br/><small>${escapeHtml(j.current_stage)}</small></td>
        <td>${statusBadge(j.status)}</td>
        <td>
          <div class="progress-bar-outer"><div class="progress-bar-inner" style="width:${j.progress_pct}%"></div></div>
          <small>${j.progress_pct}%</small>
        </td>
        <td>
          Proc: <strong>${j.processed_count}</strong> |
          Pass: <strong style="color:#15803d;">${j.passed_count}</strong> |
          Rev: <strong style="color:#b45309;">${j.review_count}</strong> |
          Rej: <strong style="color:#b91c1c;">${j.rejected_count}</strong>
        </td>
        <td>${j.runtime_seconds}s</td>
        <td>${j.error_count} error(s)</td>
        <td>
          ${
            j.can_retry
              ? `<button class="btn btn-secondary btn-sm retry-job-btn" data-id="${escapeHtml(j.id)}">Retry / Resume</button>`
              : "—"
          }
        </td>
      </tr>
    `
      )
      .join("");

    const refreshRows = refreshes
      .map(
        (r) => `
      <tr>
        <td><code>${escapeHtml(r.id)}</code></td>
        <td><span class="badge badge-success">+${r.new_creators_count} New</span></td>
        <td><span class="badge badge-info">${r.updated_creators_count} Updated</span></td>
        <td>${r.unchanged_records_count} Unchanged</td>
        <td>${r.stale_evidence_count} Stale | ${r.invalidated_qualifications_count} Invalidated</td>
        <td><strong>${r.duplicates_prevented_count}</strong> Prevented</td>
        <td>${r.runtime_seconds}s (${r.api_calls_used} API calls)</td>
        <td><small>${escapeHtml(r.executed_at?.slice(0, 19))}</small></td>
      </tr>
    `
      )
      .join("");

    const stageMetricsHtml = latestJob?.stage_metrics
      ? Object.entries(latestJob.stage_metrics)
          .map(
            ([stage, sm]) => `
        <div class="evidence-item">
          <div style="display:flex;justify-content:space-between;">
            <strong>${escapeHtml(stage)}</strong>
            ${statusBadge(sm.status || "COMPLETED")}
          </div>
          <pre style="font-size:11.5px;margin-top:6px;white-space:pre-wrap;color:#334155;">${escapeHtml(JSON.stringify(sm, null, 2))}</pre>
        </div>
      `
          )
          .join("")
      : `<div class="empty-state">Run the pipeline to inspect stage-by-stage agent execution metrics.</div>`;

    container.innerHTML = `
      <div class="card">
        <div class="card-header">
          <span class="card-title">Feature 7 — Live Agent Monitor & Pipeline Orchestrator</span>
        </div>
        <p style="margin-bottom:14px;color:#475569;">
          Execute individual agents or the complete end-to-end 3-Agent pipeline with persistent checkpoints, partial failure isolation, and Smart Refresh.
        </p>
        <div style="display:flex;gap:10px;flex-wrap:wrap;">
          <button class="btn btn-primary" id="btn-run-full-demo">Run Full Pipeline (35 Synthetic Demo Fixtures)</button>
          <button class="btn btn-teal" id="btn-run-full-podcast">Run Full Pipeline (Live Podcast RSS Discovery)</button>
          <button class="btn btn-secondary" id="btn-run-smart-refresh">Run Smart Refresh (Feature 4)</button>
          <button class="btn btn-secondary" id="btn-run-agent2-only">Run Agent 2 Only (Scoring & Outreach)</button>
          <button class="btn btn-secondary" id="btn-run-agent3-only">Run Agent 3 Only (Independent Audit)</button>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">Latest Pipeline Stage Metrics & Error Logs</span>
          ${latestJob ? statusBadge(latestJob.status) : ""}
        </div>
        ${stageMetricsHtml}
        ${
          latestJob?.error_messages?.length
            ? `<div style="margin-top:10px;background:#fee2e2;color:#b91c1c;padding:10px;border-radius:6px;font-size:12px;">
                <strong>Error Log:</strong><br/>${latestJob.error_messages.map(escapeHtml).join("<br/>")}
              </div>`
            : ""
        }
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">Persistent Pipeline Jobs</span>
        </div>
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>Job ID</th>
                <th>Type & Stage</th>
                <th>Status</th>
                <th>Progress</th>
                <th>Counts (Proc / Pass / Rev / Rej)</th>
                <th>Runtime</th>
                <th>Errors</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${jobsRows || '<tr><td colspan="8" class="empty-state">No pipeline jobs recorded yet.</td></tr>'}
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">Feature 4 — Smart Refresh History (Idempotent Delta Tracking)</span>
        </div>
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>Refresh ID</th>
                <th>New Creators</th>
                <th>Updated Creators</th>
                <th>Unchanged Skipped</th>
                <th>Stale / Invalidated</th>
                <th>Duplicates Prevented</th>
                <th>Runtime & API Usage</th>
                <th>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              ${refreshRows || '<tr><td colspan="8" class="empty-state">No Smart Refresh runs recorded yet.</td></tr>'}
            </tbody>
          </table>
        </div>
      </div>
    `;

    document.getElementById("btn-run-full-demo")?.addEventListener("click", async (e) => {
      e.target.disabled = true;
      showToast("Executing Full 3-Agent Pipeline (Synthetic Demo)...", "info");
      try {
        await api.runFullPipeline({
          keyword: "video podcast creator",
          source: "synthetic_demo",
          run_mode: "synthetic_demo",
          max_candidates: 35,
        });
        showToast("Full pipeline completed!", "success");
        await renderAgentsPage(container);
      } catch (err) {
        showToast(err.message, "error");
        e.target.disabled = false;
      }
    });

    document.getElementById("btn-run-full-podcast")?.addEventListener("click", async (e) => {
      e.target.disabled = true;
      showToast("Executing Full Pipeline with Live Podcast RSS Discovery...", "info");
      try {
        await api.runFullPipeline({
          keyword: "business entrepreneur podcast",
          source: "podcast_rss",
          run_mode: "live",
          max_candidates: 15,
        });
        showToast("Live Podcast RSS pipeline run completed!", "success");
        await renderAgentsPage(container);
      } catch (err) {
        showToast(err.message, "error");
        e.target.disabled = false;
      }
    });

    document.getElementById("btn-run-smart-refresh")?.addEventListener("click", async (e) => {
      e.target.disabled = true;
      showToast("Running Smart Refresh...", "info");
      try {
        const r = await api.runSmartRefresh({ keyword: "video podcast", source: "synthetic_demo", max_candidates: 10 });
        showToast(
          `Smart Refresh complete: ${r.duplicates_prevented_count} duplicates prevented, ${r.unchanged_records_count} unchanged skipped!`,
          "success"
        );
        await renderAgentsPage(container);
      } catch (err) {
        showToast(err.message, "error");
        e.target.disabled = false;
      }
    });

    document.getElementById("btn-run-agent2-only")?.addEventListener("click", async (e) => {
      e.target.disabled = true;
      try {
        await api.runIntelligence({ regenerate_outreach: true });
        showToast("Agent 2 scoring & outreach completed!", "success");
        await renderAgentsPage(container);
      } catch (err) {
        showToast(err.message, "error");
        e.target.disabled = false;
      }
    });

    document.getElementById("btn-run-agent3-only")?.addEventListener("click", async (e) => {
      e.target.disabled = true;
      try {
        await api.runAudit({ random_seed: 42, sample_size: 20, include_synthetic: true });
        showToast("Agent 3 independent audit completed!", "success");
        await renderAgentsPage(container);
      } catch (err) {
        showToast(err.message, "error");
        e.target.disabled = false;
      }
    });

    container.querySelectorAll(".retry-job-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        showToast(`Resuming job ${btn.dataset.id}...`, "info");
        try {
          await api.runFullPipeline({ resume_job_id: btn.dataset.id, skip_discovery: true });
          showToast(`Job ${btn.dataset.id} resumed and completed!`, "success");
          await renderAgentsPage(container);
        } catch (err) {
          showToast(err.message, "error");
        }
      });
    });
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Error loading Agent Control Centre: ${escapeHtml(err.message)}</div>`;
  }
}
