"use client";

/**
 * useAgentChat — SSE stream parser and chat state manager.
 *
 * Connects to the agent SSE endpoint, parses events in real-time,
 * and maintains the message list with streaming text, tool activities,
 * clarifications, and dynamic UI widgets.
 */
import { useState, useCallback, useRef, useEffect } from "react";
import { agentService } from "@/services/agentService";
import type {
  AgentMessage,
  AgentEvent,
  ToolActivity,
  AgentHistoryMessage,
} from "@/types";

let _msgIdCounter = 0;
function nextId(): string {
  return `msg-${Date.now()}-${++_msgIdCounter}`;
}

interface UseAgentChatOptions {
  agentType: "teacher" | "mentor";
  courseId?: number;
  initialSessionId?: string;
  userId?: number;
}

export function useAgentChat({ agentType, courseId, initialSessionId, userId }: UseAgentChatOptions) {
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(initialSessionId || null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // Load history when session changes externally
  useEffect(() => {
    if (initialSessionId && initialSessionId !== sessionId) {
      switchSession(initialSessionId);
    }
  }, [initialSessionId]);

  const loadHistory = async (sid: string) => {
    setIsLoadingHistory(true);
    try {
      const history: AgentHistoryMessage[] = await agentService.getSessionMessages(sid);
      const mappedMessages: AgentMessage[] = history.map((m) => ({
        id: m.id,
        role: m.role as any,
        content: m.content || "",
        timestamp: new Date(m.created_at).getTime(),
        toolActivities: m.metadata?.toolActivities || [],
        uiComponent: m.metadata?.uiComponent,
        hitlRequest: m.metadata?.hitlRequest,
      }));
      setMessages(mappedMessages);
    } catch (err) {
      console.error("Failed to load session history:", err);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  const switchSession = useCallback(async (newSessionId: string) => {
    stopStreaming();
    setSessionId(newSessionId);
    setMessages([]);
    await loadHistory(newSessionId);
  }, []);

  const startNewChat = useCallback(async () => {
    stopStreaming();
    try {
      if (!userId) return;
      const res = await agentService.createNewSession({
        agent_type: agentType,
        course_id: courseId,
      });
      setSessionId(res.session_id);
      setMessages([]);
    } catch (err) {
      console.error("Failed to start entirely new chat:", err);
      // Fallback
      setSessionId(null);
      setMessages([]);
    }
  }, [agentType, courseId, userId]);

  /**
   * Send a message and process the SSE stream.
   */
  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isStreaming) return;

      // Add user message
      const userMsg: AgentMessage = {
        id: nextId(),
        role: "user",
        content: text,
        timestamp: Date.now(),
      };

      // Add placeholder assistant message
      const assistantMsg: AgentMessage = {
        id: nextId(),
        role: "assistant",
        content: "",
        isStreaming: true,
        timestamp: Date.now(),
        thinkingSteps: [],
        toolActivities: [],
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsStreaming(true);
      setIsThinking(true);

      const assistantId = assistantMsg.id;

      try {
        abortRef.current = new AbortController();

        const response = await fetch("/api/ai/agents/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: text,
            agent_type: agentType,
            course_id: courseId,
            session_id: sessionId,
          }),
          signal: abortRef.current.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error(`Request failed: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          // Keep the last potentially-incomplete line in the buffer
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const raw = line.slice(6).trim();
            if (!raw) continue;

            let event: AgentEvent;
            try {
              event = JSON.parse(raw);
            } catch {
              continue;
            }

            processEvent(event, assistantId);
          }
        }

        // Process any remaining buffer
        if (buffer.startsWith("data: ")) {
          const raw = buffer.slice(6).trim();
          if (raw) {
            try {
              processEvent(JSON.parse(raw), assistantId);
            } catch {
              /* ignore */
            }
          }
        }
      } catch (err: any) {
        if (err.name !== "AbortError") {
          updateAssistant(assistantId, (msg) => ({
            ...msg,
            content:
              msg.content || "Đã xảy ra lỗi kết nối. Vui lòng thử lại.",
            isStreaming: false,
          }));
        }
      } finally {
        setIsStreaming(false);
        setIsThinking(false);
        abortRef.current = null;

        // Ensure streaming flag is cleared
        updateAssistant(assistantId, (msg) => ({
          ...msg,
          isStreaming: false,
        }));
      }
    },
    [agentType, courseId, sessionId, isStreaming],
  );

  /**
   * Process a single SSE event and update the assistant message.
   */
  function processEvent(event: AgentEvent, assistantId: string) {
    switch (event.type) {
      case "session":
        setSessionId(event.data.session_id);
        break;

      case "thinking":
        setIsThinking(true);
        updateAssistant(assistantId, (msg) => ({
          ...msg,
          thinkingSteps: [
            ...(msg.thinkingSteps || []),
            {
              step: event.data.step,
              detail: event.data.intent || event.data.token_estimate?.toString(),
            },
          ],
        }));
        break;

      case "text_delta":
        setIsThinking(false);
        updateAssistant(assistantId, (msg) => ({
          ...msg,
          content: msg.content + (event.data.delta || ""),
        }));
        break;

      case "tool_start":
        setIsThinking(false);
        updateAssistant(assistantId, (msg) => ({
          ...msg,
          toolActivities: [
            ...(msg.toolActivities || []),
            {
              tool: event.data.tool,
              status: "running" as const,
              args: event.data.args,
            },
          ],
        }));
        break;

      case "tool_result":
        updateAssistant(assistantId, (msg) => ({
          ...msg,
          toolActivities: (msg.toolActivities || []).map((t) =>
            t.tool === event.data.tool
              ? {
                  ...t,
                  status: (event.data.status === "error"
                    ? "error"
                    : "done") as ToolActivity["status"],
                  message: event.data.message,
                }
              : t,
          ),
        }));
        break;

      case "ui_component":
        updateAssistant(assistantId, (msg) => ({
          ...msg,
          uiComponent: event.data as any,
        }));
        break;

      case "clarification":
        setIsThinking(false);
        updateAssistant(assistantId, (msg) => ({
          ...msg,
          content: event.data.question || msg.content,
          clarification: event.data as any,
          isStreaming: false,
        }));
        break;

      case "hitl_request":
        updateAssistant(assistantId, (msg) => ({
          ...msg,
          hitlRequest: event.data as any,
        }));
        break;

      case "done":
        setIsThinking(false);
        updateAssistant(assistantId, (msg) => ({
          ...msg,
          isStreaming: false,
        }));
        break;

      case "error":
        setIsThinking(false);
        updateAssistant(assistantId, (msg) => ({
          ...msg,
          content:
            msg.content || event.data.error || "Đã xảy ra lỗi.",
          isStreaming: false,
        }));
        break;
    }
  }

  /**
   * Update the assistant message by ID using an updater function.
   */
  function updateAssistant(
    id: string,
    updater: (msg: AgentMessage) => AgentMessage,
  ) {
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? updater(m) : m)),
    );
  }

  /**
   * Abort the current SSE stream.
   */
  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
    setIsThinking(false);
  }, []);

  /**
   * Clear all messages and reset session.
   */
  const clearChat = useCallback(() => {
    setMessages([]);
    setSessionId(null);
  }, []);

  return {
    messages,
    sessionId,
    isStreaming,
    isThinking,
    isLoadingHistory,
    sendMessage,
    stopStreaming,
    clearChat,
    switchSession,
    startNewChat,
  };
}
