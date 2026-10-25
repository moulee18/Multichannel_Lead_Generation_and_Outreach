import { api } from "../api.js";
import { escapeHtml, showToast, statusBadge } from "../components/modals.js";

let countryChart = null;
let funnelChart = null;

export async function renderOverviewPage(container) {
  container.innerHTML = `<div class="loading-state">Loading database metrics...</div>`;
  try {
    const data = await api.getOverview();
    const m = data.metrics;
    const r = data.submission_readiness;
    const a = data.agent_statuses;

    container.innerHTML = `
      <div class="grid-kpi">
        <div class="kpi-card">
          <div class="kpi-label">Total Discovered</div>
          <div class="kpi-value">${m.total_discovered}</div>
          <div class="kpi-sub">Unique stored creators</div>
        </div>
        <div class="kpi-card teal">
          <div class="kpi-label">Qualified Leads</div>
          <div class="kpi-value">${m.qualified_leads}</div>
          <div class="kpi-sub">Genuine: ${m.genuine_qualified_leads} | Demo: ${m.synthetic_qualified_leads}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Priority A Leads</div>
          <div class="kpi-value">${m.priority_a_count}</div>
          <div class="kpi-sub">Top 25 target cohort</div>
        </div>
        <div class="kpi-card warning">
          <div class="kpi-label">Pending Review</div>
          <div class="kpi-value">${m.pending_review}</div>
          <div class="kpi-sub">In Verification Queue</div>
        </div>
        <div class="kpi-card danger">
          <div class="kpi-label">Rejected Leads</div>
          <div class="kpi-value">${m.rejected_leads}</div>
          <div class="kpi-sub">Excluded or non-English</div>
        </div>
        <div class="kpi-card teal">
          <div class="kpi-label">Outreach Drafts</div>
          <div class="kpi-value">${m.outreach_messages_count}</div>
          <div class="kpi-sub">3-step multi-channel</div>
        </div>
      </div>

      <div class="grid-2">
        <div class="card">
          <div class="card-header">
            <span class="card-title">Country Distribution (Qualified Leads)</span>
          </div>
          <canvas id="chart-countries" height="190"></canvas>
        </div>

        <div class="card">
          <div class="card-header">
            <span class="card-title">Qualification Funnel</span>
          </div>
          <canvas id="chart-funnel" height="190"></canvas>
        </div>
      </div>

      <div class="grid-3">
        <div class="card">
          <div class="card-header">
            <span class="card-title">${escapeHtml(a.agent1.name)}</span>
            ${statusBadge(a.agent1.status)}
          </div>
          <p><strong>Processed:</strong> ${a.agent1.processed}</p>
          <p><strong>Qualified:</strong> ${a.agent1.passed} | <strong>Needs Review:</strong> ${a.agent1.needs_review}</p>
          <p><strong>Rejected:</strong> ${a.agent1.rejected}</p>
        </div>

        <div class="card">
          <div class="card-header">
            <span class="card-title">${escapeHtml(a.agent2.name)}</span>
            ${statusBadge(a.agent2.status)}
          </div>
          <p><strong>Scored Leads:</strong> ${a.agent2.scored_leads}</p>
          <p><strong>Priority A Selected:</strong> ${a.agent2.priority_a}</p>
          <p><strong>Messages Drafted:</strong> ${a.agent2.messages_drafted}</p>
        </div>

        <div class="card">
          <div class="card-header">
            <span class="card-title">${escapeHtml(a.agent3.name)}</span>
            ${statusBadge(a.agent3.status)}
          </div>
          <p><strong>Random Audit Pass Rate:</strong> ${a.agent3.last_audit_pass_rate}%</p>
          <p><strong>Contact Accuracy Rate:</strong> ${a.agent3.last_contact_accuracy}%</p>
          <p><strong>Submission Readiness:</strong> ${statusBadge(r.overall_status)}</p>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">Official Submission Readiness Summary</span>
          ${statusBadge(r.overall_status)}
        </div>
        <p style="margin-bottom:12px;">${escapeHtml(r.explanation)}</p>
        <div style="display:flex;gap:10px;flex-wrap:wrap;">
          <button class="btn btn-primary btn-sm" id="btn-overview-demo-run">Load & Run 35 Synthetic Demo Fixtures</button>
          <button class="btn btn-teal btn-sm" id="btn-overview-public-import">Import Genuine Public Research Records</button>
        </div>
      </div>
    `;

    renderOverviewCharts(data.country_distribution, data.qualification_funnel);

    document.getElementById("btn-overview-demo-run")?.addEventListener("click", async (e) => {
      e.target.disabled = true;
      showToast("Running full pipeline with 35 synthetic demo fixtures...", "info");
      try {
        await api.runFullPipeline({
          keyword: "video podcast creator",
          source: "synthetic_demo",
          run_mode: "synthetic_demo",
          max_candidates: 35,
        });
        showToast("Demo pipeline completed! Refreshing Overview...", "success");
        await renderOverviewPage(container);
      } catch (err) {
        showToast(err.message, "error");
        e.target.disabled = false;
      }
    });

    document.getElementById("btn-overview-public-import")?.addEventListener("click", async (e) => {
      e.target.disabled = true;
      showToast("Importing genuine public research records...", "info");
      try {
        await api.startDiscoveryRun({
          keyword: "public podcast chart research",
          source: "public_research_import",
          run_mode: "live",
          max_candidates: 105,
        });
        showToast("Imported genuine public research candidates!", "success");
        await renderOverviewPage(container);
      } catch (err) {
        showToast(err.message, "error");
        e.target.disabled = false;
      }
    });
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Failed to load overview: ${escapeHtml(err.message)}</div>`;
  }
}

function renderOverviewCharts(countryDist, funnel) {
  if (typeof window.Chart === "undefined") return;

  const ctxCountry = document.getElementById("chart-countries");
  if (ctxCountry) {
    if (countryChart) countryChart.destroy();
    const labels = Object.keys(countryDist || {});
    const values = Object.values(countryDist || {});
    countryChart = new window.Chart(ctxCountry, {
      type: "bar",
      data: {
        labels: labels.length ? labels : ["No Qualified Leads Yet"],
        datasets: [
          {
            label: "Qualified Creators",
            data: values.length ? values : [0],
            backgroundColor: "#0284c7",
            borderRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
      },
    });
  }

  const ctxFunnel = document.getElementById("chart-funnel");
  if (ctxFunnel) {
    if (funnelChart) funnelChart.destroy();
    funnelChart = new window.Chart(ctxFunnel, {
      type: "bar",
      data: {
        labels: ["Discovered", "Qualified", "Priority A", "Needs Review", "Rejected"],
        datasets: [
          {
            label: "Creators",
            data: [
              funnel.discovered || 0,
              funnel.qualified || 0,
              funnel.priority_a || 0,
              funnel.needs_review || 0,
              funnel.rejected || 0,
            ],
            backgroundColor: ["#0284c7", "#15803d", "#0d9488", "#f59e0b", "#ef4444"],
            borderRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
      },
    });
  }
}
