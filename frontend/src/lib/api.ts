import { supabase } from "./supabase";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

async function getToken(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token || "";
}

async function apiFetch(path: string, options: RequestInit = {}): Promise<any> {
  const token = await getToken();
  const res = await fetch(`${BACKEND_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Chat
  sendMessage: (message: string, conversationId?: string, agentId?: string) =>
    apiFetch("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message, conversation_id: conversationId, agent_id: agentId }),
    }),
  getConversations: (limit = 20) => apiFetch(`/api/chat/conversations?limit=${limit}`),
  getMessages: (conversationId: string) => apiFetch(`/api/chat/conversations/${conversationId}/messages`),

  // Agents
  getAgents: () => apiFetch("/api/agents"),
  getAgent: (id: string) => apiFetch(`/api/agents/${id}`),
  createAgent: (data: any) => apiFetch("/api/agents", { method: "POST", body: JSON.stringify(data) }),
  updateAgent: (id: string, data: any) => apiFetch(`/api/agents/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteAgent: (id: string) => apiFetch(`/api/agents/${id}`, { method: "DELETE" }),
  cloneAgent: (id: string) => apiFetch(`/api/agents/${id}/clone`, { method: "POST" }),

  // Integrations
  getGoogleAuthUrl: () => apiFetch("/api/auth/google"),
  getGoogleStatus: () => apiFetch("/api/auth/google/status"),
  revokeGoogle: () => apiFetch("/api/auth/google/revoke", { method: "POST" }),

  // Usage
  getUsage: () => apiFetch("/api/usage"),
  getUsageHistory: (days = 30) => apiFetch(`/api/usage/history?days=${days}`),
  getCallLogs: () => apiFetch("/api/usage/call-logs"),

  // Memories
  getMemories: (category = "", activeOnly = true) =>
    apiFetch(`/api/memories?category=${category}&active_only=${activeOnly}`),
  createMemory: (data: any) => apiFetch("/api/memories", { method: "POST", body: JSON.stringify(data) }),
  updateMemory: (id: string, data: any) => apiFetch(`/api/memories/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteMemory: (id: string) => apiFetch(`/api/memories/${id}`, { method: "DELETE" }),
  getSummaries: () => apiFetch("/api/memories/summaries"),
  triggerSummarize: () => apiFetch("/api/memories/summarize-now", { method: "POST" }),

  // System
  getSystemStatus: () => apiFetch("/api/system-status"),
  getHealth: () => apiFetch("/api/health"),

  // Phone
  getPhoneNumbers: () => apiFetch("/api/telephony/phone-numbers"),
};
