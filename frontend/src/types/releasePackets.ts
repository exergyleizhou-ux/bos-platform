export interface SimulationAppendixAttachRequest {
  simulation_id: string;
  run_id?: string | null;
}

export interface ReleasePacketAttachment {
  attachment_id: string;
  release_decision_id: number;
  tenant_id: number;
  user_id: number;
  attachment_type: string;
  simulation_id: string | null;
  run_id: string | null;
  evidence_pack_id: string | null;
  appendix_hash: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface HumanApprovalRequestCreate {
  subject_type?: string;
  subject_id?: string | null;
  reason?: string | null;
  payload?: Record<string, unknown>;
}

export interface HumanApprovalRequest {
  approval_request_id: string;
  release_decision_id: number | null;
  tenant_id: number;
  user_id: number;
  subject_type: string;
  subject_id: string;
  status: string;
  reason: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
  resolved_at: string | null;
}
