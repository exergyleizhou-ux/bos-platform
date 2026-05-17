/**
 * BOS Agent API client (Phase A6).
 *
 * Talks to the independent LangGraph service. Default base URL is
 * the empty string so Vite's dev-server proxy rewrites `/agent/*` to
 * `http://localhost:8001`. Override with `VITE_AGENT_BASE_URL` for
 * direct cross-origin calls (e.g. production behind a different
 * host).
 *
 * This client deliberately does NOT share the axios instance from
 * `@/api/client` because:
 *   1. Different base URL.
 *   2. No auth interceptor today — the agent endpoint is intended
 *      for operator chat and Phase A6 ships without auth gating.
 *      Phase B will wire JWT forwarding.
 */

import axios from "axios";

const baseURL = import.meta.env.VITE_AGENT_BASE_URL ?? "";

export const agentClient = axios.create({
  baseURL,
  timeout: 60_000,
  headers: { "Content-Type": "application/json" },
});

// ────────────────────────────────────────────────────────────────────
// Types — mirror agent/server.py AgentRunRequest / AgentRunResponse
// ────────────────────────────────────────────────────────────────────

export interface AgentToolCallRecord {
  tool: string;
  endpoint?: string;
  started_at?: string;
  duration_ms?: number;
  status?: "ok" | "error";
  error?: string | null;
  evidence_level?: "validated" | "supported" | "planned" | null;
}

export interface AgentRunRequest {
  message: string;
  state?: Record<string, unknown>;
  thread_id?: string | null;
}

export interface AgentRunResponse {
  thread_id: string;
  intent: string | null;
  report: string | null;
  ser: number | null;
  sfi_pass: boolean | null;
  sfi_zone: string | null;
  simulation_result: Record<string, unknown> | null;
  cyber_experiment: Record<string, unknown> | null;
  evidence_level: "validated" | "supported" | "planned" | null;
  tool_calls: AgentToolCallRecord[];
}

export interface AgentHealthResponse {
  status: string;
  service: string;
  version: string;
  core_url: string;
}

// ────────────────────────────────────────────────────────────────────
// API methods
// ────────────────────────────────────────────────────────────────────

export async function getAgentHealth(): Promise<AgentHealthResponse> {
  const { data } = await agentClient.get<AgentHealthResponse>("/agent/health");
  return data;
}

export async function createAgentRun(
  body: AgentRunRequest,
): Promise<AgentRunResponse> {
  const { data } = await agentClient.post<AgentRunResponse>(
    "/agent/runs",
    body,
  );
  return data;
}
