import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { translateText } from "@/lib/i18n";
import type { PortabilityRecommendationResponse } from "@/types/bos";
import { formatNumber, formatPercent } from "@/lib/utils";

interface PortabilityRecommendationCardProps {
  recommendation?: PortabilityRecommendationResponse;
  isLoading?: boolean;
  emptyMessage?: string;
}

export function PortabilityRecommendationCard({
  recommendation,
  isLoading = false,
  emptyMessage = "Select a signal and executor to preview the recommendation here.",
}: PortabilityRecommendationCardProps) {
  return (
    <Card className="assistant-aside-card rounded-[28px]">
      <CardHeader
        title="Current portability posture"
        description="Lead with the readable posture, rationale, and next action before diving into detailed evidence."
      />
      <CardBody className="space-y-4">
        {recommendation ? (
          <>
            <div className="assistant-thread-shell rounded-3xl border border-white/8 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={recommendationVariant(recommendation.recommended_outcome)}>
                  {humanizeRecommendation(recommendation.recommended_outcome)}
                </Badge>
                {recommendation.requires_requalification ? (
                  <Badge variant="danger">Requalification required</Badge>
                ) : null}
                {recommendation.override_outcome ? (
                  <Badge variant="warning">Override: {recommendation.override_outcome}</Badge>
                ) : null}
              </div>
              <p className="mt-3 text-sm leading-6 text-surface-300">
                {translateText(recommendation.rationale)}
              </p>
              <div className="mt-3 rounded-2xl border border-white/8 bg-surface-900/80 px-4 py-3 text-sm text-surface-200">
                {translateText(recommendation.recommended_action)}
              </div>
            </div>

            <div className="assistant-aside-card rounded-3xl border border-white/8 p-4">
              <p className="assistant-section-kicker">Portability evidence</p>
              <dl className="mt-4 grid gap-3 sm:grid-cols-2">
                <Metric label="Portability score" value={formatPercent(recommendation.portability_score, 0)} />
                <Metric label="Retuning magnitude" value={formatNumber(recommendation.retuning_magnitude, 3)} />
              </dl>
              <div className="mt-4 flex flex-wrap gap-2">
                {recommendation.retuning_axes.length ? (
                  recommendation.retuning_axes.map((axis) => (
                    <Badge key={axis} variant="info">
                      {axis}
                    </Badge>
                  ))
                ) : (
                  <Badge variant="neutral">No retuning axes suggested</Badge>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="assistant-aside-card rounded-3xl border border-dashed border-white/10 bg-white/3 px-4 py-8 text-center text-sm text-surface-400">
            {isLoading ? translateText("Generating recommendation preview...") : translateText(emptyMessage)}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="assistant-meta-panel rounded-2xl border border-white/8 bg-surface-900/70 px-4 py-3">
      <p className="assistant-section-kicker !text-surface-500">
        {translateText(label)}
      </p>
      <p className="mt-2 text-sm font-medium text-white">{value}</p>
    </div>
  );
}

function humanizeRecommendation(value: string) {
  if (value === "PASS") return "Recommend release";
  if (value === "PASS_WITH_RETUNING") return "Release with retuning";
  return "Do not release";
}

function recommendationVariant(value: string) {
  if (value === "PASS") return "success" as const;
  if (value === "PASS_WITH_RETUNING") return "warning" as const;
  return "danger" as const;
}
