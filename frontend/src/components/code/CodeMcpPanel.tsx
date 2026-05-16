import { Cable, Lock, PlugZap } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CardBody, CardHeader } from "@/components/ui/Card";
import { CockpitPanel } from "@/components/ui/Cockpit";
import { SurfaceTile } from "@/components/ui/SurfaceTile";
import { translateText } from "@/lib/i18n";
import type { CodeMcpResource, CodeMcpServer } from "@/types/code";

interface CodeMcpPanelProps {
  servers?: CodeMcpServer[];
  resources?: CodeMcpResource[];
  connecting: boolean;
  disconnecting: boolean;
  onConnectDemo: () => void;
  onConnectAuthDemo: () => void;
  onDisconnect: (serverName: string) => void;
  onSelectServer: (serverName: string) => void;
}

function serverVariant(status?: string): "success" | "warning" | "danger" | "info" | "neutral" {
  switch (status) {
    case "connected":
      return "success";
    case "auth_required":
      return "warning";
    case "degraded":
      return "info";
    case "failed":
      return "danger";
    default:
      return "neutral";
  }
}

function discoveryVariant(status?: string | null): "success" | "warning" | "danger" | "info" | "neutral" {
  switch (status) {
    case "completed":
      return "success";
    case "blocked":
      return "warning";
    case "failed":
      return "danger";
    case "idle":
      return "neutral";
    default:
      return "info";
  }
}

export function CodeMcpPanel({
  servers,
  resources,
  connecting,
  disconnecting,
  onConnectDemo,
  onConnectAuthDemo,
  onDisconnect,
  onSelectServer,
}: CodeMcpPanelProps) {
  return (
    <CockpitPanel className="border-violet-400/15 bg-violet-500/5 p-5 lg:p-6">
      <CardHeader
        title={translateText("MCP Control Plane")}
        description={translateText("Minimal MCP lifecycle surface for BOS Code v2.")}
        action={<Badge variant="info" dot>v2</Badge>}
      />
      <CardBody className="space-y-4">
        <div className="flex flex-wrap gap-3">
          <Button
            variant="secondary"
            size="sm"
            leftIcon={<PlugZap className="h-4 w-4" />}
            loading={connecting}
            onClick={onConnectDemo}
          >
            {translateText("Connect demo")}
          </Button>
          <Button
            variant="outline"
            size="sm"
            leftIcon={<Lock className="h-4 w-4" />}
            loading={connecting}
            onClick={onConnectAuthDemo}
          >
            {translateText("Connect auth-demo")}
          </Button>
        </div>

        <div className="space-y-2">
          {servers?.length ? (
            servers.map((server) => (
              <SurfaceTile
                key={server.id}
                className="p-3"
              >
                <div className="flex items-center justify-between gap-3">
                  <button
                    type="button"
                    className="flex min-w-0 items-center gap-2 text-left"
                    onClick={() => onSelectServer(server.server_name)}
                  >
                    <Cable className="h-4 w-4 text-violet-300" />
                    <p className="truncate text-sm font-medium text-white">{server.server_name}</p>
                  </button>
                  <Badge variant={serverVariant(server.connection_status)} dot>
                    {translateText(server.connection_status)}
                  </Badge>
                </div>
                {server.error_message ? (
                  <p className="mt-2 text-xs text-surface-400">{server.error_message}</p>
                ) : null}
                <div className="mt-3 flex flex-wrap gap-2">
                  {server.startup_phase ? (
                    <Badge variant="neutral">{translateText(server.startup_phase)}</Badge>
                  ) : null}
                  {server.discovery_status ? (
                    <Badge variant={discoveryVariant(server.discovery_status)}>{translateText(server.discovery_status)}</Badge>
                  ) : null}
                  <Badge variant="info">{translateText("resources")} {server.resource_count}</Badge>
                  <Badge variant="info">{translateText("tools")} {server.tool_count}</Badge>
                  {server.failure_class ? (
                    <Badge variant="warning">{translateText(server.failure_class)}</Badge>
                  ) : null}
                  {server.degraded_scope ? (
                    <Badge variant="neutral">{translateText(server.degraded_scope)}</Badge>
                  ) : null}
                </div>
                {server.recovery_recommendations?.length ? (
                  <div className="mt-3 space-y-1 rounded-xl border border-white/8 bg-surface-950/40 px-3 py-3 text-xs text-surface-300">
                    <p className="font-medium text-white">{translateText("Recovery actions")}</p>
                    {server.recovery_recommendations.slice(0, 2).map((item, index) => (
                      <p key={`${server.id}-recovery-${index}`}>- {item}</p>
                    ))}
                  </div>
                ) : null}
                <div className="mt-3 flex justify-end">
                  <Button
                    variant="ghost"
                    size="sm"
                    loading={disconnecting}
                    onClick={() => onDisconnect(server.server_name)}
                  >
                    {translateText("Disconnect")}
                  </Button>
                </div>
              </SurfaceTile>
            ))
          ) : (
            <p className="text-sm text-surface-400">{translateText("No MCP servers connected yet.")}</p>
          )}
        </div>

        <SurfaceTile tone="subtle">
          <p className="text-[11px] uppercase tracking-[0.18em] text-surface-500">
            {translateText("Resources")}
          </p>
          <div className="mt-3 space-y-2">
            {resources?.length ? (
              resources.map((resource) => (
                <SurfaceTile key={resource.uri} className="rounded-xl p-3">
                  <p className="text-sm font-medium text-white">{resource.name}</p>
                  <p className="mt-1 text-xs text-surface-400">{resource.uri}</p>
                </SurfaceTile>
              ))
            ) : (
              <p className="text-sm text-surface-400">{translateText("No MCP resources available.")}</p>
            )}
          </div>
        </SurfaceTile>
      </CardBody>
    </CockpitPanel>
  );
}
