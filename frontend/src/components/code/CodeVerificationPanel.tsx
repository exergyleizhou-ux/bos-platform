import { FlaskConical, PlayCircle } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { translateText } from "@/lib/i18n";
import type { CodeVerificationResponse } from "@/types/code";

interface CodeVerificationPanelProps {
  verification?: CodeVerificationResponse;
  running: boolean;
  onRunLint: () => void;
  onRunTypecheck: () => void;
  onRunUnitTest: () => void;
  onRunBuild: () => void;
  onRunSmokeTest: () => void;
  onRunPipeline: () => void;
}

function stageVariant(status?: string): "success" | "warning" | "danger" | "neutral" {
  switch (status) {
    case "passed":
      return "success";
    case "running":
      return "warning";
    case "failed":
      return "danger";
    default:
      return "neutral";
  }
}

export function CodeVerificationPanel({
  verification,
  running,
  onRunLint,
  onRunTypecheck,
  onRunUnitTest,
  onRunBuild,
  onRunSmokeTest,
  onRunPipeline,
}: CodeVerificationPanelProps) {
  return (
    <Card className="border-fuchsia-400/15 bg-fuchsia-500/5">
      <CardHeader
        title={translateText("Verification Runner")}
        description={translateText("Execute and observe stage-based verification inside the current coding session.")}
        action={
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              size="sm"
              leftIcon={<PlayCircle className="h-4 w-4" />}
              loading={running}
              onClick={onRunPipeline}
            >
              {translateText("Run Pipeline")}
            </Button>
          </div>
        }
      />
      <CardBody className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" loading={running} onClick={onRunLint}>
            {translateText("Lint")}
          </Button>
          <Button variant="outline" size="sm" loading={running} onClick={onRunTypecheck}>
            {translateText("Typecheck")}
          </Button>
          <Button variant="outline" size="sm" loading={running} onClick={onRunUnitTest}>
            {translateText("Unit Test")}
          </Button>
          <Button variant="outline" size="sm" loading={running} onClick={onRunBuild}>
            {translateText("Build")}
          </Button>
          <Button variant="outline" size="sm" loading={running} onClick={onRunSmokeTest}>
            {translateText("Smoke")}
          </Button>
        </div>

        <div className="flex items-center gap-2">
          <FlaskConical className="h-4 w-4 text-fuchsia-300" />
          <p className="text-sm font-medium text-white">
            {translateText("Overall")}: {translateText(verification?.overall_status ?? "pending")}
          </p>
        </div>

        {verification?.stages.length ? (
          verification.stages.map((stage) => (
            <div key={stage.id} className="rounded-2xl border border-white/8 bg-white/4 p-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-white">{stage.verification_stage}</p>
                <Badge variant={stageVariant(stage.verification_status)} dot>
                  {translateText(stage.verification_status)}
                </Badge>
              </div>
              {stage.summary ? (
                <p className="mt-2 text-xs text-surface-400">{stage.summary}</p>
              ) : null}
            </div>
          ))
        ) : (
          <p className="text-sm text-surface-400">{translateText("No verification runs yet.")}</p>
        )}
      </CardBody>
    </Card>
  );
}
