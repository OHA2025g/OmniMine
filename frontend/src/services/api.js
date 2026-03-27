import axios from 'axios';

const API_URL = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Feedback APIs
export const getFeedbacks = async (params = {}) => {
  const response = await axios.get(`${API_URL}/feedback`, { params });
  return response.data;
};

export const getFeedback = async (id) => {
  const response = await axios.get(`${API_URL}/feedback/${id}`);
  return response.data;
};

export const createFeedback = async (data) => {
  const response = await axios.post(`${API_URL}/feedback`, data);
  return response.data;
};

// Dev / testing
export const generateDummyFeedback = async () => {
  const response = await axios.post(`${API_URL}/dev/dummy-feedback`, {});
  return response.data;
};

export const generateDummyFeedbackBatch = async (count = 10, negativeMin = 0.55, negativeMax = 0.6) => {
  const response = await axios.post(`${API_URL}/dev/dummy-feedback/batch`, {
    count,
    negative_min: negativeMin,
    negative_max: negativeMax,
  });
  return response.data;
};

export const bulkCreateFeedback = async (feedbacks) => {
  const response = await axios.post(`${API_URL}/feedback/bulk`, { feedbacks });
  return response.data;
};

export const reanalyzeFeedback = async (id) => {
  const response = await axios.post(`${API_URL}/feedback/${id}/analyze`);
  return response.data;
};

// Cases APIs
export const getCases = async (params = {}) => {
  const response = await axios.get(`${API_URL}/cases`, { params });
  return response.data;
};

export const getCase = async (id) => {
  const response = await axios.get(`${API_URL}/cases/${id}`);
  return response.data;
};

export const createCase = async (data) => {
  const response = await axios.post(`${API_URL}/cases`, data);
  return response.data;
};

export const assignCase = async (caseId, assigneeId) => {
  const response = await axios.put(`${API_URL}/cases/${caseId}/assign?assignee_id=${assigneeId}`);
  return response.data;
};

export const startCaseWork = async (caseId) => {
  const response = await axios.put(`${API_URL}/cases/${caseId}/start`);
  return response.data;
};

export const resolveCase = async (caseId, resolutionNotes) => {
  const response = await axios.put(`${API_URL}/cases/${caseId}/resolve?resolution_notes=${encodeURIComponent(resolutionNotes)}`);
  return response.data;
};

export const verifyCase = async (caseId, data) => {
  const response = await axios.post(`${API_URL}/cases/${caseId}/verify`, data);
  return response.data;
};

export const uploadCaseEvidence = async (caseId, file, note) => {
  const formData = new FormData();
  formData.append('file', file);
  if (note) formData.append('note', note);
  const response = await axios.post(`${API_URL}/cases/${caseId}/evidence`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const getCaseLogs = async (caseId) => {
  const response = await axios.get(`${API_URL}/cases/${caseId}/logs`);
  return response.data;
};

// Surveys APIs
export const getSurveys = async (params = {}) => {
  const response = await axios.get(`${API_URL}/surveys`, { params });
  return response.data;
};

export const createSurvey = async (data) => {
  const response = await axios.post(`${API_URL}/surveys`, data);
  return response.data;
};

// Alerts APIs
export const getAlerts = async (unreadOnly = false) => {
  const response = await axios.get(`${API_URL}/alerts`, { params: { unread_only: unreadOnly } });
  return response.data;
};

export const markAlertRead = async (id) => {
  const response = await axios.put(`${API_URL}/alerts/${id}/read`);
  return response.data;
};

export const markAllAlertsRead = async () => {
  const response = await axios.put(`${API_URL}/alerts/read-all`);
  return response.data;
};

// Users APIs
export const getUsers = async (params = {}) => {
  const response = await axios.get(`${API_URL}/users`, { params });
  return response.data;
};

export const updateUserRole = async (userId, newRole) => {
  const response = await axios.put(`${API_URL}/users/${userId}/role?new_role=${newRole}`);
  return response.data;
};

// Teams APIs
export const getTeams = async () => {
  const response = await axios.get(`${API_URL}/teams`);
  return response.data;
};

export const createTeam = async (name, description) => {
  const response = await axios.post(`${API_URL}/teams?name=${encodeURIComponent(name)}&description=${encodeURIComponent(description || '')}`);
  return response.data;
};

export const addTeamMember = async (teamId, memberId) => {
  const response = await axios.put(`${API_URL}/teams/${teamId}/members?member_id=${memberId}`);
  return response.data;
};

// Analytics APIs
export const getAnalyticsOverview = async () => {
  const response = await axios.get(`${API_URL}/analytics/overview`);
  return response.data;
};

export const getSentimentTrends = async (days = 30) => {
  const response = await axios.get(`${API_URL}/analytics/sentiment-trends`, { params: { days } });
  return response.data;
};

export const getSourceDistribution = async () => {
  const response = await axios.get(`${API_URL}/analytics/source-distribution`);
  return response.data;
};

export const getThemeDistribution = async () => {
  const response = await axios.get(`${API_URL}/analytics/themes`);
  return response.data;
};

export const getEmotionDistribution = async () => {
  const response = await axios.get(`${API_URL}/analytics/emotions`);
  return response.data;
};

// Demo Data
export const seedDemoData = async () => {
  const response = await axios.post(`${API_URL}/demo/seed`);
  return response.data;
};

// Agentic AI (Phase 2)
export const agenticTriageFeedback = async (feedbackId) => {
  const response = await axios.post(`${API_URL}/agentic/triage/feedback/${feedbackId}`);
  return response.data;
};

export const agenticResponseDraft = async (caseId) => {
  const response = await axios.post(`${API_URL}/agentic/response/case/${caseId}`);
  return response.data;
};

export const getExecutiveDigest = async (days = 7) => {
  const response = await axios.get(`${API_URL}/agentic/executive/digest`, { params: { days } });
  return response.data;
};

// Agentic Orchestration (Phase C)
export const startCaseOrchestration = async (caseId) => {
  const response = await axios.post(`${API_URL}/agentic/orchestrations/case/${caseId}`);
  return response.data;
};

export const getOrchestrationRun = async (runId) => {
  const response = await axios.get(`${API_URL}/agentic/orchestrations/${runId}`);
  return response.data;
};

export const decideOrchestrationGate = async (runId, stepKey, decision, note) => {
  const response = await axios.post(`${API_URL}/agentic/orchestrations/${runId}/gates/${stepKey}`, {
    decision,
    note,
  });
  return response.data;
};

export const resumeOrchestration = async (runId) => {
  const response = await axios.post(`${API_URL}/agentic/orchestrations/${runId}/resume`);
  return response.data;
};

// Monitoring (Phase B)
export const getMonitoringLive = async () => {
  const response = await axios.get(`${API_URL}/monitoring/live`);
  return response.data;
};

// Orgs (Phase 4)
export const listOrgs = async () => {
  const response = await axios.get(`${API_URL}/orgs`);
  return response.data;
};

export const switchOrg = async (orgId) => {
  const response = await axios.post(`${API_URL}/auth/switch-org`, { org_id: orgId });
  return response.data;
};

// Admin console
export const getAdminSummary = async () => {
  const response = await axios.get(`${API_URL}/admin/summary`);
  return response.data;
};

export const createOrg = async (name) => {
  const response = await axios.post(`${API_URL}/orgs`, { name });
  return response.data;
};

export const moveUserToOrg = async (orgId, userId) => {
  const response = await axios.put(`${API_URL}/orgs/${orgId}/users/${userId}`);
  return response.data;
};

export const queryAuditEvents = async (payload = {}) => {
  const response = await axios.post(`${API_URL}/audit`, payload);
  return response.data;
};

export const exportAuditCsv = async (payload = {}) => {
  const response = await axios.post(`${API_URL}/audit/export/csv`, payload, { responseType: 'blob' });
  return response.data;
};

export const bulkUserAction = async (data) => {
  const response = await axios.post(`${API_URL}/users/bulk-action`, data);
  return response.data;
};

export const getSystemSettings = async () => {
  const response = await axios.get(`${API_URL}/settings/system`);
  return response.data;
};

export const updateSystemSettings = async (data) => {
  const response = await axios.put(`${API_URL}/settings/system`, data);
  return response.data;
};
