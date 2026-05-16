import { ActivitySquare } from "lucide-react";

import { SupervisorHistoryChart } from "@/components/charts/SupervisorHistoryChart";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { translateText } from "@/lib/i18n";
import type { SupervisorSnapshot } from "@/types/bos";

interface SupervisorHistoryCardProps {
  history?: SupervisorSnapshot[] | null;
  title?: string;
  description?: string;
}

export function SupervisorHistoryCard({
  history,
  title = "Supervisor history",
  description = "Recent causal observations and BOS supervisor decisions for this signal.",
}: SupervisorHistoryCardProps) {
  const usableHistory = (history ?? []).filter((item) => item?.recorded_at);

  return (
    <Card className="assistant-aside-card rounded-[28px]">
      <CardHeader title={title} description={description} />
      <CardBody className="space-y-4">
        {usableHistory.length ? (
          <>
            <div className="assistant-thread-shell rounded-3xl border border-white/8 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="info">{translateText(`${usableHistory.length} observations`)}</Badge>
                <Badge variant="neutral">
                  {translateText(`Latest mode ${usableHistory.at(-1)?.mode ?? "unknown"}`)}
                </Badge>
              </div>
              <p className="mt-3 text-sm leading-6 text-surface-300">
                {translateText(
                  "Use this trend to understand whether the signal is stabilizing, improving in observability, or tipping into a persistent negative slope.",
                )}
              </p>
            </div>

            <SupervisorHistoryChart history={usableHistory} />
          </>
        ) : (
          <div className="assistant-aside-card rounded-3xl border border-dashed border-white/10 bg-white/3 px-4 py-8 text-center text-sm text-surface-400">
            <div className="mb-3 flex justify-center text-brand-200">
              <ActivitySquare className="h-5 w-5" />
            </div>
            {translateText("No supervisor history has been recorded yet.")}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
