import { AlertTriangle, CheckCircle2, Lightbulb } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { SurfaceTile } from "@/components/ui/SurfaceTile";
import { translateText } from "@/lib/i18n";

export interface NextBestActionItem {
  code: string;
  title: string;
  message: string;
  recommendedAction: string;
  severity: "info" | "warning" | "critical";
  blocking: boolean;
  actionIntent?: string;
  actionLabel?: string;
}

interface NextBestActionsCardProps {
  items: NextBestActionItem[];
  isLoading?: boolean;
  onAction?: (item: NextBestActionItem) => void;
}

export function NextBestActionsCard({
  items,
  isLoading = false,
  onAction,
}: NextBestActionsCardProps) {
  return (
    <Card className="assistant-aside-card rounded-[28px]">
      <CardHeader
        title="Next Best Actions"
        description="Summarize the next highest-leverage release actions in one operator-facing list."
      />
      <CardBody className="space-y-3">
        {items.length ? (
          items.slice(0, 3).map((item) => (
            <div
              key={item.code}
              className="assistant-thread-shell rounded-3xl border border-white/8 p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 gap-3">
                  <div className={iconShellClassName(item.severity)}>
                    {item.blocking ? (
                      <AlertTriangle className="h-4 w-4" />
                    ) : item.severity === "info" ? (
                      <Lightbulb className="h-4 w-4" />
                    ) : (
                      <CheckCircle2 className="h-4 w-4" />
                    )}
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-white">{translateText(item.title)}</p>
                    <p className="mt-2 text-sm leading-6 text-surface-300">{translateText(item.message)}</p>
                  </div>
                </div>
                <div className="flex flex-col items-end gap-2">
                  <Badge variant={badgeVariant(item.severity)}>
                    {severityLabel(item.severity)}
                  </Badge>
                  {item.blocking ? <Badge variant="danger">Blocking</Badge> : null}
                </div>
              </div>
              <div className="assistant-meta-panel mt-4 rounded-2xl border border-brand-300/15 bg-brand-500/10 px-4 py-3">
                <p className="assistant-section-kicker !text-brand-100/80">
                  Recommended Action
                </p>
                <p className="mt-2 text-sm font-medium text-brand-50">{translateText(item.recommendedAction)}</p>
                {item.actionLabel && onAction ? (
                  <div className="mt-3 flex justify-end">
                    <Button size="sm" variant="secondary" onClick={() => onAction(item)}>
                      {translateText(item.actionLabel)}
                    </Button>
                  </div>
                ) : null}
              </div>
            </div>
          ))
        ) : (
          <SurfaceTile className="rounded-3xl border-dashed border-white/10 bg-white/3 px-4 py-8 text-center text-sm text-surface-400">
            {isLoading
              ? translateText("Compiling next-best actions...")
              : translateText("No additional actions are recommended right now. You can continue reviewing release, signal, and audit evidence.")}
          </SurfaceTile>
        )}
      </CardBody>
    </Card>
  );
}

function badgeVariant(severity: NextBestActionItem["severity"]) {
  if (severity === "critical") return "danger" as const;
  if (severity === "warning") return "warning" as const;
  return "info" as const;
}

function severityLabel(severity: NextBestActionItem["severity"]) {
  if (severity === "critical") return "High";
  if (severity === "warning") return "Watch";
  return "Info";
}

function iconShellClassName(severity: NextBestActionItem["severity"]) {
  if (severity === "critical") {
    return "mt-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-2xl border border-red-400/18 bg-red-500/12 text-red-100";
  }
  if (severity === "warning") {
    return "mt-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-2xl border border-amber-400/18 bg-amber-500/12 text-amber-100";
  }
  return "mt-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-2xl border border-sky-400/18 bg-sky-500/12 text-sky-100";
}
