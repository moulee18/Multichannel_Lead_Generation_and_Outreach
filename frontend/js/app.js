/**
 * Main Application Entry Point — IncuBrix GrowthOS
 */
import { api } from "./api.js";
import { closeModal, showToast } from "./components/modals.js";
import { PAGE_METADATA } from "./router.js";
import { renderOverviewPage } from "./pages/overview.js";
import { renderDiscoveryPage } from "./pages/discovery.js";
import { renderCreatorsPage } from "./pages/creators.js";
import { renderVerificationPage } from "./pages/verification.js";
import { renderIntelligencePage } from "./pages/intelligence.js";
import { renderOutreachPage } from "./pages/outreach.js";
import { renderAgentsPage } from "./pages/agents.js";
import { renderAuditPage } from "./pages/audit.js";
import { renderSeedTestsPage } from "./pages/seed-tests.js";
import { renderSubmissionPage } from "./pages/submission.js";
import { renderSettingsPage } from "./pages/settings.js";

const PAGE_RENDERERS = {
  overview: renderOverviewPage,
  discovery: renderDiscoveryPage,
  creators: renderCreatorsPage,
  verification: renderVerificationPage,
  intelligence: renderIntelligencePage,
  outreach: renderOutreachPage,
  agents: renderAgentsPage,
  audit: renderAuditPage,
  "seed-tests": renderSeedTestsPage,
  submission: renderSubmissionPage,
  settings: renderSettingsPage,
};

let currentPage = "overview";

export async function navigateTo(pageKey) {
  const key = PAGE_RENDERERS[pageKey] ? pageKey : "overview";
  currentPage = key;

  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.page === key);
  });

  const meta = PAGE_METADATA[key];
  const titleEl = document.getElementById("page-title");
  const subEl = document.getElementById("page-subtitle");
  if (titleEl && meta) titleEl.textContent = meta.title;
  if (subEl && meta) subEl.textContent = meta.subtitle;

  document.getElementById("sidebar")?.classList.remove("open");

  const container = document.getElementById("workspace-content");
  if (container) {
    await PAGE_RENDERERS[key](container);
  }
}

async function initApp() {
  // Bind navigation buttons
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      navigateTo(btn.dataset.page);
    });
  });

  // Mobile menu button
  document.getElementById("mobile-menu-btn")?.addEventListener("click", () => {
    document.getElementById("sidebar")?.classList.toggle("open");
  });

  // Modal close handlers
  document.getElementById("modal-close-btn")?.addEventListener("click", closeModal);
  document.getElementById("global-modal-backdrop")?.addEventListener("click", (e) => {
    if (e.target.id === "global-modal-backdrop") closeModal();
  });

  // Topbar quick action buttons
  document.getElementById("btn-quick-refresh")?.addEventListener("click", async (e) => {
    e.target.disabled = true;
    showToast("Running Smart Refresh across stored creators...", "info");
    try {
      const r = await api.runSmartRefresh({});
      showToast(
        `Smart Refresh complete: ${r.updated_creators_count} updated, ${r.unchanged_records_count} unchanged.`,
        "success"
      );
      await navigateTo(currentPage);
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      e.target.disabled = false;
    }
  });

  document.getElementById("btn-quick-pipeline")?.addEventListener("click", async (e) => {
    e.target.disabled = true;
    showToast("Running Full 3-Agent Pipeline...", "info");
    try {
      await api.runFullPipeline({
        keyword: "video podcast creator",
        source: "synthetic_demo",
        run_mode: "synthetic_demo",
        max_candidates: 35,
      });
      showToast("Full 3-Agent Pipeline completed!", "success");
      await navigateTo(currentPage);
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      e.target.disabled = false;
    }
  });

  // Check API health
  try {
    const h = await api.getHealth();
    const healthText = document.getElementById("health-text");
    if (healthText) {
      healthText.textContent = `API Healthy (${h.total_creators_in_db} creators)`;
    }
  } catch {
    const healthText = document.getElementById("health-text");
    if (healthText) healthText.textContent = "API Offline";
  }

  await navigateTo("overview");
}

window.addEventListener("DOMContentLoaded", initApp);
