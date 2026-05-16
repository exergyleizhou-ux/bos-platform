import { Boxes, BrainCircuit, ExternalLink, ScanSearch } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { SurfaceTile, surfaceTileButtonClasses } from "@/components/ui/SurfaceTile";
import type { NativeModelCatalog } from "@/types/bos";

interface NativeModelStackCardProps {
  catalog: NativeModelCatalog | null;
}

const FIT_VARIANT = {
  high: "success",
  medium: "info",
  low: "warning",
} as const;

export function NativeModelStackCard({ catalog }: NativeModelStackCardProps) {
  if (!catalog) return null;

  return (
    <Card tone="strong" className="assistant-thread-stage overflow-hidden">
      <CardHeader
        title="BOS native model stack"
        description="Compress 2025-2026 open-source frontier models into the BOS native capability layer, directly mapping insect-state recognition, residue estimation, time-series forecasting, and biosecurity."
      />
      <CardBody className="space-y-5">
        <div className="grid gap-3 xl:grid-cols-[1.05fr_0.95fr]">
          <SurfaceTile className="rounded-[24px] p-4">
            <div className="flex items-center gap-2">
              <BrainCircuit className="h-4 w-4 text-brand-200" />
              <p className="assistant-section-kicker">Recommended rollout</p>
            </div>
            <div className="mt-4 space-y-3">
              {catalog.recommendations.map((item) => (
                <SurfaceTile
                  key={item.key}
                  tone="subtle"
                  className="rounded-[20px] px-4 py-3"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-white">{item.title}</p>
                    <Badge variant={FIT_VARIANT[item.fit as keyof typeof FIT_VARIANT] ?? "neutral"}>
                      {item.fit}
                    </Badge>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-surface-300">{item.rationale}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {item.model_keys.map((key) => (
                      <Badge key={key} variant="brand">
                        {key}
                      </Badge>
                    ))}
                  </div>
                </SurfaceTile>
              ))}
            </div>
          </SurfaceTile>

          <SurfaceTile className="rounded-[24px] p-4">
            <div className="flex items-center gap-2">
              <Boxes className="h-4 w-4 text-brand-200" />
              <p className="assistant-section-kicker">Composition patterns</p>
            </div>
            <div className="mt-4 space-y-3">
              {catalog.compositions.map((composition) => (
                <SurfaceTile
                  key={composition.key}
                  tone="subtle"
                  className="rounded-[20px] px-4 py-3"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-white">{composition.title}</p>
                    <Badge variant="neutral">{composition.model_keys.length} models</Badge>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-surface-300">{composition.why_it_matters}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {composition.bos_agents.map((agent) => (
                      <Badge key={agent} variant="info">
                        {agent}
                      </Badge>
                    ))}
                  </div>
                </SurfaceTile>
              ))}
            </div>
          </SurfaceTile>
        </div>

        <SurfaceTile tone="info" className="rounded-[28px] border-white/8 bg-gradient-to-br from-emerald-500/8 via-transparent to-sky-500/10 p-4">
          <div className="flex items-center gap-2">
            <ScanSearch className="h-4 w-4 text-emerald-200" />
            <p className="assistant-section-kicker">Frontier models verified</p>
          </div>
          <p className="mt-2 text-sm text-surface-300">
            Catalog version {catalog.catalog_version} · verified on {catalog.verified_on}
          </p>
          <div className="mt-4 grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
            {catalog.models.map((model) => (
              <SurfaceTile
                key={model.key}
                className="rounded-[22px] border-white/8 bg-black/20 p-4 backdrop-blur-sm"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-semibold text-white">{model.name}</p>
                  <Badge variant="neutral">{model.frontier_window}</Badge>
                  <Badge variant={model.modality === "vision" ? "info" : "brand"}>
                    {model.modality}
                  </Badge>
                </div>
                <p className="mt-2 text-sm leading-6 text-surface-300">{model.primary_fit}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {model.native_outputs.slice(0, 3).map((output) => (
                    <Badge key={output} variant="success">
                      {output}
                    </Badge>
                  ))}
                </div>
                <div className="mt-4 space-y-2">
                  {model.sources.map((source) => (
                    <a
                      key={`${model.key}-${source.url}`}
                      href={source.url}
                      target="_blank"
                      rel="noreferrer"
                      className={`${surfaceTileButtonClasses(false)} flex items-center justify-between rounded-2xl px-3 py-2 text-xs text-surface-300 hover:text-white`}
                    >
                      <span className="truncate">{source.label}</span>
                      <ExternalLink className="ml-3 h-3.5 w-3.5 flex-shrink-0" />
                    </a>
                  ))}
                </div>
              </SurfaceTile>
            ))}
          </div>
        </SurfaceTile>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {catalog.rollout.map((step) => (
            <SurfaceTile key={step.phase} className="rounded-[22px] px-4 py-4">
              <Badge variant="warning">{step.phase}</Badge>
              <p className="mt-3 text-sm font-semibold text-white">{step.title}</p>
              <p className="mt-2 text-sm leading-6 text-surface-300">{step.objective}</p>
            </SurfaceTile>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}
