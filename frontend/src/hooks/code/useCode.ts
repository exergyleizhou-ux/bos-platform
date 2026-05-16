import type { AxiosError } from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";

import { codeApi } from "@/api/codeApi";
import type {
  CodeTaskArchitectPlanRequest,
  CodeTaskArchitectRouteRequest,
  CodeCancelSessionRequest,
  CodeSafeBashRequest,
  CodeSessionCreateRequest,
  CodeSessionUpdateRequest,
  CodeTaskReviewDecisionRequest,
  CodeTaskReviewRequest,
  CodeTurnCreateRequest,
  CodeVerificationRunRequest,
  CodeWorkerStatusUpdateRequest,
} from "@/types/code";

export const codeKeys = {
  all: ["code"] as const,
  workspace: () => [...codeKeys.all, "workspace"] as const,
  workspaceStatus: () => [...codeKeys.all, "workspace-status"] as const,
  workspaceTree: (path: string) => [...codeKeys.all, "workspace-tree", path] as const,
  workspaceFile: (path: string) => [...codeKeys.all, "workspace-file", path] as const,
  sessions: () => [...codeKeys.all, "sessions"] as const,
  session: (id: number) => [...codeKeys.all, "session", id] as const,
  events: (id: number, afterSeq?: number) => [...codeKeys.all, "events", id, afterSeq ?? "all"] as const,
  diff: (id: number) => [...codeKeys.all, "diff", id] as const,
  artifacts: (id: number) => [...codeKeys.all, "artifacts", id] as const,
  verification: (id: number) => [...codeKeys.all, "verification", id] as const,
  gitStatus: (id: number) => [...codeKeys.all, "git-status", id] as const,
  branchState: (id: number) => [...codeKeys.all, "branch-state", id] as const,
  readiness: (id: number) => [...codeKeys.all, "readiness", id] as const,
  recovery: (id: number) => [...codeKeys.all, "recovery", id] as const,
  mcpServers: () => [...codeKeys.all, "mcp-servers"] as const,
  mcpResources: (serverName: string) => [...codeKeys.all, "mcp-resources", serverName] as const,
  lspDiagnostics: (language: string) => [...codeKeys.all, "lsp-diagnostics", language] as const,
  lspSymbols: (language: string) => [...codeKeys.all, "lsp-symbols", language] as const,
  tasks: () => [...codeKeys.all, "tasks"] as const,
  workers: () => [...codeKeys.all, "workers"] as const,
  orchestration: () => [...codeKeys.all, "orchestration"] as const,
  runtime: () => [...codeKeys.all, "runtime"] as const,
  releaseReadiness: () => [...codeKeys.all, "release-readiness"] as const,
  automationJobs: () => [...codeKeys.all, "automation-jobs"] as const,
  memorySnapshots: (sessionId: number) => [...codeKeys.all, "memory-snapshots", sessionId] as const,
  sessionSearch: (query: string, limit: number) => [...codeKeys.all, "session-search", query, limit] as const,
  reflections: () => [...codeKeys.all, "reflections"] as const,
  skills: () => [...codeKeys.all, "skills"] as const,
  workerEvents: (params?: { afterId?: number; lane?: string; taskId?: number; workerName?: string }) =>
    [
      ...codeKeys.all,
      "worker-events",
      params?.afterId ?? "all",
      params?.lane ?? "all",
      params?.taskId ?? "all",
      params?.workerName ?? "all",
    ] as const,
};

function getErrorDetail(error: unknown, fallback: string): string {
  const detail =
    (error as AxiosError<{ detail?: string }>)?.response?.data?.detail;
  return detail ?? fallback;
}

export function useCodeWorkspace(enabled = true) {
  return useQuery({
    queryKey: codeKeys.workspace(),
    queryFn: codeApi.getWorkspace,
    enabled,
    retry: false,
  });
}

export function useInitCodeWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: codeApi.initWorkspace,
    onSuccess: () => {
      toast.success("BOS Code workspace initialized");
      qc.invalidateQueries({ queryKey: codeKeys.workspace() });
      qc.invalidateQueries({ queryKey: codeKeys.workspaceStatus() });
    },
    onError: () => toast.error("Failed to initialize BOS Code workspace"),
  });
}

export function useCodeWorkspaceStatus(enabled = true) {
  return useQuery({
    queryKey: codeKeys.workspaceStatus(),
    queryFn: codeApi.getWorkspaceStatus,
    enabled,
    retry: false,
    refetchInterval: 30_000,
  });
}

export function useCodeWorkspaceTree(path = ".", enabled = true) {
  return useQuery({
    queryKey: codeKeys.workspaceTree(path),
    queryFn: () => codeApi.getWorkspaceTree(path),
    enabled,
  });
}

export function useCodeFile(path: string, enabled = true) {
  return useQuery({
    queryKey: codeKeys.workspaceFile(path),
    queryFn: () => codeApi.getWorkspaceFile(path),
    enabled: enabled && !!path,
  });
}

export function useCodeSessions(enabled = true) {
  return useQuery({
    queryKey: codeKeys.sessions(),
    queryFn: codeApi.listSessions,
    enabled,
    retry: false,
    refetchInterval: 15_000,
  });
}

export function useCreateCodeSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CodeSessionCreateRequest) => codeApi.createSession(payload),
    onSuccess: (session) => {
      toast.success("BOS Code session started");
      qc.invalidateQueries({ queryKey: codeKeys.sessions() });
      qc.invalidateQueries({ queryKey: codeKeys.workspaceStatus() });
      qc.invalidateQueries({ queryKey: codeKeys.session(session.id) });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to start BOS Code session")),
  });
}

export function useUpdateCodeSession(sessionId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CodeSessionUpdateRequest) => codeApi.updateSession(sessionId as number, payload),
    onSuccess: () => {
      if (!sessionId) return;
      toast.success("Thread title updated");
      qc.invalidateQueries({ queryKey: codeKeys.sessions() });
      qc.invalidateQueries({ queryKey: codeKeys.session(sessionId) });
      qc.invalidateQueries({ queryKey: codeKeys.events(sessionId) });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to update thread title")),
  });
}

export function useCodeSession(sessionId: number | null) {
  return useQuery({
    queryKey: codeKeys.session(sessionId ?? 0),
    queryFn: () => codeApi.getSession(sessionId as number),
    enabled: !!sessionId,
    refetchInterval: 10_000,
  });
}

export function useCreateCodeTurn(sessionId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CodeTurnCreateRequest) => codeApi.createTurn(sessionId as number, payload),
    onSuccess: () => {
      if (!sessionId) return;
      toast.success("Prompt dispatched");
      qc.invalidateQueries({ queryKey: codeKeys.sessions() });
      qc.invalidateQueries({ queryKey: codeKeys.session(sessionId) });
      qc.invalidateQueries({ queryKey: codeKeys.events(sessionId) });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to send BOS Code prompt")),
  });
}

export function useCancelCodeSession(sessionId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CodeCancelSessionRequest) => codeApi.cancelSession(sessionId as number, payload),
    onSuccess: () => {
      if (!sessionId) return;
      toast.success("BOS Code session cancelled");
      qc.invalidateQueries({ queryKey: codeKeys.sessions() });
      qc.invalidateQueries({ queryKey: codeKeys.session(sessionId) });
      qc.invalidateQueries({ queryKey: codeKeys.workspaceStatus() });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to cancel BOS Code session")),
  });
}

export function useCodeSessionEvents(sessionId: number | null, afterSeq?: number) {
  return useQuery({
    queryKey: codeKeys.events(sessionId ?? 0, afterSeq),
    queryFn: () => codeApi.getSessionEvents(sessionId as number, afterSeq),
    enabled: !!sessionId,
    refetchInterval: 8_000,
  });
}

export function useCodeDiff(sessionId: number | null) {
  return useQuery({
    queryKey: codeKeys.diff(sessionId ?? 0),
    queryFn: () => codeApi.getSessionDiff(sessionId as number),
    enabled: !!sessionId,
  });
}

export function useCodeArtifacts(sessionId: number | null) {
  return useQuery({
    queryKey: codeKeys.artifacts(sessionId ?? 0),
    queryFn: () => codeApi.getSessionArtifacts(sessionId as number),
    enabled: !!sessionId,
  });
}

export function useCodeVerification(sessionId: number | null) {
  return useQuery({
    queryKey: codeKeys.verification(sessionId ?? 0),
    queryFn: () => codeApi.getSessionVerification(sessionId as number),
    enabled: !!sessionId,
    refetchInterval: 12_000,
  });
}

export function useRunCodeVerification(sessionId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CodeVerificationRunRequest) => codeApi.runVerification(sessionId as number, payload),
    onSuccess: () => {
      if (!sessionId) return;
      toast.success("Verification started");
      qc.invalidateQueries({ queryKey: codeKeys.verification(sessionId) });
      qc.invalidateQueries({ queryKey: codeKeys.events(sessionId) });
      qc.invalidateQueries({ queryKey: codeKeys.session(sessionId) });
      qc.invalidateQueries({ queryKey: codeKeys.tasks() });
      qc.invalidateQueries({ queryKey: codeKeys.orchestration() });
      qc.invalidateQueries({ queryKey: [...codeKeys.all, "worker-events"] });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to run verification")),
  });
}

export function useCodeRuntime(enabled = true) {
  return useQuery({
    queryKey: codeKeys.runtime(),
    queryFn: codeApi.getRuntime,
    enabled,
    refetchInterval: 20_000,
  });
}

export function useCodeReleaseReadiness(enabled = true) {
  return useQuery({
    queryKey: codeKeys.releaseReadiness(),
    queryFn: codeApi.getReleaseReadiness,
    enabled,
    retry: false,
    refetchInterval: 60_000,
  });
}

export function useCodeAutomationJobs(enabled = true) {
  return useQuery({
    queryKey: codeKeys.automationJobs(),
    queryFn: codeApi.listAutomationJobs,
    enabled,
    refetchInterval: 20_000,
  });
}

export function useCreateCodeAutomationJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: codeApi.createAutomationJob,
    onSuccess: () => {
      toast.success("Automation created");
      qc.invalidateQueries({ queryKey: codeKeys.automationJobs() });
      qc.invalidateQueries({ queryKey: codeKeys.runtime() });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to create automation")),
  });
}

export function useUpdateCodeAutomationJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ jobId, payload }: { jobId: number; payload: Parameters<typeof codeApi.updateAutomationJob>[1] }) =>
      codeApi.updateAutomationJob(jobId, payload),
    onSuccess: () => {
      toast.success("Automation updated");
      qc.invalidateQueries({ queryKey: codeKeys.automationJobs() });
      qc.invalidateQueries({ queryKey: codeKeys.runtime() });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to update automation")),
  });
}

export function useRunCodeAutomationJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (jobId: number) => codeApi.runAutomationJob(jobId),
    onSuccess: () => {
      toast.success("Automation run started");
      qc.invalidateQueries({ queryKey: codeKeys.automationJobs() });
      qc.invalidateQueries({ queryKey: codeKeys.runtime() });
      qc.invalidateQueries({ queryKey: codeKeys.sessions() });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to run automation")),
  });
}

export function useCodeMemorySnapshots(sessionId: number | null) {
  return useQuery({
    queryKey: codeKeys.memorySnapshots(sessionId ?? 0),
    queryFn: () => codeApi.getMemorySnapshots(sessionId as number),
    enabled: !!sessionId,
    refetchInterval: 20_000,
  });
}

export function useRefreshCodeMemorySnapshot(sessionId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => codeApi.refreshMemorySnapshots(sessionId as number),
    onSuccess: () => {
      if (!sessionId) return;
      toast.success("Memory snapshot refreshed");
      qc.invalidateQueries({ queryKey: codeKeys.memorySnapshots(sessionId) });
      qc.invalidateQueries({ queryKey: codeKeys.session(sessionId) });
      qc.invalidateQueries({ queryKey: codeKeys.runtime() });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to refresh memory snapshot")),
  });
}

export function useSearchCodeSessions(query: string, limit = 5, enabled = true) {
  return useQuery({
    queryKey: codeKeys.sessionSearch(query, limit),
    queryFn: () => codeApi.searchSessions({ query, limit }),
    enabled: enabled && query.trim().length > 0,
  });
}

export function useCodeReflections(enabled = true) {
  return useQuery({
    queryKey: codeKeys.reflections(),
    queryFn: codeApi.listReflections,
    enabled,
    refetchInterval: 20_000,
  });
}

export function useRunCodeReflection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: codeApi.runReflection,
    onSuccess: () => {
      toast.success("Reflection completed");
      qc.invalidateQueries({ queryKey: codeKeys.reflections() });
      qc.invalidateQueries({ queryKey: codeKeys.skills() });
      qc.invalidateQueries({ queryKey: codeKeys.runtime() });
      qc.invalidateQueries({ queryKey: [...codeKeys.all, "worker-events"] });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to run reflection")),
  });
}

export function useCodeSkills(enabled = true) {
  return useQuery({
    queryKey: codeKeys.skills(),
    queryFn: codeApi.listSkills,
    enabled,
    refetchInterval: 20_000,
  });
}

export function useCreateCodeSkill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: codeApi.createSkill,
    onSuccess: () => {
      toast.success("Skill created");
      qc.invalidateQueries({ queryKey: codeKeys.skills() });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to create skill")),
  });
}

export function useUpdateCodeSkill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ skillId, payload }: { skillId: number; payload: Parameters<typeof codeApi.updateSkill>[1] }) =>
      codeApi.updateSkill(skillId, payload),
    onSuccess: () => {
      toast.success("Skill updated");
      qc.invalidateQueries({ queryKey: codeKeys.skills() });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to update skill")),
  });
}

export function useFeedbackCodeSkill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ skillId, payload }: { skillId: number; payload: Parameters<typeof codeApi.feedbackSkill>[1] }) =>
      codeApi.feedbackSkill(skillId, payload),
    onSuccess: () => {
      toast.success("Skill feedback saved");
      qc.invalidateQueries({ queryKey: codeKeys.skills() });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to save skill feedback")),
  });
}

export function useCodeGitStatus(sessionId: number | null) {
  return useQuery({
    queryKey: codeKeys.gitStatus(sessionId ?? 0),
    queryFn: () => codeApi.getGitStatus(sessionId as number),
    enabled: !!sessionId,
    refetchInterval: 15_000,
  });
}

export function useCodeBranchState(sessionId: number | null) {
  return useQuery({
    queryKey: codeKeys.branchState(sessionId ?? 0),
    queryFn: () => codeApi.getBranchState(sessionId as number),
    enabled: !!sessionId,
    refetchInterval: 20_000,
  });
}

export function useRefreshCodeBranchState(sessionId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => codeApi.refreshBranchState(sessionId as number),
    onSuccess: () => {
      if (!sessionId) return;
      toast.success("Branch posture refreshed");
      qc.invalidateQueries({ queryKey: codeKeys.branchState(sessionId) });
      qc.invalidateQueries({ queryKey: codeKeys.readiness(sessionId) });
      qc.invalidateQueries({ queryKey: codeKeys.events(sessionId) });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to refresh branch posture")),
  });
}

export function useCodeReadiness(sessionId: number | null) {
  return useQuery({
    queryKey: codeKeys.readiness(sessionId ?? 0),
    queryFn: () => codeApi.getReadiness(sessionId as number),
    enabled: !!sessionId,
    refetchInterval: 20_000,
  });
}

export function useCodeRecovery(sessionId: number | null) {
  return useQuery({
    queryKey: codeKeys.recovery(sessionId ?? 0),
    queryFn: () => codeApi.getRecovery(sessionId as number),
    enabled: !!sessionId,
    refetchInterval: 20_000,
  });
}

export function useCodeMcpServers(enabled = true) {
  return useQuery({
    queryKey: codeKeys.mcpServers(),
    queryFn: codeApi.listMcpServers,
    enabled,
    retry: false,
    refetchInterval: 20_000,
  });
}

export function useConnectCodeMcpServer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: codeApi.connectMcpServer,
    onSuccess: () => {
      toast.success("MCP server connected");
      qc.invalidateQueries({ queryKey: codeKeys.mcpServers() });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to connect MCP server")),
  });
}

export function useDisconnectCodeMcpServer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: codeApi.disconnectMcpServer,
    onSuccess: () => {
      toast.success("MCP server disconnected");
      qc.invalidateQueries({ queryKey: codeKeys.mcpServers() });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to disconnect MCP server")),
  });
}

export function useCodeMcpResources(serverName: string, enabled = true) {
  return useQuery({
    queryKey: codeKeys.mcpResources(serverName),
    queryFn: () => codeApi.listMcpResources(serverName),
    enabled: enabled && !!serverName,
    retry: false,
  });
}

export function useCodeLspDiagnostics(language = "python", enabled = true) {
  return useQuery({
    queryKey: codeKeys.lspDiagnostics(language),
    queryFn: () => codeApi.getLspDiagnostics(language),
    enabled,
    retry: false,
    refetchInterval: 20_000,
  });
}

export function useCodeLspSymbols(language = "python", enabled = true) {
  return useQuery({
    queryKey: codeKeys.lspSymbols(language),
    queryFn: () => codeApi.getLspSymbols(language),
    enabled,
    retry: false,
    refetchInterval: 20_000,
  });
}

export function useCodeTasks(enabled = true) {
  return useQuery({
    queryKey: codeKeys.tasks(),
    queryFn: codeApi.listTasks,
    enabled,
    retry: false,
    refetchInterval: 20_000,
  });
}

export function useCreateCodeTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: codeApi.createTask,
    onSuccess: () => {
      toast.success("Task created");
      qc.invalidateQueries({ queryKey: codeKeys.tasks() });
      qc.invalidateQueries({ queryKey: codeKeys.orchestration() });
      qc.invalidateQueries({ queryKey: [...codeKeys.all, "worker-events"] });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to create task")),
  });
}

export function useArchitectRouteCodeTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, payload }: { taskId: number; payload: CodeTaskArchitectRouteRequest }) =>
      codeApi.architectRouteTask(taskId, payload),
    onSuccess: () => {
      toast.success("Architect routed task");
      qc.invalidateQueries({ queryKey: codeKeys.tasks() });
      qc.invalidateQueries({ queryKey: codeKeys.workers() });
      qc.invalidateQueries({ queryKey: codeKeys.orchestration() });
      qc.invalidateQueries({ queryKey: [...codeKeys.all, "worker-events"] });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to route task with architect")),
  });
}

export function useArchitectPlanCodeTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, payload }: { taskId: number; payload?: CodeTaskArchitectPlanRequest }) =>
      codeApi.architectPlanTask(taskId, payload),
    onSuccess: () => {
      toast.success("Architect drafted plan");
      qc.invalidateQueries({ queryKey: codeKeys.tasks() });
      qc.invalidateQueries({ queryKey: codeKeys.workers() });
      qc.invalidateQueries({ queryKey: codeKeys.orchestration() });
      qc.invalidateQueries({ queryKey: [...codeKeys.all, "worker-events"] });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to draft architect plan")),
  });
}

export function useRequestCodeTaskReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, payload }: { taskId: number; payload?: CodeTaskReviewRequest }) =>
      codeApi.requestTaskReview(taskId, payload),
    onSuccess: () => {
      toast.success("Task sent to review");
      qc.invalidateQueries({ queryKey: codeKeys.tasks() });
      qc.invalidateQueries({ queryKey: codeKeys.workers() });
      qc.invalidateQueries({ queryKey: codeKeys.orchestration() });
      qc.invalidateQueries({ queryKey: [...codeKeys.all, "worker-events"] });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to request review")),
  });
}

export function useSubmitCodeTaskReviewDecision() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, payload }: { taskId: number; payload: CodeTaskReviewDecisionRequest }) =>
      codeApi.submitTaskReviewDecision(taskId, payload),
    onSuccess: (_task, variables) => {
      toast.success(variables.payload.decision === "accept" ? "Review accepted" : "Review rejected");
      qc.invalidateQueries({ queryKey: codeKeys.tasks() });
      qc.invalidateQueries({ queryKey: codeKeys.workers() });
      qc.invalidateQueries({ queryKey: codeKeys.orchestration() });
      qc.invalidateQueries({ queryKey: [...codeKeys.all, "worker-events"] });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to submit review decision")),
  });
}

export function useCodeWorkers(enabled = true) {
  return useQuery({
    queryKey: codeKeys.workers(),
    queryFn: codeApi.listWorkers,
    enabled,
    retry: false,
    refetchInterval: 20_000,
  });
}

export function useCodeOrchestration(enabled = true) {
  return useQuery({
    queryKey: codeKeys.orchestration(),
    queryFn: codeApi.getOrchestrationSnapshot,
    enabled,
    retry: false,
    refetchInterval: 10_000,
  });
}

export function useExecuteNextAutomationAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => codeApi.executeNextAutomationAction(),
    onSuccess: (result) => {
      toast.success(result.summary);
      if (result.session_id) {
        qc.invalidateQueries({ queryKey: codeKeys.session(result.session_id) });
        qc.invalidateQueries({ queryKey: codeKeys.events(result.session_id) });
        qc.invalidateQueries({ queryKey: codeKeys.verification(result.session_id) });
        qc.invalidateQueries({ queryKey: codeKeys.branchState(result.session_id) });
        qc.invalidateQueries({ queryKey: codeKeys.readiness(result.session_id) });
      }
      qc.invalidateQueries({ queryKey: codeKeys.tasks() });
      qc.invalidateQueries({ queryKey: codeKeys.workers() });
      qc.invalidateQueries({ queryKey: codeKeys.orchestration() });
      qc.invalidateQueries({ queryKey: [...codeKeys.all, "worker-events"] });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to execute next automation action")),
  });
}

export function useAssignCodeWorker() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: codeApi.assignWorker,
    onSuccess: () => {
      toast.success("Worker assigned");
      qc.invalidateQueries({ queryKey: codeKeys.workers() });
      qc.invalidateQueries({ queryKey: codeKeys.tasks() });
      qc.invalidateQueries({ queryKey: codeKeys.orchestration() });
      qc.invalidateQueries({ queryKey: [...codeKeys.all, "worker-events"] });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to assign worker")),
  });
}

export function useUpdateCodeWorkerStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ workerName, payload }: { workerName: string; payload: CodeWorkerStatusUpdateRequest }) =>
      codeApi.updateWorkerStatus(workerName, payload),
    onSuccess: () => {
      toast.success("Worker status updated");
      qc.invalidateQueries({ queryKey: codeKeys.workers() });
      qc.invalidateQueries({ queryKey: codeKeys.tasks() });
      qc.invalidateQueries({ queryKey: codeKeys.orchestration() });
      qc.invalidateQueries({ queryKey: [...codeKeys.all, "worker-events"] });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Failed to update worker status")),
  });
}

export function useCodeWorkerEvents(
  params: { afterId?: number; lane?: string; taskId?: number; workerName?: string } = {},
  enabled = true,
) {
  return useQuery({
    queryKey: codeKeys.workerEvents(params),
    queryFn: () => codeApi.listWorkerEvents(params),
    enabled,
    retry: false,
    refetchInterval: 8_000,
  });
}


export function useRunCodeSafeBash(sessionId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CodeSafeBashRequest) => codeApi.runSafeBash(sessionId as number, payload),
    onSuccess: (result) => {
      if (!sessionId) return;
      if (result.denied_reason) {
        toast.error(`Safe bash denied: ${result.denied_reason}`);
      } else if (result.success) {
        toast.success("Safe bash executed");
      } else {
        toast.error("Safe bash finished with errors");
      }
      qc.invalidateQueries({ queryKey: codeKeys.session(sessionId) });
      qc.invalidateQueries({ queryKey: codeKeys.events(sessionId) });
      qc.invalidateQueries({ queryKey: codeKeys.gitStatus(sessionId) });
    },
    onError: (error) => toast.error(getErrorDetail(error, "Safe bash execution failed")),
  });
}
