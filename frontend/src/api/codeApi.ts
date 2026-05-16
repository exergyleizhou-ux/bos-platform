import client from "@/api/client";
import type {
  CodeArtifact,
  CodeAutomationExecutionResponse,
  CodeAutomationJob,
  CodeAutomationJobCreateRequest,
  CodeAutomationJobUpdateRequest,
  CodeBranchState,
  CodeCancelSessionRequest,
  CodeDiffResponse,
  CodeEventListResponse,
  CodeGitStatusResponse,
  CodeLspDiagnosticsPayload,
  CodeLspSymbolsPayload,
  CodeMemoryRefreshResponse,
  CodeMemorySnapshot,
  CodeMcpResource,
  CodeMcpResourceReadResponse,
  CodeMcpServer,
  CodeMcpServerConnectRequest,
  CodeOrchestrationSnapshot,
  CodeReadinessResponse,
  CodeReleaseReadiness,
  CodeRecoveryResponse,
  CodeReflectionRun,
  CodeReflectionRunRequest,
  CodeRuntimeResponse,
  CodeSessionCreateRequest,
  CodeSessionDetail,
  CodeSessionListResponse,
  CodeSessionSearchRequest,
  CodeSessionSearchResponse,
  CodeSession,
  CodeSessionUpdateRequest,
  CodeSafeBashRequest,
  CodeSkill,
  CodeSkillCreateRequest,
  CodeSkillFeedbackRequest,
  CodeSkillUpdateRequest,
  CodeToolExecutionResponse,
  CodeTask,
  CodeTaskArchitectPlanRequest,
  CodeTaskArchitectPlanResponse,
  CodeTaskArchitectRouteRequest,
  CodeTaskCreateRequest,
  CodeTaskReviewDecisionRequest,
  CodeTaskReviewRequest,
  CodeTurnCreateRequest,
  CodeTurn,
  CodeVerificationResponse,
  CodeVerificationRunRequest,
  CodeWorkspace,
  CodeWorkspaceFileResponse,
  CodeWorkspaceInitRequest,
  CodeWorkspaceStatus,
  CodeWorkspaceTreeResponse,
  CodeWorker,
  CodeWorkerAssignRequest,
  CodeWorkerEventListResponse,
  CodeWorkerStatusUpdateRequest,
} from "@/types/code";

export const codeApi = {
  initWorkspace: async (payload: CodeWorkspaceInitRequest = {}): Promise<CodeWorkspace> => {
    const { data } = await client.post<CodeWorkspace>("/code/workspace/init", payload);
    return data;
  },
  getWorkspace: async (): Promise<CodeWorkspace> => {
    const { data } = await client.get<CodeWorkspace>("/code/workspace");
    return data;
  },
  getWorkspaceStatus: async (): Promise<CodeWorkspaceStatus> => {
    const { data } = await client.get<CodeWorkspaceStatus>("/code/workspace/status");
    return data;
  },
  getWorkspaceTree: async (path = "."): Promise<CodeWorkspaceTreeResponse> => {
    const { data } = await client.get<CodeWorkspaceTreeResponse>("/code/workspace/tree", { params: { path } });
    return data;
  },
  getWorkspaceFile: async (path: string): Promise<CodeWorkspaceFileResponse> => {
    const { data } = await client.get<CodeWorkspaceFileResponse>("/code/workspace/file", { params: { path } });
    return data;
  },
  listSessions: async (): Promise<CodeSessionListResponse> => {
    const { data } = await client.get<CodeSessionListResponse>("/code/sessions");
    return data;
  },
  createSession: async (payload: CodeSessionCreateRequest): Promise<CodeSession> => {
    const { data } = await client.post<CodeSession>("/code/sessions", payload);
    return data;
  },
  updateSession: async (sessionId: number, payload: CodeSessionUpdateRequest): Promise<CodeSession> => {
    const { data } = await client.patch<CodeSession>(`/code/sessions/${sessionId}`, payload);
    return data;
  },
  getSession: async (sessionId: number): Promise<CodeSessionDetail> => {
    const { data } = await client.get<CodeSessionDetail>(`/code/sessions/${sessionId}`);
    return data;
  },
  createTurn: async (sessionId: number, payload: CodeTurnCreateRequest): Promise<CodeTurn> => {
    const { data } = await client.post<CodeTurn>(`/code/sessions/${sessionId}/turns`, payload);
    return data;
  },
  streamTurn: async (
    sessionId: number,
    payload: CodeTurnCreateRequest,
    token: string,
    handlers: {
      onDelta: (delta: string) => void;
      onDone: () => void;
      onError: (detail: string) => void;
    },
    signal?: AbortSignal,
  ): Promise<void> => {
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
    const url = new URL(`${apiBaseUrl}/code/sessions/${sessionId}/stream`);
    url.searchParams.set("user_message", payload.user_message);
    if (payload.provider) {
      url.searchParams.set("provider", payload.provider);
    }
    if (payload.model) {
      url.searchParams.set("model", payload.model);
    }

    const response = await fetch(url.toString(), {
      signal,
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "text/event-stream",
      },
    });
    if (!response.ok || !response.body) {
      throw new Error(`Streaming request failed with HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";

      for (const event of events) {
        const dataLine = event
          .split("\n")
          .find((line) => line.startsWith("data:"));
        if (!dataLine) continue;
        const raw = dataLine.slice(5).trim();
        if (!raw) continue;
        const parsed = JSON.parse(raw) as { type?: string; delta?: string; detail?: string };
        if (parsed.type === "delta" && parsed.delta) handlers.onDelta(parsed.delta);
        else if (parsed.type === "done") handlers.onDone();
        else if (parsed.type === "error") handlers.onError(parsed.detail ?? "Streaming failed");
      }
    }
  },
  cancelSession: async (sessionId: number, payload: CodeCancelSessionRequest = {}): Promise<CodeSession> => {
    const { data } = await client.post<CodeSession>(`/code/sessions/${sessionId}/cancel`, payload);
    return data;
  },
  getSessionEvents: async (sessionId: number, afterSeq?: number): Promise<CodeEventListResponse> => {
    const { data } = await client.get<CodeEventListResponse>(`/code/sessions/${sessionId}/events`, {
      params: afterSeq === undefined ? undefined : { after_seq: afterSeq },
    });
    return data;
  },
  getSessionDiff: async (sessionId: number): Promise<CodeDiffResponse> => {
    const { data } = await client.get<CodeDiffResponse>(`/code/sessions/${sessionId}/diff`);
    return data;
  },
  getSessionArtifacts: async (sessionId: number): Promise<CodeArtifact[]> => {
    const { data } = await client.get<CodeArtifact[]>(`/code/sessions/${sessionId}/artifacts`);
    return data;
  },
  getSessionVerification: async (sessionId: number): Promise<CodeVerificationResponse> => {
    const { data } = await client.get<CodeVerificationResponse>(`/code/sessions/${sessionId}/verification`);
    return data;
  },
  runVerification: async (sessionId: number, payload: CodeVerificationRunRequest): Promise<CodeVerificationResponse> => {
    const { data } = await client.post<CodeVerificationResponse>(`/code/sessions/${sessionId}/verification/run`, payload);
    return data;
  },
  runSafeBash: async (sessionId: number, payload: CodeSafeBashRequest): Promise<CodeToolExecutionResponse> => {
    const { data } = await client.post<CodeToolExecutionResponse>(`/code/sessions/${sessionId}/tools/safe-bash`, payload);
    return data;
  },
  getGitStatus: async (sessionId: number): Promise<CodeGitStatusResponse> => {
    const { data } = await client.get<CodeGitStatusResponse>(`/code/sessions/${sessionId}/git/status`);
    return data;
  },
  getBranchState: async (sessionId: number): Promise<CodeBranchState> => {
    const { data } = await client.get<CodeBranchState>(`/code/sessions/${sessionId}/git/branch-state`);
    return data;
  },
  refreshBranchState: async (sessionId: number): Promise<CodeBranchState> => {
    const { data } = await client.post<CodeBranchState>(`/code/sessions/${sessionId}/git/refresh`);
    return data;
  },
  getReadiness: async (sessionId: number): Promise<CodeReadinessResponse> => {
    const { data } = await client.get<CodeReadinessResponse>(`/code/sessions/${sessionId}/readiness`);
    return data;
  },
  getRecovery: async (sessionId: number): Promise<CodeRecoveryResponse> => {
    const { data } = await client.get<CodeRecoveryResponse>(`/code/sessions/${sessionId}/recovery`);
    return data;
  },
  listMcpServers: async (): Promise<CodeMcpServer[]> => {
    const { data } = await client.get<CodeMcpServer[]>("/code/workspace/mcp/servers");
    return data;
  },
  connectMcpServer: async (payload: CodeMcpServerConnectRequest): Promise<CodeMcpServer> => {
    const { data } = await client.post<CodeMcpServer>("/code/workspace/mcp/servers/connect", payload);
    return data;
  },
  disconnectMcpServer: async (payload: CodeMcpServerConnectRequest): Promise<CodeMcpServer> => {
    const { data } = await client.post<CodeMcpServer>("/code/workspace/mcp/servers/disconnect", payload);
    return data;
  },
  listMcpResources: async (serverName: string): Promise<CodeMcpResource[]> => {
    const { data } = await client.get<CodeMcpResource[]>("/code/workspace/mcp/resources", {
      params: { server_name: serverName },
    });
    return data;
  },
  readMcpResource: async (serverName: string, uri: string): Promise<CodeMcpResourceReadResponse> => {
    const { data } = await client.get<CodeMcpResourceReadResponse>("/code/workspace/mcp/resource", {
      params: { server_name: serverName, uri },
    });
    return data;
  },
  getLspDiagnostics: async (language = "python"): Promise<CodeLspDiagnosticsPayload> => {
    const { data } = await client.get<CodeLspDiagnosticsPayload>("/code/workspace/lsp/diagnostics", {
      params: { language },
    });
    return data;
  },
  getLspSymbols: async (language = "python"): Promise<CodeLspSymbolsPayload> => {
    const { data } = await client.get<CodeLspSymbolsPayload>("/code/workspace/lsp/symbols", {
      params: { language },
    });
    return data;
  },
  listTasks: async (): Promise<CodeTask[]> => {
    const { data } = await client.get<CodeTask[]>("/code/workspace/tasks");
    return data;
  },
  createTask: async (payload: CodeTaskCreateRequest): Promise<CodeTask> => {
    const { data } = await client.post<CodeTask>("/code/workspace/tasks", payload);
    return data;
  },
  architectRouteTask: async (taskId: number, payload: CodeTaskArchitectRouteRequest): Promise<CodeTask> => {
    const { data } = await client.post<CodeTask>(`/code/workspace/tasks/${taskId}/architect-route`, payload);
    return data;
  },
  architectPlanTask: async (
    taskId: number,
    payload: CodeTaskArchitectPlanRequest = {},
  ): Promise<CodeTaskArchitectPlanResponse> => {
    const { data } = await client.post<CodeTaskArchitectPlanResponse>(`/code/workspace/tasks/${taskId}/architect-plan`, payload);
    return data;
  },
  requestTaskReview: async (taskId: number, payload: CodeTaskReviewRequest = {}): Promise<CodeTask> => {
    const { data } = await client.post<CodeTask>(`/code/workspace/tasks/${taskId}/review-request`, payload);
    return data;
  },
  submitTaskReviewDecision: async (
    taskId: number,
    payload: CodeTaskReviewDecisionRequest,
  ): Promise<CodeTask> => {
    const { data } = await client.post<CodeTask>(`/code/workspace/tasks/${taskId}/review-decision`, payload);
    return data;
  },
  listWorkers: async (): Promise<CodeWorker[]> => {
    const { data } = await client.get<CodeWorker[]>("/code/workspace/workers");
    return data;
  },
  getOrchestrationSnapshot: async (): Promise<CodeOrchestrationSnapshot> => {
    const { data } = await client.get<CodeOrchestrationSnapshot>("/code/workspace/orchestration");
    return data;
  },
  executeNextAutomationAction: async (): Promise<CodeAutomationExecutionResponse> => {
    const { data } = await client.post<CodeAutomationExecutionResponse>("/code/workspace/orchestration/execute-next-automation");
    return data;
  },
  getRuntime: async (): Promise<CodeRuntimeResponse> => {
    const { data } = await client.get<CodeRuntimeResponse>("/code/workspace/runtime");
    return data;
  },
  getReleaseReadiness: async (): Promise<CodeReleaseReadiness> => {
    const { data } = await client.get<CodeReleaseReadiness>("/code/release-readiness");
    return data;
  },
  listAutomationJobs: async (): Promise<CodeAutomationJob[]> => {
    const { data } = await client.get<CodeAutomationJob[]>("/code/workspace/automations");
    return data;
  },
  createAutomationJob: async (payload: CodeAutomationJobCreateRequest): Promise<CodeAutomationJob> => {
    const { data } = await client.post<CodeAutomationJob>("/code/workspace/automations", payload);
    return data;
  },
  updateAutomationJob: async (jobId: number, payload: CodeAutomationJobUpdateRequest): Promise<CodeAutomationJob> => {
    const { data } = await client.patch<CodeAutomationJob>(`/code/workspace/automations/${jobId}`, payload);
    return data;
  },
  runAutomationJob: async (jobId: number): Promise<CodeAutomationJob> => {
    const { data } = await client.post<CodeAutomationJob>(`/code/workspace/automations/${jobId}/run`);
    return data;
  },
  getMemorySnapshots: async (sessionId: number): Promise<CodeMemorySnapshot[]> => {
    const { data } = await client.get<CodeMemorySnapshot[]>(`/code/memory/${sessionId}`);
    return data;
  },
  refreshMemorySnapshots: async (sessionId: number): Promise<CodeMemoryRefreshResponse> => {
    const { data } = await client.post<CodeMemoryRefreshResponse>(`/code/memory/${sessionId}/refresh`);
    return data;
  },
  searchSessions: async (payload: CodeSessionSearchRequest): Promise<CodeSessionSearchResponse> => {
    const { data } = await client.post<CodeSessionSearchResponse>("/code/session-search", payload);
    return data;
  },
  listReflections: async (): Promise<CodeReflectionRun[]> => {
    const { data } = await client.get<CodeReflectionRun[]>("/code/workspace/reflections");
    return data;
  },
  runReflection: async (payload: CodeReflectionRunRequest): Promise<CodeReflectionRun> => {
    const { data } = await client.post<CodeReflectionRun>("/code/workspace/reflections/run", payload);
    return data;
  },
  listSkills: async (): Promise<CodeSkill[]> => {
    const { data } = await client.get<CodeSkill[]>("/code/workspace/skills");
    return data;
  },
  createSkill: async (payload: CodeSkillCreateRequest): Promise<CodeSkill> => {
    const { data } = await client.post<CodeSkill>("/code/workspace/skills", payload);
    return data;
  },
  updateSkill: async (skillId: number, payload: CodeSkillUpdateRequest): Promise<CodeSkill> => {
    const { data } = await client.patch<CodeSkill>(`/code/workspace/skills/${skillId}`, payload);
    return data;
  },
  feedbackSkill: async (skillId: number, payload: CodeSkillFeedbackRequest): Promise<CodeSkill> => {
    const { data } = await client.post<CodeSkill>(`/code/workspace/skills/${skillId}/feedback`, payload);
    return data;
  },
  assignWorker: async (payload: CodeWorkerAssignRequest): Promise<CodeWorker> => {
    const { data } = await client.post<CodeWorker>("/code/workspace/workers/assign", payload);
    return data;
  },
  updateWorkerStatus: async (workerName: string, payload: CodeWorkerStatusUpdateRequest): Promise<CodeWorker> => {
    const { data } = await client.post<CodeWorker>(`/code/workspace/workers/${workerName}/status`, payload);
    return data;
  },
  listWorkerEvents: async (
    params: { afterId?: number; lane?: string; taskId?: number; workerName?: string } = {},
  ): Promise<CodeWorkerEventListResponse> => {
    const { data } = await client.get<CodeWorkerEventListResponse>("/code/workspace/worker-events", {
      params: {
        after_id: params.afterId,
        lane: params.lane,
        task_id: params.taskId,
        worker_name: params.workerName,
      },
    });
    return data;
  },
};
