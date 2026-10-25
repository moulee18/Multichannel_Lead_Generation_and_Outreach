/**
 * Page Router for IncuBrix GrowthOS (11 Pages)
 */

export const PAGE_METADATA = {
  overview: {
    title: "Overview Dashboard",
    subtitle: "Database metrics, country distribution, qualification funnel, agent statuses & submission progress",
  },
  discovery: {
    title: "Creator Discovery (Agent 1)",
    subtitle: "Discover creators from YouTube API, Public Podcast RSS, or Verified Research with pre-verification deduplication",
  },
  creators: {
    title: "Creator Database & Evidence Passports",
    subtitle: "Search, filter, sort, and inspect full Lead Evidence Passports for all discovered creators",
  },
  verification: {
    title: "Verification Queue (Human-in-the-Loop)",
    subtitle: "Review unresolved NEEDS_REVIEW evidence claims and record audited qualification decisions",
  },
  intelligence: {
    title: "Lead Intelligence & Explainable Scoring (Agent 2)",
    subtitle: "100-point explainable lead scoring, Priority A selection, Contact Channel Explainer & AI content analysis",
  },
  outreach: {
    title: "Outreach Studio (Multi-Channel Sequences)",
    subtitle: "Inspect, edit, validate with AI Hallucination Guard, and approve 3-step sequences across Email, LinkedIn & Instagram",
  },
  agents: {
    title: "Agent Control Centre (Live Agent Monitor)",
    subtitle: "Run individual agents, full pipeline, or Smart Refresh with persistent checkpoints & error recovery",
  },
  audit: {
    title: "Quality Audit & Random 20-Lead Simulator (Agent 3)",
    subtitle: "Independent qualification audit, geographic compliance, duplicate check & reproducible 20-lead internal audit",
  },
  "seed-tests": {
    title: "Seed Test Lab (Safe 3-Channel Proof)",
    subtitle: "Participant-owned allowlisted test accounts, DRY_RUN default, tracking links, reply logging & error recovery",
  },
  submission: {
    title: "Submission Readiness Centre & Exporter",
    subtitle: "Official assessment readiness checklist, Product & Market Insight editor, 30-day launch kit & ZIP download",
  },
  settings: {
    title: "System Settings & Product Registry",
    subtitle: "API availability, shared LLM provider, scoring weights, confirmed IncuBrix capabilities & API usage logs",
  },
};
