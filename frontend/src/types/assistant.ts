export interface AssistantRunCreate {
  message: string;
  mode: "simulation_lab" | "research_review";
  thread_id?: string | null;
  parent_run_id?: string | null;
}

export interface AssistantToolCall {
  call_id: string;
  tool_name: string;
  input_payload: Record<string, unknown> | null;
  output_payload: Record<string, unknown> | null;
  status: string;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
}

export interface AssistantConfirmationRequest {
  confirmation_id: string;
  action_name: string;
  action_payload: Record<string, unknown> | null;
  status: string;
  reason: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface AssistantRunResponse {
  run_id: string;
  tenant_id: number;
  user_id: number;
  user_message: string;
  parsed_intent: Record<string, unknown>;
  status: string;
  result_summary: Record<string, unknown> | null;
  evidence_pack_id: string | null;
  tool_registry: Record<string, unknown> | null;
  team_plan?: Record<string, unknown>[];
  specialist_cards?: Record<string, unknown>[];
  handoff_records?: Record<string, unknown>[];
  review_verdicts?: Record<string, unknown>[];
  action_ledger?: Record<string, unknown>[];
  memory_tags?: string[];
  final_synthesis?: Record<string, unknown> | null;
  created_at: string;
  completed_at: string | null;
  tool_calls: AssistantToolCall[];
  confirmation_requests: AssistantConfirmationRequest[];
}

export interface AssistantConfirmRequest {
  confirmation_id: string;
  approved: boolean;
  reason?: string | null;
}

export interface HumanApprovalResolveRequest {
  approved: boolean;
  reason?: string | null;
}

export interface AssistantReviewConfirmationItem {
  confirmation_id: string;
  action_name: string;
  action_payload: Record<string, unknown> | null;
  status: string;
  reason: string | null;
  source_assistant_run_id: string;
  source_evidence_pack_id: string | null;
  evidence_pack_ids: string[];
  risk_guardrails: string[];
  created_at: string;
  resolved_at: string | null;
}

export interface AssistantReviewHumanApprovalItem {
  approval_request_id: string;
  release_decision_id: number | null;
  subject_type: string;
  subject_id: string;
  status: string;
  reason: string | null;
  payload: Record<string, unknown> | null;
  source_assistant_run_id: string | null;
  source_evidence_pack_id: string | null;
  evidence_pack_ids: string[];
  risk_guardrails: string[];
  created_at: string;
  resolved_at: string | null;
}

export interface AssistantReviewWorkbenchResponse {
  assistant_confirmations: AssistantReviewConfirmationItem[];
  human_approval_requests: AssistantReviewHumanApprovalItem[];
  guardrails: string[];
}
