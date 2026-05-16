import { useMemo, useState } from "react";
import { ArrowRight, BookOpenText, Brain, Sparkles, TrendingUp } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CardBody, CardHeader } from "@/components/ui/Card";
import {
  CockpitGrid,
  CockpitMetric,
  CockpitPanel,
  CockpitSectionLabel,
} from "@/components/ui/Cockpit";
import { ErrorState } from "@/components/ui/EmptyState";
import { SpinnerOverlay } from "@/components/ui/Spinner";
import { SurfaceTile } from "@/components/ui/SurfaceTile";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import { Textarea } from "@/components/ui/Textarea";
import { useBrainRuntime, useUpdateBrainRuntimeDocument } from "@/hooks/useBos";
import { collectApiErrorDetails } from "@/lib/apiError";
import {
  auditBrainRuntimeDocument,
  buildStructuredRuntimeDocument,
  inferBrainRouteFromTarget,
  inferBrainRouteFromText,
  summarizeBrainRuntimeDocuments,
} from "@/lib/brainRuntime";
import { translateText } from "@/lib/i18n";
import { formatDateTime } from "@/lib/utils";
import type { BrainRuntimeDocument } from "@/types/bos";

const TAB_ORDER = ["project_brain", "decision_journal", "evolution_log", "run_ledger"] as const;

export default function BrainDashboardPage() {
  const navigate = useNavigate();
  const brainRuntime = useBrainRuntime();
  const updateBrainRuntime = useUpdateBrainRuntimeDocument();
  const [activeTab, setActiveTab] = useState<string>(TAB_ORDER[0]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const documents = brainRuntime.data?.documents ?? [];
  const documentMap = useMemo(
    () => new Map(documents.map((item) => [item.key, item])),
    [documents],
  );
  const activeDocument = documentMap.get(activeTab) ?? documents[0] ?? null;
  const filledDocuments = documents.filter((item) => !item.is_missing && item.content.trim().length > 0);
  const summary = useMemo(() => summarizeBrainRuntimeDocuments(documents), [documents]);
  const activeDocumentAudit = useMemo(
    () => (activeDocument ? auditBrainRuntimeDocument(activeDocument) : null),
    [activeDocument],
  );
  const activeDraft = activeDocument ? drafts[activeDocument.key] ?? activeDocument.content : "";
  const isDirty = Boolean(activeDocument) && activeDraft !== activeDocument.content;
  const errorDetails = useMemo(
    () =>
      collectApiErrorDetails([
        { label: "Brain runtime", error: brainRuntime.error },
      ]),
    [brainRuntime.error],
  );

  if (brainRuntime.isLoading) {
    return <SpinnerOverlay label="Loading project brain" />;
  }

  if (brainRuntime.isError || !brainRuntime.data) {
    return (
      <ErrorState
        title="Brain dashboard unavailable"
        description="The runtime brain files could not be loaded from the BOS workspace."
        details={errorDetails}
        onRetry={() => brainRuntime.refetch()}
      />
    );
  }

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
              <CockpitSectionLabel>{translateText("BOS / Brain")}</CockpitSectionLabel>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.65rem]">
                {translateText("Brain Dashboard / Evolution Inspector")}
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-surface-300">
                {translateText("Inspect the persistent project brain, decision journal, and growth heuristics that power the autonomy loop.")}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="brand">{translateText("Persistent memory")}</Badge>
              <Badge variant="info">{translateText("Autonomy aware")}</Badge>
              <Button
                variant="secondary"
                leftIcon={<ArrowRight className="h-4 w-4" />}
                onClick={() => navigate("/bos/orchestrator")}
              >
                {translateText("Open orchestrator")}
              </Button>
              <Button
                variant="outline"
                leftIcon={<ArrowRight className="h-4 w-4" />}
                onClick={() => navigate("/bos/signal-lab")}
              >
                {translateText("Open signal lab")}
              </Button>
            </div>
          </div>

          <CockpitGrid className="sm:grid-cols-2 xl:grid-cols-4">
            <CockpitMetric label={translateText("Documents")} value={String(documents.length)} hint={translateText(`${filledDocuments.length} populated`)} accent="cyan" />
            <CockpitMetric label={translateText("Total lines")} value={String(brainRuntime.data.total_line_count)} hint={translateText("Loaded from runtime memory")} accent="violet" />
            <CockpitMetric label={translateText("Runtime root")} value={brainRuntime.data.root_path} hint={translateText("Repo-local memory area")} accent="amber" />
            <CockpitMetric
              label={translateText("Last updated")}
              value={brainRuntime.data.last_updated_at ? formatDateTime(brainRuntime.data.last_updated_at) : "N/A"}
              hint={translateText("Most recent memory write")}
              accent="neutral"
            />
          </CockpitGrid>
        </div>
      </CockpitPanel>

      <CockpitPanel className="p-5 lg:p-6">
        <div>
          <CockpitSectionLabel>{translateText("Runtime memory surfaces")}</CockpitSectionLabel>
          <p className="mt-3 text-sm leading-7 text-surface-300">
            {translateText("Switch between durable project memory, chronological decisions, and learned heuristics.")}
          </p>
        </div>
        <div className="mt-5">
          <Tabs
            tabs={TAB_ORDER.map((tabId) => {
              const doc = documentMap.get(tabId);
              return {
                id: tabId,
                label: doc?.title ?? tabId,
                icon:
                  tabId === "project_brain" ? (
                    <Brain className="h-4 w-4" />
                  ) : tabId === "decision_journal" ? (
                    <BookOpenText className="h-4 w-4" />
                  ) : tabId === "run_ledger" ? (
                    <Sparkles className="h-4 w-4" />
                  ) : (
                    <TrendingUp className="h-4 w-4" />
                  ),
                count: doc?.line_count ?? 0,
              };
            })}
            activeTab={activeTab}
            onChange={setActiveTab}
          />
        </div>
      </CockpitPanel>

      <CockpitPanel tone="emphasis" className="p-5 lg:p-6">
        <div className="space-y-5">
          {TAB_ORDER.map((tabId) => {
            const document = documentMap.get(tabId);
            return (
              <TabPanel key={tabId} tabId={tabId} activeTab={activeTab}>
                <BrainDocumentPanel
                  document={document ?? null}
                  audit={document ? auditBrainRuntimeDocument(document) : null}
                  draftValue={document ? drafts[document.key] ?? document.content : ""}
                  onDraftChange={(value) => {
                    if (!document) return;
                    setDrafts((current) => ({ ...current, [document.key]: value }));
                  }}
                />
              </TabPanel>
            );
          })}
        </div>
      </CockpitPanel>

      {activeDocument ? (
        <CockpitPanel className="p-5 lg:p-6">
          <CardHeader
            title="Editor controls"
            description="Edit the active runtime document and write it back to the autonomy memory area."
          />
          <CardBody className="flex flex-wrap gap-3">
            <Button
              onClick={() => {
                if (!activeDocument) return;
                updateBrainRuntime.mutate({
                  documentKey: activeDocument.key,
                  payload: { content: activeDraft },
                });
              }}
              loading={updateBrainRuntime.isPending}
              disabled={!isDirty || updateBrainRuntime.isPending}
            >
              Save changes
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                if (!activeDocument) return;
                setDrafts((current) => ({ ...current, [activeDocument.key]: activeDocument.content }));
              }}
              disabled={!isDirty}
            >
              Reset draft
            </Button>
            <Button variant="outline" onClick={() => void brainRuntime.refetch()}>
              Refresh runtime
            </Button>
            {activeDocument ? (
              <Button
                variant="outline"
                onClick={() => {
                  setDrafts((current) => ({
                    ...current,
                    [activeDocument.key]: buildStructuredRuntimeDocument(activeDocument.key, activeDraft),
                  }));
                }}
              >
                Repair structure
              </Button>
            ) : null}
          </CardBody>
        </CockpitPanel>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <CockpitPanel className="p-5 lg:p-6">
          <CardHeader
            title="Inspector summary"
            description="A fast operator read of what the autonomy loop is carrying forward."
          />
          <CardBody className="space-y-4">
            <SummaryListCard
              title="Current focus"
              items={summary.currentFocus}
              empty="No current focus has been written into the project brain yet."
            />
            <SummaryListCard
              title="Next slices"
              items={summary.nextSlices}
              empty="No next slices are recorded yet."
            />
            <SummaryListCard
              title="Recent decisions"
              items={summary.recentDecisions}
              empty="No decision entries are available yet."
            />
            <SummaryListCard
              title="Active heuristics"
              items={summary.activeHeuristics}
              empty="No active heuristics have been recorded yet."
            />
            <SummaryListCard
              title="Latest autonomous run"
              items={summary.latestRun}
              empty="No autonomous run has been recorded yet."
            />
            <SurfaceTile>
              <p className="assistant-section-kicker">{translateText("Run artifact quality")}</p>
              <p className="mt-3 text-sm font-medium text-white">
                {translateText(summary.latestRunAudit.isComplete ? "Complete" : "Incomplete")}
              </p>
              {!summary.latestRunAudit.isComplete ? (
                <p className="mt-2 text-sm leading-6 text-surface-400">
                  {translateText("Missing fields:")} {summary.latestRunAudit.missingFields.join(", ")}
                </p>
              ) : (
                <p className="mt-2 text-sm leading-6 text-surface-400">
                  {translateText("Latest run captured all expected fields.")}
                </p>
              )}
            </SurfaceTile>
          </CardBody>
        </CockpitPanel>

        <CockpitPanel className="p-5 lg:p-6">
          <CardHeader
            title="What this means"
            description="How the runtime files map to the autonomy stack."
          />
          <CardBody className="space-y-3">
            <InsightCard
              icon={<Brain className="h-4 w-4" />}
              title="Project brain"
              body="Stable repo truths, current mission, and known pitfalls that should be loaded before each autonomous run."
            />
            <InsightCard
              icon={<BookOpenText className="h-4 w-4" />}
              title="Decision journal"
              body="Chronological reasoning trace for why a slice, constraint, or plan changed over time."
            />
            <InsightCard
              icon={<Sparkles className="h-4 w-4" />}
              title="Evolution log"
              body="Small verified heuristics extracted from real runs so the next cycle starts smarter, not just longer."
            />
            <SummaryListCard
              title="Stable facts"
              items={summary.stableFacts}
              empty="No stable facts have been written yet."
            />
            <SummaryListCard
              title="Repeated pitfalls"
              items={summary.repeatedPitfalls}
              empty="No repeated pitfalls are tracked yet."
            />
            <SummaryListCard
              title="Recent learnings"
              items={summary.recentLearnings}
              empty="No recent learnings are available yet."
            />
          </CardBody>
        </CockpitPanel>
      </div>

      <CockpitPanel className="p-5 lg:p-6">
        <CardHeader
          title="Recent autonomous runs"
          description="Structured run history from the autonomy ledger, showing what the loop worked on and how it ended."
        />
        <CardBody className="space-y-3">
          {summary.recentRunDetails.length ? (
            summary.recentRunDetails.map((run, index) => {
              const route =
                inferBrainRouteFromTarget(run.targetSurface, run.targetId, run.targetRoute) ??
                inferBrainRouteFromText([run.slice, run.note].filter(Boolean).join(" "));
              return (
              <SurfaceTile key={`${run.when ?? "run"}-${index}`}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="assistant-section-kicker">Run {index + 1}</p>
                    <p className="mt-2 text-sm font-medium text-white">{run.slice ?? "Unknown slice"}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-surface-400">{run.when ?? "Unknown time"}</p>
                    <p className="mt-1 text-sm text-white">{run.outcome ?? "Unknown outcome"}</p>
                  </div>
                </div>
                {run.note ? (
                  <p className="mt-3 text-sm leading-6 text-surface-300">{run.note}</p>
                ) : null}
                {route ? (
                  <div className="mt-3">
                    <Button
                      variant="outline"
                      leftIcon={<ArrowRight className="h-4 w-4" />}
                      onClick={() => navigate(route.to)}
                    >
                      {translateText("Open")} {translateText(route.label)}
                    </Button>
                  </div>
                ) : null}
              </SurfaceTile>
            )})
          ) : (
            <div className="rounded-2xl border border-dashed border-white/10 bg-white/3 px-4 py-8 text-center text-sm text-surface-400">
              {translateText("No recent autonomous runs are available yet.")}
            </div>
          )}
        </CardBody>
      </CockpitPanel>

      {activeDocument ? (
        <CockpitPanel className="p-5 lg:p-6">
          <CardHeader
            title="Active document metadata"
            description="Current tab path, timestamp, and load state."
          />
          <CardBody className="grid gap-4 sm:grid-cols-3">
            <MetaTile label="Relative path" value={activeDocument.relative_path} />
            <MetaTile
              label="Updated"
              value={activeDocument.updated_at ? formatDateTime(activeDocument.updated_at) : "N/A"}
            />
            <MetaTile
              label="Load state"
              value={
                activeDocument.is_missing
                  ? "Missing"
                  : activeDocumentAudit?.isStructured
                    ? "Structured"
                    : "Needs cleanup"
              }
            />
          </CardBody>
        </CockpitPanel>
      ) : null}
    </div>
  );
}

function BrainDocumentPanel({
  document,
  audit,
  draftValue,
  onDraftChange,
}: {
  document: BrainRuntimeDocument | null;
  audit: ReturnType<typeof auditBrainRuntimeDocument> | null;
  draftValue: string;
  onDraftChange: (value: string) => void;
}) {
  if (!document) {
    return (
      <div className="rounded-3xl border border-dashed border-white/10 bg-white/3 px-4 py-8 text-center text-sm text-surface-400">
        {translateText("No runtime document is available for this tab.")}
      </div>
    );
  }

  if (document.is_missing) {
    return (
      <div className="rounded-3xl border border-dashed border-white/10 bg-white/3 px-4 py-8 text-center text-sm text-surface-400">
        {translateText(document.title)} {translateText("does not exist yet at")} {document.relative_path}.
      </div>
    );
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
      <CockpitPanel className="p-5 lg:p-6">
        <CardHeader
          title={document.title}
          description="Edit the runtime memory directly, then save it back into the autonomy loop."
        />
        <CardBody>
          <Textarea
            value={draftValue}
            onChange={(event) => onDraftChange(event.target.value)}
            autoResize
            rows={18}
            helperText="Keep memory compact and durable. Prefer concise bullets over long transcripts."
          />
        </CardBody>
      </CockpitPanel>

      <CockpitPanel className="p-5 lg:p-6">
        <CardHeader
          title="Content structure"
          description="A quick structural read so the operator can tell whether the memory is becoming richer."
        />
        <CardBody className="space-y-4">
          <MetaTile label="Headings" value={countMatches(document.content, /^#+\s+/gm).toString()} />
          <MetaTile label="Bullets" value={countMatches(document.content, /^-\s+/gm).toString()} />
          <MetaTile label="Code fences" value={countMatches(document.content, /^```/gm).toString()} />
          <MetaTile
            label="Structure status"
            value={audit?.isStructured ? "Required headings intact" : "Missing or drifted"}
          />
          {!audit?.isStructured ? (
            <>
              <SummaryListCard
                title="Missing headings"
                items={audit?.missingHeadings ?? []}
                empty="No required headings are missing."
              />
              <SummaryListCard
                title="Unexpected headings"
                items={audit?.unexpectedHeadings ?? []}
                empty="No unexpected headings were found."
              />
              <SummaryListCard
                title="Invalid lines"
                items={audit?.invalidLines ?? []}
                empty="No invalid lines were found."
              />
            </>
          ) : null}
          <SurfaceTile>
            <p className="assistant-section-kicker">Preview</p>
            <p className="mt-3 text-sm leading-7 text-surface-300">
              {draftValue.trim().slice(0, 320) || "No preview available."}
              {draftValue.trim().length > 320 ? "..." : ""}
            </p>
          </SurfaceTile>
        </CardBody>
      </CockpitPanel>
    </div>
  );
}

function InsightCard({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <SurfaceTile>
      <div className="flex items-center gap-2 text-brand-200">
        {icon}
        <p className="assistant-section-kicker !text-surface-300">{translateText(title)}</p>
      </div>
      <p className="mt-3 text-sm leading-6 text-surface-300">{translateText(body)}</p>
    </SurfaceTile>
  );
}

function SummaryListCard({
  title,
  items,
  empty,
}: {
  title: string;
  items: string[];
  empty: string;
}) {
  return (
    <SurfaceTile>
      <p className="assistant-section-kicker">{translateText(title)}</p>
      {items.length ? (
        <ul className="mt-3 space-y-2">
          {items.map((item) => (
            <li key={item} className="text-sm leading-6 text-surface-300">
              - {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm leading-6 text-surface-400">{translateText(empty)}</p>
      )}
    </SurfaceTile>
  );
}

function MetaTile({ label, value }: { label: string; value: string }) {
  return (
    <SurfaceTile>
      <p className="assistant-section-kicker">{translateText(label)}</p>
      <p className="mt-3 text-sm font-medium text-white break-all">{value}</p>
    </SurfaceTile>
  );
}

function countMatches(content: string, pattern: RegExp) {
  return content.match(pattern)?.length ?? 0;
}
