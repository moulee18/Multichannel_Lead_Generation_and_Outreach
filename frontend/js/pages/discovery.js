import { api } from "../api.js";
import { escapeHtml, showToast, statusBadge } from "../components/modals.js";

export async function renderDiscoveryPage(container) {
  container.innerHTML = `<div class="loading-state">Loading Creator Discovery console...</div>`;
  try {
    const [kwData, runsData] = await Promise.all([
      api.getKeywords(),
      api.listDiscoveryRuns(),
    ]);

    const kwLibrary = kwData.keyword_library || {};
    const kwPills = Object.entries(kwLibrary)
      .map(
        ([niche, kws]) =>
          `<div style="margin-bottom:6px;">
            <strong style="font-size:11.5px;text-transform:uppercase;color:#475569;">${escapeHtml(niche)}:</strong>
            ${kws
              .map(
                (k) =>
                  `<button type="button" class="btn btn-secondary btn-sm kw-pick-btn" data-kw="${escapeHtml(k)}" style="margin:2px;">${escapeHtml(k)}</button>`
              )
              .join("")}
          </div>`
      )
      .join("");

    const runsRows = (runsData.runs || [])
      .map(
        (r) => `
      <tr>
        <td><code>${escapeHtml(r.id)}</code></td>
        <td><strong>${escapeHtml(r.keyword)}</strong><br/><small>${escapeHtml(r.category)}</small></td>
        <td><code>${escapeHtml(r.source)}</code> (${escapeHtml(r.run_mode)})</td>
        <td>${statusBadge(r.status)}</td>
        <td>Disc: ${r.discovered_count} | Dedup: ${r.deduplicated_count}</td>
        <td>
          <span class="badge badge-success">Q: ${r.qualified_count}</span>
          <span class="badge badge-warning">R: ${r.needs_review_count}</span>
          <span class="badge badge-danger">X: ${r.rejected_count}</span>
        </td>
        <td>${r.error_log && r.error_log.length ? `<span style="color:#b91c1c;">${escapeHtml(r.error_log[0].message || r.error_log[0].error)}</span>` : "None"}</td>
        <td>
          ${
            r.status === "RUNNING"
              ? `<button class="btn btn-danger btn-sm cancel-run-btn" data-id="${escapeHtml(r.id)}">Cancel</button>`
              : `<span style="font-size:11.5px;color:#64748b;">${escapeHtml(r.started_at?.slice(0, 19))}</span>`
          }
        </td>
      </tr>
    `
      )
      .join("");

    container.innerHTML = `
      <div class="card">
        <div class="card-header">
          <span class="card-title">Start Creator Discovery & Verification (Agent 1)</span>
        </div>
        <form id="discovery-form">
          <div class="form-grid">
            <div class="form-group">
              <label for="disc-keyword">Search Keyword</label>
              <input id="disc-keyword" class="form-control" type="text" value="b2b founder podcast" required />
            </div>
            <div class="form-group">
              <label for="disc-category">Creator Category</label>
              <select id="disc-category" class="form-control">
                <option value="Podcaster / Video Podcaster">Podcaster / Video Podcaster</option>
                <option value="YouTuber / Video-First Creator">YouTuber / Video-First Creator</option>
                <option value="Expert-Led Creator (Coach / Consultant / Educator)">Expert-Led Creator (Coach / Consultant / Educator)</option>
              </select>
            </div>
            <div class="form-group">
              <label for="disc-source">Discovery Source Adapter</label>
              <select id="disc-source" class="form-control">
                <option value="podcast_rss">Public Podcast RSS + Apple iTunes API (Live No-Key)</option>
                <option value="youtube_api">Official YouTube Data API v3 (Requires YOUTUBE_API_KEY)</option>
                <option value="public_research_import">Verified Public Research Bundle (Jay Clouse + 100 US Chart)</option>
                <option value="synthetic_demo">Synthetic Demo Fixtures (35 Labelled Test Records)</option>
              </select>
            </div>
            <div class="form-group">
              <label for="disc-limit">Candidate Limit</label>
              <input id="disc-limit" class="form-control" type="number" min="1" max="500" value="15" required />
            </div>
            <div class="form-group">
              <label for="disc-countries">Target Markets (Comma-Separated)</label>
              <input id="disc-countries" class="form-control" type="text" value="United States, Canada, United Kingdom, Ireland, Australia, New Zealand, Singapore" />
            </div>
          </div>

          <div style="margin-bottom:14px;">
            <div style="font-size:12px;font-weight:700;color:#475569;margin-bottom:6px;">Initial Niche Keyword Library (Click to fill):</div>
            ${kwPills}
          </div>

          <div style="display:flex;gap:10px;flex-wrap:wrap;">
            <button type="submit" class="btn btn-primary" id="btn-start-disc">Start Discovery</button>
            <button type="button" class="btn btn-teal" id="btn-refresh-leads">Refresh Existing Leads</button>
            <button type="button" class="btn btn-secondary" id="btn-reload-runs">View / Refresh Run History</button>
          </div>
        </form>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">Discovery Run History & Source Errors</span>
        </div>
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Keyword & Category</th>
                <th>Source & Mode</th>
                <th>Status</th>
                <th>Candidates</th>
                <th>Verification Breakdown</th>
                <th>Source Restrictions / Errors</th>
                <th>Timestamp / Action</th>
              </tr>
            </thead>
            <tbody>
              ${runsRows || '<tr><td colspan="8" class="empty-state">No discovery runs recorded yet.</td></tr>'}
            </tbody>
          </table>
        </div>
      </div>
    `;

    container.querySelectorAll(".kw-pick-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const input = document.getElementById("disc-keyword");
        if (input) input.value = btn.dataset.kw;
      });
    });

    document.getElementById("discovery-form")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = document.getElementById("btn-start-disc");
      btn.disabled = true;
      const source = document.getElementById("disc-source").value;
      const keyword = document.getElementById("disc-keyword").value.trim();
      const category = document.getElementById("disc-category").value;
      const max_candidates = parseInt(document.getElementById("disc-limit").value, 10) || 15;
      const countries = document
        .getElementById("disc-countries")
        .value.split(",")
        .map((c) => c.trim())
        .filter(Boolean);

      showToast(`Starting discovery on '${source}' for '${keyword}'...`, "info");
      try {
        const res = await api.startDiscoveryRun({
          keyword,
          category,
          countries,
          max_candidates,
          source,
          run_mode: source === "synthetic_demo" ? "synthetic_demo" : "live",
        });
        if (res.status === "FAILED_SOURCE_RESTRICTION") {
          showToast(res.error_log?.[0]?.message || "Source restriction logged.", "error");
        } else {
          showToast(
            `Discovery completed: ${res.discovered_count} discovered, ${res.qualified_count} qualified!`,
            "success"
          );
        }
        await renderDiscoveryPage(container);
      } catch (err) {
        showToast(err.message, "error");
        btn.disabled = false;
      }
    });

    document.getElementById("btn-refresh-leads")?.addEventListener("click", async (e) => {
      e.target.disabled = true;
      showToast("Running Smart Refresh on existing leads...", "info");
      try {
        const r = await api.runSmartRefresh({});
        showToast(
          `Smart Refresh done: ${r.updated_creators_count} updated, ${r.unchanged_records_count} unchanged.`,
          "success"
        );
        await renderDiscoveryPage(container);
      } catch (err) {
        showToast(err.message, "error");
        e.target.disabled = false;
      }
    });

    document.getElementById("btn-reload-runs")?.addEventListener("click", () =>
      renderDiscoveryPage(container)
    );

    container.querySelectorAll(".cancel-run-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await api.cancelDiscoveryRun(btn.dataset.id);
          showToast(`Cancelled run ${btn.dataset.id}`, "info");
          await renderDiscoveryPage(container);
        } catch (err) {
          showToast(err.message, "error");
        }
      });
    });
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Error loading discovery page: ${escapeHtml(err.message)}</div>`;
  }
}
