import { TerminalSquare, Workflow } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { translateText } from "@/lib/i18n";
import type { CodeGitStatusResponse, CodeToolExecutionResponse } from "@/types/code";

interface CodeToolConsoleProps {
  gitStatus?: CodeGitStatusResponse;
  latestToolResult?: CodeToolExecutionResponse | null;
  running: boolean;
  onRunGitStatus: () => void;
  onRunSafeCommand: (command: string) => void;
}

export function CodeToolConsole({
  gitStatus,
  latestToolResult,
  running,
  onRunGitStatus,
  onRunSafeCommand,
}: CodeToolConsoleProps) {
  const [command, setCommand] = useState("git status");

  return (
    <Card className="border-sky-400/15 bg-sky-500/5">
      <CardHeader
        title={translateText("Runtime Tool Console")}
        description={translateText("Operate guarded shell and git surfaces inside the tenant worktree.")}
      />
      <CardBody className="space-y-4">
        <div className="flex gap-3">
          <Button
            variant="secondary"
            leftIcon={<Workflow className="h-4 w-4" />}
            loading={running}
            onClick={onRunGitStatus}
          >
            {translateText("Refresh Git Status")}
          </Button>
        </div>

        <div className="flex gap-3">
          <Input
            value={command}
            onChange={(event) => setCommand(event.target.value)}
            leftIcon={<TerminalSquare className="h-4 w-4" />}
            placeholder={translateText("pwd / ls / git diff / pytest ...")}
          />
          <Button
            variant="outline"
            loading={running}
            onClick={() => onRunSafeCommand(command)}
          >
            {translateText("Run Safe Bash")}
          </Button>
        </div>

        <div className="rounded-2xl border border-white/8 bg-surface-950/70 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[11px] uppercase tracking-[0.18em] text-surface-500">{translateText("Git Status")}</p>
            {gitStatus ? (
              <Badge variant={gitStatus.success ? "success" : "warning"} dot>
                {translateText(gitStatus.success ? "healthy" : "degraded")}
              </Badge>
            ) : null}
          </div>
          <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs text-surface-300">
            {gitStatus?.output || translateText("No git status captured yet.")}
          </pre>
          {gitStatus?.output?.includes("git executable was not detected") ? (
            <p className="mt-2 text-xs text-amber-200/80">
              {translateText("This runtime is healthy, but no usable `git` executable was detected. Set `BOS_CODE_GIT_EXECUTABLE` or install Git.")}
            </p>
          ) : null}
          {gitStatus?.diff_summary ? (
            <>
              <p className="mt-3 text-[11px] uppercase tracking-[0.18em] text-surface-500">{translateText("Diff Summary")}</p>
              <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap text-xs text-surface-400">
                {gitStatus.diff_summary}
              </pre>
            </>
          ) : null}
        </div>

        <div className="rounded-2xl border border-white/8 bg-surface-950/70 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[11px] uppercase tracking-[0.18em] text-surface-500">{translateText("Latest Tool Output")}</p>
            {latestToolResult ? (
              <Badge
                variant={
                  latestToolResult.denied_reason
                    ? "warning"
                    : latestToolResult.success
                      ? "success"
                      : "danger"
                }
                dot
              >
                {latestToolResult.denied_reason
                  ? translateText("denied")
                  : latestToolResult.success
                    ? translateText("success")
                    : translateText("failed")}
              </Badge>
            ) : null}
          </div>
          <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs text-surface-300">
            {latestToolResult?.output || translateText("No tool execution yet.")}
          </pre>
          {latestToolResult ? (
            <p className="mt-2 text-[11px] uppercase tracking-[0.18em] text-surface-500">
              {latestToolResult.tool_name} / {translateText("exit")} {latestToolResult.exit_code ?? "n/a"}
            </p>
          ) : null}
        </div>
      </CardBody>
    </Card>
  );
}
