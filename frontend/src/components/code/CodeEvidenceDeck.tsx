import { GitBranch, PlugZap, ScrollText, TerminalSquare } from "lucide-react";
import { useMemo, useState } from "react";

import { CodeBranchPanel } from "@/components/code/CodeBranchPanel";
import { CodeRecoveryPanel } from "@/components/code/CodeRecoveryPanel";
import { CodeReviewRail } from "@/components/code/CodeReviewRail";
import { CodeTaskWorkerPanel } from "@/components/code/CodeTaskWorkerPanel";
import { CodeVerificationPanel } from "@/components/code/CodeVerificationPanel";
import { CardBody, CardHeader } from "@/components/ui/Card";
import { CockpitPanel } from "@/components/ui/Cockpit";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import { CodeSessionTimeline } from "@/components/code/CodeSessionTimeline";
import { CodeToolConsole } from "@/components/code/CodeToolConsole";
import { CodeWorkbenchTabs } from "@/components/code/CodeWorkbenchTabs";
import { CodeLspPanel } from "@/components/code/CodeLspPanel";
import { CodeMcpPanel } from "@/components/code/CodeMcpPanel";
import { translateText } from "@/lib/i18n";
import type {
  CodeArtifact,
  CodeAutomationExecutionResponse,
  CodeDiffResponse,
  CodeEvent,
  CodeGitStatusResponse,
  CodeLspDiagnosticsPayload,
  CodeLspSymbolsPayload,
  CodeMcpResource,
  CodeMcpServer,
  CodeOrchestrationSnapshot,
  CodeReadinessResponse,
  CodeRecoveryResponse,
  CodeSessionDetail,
  CodeToolExecutionResponse,
  CodeVerificationResponse,
  CodeWorkerEvent,
  CodeWorkspaceFileResponse,
  CodeWorkspaceTreeResponse,
  CodeBranchState,
  CodeTask,
  CodeTaskArchitectPlanResponse,
  CodeTaskPacket,
  CodeWorker,
} from "@/types/code";

interface CodeEvidenceDeckProps {
  sessionDetail?: CodeSessionDetail;
  tasks?: CodeTask[];
  workers?: CodeWorker[];
  orchestration?: CodeOrchestrationSnapshot;
  events: CodeEvent[];
  workerEvents?: CodeWorkerEvent[];
  streamConnected: boolean;
  branchState?: CodeBranchState;
  readiness?: CodeReadinessResponse;
  recovery?: CodeRecoveryResponse;
  gitStatus?: CodeGitStatusResponse;
  latestToolResult?: CodeToolExecutionResponse | null;
  toolRunning: boolean;
  onRunGitStatus: () => void;
  onRunSafeCommand: (command: string) => void;
  tree?: CodeWorkspaceTreeResponse;
  file?: CodeWorkspaceFileResponse;
  diff?: CodeDiffResponse;
  verification?: CodeVerificationResponse;
  artifacts?: CodeArtifact[];
  selectedFilePath?: string;
  onSelectFile?: (path: string) => void;
  mcpServers?: CodeMcpServer[];
  mcpResources?: CodeMcpResource[];
  mcpConnecting: boolean;
  mcpDisconnecting: boolean;
  onConnectDemo: () => void;
  onConnectAuthDemo: () => void;
  onDisconnect: (serverName: string) => void;
  onSelectServer: (serverName: string) => void;
  diagnostics?: CodeLspDiagnosticsPayload;
  symbols?: CodeLspSymbolsPayload;
  refreshingBranch: boolean;
  onRefreshBranch: () => void;
  runningVerification: boolean;
  onRunLint: () => void;
  onRunTypecheck: () => void;
  onRunUnitTest: () => void;
  onRunBuild: () => void;
  onRunSmokeTest: () => void;
  onRunPipeline: () => void;
  recoveryResult?: CodeAutomationExecutionResponse | null;
  recoveryActionLabel?: string;
  recoveryActionLoading?: boolean;
  recoveryActionDisabled?: boolean;
  onRecoveryAction?: () => void;
  plannerDrafts?: Record<number, CodeTaskArchitectPlanResponse>;
  creatingTask?: boolean;
  assigningTask?: boolean;
  updatingTask?: boolean;
  onCreateTask?: (title: string, objective: string, acceptanceCriteria: string[], taskPacket: CodeTaskPacket) => void;
  onArchitectPlan?: (taskId: number) => void;
  onArchitectRoute?: (taskId: number, acceptanceCriteria: string[]) => void;
  onRequestReview?: (taskId: number) => void;
  onBeginReview?: (taskId: number) => void;
  onAcceptReview?: (taskId: number) => void;
  onRejectReview?: (taskId: number, reason: string, reasonCode: string, checklist: string[]) => void;
  onMarkWorkerReady?: (workerName: string) => void;
  onMarkWorkerBlocked?: (workerName: string) => void;
}

export function CodeEvidenceDeck(props: CodeEvidenceDeckProps) {
  const [activeTab, setActiveTab] = useState("timeline");
  const tabs = useMemo(
      () => [
      { id: "timeline", label: translateText("Flow Notes"), icon: <ScrollText className="h-4 w-4" />, count: props.events.length },
      { id: "lanes", label: translateText("Lanes"), icon: <GitBranch className="h-4 w-4" /> },
      { id: "review", label: translateText("Review"), icon: <GitBranch className="h-4 w-4" /> },
      { id: "controls", label: translateText("Controls"), icon: <TerminalSquare className="h-4 w-4" /> },
      { id: "workspace", label: translateText("Files & Diff"), icon: <GitBranch className="h-4 w-4" /> },
      { id: "tools", label: translateText("Tool Shelf"), icon: <TerminalSquare className="h-4 w-4" /> },
      { id: "connectors", label: translateText("Connectors"), icon: <PlugZap className="h-4 w-4" /> },
    ],
    [props.events.length],
  );

  return (
    <CockpitPanel className="p-5 lg:p-6">
      <CardHeader
        title={translateText("Evidence Deck")}
        description={translateText("Proof, trace, and deeper technical state stay nearby here, ready when you want them without taking over the room.")}
      />
      <CardBody className="space-y-4">
        <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} className="bg-white/3" />

        <TabPanel tabId="timeline" activeTab={activeTab}>
          <CodeSessionTimeline
            sessionDetail={props.sessionDetail}
            events={props.events}
            streamConnected={props.streamConnected}
          />
        </TabPanel>

        <TabPanel tabId="review" activeTab={activeTab}>
          <CodeReviewRail tasks={props.tasks} workerEvents={props.workerEvents} orchestration={props.orchestration} />
        </TabPanel>

        <TabPanel tabId="lanes" activeTab={activeTab}>
          <CodeTaskWorkerPanel
            tasks={props.tasks}
            workers={props.workers}
            workerEvents={props.workerEvents}
            orchestration={props.orchestration}
            streamConnected={props.streamConnected}
            creating={props.creatingTask ?? false}
            assigning={props.assigningTask ?? false}
            updating={props.updatingTask ?? false}
            plannerDrafts={props.plannerDrafts}
            onCreateTask={props.onCreateTask ?? (() => {})}
            onArchitectPlan={props.onArchitectPlan ?? (() => {})}
            onArchitectRoute={props.onArchitectRoute ?? (() => {})}
            onRequestReview={props.onRequestReview ?? (() => {})}
            onBeginReview={props.onBeginReview ?? (() => {})}
            onAcceptReview={props.onAcceptReview ?? (() => {})}
            onRejectReview={props.onRejectReview ?? (() => {})}
            onMarkWorkerReady={props.onMarkWorkerReady ?? (() => {})}
            onMarkWorkerBlocked={props.onMarkWorkerBlocked ?? (() => {})}
          />
        </TabPanel>

        <TabPanel tabId="controls" activeTab={activeTab}>
          <div className="grid gap-4 xl:grid-cols-[1fr_1fr_1fr]">
            <CodeVerificationPanel
              verification={props.verification}
              running={props.runningVerification}
              onRunLint={props.onRunLint}
              onRunTypecheck={props.onRunTypecheck}
              onRunUnitTest={props.onRunUnitTest}
              onRunBuild={props.onRunBuild}
              onRunSmokeTest={props.onRunSmokeTest}
              onRunPipeline={props.onRunPipeline}
            />
            <CodeBranchPanel
              branchState={props.branchState}
              readiness={props.readiness}
              refreshing={props.refreshingBranch}
              onRefresh={props.onRefreshBranch}
            />
            <CodeRecoveryPanel
              recovery={props.recovery}
              result={props.recoveryResult}
              actionLabel={props.recoveryActionLabel}
              actionLoading={props.recoveryActionLoading}
              actionDisabled={props.recoveryActionDisabled}
              onAction={props.onRecoveryAction}
            />
          </div>
        </TabPanel>

        <TabPanel tabId="workspace" activeTab={activeTab}>
          <CodeWorkbenchTabs
            tree={props.tree}
            file={props.file}
            diff={props.diff}
            verification={props.verification}
            artifacts={props.artifacts}
            selectedFilePath={props.selectedFilePath}
            onSelectFile={props.onSelectFile}
          />
        </TabPanel>

        <TabPanel tabId="tools" activeTab={activeTab}>
          <CodeToolConsole
            gitStatus={props.gitStatus}
            latestToolResult={props.latestToolResult}
            running={props.toolRunning}
            onRunGitStatus={props.onRunGitStatus}
            onRunSafeCommand={props.onRunSafeCommand}
          />
        </TabPanel>

        <TabPanel tabId="connectors" activeTab={activeTab}>
          <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
            <CodeMcpPanel
              servers={props.mcpServers}
              resources={props.mcpResources}
              connecting={props.mcpConnecting}
              disconnecting={props.mcpDisconnecting}
              onConnectDemo={props.onConnectDemo}
              onConnectAuthDemo={props.onConnectAuthDemo}
              onDisconnect={props.onDisconnect}
              onSelectServer={props.onSelectServer}
            />
            <CodeLspPanel diagnostics={props.diagnostics} symbols={props.symbols} />
          </div>
        </TabPanel>
      </CardBody>
    </CockpitPanel>
  );
}
