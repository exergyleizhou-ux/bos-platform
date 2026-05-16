import { useEffect, useMemo, useState } from "react";
import { Bot, PlayCircle, RefreshCcw } from "lucide-react";
import type { AxiosError } from "axios";

import { CodeContextRail } from "@/components/code/CodeContextRail";
import { CodeEvidenceDeck } from "@/components/code/CodeEvidenceDeck";
import { CodeAlwaysOnPanel } from "@/components/code/CodeAlwaysOnPanel";
import { CodeMemoryPanel } from "@/components/code/CodeMemoryPanel";
import { CodeReviewRail } from "@/components/code/CodeReviewRail";
import { ReleaseReadinessCard } from "@/components/code/ReleaseReadinessCard";
import { CodeStatusBand } from "@/components/code/CodeStatusBand";
import { CodeWorkThread } from "@/components/code/CodeWorkThread";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorState, EmptyState } from "@/components/ui/EmptyState";
import { Select } from "@/components/ui/Select";
import {
  CockpitGrid,
  CockpitMetric,
  CockpitPanel,
  CockpitSectionLabel,
} from "@/components/ui/Cockpit";
import {
  useCancelCodeSession,
  useCodeArtifacts,
  useCreateCodeAutomationJob,
  useCodeBranchState,
  useCodeDiff,
  useCodeFile,
  useCodeLspDiagnostics,
  useCodeLspSymbols,
  useCodeMcpResources,
  useCodeMcpServers,
  useCodeOrchestration,
  useCodeRuntime,
  useCodeReadiness,
  useCodeReleaseReadiness,
  useCodeRecovery,
  useCodeReflections,
  useCodeSession,
  useCodeSessionEvents,
  useCodeMemorySnapshots,
  useCodeSessions,
  useCodeSkills,
  useCodeTasks,
  useCodeWorkers,
  useCodeWorkerEvents,
  useArchitectPlanCodeTask,
  useArchitectRouteCodeTask,
  useFeedbackCodeSkill,
  useRequestCodeTaskReview,
  useRefreshCodeBranchState,
  useRefreshCodeMemorySnapshot,
  useRunCodeAutomationJob,
  useRunCodeReflection,
  useSubmitCodeTaskReviewDecision,
  useUpdateCodeAutomationJob,
  useUpdateCodeSkill,
  useUpdateCodeWorkerStatus,
  useCodeVerification,
  useCodeGitStatus,
  useCodeWorkspace,
  useCodeWorkspaceStatus,
  useCodeWorkspaceTree,
  useCreateCodeSession,
  useCreateCodeTask,
  useCreateCodeTurn,
  useConnectCodeMcpServer,
  useDisconnectCodeMcpServer,
  useExecuteNextAutomationAction,
  useInitCodeWorkspace,
  useRunCodeSafeBash,
  useSearchCodeSessions,
  useRunCodeVerification,
} from "@/hooks/code/useCode";
import { formatCodeActionCallToAction } from "@/lib/codeActionPolicy";
import { CODE_LANES, CODE_REVIEW_DECISIONS } from "@/lib/codeProtocol";
import { translateText } from "@/lib/i18n";
import {
  runtimeStatusLabel,
  runtimeStatusVariant,
  scopedAutomationAction,
} from "@/lib/codeRuntimeUi";
import { useCodeSessionStream } from "@/hooks/code/useCodeSessionStream";
import { useCodeWorkerEventStream } from "@/hooks/code/useCodeWorkerEventStream";
import { truncate } from "@/lib/utils";
import type { CodeAutomationExecutionResponse, CodeTaskArchitectPlanResponse } from "@/types/code";

function branchPosture(branchName?: string | null) {
  if (!branchName) return "No branch";
  if (branchName === "main" || branchName === "master") return "Base branch";
  return "Working branch";
}

function initShell(action: () => void, isPending: boolean) {
  return (
    <div className="assistant-ambient-shell space-y-6">
      <div className="assistant-ambient-backdrop" aria-hidden="true">
        <span className="assistant-ambient-orb assistant-ambient-orb-cyan" />
        <span className="assistant-ambient-orb assistant-ambient-orb-violet" />
        <span className="assistant-ambient-orb assistant-ambient-orb-white" />
        <span className="assistant-ambient-grid" />
        <span className="assistant-ambient-scan assistant-ambient-scan-a" />
        <span className="assistant-ambient-scan assistant-ambient-scan-b" />
      </div>

      <CockpitPanel tone="hero" className="p-6 lg:p-7">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <CockpitSectionLabel>BOS Code</CockpitSectionLabel>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.65rem]">
                Embedded engineering cockpit
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-surface-300">
                Initialize a tenant-scoped coding workspace inside the canonical BOS repository,
                then drive the session from the thread-first cockpit.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="brand">Validated scope</Badge>
              <Badge variant="neutral">Single-repo v1</Badge>
            </div>
          </div>
        </div>
      </CockpitPanel>

      <CockpitPanel className="p-5 lg:p-6">
        <EmptyState
          icon={<Bot className="h-12 w-12" />}
          title="No workspace initialized"
          description="Create the tenant worktree and boot the BOS Code runtime contract."
          actionLabel={isPending ? "Initializing..." : "Initialize BOS Code"}
          onAction={action}
          className="premium-panel-strong rounded-[28px]"
        />
      </CockpitPanel>
    </div>
  );
}

export default function CodeCockpitPage() {
  const workspace = useCodeWorkspace();
  const workspaceStatus = useCodeWorkspaceStatus();
  const sessions = useCodeSessions();
  const initWorkspace = useInitCodeWorkspace();
  const createSession = useCreateCodeSession();

  const activeSessionId = sessions.data?.active_session_id ?? sessions.data?.items[0]?.id ?? null;
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(activeSessionId);
  const [selectedFilePath, setSelectedFilePath] = useState("");
  const [sessionProvider, setSessionProvider] = useState("openai");
  const [plannerDrafts, setPlannerDrafts] = useState<Record<number, CodeTaskArchitectPlanResponse>>({});
  const [runningAutomationJobId, setRunningAutomationJobId] = useState<number | null>(null);
  const [automationResultBySession, setAutomationResultBySession] = useState<Record<number, CodeAutomationExecutionResponse>>({});
  const sessionId = selectedSessionId ?? activeSessionId;

  const sessionDetail = useCodeSession(sessionId);
  const events = useCodeSessionEvents(sessionId);
  const stream = useCodeSessionStream(sessionId, events.data?.next_seq ?? undefined);
  const diff = useCodeDiff(sessionId);
  const artifacts = useCodeArtifacts(sessionId);
  const branchState = useCodeBranchState(sessionId);
  const lspDiagnostics = useCodeLspDiagnostics("python", !!workspace.data);
  const lspSymbols = useCodeLspSymbols("python", !!workspace.data);
  const mcpServers = useCodeMcpServers(!!workspace.data);
  const tasks = useCodeTasks(!!workspace.data);
  const workers = useCodeWorkers(!!workspace.data);
  const orchestration = useCodeOrchestration(!!workspace.data);
  const runtime = useCodeRuntime(!!workspace.data);
  const releaseReadiness = useCodeReleaseReadiness();
  const reflections = useCodeReflections(!!workspace.data);
  const skills = useCodeSkills(!!workspace.data);
  const workerEvents = useCodeWorkerEvents({}, !!workspace.data);
  const [selectedMcpServer, setSelectedMcpServer] = useState("");
  const mcpResources = useCodeMcpResources(selectedMcpServer, !!selectedMcpServer);
  const readiness = useCodeReadiness(sessionId);
  const recovery = useCodeRecovery(sessionId);
  const verification = useCodeVerification(sessionId);
  const gitStatus = useCodeGitStatus(sessionId);
  const tree = useCodeWorkspaceTree(".", !!workspace.data);
  const currentFilePath = selectedFilePath || tree.data?.items.find((item) => item.node_type === "file")?.path || "";
  const currentFile = useCodeFile(currentFilePath, !!currentFilePath);
  const memorySnapshots = useCodeMemorySnapshots(sessionId);
  const createAutomationJob = useCreateCodeAutomationJob();
  const createTurn = useCreateCodeTurn(sessionId);
  const feedbackSkill = useFeedbackCodeSkill();
  const refreshMemorySnapshot = useRefreshCodeMemorySnapshot(sessionId);
  const runAutomationJob = useRunCodeAutomationJob();
  const updateAutomationJob = useUpdateCodeAutomationJob();
  const runReflection = useRunCodeReflection();
  const updateSkill = useUpdateCodeSkill();
  const createTask = useCreateCodeTask();
  const architectPlanTask = useArchitectPlanCodeTask();
  const architectRouteTask = useArchitectRouteCodeTask();
  const requestTaskReview = useRequestCodeTaskReview();
  const updateWorkerStatus = useUpdateCodeWorkerStatus();
  const connectMcpServer = useConnectCodeMcpServer();
  const cancelSession = useCancelCodeSession(sessionId);
  const disconnectMcpServer = useDisconnectCodeMcpServer();
  const refreshBranchState = useRefreshCodeBranchState(sessionId);
  const executeNextAutomationAction = useExecuteNextAutomationAction();
  const runSafeBash = useRunCodeSafeBash(sessionId);
  const runVerification = useRunCodeVerification(sessionId);
  const submitReviewDecision = useSubmitCodeTaskReviewDecision();
  const [prompt, setPrompt] = useState("");
  const sessionSearchSeed =
    prompt.trim() ||
    sessionDetail.data?.turns?.[sessionDetail.data.turns.length - 1]?.user_message ||
    "";
  const sessionSearch = useSearchCodeSessions(sessionSearchSeed, 3, !!workspace.data && sessionSearchSeed.trim().length > 0);
  const workerStream = useCodeWorkerEventStream(
    workspace.data?.id ?? null,
    workerEvents.data?.next_id ?? undefined,
  );

  const mergedEvents = useMemo(() => {
    const seeded = events.data?.items ?? [];
    const streamed = stream.events ?? [];
    const byId = new Map<number, (typeof seeded)[number]>();
    [...seeded, ...streamed].forEach((item) => byId.set(item.id, item));
    return [...byId.values()].sort((a, b) => a.seq_no - b.seq_no);
  }, [events.data?.items, stream.events]);

  const mergedWorkerEvents = useMemo(() => {
    const seeded = workerEvents.data?.items ?? [];
    const streamed = workerStream.events ?? [];
    const byId = new Map<number, (typeof seeded)[number]>();
    [...seeded, ...streamed].forEach((item) => byId.set(item.id, item));
    return [...byId.values()].sort((a, b) => b.id - a.id);
  }, [workerEvents.data?.items, workerStream.events]);
  const mcpSummary = useMemo(() => {
    const servers = mcpServers.data ?? [];
    if (!servers.length) {
      return undefined;
    }
    const degraded = servers.filter((server) => server.connection_status === "degraded" || server.connection_status === "auth_required");
    const connected = servers.filter((server) => server.connection_status === "connected");
    if (!degraded.length) {
      return `${connected.length} MCP server${connected.length === 1 ? "" : "s"} connected with discovery in view.`;
    }
    const primary = degraded[0];
    const nextAction = primary.recovery_recommendations?.[0] ?? primary.error_message ?? "Inspect the affected MCP server.";
    return `${degraded.length} degraded connector${degraded.length === 1 ? "" : "s"} / ${nextAction}`;
  }, [mcpServers.data]);
  const automationTargetSessionId = sessions.data?.items[0]?.id ?? null;
  const recoveryAutomationAction = scopedAutomationAction(
    orchestration.data?.automation_ready,
    orchestration.data?.next_automation_action ?? null,
    sessionId,
    automationTargetSessionId,
  );
  const recoveryResult = sessionId ? automationResultBySession[sessionId] ?? null : null;
  const providerOptions =
    runtime.data?.available_providers?.map((provider) => ({
      value: provider.name,
      label: `${provider.label}${provider.is_default ? " (default)" : ""}`,
    })) ?? [];

  useEffect(() => {
    if (!executeNextAutomationAction.data?.session_id) return;
    setAutomationResultBySession((current) => ({
      ...current,
      [executeNextAutomationAction.data!.session_id as number]: executeNextAutomationAction.data!,
    }));
  }, [executeNextAutomationAction.data]);

  useEffect(() => {
    if (selectedSessionId === null && activeSessionId !== null) {
      setSelectedSessionId(activeSessionId);
    }
  }, [activeSessionId, selectedSessionId]);

  useEffect(() => {
    const fileItems = tree.data?.items.filter((item) => item.node_type === "file") ?? [];
    const hasSelectedFile = fileItems.some((item) => item.path === selectedFilePath);
    if (hasSelectedFile) return;

    const firstFile = fileItems[0]?.path ?? "";
    if (firstFile !== selectedFilePath) {
      setSelectedFilePath(firstFile);
    }
  }, [selectedFilePath, tree.data?.items]);

  useEffect(() => {
    if (!selectedMcpServer && mcpServers.data?.length) {
      setSelectedMcpServer(mcpServers.data[0].server_name);
    }
  }, [mcpServers.data, selectedMcpServer]);

  useEffect(() => {
    if (!providerOptions.length) return;
    if (providerOptions.some((option) => option.value === sessionProvider)) return;
    const defaultProvider =
      runtime.data?.available_providers?.find((provider) => provider.is_default)?.name ??
      providerOptions[0]?.value;
    if (defaultProvider) {
      setSessionProvider(defaultProvider);
    }
  }, [providerOptions, runtime.data?.available_providers, sessionProvider]);

  const workspaceStatusCode = (workspace.error as AxiosError | null)?.response?.status;
  const showWorkspaceInit = !workspace.data && !workspace.isLoading && workspaceStatusCode === 404;

  if (workspace.isError && !workspace.data) {
    if (showWorkspaceInit) {
      return initShell(() => initWorkspace.mutate({}), initWorkspace.isPending);
    }
    return (
      <ErrorState
        title="BOS Code unavailable"
        description="The embedded coding workspace could not be loaded. Check feature gating or workspace setup."
        onRetry={() => workspace.refetch()}
      />
    );
  }

  if (showWorkspaceInit || (!workspace.data && !workspace.isLoading)) {
    return initShell(() => initWorkspace.mutate({}), initWorkspace.isPending);
  }

  const activeSession = sessions.data?.items.find((item) => item.id === sessionId) ?? null;
  const leaseOccupied = workspaceStatus.data?.lease?.lease_status === "active" && !workspaceStatus.data?.can_write;
  const runtimePosture = runtimeStatusLabel(activeSession?.session_status ?? null);
  const releaseState = releaseReadiness.data?.release_state ?? "pending";
  const releaseStateVariant = releaseState === "ready_for_review" ? "success" : releaseState === "pending" ? "neutral" : "warning";
  const releaseStateAccent = releaseState === "ready_for_review" ? "cyan" : releaseState === "pending" ? "neutral" : "amber";
  const branchName = workspaceStatus.data?.workspace.active_branch ?? workspace.data?.active_branch ?? null;

  return (
    <div className="assistant-ambient-shell space-y-6">
      <div className="assistant-ambient-backdrop" aria-hidden="true">
        <span className="assistant-ambient-orb assistant-ambient-orb-cyan" />
        <span className="assistant-ambient-orb assistant-ambient-orb-violet" />
        <span className="assistant-ambient-orb assistant-ambient-orb-white" />
        <span className="assistant-ambient-grid" />
        <span className="assistant-ambient-scan assistant-ambient-scan-a" />
        <span className="assistant-ambient-scan assistant-ambient-scan-b" />
      </div>

      <CockpitPanel tone="hero" className="p-6 lg:p-7">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <CockpitSectionLabel>{translateText("BOS Code")}</CockpitSectionLabel>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.65rem]">
                {translateText("Embedded engineering cockpit")}
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-surface-300">
                {translateText("Start in the thread, keep release posture visible, and pull the deeper scientific controls closer only when you need them.")}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant={runtimeStatusVariant(activeSession?.session_status ?? null)}>
                {translateText(runtimePosture)}
              </Badge>
              <Badge variant={releaseStateVariant}>
                {translateText(releaseState)}
              </Badge>
              {mcpSummary ? <Badge variant="info">{translateText("MCP in view")}</Badge> : null}
            </div>
          </div>

          <CockpitGrid className="sm:grid-cols-2 xl:grid-cols-5">
            <CockpitMetric
              label={translateText("Workspace branch")}
              value={branchName ?? translateText("No branch")}
              hint={translateText(branchPosture(branchName))}
              accent="cyan"
            />
            <CockpitMetric
              label={translateText("Session")}
              value={activeSession ? `#${activeSession.id}` : translateText("No active session")}
              hint={translateText(runtimePosture)}
              accent="violet"
            />
            <CockpitMetric
              label={translateText("Verification")}
              value={translateText(orchestration.data?.verification_gate ?? activeSession?.verification_status ?? "pending")}
              hint={translateText(orchestration.data?.merge_readiness ?? "merge idle")}
              accent="amber"
            />
            <CockpitMetric
              label={translateText("Automation")}
              value={orchestration.data?.automation_ready ? translateText("Ready") : translateText("Blocked")}
              hint={translateText(orchestration.data?.next_automation_action ?? orchestration.data?.automation_summary ?? "Awaiting operator")}
              accent="neutral"
            />
            <CockpitMetric
              label={translateText("Release posture")}
              value={translateText(releaseState)}
              hint={translateText(releaseReadiness.data?.recommended_next_action ?? "Dossier-backed release signal")}
              accent={releaseStateAccent}
            />
          </CockpitGrid>
        </div>
      </CockpitPanel>

      <CockpitPanel className="p-5 lg:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <CockpitSectionLabel>{translateText("Session controls")}</CockpitSectionLabel>
            <p className="mt-3 text-sm leading-7 text-surface-300">
              {translateText("Refresh the workspace, start a new coding session, or jump across the current session stack without disturbing the deeper code widgets below.")}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {providerOptions.length ? (
              <div className="min-w-[15rem]">
                <Select
                  aria-label="Session provider"
                  value={sessionProvider}
                  options={providerOptions}
                  onChange={(event) => setSessionProvider(event.target.value)}
                />
              </div>
            ) : null}
            <Button
              variant="ghost"
              leftIcon={<RefreshCcw className="h-4 w-4" />}
              onClick={() => {
                workspace.refetch();
                workspaceStatus.refetch();
                sessions.refetch();
              }}
            >
              {translateText("Refresh")}
            </Button>
            <Button
              leftIcon={<PlayCircle className="h-4 w-4" />}
              loading={createSession.isPending}
              onClick={() =>
                createSession.mutate(
                  { acquire_write_lease: true, provider: sessionProvider },
                  {
                    onSuccess: (session) => {
                      setSelectedSessionId(session.id);
                    },
                  },
                )
              }
            >
              {translateText("Start session")}
            </Button>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-2 text-xs text-surface-500">
          <Badge variant={leaseOccupied ? "warning" : "success"}>
            {leaseOccupied ? "lease occupied" : "lease available"}
          </Badge>
          {providerOptions.length ? (
            <Badge variant="info">
              {`provider ${sessionProvider}`}
            </Badge>
          ) : null}
          {sessions.data?.items.length ? (
            sessions.data.items.slice(0, 3).map((session) => (
              <button
                key={session.id}
                onClick={() => setSelectedSessionId(session.id)}
                className={`rounded-full border px-3 py-1.5 transition-colors ${
                  session.id === sessionId
                    ? "border-brand-400/20 bg-brand-500/15 text-white"
                    : "border-white/8 bg-white/4 text-surface-400 hover:text-white"
                }`}
              >
                #{session.id} {truncate(session.session_status, 18)}
              </button>
            ))
          ) : (
            <span>{translateText("No active sessions yet.")}</span>
          )}
          <Button
            size="sm"
            variant="ghost"
            disabled={!sessionId}
            loading={cancelSession.isPending}
            onClick={() => cancelSession.mutate({ reason: "operator_cancelled" })}
          >
            {translateText("Stop session")}
          </Button>
        </div>
      </CockpitPanel>

      <CodeStatusBand
        workspaceStatus={workspaceStatus.data}
        activeSession={activeSession}
        orchestration={orchestration.data}
        runtime={runtime.data}
        sessionDetail={sessionDetail.data}
        events={mergedEvents}
      />

      <ReleaseReadinessCard readiness={releaseReadiness.data} compact />

      <CodeAlwaysOnPanel
        runtime={runtime.data}
        reflections={reflections.data}
        skills={skills.data}
        activeSessionId={sessionId}
        runningAutomationJobId={runningAutomationJobId}
        reflectionRunning={runReflection.isPending}
        skillSaving={updateSkill.isPending}
        onRunAutomation={(jobId) => {
          setRunningAutomationJobId(jobId);
          runAutomationJob.mutate(jobId, {
            onSettled: () => setRunningAutomationJobId(null),
          });
        }}
        onToggleAutomation={(jobId, enabled) => updateAutomationJob.mutate({ jobId, payload: { enabled } })}
        onUpdateAutomation={(jobId, payload) => updateAutomationJob.mutate({ jobId, payload })}
        onCreateAutomation={(payload) => createAutomationJob.mutate(payload)}
        onRunReflection={(targetSessionId) => runReflection.mutate({ session_id: targetSessionId, trigger_source: "manual" })}
        onUpdateSkill={(skillId, payload) => updateSkill.mutate({ skillId, payload })}
        onFeedbackSkill={(skillId, sentiment, note) => feedbackSkill.mutate({ skillId, payload: { sentiment, note } })}
      />

      <CodeMemoryPanel
        snapshots={memorySnapshots.data}
        searchResults={sessionSearch.data?.results}
        refreshing={refreshMemorySnapshot.isPending}
        onRefresh={sessionId ? () => refreshMemorySnapshot.mutate() : undefined}
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_18.5rem]">
        <CodeWorkThread
          activeSession={activeSession}
          orchestration={orchestration.data}
          tasks={tasks.data}
          plannerDrafts={plannerDrafts}
          prompt={prompt}
          onPromptChange={setPrompt}
          submittingPrompt={createTurn.isPending}
          onSubmitPrompt={() => createTurn.mutate({ user_message: prompt, stream: true }, { onSuccess: () => setPrompt("") })}
          creating={createTask.isPending}
          onCreateTask={(title, objective, acceptanceCriteria, taskPacket) =>
            createTask.mutate({
              title,
              objective,
              scope: taskPacket.scope,
              session_id: sessionId ?? undefined,
              acceptance_criteria: acceptanceCriteria,
              task_packet: taskPacket,
            })
          }
          assigning={architectPlanTask.isPending || architectRouteTask.isPending}
          updating={requestTaskReview.isPending || submitReviewDecision.isPending}
          onArchitectPlan={(taskId) =>
            architectPlanTask.mutate({
              taskId,
              payload: {
                regenerate: true,
                summary: "Architect drafted acceptance criteria and suggested executor routing.",
                payload: { source: "cockpit", lane: CODE_LANES.architect },
              },
            }, {
              onSuccess: (result) => {
                setPlannerDrafts((current) => ({
                  ...current,
                  [taskId]: result,
                }));
              },
            })
          }
          onArchitectRoute={(taskId, acceptanceCriteria) =>
            architectRouteTask.mutate({
              taskId,
              payload: {
                acceptance_criteria: plannerDrafts[taskId]?.acceptance_criteria ?? acceptanceCriteria,
                summary: "Architect decomposed and routed the task to executor.",
                route_to: plannerDrafts[taskId]?.route_to ?? CODE_LANES.executor,
                payload: { source: "cockpit", lane: CODE_LANES.architect },
              },
            })
          }
          onRequestReview={(taskId) =>
            requestTaskReview.mutate({
              taskId,
              payload: {
                summary: "Executor submitted implementation for reviewer decision.",
                payload: { source: "cockpit", lane: CODE_LANES.executor },
              },
            })
          }
          onBeginReview={(taskId) =>
            updateWorkerStatus.mutate({
              workerName: CODE_LANES.reviewer,
              payload: {
                worker_status: "running",
                last_event_summary: `Reviewer is actively evaluating task #${taskId}.`,
                lane: CODE_LANES.reviewer,
                event_name: "lane.progressed",
                payload: { source: "cockpit", task_id: taskId, review_state: "in_review" },
              },
            })
          }
          onAcceptReview={(taskId) =>
            submitReviewDecision.mutate({
              taskId,
              payload: {
                decision: CODE_REVIEW_DECISIONS.accept,
                summary: "Reviewer accepted the implementation.",
                payload: { source: "cockpit", lane: CODE_LANES.reviewer },
              },
            })
          }
          onRejectReview={(taskId, reason, reasonCode, checklist) =>
            submitReviewDecision.mutate({
              taskId,
              payload: {
                decision: CODE_REVIEW_DECISIONS.reject,
                summary: "Reviewer rejected the implementation.",
                reason: reason || translateText("Follow-up changes requested before task completion."),
                reason_code: reasonCode || "changes_requested",
                checklist,
                payload: { source: "cockpit", lane: CODE_LANES.reviewer },
              },
            })
          }
        />

        <div className="space-y-4">
          <CodeReviewRail tasks={tasks.data} workerEvents={mergedWorkerEvents} orchestration={orchestration.data} />
          <CodeContextRail
            activeSession={activeSession}
            orchestration={orchestration.data}
            runtime={runtime.data}
            branchState={branchState.data}
            readiness={readiness.data}
            recovery={recovery.data}
            verification={verification.data}
            mcpSummary={mcpSummary}
            runningVerification={runVerification.isPending}
            refreshingBranch={refreshBranchState.isPending}
            runningAutomation={executeNextAutomationAction.isPending}
            onRunVerification={() => runVerification.mutate({ stop_on_failure: true })}
            onRefreshBranch={() => refreshBranchState.mutate()}
            onRunAutomation={() => executeNextAutomationAction.mutate()}
          />
        </div>
      </div>

      <div className="space-y-4">
        <CodeEvidenceDeck
            sessionDetail={sessionDetail.data}
            tasks={tasks.data}
            workers={workers.data}
            orchestration={orchestration.data}
            events={mergedEvents}
            workerEvents={mergedWorkerEvents}
            streamConnected={stream.connected}
            branchState={branchState.data}
            readiness={readiness.data}
            recovery={recovery.data}
            gitStatus={gitStatus.data}
            latestToolResult={runSafeBash.data ?? null}
            toolRunning={runSafeBash.isPending || gitStatus.isFetching}
            onRunGitStatus={() => gitStatus.refetch()}
            onRunSafeCommand={(command) => runSafeBash.mutate({ command })}
            tree={tree.data}
            file={currentFile.data}
            diff={diff.data}
            verification={verification.data}
            artifacts={artifacts.data}
            selectedFilePath={currentFilePath}
            onSelectFile={setSelectedFilePath}
            mcpServers={mcpServers.data}
            mcpResources={mcpResources.data}
            mcpConnecting={connectMcpServer.isPending}
            mcpDisconnecting={disconnectMcpServer.isPending}
            onConnectDemo={() => connectMcpServer.mutate({ server_name: "demo", transport: "stub" })}
            onConnectAuthDemo={() => connectMcpServer.mutate({ server_name: "auth-demo", transport: "stub" })}
            onDisconnect={(serverName) =>
              disconnectMcpServer.mutate({ server_name: serverName, transport: "stub" })
            }
            onSelectServer={setSelectedMcpServer}
            diagnostics={lspDiagnostics.data}
            symbols={lspSymbols.data}
            refreshingBranch={refreshBranchState.isPending}
            onRefreshBranch={() => refreshBranchState.mutate()}
            runningVerification={runVerification.isPending}
            onRunLint={() => runVerification.mutate({ stage: "lint", stop_on_failure: true })}
            onRunTypecheck={() => runVerification.mutate({ stage: "typecheck", stop_on_failure: true })}
            onRunUnitTest={() => runVerification.mutate({ stage: "unit_test", stop_on_failure: true })}
            onRunBuild={() => runVerification.mutate({ stage: "build", stop_on_failure: true })}
            onRunSmokeTest={() => runVerification.mutate({ stage: "smoke_test", stop_on_failure: true })}
            onRunPipeline={() => runVerification.mutate({ stop_on_failure: true })}
            recoveryResult={recoveryResult}
            recoveryActionLabel={recoveryAutomationAction ? formatCodeActionCallToAction(recoveryAutomationAction) : undefined}
            recoveryActionLoading={executeNextAutomationAction.isPending}
            recoveryActionDisabled={!recoveryAutomationAction}
            onRecoveryAction={recoveryAutomationAction ? () => executeNextAutomationAction.mutate() : undefined}
            plannerDrafts={plannerDrafts}
            creatingTask={createTask.isPending}
            assigningTask={architectPlanTask.isPending || architectRouteTask.isPending}
            updatingTask={requestTaskReview.isPending || submitReviewDecision.isPending || updateWorkerStatus.isPending}
            onCreateTask={(title, objective, acceptanceCriteria, taskPacket) =>
              createTask.mutate({
                title,
                objective,
                scope: taskPacket.scope,
                session_id: sessionId ?? undefined,
                acceptance_criteria: acceptanceCriteria,
                task_packet: taskPacket,
              })
            }
            onArchitectPlan={(taskId) =>
              architectPlanTask.mutate({
                taskId,
                payload: {
                  regenerate: true,
                  summary: "Architect drafted acceptance criteria and suggested executor routing.",
                  payload: { source: "cockpit", lane: CODE_LANES.architect },
                },
              }, {
                onSuccess: (result) => {
                  setPlannerDrafts((current) => ({
                    ...current,
                    [taskId]: result,
                  }));
                },
              })
            }
            onArchitectRoute={(taskId, acceptanceCriteria) =>
              architectRouteTask.mutate({
                taskId,
                payload: {
                  acceptance_criteria: plannerDrafts[taskId]?.acceptance_criteria ?? acceptanceCriteria,
                  summary: "Architect decomposed and routed the task to executor.",
                  route_to: plannerDrafts[taskId]?.route_to ?? CODE_LANES.executor,
                  payload: { source: "cockpit", lane: CODE_LANES.architect },
                },
              })
            }
            onRequestReview={(taskId) =>
              requestTaskReview.mutate({
                taskId,
                payload: {
                  summary: "Executor submitted implementation for reviewer decision.",
                  payload: { source: "cockpit", lane: CODE_LANES.executor },
                },
              })
            }
            onBeginReview={(taskId) =>
              updateWorkerStatus.mutate({
                workerName: CODE_LANES.reviewer,
                payload: {
                  worker_status: "running",
                  last_event_summary: `Reviewer is actively evaluating task #${taskId}.`,
                  lane: CODE_LANES.reviewer,
                  event_name: "lane.progressed",
                  payload: { source: "cockpit", task_id: taskId, review_state: "in_review" },
                },
              })
            }
            onAcceptReview={(taskId) =>
              submitReviewDecision.mutate({
                taskId,
                payload: {
                  decision: CODE_REVIEW_DECISIONS.accept,
                  summary: "Reviewer accepted the implementation.",
                  payload: { source: "cockpit", lane: CODE_LANES.reviewer },
                },
              })
            }
            onRejectReview={(taskId, reason, reasonCode, checklist) =>
              submitReviewDecision.mutate({
                taskId,
                payload: {
                  decision: CODE_REVIEW_DECISIONS.reject,
                  summary: "Reviewer rejected the implementation.",
                  reason: reason || "Follow-up changes requested before task completion.",
                  reason_code: reasonCode || "changes_requested",
                  checklist,
                  payload: { source: "cockpit", lane: CODE_LANES.reviewer },
                },
              })
            }
            onMarkWorkerReady={(workerName) =>
              updateWorkerStatus.mutate({
                workerName,
                payload: {
                  worker_status: "ready",
                  last_event_summary: `${workerName} lane is ready for the next handoff.`,
                  lane: workerName,
                  event_name: "lane.progressed",
                  payload: { source: "cockpit", lane_state: "ready" },
                },
              })
            }
            onMarkWorkerBlocked={(workerName) =>
              updateWorkerStatus.mutate({
                workerName,
                payload: {
                  worker_status: "blocked",
                  last_event_summary: `${workerName} lane is blocked and needs operator attention.`,
                  lane: workerName,
                  event_name: "lane.blocked",
                  payload: { source: "cockpit", lane_state: "blocked" },
                },
              })
            }
          />
      </div>
    </div>
  );
}
