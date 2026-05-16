import { Braces, Radar } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { translateText } from "@/lib/i18n";
import type { CodeLspDiagnosticsPayload, CodeLspSymbolsPayload } from "@/types/code";

interface CodeLspPanelProps {
  diagnostics?: CodeLspDiagnosticsPayload;
  symbols?: CodeLspSymbolsPayload;
}

function statusVariant(status?: string): "success" | "warning" | "danger" | "neutral" {
  switch (status) {
    case "ready":
      return "success";
    case "degraded":
      return "warning";
    case "failed":
      return "danger";
    default:
      return "neutral";
  }
}

export function CodeLspPanel({ diagnostics, symbols }: CodeLspPanelProps) {
  return (
    <Card className="border-cyan-400/15 bg-cyan-500/5">
      <CardHeader
        title={translateText("LSP Surface")}
        description={translateText("Minimal diagnostics and symbol navigation contract for BOS Code v2.")}
        action={
          <Badge variant={statusVariant(diagnostics?.session.status)} dot>
            {translateText(diagnostics?.session.status ?? "idle")}
          </Badge>
        }
      />
      <CardBody className="space-y-4">
        <div className="rounded-2xl border border-white/8 bg-surface-950/60 p-4">
          <div className="flex items-center gap-2">
            <Radar className="h-4 w-4 text-cyan-300" />
            <p className="text-sm font-medium text-white">
              {translateText("Diagnostics")} ({diagnostics?.diagnostics.length ?? 0})
            </p>
          </div>
          <div className="mt-3 space-y-2">
            {diagnostics?.diagnostics.length ? (
              diagnostics.diagnostics.map((item, index) => (
                <div key={`${item.path}-${index}`} className="rounded-xl border border-white/8 bg-white/4 p-3">
                  <p className="text-sm font-medium text-white">{item.message}</p>
                  <p className="mt-1 text-xs text-surface-400">
                    {item.path}:{item.line} / {item.severity}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-sm text-surface-400">{translateText("No diagnostics available.")}</p>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-white/8 bg-surface-950/60 p-4">
          <div className="flex items-center gap-2">
            <Braces className="h-4 w-4 text-cyan-300" />
            <p className="text-sm font-medium text-white">
              {translateText("Symbols")} ({symbols?.symbols.length ?? 0})
            </p>
          </div>
          <div className="mt-3 space-y-2">
            {symbols?.symbols.length ? (
              symbols.symbols.map((item) => (
                <div key={`${item.path}-${item.name}`} className="rounded-xl border border-white/8 bg-white/4 p-3">
                  <p className="text-sm font-medium text-white">{item.name}</p>
                  <p className="mt-1 text-xs text-surface-400">
                    {item.kind} / {item.path}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-sm text-surface-400">{translateText("No symbols available.")}</p>
            )}
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
