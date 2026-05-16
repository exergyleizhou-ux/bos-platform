import { FileBadge2, ShieldCheck, TriangleAlert } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { translateText } from "@/lib/i18n";
import type { CodeReleaseReadiness } from "@/types/code";

const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1").replace(/\/api\/v1$/, "");

function releaseVariant(state: string) {
  if (state === "READY") return "success" as const;
  if (state === "READY WITH WARNINGS") return "warning" as const;
  return "danger" as const;
}

export function ReleaseReadinessCard({
  readiness,
  compact = false,
}: {
  readiness?: CodeReleaseReadiness;
  compact?: boolean;
}) {
  if (!readiness) {
    return (
      <Card className="assistant-aside-card rounded-[28px]">
        <CardHeader
          title={translateText("BOS Code Release Dossier")}
          description={translateText("Verification artifacts will appear here after the release report is generated.")}
        />
      </Card>
    );
  }

  const releaseDossier = readiness.artifacts.find((item) => item.key === "release_dossier");
  const codeSmoke = readiness.artifacts.find((item) => item.key === "code_smoke_png");
  const bosSmoke = readiness.artifacts.find((item) => item.key === "bos_smoke_png");

  return (
    <Card tone={compact ? "default" : "strong"} className={compact ? "assistant-aside-card rounded-[28px]" : "assistant-thread-stage rounded-[28px]"}>
      <CardHeader
        title={translateText("BOS Code Release Dossier")}
        description={translateText("Current release trust posture, verification counts, and buyer-facing artifacts.")}
        action={<Badge variant={releaseVariant(readiness.release_state)}>{translateText(readiness.release_state)}</Badge>}
      />
      <CardBody className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-3">
            <p className="assistant-section-kicker !text-surface-500">{translateText("Preflight")}</p>
            <p className="mt-2 text-lg font-semibold text-white">
              {readiness.preflight_pass_count} {translateText("pass")} / {readiness.preflight_warn_count} {translateText("warn")} / {readiness.preflight_fail_count} {translateText("fail")}
            </p>
          </div>
          <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-3">
            <p className="assistant-section-kicker !text-surface-500">{translateText("Build")}</p>
            <p className="mt-2 text-lg font-semibold text-white">
              {readiness.backend_version} / {readiness.frontend_version}
            </p>
          </div>
          <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-3">
            <p className="assistant-section-kicker !text-surface-500">{translateText("Git")}</p>
            <p className="mt-2 text-lg font-semibold text-white">
              {readiness.git_branch}
            </p>
            <p className="text-xs text-surface-500">{readiness.git_commit}</p>
          </div>
        </div>

        {readiness.known_warnings.length ? (
          <div className="rounded-2xl border border-amber-400/15 bg-amber-500/10 px-4 py-4">
            <div className="flex items-center gap-2">
              <TriangleAlert className="h-4 w-4 text-amber-200" />
              <p className="text-sm font-medium text-white">{translateText("Known warnings")}</p>
            </div>
            <div className="mt-3 space-y-2">
              {readiness.known_warnings.map((warning) => (
                <p key={warning} className="text-sm text-amber-100">
                  {warning}
                </p>
              ))}
            </div>
          </div>
        ) : (
          <div className="rounded-2xl border border-emerald-400/15 bg-emerald-500/10 px-4 py-4">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-200" />
              <p className="text-sm font-medium text-white">{translateText("No active warnings")}</p>
            </div>
            <p className="mt-2 text-sm text-emerald-100">
              {translateText("This candidate is currently verification-clean at the dossier level.")}
            </p>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          {releaseDossier ? (
            <a
              href={`${API_ORIGIN}${releaseDossier.download_url}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/6 px-4 py-2 text-sm text-white transition-colors hover:bg-white/10"
            >
              <FileBadge2 className="h-4 w-4" />
              {translateText("Open dossier")}
            </a>
          ) : null}
          {codeSmoke ? (
            <a
              href={`${API_ORIGIN}${codeSmoke.download_url}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/6 px-4 py-2 text-sm text-white transition-colors hover:bg-white/10"
            >
              {translateText("Open code smoke")}
            </a>
          ) : null}
          {bosSmoke ? (
            <a
              href={`${API_ORIGIN}${bosSmoke.download_url}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/6 px-4 py-2 text-sm text-white transition-colors hover:bg-white/10"
            >
              {translateText("Open BOS smoke")}
            </a>
          ) : null}
        </div>

        {!compact && readiness.recommended_next_action ? (
          <div className="assistant-meta-panel rounded-2xl border border-white/8 bg-surface-950/60 px-4 py-4">
            <p className="assistant-section-kicker !text-surface-500">{translateText("Recommended next action")}</p>
            <p className="mt-2 text-sm text-surface-300">{readiness.recommended_next_action}</p>
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}
