import { useMemo, useState } from "react";
import toast from "react-hot-toast";

import {
  useApproveLiteratureValuePromotionRequest,
  useBioexecutorCandidates,
  useBusinessKnowledgeReviewPacketExport,
  useCreateLiteratureValuePromotionRequest,
  useCreateLiteratureValueRuntimeActivation,
  useExternalSourceProcurementSummary,
  useExternalSourceExtractions,
  useExternalSourceReviewCards,
  useExternalSourceSchemaReadiness,
  useExternalSources,
  useFeedstockCandidates,
  useFeedstockDatasetCandidates,
  useFeedstocksCatalog,
  useLiteratureExtractionCandidateReviewPacketBulkExport,
  useLiteratureExtractionCandidateReviewPacketExport,
  useLiteratureExtractionCandidates,
  useLiteratureExtractionEvidenceChainReadiness,
  useLiteratureValuePromotionAuditExport,
  useLiteratureValuePromotionLifecycle,
  useLiteratureValuePromotionReadiness,
  useLiteratureValueRuntimeActivationPreview,
  usePromoteLiteratureValueRequestToOverlay,
  useRejectLiteratureValuePromotionRequest,
  useRollbackLiteratureValueRuntimeActivation,
  useCreateLiteratureExtractionReviewDraft,
  useLiteratureExtractionReviewDraftComparison,
  useLiteratureExtractionReviewDrafts,
  useManuscriptCampaigns,
  useParseReferenceDocument,
  usePromoteReferenceIngestionItem,
  useReferenceIngestionHealth,
  useReferenceIngestionItems,
  useResolveExternalSourceReviewCard,
  useReviewedExternalCandidateKnowledgeBase,
  useReviewedExternalCandidateActivationPreview,
  useReviewedExternalCandidateRollbackPreview,
  useReviewedExternalCandidateRuntimeReadiness,
  useReviewedExternalCandidateSummary,
  useReviewedExternalCandidates,
  useSpeciesCatalog,
} from "@/hooks/useBos";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import {
  CockpitGrid,
  CockpitMetric,
  CockpitPanel,
  CockpitSectionLabel,
} from "@/components/ui/Cockpit";
import { ErrorState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { SpinnerOverlay } from "@/components/ui/Spinner";
import { Textarea } from "@/components/ui/Textarea";
import {
  buildReviewedCandidateEvidenceSummary,
  formatReviewedCandidateGuardrail,
} from "@/lib/reviewedCandidateEvidence";
import { translateText } from "@/lib/i18n";
import type {
  BioexecutorCandidate,
  BusinessKnowledgeCoverageItem,
  BusinessKnowledgeReviewWorkflow,
  ExternalSourceRecord,
  ExternalSourceReviewAction,
  ExternalSourceReviewCard,
  ExternalSourceReviewCardResolveRequest,
  ExternalSourceSchemaReadinessResponse,
  FeedstockCandidate,
  FeedstockDatasetCandidate,
  LiteratureExtractionCandidate,
  LiteratureExtractionEvidenceChainReadinessResponse,
  LiteratureExtractionCandidateReviewPacketBulkExportResponse,
  LiteratureExtractionReviewDraftComparisonResponse,
  LiteratureExtractionReviewDraftResponse,
  LiteratureValuePromotionAuditExportResponse,
  LiteratureValuePromotionLifecycleResponse,
  LiteratureValuePromotionReadinessResponse,
  ReferenceIngestionStagedItem,
  ReviewedExternalCandidate,
  ReviewedExternalCandidateActivationPreviewResponse,
  ReviewedExternalCandidateKnowledgeBaseResponse,
  ReviewedExternalCandidateRollbackPreviewResponse,
  ReviewedExternalCandidateRuntimeReadinessResponse,
} from "@/types/bos";

type DomainGroupKey = "bsf" | "feedstock" | "lca" | "tea" | "compliance" | "agronomy" | "model" | "oss";

interface DomainGroupConfig {
  key: DomainGroupKey;
  label: string;
  candidateDomains: string[];
  sourcePrefixes: string[];
  fallbackCandidateType: string;
}

export interface DomainCandidateCardModel {
  id: string;
  domain: DomainGroupKey;
  title: string;
  subtitle: string;
  lane: string;
  candidateType: string;
  reviewStatus: string;
  licenseStatus: string;
  allowedUse: string;
  blockedUse: string;
  humanReviewRequired: boolean;
  promotionEnabled: boolean;
  runtimeActivated: boolean;
  validatedDefaultWriteEnabled: boolean;
  sourceKind: string;
  sourceRef: string;
  note?: string;
  reviewWorkflow?: BusinessKnowledgeReviewWorkflow | null;
  reviewPacketExportItemKey?: string;
  reviewPacketExportCandidateId?: string;
  reviewDraft?: LiteratureExtractionReviewDraftResponse | null;
}

const DOMAIN_GROUPS: DomainGroupConfig[] = [
  {
    key: "bsf",
    label: "BSF",
    candidateDomains: ["bsf_metadata", "species_metadata"],
    sourcePrefixes: ["A-BSF"],
    fallbackCandidateType: "bsf_reviewed_metadata_candidate",
  },
  {
    key: "feedstock",
    label: "Feedstock",
    candidateDomains: ["feedstock_metadata"],
    sourcePrefixes: ["B-FEED"],
    fallbackCandidateType: "feedstock_metadata_candidate",
  },
  {
    key: "lca",
    label: "LCA",
    candidateDomains: ["lca"],
    sourcePrefixes: ["C-LCA"],
    fallbackCandidateType: "lca_boundary_metadata_candidate",
  },
  {
    key: "tea",
    label: "TEA",
    candidateDomains: ["tea"],
    sourcePrefixes: ["D-TEA"],
    fallbackCandidateType: "tea_factor_candidate",
  },
  {
    key: "compliance",
    label: "Compliance",
    candidateDomains: ["compliance"],
    sourcePrefixes: ["E-COMP"],
    fallbackCandidateType: "compliance_rule_candidate",
  },
  {
    key: "agronomy",
    label: "Agronomy",
    candidateDomains: [],
    sourcePrefixes: [],
    fallbackCandidateType: "release_gate_candidate",
  },
  {
    key: "model",
    label: "Model",
    candidateDomains: ["model_provider"],
    sourcePrefixes: ["F-MODEL"],
    fallbackCandidateType: "model_provider_capability_candidate",
  },
  {
    key: "oss",
    label: "OSS",
    candidateDomains: ["github_reference"],
    sourcePrefixes: ["G-OSS"],
    fallbackCandidateType: "github_reference_candidate",
  },
];

function asText(value: unknown, fallback: string): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function asBoolean(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function rawText(raw: Record<string, unknown> | undefined, keys: string[], fallback: string): string {
  for (const key of keys) {
    const value = raw?.[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return fallback;
}

function domainForSourceId(sourceId: string): DomainGroupKey | undefined {
  return DOMAIN_GROUPS.find((group) =>
    group.sourcePrefixes.some((prefix) => sourceId.startsWith(prefix)),
  )?.key;
}

function domainForReviewedCandidate(candidate: ReviewedExternalCandidate): DomainGroupKey | undefined {
  const domain = candidate.candidate_domain;
  return DOMAIN_GROUPS.find((group) => domain ? group.candidateDomains.includes(domain) : false)?.key;
}

function configForDomain(domain: DomainGroupKey): DomainGroupConfig {
  return DOMAIN_GROUPS.find((group) => group.key === domain) ?? DOMAIN_GROUPS[0]!;
}

function parseUnitsJson(value: string): Record<string, string> | undefined {
  const trimmed = value.trim();
  if (!trimmed) return undefined;

  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return undefined;
    return Object.fromEntries(
      Object.entries(parsed).map(([key, unit]) => [key, String(unit)]),
    );
  } catch {
    return undefined;
  }
}

function buildBioexecutorSeedCard(item: BioexecutorCandidate): DomainCandidateCardModel {
  return {
    id: `bioexecutor-${item.code}`,
    domain: "bsf",
    title: `${item.code} / ${item.common_name}`,
    subtitle: item.scientific_name,
    lane: "Candidate seeds",
    candidateType: "species_metadata_candidate",
    reviewStatus: item.review_status,
    licenseStatus: "pending_review",
    allowedUse: "candidate metadata review only",
    blockedUse: "no runtime activation; no release evidence; no validated defaults",
    humanReviewRequired: item.human_review_required,
    promotionEnabled: false,
    runtimeActivated: false,
    validatedDefaultWriteEnabled: false,
    sourceKind: item.source_kind,
    sourceRef: item.source_ref,
    note: item.notes,
  };
}

function buildFeedstockSeedCard(item: FeedstockCandidate): DomainCandidateCardModel {
  return {
    id: `feedstock-${item.key}`,
    domain: "feedstock",
    title: item.display_name,
    subtitle: item.category,
    lane: "Candidate seeds",
    candidateType: "feedstock_metadata_candidate",
    reviewStatus: item.review_status,
    licenseStatus: "pending_review",
    allowedUse: "candidate metadata review only",
    blockedUse: "no runtime activation; no release evidence; no validated feedstock defaults",
    humanReviewRequired: item.human_review_required,
    promotionEnabled: false,
    runtimeActivated: false,
    validatedDefaultWriteEnabled: false,
    sourceKind: item.source_kind,
    sourceRef: item.source_ref,
    note: item.suitability_notes,
  };
}

function buildFeedstockDatasetCard(item: FeedstockDatasetCandidate): DomainCandidateCardModel {
  return {
    id: item.candidate_uid,
    domain: "feedstock",
    title: item.source_id,
    subtitle: item.source_name,
    lane: "Feedstock public dataset candidates",
    candidateType: item.candidate_type,
    reviewStatus: item.review_status,
    licenseStatus: "pending_review",
    allowedUse: "source metadata and mapping review only",
    blockedUse: "no composition defaults; no release evidence; no runtime activation",
    humanReviewRequired: item.human_review_required,
    promotionEnabled: false,
    runtimeActivated: item.runtime_activated,
    validatedDefaultWriteEnabled: item.validated_default_write_enabled,
    sourceKind: item.source_kind,
    sourceRef: item.source_ref,
    note: item.waste_proxy_warning,
  };
}

const AGRONOMY_OUTPUT_KEYS = new Set(["germination_rate", "germination_index", "phytotoxicity"]);

function buildAgronomyOutputCandidateCard(item: BusinessKnowledgeCoverageItem): DomainCandidateCardModel {
  return {
    id: `agronomy-${item.item_key}`,
    domain: "agronomy",
    title: item.label,
    subtitle: item.coverage_basis,
    lane: "Agronomy output candidates",
    candidateType: "release_gate_candidate",
    reviewStatus: item.status,
    licenseStatus: "metadata_only",
    allowedUse: "Reference Atlas read-only agronomy output metadata",
    blockedUse: "no validated defaults; no release evidence; no runtime activation; no numeric thresholds",
    humanReviewRequired: item.review_gated,
    promotionEnabled: false,
    runtimeActivated: item.runtime_activation_enabled,
    validatedDefaultWriteEnabled: item.validated_default_write_enabled,
    sourceKind: item.coverage_basis,
    sourceRef: item.evidence_refs[0] ?? "external_knowledge_candidates",
    note: item.notes,
    reviewWorkflow: item.review_workflow,
    reviewPacketExportItemKey: item.item_key,
  };
}

function buildLiteratureExtractionCandidateCard(
  item: LiteratureExtractionCandidate,
  reviewDraft?: LiteratureExtractionReviewDraftResponse,
): DomainCandidateCardModel {
  return {
    id: item.candidate_uid,
    domain: "agronomy",
    title: `${item.metric_label}: ${item.raw_value} ${item.unit}`,
    subtitle: item.title,
    lane: "Literature extraction candidates",
    candidateType: item.candidate_type,
    reviewStatus: item.review_status,
    licenseStatus: "pending_review",
    allowedUse: "raw literature extraction candidate for human review only",
    blockedUse: "no validated defaults; no release evidence; no runtime activation; no promotion",
    humanReviewRequired: item.human_review_required,
    promotionEnabled: item.promotion_enabled,
    runtimeActivated: item.runtime_activation_enabled,
    validatedDefaultWriteEnabled: item.validated_default_write_enabled,
    sourceKind: item.source_kind,
    sourceRef: item.source_ref,
    note: `numeric candidate only; ${item.feedstock} / ${item.treatment} / ${item.condition_context}`,
    reviewPacketExportCandidateId: item.candidate_id,
    reviewDraft,
  };
}

function buildSourceCatalogCard(source: ExternalSourceRecord): DomainCandidateCardModel | undefined {
  const domain = domainForSourceId(source.source_id);
  if (!domain) return undefined;

  const config = configForDomain(domain);
  const raw = source.raw_payload;
  return {
    id: `source-${source.source_id}`,
    domain,
    title: source.source_id,
    subtitle: source.source_name,
    lane: "Reviewed metadata source catalog",
    candidateType: rawText(raw, ["candidate_type"], config.fallbackCandidateType),
    reviewStatus: rawText(raw, ["review_status"], "pending_review"),
    licenseStatus: rawText(raw, ["license_status"], "pending_review"),
    allowedUse: rawText(raw, ["allowed_use"], "metadata discovery and reviewer triage only"),
    blockedUse: rawText(raw, ["blocked_use"], "no runtime activation; no release evidence; no validated defaults"),
    humanReviewRequired: asBoolean(raw?.human_review_required, true),
    promotionEnabled: false,
    runtimeActivated: false,
    validatedDefaultWriteEnabled: false,
    sourceKind: source.evidence_source_kind,
    sourceRef: rawText(raw, ["source_ref", "doi", "source_url"], source.source_id),
    note: source.next_action ?? source.human_review_note ?? source.license_note ?? undefined,
  };
}

function buildReviewedExternalCard(candidate: ReviewedExternalCandidate): DomainCandidateCardModel {
  const payload = candidate.candidate_payload as Record<string, unknown>;
  const domain = domainForReviewedCandidate(candidate) ?? domainForSourceId(candidate.source_id) ?? "bsf";
  return {
    id: candidate.candidate_id,
    domain,
    title: candidate.candidate_id,
    subtitle: candidate.candidate_key,
    lane: "Reviewed external",
    candidateType: candidate.candidate_type,
    reviewStatus: candidate.review_status,
    licenseStatus: candidate.license_status,
    allowedUse: candidate.allowed_use,
    blockedUse: candidate.blocked_use,
    humanReviewRequired: candidate.human_review_required,
    promotionEnabled: candidate.promotion_enabled,
    runtimeActivated: candidate.runtime_activated,
    validatedDefaultWriteEnabled: candidate.validated_default_write_enabled,
    sourceKind: candidate.source_kind,
    sourceRef: candidate.source_ref,
    note: asText(payload.title, candidate.boundary_condition),
  };
}

function groupDomainCandidateCards(cards: DomainCandidateCardModel[]): Record<DomainGroupKey, DomainCandidateCardModel[]> {
  return DOMAIN_GROUPS.reduce(
    (acc, group) => {
      acc[group.key] = cards.filter((card) => card.domain === group.key);
      return acc;
    },
    {} as Record<DomainGroupKey, DomainCandidateCardModel[]>,
  );
}

export default function BOSReferenceAtlasPage() {
  const [view, setView] = useState<"species" | "feedstocks" | "candidate-seeds" | "reviewed-external" | "campaigns" | "staged-ingestion">("species");
  const speciesCatalog = useSpeciesCatalog();
  const bioexecutorCandidates = useBioexecutorCandidates();
  const feedstocksCatalog = useFeedstocksCatalog();
  const feedstockCandidates = useFeedstockCandidates();
  const feedstockDatasetCandidates = useFeedstockDatasetCandidates();
  const literatureExtractionCandidates = useLiteratureExtractionCandidates();
  const literatureExtractionBulkExport = useLiteratureExtractionCandidateReviewPacketBulkExport(
    view === "candidate-seeds" && (literatureExtractionCandidates.data?.count ?? 0) > 0,
  );
  const literatureEvidenceChainReadiness = useLiteratureExtractionEvidenceChainReadiness(view === "candidate-seeds");
  const literatureReviewDrafts = useLiteratureExtractionReviewDrafts();
  const externalSources = useExternalSources();
  const externalSourceSummary = useExternalSourceProcurementSummary();
  const externalSourceSchemaReadiness = useExternalSourceSchemaReadiness();
  const externalReviewCards = useExternalSourceReviewCards();
  const externalExtractions = useExternalSourceExtractions();
  const reviewedExternalCandidates = useReviewedExternalCandidates();
  const reviewedExternalSummary = useReviewedExternalCandidateSummary();
  const reviewedExternalKnowledgeBase = useReviewedExternalCandidateKnowledgeBase();
  const resolveReviewCard = useResolveExternalSourceReviewCard();
  const manuscriptCampaigns = useManuscriptCampaigns();
  const referenceIngestion = useReferenceIngestionItems();
  const referenceIngestionHealth = useReferenceIngestionHealth();
  const parseReferenceDocument = useParseReferenceDocument();
  const promoteReference = usePromoteReferenceIngestionItem();
  const [sourceTitle, setSourceTitle] = useState("");
  const [sourceOwner, setSourceOwner] = useState("");
  const [licenseNote, setLicenseNote] = useState("");
  const [sourceRegion, setSourceRegion] = useState("");
  const [unitsJson, setUnitsJson] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const isLoading =
    speciesCatalog.isLoading ||
    bioexecutorCandidates.isLoading ||
    feedstocksCatalog.isLoading ||
    feedstockCandidates.isLoading ||
    feedstockDatasetCandidates.isLoading ||
    literatureExtractionCandidates.isLoading ||
    manuscriptCampaigns.isLoading;
  const isError =
    speciesCatalog.isError ||
    bioexecutorCandidates.isError ||
    feedstocksCatalog.isError ||
    feedstockCandidates.isError ||
    feedstockDatasetCandidates.isError ||
    literatureExtractionCandidates.isError ||
    manuscriptCampaigns.isError;

  const counts = useMemo(
    () => ({
      species: speciesCatalog.data?.count ?? 0,
      feedstocks: feedstocksCatalog.data?.count ?? 0,
      candidates: (bioexecutorCandidates.data?.count ?? 0) + (feedstockCandidates.data?.count ?? 0),
      feedstockDatasetCandidates: feedstockDatasetCandidates.data?.count ?? 0,
      literatureExtractionCandidates: literatureExtractionCandidates.data?.count ?? 0,
      reviewedExternal: reviewedExternalCandidates.data?.count ?? 0,
      reviewedMetadata: reviewedExternalSummary.data?.reviewed_metadata_candidate_count ?? 0,
      releaseEvidenceBlocked: reviewedExternalSummary.data?.release_evidence_blocked_count ?? 0,
      reviewCards: externalReviewCards.data?.count ?? 0,
      campaigns: manuscriptCampaigns.data?.count ?? 0,
      staged: referenceIngestion.data?.count ?? 0,
      sourceReviewRequired: externalSourceSummary.data?.review_required_count ?? 0,
    }),
    [
      speciesCatalog.data,
      bioexecutorCandidates.data,
      feedstocksCatalog.data,
      feedstockCandidates.data,
      feedstockDatasetCandidates.data,
      literatureExtractionCandidates.data,
      reviewedExternalCandidates.data,
      reviewedExternalSummary.data,
      externalReviewCards.data,
      manuscriptCampaigns.data,
      referenceIngestion.data,
      externalSourceSummary.data,
    ],
  );

  const domainCandidateCards = useMemo(() => {
    const sourceCards = (externalSources.data?.items ?? [])
      .map(buildSourceCatalogCard)
      .filter((card): card is DomainCandidateCardModel => Boolean(card));
    const agronomyOutputCards = (reviewedExternalKnowledgeBase.data?.business_knowledge_coverage_groups ?? [])
      .find((group) => group.group_key === "product_agronomy_outputs")
      ?.items.filter((item) => AGRONOMY_OUTPUT_KEYS.has(item.item_key) && item.status === "candidate_read_model")
      .map(buildAgronomyOutputCandidateCard) ?? [];
    const literatureReviewDraftByCandidate = new Map(
      (literatureReviewDrafts.data?.drafts ?? []).map((draft) => [draft.candidate_id, draft]),
    );

    return [
      ...(bioexecutorCandidates.data?.candidates ?? []).map(buildBioexecutorSeedCard),
      ...(feedstockCandidates.data?.candidates ?? []).map(buildFeedstockSeedCard),
      ...(feedstockDatasetCandidates.data?.items ?? []).map(buildFeedstockDatasetCard),
      ...(literatureExtractionCandidates.data?.items ?? []).map((item) =>
        buildLiteratureExtractionCandidateCard(item, literatureReviewDraftByCandidate.get(item.candidate_id)),
      ),
      ...agronomyOutputCards,
      ...sourceCards,
      ...(reviewedExternalCandidates.data?.items ?? []).map(buildReviewedExternalCard),
    ];
  }, [
    bioexecutorCandidates.data,
    feedstockCandidates.data,
    feedstockDatasetCandidates.data,
    literatureExtractionCandidates.data,
    literatureReviewDrafts.data,
    reviewedExternalKnowledgeBase.data,
    externalSources.data,
    reviewedExternalCandidates.data,
  ]);
  const reviewedCandidateCardIds = useMemo(
    () => new Set((reviewedExternalCandidates.data?.items ?? []).map((candidate) => candidate.card_id)),
    [reviewedExternalCandidates.data],
  );

  if (isLoading) return <SpinnerOverlay label={translateText("Loading BOS reference atlas")} />;
  if (isError) return <ErrorState onRetry={() => {
    void speciesCatalog.refetch();
    void bioexecutorCandidates.refetch();
    void feedstocksCatalog.refetch();
    void feedstockCandidates.refetch();
    void feedstockDatasetCandidates.refetch();
    void manuscriptCampaigns.refetch();
  }} />;

  return (
    <div className="assistant-ambient-shell space-y-6">
      <CockpitPanel tone="hero" className="p-6 lg:p-7">
        <div className="flex flex-col gap-6">
          <div className="max-w-3xl">
            <CockpitSectionLabel>{translateText("BOS / Reference Atlas")}</CockpitSectionLabel>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.65rem]">
              {translateText("Species, feedstocks, and manuscript-backed evidence")}
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-surface-300">
              {translateText("A dedicated reference surface for BOS defaults, feedstock posture, and experimentally grounded campaign evidence.")}
            </p>
          </div>

          <CockpitGrid className="md:grid-cols-2 xl:grid-cols-6">
            <CockpitMetric label="Species" value={String(counts.species)} hint="Reference insect profiles" accent="cyan" />
            <CockpitMetric label="Feedstocks" value={String(counts.feedstocks)} hint="Substrate and contamination posture" accent="amber" />
            <CockpitMetric
              label="Candidates"
              value={String(counts.candidates + counts.feedstockDatasetCandidates + counts.literatureExtractionCandidates)}
              hint={`${counts.feedstockDatasetCandidates} public dataset candidates / ${counts.literatureExtractionCandidates} literature value candidates`}
              accent="amber"
            />
            <CockpitMetric label="Reviewed" value={String(counts.reviewedExternal)} hint={`${counts.reviewedMetadata} metadata lane / ${counts.reviewCards} review cards`} accent="cyan" />
            <CockpitMetric label="Campaigns" value={String(counts.campaigns)} hint="Manuscript-backed evidence slices" accent="violet" />
            <CockpitMetric label="Staged" value={String(counts.staged)} hint="Parsed documents awaiting review" accent="cyan" />
          </CockpitGrid>
        </div>
      </CockpitPanel>

      <CockpitPanel className="p-5 lg:p-6">
        <div className="space-y-4">
          <div>
            <CockpitSectionLabel>{translateText("Reference scope")}</CockpitSectionLabel>
            <p className="mt-3 text-sm leading-7 text-surface-300">
              {translateText("Switch between insect profiles, substrate defaults, and campaign evidence without leaving BOS.")}
            </p>
          </div>
          <Select
            options={[
              { value: "species", label: "Species" },
              { value: "feedstocks", label: "Feedstocks" },
              { value: "candidate-seeds", label: "Candidate seeds" },
              { value: "reviewed-external", label: "Reviewed external" },
              { value: "campaigns", label: "Campaigns" },
              { value: "staged-ingestion", label: "Staged ingestion" },
            ]}
            value={view}
            onChange={(event) => setView(event.target.value as typeof view)}
          />
        </div>
      </CockpitPanel>

      {view === "candidate-seeds" || view === "reviewed-external" ? (
        <ExternalSourceSchemaReadinessStrip
          readiness={externalSourceSchemaReadiness.data}
          isLoading={externalSourceSchemaReadiness.isLoading}
          isError={externalSourceSchemaReadiness.isError}
        />
      ) : null}

      {view === "species" ? (
        <div className="grid gap-6 xl:grid-cols-2">
          {(speciesCatalog.data?.species ?? []).map((item) => (
            <Card key={item.code} className="assistant-aside-card rounded-[28px]">
              <CardHeader
                title={`${item.code} / ${item.common_name}`}
                description={item.scientific_name}
              />
              <CardBody className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="info">{item.source_basis}</Badge>
                  {item.aliases.map((alias) => (
                    <Badge key={alias} variant="neutral">{alias}</Badge>
                  ))}
                </div>
                <p className="text-sm leading-6 text-surface-300">{item.notes}</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  <MiniInfo label="Development days" value={String(item.development_days)} />
                  <MiniInfo label="SER typical" value={String(item.ser_typical)} />
                  <MiniInfo label="Protein (%)" value={String(item.protein_content)} />
                  <MiniInfo label="Fat (%)" value={String(item.fat_content)} />
                </div>
                <div className="space-y-2">
                  <p className="assistant-section-kicker">References</p>
                  {item.references.map((ref) => (
                    <div key={ref} className="rounded-2xl border border-white/8 bg-white/5 px-3 py-3 text-sm text-surface-200">
                      {ref}
                    </div>
                  ))}
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      ) : null}

      {view === "feedstocks" ? (
        <div className="grid gap-6 xl:grid-cols-2">
          {(feedstocksCatalog.data?.feedstocks ?? []).map((item) => (
            <Card key={item.key} className="assistant-aside-card rounded-[28px]">
              <CardHeader
                title={item.display_name}
                description={item.category}
              />
              <CardBody className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  <Badge variant={item.contamination_risk === "critical" ? "danger" : item.contamination_risk === "high" ? "warning" : "success"}>
                    {item.contamination_risk}
                  </Badge>
                  <Badge variant="info">{item.lignocellulose_severity}</Badge>
                  <Badge variant="neutral">{item.moisture_risk}</Badge>
                </div>
                <p className="text-sm leading-6 text-surface-300">{item.suitability_notes}</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  <MiniInfo label="Typical C/N min" value={String(item.typical_cn_min ?? "N/A")} />
                  <MiniInfo label="Typical C/N max" value={String(item.typical_cn_max ?? "N/A")} />
                </div>
                <div className="space-y-2">
                  <p className="assistant-section-kicker">References</p>
                  {item.references.map((ref) => (
                    <div key={ref} className="rounded-2xl border border-white/8 bg-white/5 px-3 py-3 text-sm text-surface-200">
                      {ref}
                    </div>
                  ))}
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      ) : null}

      {view === "candidate-seeds" ? (
        <DomainCandidateGroups
          cards={domainCandidateCards}
          readiness={externalSourceSchemaReadiness.data}
          knowledgeBase={reviewedExternalKnowledgeBase.data}
          feedstockGuardrails={feedstockDatasetCandidates.data?.guardrails ?? []}
          literatureBulkExport={literatureExtractionBulkExport.data}
          literatureEvidenceChainReadiness={literatureEvidenceChainReadiness.data}
        />
      ) : null}

      {view === "reviewed-external" ? (
        <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <Card className="assistant-aside-card rounded-[28px]">
            <CardHeader
              title="Reviewed metadata lane"
              description="DB-backed reviewed candidates approved as metadata context only; runtime activation remains a separate future gate."
            />
            <CardBody className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-3">
                <MiniInfo label="Source rows" value={String(externalSources.data?.count ?? 0)} />
                <MiniInfo label="Review cards" value={String(externalReviewCards.data?.count ?? 0)} />
                <MiniInfo label="Extractions" value={String(externalExtractions.data?.count ?? 0)} />
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <MiniInfo label="Procurement sources" value={String(externalSourceSummary.data?.source_count ?? 0)} />
                <MiniInfo label="Review required" value={String(counts.sourceReviewRequired)} />
                <MiniInfo label="Metadata only" value={String(externalSourceSummary.data?.metadata_only_count ?? 0)} />
                <MiniInfo label="Manual review first" value={String(externalSourceSummary.data?.manual_review_first_count ?? 0)} />
                <MiniInfo label="Other ingestion modes" value={String(externalSourceSummary.data?.other_ingestion_mode_count ?? 0)} />
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <MiniInfo label="Metadata reviewed" value={String(reviewedExternalSummary.data?.reviewed_metadata_candidate_count ?? 0)} />
                <MiniInfo label="Pending activation" value={String(reviewedExternalSummary.data?.pending_runtime_activation_count ?? 0)} />
                <MiniInfo label="Numeric value candidates" value={String(reviewedExternalSummary.data?.numeric_value_candidate_count ?? 0)} />
                <MiniInfo label="Default writes enabled" value={String(reviewedExternalSummary.data?.validated_default_write_enabled_count ?? 0)} />
                <MiniInfo label="Release evidence blocked" value={String(counts.releaseEvidenceBlocked)} />
                <MiniInfo label="Domain groups" value={Object.keys(reviewedExternalSummary.data?.candidate_domains ?? {}).join(", ") || "none"} />
                <MiniInfo label="Knowledge base status" value={reviewedExternalKnowledgeBase.data?.status ?? "checking"} />
                <MiniInfo label="Domain metadata ready" value={String(reviewedExternalKnowledgeBase.data?.phase4a_domain_metadata_ready ?? false)} />
                <MiniInfo
                  label="Source metadata coverage"
                  value={`${String(reviewedExternalKnowledgeBase.data?.source_metadata_coverage_percent ?? 0)}%`}
                />
                <MiniInfo
                  label="Business knowledge coverage"
                  value={`${String(reviewedExternalKnowledgeBase.data?.business_knowledge_coverage_percent ?? 0)}%`}
                />
              </div>

              {reviewedExternalKnowledgeBase.data?.knowledge_coverage_domains?.length ? (
                <div className="rounded-2xl border border-emerald-300/15 bg-emerald-400/8 px-3 py-3">
                  <p className="assistant-section-kicker">{translateText("Source metadata family coverage")}</p>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    {reviewedExternalKnowledgeBase.data.knowledge_coverage_domains.map((domain) => (
                      <MiniInfo
                        key={domain.domain_key}
                        label={domain.label}
                        value={`${domain.covered_source_count}/${domain.expected_source_count} sources · ${domain.status}`}
                      />
                    ))}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Badge variant={reviewedExternalKnowledgeBase.data.knowledge_coverage_ready ? "success" : "warning"}>
                      {translateText(`knowledge_coverage_ready: ${String(reviewedExternalKnowledgeBase.data.knowledge_coverage_ready)}`)}
                    </Badge>
                    <Badge variant="neutral">{translateText("review-gated metadata only")}</Badge>
                    <Badge variant="neutral">{translateText("runtime activation disabled")}</Badge>
                    <Badge variant="neutral">{translateText("validated default writes disabled")}</Badge>
                  </div>
                </div>
              ) : null}

              {reviewedExternalKnowledgeBase.data?.business_knowledge_coverage_groups?.length ? (
                <div className="rounded-2xl border border-amber-300/15 bg-amber-400/8 px-3 py-3">
                  <p className="assistant-section-kicker">{translateText("Business knowledge coverage")}</p>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    {reviewedExternalKnowledgeBase.data.business_knowledge_coverage_groups.map((group) => (
                      <MiniInfo
                        key={group.group_key}
                        label={group.label}
                        value={`${group.covered_item_count}/${group.expected_item_count} items - ${group.coverage_percent}% - ${group.status}`}
                      />
                    ))}
                  </div>
                  <div className="mt-3 grid gap-2 md:grid-cols-2">
                    {reviewedExternalKnowledgeBase.data.business_knowledge_coverage_groups.flatMap((group) =>
                      group.items
                        .filter((item) => item.status !== "validated_read_model")
                        .map((item) => (
                          <div key={`${group.group_key}:${item.item_key}`} className="rounded-xl border border-white/8 bg-black/15 px-3 py-2">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="text-sm font-semibold text-surface-100">{translateText(item.label)}</span>
                              <Badge variant={item.status === "candidate_needed" || item.status === "missing" ? "warning" : "neutral"}>
                                {translateText(item.status)}
                              </Badge>
                            </div>
                            <p className="mt-1 text-xs leading-5 text-surface-300">{translateText(item.notes)}</p>
                          </div>
                        )),
                    )}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Badge variant="warning">{translateText("business_knowledge_coverage_is_not_source_metadata_coverage")}</Badge>
                    <Badge variant="neutral">{translateText("MW/PB/feedstocks counted separately")}</Badge>
                    <Badge variant="neutral">{translateText("germination/GI/phytotoxicity candidates are review-gated")}</Badge>
                    <Badge variant="neutral">{translateText("no numeric extraction")}</Badge>
                  </div>
                </div>
              ) : null}

              {externalSourceSummary.data ? (
                <div className="rounded-2xl border border-white/8 bg-white/5 px-3 py-3">
                  <p className="assistant-section-kicker">{translateText("Procurement guardrails")}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {externalSourceSummary.data.guardrails.map((guardrail) => (
                      <Badge key={guardrail} variant="neutral">{translateText(guardrail)}</Badge>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="rounded-2xl border border-white/8 bg-white/5 px-3 py-3">
                <p className="assistant-section-kicker">{translateText("Source catalog preview")}</p>
                <div className="mt-3 space-y-3">
                  {(externalSources.data?.items ?? []).slice(0, 6).map((source) => (
                    <ExternalSourcePreviewItem key={source.source_id} source={source} />
                  ))}
                  {(externalSources.data?.items ?? []).length === 0 ? (
                    <p className="text-sm text-surface-400">
                      {translateText("No external source catalog rows are loaded yet. Seed P0 sources before review-card resolution.")}
                    </p>
                  ) : null}
                </div>
              </div>

              <div className="rounded-2xl border border-cyan-300/15 bg-cyan-400/8 px-3 py-3 text-xs leading-5 text-cyan-100">
                {translateText("This lane exposes DOI, article type, method boundary, license, allowed use, and blocked use for review. Numeric values, release evidence use, validated-default writes, and runtime activation stay blocked.")}
              </div>

              {reviewedExternalCandidates.isLoading ? (
                <p className="text-sm text-surface-400">{translateText("Loading reviewed candidates...")}</p>
              ) : reviewedExternalCandidates.isError ? (
                <p className="text-sm text-red-300">{translateText("Failed to load reviewed external candidates.")}</p>
              ) : (reviewedExternalCandidates.data?.items ?? []).length ? (
                <div className="space-y-4">
                  {(reviewedExternalCandidates.data?.items ?? []).map((candidate, index) => (
                    <ReviewedExternalCandidateCard
                      key={candidate.candidate_id}
                      candidate={candidate}
                      evidencePanelsEnabled={index === 0}
                    />
                  ))}
                </div>
              ) : (
                <p className="text-sm text-surface-400">
                  {translateText("No reviewed external candidates yet. Resolve review cards first; activation remains a later workflow.")}
                </p>
              )}
            </CardBody>
          </Card>

          <Card className="assistant-aside-card rounded-[28px]">
            <CardHeader
              title="Review-card queue"
              description="P0 reviewer-owned cards and extraction shells. Numeric values remain blocked in this lane."
            />
            <CardBody className="space-y-4">
              {externalReviewCards.isLoading ? (
                <p className="text-sm text-surface-400">{translateText("Loading review cards...")}</p>
              ) : externalReviewCards.isError ? (
                <p className="text-sm text-red-300">{translateText("Failed to load external review cards.")}</p>
              ) : (externalReviewCards.data?.items ?? []).length ? (
                <div className="space-y-3">
                  {(externalReviewCards.data?.items ?? []).map((card) => (
                    <ExternalReviewCardQueueItem
                      key={card.card_id}
                      card={card}
                      candidateGenerated={reviewedCandidateCardIds.has(card.card_id)}
                      isResolving={resolveReviewCard.isPending}
                      onResolve={(payload) => resolveReviewCard.mutate({ cardId: card.card_id, payload })}
                    />
                  ))}
                </div>
              ) : (
                <p className="text-sm text-surface-400">
                  {translateText("No external review cards have been seeded into this tenant yet.")}
                </p>
              )}

              <div className="rounded-2xl border border-white/8 bg-white/5 px-3 py-3">
                <p className="assistant-section-kicker">{translateText("Extraction guardrails")}</p>
                <p className="mt-2 text-sm leading-6 text-surface-300">
                  {translateText(
                    `${externalExtractions.data?.count ?? 0} staged extraction records; numeric values are excluded until a reviewer-approved candidate contract permits them.`,
                  )}
                </p>
              </div>
            </CardBody>
          </Card>
        </div>
      ) : null}

      {view === "campaigns" ? (
        <div className="grid gap-6 xl:grid-cols-2">
          {(manuscriptCampaigns.data?.campaigns ?? []).map((item) => (
            <Card key={item.key} className="assistant-aside-card rounded-[28px]">
              <CardHeader title={item.title} description={item.source_anchor} />
              <CardBody className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="brand">{item.evidence_level}</Badge>
                  <Badge variant="neutral">{item.campaign_type}</Badge>
                  {item.species_chain.map((sp) => (
                    <Badge key={sp} variant="info">{sp}</Badge>
                  ))}
                </div>
                <p className="text-sm leading-6 text-surface-300">{item.summary}</p>
                <div className="space-y-2">
                  <p className="assistant-section-kicker">References</p>
                  {item.references.map((ref) => (
                    <div key={ref} className="rounded-2xl border border-white/8 bg-white/5 px-3 py-3 text-sm text-surface-200">
                      {ref}
                    </div>
                  ))}
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      ) : null}

      {view === "staged-ingestion" ? (
        <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
          <Card className="assistant-aside-card rounded-[28px]">
            <CardHeader
              title="Parse PDF into staging"
              description="Phase 1 stores parsed output in staging only. Promotion is explicit and campaign-only."
            />
            <CardBody className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <MiniInfo
                  label="Parser"
                  value={
                    referenceIngestionHealth.data?.parser_available
                      ? `${referenceIngestionHealth.data.parser_name} ready`
                      : `${referenceIngestionHealth.data?.parser_name ?? "mineru"} fallback`
                  }
                />
                <MiniInfo
                  label="Rollback mode"
                  value={referenceIngestionHealth.data?.rollback_mode ?? "checking"}
                />
              </div>
              {referenceIngestionHealth.data?.promotion_enabled === false ? (
                <div className="rounded-2xl border border-amber-300/15 bg-amber-400/8 px-3 py-3 text-xs leading-5 text-amber-100">
                  {translateText("Promotion is disabled. Staging review remains available for rollback-safe inspection.")}
                </div>
              ) : null}
              <Input
                label="Source title"
                placeholder="Core relay manuscript PDF"
                value={sourceTitle}
                onChange={(event) => setSourceTitle(event.target.value)}
              />
              <div className="grid gap-3 sm:grid-cols-2">
                <Input
                  label="Source owner"
                  placeholder="EPA / Journal / Supplier"
                  value={sourceOwner}
                  onChange={(event) => setSourceOwner(event.target.value)}
                />
                <Input
                  label="Region"
                  placeholder="US / EU / CN / Global"
                  value={sourceRegion}
                  onChange={(event) => setSourceRegion(event.target.value)}
                />
              </div>
              <Input
                label="License note"
                placeholder="Review source license before customer-facing use"
                value={licenseNote}
                onChange={(event) => setLicenseNote(event.target.value)}
              />
              <Input
                label="Units JSON"
                placeholder='{"cn_ratio":"dimensionless","moisture":"% wet basis"}'
                value={unitsJson}
                onChange={(event) => setUnitsJson(event.target.value)}
              />
              <Input
                label="PDF file"
                type="file"
                accept="application/pdf,.pdf"
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null;
                  setSelectedFile(file);
                  if (file && !sourceTitle) {
                    setSourceTitle(file.name.replace(/\.pdf$/i, ""));
                  }
                }}
              />
              <Button
                type="button"
                disabled={!selectedFile}
                loading={parseReferenceDocument.isPending}
                onClick={() => {
                  if (!selectedFile) return;
                  parseReferenceDocument.mutate({
                    file: selectedFile,
                    source_title: sourceTitle || selectedFile.name.replace(/\.pdf$/i, ""),
                    source_type: "pdf",
                    source_owner: sourceOwner || undefined,
                    license_note: licenseNote || undefined,
                    region: sourceRegion || undefined,
                    units: parseUnitsJson(unitsJson),
                    ingestion_mode: "manual_review_first",
                    human_review_required: true,
                  });
                }}
              >
                Parse into staging
              </Button>
              <p className="text-xs leading-5 text-surface-400">
                {translateText("Rollback is staging-only: failed or low-quality parses do not mutate production species, feedstocks, or campaign constants.")}
              </p>
            </CardBody>
          </Card>

          <Card className="assistant-aside-card rounded-[28px]">
            <CardHeader
              title="Staged documents"
              description="Review parsed BOS fields, then explicitly promote campaign-compatible candidates."
            />
            <CardBody className="space-y-4">
              {referenceIngestion.isLoading ? (
                <p className="text-sm text-surface-400">{translateText("Loading staged documents...")}</p>
              ) : referenceIngestion.isError ? (
                <p className="text-sm text-red-300">{translateText("Failed to load staged documents.")}</p>
              ) : (referenceIngestion.data?.items ?? []).length ? (
                (referenceIngestion.data?.items ?? []).map((item) => (
                  <StagedIngestionCard
                    key={item.id}
                    item={item}
                    isPromoting={promoteReference.isPending}
                    onPromote={() => {
                      promoteReference.mutate({
                        itemId: item.id,
                        payload: { target_type: "campaign" },
                      });
                    }}
                  />
                ))
              ) : (
                <p className="text-sm text-surface-400">
                  {translateText("No staged documents yet. Parse a PDF to begin review.")}
                </p>
              )}
            </CardBody>
          </Card>
        </div>
      ) : null}
    </div>
  );
}

function MiniInfo({ label, value }: { label: string; value: string }) {
  return (
    <div className="assistant-meta-panel rounded-2xl border border-white/8 bg-surface-900/70 px-4 py-3">
      <p className="assistant-section-kicker !text-surface-500">{translateText(label)}</p>
      <p className="mt-2 break-words text-sm font-medium text-white">{translateText(value)}</p>
    </div>
  );
}

export function DomainCandidateGroups({
  cards,
  readiness,
  knowledgeBase,
  feedstockGuardrails = [],
  literatureBulkExport,
  literatureEvidenceChainReadiness,
}: {
  cards: DomainCandidateCardModel[];
  readiness?: ExternalSourceSchemaReadinessResponse;
  knowledgeBase?: ReviewedExternalCandidateKnowledgeBaseResponse;
  feedstockGuardrails?: string[];
  literatureBulkExport?: LiteratureExtractionCandidateReviewPacketBulkExportResponse;
  literatureEvidenceChainReadiness?: LiteratureExtractionEvidenceChainReadinessResponse;
}) {
  const grouped = groupDomainCandidateCards(cards);
  const guardrails = Array.from(new Set([
    "promotion_enabled=false",
    "runtime_activated=false",
    "validated_default_write_enabled=false",
    "candidate records are not validated defaults",
    ...feedstockGuardrails,
    ...(knowledgeBase?.guardrails ?? []),
  ]));

  return (
    <div className="space-y-6">
      <Card className="assistant-aside-card rounded-[28px]">
        <CardHeader
          title="Candidate seeds"
          description="Pending, reviewed, and runtime-inactive domain candidates are shown as read-only metadata, not validated defaults."
        />
        <CardBody className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MiniInfo label="External source schema readiness" value={readiness?.status ?? "checking"} />
            <MiniInfo label="Reviewed metadata lane" value={String(readiness?.reviewed_metadata_lane_ready ?? false)} />
            <MiniInfo label="Domain metadata ready" value={String(readiness?.phase4a_domain_metadata_ready ?? false)} />
            <MiniInfo label="Knowledge base status" value={knowledgeBase?.status ?? "checking"} />
          </div>
          <div className="flex flex-wrap gap-2">
            {guardrails.map((guardrail) => (
              <Badge key={guardrail} variant="neutral">{translateText(guardrail)}</Badge>
            ))}
          </div>
          {literatureBulkExport ? (
            <div className="rounded-2xl border border-emerald-300/15 bg-emerald-400/8 px-3 py-3 text-xs leading-5 text-surface-300">
              <p className="font-medium text-emerald-100">{translateText("Literature reviewer packet bulk export")}</p>
              <div className="mt-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                <span>{translateText("export_filename")}: {literatureBulkExport.export_filename}</span>
                <span>{translateText("candidate_count")}: {String(literatureBulkExport.count)}</span>
                <span>{translateText("export_policy")}: {displayValue(literatureBulkExport.export_manifest.export_policy)}</span>
                <span>{translateText("source_packet_persistence")}: {displayValue(literatureBulkExport.export_manifest.source_packet_persistence)}</span>
                <span>{translateText("content_hash")}: {literatureBulkExport.content_hash.slice(0, 12)}</span>
                <span>{translateText("file_written")}: {String(literatureBulkExport.side_effects.file_written)}</span>
                <span>{translateText("release_evidence_use")}: {String(literatureBulkExport.side_effects.release_evidence_use)}</span>
                <span>{translateText("final_action_execution")}: {String(literatureBulkExport.side_effects.final_action_execution)}</span>
              </div>
            </div>
          ) : null}
          {literatureEvidenceChainReadiness ? (
            <div className="rounded-2xl border border-cyan-300/15 bg-cyan-400/8 px-3 py-3 text-xs leading-5 text-surface-300">
              <p className="font-medium text-cyan-100">{translateText("Literature evidence chain readiness")}</p>
              <div className="mt-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                <span>{translateText("chain_complete")}: {String(literatureEvidenceChainReadiness.chain_complete)}</span>
                <span>{translateText("candidate_count")}: {String(literatureEvidenceChainReadiness.candidate_count)}</span>
                <span>{translateText("packet_export_ready")}: {String(literatureEvidenceChainReadiness.packet_export_ready)}</span>
                <span>{translateText("bulk_export_ready")}: {String(literatureEvidenceChainReadiness.bulk_export_ready)}</span>
                <span>{translateText("review_draft_count")}: {String(literatureEvidenceChainReadiness.review_draft_count)}</span>
                <span>{translateText("comparison_ready")}: {String(literatureEvidenceChainReadiness.comparison_ready)}</span>
                <span>{translateText("report_ready")}: {String(literatureEvidenceChainReadiness.report_ready)}</span>
                <span>{translateText("auto_use_allowed")}: {String(literatureEvidenceChainReadiness.auto_use_allowed)}</span>
                <span>{translateText("release/runtime/default/promotion/final-action")}: false</span>
                <span>{translateText("release_evidence_allowed")}: {String(literatureEvidenceChainReadiness.release_evidence_allowed)}</span>
                <span>{translateText("runtime_activation_enabled")}: {String(literatureEvidenceChainReadiness.runtime_activation_enabled)}</span>
                <span>{translateText("validated_default_write_enabled")}: {String(literatureEvidenceChainReadiness.validated_default_write_enabled)}</span>
                <span>{translateText("promotion_enabled")}: {String(literatureEvidenceChainReadiness.promotion_enabled)}</span>
                <span>{translateText("final_action_execution")}: {String(literatureEvidenceChainReadiness.final_action_execution)}</span>
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {literatureEvidenceChainReadiness.guardrails.slice(0, 4).map((guardrail) => (
                  <Badge key={guardrail} variant="neutral">{translateText(guardrail)}</Badge>
                ))}
              </div>
            </div>
          ) : null}
        </CardBody>
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        {DOMAIN_GROUPS.map((group) => {
          const items = grouped[group.key] ?? [];
          const domainCounts = knowledgeBase?.candidate_domains ?? {};
          const reviewedCount = group.candidateDomains.reduce(
            (total, domain) => total + (domainCounts[domain] ?? 0),
            0,
          );
          const metadataCount = group.candidateDomains.reduce(
            (total, domain) => total + (readiness?.phase4a_domain_candidate_counts?.[domain] ?? 0),
            0,
          );
          const missingCount = group.candidateDomains.reduce(
            (total, domain) => total + (readiness?.phase4a_domain_missing_counts?.[domain] ?? 0),
            0,
          );

          return (
            <Card key={group.key} className="assistant-aside-card rounded-[28px]">
              <CardHeader
                title={`${group.label} domain candidates`}
                description="Review-gated metadata only; runtime activation and default writes stay disabled."
              />
              <CardBody className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="warning">{translateText(`${items.length} visible candidates`)}</Badge>
                  <Badge variant="neutral">{translateText(`${reviewedCount} reviewed external`)}</Badge>
                  <Badge variant="neutral">{translateText(`${metadataCount} metadata source candidates`)}</Badge>
                  <Badge variant={missingCount === 0 ? "success" : "warning"}>
                    {translateText(`${missingCount} missing metadata sources`)}
                  </Badge>
                </div>

                {items.length ? (
                  <div className="space-y-3">
                    {items.map((candidate) => (
                      <DomainCandidateCard key={candidate.id} candidate={candidate} />
                    ))}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-amber-300/15 bg-amber-400/8 px-3 py-3 text-xs leading-5 text-amber-100">
                    {translateText("No candidate records are visible in this domain yet. This empty state does not create defaults or activate runtime data.")}
                  </div>
                )}
              </CardBody>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

function DomainCandidateCard({ candidate }: { candidate: DomainCandidateCardModel }) {
  const allRuntimeGuardrailsDisabled =
    candidate.promotionEnabled === false &&
    candidate.runtimeActivated === false &&
    candidate.validatedDefaultWriteEnabled === false;
  const reviewPacketExport = useBusinessKnowledgeReviewPacketExport(candidate.reviewPacketExportItemKey);
  const literatureReviewPacketExport = useLiteratureExtractionCandidateReviewPacketExport(
    candidate.reviewPacketExportCandidateId,
  );
  const [comparisonFieldFilter, setComparisonFieldFilter] = useState("");
  const literatureReviewDraftComparison = useLiteratureExtractionReviewDraftComparison(
    candidate.reviewDraft ? candidate.reviewPacketExportCandidateId : undefined,
    comparisonFieldFilter || undefined,
  );
  const literaturePromotionReadiness = useLiteratureValuePromotionReadiness(candidate.reviewPacketExportCandidateId);
  const literaturePromotionLifecycle = useLiteratureValuePromotionLifecycle(candidate.reviewPacketExportCandidateId);
  const literaturePromotionAuditExport = useLiteratureValuePromotionAuditExport(candidate.reviewPacketExportCandidateId);
  const reviewDraftMutation = useCreateLiteratureExtractionReviewDraft();
  const exportData = literatureReviewPacketExport.data ?? reviewPacketExport.data;
  const draftComparison: LiteratureExtractionReviewDraftComparisonResponse | undefined =
    literatureReviewDraftComparison.data;
  const canRecordLiteratureReviewDraft = Boolean(candidate.reviewPacketExportCandidateId);
  const recordLiteratureReviewDraft = () => {
    if (!candidate.reviewPacketExportCandidateId) return;
    reviewDraftMutation.mutate({
      candidateId: candidate.reviewPacketExportCandidateId,
      payload: {
        review_intent: "approve_candidate_use_intent",
        reviewer_notes: "Reference Atlas reviewer draft intent only; candidate remains pending_review.",
        idempotency_key: `reference-atlas:${candidate.reviewPacketExportCandidateId}:approve_candidate_use_intent`,
      },
    });
  };

  return (
    <div className="rounded-2xl border border-white/8 bg-white/5 px-3 py-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-medium text-white">{candidate.title}</p>
          <p className="mt-1 text-xs leading-5 text-surface-400">{candidate.subtitle}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="info">{translateText(candidate.lane)}</Badge>
          <Badge variant="warning">{candidate.reviewStatus}</Badge>
          <Badge variant={allRuntimeGuardrailsDisabled ? "success" : "danger"}>
            {translateText(allRuntimeGuardrailsDisabled ? "runtime inactive / defaults disabled" : "guardrail violation")}
          </Badge>
        </div>
      </div>

      {candidate.note ? (
        <p className="mt-3 text-xs leading-5 text-surface-300">{translateText(candidate.note)}</p>
      ) : null}

      <div className="mt-3 grid gap-2 text-xs text-surface-300 sm:grid-cols-2">
        <span>{translateText("candidate_type")}: {candidate.candidateType}</span>
        <span>{translateText("review_status")}: {candidate.reviewStatus}</span>
        <span>{translateText("license_status")}: {candidate.licenseStatus}</span>
        <span>{translateText("human_review_required")}: {String(candidate.humanReviewRequired)}</span>
        <span>{translateText("promotion_enabled")}: {String(candidate.promotionEnabled)}</span>
        <span>{translateText("runtime_activated")}: {String(candidate.runtimeActivated)}</span>
        <span className="sm:col-span-2">
          {translateText("validated_default_write_enabled")}: {String(candidate.validatedDefaultWriteEnabled)}
        </span>
        <span className="sm:col-span-2">{translateText("allowed_use")}: {candidate.allowedUse}</span>
        <span className="sm:col-span-2">{translateText("blocked_use")}: {candidate.blockedUse}</span>
        <span>{translateText("source_kind")}: {candidate.sourceKind}</span>
        <span>{translateText("source_ref")}: {candidate.sourceRef}</span>
      </div>

      {candidate.reviewWorkflow ? (
        <div className="mt-3 border-t border-white/10 pt-3 text-xs leading-5 text-surface-300">
          <p className="font-medium text-white">{translateText("Reviewer workflow")}</p>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            <span>{translateText("review_packet_id")}: {candidate.reviewWorkflow.review_packet_id}</span>
            <span>{translateText("review_state")}: {candidate.reviewWorkflow.review_state}</span>
            <span>{translateText("source_packet_persistence")}: {candidate.reviewWorkflow.source_packet_persistence}</span>
            <span>{translateText("reviewer_notes_required")}: {String(candidate.reviewWorkflow.reviewer_notes_required)}</span>
            <span>{translateText("approval_enabled")}: {String(candidate.reviewWorkflow.approval_enabled)}</span>
            <span>{translateText("rejection_enabled")}: {String(candidate.reviewWorkflow.rejection_enabled)}</span>
            <span>{translateText("release_evidence_allowed")}: {String(candidate.reviewWorkflow.release_evidence_allowed)}</span>
            <span>{translateText("numeric_values_allowed")}: {String(candidate.reviewWorkflow.numeric_values_allowed)}</span>
            <span className="sm:col-span-2">
              {translateText("allowed_review_actions")}: {candidate.reviewWorkflow.allowed_review_actions.join(", ")}
            </span>
          </div>
        </div>
      ) : null}

      {exportData ? (
        <div className="mt-3 rounded-xl border border-emerald-300/15 bg-emerald-400/8 px-3 py-2 text-xs leading-5 text-surface-300">
          <p className="font-medium text-emerald-100">{translateText("Response-only reviewer packet export")}</p>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            <span>{translateText("export_filename")}: {exportData.export_filename}</span>
            <span>{translateText("export_policy")}: {displayValue(exportData.export_manifest.export_policy)}</span>
            <span>{translateText("export_id")}: {displayValue(exportData.export_manifest.export_id)}</span>
            <span>{translateText("content_hash")}: {exportData.content_hash.slice(0, 12)}</span>
            <span>{translateText("candidate_id")}: {displayValue(exportData.export_manifest.candidate_id ?? exportData.export_manifest.item_key)}</span>
            <span>{translateText("file_written")}: {String(exportData.side_effects.file_written)}</span>
            <span>{translateText("runtime_activation")}: {String(exportData.side_effects.runtime_activation)}</span>
            <span>{translateText("validated_default_write")}: {String(exportData.side_effects.validated_default_write)}</span>
            <span>{translateText("release_evidence_use")}: {displayValue(exportData.side_effects.release_evidence_use)}</span>
            <span>{translateText("promotion")}: {displayValue(exportData.side_effects.promotion)}</span>
            {"numeric_value_extraction" in exportData.side_effects ? (
              <span>{translateText("numeric_value_extraction")}: {String(exportData.side_effects.numeric_value_extraction)}</span>
            ) : null}
            <span>{translateText("final_action_execution")}: {String(exportData.side_effects.final_action_execution)}</span>
          </div>
        </div>
      ) : null}

      {canRecordLiteratureReviewDraft ? (
        <div className="mt-3 rounded-xl border border-cyan-300/15 bg-cyan-400/8 px-3 py-2 text-xs leading-5 text-surface-300">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <p className="font-medium text-cyan-100">{translateText("Reviewer draft intent")}</p>
            <Button
              type="button"
              variant="secondary"
              size="xs"
              onClick={recordLiteratureReviewDraft}
              loading={reviewDraftMutation.isPending}
            >
              {candidate.reviewDraft ? "Refresh draft intent" : "Record draft intent"}
            </Button>
          </div>
          {candidate.reviewDraft ? (
            <>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                <span>{translateText("review_draft_id")}: {candidate.reviewDraft.review_draft_id}</span>
                <span>{translateText("status")}: {candidate.reviewDraft.status}</span>
                <span>{translateText("review_intent")}: {candidate.reviewDraft.review_intent}</span>
                <span>{translateText("source_review_packet_hash")}: {candidate.reviewDraft.source_review_packet_hash.slice(0, 12)}</span>
                <span>{translateText("export_policy")}: {displayValue(candidate.reviewDraft.export_manifest.export_policy)}</span>
                <span>{translateText("candidate_status_update")}: {String(candidate.reviewDraft.side_effects.candidate_status_update)}</span>
                <span>{translateText("release_evidence_use")}: {String(candidate.reviewDraft.side_effects.release_evidence_use)}</span>
                <span>{translateText("final_action_execution")}: {String(candidate.reviewDraft.side_effects.final_action_execution)}</span>
              </div>
              {draftComparison ? (
                <div className="mt-3 rounded-lg border border-cyan-200/15 bg-slate-950/25 px-3 py-2">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <p className="font-medium text-cyan-100">{translateText("Reviewer draft revision comparison")}</p>
                    <Select
                      className="h-8 min-w-48 text-xs"
                      value={comparisonFieldFilter}
                      onChange={(event) => setComparisonFieldFilter(event.target.value)}
                      options={[
                        { value: "", label: "All changed fields" },
                        { value: "review_intent", label: "review_intent" },
                        { value: "candidate_snapshot", label: "candidate_snapshot" },
                        { value: "source_review_packet_hash", label: "source_review_packet_hash" },
                        { value: "side_effects", label: "side_effects" },
                        { value: "export_manifest", label: "export_manifest" },
                      ]}
                    />
                  </div>
                  <div className="mt-2 grid gap-2 sm:grid-cols-2">
                    <span>{translateText("comparison_policy")}: {displayValue(draftComparison.comparison_manifest.comparison_policy)}</span>
                    <span>{translateText("report_policy")}: {displayValue(draftComparison.report_manifest.report_policy)}</span>
                    <span>{translateText("revision_hash")}: {draftComparison.current_revision_hash.slice(0, 12)}</span>
                    <span>{translateText("comparison_hash")}: {displayValue(draftComparison.comparison_manifest.comparison_hash).slice(0, 12)}</span>
                    <span>{translateText("report_id")}: {displayValue(draftComparison.report_manifest.report_id).slice(0, 24)}</span>
                    <span>{translateText("revision_count")}: {displayValue(draftComparison.comparison_manifest.revision_count)}</span>
                    <span>{translateText("changed_field_filter")}: {displayValue(draftComparison.changed_field_filter)}</span>
                    <span>{translateText("changed_fields")}: {draftComparison.changed_fields.length ? draftComparison.changed_fields.join(", ") : "none"}</span>
                    <span>{translateText("packet_hash_matches")}: {String(draftComparison.comparison_summary.current_response_packet_hash_matches_draft)}</span>
                    <span>{translateText("candidate_snapshot_matches")}: {String(draftComparison.comparison_summary.current_candidate_snapshot_matches_draft)}</span>
                    <span>{translateText("file_written")}: {String(draftComparison.side_effects.file_written)}</span>
                    <span>{translateText("release_evidence_use")}: {String(draftComparison.side_effects.release_evidence_use)}</span>
                    <span>{translateText("final_action_execution")}: {String(draftComparison.side_effects.final_action_execution)}</span>
                  </div>
                </div>
              ) : null}
            </>
          ) : (
            <p className="mt-2 text-cyan-100/80">
              {translateText("No reviewer draft intent recorded; recording creates an isolated draft row and does not change candidate status.")}
            </p>
          )}
        </div>
      ) : null}

      {candidate.reviewPacketExportCandidateId ? (
        <LiteraturePromotionLifecyclePanel
          candidateId={candidate.reviewPacketExportCandidateId}
          isLoading={
            literaturePromotionReadiness.isLoading ||
            literaturePromotionLifecycle.isLoading ||
            literaturePromotionAuditExport.isLoading
          }
          isError={
            literaturePromotionReadiness.isError &&
            literaturePromotionLifecycle.isError &&
            literaturePromotionAuditExport.isError
          }
          readiness={literaturePromotionReadiness.data}
          lifecycle={literaturePromotionLifecycle.data}
          auditExport={literaturePromotionAuditExport.data}
        />
      ) : null}
    </div>
  );
}

const BLOCKED_LITERATURE_SCOPE_KEYS = new Set([
  "global",
  "default",
  "all",
  "all_tenants",
  "all_batches",
  "global_default",
]);

function nextLiteratureWorkflowIdempotencyKey(prefix: string, id: string) {
  const suffix = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `reference-atlas:${prefix}:${id}:${suffix}`;
}

function latestLifecycleId(ids: string[] = [], statuses: string[] = [], acceptedStatuses?: Set<string>) {
  for (let index = ids.length - 1; index >= 0; index -= 1) {
    const status = statuses[index];
    if (!acceptedStatuses || acceptedStatuses.has(status)) return ids[index];
  }
  return undefined;
}

function parseLiteratureActivationScope(value: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(value);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      toast.error("Activation scope must be a JSON object");
      return null;
    }
    const blocked = Object.keys(parsed).filter((key) => BLOCKED_LITERATURE_SCOPE_KEYS.has(key));
    if (blocked.length) {
      toast.error(`Blocked activation scope: ${blocked.join(", ")}`);
      return null;
    }
    return parsed as Record<string, unknown>;
  } catch {
    toast.error("Activation scope JSON is invalid");
    return null;
  }
}

function LiteraturePromotionLifecyclePanel({
  candidateId,
  isLoading,
  isError,
  readiness,
  lifecycle,
  auditExport,
}: {
  candidateId?: string;
  isLoading: boolean;
  isError: boolean;
  readiness?: LiteratureValuePromotionReadinessResponse;
  lifecycle?: LiteratureValuePromotionLifecycleResponse;
  auditExport?: LiteratureValuePromotionAuditExportResponse;
}) {
  const latestRequestStatus =
    readiness?.request_status ??
    lifecycle?.request_statuses[lifecycle.request_statuses.length - 1] ??
    "not_requested";
  const latestOverlayStatus = lifecycle?.overlay_statuses[lifecycle.overlay_statuses.length - 1] ?? "none";
  const latestActivationStatus = lifecycle?.activation_statuses[lifecycle.activation_statuses.length - 1] ?? "not active";
  const latestRollbackStatus = lifecycle?.rollback_statuses[lifecycle.rollback_statuses.length - 1] ?? "not_rolled_back";
  const activeCandidateId = candidateId ?? readiness?.candidate_id ?? lifecycle?.candidate_id ?? auditExport?.candidate_id;
  const latestPromotionRequestId =
    readiness?.existing_promotion_request_id ??
    latestLifecycleId(lifecycle?.promotion_request_ids, lifecycle?.request_statuses, new Set(["requested", "approved", "approved_for_promotion"]));
  const latestOverlayId = latestLifecycleId(lifecycle?.overlay_ids, lifecycle?.overlay_statuses, new Set(["inactive"]));
  const latestActiveActivationId = latestLifecycleId(lifecycle?.activation_ids, lifecycle?.activation_statuses, new Set(["active"]));
  const defaultScope = activeCandidateId ? `{"campaign_key":"literature-promotion:${activeCandidateId}"}` : "{\"campaign_key\":\"literature-promotion\"}";
  const [approverNotes, setApproverNotes] = useState("Reviewed packet and comparison hash for scoped overlay promotion only.");
  const [rejectorNotes, setRejectorNotes] = useState("");
  const [overlayNotes, setOverlayNotes] = useState("Create inactive overlay only; scoped runtime activation remains separate.");
  const [activationScopeJson, setActivationScopeJson] = useState(defaultScope);
  const [operatorAttestation, setOperatorAttestation] = useState("I attest this activation is scoped and does not write validated defaults.");
  const [rollbackReason, setRollbackReason] = useState("Rollback scoped literature overlay after review.");
  const [rollbackAttestation, setRollbackAttestation] = useState("I attest rollback preserves review_required release decisions and does not execute final actions.");
  const requestPromotion = useCreateLiteratureValuePromotionRequest();
  const approvePromotion = useApproveLiteratureValuePromotionRequest();
  const rejectPromotion = useRejectLiteratureValuePromotionRequest();
  const promoteOverlay = usePromoteLiteratureValueRequestToOverlay();
  const activateRuntime = useCreateLiteratureValueRuntimeActivation();
  const rollbackActivation = useRollbackLiteratureValueRuntimeActivation();
  const activationPreview = useLiteratureValueRuntimeActivationPreview(latestOverlayId);
  const canRequestPromotion = Boolean(readiness?.promotion_ready && activeCandidateId && !readiness.existing_promotion_request_id);
  const canApproveOrReject = Boolean(
    latestPromotionRequestId && (latestRequestStatus === "requested" || latestRequestStatus === "approved"),
  );
  const canCreateOverlay = Boolean(latestPromotionRequestId && latestRequestStatus === "approved_for_promotion" && !latestOverlayId);
  const canActivate = Boolean(
    activeCandidateId &&
    latestOverlayId &&
    activationPreview.data?.can_activate_scoped_runtime === true &&
    !latestActiveActivationId,
  );
  const canRollback = Boolean(activeCandidateId && latestActiveActivationId);
  const releaseReviewRequired =
    auditExport?.final_action_non_execution_proof.release_decisions_all_review_required === true ||
    (lifecycle?.release_decision_states ?? []).every(
      (state) => state.release_decision_before === "review_required" && state.release_decision_after === "review_required",
    );
  const manifest = auditExport?.export_manifest ?? {};

  return (
    <div className="mt-3 rounded-xl border border-sky-300/15 bg-sky-400/8 px-3 py-2 text-xs leading-5 text-surface-300">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="font-medium text-sky-100">{translateText("Promotion lifecycle")}</p>
        <Badge variant={latestRequestStatus === "approved_for_promotion" ? "success" : "warning"}>
          {translateText(`Promotion request: ${latestRequestStatus}`)}
        </Badge>
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        <span>{translateText("request status")}: {translateText(latestRequestStatus)}</span>
        <span>{translateText("runtime")}: {translateText(latestActivationStatus === "active" ? "active" : "not active")}</span>
        <span>{translateText("promotion lifecycle")}: {translateText(lifecycle?.lifecycle_read_only ? "read only" : "pending read")}</span>
        <span>{translateText("overlay")}: {translateText(latestOverlayStatus)}</span>
        <span>{translateText("rollback")}: {translateText(latestRollbackStatus)}</span>
        <span>{translateText("release decision")}: {translateText(releaseReviewRequired ? "review_required" : "not linked")}</span>
        <span>{translateText("approval count")}: {String(lifecycle?.approval_count ?? auditExport?.approvals.length ?? 0)}</span>
        <span>{translateText("activation scope")}: {displayValue(auditExport?.runtime_activation?.activation_scope)}</span>
        <span>{translateText("source")}: {displayValue(auditExport?.overlay?.source_ref ?? readiness?.conditions.source_ref)}</span>
        <span>{translateText("audit export policy")}: {displayValue(auditExport?.export_policy ?? manifest.export_policy)}</span>
        <span>{translateText("file_written")}: {displayValue(manifest.file_written ?? auditExport?.side_effects.file_written)}</span>
        <span>{translateText("content_hash")}: {auditExport?.content_hash ? auditExport.content_hash.slice(0, 12) : "pending"}</span>
      </div>
      <div className="mt-3 rounded-lg border border-white/10 bg-black/10 px-3 py-3">
        <p className="font-medium text-sky-100">{translateText("Controlled promotion workflow")}</p>
        <div className="mt-2 grid gap-2 text-surface-300 sm:grid-cols-2 xl:grid-cols-5">
          <span>{translateText("species_db_write")}: false</span>
          <span>{translateText("feedstock_db_write")}: false</span>
          <span>{translateText("validated_default_write")}: false</span>
          <span>{translateText("final_action_execution")}: false</span>
          <span>{translateText("release_decision")}: {translateText("review_required")}</span>
        </div>
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          <Textarea
            label="Approver notes"
            value={approverNotes}
            onChange={(event) => setApproverNotes(event.target.value)}
            rows={2}
          />
          <Textarea
            label="Rejection notes"
            value={rejectorNotes}
            onChange={(event) => setRejectorNotes(event.target.value)}
            rows={2}
          />
          <Textarea
            label="Overlay notes"
            value={overlayNotes}
            onChange={(event) => setOverlayNotes(event.target.value)}
            rows={2}
          />
          <Textarea
            label="Activation scope JSON"
            value={activationScopeJson}
            onChange={(event) => setActivationScopeJson(event.target.value)}
            rows={2}
          />
          <Textarea
            label="Operator attestation"
            value={operatorAttestation}
            onChange={(event) => setOperatorAttestation(event.target.value)}
            rows={2}
          />
          <Textarea
            label="Rollback reason"
            value={rollbackReason}
            onChange={(event) => setRollbackReason(event.target.value)}
            rows={2}
          />
        </div>
        <Textarea
          className="mt-3"
          label="Rollback operator attestation"
          value={rollbackAttestation}
          onChange={(event) => setRollbackAttestation(event.target.value)}
          rows={2}
        />
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            type="button"
            variant="secondary"
            size="xs"
            disabled={!canRequestPromotion}
            loading={requestPromotion.isPending}
            onClick={() => {
              if (!activeCandidateId) return;
              requestPromotion.mutate({
                candidateId: activeCandidateId,
                payload: {
                  target_use: "candidate_overlay_review",
                  target_scope: { campaign_key: `literature-promotion:${activeCandidateId}` },
                  idempotency_key: nextLiteratureWorkflowIdempotencyKey("promotion-request", activeCandidateId),
                },
              });
            }}
          >
            {translateText("Request promotion review")}
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="xs"
            disabled={!canApproveOrReject || !approverNotes.trim()}
            loading={approvePromotion.isPending}
            onClick={() => {
              if (!latestPromotionRequestId) return;
              approvePromotion.mutate({
                promotionRequestId: latestPromotionRequestId,
                candidateId: activeCandidateId,
                payload: {
                  approval_action: "approve",
                  approver_notes: approverNotes,
                  idempotency_key: nextLiteratureWorkflowIdempotencyKey("promotion-approve", latestPromotionRequestId),
                },
              });
            }}
          >
            {translateText("Approve promotion review")}
          </Button>
          <Button
            type="button"
            variant="danger"
            size="xs"
            disabled={!canApproveOrReject || !rejectorNotes.trim()}
            loading={rejectPromotion.isPending}
            onClick={() => {
              if (!latestPromotionRequestId) return;
              rejectPromotion.mutate({
                promotionRequestId: latestPromotionRequestId,
                candidateId: activeCandidateId,
                payload: {
                  rejector_notes: rejectorNotes,
                  idempotency_key: nextLiteratureWorkflowIdempotencyKey("promotion-reject", latestPromotionRequestId),
                },
              });
            }}
          >
            {translateText("Reject promotion review")}
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="xs"
            disabled={!canCreateOverlay || !overlayNotes.trim()}
            loading={promoteOverlay.isPending}
            onClick={() => {
              if (!latestPromotionRequestId) return;
              promoteOverlay.mutate({
                promotionRequestId: latestPromotionRequestId,
                candidateId: activeCandidateId,
                payload: {
                  overlay_notes: overlayNotes,
                  idempotency_key: nextLiteratureWorkflowIdempotencyKey("inactive-overlay", latestPromotionRequestId),
                },
              });
            }}
          >
            {translateText("Create inactive overlay")}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="xs"
            disabled={!latestOverlayId}
            loading={activationPreview.isLoading}
            onClick={() => latestOverlayId && void activationPreview.refetch()}
          >
            {translateText("Preview scoped activation")}
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="xs"
            disabled={!canActivate || !operatorAttestation.trim()}
            loading={activateRuntime.isPending}
            onClick={() => {
              if (!latestOverlayId) return;
              const activationScope = parseLiteratureActivationScope(activationScopeJson);
              if (!activationScope) return;
              activateRuntime.mutate({
                overlayId: latestOverlayId,
                candidateId: activeCandidateId,
                payload: {
                  activation_scope: activationScope,
                  operator_attestation: operatorAttestation,
                  idempotency_key: nextLiteratureWorkflowIdempotencyKey("runtime-activation", latestOverlayId),
                },
              });
            }}
          >
            {translateText("Activate scoped runtime overlay")}
          </Button>
          <Button
            type="button"
            variant="danger"
            size="xs"
            disabled={!canRollback || !rollbackReason.trim() || !rollbackAttestation.trim()}
            loading={rollbackActivation.isPending}
            onClick={() => {
              if (!latestActiveActivationId) return;
              rollbackActivation.mutate({
                activationId: latestActiveActivationId,
                candidateId: activeCandidateId,
                overlayId: latestOverlayId,
                payload: {
                  rollback_reason: rollbackReason,
                  operator_attestation: rollbackAttestation,
                  idempotency_key: nextLiteratureWorkflowIdempotencyKey("runtime-rollback", latestActiveActivationId),
                },
              });
            }}
          >
            {translateText("Rollback activation")}
          </Button>
        </div>
        <div className="mt-3 grid gap-2 text-sky-100/80 sm:grid-cols-2">
          <span>{translateText("promotion_request_id")}: {displayValue(latestPromotionRequestId)}</span>
          <span>{translateText("overlay_id")}: {displayValue(latestOverlayId)}</span>
          <span>{translateText("active_activation_id")}: {displayValue(latestActiveActivationId)}</span>
          <span>{translateText("can_activate_scoped_runtime")}: {String(activationPreview.data?.can_activate_scoped_runtime ?? false)}</span>
        </div>
      </div>
      {isLoading ? (
        <p className="mt-2 text-sky-100/70">{translateText("Loading promotion lifecycle.")}</p>
      ) : null}
      {isError ? (
        <p className="mt-2 text-amber-100/80">
          {translateText("Promotion lifecycle is not available yet; candidate remains not active.")}
        </p>
      ) : null}
      <div className="mt-2 flex flex-wrap gap-2">
        {(auditExport?.guardrails ?? lifecycle?.guardrails ?? readiness?.guardrails ?? ["no_runtime_activation", "no_final_action_execution"])
          .slice(0, 5)
          .map((guardrail) => (
            <Badge key={guardrail} variant="neutral">{translateText(guardrail)}</Badge>
          ))}
      </div>
    </div>
  );
}

export function ExternalSourceSchemaReadinessStrip({
  readiness,
  isLoading,
  isError,
}: {
  readiness: ExternalSourceSchemaReadinessResponse | undefined;
  isLoading: boolean;
  isError: boolean;
}) {
  if (isLoading) {
    return (
      <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3 text-sm text-surface-300">
        {translateText("Checking external source schema readiness...")}
      </div>
    );
  }

  if (isError || !readiness) {
    return (
      <div className="rounded-2xl border border-red-300/20 bg-red-500/10 px-4 py-3 text-sm text-red-100">
        {translateText("External source schema readiness is unavailable. Reference Atlas external lanes may fail until the local DB schema is checked.")}
      </div>
    );
  }

  const tableSummary = readiness.required_tables
    .map((table) => `${table.table_name}: ${table.present ? table.row_count ?? 0 : "missing"}`)
    .join(" / ");
  const domainSummary = Object.entries(readiness.phase4a_domain_candidate_counts ?? {})
    .map(([domain, count]) => `${domain}: ${count}/${readiness.phase4a_domain_expected_counts?.[domain] ?? count}`)
    .join(" / ");

  return (
    <div className={`rounded-2xl border px-4 py-3 ${
      readiness.status === "ready"
        ? "border-emerald-300/20 bg-emerald-500/10"
        : "border-amber-300/20 bg-amber-500/10"
    }`}>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="assistant-section-kicker">{translateText("External source schema readiness")}</p>
          <p className="mt-2 text-sm leading-6 text-surface-200">
            {translateText(
              readiness.status === "ready"
                ? "Schema ready; external source lanes can distinguish empty candidates from missing local tables."
                : `Schema blocked: ${readiness.blockers.join("; ") || "missing readiness details"}`,
            )}
          </p>
          <p className="mt-2 text-xs leading-5 text-surface-400">{tableSummary}</p>
          {domainSummary ? (
            <p className="mt-1 text-xs leading-5 text-surface-400">{domainSummary}</p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2 lg:justify-end">
          <Badge variant={readiness.status === "ready" ? "success" : "warning"}>{readiness.status}</Badge>
          <Badge variant="neutral">{translateText(`${readiness.feedstock_dataset_candidate_count} feedstock dataset candidates`)}</Badge>
          <Badge variant={readiness.phase4a_domain_metadata_ready ? "success" : "warning"}>
            {translateText(`phase4a_domain_metadata_ready: ${String(readiness.phase4a_domain_metadata_ready ?? false)}`)}
          </Badge>
          <Badge variant={readiness.reviewed_metadata_lane_ready ? "success" : "warning"}>
            {translateText(`reviewed_metadata_lane_ready: ${String(readiness.reviewed_metadata_lane_ready)}`)}
          </Badge>
          {readiness.guardrails.map((guardrail) => (
            <Badge key={guardrail} variant="neutral">{translateText(guardrail)}</Badge>
          ))}
        </div>
      </div>
    </div>
  );
}

export function ReviewedExternalCandidateCard({
  candidate,
  evidencePanelsEnabled = true,
}: {
  candidate: ReviewedExternalCandidate;
  evidencePanelsEnabled?: boolean;
}) {
  const payload = candidate.candidate_payload as Record<string, unknown>;
  const evidenceCandidateId = evidencePanelsEnabled ? candidate.candidate_id : undefined;
  const activationPreview = useReviewedExternalCandidateActivationPreview(evidenceCandidateId);
  const runtimeReadiness = useReviewedExternalCandidateRuntimeReadiness(evidenceCandidateId);
  const rollbackPreview = useReviewedExternalCandidateRollbackPreview(evidenceCandidateId);
  const numericValuesIncluded = Boolean(payload.numeric_values_included);
  const isRuntimeBlocked =
    candidate.runtime_activated === false &&
    candidate.promotion_enabled === false &&
    candidate.validated_default_write_enabled === false;

  return (
    <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm font-medium text-white">{candidate.candidate_id}</p>
          <p className="mt-1 text-xs text-surface-400">{candidate.candidate_key}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="success">{candidate.review_status}</Badge>
          <Badge variant={isRuntimeBlocked ? "warning" : "danger"}>
            {candidate.runtime_activated ? "runtime active" : "runtime inactive"}
          </Badge>
          <Badge variant="neutral">{String(payload.payload_version ?? candidate.candidate_type)}</Badge>
        </div>
      </div>

      <p className="mt-3 text-sm leading-6 text-surface-300">{String(payload.title ?? candidate.source_ref)}</p>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <MiniInfo label="Source" value={`${candidate.source_kind} / ${candidate.source_ref}`} />
        <MiniInfo label="Candidate type" value={candidate.candidate_type} />
        <MiniInfo label="Candidate domain" value={candidate.candidate_domain ?? "unknown"} />
        <MiniInfo label="Review status" value={candidate.review_status} />
        <MiniInfo label="DOI" value={String(payload.doi ?? candidate.source_ref)} />
        <MiniInfo label="Article type" value={String(payload.article_type ?? candidate.candidate_type)} />
        <MiniInfo label="Numeric values included" value={String(numericValuesIncluded)} />
        <MiniInfo label="License status" value={candidate.license_status} />
        <MiniInfo label="Human review required" value={String(candidate.human_review_required)} />
        <MiniInfo label="Promotion enabled" value={String(candidate.promotion_enabled)} />
        <MiniInfo label="Runtime activated" value={String(candidate.runtime_activated)} />
        <MiniInfo label="Validated default write enabled" value={String(candidate.validated_default_write_enabled)} />
        <MiniInfo label="Allowed use" value={candidate.allowed_use} />
        <MiniInfo label="Blocked use" value={candidate.blocked_use} />
      </div>

      <div className="mt-4 rounded-2xl border border-amber-300/15 bg-amber-400/8 px-3 py-3 text-xs leading-5 text-amber-100">
        {translateText("Approved for candidate use only. Runtime overlay activation and validated-default writes are still blocked.")}
      </div>

      {evidencePanelsEnabled ? (
        <>
          <OperatorEvidenceSummary
            activationPreview={activationPreview.data}
            rollbackPreview={rollbackPreview.data}
            runtimeReadiness={runtimeReadiness.data}
          />
          <ActivationPreviewPanel
            isError={activationPreview.isError}
            isLoading={activationPreview.isLoading}
            preview={activationPreview.data}
          />
          <RuntimeReadinessPanel
            isError={runtimeReadiness.isError}
            isLoading={runtimeReadiness.isLoading}
            readiness={runtimeReadiness.data}
          />
          <RollbackPreviewPanel
            isError={rollbackPreview.isError}
            isLoading={rollbackPreview.isLoading}
            preview={rollbackPreview.data}
          />
        </>
      ) : null}
    </div>
  );
}

function OperatorEvidenceSummary({
  activationPreview,
  runtimeReadiness,
  rollbackPreview,
}: {
  activationPreview?: ReviewedExternalCandidateActivationPreviewResponse;
  runtimeReadiness?: ReviewedExternalCandidateRuntimeReadinessResponse;
  rollbackPreview?: ReviewedExternalCandidateRollbackPreviewResponse;
}) {
  const evidence = buildReviewedCandidateEvidenceSummary({
    activationPreview,
    runtimeReadiness,
    rollbackPreview,
  });

  return (
    <div className="mt-4 rounded-2xl border border-emerald-300/15 bg-emerald-400/8 px-3 py-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm font-medium text-white">{translateText("Operator evidence summary")}</p>
          <p className="mt-1 text-xs leading-5 text-emerald-100/80">
            {translateText("Activation, runtime read path, and rollback evidence are grouped for review without enabling runtime mutation.")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant={evidence.operatorEvidenceStatus.includes("ready") ? "success" : "warning"}>
            {translateText(evidence.operatorEvidenceStatus)}
          </Badge>
          <Badge variant="neutral">
            {translateText(`release_evidence_allowed: ${String(evidence.releaseEvidenceAllowed)}`)}
          </Badge>
          <Badge variant="neutral">
            {translateText(`side_effects_blocked: ${String(evidence.sideEffectsBlocked)}`)}
          </Badge>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <MiniInfo label="activation_execution" value={evidence.activationExecution} />
        <MiniInfo label="runtime_read_path" value={evidence.runtimeReadPath} />
        <MiniInfo label="runtime_payload_readable" value={String(evidence.runtimePayloadReadable)} />
        <MiniInfo label="rollback_execution" value={evidence.rollbackExecution} />
        <MiniInfo label="rollback_target_available" value={String(evidence.rollbackTargetAvailable)} />
        <MiniInfo label="release_decision" value={evidence.releaseDecision} />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {evidence.guardrailSummary.map((guardrail) => (
          <Badge key={guardrail} variant="neutral">{translateText(formatReviewedCandidateGuardrail(guardrail))}</Badge>
        ))}
      </div>
    </div>
  );
}

function ActivationPreviewPanel({
  isError,
  isLoading,
  preview,
}: {
  isError?: boolean;
  isLoading?: boolean;
  preview?: ReviewedExternalCandidateActivationPreviewResponse;
}) {
  if (isLoading) {
    return (
      <div className="mt-4 rounded-2xl border border-white/8 bg-black/10 px-3 py-3 text-xs text-surface-400">
        {translateText("Loading activation preview")}
      </div>
    );
  }

  if (isError || !preview) {
    return (
      <div className="mt-4 rounded-2xl border border-amber-300/15 bg-amber-400/8 px-3 py-3 text-xs leading-5 text-amber-100">
        {translateText("Activation preview unavailable. Runtime activation remains blocked.")}
      </div>
    );
  }

  const scope = preview.activation_scope;
  const activeState = preview.active_overlay_state;
  const auditContract = preview.activation_audit_contract;
  const sourceLineage = readRecord(scope.source_lineage);
  const runtimePaths = readStringList(scope.runtime_paths);
  const runtimeInactiveDefaultsDisabled =
    preview.candidate.runtime_activated === false &&
    preview.candidate.validated_default_write_enabled === false &&
    preview.can_execute_activation === false;

  return (
    <div className="mt-4 rounded-2xl border border-cyan-300/15 bg-cyan-400/8 px-3 py-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm font-medium text-white">{translateText("Activation preview (read only)")}</p>
          <p className="mt-1 text-xs leading-5 text-surface-400">
            {translateText("Tenant-scoped preview only; no runtime execution endpoint is enabled.")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant={runtimeInactiveDefaultsDisabled ? "warning" : "danger"}>
            {translateText(runtimeInactiveDefaultsDisabled ? "runtime inactive / defaults disabled" : "runtime guardrail drift")}
          </Badge>
          <Badge variant="neutral">{translateText(`can_execute_activation: ${String(preview.can_execute_activation)}`)}</Badge>
          <Badge variant="neutral">{translateText(`rollback_required: ${String(preview.rollback_required)}`)}</Badge>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <MiniInfo label="tenant_scoped" value={displayValue(scope.tenant_scoped)} />
        <MiniInfo label="tenant_id" value={displayValue(scope.tenant_id ?? preview.tenant_id)} />
        <MiniInfo label="candidate_type" value={displayValue(scope.candidate_type ?? preview.candidate.candidate_type)} />
        <MiniInfo label="candidate_key" value={displayValue(scope.candidate_key ?? preview.candidate.candidate_key)} />
        <MiniInfo label="scope_key" value={displayValue(scope.scope_key)} />
        <MiniInfo label="runtime_paths" value={runtimePaths.length ? runtimePaths.join(", ") : "external_knowledge.runtime"} />
        <MiniInfo label="active_overlay_state" value={displayObjectSummary(activeState)} />
        <MiniInfo
          label="activation_required_before_runtime_use"
          value={displayValue(activeState.activation_required_before_runtime_use)}
        />
        <MiniInfo
          label="activation_audit_required"
          value={displayValue(auditContract.activation_audit_id_required)}
        />
        <MiniInfo
          label="activation_execution_endpoint_enabled"
          value={displayValue(auditContract.activation_execution_endpoint_enabled)}
        />
        <MiniInfo label="runtime_overlay_preview_only" value={String(preview.runtime_overlay_preview_only)} />
        <MiniInfo label="validated_default_write_enabled" value={String(preview.candidate.validated_default_write_enabled)} />
        <MiniInfo label="source_lineage" value={displayObjectSummary(sourceLineage)} />
        <MiniInfo label="side_effects" value={displayObjectSummary(preview.side_effects)} />
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {preview.guardrails.map((guardrail) => (
          <Badge key={guardrail} variant="neutral">{translateText(guardrail)}</Badge>
        ))}
      </div>
    </div>
  );
}

function RuntimeReadinessPanel({
  isError,
  isLoading,
  readiness,
}: {
  isError?: boolean;
  isLoading?: boolean;
  readiness?: ReviewedExternalCandidateRuntimeReadinessResponse;
}) {
  if (isLoading) {
    return (
      <div className="mt-4 rounded-2xl border border-white/8 bg-black/10 px-3 py-3 text-xs text-surface-400">
        {translateText("Loading runtime readiness")}
      </div>
    );
  }

  if (isError || !readiness) {
    return (
      <div className="mt-4 rounded-2xl border border-amber-300/15 bg-amber-400/8 px-3 py-3 text-xs leading-5 text-amber-100">
        {translateText("Runtime readiness unavailable. Runtime payload use remains blocked.")}
      </div>
    );
  }

  const scope = readiness.activation_scope;
  const activeState = readiness.active_overlay_state;
  const rollbackContract = readiness.rollback_contract;
  const runtimePaths = readStringList(scope.runtime_paths);
  const hasRuntimePayload = readiness.can_read_runtime_payload && readiness.active_candidate_payload !== null;

  return (
    <div className="mt-4 rounded-2xl border border-white/8 bg-black/10 px-3 py-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm font-medium text-white">{translateText("Runtime readiness (read only)")}</p>
          <p className="mt-1 text-xs leading-5 text-surface-400">
            {translateText("Reads tenant-scoped runtime state only; activation and rollback execution remain unavailable.")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant={hasRuntimePayload ? "success" : "warning"}>
            {translateText(hasRuntimePayload ? "runtime payload readable" : "runtime payload blocked")}
          </Badge>
          <Badge variant="neutral">{translateText(`rollback_required: ${String(readiness.rollback_required)}`)}</Badge>
          <Badge variant="neutral">
            {translateText(`rollback_endpoint_enabled: ${String(rollbackContract.rollback_execution_endpoint_enabled)}`)}
          </Badge>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <MiniInfo label="runtime_read_path_enabled" value={String(readiness.runtime_read_path_enabled)} />
        <MiniInfo label="can_read_runtime_payload" value={String(readiness.can_read_runtime_payload)} />
        <MiniInfo label="runtime_payload_state" value={hasRuntimePayload ? "available" : "none"} />
        <MiniInfo label="runtime_paths" value={runtimePaths.length ? runtimePaths.join(", ") : "external_knowledge.runtime"} />
        <MiniInfo label="scope_key" value={displayValue(scope.scope_key)} />
        <MiniInfo label="active_overlay_state" value={displayObjectSummary(activeState)} />
        <MiniInfo label="rollback_target_required" value={displayValue(rollbackContract.rollback_target_required)} />
        <MiniInfo label="rollback_contract" value={displayObjectSummary(rollbackContract)} />
        <MiniInfo label="side_effects" value={displayObjectSummary(readiness.side_effects)} />
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {readiness.guardrails.map((guardrail) => (
          <Badge key={guardrail} variant="neutral">{translateText(guardrail)}</Badge>
        ))}
      </div>
    </div>
  );
}

function RollbackPreviewPanel({
  isError,
  isLoading,
  preview,
}: {
  isError?: boolean;
  isLoading?: boolean;
  preview?: ReviewedExternalCandidateRollbackPreviewResponse;
}) {
  if (isLoading) {
    return (
      <div className="mt-4 rounded-2xl border border-white/8 bg-black/10 px-3 py-3 text-xs text-surface-400">
        {translateText("Loading rollback preview")}
      </div>
    );
  }

  if (isError || !preview) {
    return (
      <div className="mt-4 rounded-2xl border border-amber-300/15 bg-amber-400/8 px-3 py-3 text-xs leading-5 text-amber-100">
        {translateText("Rollback preview unavailable. Runtime rollback remains blocked.")}
      </div>
    );
  }

  const auditPacket = preview.rollback_audit_packet;
  const rollbackContract = preview.rollback_contract;
  const blockers = preview.rollback_blockers.length ? preview.rollback_blockers.join(", ") : "none";

  return (
    <div className="mt-4 rounded-2xl border border-amber-300/15 bg-amber-400/8 px-3 py-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm font-medium text-white">{translateText("Rollback preview (read only)")}</p>
          <p className="mt-1 text-xs leading-5 text-amber-100/80">
            {translateText("Rollback requires a separate audited execution path; this panel only shows evidence and blockers.")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant={preview.rollback_target_available ? "success" : "warning"}>
            {translateText(preview.rollback_target_available ? "rollback target available" : "rollback target unavailable")}
          </Badge>
          <Badge variant="neutral">{translateText(`can_execute_rollback: ${String(preview.can_execute_rollback)}`)}</Badge>
          <Badge variant="neutral">{translateText(`rollback_preview_only: ${String(preview.rollback_preview_only)}`)}</Badge>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <MiniInfo label="rollback_required" value={String(preview.rollback_required)} />
        <MiniInfo
          label="rollback_execution_endpoint_enabled"
          value={displayValue(rollbackContract.rollback_execution_endpoint_enabled)}
        />
        <MiniInfo label="rollback_blockers" value={blockers} />
        <MiniInfo label="rollback_audit_packet" value={displayObjectSummary(auditPacket)} />
        <MiniInfo label="required_attestations" value={displayValue(auditPacket.required_attestations)} />
        <MiniInfo label="side_effects" value={displayObjectSummary(preview.side_effects)} />
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {preview.guardrails.map((guardrail) => (
          <Badge key={guardrail} variant="neutral">{translateText(guardrail)}</Badge>
        ))}
      </div>
    </div>
  );
}

function readRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function readStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)) : [];
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "none";
  if (Array.isArray(value)) return value.map((item) => String(item)).join(", ");
  if (typeof value === "object") return displayObjectSummary(readRecord(value));
  return String(value);
}

function displayObjectSummary(value: Record<string, unknown>): string {
  const entries = Object.entries(value);
  if (!entries.length) return "none";
  return entries.map(([key, entryValue]) => `${key}: ${displayValue(entryValue)}`).join("; ");
}

export function ExternalReviewCardQueueItem({
  card,
  candidateGenerated = false,
  isResolving = false,
  onResolve,
}: {
  card: ExternalSourceReviewCard;
  candidateGenerated?: boolean;
  isResolving?: boolean;
  onResolve?: (payload: ExternalSourceReviewCardResolveRequest) => void;
}) {
  const [reviewer, setReviewer] = useState(card.reviewer === "unassigned" ? "" : card.reviewer);
  const [licenseStatus, setLicenseStatus] = useState(
    card.license_status === "pending_review" ? "metadata_only" : card.license_status,
  );
  const [boundaryCondition, setBoundaryCondition] = useState(defaultReviewBoundary(card));
  const [allowedUse, setAllowedUse] = useState(card.allowed_use || "review workflow metadata only");
  const [blockedUse, setBlockedUse] = useState(
    card.blocked_use || "no validated defaults; no release evidence; no runtime activation",
  );

  const submitAction = (reviewAction: ExternalSourceReviewAction) => {
    const normalizedLicense =
      reviewAction === "reject"
        ? "blocked"
        : reviewAction === "request_license_clearance"
          ? "restricted"
          : licenseStatus === "pending_review" || licenseStatus === "blocked"
            ? "metadata_only"
            : licenseStatus;

    onResolve?.({
      review_action: reviewAction,
      reviewer: reviewer.trim() || "Reference Atlas reviewer",
      reviewed_at: new Date().toISOString(),
      license_status: normalizedLicense,
      boundary_condition: boundaryCondition.trim() || defaultReviewBoundary(card),
      allowed_use: allowedUse.trim() || "review workflow metadata only",
      blocked_use: ensureBlockedUse(blockedUse),
      candidate_type: candidateTypeForReviewCard(card),
      candidate_payload: {
        review_surface: "reference_atlas_phase5b",
        requested_action: reviewAction,
      },
      numeric_values_included: false,
      extracted_numeric_values: {},
      promotion_enabled: false,
      runtime_activated: false,
      validated_default_write_enabled: false,
      next_action:
        reviewAction === "approve_for_candidate_use"
          ? "Reviewed candidate is ready for future activation review."
          : "Review action persisted without candidate creation.",
    });
  };

  return (
    <div className="rounded-2xl border border-white/8 bg-white/5 px-3 py-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-medium text-white">{card.card_id}</p>
          <p className="mt-1 text-xs leading-5 text-surface-400">{card.title}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant={card.review_status === "approved_for_candidate_use" ? "success" : "warning"}>
            {card.review_status}
          </Badge>
          <Badge variant="neutral">{card.review_action}</Badge>
          <Badge variant="info">{card.license_status}</Badge>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <Badge variant="neutral">{card.ingestion_mode}</Badge>
        <Badge variant="neutral">{card.evidence_source_kind}</Badge>
        {card.human_review_required ? <Badge variant="danger">human review required</Badge> : null}
        {card.runtime_activated ? <Badge variant="danger">runtime active</Badge> : <Badge variant="warning">runtime inactive</Badge>}
      </div>

      <div className="mt-3 grid gap-2 text-xs text-surface-400 sm:grid-cols-2">
        <span>{translateText("reviewer")}: {card.reviewer}</span>
        <span>{translateText("reviewed_at")}: {card.reviewed_at ?? "pending"}</span>
        <span>{translateText("license_status")}: {card.license_status}</span>
        <span>{translateText("allowed_use")}: {card.allowed_use}</span>
        <span>{translateText("blocked_use")}: {card.blocked_use}</span>
        <span>{translateText("candidate_generated")}: {String(candidateGenerated)}</span>
        <span>{translateText("runtime_active")}: {String(card.runtime_activated)}</span>
      </div>
      {onResolve ? (
        <div className="mt-4 space-y-3 rounded-2xl border border-white/8 bg-black/10 p-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Input
              label="Reviewer"
              placeholder="Dr. Reviewer"
              value={reviewer}
              onChange={(event) => setReviewer(event.target.value)}
            />
            <Select
              label="License status"
              value={licenseStatus}
              onChange={(event) => setLicenseStatus(event.target.value)}
              options={[
                { value: "metadata_only", label: "metadata_only" },
                { value: "cleared", label: "cleared" },
                { value: "restricted", label: "restricted" },
              ]}
            />
          </div>
          <Input
            label="Boundary condition"
            value={boundaryCondition}
            onChange={(event) => setBoundaryCondition(event.target.value)}
          />
          <Input
            label="Allowed use"
            value={allowedUse}
            onChange={(event) => setAllowedUse(event.target.value)}
          />
          <Input
            label="Blocked use"
            value={blockedUse}
            onChange={(event) => setBlockedUse(event.target.value)}
          />
          <div className="grid gap-2 sm:grid-cols-2">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              loading={isResolving}
              onClick={() => submitAction("approve_metadata")}
            >
              Approve metadata
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              loading={isResolving}
              onClick={() => submitAction("request_license_clearance")}
            >
              Request license clearance
            </Button>
            <Button
              type="button"
              variant="danger"
              size="sm"
              loading={isResolving}
              onClick={() => submitAction("reject")}
            >
              Reject
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              loading={isResolving}
              onClick={() => submitAction("approve_for_candidate_use")}
            >
              Approve for candidate use
            </Button>
          </div>
          <p className="text-xs leading-5 text-surface-400">
            {translateText("These actions only resolve review cards. They do not activate runtime overlays or write validated defaults.")}
          </p>
        </div>
      ) : null}
    </div>
  );
}

function candidateTypeForReviewCard(card: ExternalSourceReviewCard): string {
  if (card.source_id.startsWith("B-FEED")) return "feedstock_metadata_candidate";
  if (card.source_id.startsWith("C-LCA")) return "lca_boundary_metadata_candidate";
  if (card.source_id.startsWith("D-TEA")) return "tea_factor_candidate";
  if (card.source_id.startsWith("E-COMP")) return "compliance_rule_candidate";
  if (card.source_id.startsWith("F-MODEL")) return "model_provider_capability_candidate";
  if (card.source_id.startsWith("G-OSS")) return "github_reference_candidate";
  return "bsf_reviewed_metadata_candidate";
}

function defaultReviewBoundary(card: ExternalSourceReviewCard): string {
  const boundaryFields = rawText(
    card.boundary_metadata,
    ["target_boundary_fields", "review_boundary_condition"],
    "",
  );
  if (boundaryFields) return boundaryFields;
  return "Reviewed metadata boundary only; no numeric extraction.";
}

function ensureBlockedUse(value: string): string {
  const required = ["no validated defaults", "no release evidence", "no runtime activation"];
  const lower = value.toLowerCase();
  const missing = required.filter((text) => !lower.includes(text.replace("validated ", "")) && !lower.includes(text));
  const base = value.trim() || "no validated defaults; no release evidence; no runtime activation";
  return missing.length ? `${base}; ${missing.join("; ")}` : base;
}

function ExternalSourcePreviewItem({ source }: { source: ExternalSourceRecord }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-black/10 px-3 py-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-medium text-white">{source.source_id}</p>
          <p className="mt-1 text-xs leading-5 text-surface-400">{source.source_name}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="info">{source.evidence_source_kind}</Badge>
          <Badge variant="neutral">{source.ingestion_mode}</Badge>
        </div>
      </div>
      <div className="mt-3 grid gap-2 text-xs text-surface-400 sm:grid-cols-2">
        <span>{translateText("module")}: {source.bos_module ?? "unmapped"}</span>
        <span>{translateText("category")}: {source.source_category ?? "uncategorized"}</span>
        <span className="sm:col-span-2">{translateText("license")}: {source.license_note ?? "review required"}</span>
        <span className="sm:col-span-2">{translateText("next_action")}: {source.next_action ?? "review required"}</span>
      </div>
    </div>
  );
}

export function FeedstockDatasetCandidateCard({ candidate }: { candidate: FeedstockDatasetCandidate }) {
  return (
    <div className="rounded-2xl border border-amber-300/15 bg-amber-400/8 px-3 py-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-medium text-white">{candidate.source_id}</p>
          <p className="mt-1 text-xs leading-5 text-amber-100/80">{candidate.source_name}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="info">{candidate.source_kind}</Badge>
          <Badge variant="neutral">{candidate.ingestion_mode}</Badge>
          <Badge variant="warning">{candidate.review_status}</Badge>
        </div>
      </div>

      <div className="mt-3 grid gap-2 text-xs text-amber-100/80 sm:grid-cols-2">
        <span>{translateText("candidate_type")}: {candidate.candidate_type}</span>
        <span>{translateText("review_status")}: {candidate.review_status}</span>
        <span>{translateText("license_status")}: pending_review</span>
        <span>{translateText("human_review_required")}: {String(candidate.human_review_required)}</span>
        <span>{translateText("geography")}: {candidate.geography ?? "review required"}</span>
        <span>{translateText("units")}: {candidate.units ?? "review required"}</span>
        <span>{translateText("mapping_confidence")}: {candidate.mapping_confidence}</span>
        <span>{translateText("numeric_values_included")}: {String(candidate.numeric_values_included)}</span>
        <span>{translateText("promotion_enabled")}: false</span>
        <span>{translateText("runtime_activated")}: {String(candidate.runtime_activated)}</span>
        <span>{translateText("validated_default_write_enabled")}: {String(candidate.validated_default_write_enabled)}</span>
        <span className="sm:col-span-2">{translateText("allowed_use")}: source metadata and mapping review only</span>
        <span className="sm:col-span-2">{translateText("blocked_use")}: no composition defaults; no release evidence; no runtime activation</span>
      </div>

      <p className="mt-3 text-xs leading-5 text-amber-100/80">{candidate.waste_proxy_warning}</p>
    </div>
  );
}

function StagedIngestionCard({
  item,
  isPromoting,
  onPromote,
}: {
  item: ReferenceIngestionStagedItem;
  isPromoting: boolean;
  onPromote: () => void;
}) {
  return (
    <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm font-medium text-white">{item.source_title}</p>
          <p className="mt-1 text-xs text-surface-400">{item.source_anchor}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant={item.status === "promoted" ? "success" : "info"}>{item.status}</Badge>
          <Badge variant="neutral">{item.parser_metadata.execution_mode}</Badge>
        </div>
      </div>

      <p className="mt-3 text-sm leading-6 text-surface-300">{item.summary}</p>

      <div className="mt-4 flex flex-wrap gap-2">
        {item.species_chain.map((species) => (
          <Badge key={species} variant="info">{species}</Badge>
        ))}
        {item.feedstocks.map((feedstock) => (
          <Badge key={feedstock} variant="neutral">{feedstock}</Badge>
        ))}
        <Badge variant="brand">{item.evidence_level}</Badge>
        <Badge variant="neutral">{item.campaign_type}</Badge>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <JsonPreview label="Key parameters" value={item.key_parameters} />
        <JsonPreview label="Observed outputs" value={item.observed_outputs} />
      </div>

      {item.parser_metadata.warnings.length ? (
        <div className="mt-4 rounded-2xl border border-amber-300/15 bg-amber-400/8 px-3 py-3 text-xs leading-5 text-amber-100">
          {item.parser_metadata.warnings.join(" ")}
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-surface-500">
          {translateText("Extracted fields")}: {item.parser_metadata.extracted_field_count}
        </p>
        <Button
          type="button"
          size="sm"
          variant={item.status === "promoted" ? "secondary" : "primary"}
          disabled={item.status === "promoted"}
          loading={isPromoting && item.status !== "promoted"}
          onClick={onPromote}
        >
          {item.status === "promoted" ? "Promoted" : "Promote campaign"}
        </Button>
      </div>
    </div>
  );
}

function JsonPreview({ label, value }: { label: string; value: Record<string, unknown> }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/5 px-3 py-3">
      <p className="assistant-section-kicker">{translateText(label)}</p>
      <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs leading-5 text-surface-300">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}
