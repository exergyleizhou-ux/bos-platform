import { Search, RefreshCcw } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CardBody, CardHeader } from "@/components/ui/Card";
import { CockpitPanel } from "@/components/ui/Cockpit";
import { translateText } from "@/lib/i18n";
import type { CodeMemorySnapshot, CodeSessionSearchResult } from "@/types/code";

interface CodeMemoryPanelProps {
  snapshots?: CodeMemorySnapshot[];
  searchResults?: CodeSessionSearchResult[];
  refreshing?: boolean;
  onRefresh?: () => void;
}

export function CodeMemoryPanel({
  snapshots,
  searchResults,
  refreshing,
  onRefresh,
}: CodeMemoryPanelProps) {
  const latest = snapshots?.[0] ?? null;

  return (
    <CockpitPanel className="p-5 lg:p-6">
      <CardHeader
        title={translateText("Memory + Recall")}
        description={translateText("Context compression, snapshot carry-forward, and cross-session recall for BOS Code.")}
        action={
          onRefresh ? (
            <Button size="sm" variant="ghost" loading={refreshing} leftIcon={<RefreshCcw className="h-4 w-4" />} onClick={onRefresh}>
              {translateText("Refresh memory")}
            </Button>
          ) : undefined
        }
      />
      <CardBody className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
        <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-white">{translateText("Latest Snapshot")}</p>
            <Badge variant="neutral">{snapshots?.length ?? 0} {translateText("total")}</Badge>
          </div>
          {latest ? (
            <div className="mt-3 space-y-3">
              <div className="flex flex-wrap gap-2">
                <Badge variant="brand">{latest.snapshot_kind}</Badge>
                <Badge variant="neutral">
                  turns {latest.source_turn_start ?? "?"}-{latest.source_turn_end ?? "?"}
                </Badge>
              </div>
              <pre className="overflow-x-auto whitespace-pre-wrap rounded-2xl border border-white/8 bg-surface-950/70 px-4 py-4 text-sm leading-6 text-surface-300">
                {latest.summary_markdown}
              </pre>
            </div>
          ) : (
            <p className="mt-3 text-sm text-surface-400">{translateText("No memory snapshot yet.")}</p>
          )}
        </div>

        <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
          <div className="flex items-center gap-2">
            <Search className="h-4 w-4 text-sky-300" />
            <p className="text-sm font-semibold text-white">{translateText("Cross-Session Recall")}</p>
          </div>
          <div className="mt-3 space-y-3">
            {(searchResults ?? []).length ? (
              searchResults?.map((result) => (
                <div key={result.session_id} className="rounded-2xl border border-white/8 bg-white/4 px-3 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-white">{translateText("Session")} #{result.session_id}</p>
                    <Badge variant="info">{result.score.toFixed(1)}</Badge>
                  </div>
                  <p className="mt-2 text-sm text-surface-200">{result.headline}</p>
                  <p className="mt-2 text-sm leading-6 text-surface-400">{result.summary}</p>
                </div>
              ))
            ) : (
              <p className="text-sm text-surface-400">{translateText("Cross-session search results will appear here once a query is available.")}</p>
            )}
          </div>
        </div>
      </CardBody>
    </CockpitPanel>
  );
}
