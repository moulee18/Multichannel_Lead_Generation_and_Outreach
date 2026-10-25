/**
 * IncuBrix GrowthOS API Client
 */

export async function apiRequest(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    "X-GrowthOS-Client": "local-web-ui",
    ...(options.headers || {}),
  };

  const token = localStorage.getItem("growthos_token");
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(path, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errDetail = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      if (data.detail) {
        if (typeof data.detail === "string") {
          errDetail = data.detail;
        } else if (data.detail.message) {
          errDetail = `${data.detail.error || "ERROR"}: ${data.detail.message}`;
        } else {
          errDetail = JSON.stringify(data.detail);
        }
      }
    } catch {
      errDetail = await response.text();
    }
    throw new Error(errDetail);
  }

  return response.json();
}

export const api = {
  getHealth: () => apiRequest("/api/health"),
  getOverview: () => apiRequest("/api/overview"),
  getConfigStatus: () => apiRequest("/api/config/status"),
  updateScoring: (payload) =>
    apiRequest("/api/config/scoring", { method: "POST", body: JSON.stringify(payload) }),
  saveCapability: (payload) =>
    apiRequest("/api/config/capabilities", { method: "POST", body: JSON.stringify(payload) }),
  updateInsight: (payload) =>
    apiRequest("/api/config/insights", { method: "POST", body: JSON.stringify(payload) }),

  // Discovery
  getKeywords: () => apiRequest("/api/discovery/keywords"),
  startDiscoveryRun: (payload) =>
    apiRequest("/api/discovery/runs", { method: "POST", body: JSON.stringify(payload) }),
  listDiscoveryRuns: () => apiRequest("/api/discovery/runs"),
  getDiscoveryRun: (runId) => apiRequest(`/api/discovery/runs/${runId}`),
  cancelDiscoveryRun: (runId) =>
    apiRequest(`/api/discovery/runs/${runId}/cancel`, { method: "POST" }),

  // Creators & Evidence Passport
  listCreators: (params = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") qs.set(k, v);
    });
    return apiRequest(`/api/creators?${qs.toString()}`);
  },
  getCreator: (id) => apiRequest(`/api/creators/${id}`),
  getCreatorEvidencePassport: (id) => apiRequest(`/api/creators/${id}/evidence`),
  submitCreatorReview: (id, payload) =>
    apiRequest(`/api/creators/${id}/review`, { method: "POST", body: JSON.stringify(payload) }),

  // Lead Intelligence & Scoring
  runIntelligence: (payload = {}) =>
    apiRequest("/api/intelligence/runs", { method: "POST", body: JSON.stringify(payload) }),
  getRankedLeads: (includeSynthetic = true) =>
    apiRequest(`/api/leads/ranked?include_synthetic=${includeSynthetic}`),
  getPriorityALeads: (includeSynthetic = true) =>
    apiRequest(`/api/leads/priority-a?include_synthetic=${includeSynthetic}`),
  getLeadScoreExplainer: (creatorId) => apiRequest(`/api/leads/${creatorId}/score`),
  getChannelExplainer: (creatorId) => apiRequest(`/api/leads/${creatorId}/channels`),

  // Outreach Studio
  generateOutreach: (payload) =>
    apiRequest("/api/outreach/generate", { method: "POST", body: JSON.stringify(payload) }),
  getCreatorOutreach: (creatorId) => apiRequest(`/api/outreach/creators/${creatorId}`),
  patchOutreachMessage: (messageId, payload) =>
    apiRequest(`/api/outreach/messages/${messageId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  reviewOutreachMessage: (messageId, payload) =>
    apiRequest(`/api/outreach/messages/${messageId}/review`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Quality Audits
  getAuditsOverview: (includeSynthetic = true, randomSeed = 42) =>
    apiRequest(`/api/audits/overview?include_synthetic=${includeSynthetic}&random_seed=${randomSeed}`),
  runAudit: (payload) =>
    apiRequest("/api/audits/run", { method: "POST", body: JSON.stringify(payload) }),
  getAuditById: (auditId) => apiRequest(`/api/audits/${auditId}`),

  // Seed Test Lab
  listSeedAccounts: () => apiRequest("/api/seed-tests/accounts/list"),
  addSeedAccount: (payload) =>
    apiRequest("/api/seed-tests/accounts", { method: "POST", body: JSON.stringify(payload) }),
  listSeedTests: () => apiRequest("/api/seed-tests"),
  createSeedTest: (payload) =>
    apiRequest("/api/seed-tests", { method: "POST", body: JSON.stringify(payload) }),
  triggerSeedClick: (token) => apiRequest(`/api/seed-tests/track/${token}`),
  recordSeedReply: (testId, payload) =>
    apiRequest(`/api/seed-tests/${testId}/replies`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Exports & Submission
  listExports: () => apiRequest("/api/exports"),
  generateExports: (payload = { include_synthetic: true }) =>
    apiRequest("/api/exports", { method: "POST", body: JSON.stringify(payload) }),

  // Pipeline & Smart Refresh
  runFullPipeline: (payload) =>
    apiRequest("/api/pipeline/run", { method: "POST", body: JSON.stringify(payload) }),
  runSmartRefresh: (payload = {}) =>
    apiRequest("/api/pipeline/refresh", { method: "POST", body: JSON.stringify(payload) }),
  listPipelineRuns: () => apiRequest("/api/pipeline/runs"),
};
