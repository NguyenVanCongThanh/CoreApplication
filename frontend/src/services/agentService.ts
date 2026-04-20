/**
 * agentService.ts
 * Frontend client for the Agent Chat system (Phase 4).
 *
 * Uses raw fetch() (not axios) because we need access to the
 * ReadableStream for SSE parsing.
 */
import type { AgentChatRequest, AgentSession } from "@/types";
import { lmsApiClient } from "./lmsApiClient";

/**
 * Send a chat message and get an SSE stream response.
 *
 * Returns the raw Response — the caller (useAgentChat hook)
 * reads the stream via response.body.getReader().
 */
export async function sendAgentMessage(
  req: Omit<AgentChatRequest, "user_id">,
): Promise<Response> {
  const response = await fetch("/api/ai/agents/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });

  if (!response.ok) {
    const err = await response.text().catch(() => "Request failed");
    throw new Error(err);
  }

  return response;
}

/**
 * List recent chat sessions for the current user.
 * Goes through Go lms-service proxy (not SSE, normal REST).
 */
export async function listAgentSessions(
  userId: number,
  agentType?: "teacher" | "mentor",
): Promise<AgentSession[]> {
  const params: Record<string, any> = { user_id: userId };
  if (agentType) params.agent_type = agentType;

  const res = await lmsApiClient.get("/ai/agents/sessions", { params });
  return res.data?.sessions ?? [];
}

export const agentService = {
  sendMessage: sendAgentMessage,
  listSessions: listAgentSessions,
};
