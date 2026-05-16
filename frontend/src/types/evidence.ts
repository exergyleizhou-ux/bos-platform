import type { EvidenceSourceKind } from "@/types/simulationLab";

export interface EvidenceItemCreate {
  kind: string;
  source_kind: EvidenceSourceKind;
  source_ref?: string | null;
  payload?: Record<string, unknown>;
  confidence?: number;
  uncertainty_level?: "low" | "medium" | "high";
}

export interface EvidencePackCreate {
  subject_type: string;
  subject_id: string;
  title: string;
  summary?: string | null;
  verification_status?: string;
  human_review_required?: boolean;
  items?: EvidenceItemCreate[];
}

export interface EvidenceItemResponse extends Required<Omit<EvidenceItemCreate, "source_ref" | "payload">> {
  evidence_item_id: string;
  evidence_pack_id: string;
  tenant_id: number;
  source_ref: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface EvidencePackResponse {
  evidence_pack_id: string;
  tenant_id: number;
  user_id: number;
  subject_type: string;
  subject_id: string;
  title: string;
  summary: string | null;
  verification_status: string;
  human_review_required: boolean;
  created_at: string;
  items: EvidenceItemResponse[];
}

export interface InputSnapshotResponse {
  input_snapshot_id: string;
  tenant_id: number;
  subject_type: string;
  subject_id: string;
  payload: Record<string, unknown>;
  payload_hash: string;
  created_at: string;
}
