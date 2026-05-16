import { ArrowRight, Brain, Sparkles, TrendingUp } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { CardBody, CardHeader } from "@/components/ui/Card";
import { CockpitPanel } from "@/components/ui/Cockpit";
import { SurfaceTile } from "@/components/ui/SurfaceTile";
import { Spinner } from "@/components/ui/Spinner";
import { useBrainRuntime } from "@/hooks/useBos";
import { translateText } from "@/lib/i18n";
import {
  derivePriorityAction,
  inferBrainRouteFromTarget,
  summarizeBrainRuntimeDocuments,
} from "@/lib/brainRuntime";

interface BrainOperatorContextCardProps {
  title?: string;
  description?: string;
  compact?: boolean;
  mode?: "default" | "dashboard" | "release" | "signal" | "assistant" | "orchestrator";
}

export function BrainOperatorContextCard({
  title = "Autonomy context",
  description = "What the project brain thinks matters now, before you dive into the next surface.",
  compact = false,
  mode = "default",
}: BrainOperatorContextCardProps) {
  const navigate = useNavigate();
  const brainRuntime = useBrainRuntime();

  if (brainRuntime.isLoading) {
    return (
        <CockpitPanel className="p-5 lg:p-6">
        <CardHeader title={title} description={description} />
        <CardBody className="flex items-center gap-3 text-sm text-surface-400">
          <Spinner size="sm" />
          {translateText("Loading autonomy context...")}
        </CardBody>
      </CockpitPanel>
    );
  }

  if (brainRuntime.isError || !brainRuntime.data) {
    return null;
  }

  const summary = summarizeBrainRuntimeDocuments(brainRuntime.data.documents);
  const view = getModeView(summary, mode);
  const priorityAction = derivePriorityAction(summary, mode);
  const latestRunRoute =
    inferBrainRouteFromTarget(
      summary.latestRunDetail.targetSurface,
      summary.latestRunDetail.targetId,
      summary.latestRunDetail.targetRoute,
    ) ??
    inferRouteFromText([
      summary.latestRunDetail.slice,
      summary.latestRunDetail.nextStep,
      ...summary.latestRun,
    ].filter(Boolean).join(" "));
  const suggestedRoutes = buildSuggestedRoutes([
    ...summary.currentFocus,
    ...summary.nextSlices,
    ...summary.latestRun,
  ]);
  const modeActions = getModeActions(mode);

  return (
    <CockpitPanel className="p-5 lg:p-6">
      <CardHeader title={title} description={description} />
      <CardBody className="space-y-4">
        <div className={`grid gap-4 ${compact ? "xl:grid-cols-4" : "xl:grid-cols-2"}`}>
          <SummaryBlock
            icon={<Brain className="h-4 w-4" />}
            title={view.primaryTitle}
            items={view.primaryItems}
            empty={view.primaryEmpty}
          />
          <SummaryBlock
            icon={<TrendingUp className="h-4 w-4" />}
            title={view.secondaryTitle}
            items={view.secondaryItems}
            empty={view.secondaryEmpty}
          />
          <SummaryBlock
            icon={<Sparkles className="h-4 w-4" />}
            title={view.tertiaryTitle}
            items={view.tertiaryItems}
            empty={view.tertiaryEmpty}
          />
          <SummaryBlock
            icon={<TrendingUp className="h-4 w-4" />}
            title="Latest autonomous run"
            items={summary.latestRun}
            empty="No autonomous run summary has been recorded yet."
          />
        </div>

        {summary.latestRunDetail.slice || summary.latestRunDetail.outcome ? (
          <SurfaceTile>
            <p className="assistant-section-kicker !text-surface-300">{translateText("Run inspector")}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${summary.latestRunAudit.isComplete ? "border border-emerald-400/18 bg-emerald-500/12 text-emerald-100" : "border border-amber-400/18 bg-amber-500/12 text-amber-100"}`}>
                {summary.latestRunAudit.isComplete
                  ? translateText("Run artifact complete")
                  : translateText("Run artifact incomplete")}
              </span>
              {!summary.latestRunAudit.isComplete ? (
                <span className="inline-flex items-center rounded-full border border-white/8 bg-white/5 px-2 py-1 text-xs text-surface-300">
                  {translateText("Missing:")} {summary.latestRunAudit.missingFields.join(", ")}
                </span>
              ) : null}
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <RunMetaTile label={translateText("Slice")} value={summary.latestRunDetail.slice ?? "N/A"} />
              <RunMetaTile label={translateText("Outcome")} value={summary.latestRunDetail.outcome ?? "N/A"} />
              <RunMetaTile label={translateText("Verification")} value={summary.latestRunDetail.verification ?? "N/A"} />
              <RunMetaTile label={translateText("Remaining risk")} value={summary.latestRunDetail.remainingRisk ?? "N/A"} />
            </div>
            {summary.latestRunDetail.nextStep ? (
              <p className="mt-3 text-sm leading-6 text-surface-300">
                {translateText("Next step:")} {summary.latestRunDetail.nextStep}
              </p>
            ) : null}
            {latestRunRoute ? (
              <div className="mt-3">
                <Button
                variant="outline"
                leftIcon={<ArrowRight className="h-4 w-4" />}
                onClick={() => navigate(latestRunRoute.to)}
              >
                {translateText("Open")} {latestRunRoute.label}
              </Button>
            </div>
          ) : null}
          </SurfaceTile>
        ) : null}

        {priorityAction ? (
          <SurfaceTile tone="brand">
            <p className="assistant-section-kicker !text-brand-200">{translateText("Priority action")}</p>
            <p className="mt-3 text-sm leading-6 text-surface-200">{priorityAction.reason}</p>
            <div className="mt-4">
              <Button
                leftIcon={<ArrowRight className="h-4 w-4" />}
                onClick={() => navigate(priorityAction.to)}
              >
                {priorityAction.label}
              </Button>
            </div>
          </SurfaceTile>
        ) : null}

        <div className="flex flex-wrap gap-3">
          <Button
            variant="secondary"
            leftIcon={<ArrowRight className="h-4 w-4" />}
            onClick={() => navigate("/bos/brain")}
          >
            {translateText("Open brain dashboard")}
          </Button>
          <Button
            variant="outline"
            leftIcon={<ArrowRight className="h-4 w-4" />}
            onClick={() => navigate("/bos/orchestrator")}
          >
            {translateText("Open orchestrator")}
          </Button>
          {modeActions.map((action) => (
            <Button
              key={action.to}
              variant="outline"
              leftIcon={<ArrowRight className="h-4 w-4" />}
              onClick={() => navigate(action.to)}
            >
              {translateText(action.label)}
            </Button>
          ))}
        </div>

        {suggestedRoutes.length ? (
          <SurfaceTile>
            <p className="assistant-section-kicker !text-surface-300">{translateText("Suggested surfaces")}</p>
            <div className="mt-3 flex flex-wrap gap-3">
              {suggestedRoutes.map((route) => (
                <Button
                  key={route.to}
                  variant="outline"
                  leftIcon={<ArrowRight className="h-4 w-4" />}
                  onClick={() => navigate(route.to)}
                >
                  {translateText(route.label)}
                </Button>
              ))}
            </div>
          </SurfaceTile>
        ) : null}
      </CardBody>
    </CockpitPanel>
  );
}

function SummaryBlock({
  icon,
  title,
  items,
  empty,
}: {
  icon: React.ReactNode;
  title: string;
  items: string[];
  empty: string;
}) {
  return (
    <SurfaceTile>
      <div className="flex items-center gap-2 text-brand-200">
        {icon}
        <p className="assistant-section-kicker !text-surface-300">{translateText(title)}</p>
      </div>
      {items.length ? (
        <ul className="mt-3 space-y-2">
          {items.slice(0, 3).map((item) => (
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

function getModeView(
  summary: ReturnType<typeof summarizeBrainRuntimeDocuments>,
  mode: "default" | "dashboard" | "release" | "signal" | "assistant" | "orchestrator",
) {
  if (mode === "dashboard") {
    return {
      primaryTitle: "Current focus",
      primaryItems: summary.currentFocus,
      primaryEmpty: "No current focus is written yet.",
      secondaryTitle: "Next slices",
      secondaryItems: summary.nextSlices,
      secondaryEmpty: "No next slices are queued yet.",
      tertiaryTitle: "Active heuristics",
      tertiaryItems: summary.activeHeuristics,
      tertiaryEmpty: "No active heuristics are recorded yet.",
    };
  }

  if (mode === "release") {
    return {
      primaryTitle: "Release-adjacent focus",
      primaryItems: filterItems(summary.currentFocus, /(release|verify|verification|trust|gate|dossier|risk)/),
      primaryEmpty: "No release-focused item is written yet.",
      secondaryTitle: "Recent decisions",
      secondaryItems: filterItems(summary.recentDecisions, /(release|verify|verification|trust|gate|dossier|risk)/),
      secondaryEmpty: "No release-adjacent decision is recorded yet.",
      tertiaryTitle: "Active heuristics",
      tertiaryItems: summary.activeHeuristics,
      tertiaryEmpty: "No active heuristics are recorded yet.",
    };
  }

  if (mode === "signal") {
    return {
      primaryTitle: "Signal-adjacent focus",
      primaryItems: filterItems(summary.currentFocus, /(signal|handover|mtt|hal|executor|locality|portability|control)/),
      primaryEmpty: "No signal-focused item is written yet.",
      secondaryTitle: "Next lab slices",
      secondaryItems: filterItems(summary.nextSlices, /(signal|handover|mtt|hal|executor|locality|portability|control)/),
      secondaryEmpty: "No signal-lab slice is queued yet.",
      tertiaryTitle: "Active heuristics",
      tertiaryItems: summary.activeHeuristics,
      tertiaryEmpty: "No active heuristics are recorded yet.",
    };
  }

  if (mode === "assistant") {
    return {
      primaryTitle: "Thread focus",
      primaryItems: summary.currentFocus,
      primaryEmpty: "No thread focus is written yet.",
      secondaryTitle: "Recent decisions",
      secondaryItems: summary.recentDecisions,
      secondaryEmpty: "No recent decision is recorded yet.",
      tertiaryTitle: "Active heuristics",
      tertiaryItems: summary.activeHeuristics,
      tertiaryEmpty: "No active heuristics are recorded yet.",
    };
  }

  if (mode === "orchestrator") {
    return {
      primaryTitle: "Orchestration focus",
      primaryItems: summary.nextSlices,
      primaryEmpty: "No orchestration slice is queued yet.",
      secondaryTitle: "Recent decisions",
      secondaryItems: summary.recentDecisions,
      secondaryEmpty: "No orchestration decision is recorded yet.",
      tertiaryTitle: "Recent learnings",
      tertiaryItems: summary.recentLearnings,
      tertiaryEmpty: "No recent learning is recorded yet.",
    };
  }

  return {
    primaryTitle: "Current focus",
    primaryItems: summary.currentFocus,
    primaryEmpty: "No current focus is written yet.",
    secondaryTitle: "Next slices",
    secondaryItems: summary.nextSlices,
    secondaryEmpty: "No next slices are queued yet.",
    tertiaryTitle: "Active heuristics",
    tertiaryItems: summary.activeHeuristics,
    tertiaryEmpty: "No active heuristics are recorded yet.",
  };
}

function filterItems(items: string[], pattern: RegExp) {
  const filtered = items.filter((item) => pattern.test(item.toLowerCase()));
  return filtered.length ? filtered : items;
}

function getModeActions(mode: "default" | "dashboard" | "release" | "signal" | "assistant" | "orchestrator") {
  if (mode === "dashboard") {
    return [
      { to: "/dashboard", label: "Open executive overview" },
      { to: "/batches", label: "Open batch command" },
    ];
  }

  if (mode === "release") {
    return [
      { to: "/release", label: "Open release center" },
      { to: "/bos/console", label: "Open decision console" },
    ];
  }

  if (mode === "signal") {
    return [
      { to: "/bos/signal-lab", label: "Open signal lab" },
      { to: "/batches", label: "Open batch command" },
    ];
  }

  if (mode === "assistant") {
    return [
      { to: "/bos", label: "Open assistant thread" },
      { to: "/bos/console", label: "Open decision console" },
    ];
  }

  if (mode === "orchestrator") {
    return [
      { to: "/bos/orchestrator", label: "Open orchestrator" },
      { to: "/bos/brain", label: "Open brain dashboard" },
    ];
  }

  return [];
}

function buildSuggestedRoutes(items: string[]) {
  const rules = [
    { when: /(signal|handover|mtt|hal|portability|executor|locality)/, to: "/bos/signal-lab", label: "Signal Lab" },
    { when: /(release|verification|dossier|trust|gate)/, to: "/release", label: "Release Center" },
    { when: /(brain|memory|evolution|heuristic)/, to: "/bos/brain", label: "Brain Dashboard" },
    { when: /(batch|feedstock|operator surface|command center)/, to: "/batches", label: "Batch Command" },
    { when: /(forecast|trend|drift)/, to: "/forecast", label: "Forecast" },
    { when: /(twin|scenario)/, to: "/twins", label: "Digital Twins" },
    { when: /(dashboard|overview|executive)/, to: "/dashboard", label: "Executive Overview" },
  ];

  const haystack = items.join(" ").toLowerCase();
  return rules.filter((rule) => rule.when.test(haystack)).slice(0, 4);
}

function inferRouteFromText(text: string) {
  const signalLabContextMatch = /\bbatch\s+(\d+)\b.*\bsignal\b/i.exec(text);
  if (signalLabContextMatch) {
    const batchId = signalLabContextMatch[1];
    return {
      to: `/bos/signal-lab?batchId=${batchId}`,
      label: `${translateText("Signal Lab for Batch")} ${batchId}`,
    };
  }

  const batchMatch = /\bbatch\s+(\d+)\b/i.exec(text);
  if (batchMatch) {
    return {
      to: `/batches/${batchMatch[1]}`,
      label: `${translateText("Batch")} ${batchMatch[1]}`,
    };
  }

  const auditPacketMatch = /\baudit\s+packet\s+(\d+)\b/i.exec(text);
  if (auditPacketMatch) {
    return {
      to: `/bos/console?auditPacketId=${auditPacketMatch[1]}`,
      label: `${translateText("Audit Packet")} ${auditPacketMatch[1]}`,
    };
  }

  const releaseSignalMatch = /\brelease\b.*\bsignal\b/i.exec(text);
  if (releaseSignalMatch) {
    return {
      to: "/bos/signal-lab",
      label: "Signal Lab",
    };
  }

  return buildSuggestedRoutes([text])[0] ?? null;
}

function RunMetaTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-surface-900/70 px-4 py-3">
      <p className="assistant-section-kicker !text-surface-500">{label}</p>
      <p className="mt-2 text-sm font-medium text-white">{value}</p>
    </div>
  );
}
