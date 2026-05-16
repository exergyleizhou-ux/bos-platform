import {
  Bot,
  CheckCircle2,
  Compass,
  SendHorizontal,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CardBody, CardHeader } from "@/components/ui/Card";
import { CockpitPanel } from "@/components/ui/Cockpit";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { translateText } from "@/lib/i18n";
import { pickCodeFocusTask } from "@/lib/code-orchestration-read-model";
import { CODE_LANES, CODE_TASK_STATUSES } from "@/lib/codeProtocol";
import { formatDateTime, formatRelativeTime } from "@/lib/utils";
import type {
  CodeOrchestrationSnapshot,
  CodeSession,
  CodeTaskPacket,
  CodeTask,
  CodeTaskArchitectPlanResponse,
  CodeWorkerEvent,
} from "@/types/code";

interface CodeWorkThreadProps {
  activeSession?: CodeSession | null;
  orchestration?: CodeOrchestrationSnapshot;
  tasks?: CodeTask[];
  workerEvents?: CodeWorkerEvent[];
  plannerDrafts?: Record<number, CodeTaskArchitectPlanResponse>;
  prompt: string;
  onPromptChange: (value: string) => void;
  submittingPrompt: boolean;
  onSubmitPrompt: () => void;
  creating: boolean;
  onCreateTask: (title: string, objective: string, acceptanceCriteria: string[], taskPacket: CodeTaskPacket) => void;
  assigning: boolean;
  updating: boolean;
  onArchitectPlan: (taskId: number) => void;
  onArchitectRoute: (taskId: number, acceptanceCriteria: string[]) => void;
  onRequestReview: (taskId: number) => void;
  onBeginReview: (taskId: number) => void;
  onAcceptReview: (taskId: number) => void;
  onRejectReview: (taskId: number, reason: string, reasonCode: string, checklist: string[]) => void;
}

type ThreadSpeaker = "task" | "architect" | "reviewer" | "system";

interface ThreadMessage {
  id: string;
  speaker: ThreadSpeaker;
  title: string;
  body: string;
  timestamp?: string | null;
  badges?: string[];
  checklist?: string[];
}

function speakerIcon(speaker: ThreadSpeaker) {
  switch (speaker) {
    case "architect":
      return <Compass className="h-4 w-4 text-sky-300" />;
    case "reviewer":
      return <CheckCircle2 className="h-4 w-4 text-emerald-300" />;
    case "system":
      return <ShieldAlert className="h-4 w-4 text-amber-300" />;
    default:
      return <Bot className="h-4 w-4 text-brand-300" />;
  }
}

function speakerShell(speaker: ThreadSpeaker) {
  switch (speaker) {
    case "architect":
      return "mr-20 border-sky-400/10 bg-sky-500/10";
    case "reviewer":
      return "ml-14 border-emerald-400/10 bg-emerald-500/10";
    case "system":
      return "mr-10 border-amber-400/10 bg-amber-500/10";
    default:
      return "mr-16 border-white/10 bg-white/5";
  }
}

function buildSystemGuidance(taskStatus?: string): string {
  switch (taskStatus) {
    case CODE_TASK_STATUSES.created:
      return translateText("Task created and waiting for architect planning. The next clean move is to let architect draft the route and acceptance bar before execution starts.");
    case CODE_TASK_STATUSES.running:
      return translateText("Execution is in motion. Keep the thread focused on the work itself, then hand it into review when the change has a clear story.");
    case CODE_TASK_STATUSES.reviewPending:
      return translateText("Review requested and waiting for reviewer pickup. Keep the thread stable and avoid pretending the gate is already cleared.");
    case CODE_TASK_STATUSES.inReview:
      return translateText("Reviewer is actively evaluating the implementation. An acceptance moves the task into verification. A rejection should leave a precise trail back to execution.");
    case CODE_TASK_STATUSES.verificationPending:
      return translateText("Review accepted; verification is now the only remaining gate before completion.");
    case CODE_TASK_STATUSES.blocked:
      return translateText("The thread is blocked. Read the latest reviewer or verification notes first, then decide whether to revise, reroute, or recover.");
    default:
      return translateText("Start with a task or a prompt. Once the thread starts moving, architect, executor, and reviewer will each leave a readable trace here.");
  }
}

export function CodeWorkThread({
  activeSession,
  orchestration,
  tasks,
  workerEvents,
  plannerDrafts,
  prompt,
  onPromptChange,
  submittingPrompt,
  onSubmitPrompt,
  creating,
  onCreateTask,
  assigning,
  updating,
  onArchitectPlan,
  onArchitectRoute,
  onRequestReview,
  onBeginReview,
  onAcceptReview,
  onRejectReview,
}: CodeWorkThreadProps) {
  const [title, setTitle] = useState(translateText("Prepare next engineering slice"));
  const [objective, setObjective] = useState(translateText("Coordinate the next BOS Code implementation objective."));
  const [scope, setScope] = useState("code/orchestration");
  const [repo, setRepo] = useState("canonical BOS repository worktree");
  const [branchPolicy, setBranchPolicy] = useState(
    "Use the active session branch and refresh branch posture before merge decisions.",
  );
  const [criteriaText, setCriteriaText] = useState(
    "- Architect validates scope before routing.\n- Reviewer accepts the implementation or records a structured rejection.\n- Verification gate passes before completion.",
  );
  const [acceptanceTestsText, setAcceptanceTestsText] = useState(
    "- Refresh branch posture before broad verification.\n- Run the relevant verification gate before treating the task as complete.",
  );
  const [commitPolicy, setCommitPolicy] = useState("Keep changes scoped and reviewer-friendly before handoff.");
  const [reportingContract, setReportingContract] = useState(
    "Return a concise implementation summary, changed surfaces, verification posture, and next review action.",
  );
  const [escalationPolicy, setEscalationPolicy] = useState(
    "Escalate only when the task is blocked by ambiguous scope, missing access, or unsafe uncertainty.",
  );
  const [showTaskDraft, setShowTaskDraft] = useState(false);

  const activeTask =
    (orchestration?.focus_task_id
      ? (tasks ?? []).find((task) => task.id === orchestration.focus_task_id)
      : null) ??
    pickCodeFocusTask(tasks ?? []) ??
    tasks?.[0];

  const plannerDraft = activeTask ? plannerDrafts?.[activeTask.id] : undefined;
  const taskEvents = useMemo(
    () => (workerEvents ?? []).filter((event) => event.task_id === activeTask?.id).sort((a, b) => a.id - b.id),
    [activeTask?.id, workerEvents],
  );
  const latestReviewerEvent = [...taskEvents].reverse().find((event) => event.lane === CODE_LANES.reviewer);
  const structuredTaskPacket: CodeTaskPacket = {
    objective,
    scope,
    repo,
    branch_policy: branchPolicy,
    acceptance_tests: acceptanceTestsText
      .split("\n")
      .map((item) => item.replace(/^-\s*/, "").trim())
      .filter(Boolean),
    commit_policy: commitPolicy,
    reporting_contract: reportingContract,
    escalation_policy: escalationPolicy,
  };

  const threadMessages = useMemo<ThreadMessage[]>(() => {
    if (!activeTask) {
      return [
        {
          id: "empty-thread",
          speaker: "system",
          title: translateText("The workspace is quiet"),
          body: translateText("Start with a task or a prompt. BOS Code will turn that into a readable working thread instead of dropping you into a wall of controls."),
        },
      ];
    }

    const messages: ThreadMessage[] = [
      {
        id: `task-${activeTask.id}`,
        speaker: "task",
        title: activeTask.title,
        body: activeTask.task_packet?.scope
          ? `${activeTask.objective}\n\n${translateText("Scope")}: ${activeTask.task_packet.scope}`
          : activeTask.objective,
        badges: [
          activeTask.task_status,
          activeSession?.provider ?? "openai",
          activeSession?.model ?? "gpt-5.4-mini",
        ],
        checklist: activeTask.task_packet?.acceptance_tests?.length
          ? activeTask.task_packet.acceptance_tests
          : undefined,
      },
    ];

    if (plannerDraft) {
      messages.push({
        id: `architect-draft-${activeTask.id}`,
        speaker: "architect",
        title: translateText("Architect drafted a route"),
        body: plannerDraft.plan_summary,
        badges: [`route ${plannerDraft.route_to}`],
        checklist: plannerDraft.acceptance_criteria,
      });
    } else {
      const architectEvent = [...taskEvents].reverse().find((event) => event.lane === CODE_LANES.architect);
      if (architectEvent) {
        messages.push({
          id: `architect-event-${architectEvent.id}`,
          speaker: "architect",
          title: translateText("Architect touched this thread"),
          body: architectEvent.summary ?? translateText("Architect activity is recorded for this task."),
          timestamp: architectEvent.created_at,
          badges: architectEvent.payload.route_suggestion ? [`route ${String(architectEvent.payload.route_suggestion)}`] : undefined,
          checklist: Array.isArray(architectEvent.payload.acceptance_criteria)
            ? (architectEvent.payload.acceptance_criteria as string[])
            : undefined,
        });
      }
    }

    if (latestReviewerEvent) {
        messages.push({
          id: `review-${latestReviewerEvent.id}`,
          speaker: "reviewer",
          title:
            latestReviewerEvent.event_name === "review.accepted"
            ? translateText("Reviewer accepted the handoff")
            : latestReviewerEvent.event_name === "review.rejected"
              ? translateText("Reviewer asked for changes")
              : translateText("Review is queued and waiting for reviewer pickup"),
          body: latestReviewerEvent.summary ?? translateText("The latest review event is available in the audit rail."),
          timestamp: latestReviewerEvent.created_at,
          badges: latestReviewerEvent.payload.reason_code ? [String(latestReviewerEvent.payload.reason_code)] : undefined,
          checklist: Array.isArray(latestReviewerEvent.payload.checklist)
            ? (latestReviewerEvent.payload.checklist as string[])
          : undefined,
      });
    }

    messages.push({
      id: `system-${activeTask.id}`,
      speaker: "system",
      title: translateText("System guidance"),
      body: buildSystemGuidance(activeTask.task_status),
      badges: orchestration
        ? [`verification ${orchestration.verification_gate}`, `merge ${orchestration.merge_readiness}`]
        : undefined,
    });

    return messages;
  }, [activeSession?.model, activeSession?.provider, activeTask, latestReviewerEvent, orchestration, plannerDraft, taskEvents]);

  return (
    <CockpitPanel tone="emphasis" className="min-h-[48rem] p-5 lg:p-6">
      <CardHeader
        title={translateText("Work Thread")}
        description={translateText("Stay with the thread. Let the work speak first, and let the deeper controls stay available without dominating the room.")}
        action={<Badge variant="brand">{translateText(activeTask?.task_status ?? "idle")}</Badge>}
      />
      <CardBody className="space-y-6">
        <div className="space-y-4">
          {threadMessages.map((message) => (
            <div key={message.id} className={`assistant-thread-shell rounded-2xl border border-white/8 p-5 ${speakerShell(message.speaker)}`}>
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-white/10 bg-white/6">
                    {speakerIcon(message.speaker)}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">{message.title}</p>
                    {message.timestamp ? (
                      <p className="mt-1 text-xs text-surface-500">
                        {formatRelativeTime(message.timestamp)} / {formatDateTime(message.timestamp)}
                      </p>
                    ) : null}
                  </div>
                </div>
                {message.badges?.length ? (
                  <div className="flex flex-wrap justify-end gap-2">
                    {message.badges.map((chip) => (
                      <Badge key={`${message.id}-${chip}`} variant="neutral">
                        {chip}
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </div>
              <p className="mt-4 text-[1.04rem] leading-8 text-surface-100">{message.body}</p>
              {message.checklist?.length ? (
                <div className="mt-4 space-y-2">
                  {message.checklist.map((item, index) => (
                    <div
                      key={`${message.id}-check-${index}`}
                      className="rounded-2xl border border-white/8 bg-white/4 px-3 py-3 text-sm text-surface-200"
                    >
                      {item}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </div>

        <div className="assistant-thread-stage rounded-[28px] border border-white/8 p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-white">{translateText("Compose the next move")}</p>
              <p className="mt-1 text-sm leading-6 text-surface-400">
                {translateText("Stay in the thread. Open a task when you need structure, or simply keep talking to BOS Code about what should happen next.")}
              </p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => setShowTaskDraft((value) => !value)}>
              {translateText(showTaskDraft ? "Hide task draft" : "Show task draft")}
            </Button>
          </div>

          {showTaskDraft ? (
            <div className="mt-4 grid gap-3">
              <Input label="Next task title" value={title} onChange={(event) => setTitle(event.target.value)} />
              <Textarea label="Task objective" value={objective} onChange={(event) => setObjective(event.target.value)} autoResize />
              <Input label="Scope" value={scope} onChange={(event) => setScope(event.target.value)} />
              <Input label="Repo surface" value={repo} onChange={(event) => setRepo(event.target.value)} />
              <Textarea label="Branch policy" value={branchPolicy} onChange={(event) => setBranchPolicy(event.target.value)} autoResize />
              <Textarea
                label="Acceptance criteria seed"
                value={criteriaText}
                onChange={(event) => setCriteriaText(event.target.value)}
                autoResize
              />
              <Textarea
                label="Acceptance tests"
                value={acceptanceTestsText}
                onChange={(event) => setAcceptanceTestsText(event.target.value)}
                autoResize
              />
              <Textarea label="Commit policy" value={commitPolicy} onChange={(event) => setCommitPolicy(event.target.value)} autoResize />
              <Textarea
                label="Reporting contract"
                value={reportingContract}
                onChange={(event) => setReportingContract(event.target.value)}
                autoResize
              />
              <Textarea
                label="Escalation policy"
                value={escalationPolicy}
                onChange={(event) => setEscalationPolicy(event.target.value)}
                autoResize
              />
            </div>
          ) : null}

          <div className="mt-4 space-y-3">
            <Textarea
              label="Message to BOS Code"
              value={prompt}
              onChange={(event) => onPromptChange(event.target.value)}
              placeholder="Talk to BOS Code here. Ask what should happen next, or hand it the next piece of engineering work."
              autoResize
              className="min-h-[7.5rem]"
            />
            <div className="flex flex-wrap gap-3">
              <Button
                leftIcon={<SendHorizontal className="h-4 w-4" />}
                loading={submittingPrompt}
                disabled={!prompt.trim()}
                onClick={onSubmitPrompt}
              >
                {translateText("Continue the thread")}
              </Button>
              <Button
                variant="outline"
                leftIcon={<Sparkles className="h-4 w-4" />}
                loading={creating}
                onClick={() =>
                  onCreateTask(
                    title,
                    objective,
                    criteriaText
                      .split("\n")
                      .map((item) => item.replace(/^-\s*/, "").trim())
                      .filter(Boolean),
                    structuredTaskPacket,
                  )
                }
              >
                {translateText("Open a new task")}
              </Button>

              {activeTask?.task_status === CODE_TASK_STATUSES.created ? (
                <>
                  <Button size="sm" variant="ghost" loading={assigning} onClick={() => activeTask && onArchitectPlan(activeTask.id)}>
                    {translateText("Draft with architect")}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    loading={assigning}
                    onClick={() =>
                      activeTask &&
                      onArchitectRoute(
                        activeTask.id,
                        plannerDraft?.acceptance_criteria ?? ((activeTask.acceptance_criteria as string[]) ?? []),
                      )
                    }
                  >
                    {translateText("Route with architect")}
                  </Button>
                </>
              ) : null}

              {activeTask?.task_status === CODE_TASK_STATUSES.running ? (
                <Button size="sm" variant="secondary" loading={updating} onClick={() => activeTask && onRequestReview(activeTask.id)}>
                  {translateText("Send to review")}
                </Button>
              ) : null}

              {activeTask?.task_status === CODE_TASK_STATUSES.reviewPending ? (
                <Button size="sm" variant="secondary" loading={updating} onClick={() => activeTask && onBeginReview(activeTask.id)}>
                  {translateText("Begin review")}
                </Button>
              ) : null}

              {activeTask?.task_status === CODE_TASK_STATUSES.inReview ? (
                <>
                  <Button size="sm" variant="secondary" loading={updating} onClick={() => activeTask && onAcceptReview(activeTask.id)}>
                    Accept
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    loading={updating}
                    onClick={() =>
                      activeTask &&
                      onRejectReview(
                        activeTask.id,
                        "Follow-up changes requested before task completion.",
                        "changes_requested",
                        ["Revisit reviewer feedback", "Update implementation notes"],
                      )
                    }
                  >
                    Reject with checklist
                  </Button>
                </>
              ) : null}
            </div>
          </div>
        </div>
      </CardBody>
    </CockpitPanel>
  );
}
