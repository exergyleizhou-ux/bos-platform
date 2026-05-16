import { useCallback, useEffect, useState } from "react";
import { Check, Download, FileStack, GitBranch, Lock, Network, PlayCircle, Radar, ShieldCheck, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";

import { assistantApi } from "@/api/assistantApi";
import { bosApi } from "@/api/bosApi";
import { bosKernelsApi } from "@/api/bosKernelsApi";
import { finalActionsApi } from "@/api/finalActionsApi";
import { governanceApi } from "@/api/governanceApi";
import { releasePacketApi } from "@/api/releasePacketApi";
import { simulationLabApi } from "@/api/simulationLabApi";
import { BrainOperatorContextCard } from "@/components/bos/BrainOperatorContextCard";
import { ReleaseReadinessCard } from "@/components/code/ReleaseReadinessCard";
import { Badge } from "@/components/ui/Badge";
import {
  CockpitPanel,
  CockpitSectionLabel,
} from "@/components/ui/Cockpit";
import { ErrorState } from "@/components/ui/EmptyState";
import { SpinnerOverlay } from "@/components/ui/Spinner";
import { useBrainRuntime, useRecentTimeseriesRisks } from "@/hooks/useBos";
import { useCodeReleaseReadiness } from "@/hooks/code/useCode";
import { deriveAutonomyPriority } from "@/lib/autonomyActions";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { translateText } from "@/lib/i18n";
import {
  buildReviewedCandidateEvidenceSummary,
  formatReviewedCandidateGuardrail,
  type ReviewedCandidateEvidenceSummary,
} from "@/lib/reviewedCandidateEvidence";
import { downloadBlob, formatNumber } from "@/lib/utils";
import type {
  BenchmarkCase,
  BenchmarkRun,
  ExternalKnowledgeCandidateMatrix,
  ExternalKnowledgePromotionResponse,
  ExternalKnowledgeRuntimeActivationDraft,
  ExternalKnowledgeRuntimeActivationExecutionReadiness,
  ExternalKnowledgeRuntimeActivationReadiness,
  ExternalKnowledgeRuntimeActivationRecord,
  ExternalKnowledgeRuntimeActivationState,
  ExternalKnowledgeRegistryPatchResponse,
  ExternalKnowledgeValidatedRegistry,
  KnowledgeRelation,
  ModelGovernanceResponse,
  ModelProviderCapabilityMatrix,
  ModelRegistrationResponse,
  ModelRegistryItem,
} from "@/types/bosKernels";
import type { HumanApprovalRequest, ReleasePacketAttachment } from "@/types/releasePackets";
import type {
  AssistantReviewHumanApprovalItem,
  AssistantReviewWorkbenchResponse,
  AssistantRunResponse,
} from "@/types/assistant";
import type {
  FinalActionAuditRecordItem,
  FinalActionAuditRecordListResponse,
  FinalActionReadinessResponse,
  FinalActionRequestDraftItem,
  FinalActionRequestDraftListResponse,
  FinalActionReviewPacketSnapshotResponse,
} from "@/types/finalActions";
import type {
  LiteratureValueReleaseEvidenceLinkResponse,
  LiteratureValuePromotionAuditExportResponse,
  ReviewedExternalCandidate,
  ReviewedExternalCandidateActivationPreviewResponse,
  ReviewedExternalCandidateLaneSummary,
  ReviewedExternalCandidateListResponse,
  ReviewedExternalCandidateRollbackPreviewResponse,
  ReviewedExternalCandidateRuntimeReadinessResponse,
} from "@/types/bos";
import type { BOSV9RCManifestResponse } from "@/types/governance";
import type { SimulationReleaseAppendixResponse } from "@/types/simulationLab";

interface ReleaseProofCard {
  kind: "compliance" | "lca" | "tea" | "uncertainty";
  title: string;
  status: string;
  evidencePackId: string | null;
  resultId: string | null;
  lines: string[];
}

function summaryRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function displayAuditValue(value: unknown, fallback = "pending"): string {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.map((item) => displayAuditValue(item, "")).filter(Boolean).join(", ");
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .filter(([, entryValue]) => entryValue !== null && entryValue !== undefined && entryValue !== "")
      .slice(0, 4)
      .map(([key, entryValue]) => `${key}: ${displayAuditValue(entryValue, "pending")}`);
    return entries.length ? entries.join(" / ") : fallback;
  }
  return fallback;
}

function mergeReviewWorkbenchHistory(
  ...responses: AssistantReviewWorkbenchResponse[]
): AssistantReviewWorkbenchResponse {
  return {
    assistant_confirmations: responses.flatMap((response) => response.assistant_confirmations),
    human_approval_requests: responses.flatMap((response) => response.human_approval_requests),
    guardrails: Array.from(new Set(responses.flatMap((response) => response.guardrails))),
  };
}

function humanApprovalSideEffectLines(item: AssistantReviewHumanApprovalItem): string[] {
  const payload = summaryRecord(item.payload);
  const resolution = summaryRecord(payload.workbench_resolution);
  const sideEffects = summaryRecord(resolution.side_effects);
  return Object.entries(sideEffects).map(([key, value]) => `${key}: ${String(value)}`);
}

function finalActionLabel(action: string): string {
  if (action === "final_release_approval") return "Final release approval";
  if (action === "model_activation") return "Model activation";
  if (action === "external_release_share") return "External release share";
  return action;
}

function finalActionExecuteLabel(action: string): string {
  if (action === "final_release_approval") return "Execute final release approval";
  if (action === "model_activation") return "Activate model version";
  if (action === "external_release_share") return "Prepare external share approval";
  return "Execute final action";
}

const RC_MANIFEST_REVIEW_ARTIFACT_KEYS = [
  "release_dossier",
  "release_manifest",
  "bos_v9_rc_manifest",
  "release_reference_joint_smoke_json",
  "provider_live_smoke_json",
  "code_smoke_json",
  "bos_smoke_json",
  "bos_mechanistic_smoke_json",
  "frontend_build_entry",
] as const;

function releaseArtifactLabel(key: string): string {
  return key
    .split("_")
    .map((part) => (part === "rc" ? "RC" : part === "json" ? "JSON" : part.toUpperCase() === "BOS" ? "BOS" : part))
    .join(" ");
}

const FINAL_ACTION_DRAFT_WORKFLOW_BLOCKERS = new Set([
  "request_draft_required",
  "approved_request_draft_required",
  "specific_final_action_approver_role_required",
]);

function finalActionDraftGateBlockers(action: FinalActionReadinessResponse["actions"][number]): string[] {
  return action.blockers.filter((blocker) => !FINAL_ACTION_DRAFT_WORKFLOW_BLOCKERS.has(blocker));
}

function canCreateFinalActionDraft(
  readiness: FinalActionReadinessResponse | null,
  action: FinalActionReadinessResponse["actions"][number],
): boolean {
  return Boolean(
    readiness?.source_review_packet_id &&
    action.missing_evidence_ids.length === 0 &&
    finalActionDraftGateBlockers(action).length === 0,
  );
}

function latestPreparedExternalShareId(records: FinalActionAuditRecordItem[] = []): string | null {
  const record = records.find(
    (item) =>
      item.action_type === "external_release_share" &&
      item.after_state?.status === "prepared_internal_share" &&
      item.after_state?.delivery_status === "not_sent" &&
      typeof item.after_state.share_id === "string",
  );
  return typeof record?.after_state?.share_id === "string" ? record.after_state.share_id : null;
}

function nextFinalActionIdempotencyKey(action: string): string {
  const suffix = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `release-center-${action}-${suffix}`;
}

function isReviewedMetadataCandidate(candidate: ReviewedExternalCandidate): boolean {
  const payload = summaryRecord(candidate.candidate_payload);
  return candidate.candidate_type === "bsf_reviewed_metadata_candidate" || payload.candidate_family === "bsf_reviewed_metadata";
}

function ReviewedMetadataLaneCard({
  candidate,
  evidenceSummary,
}: {
  candidate: ReviewedExternalCandidate;
  evidenceSummary?: ReviewedCandidateEvidenceSummary;
}) {
  const payload = summaryRecord(candidate.candidate_payload);
  const title = typeof payload.title === "string" ? payload.title : candidate.candidate_id;
  const doi = typeof payload.doi === "string" ? payload.doi : candidate.source_ref;
  const articleType = typeof payload.article_type === "string" ? payload.article_type : candidate.candidate_type;
  const numericValuesIncluded = Boolean(payload.numeric_values_included);

  return (
    <div className="rounded-lg border border-sky-300/15 bg-black/10 px-3 py-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-medium text-sky-50">{title}</p>
          <p className="mt-1 text-xs text-sky-100/70">{candidate.candidate_id} / {doi}</p>
        </div>
        <Badge variant="success">{translateText(candidate.review_status)}</Badge>
      </div>
      <div className="mt-3 grid gap-1 text-xs text-sky-100/75">
        <span>{translateText("article_type")}: {translateText(articleType)}</span>
        <span>{translateText("license_status")}: {translateText(candidate.license_status)}</span>
        <span>{translateText("runtime_activated")}: {String(candidate.runtime_activated)}</span>
        <span>{translateText("numeric_values_included")}: {String(numericValuesIncluded)}</span>
      </div>
      <p className="mt-3 text-xs leading-5 text-sky-100/75">
        {translateText("Allowed")}: {translateText(candidate.allowed_use)}
      </p>
      <p className="mt-1 text-xs leading-5 text-amber-100/80">
        {translateText("Blocked")}: {translateText(candidate.blocked_use)}
      </p>
      {evidenceSummary ? (
        <div className="mt-3 rounded-lg border border-emerald-300/15 bg-emerald-500/8 px-3 py-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs font-medium text-emerald-50">{translateText("Operator evidence summary")}</p>
              <p className="mt-1 text-xs leading-5 text-emerald-100/75">
                {translateText("Read-only activation, runtime, and rollback evidence; no execution is enabled from Release Center.")}
              </p>
            </div>
            <Badge variant={evidenceSummary.operatorEvidenceStatus.includes("ready") ? "success" : "warning"}>
              {translateText(evidenceSummary.operatorEvidenceStatus)}
            </Badge>
          </div>
          <div className="mt-3 grid gap-1 text-xs text-emerald-100/80 sm:grid-cols-2">
            <span>{translateText("activation_execution")}: {translateText(evidenceSummary.activationExecution)}</span>
            <span>{translateText("runtime_read_path")}: {translateText(evidenceSummary.runtimeReadPath)}</span>
            <span>{translateText("rollback_execution")}: {translateText(evidenceSummary.rollbackExecution)}</span>
            <span>{translateText("rollback_target_available")}: {String(evidenceSummary.rollbackTargetAvailable)}</span>
            <span>{translateText("release_decision")}: {translateText(evidenceSummary.releaseDecision)}</span>
            <span>{translateText("release_evidence_allowed")}: {String(evidenceSummary.releaseEvidenceAllowed)}</span>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {evidenceSummary.guardrailSummary.slice(0, 5).map((guardrail) => (
              <span key={guardrail} className="rounded-full border border-emerald-300/15 bg-black/10 px-2.5 py-1 text-xs text-emerald-100">
                {translateText(formatReviewedCandidateGuardrail(guardrail))}
              </span>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function LiteraturePromotionAuditLaneCard({
  auditExport,
}: {
  auditExport: LiteratureValuePromotionAuditExportResponse;
}) {
  const request = summaryRecord(auditExport.request);
  const overlay = summaryRecord(auditExport.overlay);
  const activation = summaryRecord(auditExport.runtime_activation);
  const releaseLink = summaryRecord(auditExport.release_evidence_link);
  const rollback = summaryRecord(auditExport.rollback);
  const manifest = summaryRecord(auditExport.export_manifest);
  const dbProof = summaryRecord(auditExport.db_pollution_proof);
  const finalActionProof = summaryRecord(auditExport.final_action_non_execution_proof);
  const approvalIds = auditExport.approvals
    .map((approval) => displayAuditValue(approval.approval_id, "approval"))
    .slice(0, 2)
    .join(", ");
  const releaseDecisionReviewRequired =
    finalActionProof.release_decisions_all_review_required === true ||
    stringArray(auditExport.guardrails).includes("release_decision_remains_review_required");

  return (
    <div className="rounded-lg border border-fuchsia-300/15 bg-black/10 px-3 py-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-medium text-fuchsia-50">
            {displayAuditValue(overlay.normalized_value ?? request.raw_value, auditExport.candidate_id)}
          </p>
          <p className="mt-1 text-xs text-fuchsia-100/70">
            {translateText("source")}: {displayAuditValue(overlay.source_ref ?? request.conditions)}
          </p>
        </div>
        <Badge variant={releaseDecisionReviewRequired ? "warning" : "neutral"}>
          {translateText(releaseDecisionReviewRequired ? "review_required" : "review pending")}
        </Badge>
      </div>
      <div className="mt-3 grid gap-2 text-xs text-fuchsia-100/80 sm:grid-cols-2">
        <span>{translateText("candidate_id")}: {auditExport.candidate_id}</span>
        <span>{translateText("request")}: {displayAuditValue(request.request_status)}</span>
        <span>{translateText("approval")}: {displayAuditValue(approvalIds, `${auditExport.approvals.length} approvals`)}</span>
        <span>{translateText("activation scope")}: {displayAuditValue(activation.activation_scope)}</span>
        <span>{translateText("overlay_hash")}: {displayAuditValue(overlay.overlay_hash ?? manifest.content_hash).slice(0, 16)}</span>
        <span>{translateText("content_hash")}: {auditExport.content_hash.slice(0, 16)}</span>
        <span>{translateText("rollback")}: {displayAuditValue(rollback.rollback_status ?? releaseLink.rollback_status, "not rolled back")}</span>
        <span>{translateText("release evidence link")}: {displayAuditValue(releaseLink.link_status, "not linked")}</span>
        <span>{translateText("species_db_write")}: {String(dbProof.species_db_write === true)}</span>
        <span>{translateText("feedstock_db_write")}: {String(dbProof.feedstock_db_write === true)}</span>
        <span>{translateText("validated_default_write")}: {String(dbProof.validated_default_write === true)}</span>
        <span>{translateText("final_action_execution")}: {String(finalActionProof.final_action_execution === true)}</span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <span className="rounded-full border border-fuchsia-300/15 bg-black/10 px-2.5 py-1 text-xs text-fuchsia-100">
          {translateText(auditExport.export_policy)}
        </span>
        <span className="rounded-full border border-fuchsia-300/15 bg-black/10 px-2.5 py-1 text-xs text-fuchsia-100">
          {translateText("file_written")}: {String(manifest.file_written === true)}
        </span>
        <span className="rounded-full border border-fuchsia-300/15 bg-black/10 px-2.5 py-1 text-xs text-fuchsia-100">
          {translateText("side_effects")}: {Object.values(auditExport.side_effects).some(Boolean) ? "true" : "false"}
        </span>
      </div>
    </div>
  );
}

async function loadReviewedCandidateEvidenceSummary(
  candidateId: string,
): Promise<ReviewedCandidateEvidenceSummary> {
  try {
    const [activationPreview, runtimeReadiness, rollbackPreview]: [
      ReviewedExternalCandidateActivationPreviewResponse,
      ReviewedExternalCandidateRuntimeReadinessResponse,
      ReviewedExternalCandidateRollbackPreviewResponse,
    ] = await Promise.all([
      bosApi.getReviewedExternalCandidateActivationPreview(candidateId),
      bosApi.getReviewedExternalCandidateRuntimeReadiness(candidateId),
      bosApi.getReviewedExternalCandidateRollbackPreview(candidateId),
    ]);
    return buildReviewedCandidateEvidenceSummary({
      activationPreview,
      runtimeReadiness,
      rollbackPreview,
    });
  } catch {
    return buildReviewedCandidateEvidenceSummary({});
  }
}

export function buildReleaseProofCardsFromAssistantRun(run: AssistantRunResponse | null): ReleaseProofCard[] {
  const summary = summaryRecord(run?.result_summary);
  const resultIds = summaryRecord(summary.result_ids);
  const cards: ReleaseProofCard[] = [];
  const compliance = summaryRecord(summary.compliance_gate);
  const complianceStatus = typeof compliance.status === "string" ? compliance.status : null;
  if (complianceStatus) {
    const missingAssays = stringArray(compliance.missing_assays);
    const blockedReasons = stringArray(compliance.blocked_reasons);
    cards.push({
      kind: "compliance",
      title: "Compliance gate",
      status: complianceStatus,
      evidencePackId:
        typeof resultIds.compliance_evidence_pack_id === "string"
          ? resultIds.compliance_evidence_pack_id
          : typeof compliance.evidence_pack_id === "string"
            ? compliance.evidence_pack_id
            : null,
      resultId:
        typeof resultIds.compliance_gate_id === "string"
          ? resultIds.compliance_gate_id
          : typeof compliance.gate_id === "string"
            ? compliance.gate_id
            : null,
      lines: [
        missingAssays.length ? `Missing assays: ${missingAssays.join(", ")}` : "Required assays present",
        blockedReasons.length ? `Blocked reasons: ${blockedReasons.join(", ")}` : "No blocked reasons reported",
      ],
    });
  }

  const lca = summaryRecord(summary.lca_value_proof);
  const lcaResult = summaryRecord(lca.result);
  const lcaResultId =
    typeof resultIds.lca_result_id === "string"
      ? resultIds.lca_result_id
      : typeof lca.result_id === "string"
        ? lca.result_id
        : null;
  if (lcaResultId) {
    cards.push({
      kind: "lca",
      title: "LCA value proof",
      status: "review_required",
      evidencePackId:
        typeof resultIds.lca_evidence_pack_id === "string"
          ? resultIds.lca_evidence_pack_id
          : typeof lca.evidence_pack_id === "string"
            ? lca.evidence_pack_id
            : null,
      resultId: lcaResultId,
      lines: [
        typeof lcaResult.co2e_abatement_kg === "number"
          ? `CO2e abatement: ${formatNumber(lcaResult.co2e_abatement_kg, 2)} kg`
          : "CO2e abatement pending",
        typeof lcaResult.energy_kwh === "number" ? `Energy: ${formatNumber(lcaResult.energy_kwh, 2)} kWh` : "Energy basis pending",
      ],
    });
  }

  const tea = summaryRecord(summary.tea_value_proof);
  const teaResult = summaryRecord(tea.result);
  const teaResultId =
    typeof resultIds.tea_result_id === "string"
      ? resultIds.tea_result_id
      : typeof tea.result_id === "string"
        ? tea.result_id
        : null;
  if (teaResultId) {
    cards.push({
      kind: "tea",
      title: "TEA value proof",
      status: "review_required",
      evidencePackId:
        typeof resultIds.tea_evidence_pack_id === "string"
          ? resultIds.tea_evidence_pack_id
          : typeof tea.evidence_pack_id === "string"
            ? tea.evidence_pack_id
            : null,
      resultId: teaResultId,
      lines: [
        typeof teaResult.gross_margin_usd === "number"
          ? `Gross margin: $${formatNumber(teaResult.gross_margin_usd, 2)}`
          : "Gross margin pending",
        typeof teaResult.operating_cost_usd === "number"
          ? `Operating cost: $${formatNumber(teaResult.operating_cost_usd, 2)}`
          : "Operating cost pending",
      ],
    });
  }

  const warnings = stringArray(summary.uncertainty_warnings);
  if (warnings.length) {
    cards.push({
      kind: "uncertainty",
      title: "Uncertainty warnings",
      status: "human_review_required",
      evidencePackId: typeof resultIds.evidence_pack_id === "string" ? resultIds.evidence_pack_id : run?.evidence_pack_id ?? null,
      resultId: run?.run_id ?? null,
      lines: warnings,
    });
  }
  return cards;
}

export default function ReleaseCenterPage() {
  const navigate = useNavigate();
  const [simulationAppendix, setSimulationAppendix] = useState<SimulationReleaseAppendixResponse | null>(null);
  const [simulationAppendixChecked, setSimulationAppendixChecked] = useState(false);
  const [releaseDecisionId, setReleaseDecisionId] = useState(() => {
    if (typeof window === "undefined") return "1";
    return new URLSearchParams(window.location.search).get("releaseDecisionId") || "1";
  });
  const [attachedAppendices, setAttachedAppendices] = useState<ReleasePacketAttachment[]>([]);
  const [lastApprovalRequest, setLastApprovalRequest] = useState<HumanApprovalRequest | null>(null);
  const [isDownloadingAppendix, setIsDownloadingAppendix] = useState(false);
  const [isLoadingAppendices, setIsLoadingAppendices] = useState(false);
  const [isAttachingAppendix, setIsAttachingAppendix] = useState(false);
  const [isRequestingApproval, setIsRequestingApproval] = useState(false);
  const [benchmarkCases, setBenchmarkCases] = useState<BenchmarkCase[]>([]);
  const [models, setModels] = useState<ModelRegistryItem[]>([]);
  const [providerCapabilityMatrix, setProviderCapabilityMatrix] = useState<ModelProviderCapabilityMatrix | null>(null);
  const [externalKnowledgeCandidates, setExternalKnowledgeCandidates] = useState<ExternalKnowledgeCandidateMatrix | null>(null);
  const [latestExternalPromotionRequest, setLatestExternalPromotionRequest] = useState<ExternalKnowledgePromotionResponse | null>(null);
  const [validatedExternalRegistry, setValidatedExternalRegistry] = useState<ExternalKnowledgeValidatedRegistry | null>(null);
  const [latestExternalRegistryPatch, setLatestExternalRegistryPatch] = useState<ExternalKnowledgeRegistryPatchResponse | null>(null);
  const [runtimeActivationReadiness, setRuntimeActivationReadiness] = useState<ExternalKnowledgeRuntimeActivationReadiness | null>(null);
  const [runtimeActivationState, setRuntimeActivationState] = useState<ExternalKnowledgeRuntimeActivationState | null>(null);
  const [latestRuntimeActivationDraft, setLatestRuntimeActivationDraft] = useState<ExternalKnowledgeRuntimeActivationDraft | null>(null);
  const [latestRuntimeActivationReadiness, setLatestRuntimeActivationReadiness] = useState<ExternalKnowledgeRuntimeActivationExecutionReadiness | null>(null);
  const [latestRuntimeActivationRecord, setLatestRuntimeActivationRecord] = useState<ExternalKnowledgeRuntimeActivationRecord | null>(null);
  const [knowledgeRelations, setKnowledgeRelations] = useState<KnowledgeRelation[]>([]);
  const [latestBenchmarkRun, setLatestBenchmarkRun] = useState<BenchmarkRun | null>(null);
  const [latestModelCandidate, setLatestModelCandidate] = useState<ModelRegistrationResponse | null>(null);
  const [latestGovernanceReview, setLatestGovernanceReview] = useState<ModelGovernanceResponse | null>(null);
  const [latestAssistantRun, setLatestAssistantRun] = useState<AssistantRunResponse | null>(null);
  const [reviewWorkbench, setReviewWorkbench] = useState<AssistantReviewWorkbenchResponse | null>(null);
  const [resolvedReviewHistory, setResolvedReviewHistory] = useState<AssistantReviewWorkbenchResponse | null>(null);
  const [finalActionReadiness, setFinalActionReadiness] = useState<FinalActionReadinessResponse | null>(null);
  const [rcManifest, setRCManifest] = useState<BOSV9RCManifestResponse | null>(null);
  const [finalActionSourcePacket, setFinalActionSourcePacket] = useState<FinalActionReviewPacketSnapshotResponse | null>(null);
  const [finalActionAuditRecords, setFinalActionAuditRecords] = useState<FinalActionAuditRecordListResponse | null>(null);
  const [finalActionRequestDrafts, setFinalActionRequestDrafts] = useState<FinalActionRequestDraftListResponse | null>(null);
  const [reviewedMetadataLane, setReviewedMetadataLane] = useState<ReviewedExternalCandidateListResponse | null>(null);
  const [reviewedMetadataSummary, setReviewedMetadataSummary] = useState<ReviewedExternalCandidateLaneSummary | null>(null);
  const [reviewedMetadataEvidenceById, setReviewedMetadataEvidenceById] = useState<Record<string, ReviewedCandidateEvidenceSummary>>({});
  const [literaturePromotionAuditExports, setLiteraturePromotionAuditExports] = useState<LiteratureValuePromotionAuditExportResponse[]>([]);
  const [literaturePromotionCandidateCount, setLiteraturePromotionCandidateCount] = useState(0);
  const [literaturePromotionAuditRefreshNonce, setLiteraturePromotionAuditRefreshNonce] = useState(0);
  const [literatureReleaseEvidenceLinkNotes, setLiteratureReleaseEvidenceLinkNotes] = useState(
    "Link active scoped literature overlay as release evidence only; release decision remains review_required.",
  );
  const [literatureReleaseEvidenceLinkResult, setLiteratureReleaseEvidenceLinkResult] =
    useState<LiteratureValueReleaseEvidenceLinkResponse | null>(null);
  const [finalActionReadinessByDraft, setFinalActionReadinessByDraft] = useState<Record<string, string>>({});
  const [finalActionBusyKey, setFinalActionBusyKey] = useState<string | null>(null);
  const [finalActionAttestation, setFinalActionAttestation] = useState("I reviewed the immutable source packet and approve this audited final action.");
  const [externalShareRecipientScope, setExternalShareRecipientScope] = useState("allowlisted:regulator");
  const [externalShareRedactionPolicyId, setExternalShareRedactionPolicyId] = useState("redaction-policy-v1");
  const [externalShareDeliveryEndpoint, setExternalShareDeliveryEndpoint] = useState("");
  const [isLoadingAssistantProofs, setIsLoadingAssistantProofs] = useState(false);
  const [isLoadingReviewWorkbench, setIsLoadingReviewWorkbench] = useState(false);
  const [isLoadingFinalActionReadiness, setIsLoadingFinalActionReadiness] = useState(false);
  const [isLoadingRCManifest, setIsLoadingRCManifest] = useState(false);
  const [isLoadingReviewedMetadataLane, setIsLoadingReviewedMetadataLane] = useState(false);
  const [isLoadingLiteraturePromotionAudits, setIsLoadingLiteraturePromotionAudits] = useState(false);
  const [isLinkingLiteratureReleaseEvidence, setIsLinkingLiteratureReleaseEvidence] = useState(false);
  const [isExportingReviewAuditPacket, setIsExportingReviewAuditPacket] = useState(false);
  const [isPersistingReviewAuditPacketSnapshot, setIsPersistingReviewAuditPacketSnapshot] = useState(false);
  const [resolvingConfirmationId, setResolvingConfirmationId] = useState<string | null>(null);
  const [resolvingApprovalRequestId, setResolvingApprovalRequestId] = useState<string | null>(null);
  const [isLoadingGovernanceKernel, setIsLoadingGovernanceKernel] = useState(false);
  const [isRunningBenchmark, setIsRunningBenchmark] = useState(false);
  const [isRequestingModelReview, setIsRequestingModelReview] = useState(false);
  const [isRequestingExternalPromotion, setIsRequestingExternalPromotion] = useState(false);
  const [isResolvingExternalPromotion, setIsResolvingExternalPromotion] = useState(false);
  const [isApplyingExternalRegistryPatch, setIsApplyingExternalRegistryPatch] = useState(false);
  const [runtimeActivationBusyKey, setRuntimeActivationBusyKey] = useState<string | null>(null);
  const readiness = useCodeReleaseReadiness();
  const brainRuntime = useBrainRuntime();
  const recentRisks = useRecentTimeseriesRisks(5, 6);
  const releasePriority = brainRuntime.data
    ? deriveAutonomyPriority(brainRuntime.data.documents, "release")
    : null;
  const highestRisk = recentRisks.data?.items
    .slice()
    .sort((left, right) => right.release_warning_score - left.release_warning_score)[0] ?? null;

  useEffect(() => {
    let active = true;
    async function loadSimulationAppendix() {
      try {
        const scenarios = await simulationLabApi.listScenarios({ limit: 1 });
        const latest = scenarios[0];
        if (!latest) return;
        const appendix = await simulationLabApi.getReleaseAppendix(latest.simulation_id);
        if (active) setSimulationAppendix(appendix);
      } catch {
        if (active) setSimulationAppendix(null);
      } finally {
        if (active) setSimulationAppendixChecked(true);
      }
    }
    void loadSimulationAppendix();
    return () => {
      active = false;
    };
  }, []);

  const loadReviewWorkbench = useCallback(async () => {
    setIsLoadingReviewWorkbench(true);
    try {
      const [workbench, approvedHistory, rejectedHistory] = await Promise.all([
        assistantApi.getReviewWorkbench("pending", 50),
        assistantApi.getReviewWorkbench("approved", 25),
        assistantApi.getReviewWorkbench("rejected", 25),
      ]);
      setReviewWorkbench(workbench);
      setResolvedReviewHistory(mergeReviewWorkbenchHistory(approvedHistory, rejectedHistory));
    } catch {
      setReviewWorkbench(null);
      setResolvedReviewHistory(null);
    } finally {
      setIsLoadingReviewWorkbench(false);
    }
  }, []);

  useEffect(() => {
    void loadReviewWorkbench();
  }, [loadReviewWorkbench]);

  const loadFinalActionReadiness = useCallback(async () => {
    setIsLoadingFinalActionReadiness(true);
    try {
      const readinessResult = await finalActionsApi.getReadiness(50);
      setFinalActionReadiness(readinessResult);
      try {
        setFinalActionAuditRecords(await finalActionsApi.getAuditRecords(25));
      } catch {
        setFinalActionAuditRecords(null);
      }
      try {
        setFinalActionRequestDrafts(await finalActionsApi.getRequestDrafts(25));
      } catch {
        setFinalActionRequestDrafts(null);
      }
      if (readinessResult.source_review_packet_id) {
        try {
          setFinalActionSourcePacket(await finalActionsApi.getSourceReviewPacket(readinessResult.source_review_packet_id));
        } catch {
          setFinalActionSourcePacket(null);
        }
      } else {
        setFinalActionSourcePacket(null);
      }
    } catch {
      setFinalActionReadiness(null);
      setFinalActionSourcePacket(null);
      setFinalActionAuditRecords(null);
      setFinalActionRequestDrafts(null);
    } finally {
      setIsLoadingFinalActionReadiness(false);
    }
  }, []);

  useEffect(() => {
    void loadFinalActionReadiness();
  }, [loadFinalActionReadiness]);

  useEffect(() => {
    let active = true;
    async function loadRCManifest() {
      setIsLoadingRCManifest(true);
      try {
        const manifest = await governanceApi.getRCManifest();
        if (active) setRCManifest(manifest);
      } catch {
        if (active) setRCManifest(null);
      } finally {
        if (active) setIsLoadingRCManifest(false);
      }
    }
    void loadRCManifest();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    async function loadReviewedMetadataLane() {
      setIsLoadingReviewedMetadataLane(true);
      try {
        const [candidates, summary] = await Promise.all([
          bosApi.listReviewedExternalCandidates(),
          bosApi.getReviewedExternalCandidateSummary(),
        ]);
        const evidenceEntries = await Promise.all(
          candidates.items
            .filter(isReviewedMetadataCandidate)
            .slice(0, 4)
            .map(async (candidate) => [
              candidate.candidate_id,
              await loadReviewedCandidateEvidenceSummary(candidate.candidate_id),
            ] as const),
        );
        if (active) {
          setReviewedMetadataLane(candidates);
          setReviewedMetadataSummary(summary);
          setReviewedMetadataEvidenceById(Object.fromEntries(evidenceEntries));
        }
      } catch {
        if (active) {
          setReviewedMetadataLane(null);
          setReviewedMetadataSummary(null);
          setReviewedMetadataEvidenceById({});
        }
      } finally {
        if (active) setIsLoadingReviewedMetadataLane(false);
      }
    }
    void loadReviewedMetadataLane();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    async function loadLiteraturePromotionAudits() {
      setIsLoadingLiteraturePromotionAudits(true);
      try {
        const candidates = await bosApi.listLiteratureExtractionCandidates();
        const auditResults = await Promise.allSettled(
          candidates.items.slice(0, 6).map((candidate) =>
            bosApi.getLiteratureValuePromotionAuditExport(candidate.candidate_id),
          ),
        );
        if (active) {
          setLiteraturePromotionCandidateCount(candidates.count);
          setLiteraturePromotionAuditExports(
            auditResults.flatMap((result) => result.status === "fulfilled" ? [result.value] : []),
          );
        }
      } catch {
        if (active) {
          setLiteraturePromotionCandidateCount(0);
          setLiteraturePromotionAuditExports([]);
        }
      } finally {
        if (active) setIsLoadingLiteraturePromotionAudits(false);
      }
    }
    void loadLiteraturePromotionAudits();
    return () => {
      active = false;
    };
  }, [literaturePromotionAuditRefreshNonce]);

  useEffect(() => {
    let active = true;
    async function loadAssistantProofs() {
      setIsLoadingAssistantProofs(true);
      try {
        const runs = await assistantApi.listRuns(5);
        if (!active) return;
        setLatestAssistantRun(runs.find((run) => buildReleaseProofCardsFromAssistantRun(run).length > 0) ?? null);
      } catch {
        if (active) setLatestAssistantRun(null);
      } finally {
        if (active) setIsLoadingAssistantProofs(false);
      }
    }
    void loadAssistantProofs();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    async function loadReleaseAppendices() {
      const decisionId = Number(releaseDecisionId);
      if (!Number.isInteger(decisionId) || decisionId <= 0) {
        setAttachedAppendices([]);
        return;
      }
      setIsLoadingAppendices(true);
      try {
        const appendices = await releasePacketApi.listAppendices(decisionId);
        if (active) setAttachedAppendices(appendices);
      } catch {
        if (active) setAttachedAppendices([]);
      } finally {
        if (active) setIsLoadingAppendices(false);
      }
    }
    void loadReleaseAppendices();
    return () => {
      active = false;
    };
  }, [releaseDecisionId]);

  useEffect(() => {
    let active = true;
    async function loadGovernanceKernel() {
      setIsLoadingGovernanceKernel(true);
      try {
        const [cases, benchmarkRuns, modelItems, providerMatrix, externalCandidates, externalRegistry, runtimeState, relations] = await Promise.all([
          bosKernelsApi.listBenchmarkCases(),
          bosKernelsApi.listBenchmarkRuns(),
          bosKernelsApi.listModels(),
          bosKernelsApi.listModelProviderCapabilities(),
          bosKernelsApi.listExternalKnowledgeCandidates(),
          bosKernelsApi.listExternalKnowledgeValidatedRegistry(),
          bosKernelsApi.listExternalKnowledgeRuntimeActivationState(),
          bosKernelsApi.listKnowledgeRelations(),
        ]);
        if (!active) return;
        setBenchmarkCases(cases);
        setLatestBenchmarkRun(benchmarkRuns[0] ?? null);
        setModels(modelItems);
        setProviderCapabilityMatrix(providerMatrix);
        setExternalKnowledgeCandidates(externalCandidates);
        setValidatedExternalRegistry(externalRegistry);
        setRuntimeActivationState(runtimeState);
        setKnowledgeRelations(relations);
      } catch {
        if (!active) return;
        setBenchmarkCases([]);
        setLatestBenchmarkRun(null);
        setModels([]);
        setProviderCapabilityMatrix(null);
        setExternalKnowledgeCandidates(null);
        setValidatedExternalRegistry(null);
        setRuntimeActivationState(null);
        setKnowledgeRelations([]);
      } finally {
        if (active) setIsLoadingGovernanceKernel(false);
      }
    }
    void loadGovernanceKernel();
    return () => {
      active = false;
    };
  }, []);

  const numericReleaseDecisionId = Number(releaseDecisionId);
  const canUseReleasePacket =
    simulationAppendix &&
    Number.isInteger(numericReleaseDecisionId) &&
    numericReleaseDecisionId > 0;
  const evidenceStatus = simulationAppendix?.selected_run && simulationAppendix.evidence_pack_id && simulationAppendix.input_snapshot_id
    ? "Evidence sufficient for review"
    : "Missing evidence";
  const benchmarkCaseCount = typeof latestBenchmarkRun?.scorecard.case_count === "number"
    ? latestBenchmarkRun.scorecard.case_count
    : null;
  const benchmarkPassedCount = typeof latestBenchmarkRun?.scorecard.passed_count === "number"
    ? latestBenchmarkRun.scorecard.passed_count
    : null;
  const benchmarkFailedCount = typeof latestBenchmarkRun?.scorecard.failed_count === "number"
    ? latestBenchmarkRun.scorecard.failed_count
    : null;
  const latestBenchmarkCases = latestBenchmarkRun?.scorecard.cases?.slice(0, 4) ?? [];
  const providerCapabilityPreview = providerCapabilityMatrix?.providers.slice(0, 6) ?? [];
  const externalKnowledgePreview = externalKnowledgeCandidates?.candidates.slice(0, 4) ?? [];
  const reviewedMetadataCandidates = reviewedMetadataLane?.items.filter(isReviewedMetadataCandidate) ?? [];
  const literaturePromotionAuditPreview = literaturePromotionAuditExports.slice(0, 3);
  const literaturePromotionAuditSideEffects = literaturePromotionAuditExports.some((auditExport) =>
    Object.values(auditExport.side_effects).some(Boolean),
  );
  const literatureEvidenceLinkTarget = literaturePromotionAuditExports.find((auditExport) => {
    const activation = summaryRecord(auditExport.runtime_activation);
    const releaseLink = summaryRecord(auditExport.release_evidence_link);
    return (
      typeof activation.activation_id === "string" &&
      activation.activation_status === "active" &&
      releaseLink.link_status !== "active"
    );
  }) ?? null;
  const literatureEvidenceLinkActivation = summaryRecord(literatureEvidenceLinkTarget?.runtime_activation);
  const literatureEvidenceLinkActivationId =
    typeof literatureEvidenceLinkActivation.activation_id === "string" ? literatureEvidenceLinkActivation.activation_id : null;
  const canLinkLiteratureReleaseEvidence =
    Boolean(literatureEvidenceLinkTarget && literatureEvidenceLinkActivationId) &&
    Number.isInteger(numericReleaseDecisionId) &&
    numericReleaseDecisionId > 0;
  const firstExternalPromotionCandidate = externalKnowledgeCandidates?.candidates.find(
    (candidate) => candidate.review_status === "pending_review",
  );
  const activationTargetPatch = latestExternalRegistryPatch ?? validatedExternalRegistry?.registry[0] ?? null;
  const latestActiveRuntimeScope = runtimeActivationState?.active_scopes[0] ?? null;
  const latestActiveActivationId =
    typeof latestActiveRuntimeScope?.active_activation_id === "string"
      ? latestActiveRuntimeScope.active_activation_id
      : latestRuntimeActivationRecord?.predicate === "runtime_activation_executed"
        ? latestRuntimeActivationRecord.activation_id
        : null;
  const benchmarkReviewState = (benchmarkFailedCount ?? 0) > 0
    ? "Blocked / review required"
    : latestBenchmarkRun
      ? "Ready for review"
      : "Evidence pending";
  const latestLoadedModel = models[models.length - 1] ?? null;
  const latestGovernanceRelation = knowledgeRelations
    .filter((relation) => relation.subject_type === "model_version")
    .slice()
    .reverse()
    .find((relation) => relation.predicate === "evaluated_by" || relation.predicate === "rejected_by") ?? null;
  const displayedKnowledgeRelations = knowledgeRelations.slice().reverse().slice(0, 3);
  const displayedModelId = latestModelCandidate?.model_id ?? latestLoadedModel?.model_id;
  const displayedModelStatus = latestModelCandidate?.status ?? latestLoadedModel?.status ?? "No promotion pending";
  const displayedGovernanceStatus =
    latestGovernanceReview?.version_status ??
    (latestGovernanceRelation
      ? latestGovernanceRelation.predicate === "evaluated_by"
        ? "ready_for_review"
        : "rejected"
      : "Human review required");
  const displayedKnowledgeRelationId = latestGovernanceReview?.knowledge_relation_id ?? latestGovernanceRelation?.relation_id;
  const assistantProofCards = buildReleaseProofCardsFromAssistantRun(latestAssistantRun);
  const assistantConfirmations = reviewWorkbench?.assistant_confirmations ?? [];
  const humanApprovalRequests = reviewWorkbench?.human_approval_requests ?? [];
  const reviewQueueCount = assistantConfirmations.length + humanApprovalRequests.length;
  const resolvedAssistantConfirmations = resolvedReviewHistory?.assistant_confirmations ?? [];
  const resolvedHumanApprovalRequests = resolvedReviewHistory?.human_approval_requests ?? [];
  const resolvedReviewCount = resolvedAssistantConfirmations.length + resolvedHumanApprovalRequests.length;
  const resolvedReviewItems = [...resolvedAssistantConfirmations, ...resolvedHumanApprovalRequests];
  const approvedReviewCount = resolvedReviewItems.filter((item) => item.status === "approved").length;
  const rejectedReviewCount = resolvedReviewItems.filter((item) => item.status === "rejected").length;
  const latestResolvedAt =
    resolvedReviewItems
      .map((item) => item.resolved_at)
      .filter((value): value is string => typeof value === "string" && value.length > 0)
      .sort()
      .at(-1) ?? null;

  const downloadSimulationAppendix = async () => {
    if (!simulationAppendix) return;
    setIsDownloadingAppendix(true);
    try {
      const blob = await simulationLabApi.exportReleaseAppendix(simulationAppendix.simulation_id, "md");
      downloadBlob(blob, `${simulationAppendix.simulation_id}-release-appendix.md`);
    } finally {
      setIsDownloadingAppendix(false);
    }
  };

  const downloadReviewWorkbenchAuditPacket = async (format: "md" | "json") => {
    setIsExportingReviewAuditPacket(true);
    try {
      const blob = await assistantApi.exportReviewWorkbenchAuditPacket(format, 50);
      downloadBlob(blob, `assistant-review-workbench-audit-packet.${format}`);
      toast.success("Review workbench audit packet exported");
    } catch {
      toast.error("Failed to export review workbench audit packet");
    } finally {
      setIsExportingReviewAuditPacket(false);
    }
  };

  const persistReviewWorkbenchAuditPacketSnapshot = async () => {
    setIsPersistingReviewAuditPacketSnapshot(true);
    try {
      const snapshot = await assistantApi.persistReviewWorkbenchAuditPacketSnapshot(50);
      setFinalActionSourcePacket(snapshot);
      toast.success("Source review packet snapshot persisted");
      await loadFinalActionReadiness();
    } catch {
      toast.error("Failed to persist source review packet snapshot");
    } finally {
      setIsPersistingReviewAuditPacketSnapshot(false);
    }
  };

  const attachSimulationAppendix = async () => {
    if (!canUseReleasePacket) return;
    setIsAttachingAppendix(true);
    try {
      const attachment = await releasePacketApi.attachSimulationAppendix(numericReleaseDecisionId, {
        simulation_id: simulationAppendix.simulation_id,
        run_id: simulationAppendix.selected_run?.run_id ?? null,
      });
      setAttachedAppendices((current) => [attachment, ...current]);
      toast.success("Simulation appendix attached for review");
    } catch {
      toast.error("Failed to attach simulation appendix");
    } finally {
      setIsAttachingAppendix(false);
    }
  };

  const requestHumanApproval = async () => {
    if (!canUseReleasePacket) return;
    setIsRequestingApproval(true);
    try {
      const approval = await releasePacketApi.createApprovalRequest(numericReleaseDecisionId, {
        subject_type: "release_decision",
        subject_id: String(numericReleaseDecisionId),
        reason: "Review simulation appendix evidence before release decision",
        payload: {
          simulation_id: simulationAppendix.simulation_id,
          evidence_pack_id: simulationAppendix.evidence_pack_id,
          input_snapshot_id: simulationAppendix.input_snapshot_id,
        },
      });
      setLastApprovalRequest(approval);
      toast.success("Human approval requested");
    } catch {
      toast.error("Failed to request human approval");
    } finally {
      setIsRequestingApproval(false);
    }
  };

  const linkLiteratureReleaseEvidence = async () => {
    if (!canLinkLiteratureReleaseEvidence || !literatureEvidenceLinkActivationId || !literatureEvidenceLinkTarget) return;
    setIsLinkingLiteratureReleaseEvidence(true);
    try {
      const link = await bosApi.createLiteratureValueReleaseEvidenceLink(numericReleaseDecisionId, {
        activation_id: literatureEvidenceLinkActivationId,
        link_notes: literatureReleaseEvidenceLinkNotes,
        idempotency_key: nextFinalActionIdempotencyKey("literature-release-evidence-link"),
      });
      setLiteratureReleaseEvidenceLinkResult(link);
      setLiteraturePromotionAuditRefreshNonce((value) => value + 1);
      toast.success("Literature value linked as review evidence");
    } catch {
      toast.error("Failed to link literature value as release evidence");
    } finally {
      setIsLinkingLiteratureReleaseEvidence(false);
    }
  };

  const createFinalActionDraft = async (action: FinalActionReadinessResponse["actions"][number]) => {
    if (!finalActionReadiness?.source_review_packet_id) {
      toast.error("Source review packet is required before drafting a final action");
      return;
    }
    const targetId =
      action.action === "model_activation"
        ? finalActionReadiness.current_state.latest_model_version_id
        : finalActionReadiness.current_state.latest_release_decision_id?.toString();
    if (!targetId) {
      toast.error("Final action target is missing");
      return;
    }
    const targetType = action.action === "model_activation" ? "model_version" : "release_decision";
    const busyKey = `draft:${action.action}`;
    setFinalActionBusyKey(busyKey);
    try {
      await finalActionsApi.createRequestDraft({
        action_type: action.action,
        target_type: targetType,
        target_id: targetId,
        source_review_packet_id: finalActionReadiness.source_review_packet_id,
        idempotency_key: nextFinalActionIdempotencyKey(`${action.action}-draft`),
      });
      toast.success("Final action request draft created");
      await loadFinalActionReadiness();
    } catch {
      toast.error("Failed to create final action request draft");
    } finally {
      setFinalActionBusyKey(null);
    }
  };

  const resolveFinalActionDraft = async (draft: FinalActionRequestDraftItem, approved: boolean) => {
    const busyKey = `resolve:${draft.final_action_request_id}:${String(approved)}`;
    setFinalActionBusyKey(busyKey);
    try {
      await finalActionsApi.resolveRequestDraft(draft.final_action_request_id, {
        approved,
        reason: approved
          ? "Release Center approved this request draft for the separate audited final-action workflow."
          : "Release Center rejected this request draft before final-action execution.",
      });
      toast.success(approved ? "Request draft approved for final workflow" : "Request draft rejected");
      await loadFinalActionReadiness();
    } catch {
      toast.error("Failed to resolve final action request draft");
    } finally {
      setFinalActionBusyKey(null);
    }
  };

  const checkFinalActionDraftReadiness = async (draft: FinalActionRequestDraftItem) => {
    const busyKey = `readiness:${draft.final_action_request_id}`;
    setFinalActionBusyKey(busyKey);
    try {
      const readinessResult = await finalActionsApi.getRequestDraftExecutionReadiness(draft.final_action_request_id);
      setFinalActionReadinessByDraft((current) => ({
        ...current,
        [draft.final_action_request_id]: readinessResult.blockers.length
          ? readinessResult.blockers.join(" / ")
          : `ready: ${String(readinessResult.executable_now)} / audit: ${String(readinessResult.would_write_audit_record_now)}`,
      }));
      toast.success("Final action execution readiness checked");
    } catch {
      toast.error("Failed to check final action execution readiness");
    } finally {
      setFinalActionBusyKey(null);
    }
  };

  const executeFinalActionDraft = async (draft: FinalActionRequestDraftItem) => {
    const busyKey = `execute:${draft.final_action_request_id}`;
    setFinalActionBusyKey(busyKey);
    try {
      if (draft.action_type === "final_release_approval") {
        await finalActionsApi.executeFinalReleaseApproval({
          final_action_request_id: draft.final_action_request_id,
          expected_current_decision: String(finalActionReadiness?.current_state.latest_release_decision ?? "review_required"),
          operator_attestation: finalActionAttestation,
          idempotency_key: nextFinalActionIdempotencyKey("final-release-execution"),
        });
      } else if (draft.action_type === "model_activation") {
        await finalActionsApi.executeFinalModelActivation({
          final_action_request_id: draft.final_action_request_id,
          expected_current_version_status: String(finalActionReadiness?.current_state.latest_model_version_status ?? "ready_for_review"),
          operator_attestation: finalActionAttestation,
          idempotency_key: nextFinalActionIdempotencyKey("model-activation-execution"),
        });
      } else if (draft.action_type === "external_release_share") {
        const releasePacketAttachmentId = attachedAppendices[0]?.attachment_id;
        if (!releasePacketAttachmentId) {
          toast.error("Attach a release packet appendix before preparing external share approval");
          return;
        }
        await finalActionsApi.executeFinalExternalReleaseShare({
          final_action_request_id: draft.final_action_request_id,
          release_packet_attachment_id: releasePacketAttachmentId,
          recipient_scope: externalShareRecipientScope,
          redaction_policy_id: externalShareRedactionPolicyId,
          operator_attestation: finalActionAttestation,
          idempotency_key: nextFinalActionIdempotencyKey("external-share-execution"),
        });
      }
      toast.success("Audited final action executed");
      await loadFinalActionReadiness();
    } catch {
      toast.error("Failed to execute audited final action");
    } finally {
      setFinalActionBusyKey(null);
    }
  };

  const executeExternalShareDelivery = async () => {
    const shareId = latestPreparedExternalShareId(finalActionAuditRecords?.records ?? []);
    if (!shareId) {
      toast.error("Prepare an external share record before delivery");
      return;
    }
    if (!externalShareDeliveryEndpoint.trim()) {
      toast.error("External share delivery endpoint is required");
      return;
    }
    const busyKey = `deliver:${shareId}`;
    setFinalActionBusyKey(busyKey);
    try {
      await finalActionsApi.executeFinalExternalReleaseDelivery({
        share_id: shareId,
        expected_delivery_status: "not_sent",
        delivery_channel: "webhook",
        delivery_endpoint: externalShareDeliveryEndpoint.trim(),
        external_network_send: true,
        operator_attestation: finalActionAttestation,
        idempotency_key: nextFinalActionIdempotencyKey("external-share-delivery"),
      });
      toast.success("External share delivered through audited gate");
      await loadFinalActionReadiness();
    } catch {
      toast.error("Failed to deliver external share");
    } finally {
      setFinalActionBusyKey(null);
    }
  };

  const runBenchmarkSuite = async () => {
    setIsRunningBenchmark(true);
    try {
      const benchmark = await bosKernelsApi.createBenchmarkRun();
      const benchmarkRuns = await bosKernelsApi.listBenchmarkRuns();
      setLatestBenchmarkRun(benchmarkRuns[0] ?? benchmark);
      toast.success("Benchmark evidence created for review");
    } catch {
      toast.error("Failed to create benchmark evidence");
    } finally {
      setIsRunningBenchmark(false);
    }
  };

  const requestModelReview = async () => {
    if (!latestBenchmarkRun) return;
    setIsRequestingModelReview(true);
    try {
      const candidate = await bosKernelsApi.registerModelCandidate(latestBenchmarkRun.benchmark_run_id);
      const review = await bosKernelsApi.requestModelGovernanceReview(
        candidate.model_id,
        candidate.model_version_id,
        latestBenchmarkRun.benchmark_run_id,
      );
      const [modelItems, relations] = await Promise.all([
        bosKernelsApi.listModels(),
        bosKernelsApi.listKnowledgeRelations(),
      ]);
      setLatestModelCandidate(candidate);
      setLatestGovernanceReview(review);
      setModels(modelItems);
      setKnowledgeRelations(relations);
      toast.success("Model governance review requested");
    } catch {
      toast.error("Failed to request model governance review");
    } finally {
      setIsRequestingModelReview(false);
    }
  };

  const requestExternalPromotionReview = async () => {
    if (!firstExternalPromotionCandidate) return;
    setIsRequestingExternalPromotion(true);
    try {
      const promotion = await bosKernelsApi.requestExternalKnowledgePromotion(
        firstExternalPromotionCandidate.candidate_type,
        firstExternalPromotionCandidate.key,
      );
      setLatestExternalPromotionRequest(promotion);
      toast.success("External knowledge promotion review requested");
    } catch {
      toast.error("Failed to request external knowledge promotion review");
    } finally {
      setIsRequestingExternalPromotion(false);
    }
  };

  const approveExternalPromotionReview = async () => {
    if (!latestExternalPromotionRequest) return;
    setIsResolvingExternalPromotion(true);
    try {
      const promotion = await bosKernelsApi.resolveExternalKnowledgePromotion(
        latestExternalPromotionRequest.approval_request_id,
        true,
      );
      setLatestExternalPromotionRequest(promotion);
      toast.success("External knowledge promotion review approved");
    } catch {
      toast.error("Failed to approve external knowledge promotion review");
    } finally {
      setIsResolvingExternalPromotion(false);
    }
  };

  const applyExternalRegistryPatch = async () => {
    if (!latestExternalPromotionRequest || latestExternalPromotionRequest.status !== "approved") return;
    setIsApplyingExternalRegistryPatch(true);
    try {
      const patch = await bosKernelsApi.applyExternalKnowledgeRegistryPatch(
        latestExternalPromotionRequest.approval_request_id,
      );
      const registry = await bosKernelsApi.listExternalKnowledgeValidatedRegistry();
      setLatestExternalRegistryPatch(patch);
      setValidatedExternalRegistry(registry);
      await refreshRuntimeActivationState(patch.registry_patch_id);
      toast.success("Manual registry patch applied without runtime default mutation");
    } catch {
      toast.error("Failed to apply manual registry patch");
    } finally {
      setIsApplyingExternalRegistryPatch(false);
    }
  };

  const refreshRuntimeActivationState = async (registryPatchId?: string | null) => {
    const [state, activationReadiness] = await Promise.all([
      bosKernelsApi.listExternalKnowledgeRuntimeActivationState(),
      registryPatchId
        ? bosKernelsApi.getExternalKnowledgeRuntimeActivationReadiness(registryPatchId)
        : Promise.resolve(null),
    ]);
    setRuntimeActivationState(state);
    setRuntimeActivationReadiness(activationReadiness);
  };

  const createRuntimeActivationDraft = async () => {
    if (!activationTargetPatch) return;
    setRuntimeActivationBusyKey("draft");
    try {
      const draft = await bosKernelsApi.createExternalKnowledgeRuntimeActivationDraft(activationTargetPatch.registry_patch_id);
      setLatestRuntimeActivationDraft(draft);
      setLatestRuntimeActivationReadiness(null);
      await refreshRuntimeActivationState(activationTargetPatch.registry_patch_id);
      toast.success("Runtime activation draft created for review");
    } catch {
      toast.error("Failed to create runtime activation draft");
    } finally {
      setRuntimeActivationBusyKey(null);
    }
  };

  const approveRuntimeActivationDraft = async () => {
    if (!latestRuntimeActivationDraft) return;
    setRuntimeActivationBusyKey("approve");
    try {
      const draft = await bosKernelsApi.resolveExternalKnowledgeRuntimeActivationDraft(
        latestRuntimeActivationDraft.activation_request_id,
        true,
      );
      setLatestRuntimeActivationDraft(draft);
      await refreshRuntimeActivationState(draft.registry_patch_id);
      toast.success("Runtime activation draft approved");
    } catch {
      toast.error("Failed to approve runtime activation draft");
    } finally {
      setRuntimeActivationBusyKey(null);
    }
  };

  const checkRuntimeActivationReadiness = async () => {
    if (!latestRuntimeActivationDraft) return;
    setRuntimeActivationBusyKey("readiness");
    try {
      const readinessResult = await bosKernelsApi.getExternalKnowledgeRuntimeActivationExecutionReadiness(
        latestRuntimeActivationDraft.activation_request_id,
      );
      setLatestRuntimeActivationReadiness(readinessResult);
      toast.success("Runtime activation execution readiness checked");
    } catch {
      toast.error("Failed to check runtime activation readiness");
    } finally {
      setRuntimeActivationBusyKey(null);
    }
  };

  const executeRuntimeActivation = async () => {
    if (!latestRuntimeActivationDraft) return;
    setRuntimeActivationBusyKey("execute");
    try {
      const activation = await bosKernelsApi.executeExternalKnowledgeRuntimeActivation(
        latestRuntimeActivationDraft.activation_request_id,
        latestRuntimeActivationDraft.previous_active_registry_patch_id,
      );
      setLatestRuntimeActivationRecord(activation);
      await refreshRuntimeActivationState(latestRuntimeActivationDraft.registry_patch_id);
      toast.success("Scoped runtime activation recorded");
    } catch {
      toast.error("Failed to execute scoped runtime activation");
    } finally {
      setRuntimeActivationBusyKey(null);
    }
  };

  const rollbackRuntimeActivation = async () => {
    if (!latestActiveActivationId) return;
    setRuntimeActivationBusyKey("rollback");
    try {
      const rollback = await bosKernelsApi.rollbackExternalKnowledgeRuntimeActivation(latestActiveActivationId);
      setLatestRuntimeActivationRecord(rollback);
      await refreshRuntimeActivationState(activationTargetPatch?.registry_patch_id);
      toast.success("Runtime activation rolled back");
    } catch {
      toast.error("Failed to rollback runtime activation");
    } finally {
      setRuntimeActivationBusyKey(null);
    }
  };

  const resolveAssistantConfirmation = async (
    sourceAssistantRunId: string,
    confirmationId: string,
    approved: boolean,
  ) => {
    setResolvingConfirmationId(confirmationId);
    try {
      await assistantApi.confirm(sourceAssistantRunId, {
        confirmation_id: confirmationId,
        approved,
        reason: approved
          ? "Release Center workbench marked this queue item reviewed; no final release/model/share action executed."
          : "Release Center workbench rejected this queue item; no final release/model/share action executed.",
      });
      await Promise.all([loadReviewWorkbench(), loadFinalActionReadiness()]);
      toast.success(approved ? "Assistant confirmation marked reviewed" : "Assistant confirmation rejected");
    } catch {
      toast.error("Failed to update Assistant confirmation");
    } finally {
      setResolvingConfirmationId(null);
    }
  };

  const resolveHumanApprovalRequest = async (approvalRequestId: string, approved: boolean) => {
    setResolvingApprovalRequestId(approvalRequestId);
    try {
      await assistantApi.resolveHumanApprovalRequest(approvalRequestId, {
        approved,
        reason: approved
          ? "Release Center workbench resolved this review request only; release/model/share state remains unchanged."
          : "Release Center workbench rejected this review request only; release/model/share state remains unchanged.",
      });
      await Promise.all([loadReviewWorkbench(), loadFinalActionReadiness()]);
      toast.success(approved ? "Human review request resolved" : "Human review request rejected");
    } catch {
      toast.error("Failed to resolve human review request");
    } finally {
      setResolvingApprovalRequestId(null);
    }
  };

  if (readiness.isLoading) {
    return <SpinnerOverlay label={translateText("Loading BOS Code release center")} />;
  }

  if (readiness.isError || !readiness.data) {
    return (
      <ErrorState
        title={translateText("Release center unavailable")}
        description={translateText("Generate the BOS Code release dossier to unlock trust and verification reporting.")}
        onRetry={() => readiness.refetch()}
      />
    );
  }

  const preparedExternalShareId = latestPreparedExternalShareId(finalActionAuditRecords?.records ?? []);
  const releaseArtifactByKey = new Map(readiness.data.artifacts.map((artifact) => [artifact.key, artifact]));
  const rcReviewArtifacts: Array<{
    key: (typeof RC_MANIFEST_REVIEW_ARTIFACT_KEYS)[number];
    relativePath: string;
    downloadUrl: string | null;
    label: string;
  }> = rcManifest
    ? RC_MANIFEST_REVIEW_ARTIFACT_KEYS.flatMap((key) => {
        const relativePath = rcManifest.artifacts[key];
        if (!relativePath) return [];
        const releaseArtifact = releaseArtifactByKey.get(key);
        return [{
          key,
          relativePath,
          downloadUrl: releaseArtifact?.download_url ?? null,
          label: releaseArtifact?.label ?? releaseArtifactLabel(key),
        }];
      })
    : [];

  return (
    <div className="assistant-ambient-shell space-y-6">
      <div className="assistant-ambient-backdrop" aria-hidden="true">
        <span className="assistant-ambient-orb assistant-ambient-orb-cyan" />
        <span className="assistant-ambient-orb assistant-ambient-orb-violet" />
        <span className="assistant-ambient-orb assistant-ambient-orb-white" />
        <span className="assistant-ambient-grid" />
        <span className="assistant-ambient-scan assistant-ambient-scan-a" />
        <span className="assistant-ambient-scan assistant-ambient-scan-b" />
      </div>

      <CockpitPanel tone="hero" className="p-6 lg:p-7">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <CockpitSectionLabel>{translateText("Operations / Trust / Release")}</CockpitSectionLabel>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.65rem]">
                {translateText("BOS Code release center")}
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-surface-300">
                {translateText("Buyer-facing trust surface for preflight, smoke verification, artifacts, and release dossier review.")}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant={readiness.data.release_state === "ready_for_review" ? "success" : "warning"}>
                {translateText(readiness.data.release_state)}
              </Badge>
              <Badge variant="brand">{translateText("Verification-first")}</Badge>
              {releasePriority ? (
                <Button
                  variant="outline"
                  onClick={() => navigate(releasePriority.to)}
                >
                  {translateText(releasePriority.label)}
                </Button>
              ) : null}
            </div>
          </div>
        </div>
      </CockpitPanel>

      <ReleaseReadinessCard readiness={readiness.data} />
      <CockpitPanel className="p-5 lg:p-6" data-testid="rc-manifest-state-panel">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <CockpitSectionLabel>{translateText("RC candidate evidence")}</CockpitSectionLabel>
            <p className="mt-3 text-sm leading-7 text-surface-300">
              {translateText("Read-only BOS v9 RC manifest view; candidate evidence readiness is separate from the release decision.")}
            </p>
          </div>
          <Badge variant={rcManifest?.candidate_evidence_state === "ready_for_review" ? "success" : "warning"}>
            {translateText(
              rcManifest
                ? `candidate_evidence_state: ${rcManifest.candidate_evidence_state}`
                : isLoadingRCManifest
                  ? "candidate_evidence_state: loading"
                  : "candidate_evidence_state: unavailable",
            )}
          </Badge>
        </div>
        {rcManifest ? (
          <>
            <div className="mt-5 grid gap-3 md:grid-cols-3">
              <div className="rounded-lg border border-white/8 bg-black/10 px-3 py-3">
                <p className="text-xs text-surface-400">{translateText("Release decision")}</p>
                <p className="mt-2 text-sm font-medium text-amber-100">
                  {translateText(`release_state: ${rcManifest.release_state}`)}
                </p>
              </div>
              <div className="rounded-lg border border-white/8 bg-black/10 px-3 py-3">
                <p className="text-xs text-surface-400">{translateText("Evidence candidate")}</p>
                <p className="mt-2 text-sm font-medium text-emerald-100">
                  {translateText(`candidate_evidence_state: ${rcManifest.candidate_evidence_state}`)}
                </p>
              </div>
              <div className="rounded-lg border border-white/8 bg-black/10 px-3 py-3">
                <p className="text-xs text-surface-400">{translateText("Six target progress")}</p>
                <p className="mt-2 text-sm font-medium text-white">{rcManifest.bos_v9_target_progress_percent}%</p>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {[
                `preflight: ${rcManifest.preflight_pass_count} pass / ${rcManifest.preflight_warn_count} warn / ${rcManifest.preflight_fail_count} fail`,
                `release_reference_smoke_passed: ${String(rcManifest.release_reference_smoke_passed)}`,
                `final_action_execute_call_count: ${rcManifest.safety_boundary.final_action_execute_call_count}`,
                `validated_default_write_enabled: ${String(rcManifest.safety_boundary.validated_default_write_enabled)}`,
                `runtime_activation_enabled: ${String(rcManifest.safety_boundary.runtime_activation_enabled)}`,
                `hardware_execution_enabled: ${String(rcManifest.safety_boundary.hardware_execution_enabled)}`,
                `final_action_execution_enabled: ${String(rcManifest.safety_boundary.final_action_execution_enabled)}`,
              ].map((item) => (
                <span key={item} className="rounded-full border border-white/8 bg-black/10 px-2.5 py-1 text-xs text-surface-300">
                  {translateText(item)}
                </span>
              ))}
            </div>
            <div className="mt-5 grid gap-4 xl:grid-cols-[1fr_1fr]">
              <div className="rounded-lg border border-white/8 bg-black/10 px-3 py-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-medium text-white">{translateText("Six 9/10 target scorecard")}</p>
                  <Badge variant="info">{rcManifest.bos_v9_target_progress_percent}%</Badge>
                </div>
                <div className="mt-3 space-y-2">
                  {rcManifest.bos_v9_target_scorecard.map((item) => (
                    <div key={item.dimension} className="rounded-md border border-white/8 bg-white/5 px-3 py-2">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-xs font-medium text-surface-100">{translateText(item.dimension)}</p>
                        <span className="text-xs text-surface-300">{item.score}/{item.target}</span>
                      </div>
                      <p className="mt-1 text-xs leading-5 text-surface-400">{translateText(item.evidence)}</p>
                    </div>
                  ))}
                </div>
              </div>
              <div className="rounded-lg border border-white/8 bg-black/10 px-3 py-3">
                <p className="text-sm font-medium text-white">{translateText("Review packet entry")}</p>
                <p className="mt-2 text-xs leading-5 text-surface-400">
                  {translateText("Use these read-only artifacts as the candidate evidence packet for human review. They do not approve the release or execute final actions.")}
                </p>
                <div className="mt-3 space-y-2">
                  {rcReviewArtifacts.map((artifact) => (
                    <div key={artifact.key} className="rounded-md border border-white/8 bg-white/5 px-3 py-2">
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <p className="text-xs font-medium text-surface-100">{translateText(artifact.label)}</p>
                          <p className="mt-1 break-all text-xs text-surface-500">{artifact.relativePath}</p>
                        </div>
                        {artifact.downloadUrl ? (
                          <a
                            className="inline-flex h-7 items-center justify-center rounded-md border border-white/10 bg-white/5 px-2 text-xs font-medium text-surface-200 transition-colors hover:bg-white/8 hover:text-white"
                            href={artifact.downloadUrl}
                          >
                            {translateText("Open")}
                          </a>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
                {finalActionReadiness?.source_review_packet_id ? (
                  <div className="mt-3 rounded-md border border-cyan-300/15 bg-cyan-500/10 px-3 py-3 text-xs leading-5 text-cyan-100">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="font-medium text-cyan-50">{translateText("Immutable source review packet")}</p>
                        <p className="mt-1 break-all">
                          {translateText("source_review_packet_id")}: {finalActionReadiness.source_review_packet_id}
                        </p>
                        {finalActionSourcePacket ? (
                          <div className="mt-2 grid gap-1 sm:grid-cols-2">
                            <span>{translateText("schema")}: {finalActionSourcePacket.schema_version}</span>
                            <span>{translateText("packet_hash")}: {finalActionSourcePacket.packet_hash.slice(0, 16)}</span>
                            <span>{translateText("evidence_packs")}: {finalActionSourcePacket.evidence_pack_ids.length}</span>
                            <span>{translateText("review_only")}: {String(finalActionSourcePacket.review_only)}</span>
                          </div>
                        ) : (
                          <p className="mt-2 text-cyan-100/80">{translateText("Packet snapshot is required before final-action execution readiness can clear.")}</p>
                        )}
                      </div>
                      <a
                        className="inline-flex h-7 items-center justify-center rounded-md border border-cyan-300/20 bg-cyan-400/10 px-2 text-xs font-medium text-cyan-50 transition-colors hover:bg-cyan-400/15"
                        href={`/api/v1/final-actions/source-review-packets/${encodeURIComponent(finalActionReadiness.source_review_packet_id)}`}
                      >
                        {translateText("Open packet")}
                      </a>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {["read_only_source_review_packet", "immutable_packet_snapshot", "final_actions_not_executed"].map((guardrail) => (
                        <span key={guardrail} className="rounded-full border border-cyan-300/15 bg-black/10 px-2.5 py-1 text-cyan-100">
                          {translateText(guardrail)}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
                <div className="mt-3 rounded-md border border-amber-300/15 bg-amber-500/10 px-3 py-2 text-xs leading-5 text-amber-100">
                  {translateText("Human review boundary")}: {translateText("release_state remains review_required until an explicit audited approval workflow exists.")}
                </div>
              </div>
            </div>
          </>
        ) : (
          <p className="mt-4 text-sm text-surface-300">
            {translateText(isLoadingRCManifest ? "Loading RC manifest" : "RC manifest unavailable")}
          </p>
        )}
      </CockpitPanel>
      <CockpitPanel className="p-5 lg:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <CockpitSectionLabel>{translateText("Model-backed risk")}</CockpitSectionLabel>
            <p className="mt-3 text-sm leading-7 text-surface-300">
              {translateText("Compact Chronos-backed next-window interpretation with heuristic fallback preserved.")}
            </p>
          </div>
          <Badge variant={highestRisk?.fallback_used ? "warning" : "success"}>
            {translateText(highestRisk?.fallback_used ? "Heuristic fallback" : "Chronos")}
          </Badge>
        </div>
        <div className="mt-5 rounded-2xl border border-white/8 bg-white/5 px-4 py-4">
          {highestRisk ? (
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-amber-300/20 bg-amber-500/10 text-amber-100">
                  <Radar className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-medium text-white">
                    {translateText("Next-window warning likelihood")}
                  </p>
                  <p className="mt-1 text-xs text-surface-400">
                    {highestRisk.batch_label} · {highestRisk.model_name} · {highestRisk.execution_mode}
                  </p>
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-3 lg:min-w-[28rem]">
                <div>
                  <p className="assistant-section-kicker !text-surface-500">{translateText("Warning")}</p>
                  <p className="mt-1 text-lg font-semibold text-white">
                    {formatNumber(highestRisk.release_warning_score * 100, 1)}%
                  </p>
                </div>
                <div>
                  <p className="assistant-section-kicker !text-surface-500">{translateText("Future risk")}</p>
                  <p className="mt-1 text-lg font-semibold text-white">
                    {formatNumber(highestRisk.future_risk_score * 100, 1)}%
                  </p>
                </div>
                <div>
                  <p className="assistant-section-kicker !text-surface-500">{translateText("Freshness drift")}</p>
                  <p className="mt-1 text-lg font-semibold text-white">
                    {formatNumber(highestRisk.freshness_drift_score * 100, 1)}%
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-sm text-surface-400">
              {translateText(recentRisks.isLoading ? "Loading model-backed risk metrics." : "No model-backed risk metrics are available yet.")}
            </p>
          )}
        </div>
      </CockpitPanel>
      <BrainOperatorContextCard
        compact
        mode="release"
        title="Autonomy release context"
        description="What the project brain currently thinks matters before the next release-quality push."
      />

      <CockpitPanel className="p-5 lg:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <CockpitSectionLabel>{translateText("Simulation appendix")}</CockpitSectionLabel>
            <p className="mt-3 text-sm leading-7 text-surface-300">
              {translateText("Simulation appendix available means virtual run evidence can be attached for review without changing release decisions.")}
            </p>
          </div>
          <Badge variant={simulationAppendix ? "success" : "neutral"}>
            {translateText(simulationAppendix ? "Simulation appendix available" : simulationAppendixChecked ? "No simulation appendix" : "Checking appendix")}
          </Badge>
        </div>
        <div className="mt-5 grid gap-4 xl:grid-cols-[1fr_0.85fr]">
          <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-4">
            {simulationAppendix ? (
              <div className="flex flex-col gap-4">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                  <div>
                    <p className="text-sm font-medium text-white">{simulationAppendix.simulation_id}</p>
                    <p className="mt-1 text-xs text-surface-400">
                      {simulationAppendix.selected_run
                        ? `${simulationAppendix.selected_run.policy} / ${simulationAppendix.selected_run.audit_event_count} audit hashes`
                        : "Scenario exists without a completed simulation run"}
                    </p>
                    <p className="mt-1 text-xs text-surface-500">
                      {translateText("Evidence pack")} {simulationAppendix.evidence_pack_id ?? "pending"} /{" "}
                      {translateText("Input snapshot")} {simulationAppendix.input_snapshot_id ?? "pending"}
                    </p>
                    <p className="mt-1 text-xs text-surface-500">
                      {translateText("Attached appendices can be linked through release packet APIs without changing release decisions.")}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <Button
                      type="button"
                      variant="secondary"
                      loading={isDownloadingAppendix}
                      leftIcon={<Download className="h-4 w-4" />}
                      onClick={() => void downloadSimulationAppendix()}
                    >
                      {translateText("Download appendix")}
                    </Button>
                    <Button
                      type="button"
                      loading={isAttachingAppendix}
                      disabled={!canUseReleasePacket}
                      onClick={() => void attachSimulationAppendix()}
                    >
                      {translateText("Attach appendix")}
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      loading={isRequestingApproval}
                      disabled={!canUseReleasePacket}
                      onClick={() => void requestHumanApproval()}
                    >
                      {translateText("Request human approval")}
                    </Button>
                  </div>
                </div>
                <div className="grid gap-3 md:grid-cols-3">
                  <div className="rounded-xl border border-white/8 bg-black/10 px-3 py-3">
                    <p className="assistant-section-kicker !text-surface-500">{translateText("Evidence")}</p>
                    <p className="mt-1 text-sm font-medium text-white">{translateText(evidenceStatus)}</p>
                  </div>
                  <div className="rounded-xl border border-white/8 bg-black/10 px-3 py-3">
                    <p className="assistant-section-kicker !text-surface-500">{translateText("Review")}</p>
                    <p className="mt-1 text-sm font-medium text-white">{translateText("Human approval required")}</p>
                  </div>
                  <div className="rounded-xl border border-white/8 bg-black/10 px-3 py-3">
                    <p className="assistant-section-kicker !text-surface-500">{translateText("Decision")}</p>
                    <p className="mt-1 text-sm font-medium text-white">{translateText("Unchanged")}</p>
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-sm text-surface-400">
                {translateText("Run Simulation Lab and export an appendix when release reviewers need virtual evidence.")}
              </p>
            )}
          </div>
          <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-4">
            <Input
              label={translateText("Release decision ID")}
              type="number"
              min={1}
              value={releaseDecisionId}
              onChange={(event) => setReleaseDecisionId(event.target.value)}
            />
            <div className="mt-4 flex items-center justify-between gap-3">
              <p className="text-xs text-surface-400">
                {translateText(isLoadingAppendices ? "Loading attached appendices" : "Attached appendices")}
              </p>
              <Badge variant={attachedAppendices.length ? "success" : "neutral"}>
                {attachedAppendices.length}
              </Badge>
            </div>
            <div className="mt-3 space-y-3">
              {attachedAppendices.length ? (
                attachedAppendices.map((attachment) => (
                  <div key={attachment.attachment_id} className="rounded-xl border border-white/8 bg-black/10 px-3 py-3 text-xs text-surface-300">
                    <p className="font-medium text-white">{attachment.attachment_id}</p>
                    <p className="mt-1">{attachment.simulation_id} / {attachment.run_id ?? "latest run"}</p>
                    <p className="mt-1 text-surface-500">{translateText("Appendix hash")} {attachment.appendix_hash}</p>
                  </div>
                ))
              ) : (
                <p className="text-xs leading-6 text-surface-500">
                  {translateText("No appendices are attached to this release decision yet.")}
                </p>
              )}
            </div>
            {lastApprovalRequest ? (
              <p className="mt-4 rounded-xl border border-emerald-400/15 bg-emerald-500/10 px-3 py-3 text-xs text-emerald-100">
                {translateText("Approval request")} {lastApprovalRequest.approval_request_id} / {translateText(lastApprovalRequest.status)}
              </p>
            ) : null}
          </div>
        </div>
      </CockpitPanel>

      <CockpitPanel className="p-5 lg:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <CockpitSectionLabel>{translateText("Human review workbench")}</CockpitSectionLabel>
            <p className="mt-3 text-sm leading-7 text-surface-300">
              {translateText("Review-gated, queue-only operator surface for pending Assistant confirmations and human approval requests. No auto approval, no model activation, and no external sharing are performed here.")}
            </p>
          </div>
          <Badge variant={reviewQueueCount ? "warning" : "neutral"}>
            {translateText(
              reviewQueueCount
                ? `${reviewQueueCount} pending review items`
                : isLoadingReviewWorkbench
                  ? "Loading review queue"
                  : "No pending review items",
            )}
          </Badge>
        </div>
        <div className="mt-5 grid gap-4 xl:grid-cols-2">
          <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-white">{translateText("Assistant confirmation queue")}</p>
                <p className="mt-1 text-xs text-surface-500">
                  {translateText("Approve/reject only changes AssistantConfirmationRequest status.")}
                </p>
              </div>
              <Badge variant={assistantConfirmations.length ? "warning" : "neutral"}>{assistantConfirmations.length}</Badge>
            </div>
            <div className="mt-4 space-y-3">
              {assistantConfirmations.length ? (
                assistantConfirmations.map((item) => (
                  <div key={item.confirmation_id} className="rounded-xl border border-white/8 bg-black/10 px-3 py-3">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="text-sm font-medium text-white">{item.action_name}</p>
                        <p className="mt-1 text-xs text-surface-500">{item.confirmation_id}</p>
                      </div>
                      <Badge variant={item.status === "pending" ? "warning" : "neutral"}>{translateText(item.status)}</Badge>
                    </div>
                    <div className="mt-3 grid gap-2 text-xs text-surface-400 sm:grid-cols-2">
                      <span>{translateText("Source Assistant run")} {item.source_assistant_run_id}</span>
                      <span>{translateText("Created")} {item.created_at}</span>
                      <span>{translateText("Evidence pack")} {item.evidence_pack_ids[0] ?? item.source_evidence_pack_id ?? "pending"}</span>
                      <span>{translateText("Guardrail")} {item.risk_guardrails[0] ?? "review_gated"}</span>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {item.risk_guardrails.slice(0, 3).map((guardrail) => (
                        <span key={`${item.confirmation_id}-${guardrail}`} className="rounded-full border border-amber-300/15 bg-amber-500/10 px-2.5 py-1 text-xs text-amber-100">
                          {translateText(guardrail)}
                        </span>
                      ))}
                    </div>
                    <div className="mt-4 flex flex-wrap gap-3">
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        loading={resolvingConfirmationId === item.confirmation_id}
                        leftIcon={<Check className="h-4 w-4" />}
                        onClick={() => void resolveAssistantConfirmation(item.source_assistant_run_id, item.confirmation_id, true)}
                      >
                        {translateText("Mark reviewed")}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        loading={resolvingConfirmationId === item.confirmation_id}
                        leftIcon={<X className="h-4 w-4" />}
                        onClick={() => void resolveAssistantConfirmation(item.source_assistant_run_id, item.confirmation_id, false)}
                      >
                        {translateText("Reject queue item")}
                      </Button>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm leading-6 text-surface-400">
                  {translateText("No pending Assistant confirmations are waiting in this tenant queue.")}
                </p>
              )}
            </div>
          </div>
          <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-white">{translateText("Human approval requests")}</p>
                <p className="mt-1 text-xs text-surface-500">
                  {translateText("Pending review requests remain separate from final release approval and model activation.")}
                </p>
              </div>
              <Badge variant={humanApprovalRequests.length ? "warning" : "neutral"}>{humanApprovalRequests.length}</Badge>
            </div>
            <div className="mt-4 space-y-3">
              {humanApprovalRequests.length ? (
                humanApprovalRequests.map((item) => (
                  <div key={item.approval_request_id} className="rounded-xl border border-white/8 bg-black/10 px-3 py-3">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="text-sm font-medium text-white">{item.subject_type}</p>
                        <p className="mt-1 text-xs text-surface-500">{item.approval_request_id}</p>
                      </div>
                      <Badge variant={item.status === "pending" ? "warning" : "neutral"}>{translateText(item.status)}</Badge>
                    </div>
                    <div className="mt-3 grid gap-2 text-xs text-surface-400 sm:grid-cols-2">
                      <span>{translateText("Subject")} {item.subject_id}</span>
                      <span>{translateText("Created")} {item.created_at}</span>
                      <span>{translateText("Source Assistant run")} {item.source_assistant_run_id ?? "manual review request"}</span>
                      <span>{translateText("Evidence pack")} {item.evidence_pack_ids[0] ?? item.source_evidence_pack_id ?? "pending"}</span>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {item.risk_guardrails.slice(0, 4).map((guardrail) => (
                        <span key={`${item.approval_request_id}-${guardrail}`} className="rounded-full border border-cyan-300/15 bg-cyan-500/10 px-2.5 py-1 text-xs text-cyan-100">
                          {translateText(guardrail)}
                        </span>
                      ))}
                    </div>
                    <div className="mt-4 flex flex-wrap gap-3">
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        loading={resolvingApprovalRequestId === item.approval_request_id}
                        leftIcon={<Check className="h-4 w-4" />}
                        onClick={() => void resolveHumanApprovalRequest(item.approval_request_id, true)}
                      >
                        {translateText("Resolve request only")}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        loading={resolvingApprovalRequestId === item.approval_request_id}
                        leftIcon={<X className="h-4 w-4" />}
                        onClick={() => void resolveHumanApprovalRequest(item.approval_request_id, false)}
                      >
                        {translateText("Reject request only")}
                      </Button>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm leading-6 text-surface-400">
                  {translateText("No pending HumanApprovalRequest records are visible for this tenant.")}
                </p>
              )}
            </div>
          </div>
        </div>
        <div className="mt-5 rounded-2xl border border-white/8 bg-white/5 px-4 py-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm font-medium text-white">{translateText("Resolved review history")}</p>
              <p className="mt-1 text-xs leading-5 text-surface-500">
                {translateText("Read-only record of recently approved or rejected queue items. History does not execute final release, model, or sharing actions.")}
              </p>
            </div>
            <Badge variant="neutral">
              {translateText(
                resolvedReviewCount
                  ? `${resolvedReviewCount} resolved items`
                  : isLoadingReviewWorkbench
                    ? "Loading review history"
                    : "No resolved review history",
              )}
            </Badge>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <div className="rounded-xl border border-white/8 bg-black/10 px-3 py-3">
              <p className="text-xs uppercase tracking-[0.16em] text-surface-500">{translateText("Pending queue")}</p>
              <p className="mt-2 text-lg font-semibold text-white">{reviewQueueCount}</p>
            </div>
            <div className="rounded-xl border border-white/8 bg-black/10 px-3 py-3">
              <p className="text-xs uppercase tracking-[0.16em] text-surface-500">{translateText("Resolved approvals")}</p>
              <p className="mt-2 text-lg font-semibold text-white">{approvedReviewCount}</p>
            </div>
            <div className="rounded-xl border border-white/8 bg-black/10 px-3 py-3">
              <p className="text-xs uppercase tracking-[0.16em] text-surface-500">{translateText("Resolved rejections")}</p>
              <p className="mt-2 text-lg font-semibold text-white">{rejectedReviewCount}</p>
            </div>
            <div className="rounded-xl border border-cyan-300/15 bg-cyan-500/10 px-3 py-3">
              <p className="text-xs uppercase tracking-[0.16em] text-cyan-100">{translateText("Final actions")}</p>
              <p className="mt-2 text-sm font-medium text-cyan-50">{translateText("not executed")}</p>
              <p className="mt-1 text-xs text-cyan-100/80">
                {translateText(latestResolvedAt ? `Latest resolved ${latestResolvedAt}` : "No resolved timestamp")}
              </p>
            </div>
          </div>
          <div className="mt-4 rounded-xl border border-cyan-300/15 bg-cyan-500/10 px-4 py-4">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <p className="text-sm font-medium text-cyan-50">{translateText("Operator audit packet")}</p>
                <p className="mt-1 text-xs leading-5 text-cyan-100/80">
                  {translateText("Read-only export of pending queue, resolved dispositions, evidence IDs, and side-effect guardrails. Final actions remain not executed.")}
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  loading={isExportingReviewAuditPacket}
                  leftIcon={<Download className="h-4 w-4" />}
                  onClick={() => void downloadReviewWorkbenchAuditPacket("md")}
                >
                  {translateText("Download audit packet")}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  loading={isExportingReviewAuditPacket}
                  onClick={() => void downloadReviewWorkbenchAuditPacket("json")}
                >
                  {translateText("JSON packet")}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  loading={isPersistingReviewAuditPacketSnapshot}
                  onClick={() => void persistReviewWorkbenchAuditPacketSnapshot()}
                >
                  {translateText("Persist source packet")}
                </Button>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {[
                "pending_queue",
                "resolved_dispositions",
                "evidence_pack_ids",
                "side_effect_guardrails",
                "final_actions_not_executed",
              ].map((label) => (
                <span key={label} className="rounded-full border border-cyan-300/15 bg-black/10 px-2.5 py-1 text-xs text-cyan-100">
                  {translateText(label)}
                </span>
              ))}
            </div>
          </div>
          <div className="mt-4 rounded-xl border border-amber-300/15 bg-amber-500/10 px-4 py-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="flex items-center gap-2 text-sm font-medium text-amber-50">
                  <Lock className="h-4 w-4" aria-hidden="true" />
                  {translateText("Final actions readiness")}
                </p>
                <p className="mt-1 text-xs leading-5 text-amber-100/80">
                  {translateText("Audited workflow for request drafts, draft review, execution readiness, and final action audit records. Assistant and HumanApprovalRequest disposition remain separate.")}
                </p>
              </div>
              <Badge variant="warning">
                {translateText(
                  finalActionReadiness
                    ? "audited final-action workflow"
                    : isLoadingFinalActionReadiness
                      ? "Loading readiness"
                      : "Readiness unavailable",
                )}
              </Badge>
            </div>
            {finalActionReadiness ? (
              <>
                <div className="mt-4 grid gap-3 md:grid-cols-3">
                  {finalActionReadiness.actions.map((action) => {
                    const draftGateBlockers = finalActionDraftGateBlockers(action);
                    const canCreateDraft = canCreateFinalActionDraft(finalActionReadiness, action);
                    return (
                      <div
                        key={action.action}
                        data-testid={`final-action-readiness-card-${action.action}`}
                        className="rounded-lg border border-amber-300/15 bg-black/10 px-3 py-3"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <p className="text-sm font-medium text-amber-50">{translateText(finalActionLabel(action.action))}</p>
                          <Badge variant={action.status === "blocked" ? "danger" : "warning"}>
                            {translateText(action.status)}
                          </Badge>
                        </div>
                        <div className="mt-3 space-y-1 text-xs text-amber-100/80">
                          <p>{translateText("executable")}: {String(action.executable)}</p>
                          <p>{translateText("required_roles")}: {action.required_roles.join(", ")}</p>
                          <p>{translateText("required_evidence_ids")}: {action.required_evidence_ids.length ? action.required_evidence_ids.join(", ") : "none"}</p>
                          <p>{translateText("missing_evidence_ids")}: {action.missing_evidence_ids.length ? action.missing_evidence_ids.join(", ") : "none"}</p>
                          <p>{translateText("source_review_packet_required")}: {String(action.source_review_packet_required)}</p>
                          <p>{translateText("blockers")}: {action.blockers.length ? action.blockers.join(" / ") : "none"}</p>
                          <p>{translateText("draft_gate")}: {canCreateDraft ? "ready_for_request_draft" : draftGateBlockers[0] ?? action.missing_evidence_ids[0] ?? "source_review_packet_required"}</p>
                        </div>
                        <div className="mt-3">
                          <Button
                            type="button"
                            size="sm"
                            variant="secondary"
                            loading={finalActionBusyKey === `draft:${action.action}`}
                            disabled={!canCreateDraft}
                            data-testid={`final-action-create-draft-${action.action}`}
                            onClick={() => void createFinalActionDraft(action)}
                          >
                            {translateText("Create request draft")}
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-3 rounded-lg border border-amber-300/15 bg-black/10 px-3 py-3">
                  <p className="text-xs font-medium text-amber-50">{translateText("Final execution attestation")}</p>
                  <Input
                    className="mt-2"
                    value={finalActionAttestation}
                    onChange={(event) => setFinalActionAttestation(event.target.value)}
                  />
                  <div className="mt-3 grid gap-2 md:grid-cols-2">
                    <Input
                      value={externalShareRecipientScope}
                      onChange={(event) => setExternalShareRecipientScope(event.target.value)}
                      aria-label="External share recipient scope"
                    />
                    <Input
                      value={externalShareRedactionPolicyId}
                      onChange={(event) => setExternalShareRedactionPolicyId(event.target.value)}
                      aria-label="External share redaction policy"
                    />
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {[
                    `release_decision: ${finalActionReadiness.current_state.latest_release_decision ?? "missing"}`,
                    `model_version: ${finalActionReadiness.current_state.latest_model_version_status ?? "missing"}`,
                    `external_share_record_created: ${String(finalActionReadiness.current_state.external_share_record_created)}`,
                    `audit_schema_available: ${String(finalActionReadiness.audit_schema_available)}`,
                    `request_draft_schema_available: ${String(finalActionReadiness.request_draft_schema_available)}`,
                    `final_action_request_drafts_created: ${String(finalActionReadiness.current_state.final_action_request_drafts_created)}`,
                    `final_action_request_drafts: ${finalActionRequestDrafts?.count ?? "unavailable"}`,
                    `source_review_packet_id: ${finalActionReadiness.source_review_packet_id ?? "not_persisted"}`,
                    `final_action_audit_records: ${finalActionAuditRecords?.count ?? "unavailable"}`,
                    "no_assistant_confirmation_authority",
                    "no_human_approval_disposition_authority",
                    "no_hardware_execution",
                  ].map((label) => (
                    <span key={label} className="rounded-full border border-amber-300/15 bg-black/10 px-2.5 py-1 text-xs text-amber-100">
                      {translateText(label)}
                    </span>
                  ))}
                </div>
                {finalActionSourcePacket ? (
                  <div className="mt-3 rounded-lg border border-amber-300/15 bg-black/10 px-3 py-3 text-xs text-amber-100/80">
                    <p className="font-medium text-amber-50">{translateText("Source review packet snapshot")}</p>
                    <div className="mt-2 grid gap-1 sm:grid-cols-2">
                      <p>{translateText("packet_hash")}: {finalActionSourcePacket.packet_hash.slice(0, 16)}</p>
                      <p>{translateText("packet_type")}: {finalActionSourcePacket.packet_type}</p>
                      <p>{translateText("evidence_packs")}: {finalActionSourcePacket.evidence_pack_ids.length}</p>
                      <p>{translateText("read_only")}: {String(finalActionSourcePacket.review_only)}</p>
                    </div>
                  </div>
                ) : null}
                {finalActionAuditRecords ? (
                  <div className="mt-3 rounded-lg border border-amber-300/15 bg-black/10 px-3 py-3 text-xs text-amber-100/80">
                    <p className="font-medium text-amber-50">{translateText("Final action audit records")}</p>
                    <div className="mt-2 grid gap-1 sm:grid-cols-2">
                      <p>{translateText("records")}: {finalActionAuditRecords.count}</p>
                      <p>{translateText("read_only")}: {String(finalActionAuditRecords.review_only)}</p>
                      <p>{translateText("schema")}: {finalActionAuditRecords.schema_version}</p>
                      <p>{translateText("guardrail")}: {finalActionAuditRecords.guardrails[0] ?? "none"}</p>
                    </div>
                    {finalActionAuditRecords.records.length ? (
                      <div className="mt-3 grid gap-2">
                        {finalActionAuditRecords.records.slice(0, 4).map((record) => {
                          const afterState = record.after_state ?? {};
                          return (
                            <div key={record.final_action_id} className="rounded-lg border border-amber-300/10 bg-black/10 px-3 py-2">
                              <p className="text-xs font-medium text-amber-50">{record.action_type}: {record.decision}</p>
                              <p className="mt-1 text-xs text-amber-100/70">final_action_id: {record.final_action_id}</p>
                              {typeof afterState.delivery_status === "string" ? (
                                <p className="mt-1 text-xs text-amber-100/70">delivery_status: {afterState.delivery_status}</p>
                              ) : null}
                              {typeof afterState.external_network_send === "boolean" ? (
                                <p className="mt-1 text-xs text-amber-100/70">external_network_send: {String(afterState.external_network_send)}</p>
                              ) : null}
                            </div>
                          );
                        })}
                      </div>
                    ) : null}
                    {preparedExternalShareId ? (
                      <div className="mt-3 rounded-lg border border-amber-300/15 bg-amber-500/10 px-3 py-3">
                        <p className="text-sm font-medium text-amber-50">{translateText("Outbound external share delivery")}</p>
                        <p className="mt-1 text-xs text-amber-100/70">
                          {translateText("share_id")}: {preparedExternalShareId}
                        </p>
                        <div className="mt-3 grid gap-2 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
                          <Input
                            value={externalShareDeliveryEndpoint}
                            onChange={(event) => setExternalShareDeliveryEndpoint(event.target.value)}
                            placeholder="http://127.0.0.1:8039/external-share-receiver"
                            data-testid="external-share-delivery-endpoint"
                          />
                          <Button
                            type="button"
                            size="sm"
                            leftIcon={<Network className="h-4 w-4" />}
                            loading={finalActionBusyKey === `deliver:${preparedExternalShareId}`}
                            disabled={!externalShareDeliveryEndpoint.trim() || !finalActionAttestation.trim()}
                            data-testid="external-share-delivery-execute"
                            onClick={() => void executeExternalShareDelivery()}
                          >
                            {translateText("Deliver external share")}
                          </Button>
                        </div>
                        <p className="mt-2 text-xs text-amber-100/70">
                          {translateText("Requires allowlisted endpoint, approved share record, redaction policy, and explicit external_network_send audit.")}
                        </p>
                      </div>
                    ) : null}
                  </div>
                ) : null}
                {finalActionRequestDrafts ? (
                  <div className="mt-3 rounded-lg border border-amber-300/15 bg-black/10 px-3 py-3 text-xs text-amber-100/80">
                    <p className="font-medium text-amber-50">{translateText("Final action request drafts")}</p>
                    <div className="mt-2 grid gap-1 sm:grid-cols-2">
                      <p>{translateText("drafts")}: {finalActionRequestDrafts.count}</p>
                      <p>{translateText("read_only")}: {String(finalActionRequestDrafts.review_only)}</p>
                      <p>{translateText("schema")}: {finalActionRequestDrafts.schema_version}</p>
                      <p>{translateText("guardrail")}: {finalActionRequestDrafts.guardrails[0] ?? "none"}</p>
                    </div>
                    {finalActionRequestDrafts.drafts.length ? (
                      <div className="mt-3 space-y-3">
                        {finalActionRequestDrafts.drafts.map((draft) => {
                          const isApproved = draft.status === "review_approved_no_execution";
                          return (
                            <div
                              key={draft.final_action_request_id}
                              data-testid={`final-action-draft-card-${draft.action_type}`}
                              className="rounded-lg border border-amber-300/15 bg-amber-500/10 px-3 py-3"
                            >
                              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                                <div>
                                  <p className="text-sm font-medium text-amber-50">{translateText(finalActionLabel(draft.action_type))}</p>
                                  <p className="mt-1 text-xs text-amber-100/70">{draft.final_action_request_id}</p>
                                  <p className="mt-1 text-xs text-amber-100/70">{draft.target_type}: {draft.target_id}</p>
                                  <p className="mt-1 text-xs text-amber-100/70">{translateText("status")}: {draft.status}</p>
                                  {finalActionReadinessByDraft[draft.final_action_request_id] ? (
                                    <p className="mt-1 text-xs text-amber-100">{finalActionReadinessByDraft[draft.final_action_request_id]}</p>
                                  ) : null}
                                </div>
                                <div className="flex flex-wrap gap-2">
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="secondary"
                                    loading={finalActionBusyKey === `resolve:${draft.final_action_request_id}:true`}
                                    disabled={isApproved}
                                    data-testid={`final-action-approve-draft-${draft.action_type}`}
                                    onClick={() => void resolveFinalActionDraft(draft, true)}
                                  >
                                    {translateText("Approve draft")}
                                  </Button>
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="ghost"
                                    loading={finalActionBusyKey === `resolve:${draft.final_action_request_id}:false`}
                                    onClick={() => void resolveFinalActionDraft(draft, false)}
                                  >
                                    {translateText("Reject draft")}
                                  </Button>
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="ghost"
                                    loading={finalActionBusyKey === `readiness:${draft.final_action_request_id}`}
                                    data-testid={`final-action-check-readiness-${draft.action_type}`}
                                    onClick={() => void checkFinalActionDraftReadiness(draft)}
                                  >
                                    {translateText("Check execution readiness")}
                                  </Button>
                                  <Button
                                    type="button"
                                    size="sm"
                                    leftIcon={<PlayCircle className="h-4 w-4" />}
                                    loading={finalActionBusyKey === `execute:${draft.final_action_request_id}`}
                                    disabled={!isApproved || !finalActionAttestation.trim()}
                                    data-testid={`final-action-execute-${draft.action_type}`}
                                    onClick={() => void executeFinalActionDraft(draft)}
                                  >
                                    {translateText(finalActionExecuteLabel(draft.action_type))}
                                  </Button>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </>
            ) : (
              <p className="mt-3 text-sm text-amber-100/80">
                {translateText("Final action readiness is unavailable; no final-action controls are exposed.")}
              </p>
            )}
          </div>
          {resolvedReviewCount ? (
            <div className="mt-4 grid gap-4 xl:grid-cols-2">
              <div className="space-y-3">
                <p className="text-xs font-medium uppercase tracking-[0.16em] text-surface-500">
                  {translateText("Assistant confirmations")}
                </p>
                {resolvedAssistantConfirmations.length ? (
                  resolvedAssistantConfirmations.map((item) => (
                    <div key={item.confirmation_id} className="rounded-xl border border-white/8 bg-black/10 px-3 py-3">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <p className="text-sm font-medium text-white">{item.action_name}</p>
                          <p className="mt-1 text-xs text-surface-500">{item.confirmation_id}</p>
                        </div>
                        <Badge variant="neutral">{translateText(item.status)}</Badge>
                      </div>
                      <div className="mt-3 grid gap-2 text-xs text-surface-400 sm:grid-cols-2">
                        <span>{translateText("Resolved")} {item.resolved_at ?? "pending timestamp"}</span>
                        <span>{translateText("Source Assistant run")} {item.source_assistant_run_id}</span>
                        <span>{translateText("Evidence pack")} {item.evidence_pack_ids[0] ?? item.source_evidence_pack_id ?? "pending"}</span>
                        <span>{translateText("Reason")} {item.reason ?? "No reason supplied"}</span>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {item.risk_guardrails.slice(0, 3).map((guardrail) => (
                          <span key={`${item.confirmation_id}-history-${guardrail}`} className="rounded-full border border-amber-300/15 bg-amber-500/10 px-2.5 py-1 text-xs text-amber-100">
                            {translateText(guardrail)}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-sm leading-6 text-surface-400">
                    {translateText("No resolved Assistant confirmation records yet.")}
                  </p>
                )}
              </div>
              <div className="space-y-3">
                <p className="text-xs font-medium uppercase tracking-[0.16em] text-surface-500">
                  {translateText("Human approval dispositions")}
                </p>
                {resolvedHumanApprovalRequests.length ? (
                  resolvedHumanApprovalRequests.map((item) => {
                    const sideEffectLines = humanApprovalSideEffectLines(item);
                    return (
                      <div key={item.approval_request_id} className="rounded-xl border border-white/8 bg-black/10 px-3 py-3">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div>
                            <p className="text-sm font-medium text-white">{item.subject_type}</p>
                            <p className="mt-1 text-xs text-surface-500">{item.approval_request_id}</p>
                          </div>
                          <Badge variant="neutral">{translateText(item.status)}</Badge>
                        </div>
                        <div className="mt-3 grid gap-2 text-xs text-surface-400 sm:grid-cols-2">
                          <span>{translateText("Resolved")} {item.resolved_at ?? "pending timestamp"}</span>
                          <span>{translateText("Source Assistant run")} {item.source_assistant_run_id ?? "manual review request"}</span>
                          <span>{translateText("Evidence pack")} {item.evidence_pack_ids[0] ?? item.source_evidence_pack_id ?? "pending"}</span>
                          <span>{translateText("Reason")} {item.reason ?? "No reason supplied"}</span>
                        </div>
                        {sideEffectLines.length ? (
                          <div className="mt-3 rounded-lg border border-cyan-300/15 bg-cyan-500/10 px-3 py-2">
                            <p className="text-xs font-medium text-cyan-100">
                              {translateText("workbench_resolution.side_effects")}
                            </p>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {sideEffectLines.map((line) => (
                                <span key={`${item.approval_request_id}-${line}`} className="rounded-full border border-cyan-300/15 bg-black/10 px-2.5 py-1 text-xs text-cyan-100">
                                  {translateText(line)}
                                </span>
                              ))}
                            </div>
                          </div>
                        ) : null}
                      </div>
                    );
                  })
                ) : (
                  <p className="text-sm leading-6 text-surface-400">
                    {translateText("No resolved HumanApprovalRequest records yet.")}
                  </p>
                )}
              </div>
            </div>
          ) : (
            <p className="mt-4 text-sm leading-6 text-surface-400">
              {translateText("Resolved approved and rejected review items will appear here after queue-only disposition.")}
            </p>
          )}
        </div>
        {reviewWorkbench?.guardrails.length ? (
          <p className="mt-4 text-xs text-surface-500">
            {translateText("Workbench guardrails")} {reviewWorkbench.guardrails.join(" / ")}
          </p>
        ) : null}
      </CockpitPanel>

      <CockpitPanel className="p-5 lg:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <CockpitSectionLabel>{translateText("Assistant proof appendix")}</CockpitSectionLabel>
            <p className="mt-3 text-sm leading-7 text-surface-300">
              {translateText("Compliance, LCA, and TEA proof generated by Assistant remain review-only evidence for release reviewers.")}
            </p>
          </div>
          <Badge variant={assistantProofCards.length ? "warning" : "neutral"}>
            {translateText(
              assistantProofCards.length
                ? "Proofs require review"
                : isLoadingAssistantProofs
                  ? "Loading proofs"
                  : "No assistant proofs",
            )}
          </Badge>
        </div>
        <div className="mt-5 grid gap-3 lg:grid-cols-2 xl:grid-cols-4">
          {assistantProofCards.length ? (
            assistantProofCards.map((proof) => (
              <div key={`${proof.kind}-${proof.resultId ?? proof.evidencePackId}`} className="rounded-xl border border-white/8 bg-white/5 px-4 py-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-white">{translateText(proof.title)}</p>
                    <p className="mt-1 text-xs text-surface-500">{proof.resultId ?? "review artifact"}</p>
                  </div>
                  <Badge variant={proof.status === "blocked" ? "danger" : "warning"}>{translateText(proof.status)}</Badge>
                </div>
                <div className="mt-3 space-y-2">
                  {proof.lines.slice(0, 3).map((line) => (
                    <p key={line} className="text-xs leading-5 text-surface-300">
                      {line}
                    </p>
                  ))}
                </div>
                <p className="mt-3 text-xs text-surface-500">
                  {translateText("Evidence pack")} {proof.evidencePackId ?? "pending"}
                </p>
              </div>
            ))
          ) : (
            <p className="rounded-xl border border-white/8 bg-white/5 px-4 py-4 text-sm text-surface-400 lg:col-span-2 xl:col-span-4">
              {translateText("Ask Assistant to run compliance, LCA, and TEA after Simulation Lab to populate review-only proof cards here.")}
            </p>
          )}
        </div>
        {latestAssistantRun ? (
          <p className="mt-4 text-xs text-surface-500">
            {translateText("Source Assistant run")} {latestAssistantRun.run_id} / {translateText("Release decision remains unchanged")}
          </p>
        ) : null}
      </CockpitPanel>

      <CockpitPanel className="p-5 lg:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <CockpitSectionLabel>{translateText("Governance kernel")}</CockpitSectionLabel>
            <p className="mt-3 text-sm leading-7 text-surface-300">
              {translateText("Replay, benchmark, model review, and knowledge relations stay review-gated and evidence-linked.")}</p>
          </div>
          <Badge variant={latestGovernanceReview ? "warning" : "neutral"}>
            {translateText(latestGovernanceReview ? "Review requested" : isLoadingGovernanceKernel ? "Loading governance" : "Review-gated")}
          </Badge>
        </div>
        <div className="mt-5 grid gap-4 xl:grid-cols-[1fr_0.85fr]">
          <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-4">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-cyan-300/20 bg-cyan-500/10 text-cyan-100">
                  <GitBranch className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-medium text-white">{translateText("Benchmark suite")}</p>
                  <p className="mt-1 text-xs text-surface-400">
                    {benchmarkCases.length} {translateText("cases loaded for regression review")}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-3">
                <Button
                  type="button"
                  loading={isRunningBenchmark}
                  onClick={() => void runBenchmarkSuite()}
                >
                  {translateText("Run benchmark suite")}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  loading={isRequestingModelReview}
                  disabled={!latestBenchmarkRun}
                  onClick={() => void requestModelReview()}
                >
                  {translateText("Request model review")}
                </Button>
              </div>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <div className="rounded-xl border border-white/8 bg-black/10 px-3 py-3">
                <p className="assistant-section-kicker !text-surface-500">{translateText("Benchmark")}</p>
                <p className="mt-1 text-sm font-medium text-white">
                  {latestBenchmarkRun?.benchmark_run_id ?? translateText("Not run")}
                </p>
                <p className="mt-1 text-xs text-surface-500">
                  {benchmarkCaseCount === null
                    ? latestBenchmarkRun?.evidence_pack_id ?? translateText("Evidence pending")
                    : `${benchmarkPassedCount ?? 0}/${benchmarkCaseCount} ${translateText("passed")} / ${benchmarkFailedCount ?? 0} ${translateText("failed")}`}
                </p>
                <p className={(benchmarkFailedCount ?? 0) > 0 ? "mt-2 text-xs font-medium text-amber-200" : "mt-2 text-xs font-medium text-cyan-100"}>
                  {translateText(benchmarkReviewState)}
                </p>
              </div>
              <div className="rounded-xl border border-white/8 bg-black/10 px-3 py-3">
                <p className="assistant-section-kicker !text-surface-500">{translateText("Model")}</p>
                <p className="mt-1 text-sm font-medium text-white">
                  {displayedModelId ?? translateText("Candidate pending")}
                </p>
                <p className="mt-1 text-xs text-surface-500">
                  {translateText(displayedModelStatus)}
                </p>
              </div>
              <div className="rounded-xl border border-white/8 bg-black/10 px-3 py-3">
                <p className="assistant-section-kicker !text-surface-500">{translateText("Governance")}</p>
                <p className="mt-1 text-sm font-medium text-white">
                  {translateText(displayedGovernanceStatus)}
                </p>
                <p className="mt-1 text-xs text-surface-500">
                  {displayedKnowledgeRelationId ?? translateText("Knowledge link pending")}
                </p>
                {latestGovernanceReview?.approval_request_id ? (
                  <p className="mt-1 text-xs text-amber-200">
                    {translateText("Approval request")} {latestGovernanceReview.approval_request_id} / {translateText("pending")}
                  </p>
                ) : null}
              </div>
            </div>
            <div className="mt-4 rounded-xl border border-amber-300/15 bg-amber-500/10 px-4 py-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-sm font-medium text-amber-50">{translateText("Model provider capability matrix")}</p>
                  <p className="mt-1 text-xs leading-5 text-amber-100/80">
                    {translateText(providerCapabilityMatrix?.checked_date_policy ?? "Provider pricing, retention, region, and capability metadata remain review-gated.")}
                  </p>
                </div>
                <Badge variant="warning">
                  {translateText(`${providerCapabilityMatrix?.count ?? 0} metadata candidates`)}
                </Badge>
              </div>
              <div className="mt-3 grid gap-2 md:grid-cols-3">
                {providerCapabilityPreview.length ? (
                  providerCapabilityPreview.map((provider) => (
                    <div key={`${provider.provider}-${provider.model_id}`} className="rounded-lg border border-amber-300/15 bg-black/10 px-3 py-3">
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-sm font-medium text-amber-50">{provider.provider}</p>
                        <Badge variant="warning">{translateText(provider.review_status)}</Badge>
                      </div>
                      <p className="mt-1 text-xs text-amber-100/70">{provider.model_id}</p>
                      <p className="mt-1 truncate text-xs text-amber-100/70">{provider.source_ref}</p>
                      <p className="mt-1 text-xs text-amber-100/70">
                        {translateText("Checked")} {provider.checked_date} / {translateText("review required")}
                      </p>
                    </div>
                  ))
                ) : (
                  <p className="text-xs leading-5 text-amber-100/80 md:col-span-3">
                    {translateText("Provider capability metadata is not loaded yet.")}
                  </p>
                )}
              </div>
            </div>
            <div className="mt-4 rounded-xl border border-cyan-300/15 bg-cyan-500/10 px-4 py-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-sm font-medium text-cyan-50">{translateText("External knowledge promotion workflow")}</p>
                  <p className="mt-1 text-xs leading-5 text-cyan-100/80">
                    {translateText("Promotion requests create human-review records only; validated defaults remain unchanged until a separate manual patch.")}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="warning">
                    {translateText(`${externalKnowledgeCandidates?.count ?? 0} gated candidates`)}
                  </Badge>
                  <Button
                    type="button"
                    variant="secondary"
                    loading={isRequestingExternalPromotion}
                    disabled={!firstExternalPromotionCandidate}
                    onClick={() => void requestExternalPromotionReview()}
                  >
                    {translateText("Request promotion review")}
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    loading={isResolvingExternalPromotion}
                    disabled={!latestExternalPromotionRequest || latestExternalPromotionRequest.status !== "pending"}
                    onClick={() => void approveExternalPromotionReview()}
                  >
                    {translateText("Approve promotion review")}
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    loading={isApplyingExternalRegistryPatch}
                    disabled={!latestExternalPromotionRequest || latestExternalPromotionRequest.status !== "approved"}
                    onClick={() => void applyExternalRegistryPatch()}
                  >
                    {translateText("Apply manual registry patch")}
                  </Button>
                </div>
              </div>
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                {externalKnowledgePreview.length ? (
                  externalKnowledgePreview.map((candidate) => (
                    <div key={candidate.candidate_uid} className="rounded-lg border border-cyan-300/15 bg-black/10 px-3 py-3">
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-sm font-medium text-cyan-50">{candidate.key}</p>
                        <Badge variant="warning">{translateText(candidate.review_status)}</Badge>
                      </div>
                      <p className="mt-1 text-xs text-cyan-100/70">{candidate.candidate_type}</p>
                      <p className="mt-1 truncate text-xs text-cyan-100/70">{candidate.source_ref}</p>
                    </div>
                  ))
                ) : (
                  <p className="text-xs leading-5 text-cyan-100/80 md:col-span-2">
                    {translateText("External knowledge candidates are not loaded yet.")}
                  </p>
                )}
              </div>
              {latestExternalPromotionRequest ? (
                <p className="mt-3 rounded-lg border border-cyan-300/15 bg-black/10 px-3 py-2 text-xs text-cyan-100">
                  {translateText("Promotion request")} {latestExternalPromotionRequest.approval_request_id} / {translateText(latestExternalPromotionRequest.status)} /{" "}
                  {translateText("validated defaults unchanged")}
                </p>
              ) : null}
              {latestExternalRegistryPatch ? (
                <p className="mt-2 rounded-lg border border-cyan-300/15 bg-black/10 px-3 py-2 text-xs text-cyan-100">
                  {translateText("Manual registry patch")} {latestExternalRegistryPatch.registry_patch_id} /{" "}
                  {translateText("runtime defaults unchanged")}
                </p>
              ) : null}
              <div className="mt-4 rounded-lg border border-sky-300/15 bg-sky-500/10 px-3 py-3">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <p className="text-sm font-medium text-sky-50">{translateText("Reviewed metadata lane")}</p>
                    <p className="mt-1 text-xs leading-5 text-sky-100/75">
                      {translateText("Review-cleared BSF metadata candidates are visible to release reviewers as context only; they are not runtime activations and cannot be used as release evidence yet.")}
                    </p>
                  </div>
                  <Badge variant={reviewedMetadataCandidates.length ? "success" : "warning"}>
                    {translateText(`${reviewedMetadataSummary?.reviewed_metadata_candidate_count ?? reviewedMetadataCandidates.length} reviewed metadata candidates`)}
                  </Badge>
                </div>
                <div className="mt-3 grid gap-2 text-xs text-sky-100/80 sm:grid-cols-2 lg:grid-cols-4">
                  <span>{translateText("pending_runtime_activation")}: {reviewedMetadataSummary?.pending_runtime_activation_count ?? reviewedMetadataCandidates.length}</span>
                  <span>{translateText("runtime_activated")}: {reviewedMetadataSummary?.runtime_activated_count ?? 0}</span>
                  <span>{translateText("numeric_value_candidates")}: {reviewedMetadataSummary?.numeric_value_candidate_count ?? 0}</span>
                  <span>{translateText("default_write_enabled")}: {reviewedMetadataSummary?.validated_default_write_enabled_count ?? 0}</span>
                </div>
                <div className="mt-3 grid gap-2 md:grid-cols-2">
                  {isLoadingReviewedMetadataLane ? (
                    <p className="text-xs leading-5 text-sky-100/80 md:col-span-2">
                      {translateText("Loading reviewed metadata candidates.")}
                    </p>
                  ) : reviewedMetadataCandidates.length ? (
                    reviewedMetadataCandidates.slice(0, 4).map((candidate) => (
                      <ReviewedMetadataLaneCard
                        key={candidate.candidate_id}
                        candidate={candidate}
                        evidenceSummary={reviewedMetadataEvidenceById[candidate.candidate_id]}
                      />
                    ))
                  ) : (
                    <p className="text-xs leading-5 text-sky-100/80 md:col-span-2">
                      {translateText("No reviewed metadata candidates are available yet. Resolve source review cards first; runtime activation remains blocked.")}
                    </p>
                  )}
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {Array.from(new Set([
                    ...(reviewedMetadataSummary?.guardrails ?? reviewedMetadataLane?.guardrails ?? [
                      "approved_for_candidate_use_is_not_runtime_activation",
                      "runtime_activated_false_until_overlay_activation",
                      "validated_default_write_enabled_false",
                    ]),
                    "metadata_candidates_excluded_from_final_action_evidence",
                  ])).map((guardrail) => (
                    <span key={guardrail} className="rounded-full border border-sky-300/15 bg-black/10 px-2.5 py-1 text-xs text-sky-100">
                      {translateText(guardrail)}
                    </span>
                  ))}
                </div>
              </div>
              <div className="mt-4 rounded-lg border border-fuchsia-300/15 bg-fuchsia-500/10 px-3 py-3">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <p className="text-sm font-medium text-fuchsia-50">
                      {translateText("Literature promotion audit export")}
                    </p>
                    <p className="mt-1 text-xs leading-5 text-fuchsia-100/75">
                      {translateText("Promotion audit packets expose request, approval, overlay, activation, release evidence, rollback, and non-execution proof as response-only JSON.")}
                    </p>
                  </div>
                  <Badge variant={literaturePromotionAuditPreview.length ? "warning" : "neutral"}>
                    {translateText(
                      literaturePromotionAuditPreview.length
                        ? "response_only_no_file_write"
                        : isLoadingLiteraturePromotionAudits
                          ? "Loading audit exports"
                          : "review_required",
                    )}
                  </Badge>
                </div>
                <div className="mt-3 grid gap-2 text-xs text-fuchsia-100/80 sm:grid-cols-2 lg:grid-cols-4">
                  <span>{translateText("literature_candidates")}: {literaturePromotionCandidateCount}</span>
                  <span>{translateText("audit_exports")}: {literaturePromotionAuditExports.length}</span>
                  <span>{translateText("release_decision")}: {translateText("review_required")}</span>
                  <span>{translateText("side_effects")}: {String(literaturePromotionAuditSideEffects)}</span>
                </div>
                <div className="mt-3 rounded-lg border border-fuchsia-300/15 bg-black/10 px-3 py-3">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
                    <Input
                      label="Release evidence link notes"
                      value={literatureReleaseEvidenceLinkNotes}
                      onChange={(event) => setLiteratureReleaseEvidenceLinkNotes(event.target.value)}
                    />
                    <Button
                      type="button"
                      variant="secondary"
                      loading={isLinkingLiteratureReleaseEvidence}
                      disabled={!canLinkLiteratureReleaseEvidence || !literatureReleaseEvidenceLinkNotes.trim()}
                      onClick={() => void linkLiteratureReleaseEvidence()}
                    >
                      {translateText("Link active scoped value as release evidence")}
                    </Button>
                  </div>
                  <div className="mt-3 grid gap-2 text-xs text-fuchsia-100/80 sm:grid-cols-2 lg:grid-cols-4">
                    <span>{translateText("active_activation_id")}: {displayAuditValue(literatureEvidenceLinkActivationId)}</span>
                    <span>{translateText("selected_release_decision_id")}: {Number.isInteger(numericReleaseDecisionId) ? numericReleaseDecisionId : "none"}</span>
                    <span>{translateText("release_decision_before")}: {translateText("review_required")}</span>
                    <span>{translateText("release_decision_after")}: {translateText("review_required")}</span>
                    <span>{translateText("release_decision_unchanged")}: true</span>
                    <span>{translateText("species_db_write")}: false</span>
                    <span>{translateText("feedstock_db_write")}: false</span>
                    <span>{translateText("validated_default_write")}: false</span>
                    <span>{translateText("final_action_execution")}: false</span>
                    <span>{translateText("default writes")}: false</span>
                    <span>{translateText("final action execution")}: false</span>
                    <span>{translateText("link_id")}: {displayAuditValue(literatureReleaseEvidenceLinkResult?.link_id)}</span>
                  </div>
                </div>
                <div className="mt-3 grid gap-2 md:grid-cols-2">
                  {isLoadingLiteraturePromotionAudits ? (
                    <p className="text-xs leading-5 text-fuchsia-100/80 md:col-span-2">
                      {translateText("Loading literature promotion audit exports.")}
                    </p>
                  ) : literaturePromotionAuditPreview.length ? (
                    literaturePromotionAuditPreview.map((auditExport) => (
                      <LiteraturePromotionAuditLaneCard
                        key={`${auditExport.candidate_id}-${auditExport.content_hash}`}
                        auditExport={auditExport}
                      />
                    ))
                  ) : (
                    <p className="text-xs leading-5 text-fuchsia-100/80 md:col-span-2">
                      {translateText("No literature promotion audit exports are available yet; release decision remains review_required and no final action is exposed.")}
                    </p>
                  )}
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {[
                    "export_response_only_no_file_write",
                    "release_decision_remains_review_required",
                    "no_validated_default_writes",
                    "no_final_action_execution",
                  ].map((guardrail) => (
                    <span key={guardrail} className="rounded-full border border-fuchsia-300/15 bg-black/10 px-2.5 py-1 text-xs text-fuchsia-100">
                      {translateText(guardrail)}
                    </span>
                  ))}
                </div>
              </div>
              <p className="mt-3 text-xs text-cyan-100/70">
                {translateText("Validated external registry")} {validatedExternalRegistry?.count ?? 0} /{" "}
                {translateText("runtime defaults mutated")} {String(validatedExternalRegistry?.runtime_defaults_mutated ?? false)}
              </p>
              <div className="mt-4 rounded-lg border border-cyan-300/15 bg-black/10 px-3 py-3">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <p className="text-sm font-medium text-cyan-50">{translateText("Runtime activation gate")}</p>
                    <p className="mt-1 text-xs leading-5 text-cyan-100/70">
                      {translateText("Validated registry patches remain inert until an approved activation draft is executed for a scoped runtime read path.")}
                    </p>
                  </div>
                  <Badge variant={latestActiveActivationId ? "success" : "warning"}>
                    {translateText(latestActiveActivationId ? "Scoped active version" : "Activation required")}
                  </Badge>
                </div>
                <div className="mt-3 grid gap-2 text-xs text-cyan-100/80 sm:grid-cols-2">
                  <span>{translateText("target patch")}: {activationTargetPatch?.registry_patch_id ?? "none"}</span>
                  <span>{translateText("activation events")}: {runtimeActivationState?.activation_event_count ?? 0}</span>
                  <span>{translateText("activation_ready")}: {String(latestRuntimeActivationReadiness?.activation_ready ?? runtimeActivationReadiness?.activation_ready ?? false)}</span>
                  <span>{translateText("runtime defaults mutated")}: {String(runtimeActivationState?.runtime_defaults_mutated ?? false)}</span>
                </div>
                {latestRuntimeActivationDraft ? (
                  <p className="mt-3 rounded-md border border-cyan-300/15 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-100">
                    {translateText("Activation draft")} {latestRuntimeActivationDraft.activation_request_id} / {translateText(latestRuntimeActivationDraft.status)}
                    {latestRuntimeActivationReadiness?.blockers.length ? ` / ${latestRuntimeActivationReadiness.blockers.join(" / ")}` : ""}
                  </p>
                ) : null}
                {latestRuntimeActivationRecord ? (
                  <p className="mt-2 rounded-md border border-cyan-300/15 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-100">
                    {translateText("Activation record")} {latestRuntimeActivationRecord.activation_id} / {translateText(latestRuntimeActivationRecord.predicate)}
                  </p>
                ) : null}
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    loading={runtimeActivationBusyKey === "draft"}
                    disabled={!activationTargetPatch}
                    data-testid="runtime-activation-create-draft"
                    onClick={() => void createRuntimeActivationDraft()}
                  >
                    {translateText("Create activation draft")}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    loading={runtimeActivationBusyKey === "approve"}
                    disabled={!latestRuntimeActivationDraft || latestRuntimeActivationDraft.status !== "pending"}
                    data-testid="runtime-activation-approve-draft"
                    onClick={() => void approveRuntimeActivationDraft()}
                  >
                    {translateText("Approve activation draft")}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    loading={runtimeActivationBusyKey === "readiness"}
                    disabled={!latestRuntimeActivationDraft}
                    data-testid="runtime-activation-check-readiness"
                    onClick={() => void checkRuntimeActivationReadiness()}
                  >
                    {translateText("Check activation readiness")}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    leftIcon={<PlayCircle className="h-4 w-4" />}
                    loading={runtimeActivationBusyKey === "execute"}
                    disabled={!latestRuntimeActivationDraft || latestRuntimeActivationDraft.status !== "approved"}
                    data-testid="runtime-activation-execute"
                    onClick={() => void executeRuntimeActivation()}
                  >
                    {translateText("Execute scoped activation")}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    loading={runtimeActivationBusyKey === "rollback"}
                    disabled={!latestActiveActivationId}
                    data-testid="runtime-activation-rollback"
                    onClick={() => void rollbackRuntimeActivation()}
                  >
                    {translateText("Rollback activation")}
                  </Button>
                </div>
              </div>
            </div>
            {latestBenchmarkCases.length ? (
              <div className="mt-4 space-y-2">
                {latestBenchmarkCases.map((benchmarkCase) => {
                  const threshold = benchmarkCase.expected_metrics?.max_ending_risk;
                  return (
                    <div
                      key={`${latestBenchmarkRun?.benchmark_run_id}-${benchmarkCase.case_id}`}
                      className="rounded-xl border border-white/8 bg-black/10 px-3 py-3"
                    >
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <p className="text-sm font-medium text-white">{benchmarkCase.name}</p>
                          <p className="mt-1 text-xs text-surface-500">{benchmarkCase.case_id}</p>
                        </div>
                        <Badge variant={benchmarkCase.status === "failed" ? "warning" : "success"}>
                          {translateText(benchmarkCase.status)}
                        </Badge>
                      </div>
                      <div className="mt-3 grid gap-2 text-xs text-surface-400 sm:grid-cols-3">
                        <span>
                          {translateText("Ending risk")} {formatNumber(benchmarkCase.metrics?.ending_risk, 2)}
                        </span>
                        <span>
                          {translateText("Threshold")} {typeof threshold === "number" ? formatNumber(threshold, 2) : String(threshold ?? "pending")}
                        </span>
                        <span className="truncate">
                          {translateText("Evidence pack")} {benchmarkCase.evidence_pack_id ?? "pending"}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : null}
          </div>
          <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-surface-200">
                  <Network className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-sm font-medium text-white">{translateText("Knowledge graph links")}</p>
                  <p className="mt-1 text-xs text-surface-500">
                    {models.length} {translateText("models")} / {knowledgeRelations.length} {translateText("relations")}
                  </p>
                </div>
              </div>
              <Badge variant={knowledgeRelations.length ? "success" : "neutral"}>
                {knowledgeRelations.length}
              </Badge>
            </div>
            <div className="mt-4 space-y-3">
              {displayedKnowledgeRelations.map((relation) => (
                <div key={relation.relation_id} className="rounded-xl border border-white/8 bg-black/10 px-3 py-3 text-xs text-surface-300">
                  <p className="font-medium text-white">{relation.subject_type} / {relation.predicate}</p>
                  <p className="mt-1">
                    {relation.subject_type} {"->"} {relation.object_type}
                    {relation.evidence_pack_id ? " -> evidence_pack" : ""}
                  </p>
                  <p className="mt-1 text-surface-500">
                    {relation.subject_id} {"->"} {relation.object_type}:{relation.object_id}
                  </p>
                  <p className="mt-1 text-surface-500">
                    {translateText("Created")} {relation.created_at ? new Date(relation.created_at).toLocaleString() : "pending"}
                  </p>
                  <p className="mt-1 text-surface-500">{translateText("Evidence pack")} {relation.evidence_pack_id ?? "pending"}</p>
                </div>
              ))}
              {!knowledgeRelations.length ? (
                <p className="text-xs leading-6 text-surface-500">
                  {translateText("No model governance knowledge relations have been created yet.")}
                </p>
              ) : null}
            </div>
          </div>
        </div>
      </CockpitPanel>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <CockpitPanel className="p-5 lg:p-6">
          <div>
            <CockpitSectionLabel>{translateText("Release dossier preview")}</CockpitSectionLabel>
            <p className="mt-3 text-sm leading-7 text-surface-300">
              {translateText("Current markdown dossier generated for this candidate.")}
            </p>
          </div>
          <div className="mt-5">
            <pre className="max-h-[34rem] overflow-auto rounded-2xl border border-white/8 bg-surface-950/70 p-4 text-xs leading-6 text-surface-300">
              {readiness.data.report_markdown}
            </pre>
          </div>
        </CockpitPanel>

        <div className="space-y-6">
          <CockpitPanel className="p-5 lg:p-6">
            <div>
              <CockpitSectionLabel>{translateText("Known limitations")}</CockpitSectionLabel>
              <p className="mt-3 text-sm leading-7 text-surface-300">
                {translateText("Items to call out during pilot handoff.")}
              </p>
            </div>
            <div className="mt-5 space-y-3">
              {readiness.data.known_limitations.map((item) => (
                <div key={item} className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-3 text-sm text-surface-300">
                  {translateText(item)}
                </div>
              ))}
            </div>
          </CockpitPanel>

          <CockpitPanel className="p-5 lg:p-6">
            <div>
              <CockpitSectionLabel>{translateText("Release checks")}</CockpitSectionLabel>
              <p className="mt-3 text-sm leading-7 text-surface-300">
                {translateText("Current dossier-backed gate results.")}
              </p>
            </div>
            <div className="mt-5 space-y-3">
              {readiness.data.checks.map((check) => (
                <div key={check.name} className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium text-white">{translateText(check.name)}</p>
                    <span className="text-xs text-surface-400">{translateText(check.status)}</span>
                  </div>
                  <p className="mt-2 text-sm text-surface-400">{translateText(check.summary)}</p>
                </div>
              ))}
            </div>
          </CockpitPanel>

          <CockpitPanel className="p-5 lg:p-6">
            <div>
              <CockpitSectionLabel>{translateText("Quick interpretation")}</CockpitSectionLabel>
              <p className="mt-3 text-sm leading-7 text-surface-300">
                {translateText("How to talk about this candidate to a buyer or pilot stakeholder.")}
              </p>
            </div>
            <div className="mt-5 space-y-3">
              <div className="rounded-2xl border border-emerald-400/15 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4" />
                  <span>{translateText("BOS Code shows live dossier-backed verification and smoke artifacts.")}</span>
                </div>
              </div>
              <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3 text-sm text-surface-300">
                <div className="flex items-center gap-2">
                  <FileStack className="h-4 w-4 text-surface-300" />
                  <span>{translateText("Use the dossier plus artifact links as the canonical release proof for demos and pilot reviews.")}</span>
                </div>
              </div>
            </div>
          </CockpitPanel>
        </div>
      </div>
    </div>
  );
}
