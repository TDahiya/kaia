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
  sendMessage: (message: string, conversationId?: string, agentId?: string, documentIds: string[] = []) =>
    apiFetch("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
        agent_id: agentId,
        document_ids: documentIds,
      }),
    }),
  /** Streams the reply. `onEvent` fires for each server-sent event. */
  streamMessage: async (
    message: string,
    onEvent: (e: any) => void,
    conversationId?: string,
    documentIds: string[] = [],
  ) => {
    const token = await getToken();
    const res = await fetch(`${BACKEND_URL}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
        document_ids: documentIds,
      }),
    });
    if (!res.ok || !res.body) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Stream failed: ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // Events are separated by a blank line; keep any partial tail.
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const line = frame.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        try { onEvent(JSON.parse(line.slice(6))); } catch {}
      }
    }
  },

  getConversations: (limit = 20) => apiFetch(`/api/chat/conversations?limit=${limit}`),
  getMessages: (conversationId: string) => apiFetch(`/api/chat/conversations/${conversationId}/messages`),
  deleteConversation: (conversationId: string) =>
    apiFetch(`/api/chat/conversations/${conversationId}`, { method: "DELETE" }),

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

  /** Is the signed-in user the owner? Decided by the backend, never the client. */
  whoAmI: () => apiFetch("/api/system-status").then(() => true).catch(() => false),

  /** A signed-in non-owner gets a small guest pass instead of a 403 wall. */
  signupPass: () => apiFetch("/api/guest/signup-pass", { method: "POST" }),

  // Guest passes (owner-only)
  getPasses: () => apiFetch("/api/guest/passes"),
  createPass: (data: {
    label: string; days: number; max_messages: number; max_calls: number; note?: string;
  }) => apiFetch("/api/guest/passes", { method: "POST", body: JSON.stringify(data) }),
  setPassRevoked: (id: string, revoked: boolean) =>
    apiFetch(`/api/guest/passes/${id}?revoked=${revoked}`, { method: "PATCH" }),
  deletePass: (id: string) =>
    apiFetch(`/api/guest/passes/${id}?hard=true`, { method: "DELETE" }),
  getGuestCv: () => apiFetch("/api/guest/cv"),
  uploadGuestCv: async (file: File) => {
    const token = await getToken();
    const body = new FormData();
    body.append("file", file);
    const res = await fetch(`${BACKEND_URL}/api/guest/cv`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Upload failed: ${res.status}`);
    }
    return res.json();
  },

  // Documents
  uploadDocument: async (file: File, conversationId?: string) => {
    const token = await getToken();
    const body = new FormData();
    body.append("file", file);
    if (conversationId) body.append("conversation_id", conversationId);
    // No Content-Type header — the browser sets the multipart boundary.
    const res = await fetch(`${BACKEND_URL}/api/documents`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Upload failed: ${res.status}`);
    }
    return res.json();
  },
  getDocuments: (conversationId: string) =>
    apiFetch(`/api/documents?conversation_id=${conversationId}`),
  deleteDocument: (id: string) => apiFetch(`/api/documents/${id}`, { method: "DELETE" }),

  // Phone
  getPhoneNumbers: () => apiFetch("/api/telephony/phone-numbers"),
  callMe: () => apiFetch("/api/telephony/call-me", { method: "POST" }),
  getOwnerPhone: () => apiFetch("/api/telephony/owner-phone"),
  setOwnerPhone: (phone: string) =>
    apiFetch("/api/telephony/owner-phone", {
      method: "PUT",
      body: JSON.stringify({ phone }),
    }),
};
