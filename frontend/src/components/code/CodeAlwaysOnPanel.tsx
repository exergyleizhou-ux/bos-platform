import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Activity, BrainCircuit, Clock3, PlayCircle, ThumbsDown, ThumbsUp } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CardBody, CardHeader } from "@/components/ui/Card";
import { CockpitPanel } from "@/components/ui/Cockpit";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { SurfaceTile } from "@/components/ui/SurfaceTile";
import { Textarea } from "@/components/ui/Textarea";
import { translateText } from "@/lib/i18n";
import type {
  CodeAutomationJob,
  CodeReflectionRun,
  CodeRunLedgerArtifactSummary,
  CodeRuntimeMetrics,
  CodeRuntimeResponse,
  CodeSkill,
} from "@/types/code";

interface CodeAlwaysOnPanelProps {
  runtime?: CodeRuntimeResponse;
  reflections?: CodeReflectionRun[];
  skills?: CodeSkill[];
  activeSessionId?: number | null;
  runningAutomationJobId?: number | null;
  reflectionRunning?: boolean;
  skillSaving?: boolean;
  onRunAutomation?: (jobId: number) => void;
  onToggleAutomation?: (jobId: number, enabled: boolean) => void;
  onUpdateAutomation?: (
    jobId: number,
    payload: {
      schedule_kind?: string;
      interval_sec?: number;
      prompt_template?: string;
      target_scope?: string;
      enabled?: boolean;
    },
  ) => void;
  onCreateAutomation?: (payload: {
    name: string;
    job_type: string;
    schedule_kind: string;
    interval_sec?: number;
    prompt_template?: string;
    target_scope?: string;
  }) => void;
  onRunReflection?: (sessionId: number) => void;
  onUpdateSkill?: (
    skillId: number,
    payload: {
      content_markdown?: string;
      supporting_files?: Record<string, string>;
      change_summary?: string;
      skill_status?: string;
    },
  ) => void;
  onFeedbackSkill?: (
    skillId: number,
    sentiment: "positive" | "negative",
    note?: string,
  ) => void;
}

export function CodeAlwaysOnPanel({
  runtime,
  reflections,
  skills,
  activeSessionId,
  runningAutomationJobId,
  reflectionRunning,
  skillSaving,
  onRunAutomation,
  onToggleAutomation,
  onUpdateAutomation,
  onCreateAutomation,
  onRunReflection,
  onUpdateSkill,
  onFeedbackSkill,
}: CodeAlwaysOnPanelProps) {
  const jobs = useMemo(() => runtime?.automation_jobs ?? [], [runtime?.automation_jobs]);
  const recentReflections = (reflections ?? []).slice(0, 3);
  const recentSkills = (skills ?? []).slice(0, 3);
  const runtimeMetrics = runtime?.runtime_state.runtime_metrics as CodeRuntimeMetrics | undefined;
  const latestRunArtifact = runtimeMetrics?.last_run_ledger_artifact as CodeRunLedgerArtifactSummary | undefined;
  const [jobName, setJobName] = useState("");
  const [jobType, setJobType] = useState("cron");
  const [scheduleKind, setScheduleKind] = useState("interval");
  const [intervalSec, setIntervalSec] = useState("900");
  const [promptTemplate, setPromptTemplate] = useState("");
  const [selectedAutomationId, setSelectedAutomationId] = useState<number | null>(null);
  const [automationPrompt, setAutomationPrompt] = useState("");
  const [automationScheduleKind, setAutomationScheduleKind] = useState("manual");
  const [automationIntervalSec, setAutomationIntervalSec] = useState("900");
  const [selectedSkillId, setSelectedSkillId] = useState<number | null>(null);
  const [skillContent, setSkillContent] = useState("");
  const [supportingFilesJson, setSupportingFilesJson] = useState("{}");
  const [feedbackNotesBySkill, setFeedbackNotesBySkill] = useState<Record<number, string>>({});

  useEffect(() => {
    if (!jobs.length) {
      setSelectedAutomationId(null);
      setAutomationPrompt("");
      setAutomationScheduleKind("manual");
      setAutomationIntervalSec("900");
      return;
    }
    if (selectedAutomationId === null || !jobs.some((job) => job.id === selectedAutomationId)) {
      const firstJob = jobs[0];
      setSelectedAutomationId(firstJob.id);
      setAutomationPrompt(firstJob.prompt_template ?? "");
      setAutomationScheduleKind(firstJob.schedule_kind);
      setAutomationIntervalSec(String(firstJob.interval_sec ?? 900));
    }
  }, [jobs, selectedAutomationId]);

  useEffect(() => {
    if (!recentSkills.length) {
      setSelectedSkillId(null);
      setSkillContent("");
      setSupportingFilesJson("{}");
      return;
    }
    if (selectedSkillId === null || !recentSkills.some((skill) => skill.id === selectedSkillId)) {
      const firstSkill = recentSkills[0];
      setSelectedSkillId(firstSkill.id);
      setSkillContent(firstSkill.latest_revision?.content_markdown ?? "");
      setSupportingFilesJson(JSON.stringify(firstSkill.latest_revision?.supporting_files ?? {}, null, 2));
    }
  }, [recentSkills, selectedSkillId]);

  const selectedSkill = recentSkills.find((skill) => skill.id === selectedSkillId) ?? null;
  const selectedAutomation = jobs.find((job) => job.id === selectedAutomationId) ?? null;

  return (
    <CockpitPanel className="p-5 lg:p-6">
      <CardHeader
        title={translateText("Always-On Runtime")}
        description={translateText("Heartbeat, scheduled jobs, background reflections, and reusable skills now live alongside the BOS Code thread.")}
      />
      <CardBody className="space-y-4">
        <div className="grid gap-3 md:grid-cols-3">
          <RuntimeStat
            icon={<Activity className="h-4 w-4 text-sky-300" />}
            label={translateText("Heartbeat")}
            value={translateText(runtime?.runtime_state.last_heartbeat_decision ?? "idle")}
            hint={
              runtimeMetrics?.last_heartbeat_summary ??
              runtime?.runtime_state.last_heartbeat_at ??
              translateText("No heartbeat yet")
            }
          />
          <RuntimeStat
            icon={<Clock3 className="h-4 w-4 text-amber-300" />}
            label={translateText("Automations")}
            value={`${jobs.length}`}
            hint={`${jobs.filter((job) => job.enabled).length} ${translateText("enabled")}`}
          />
          <RuntimeStat
            icon={<BrainCircuit className="h-4 w-4 text-fuchsia-300" />}
            label={translateText("Reflections")}
            value={`${runtime?.pending_reflections ?? 0}`}
            hint={runtime?.runtime_state.last_reflection_at ?? translateText("No reflection yet")}
          />
        </div>

        {runtimeMetrics?.last_heartbeat_focus_task_title ? (
          <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
            <p className="text-sm font-semibold text-white">{translateText("Heartbeat focus")}</p>
            <p className="mt-2 text-sm text-surface-200">
              {String(runtimeMetrics.last_heartbeat_focus_task_title)}
            </p>
            {runtimeMetrics?.last_heartbeat_planner_recommendation ? (
              <div className="mt-2 flex flex-wrap gap-2">
                <Badge variant="brand">
                  {translateText("planner")} {String(runtimeMetrics.last_heartbeat_planner_recommendation)}
                </Badge>
                {runtimeMetrics?.last_heartbeat_loop_budget ? (
                  <Badge variant="info">
                    {translateText("loop")} {String(runtimeMetrics.last_heartbeat_loop_budget)}
                  </Badge>
                ) : null}
                {runtimeMetrics?.last_heartbeat_convergence_signal ? (
                  <Badge variant="neutral">
                    {translateText("convergence")} {String(runtimeMetrics.last_heartbeat_convergence_signal)}
                  </Badge>
                ) : null}
                {runtimeMetrics?.last_heartbeat_risk_level ? (
                  <Badge variant="warning">
                    {translateText("risk")} {String(runtimeMetrics.last_heartbeat_risk_level)}
                  </Badge>
                ) : null}
              </div>
            ) : null}
            {Array.isArray(runtimeMetrics?.last_heartbeat_critic_notes) &&
            runtimeMetrics.last_heartbeat_critic_notes.length ? (
              <div className="mt-2 space-y-1">
                {runtimeMetrics.last_heartbeat_critic_notes.map((note) => (
                  <p key={note} className="text-sm text-surface-400">
                    - {note}
                  </p>
                ))}
              </div>
            ) : null}
            {Array.isArray(runtimeMetrics?.last_heartbeat_planner_steps) &&
            runtimeMetrics.last_heartbeat_planner_steps.length ? (
              <div className="mt-3">
                <p className="text-sm font-medium text-white">{translateText("Planner steps")}</p>
                <div className="mt-1 space-y-1">
                  {runtimeMetrics.last_heartbeat_planner_steps.map((step) => (
                    <p key={step} className="text-sm text-surface-400">
                      - {step}
                    </p>
                  ))}
                </div>
              </div>
            ) : null}
            {Array.isArray(runtimeMetrics?.last_heartbeat_critic_checks) &&
            runtimeMetrics.last_heartbeat_critic_checks.length ? (
              <div className="mt-3">
                <p className="text-sm font-medium text-white">{translateText("Critic checks")}</p>
                <div className="mt-1 space-y-1">
                  {runtimeMetrics.last_heartbeat_critic_checks.map((step) => (
                    <p key={step} className="text-sm text-surface-400">
                      - {step}
                    </p>
                  ))}
                </div>
              </div>
            ) : null}
            {runtimeMetrics?.last_heartbeat_policy_learning_snapshot ? (
              <div className="mt-3">
                <p className="text-sm font-medium text-white">{translateText("Policy context")}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {Object.entries(
                    runtimeMetrics.last_heartbeat_policy_learning_snapshot,
                  ).flatMap(([category, values]) =>
                    Object.entries(values).map(([label, count]) => (
                      <Badge key={`${category}-${label}`} variant="neutral">
                        {category}.{label}: {count}
                      </Badge>
                    )),
                  )}
                </div>
              </div>
            ) : null}
            {Array.isArray(runtimeMetrics?.last_heartbeat_difficulty_signals) &&
            runtimeMetrics.last_heartbeat_difficulty_signals.length ? (
              <div className="mt-3">
                <p className="text-sm font-medium text-white">{translateText("Difficulty signals")}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {runtimeMetrics.last_heartbeat_difficulty_signals.map((signal) => (
                    <Badge key={signal} variant="neutral">
                      {String(signal)}
                    </Badge>
                  ))}
                </div>
              </div>
            ) : null}
            {runtimeMetrics?.last_heartbeat_next_automation_action ? (
              <div className="mt-2 flex flex-wrap gap-2">
                <Badge variant="info">
                  {String(runtimeMetrics.last_heartbeat_next_automation_action)}
                </Badge>
                {runtimeMetrics?.last_heartbeat_executed_action ? (
                  <Badge variant="brand">
                    {translateText("executed")} {String(runtimeMetrics.last_heartbeat_executed_action)}
                  </Badge>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}

        {latestRunArtifact?.slice ? (
          <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold text-white">{translateText("Latest run artifact")}</p>
              {latestRunArtifact.recorded_at ? (
                <Badge variant="neutral">{String(latestRunArtifact.recorded_at)}</Badge>
              ) : null}
            </div>
            <p className="mt-2 text-sm font-medium text-white">{String(latestRunArtifact.slice)}</p>
            {latestRunArtifact.outcome ? (
              <p className="mt-1 text-sm text-surface-300">{String(latestRunArtifact.outcome)}</p>
            ) : null}
            <div className="mt-3 flex flex-wrap gap-2">
              {latestRunArtifact.target_surface ? (
                <Badge variant="info">
                  {translateText("surface")} {String(latestRunArtifact.target_surface)}
                </Badge>
              ) : null}
              {latestRunArtifact.target_id ? (
                <Badge variant="neutral">
                  {translateText("target")} {String(latestRunArtifact.target_id)}
                </Badge>
              ) : null}
            </div>
            {latestRunArtifact.target_route ? (
              <div className="mt-3">
                <a className="text-sm font-medium text-sky-300 hover:text-sky-200" href={String(latestRunArtifact.target_route)}>
                  {translateText("Open artifact target")}
                </a>
              </div>
            ) : null}
          </div>
        ) : null}

        {runtimeMetrics?.last_maintenance_summary ? (
          <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold text-white">{translateText("Maintenance")}</p>
              {runtimeMetrics.last_maintenance_generated_at ? (
                <Badge variant="neutral">{String(runtimeMetrics.last_maintenance_generated_at)}</Badge>
              ) : null}
            </div>
            <p className="mt-2 text-sm text-surface-300">{String(runtimeMetrics.last_maintenance_summary)}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {runtimeMetrics.last_maintenance_project_brain_path ? (
                <Badge variant="info">{translateText("brain")} {String(runtimeMetrics.last_maintenance_project_brain_path)}</Badge>
              ) : null}
              {runtimeMetrics.last_maintenance_decision_journal_path ? (
                <Badge variant="neutral">{translateText("journal")} {String(runtimeMetrics.last_maintenance_decision_journal_path)}</Badge>
              ) : null}
              {runtimeMetrics.last_maintenance_evolution_log_path ? (
                <Badge variant="neutral">{translateText("evolution")} {String(runtimeMetrics.last_maintenance_evolution_log_path)}</Badge>
              ) : null}
            </div>
            {runtimeMetrics.last_maintenance_report_markdown_path ? (
              <div className="mt-3">
                <span className="text-sm font-medium text-sky-300">
                  {translateText("Report")} {String(runtimeMetrics.last_maintenance_report_markdown_path)}
                </span>
              </div>
            ) : null}
            {runtimeMetrics.next_autonomy_objective ? (
              <SurfaceTile className="mt-3 px-3 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="brand">{translateText("next autonomy")}</Badge>
                  {runtimeMetrics.next_autonomy_mode ? (
                    <Badge variant="neutral">{String(runtimeMetrics.next_autonomy_mode)}</Badge>
                  ) : null}
                </div>
                <p className="mt-2 text-sm text-surface-200">
                  {String(runtimeMetrics.next_autonomy_objective)}
                </p>
                {(runtimeMetrics.last_seeded_autonomy_task_id || runtimeMetrics.last_seeded_autonomy_at) ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {runtimeMetrics.last_seeded_autonomy_task_id ? (
                      <Badge variant="info">
                        {translateText("seeded task")} #{String(runtimeMetrics.last_seeded_autonomy_task_id)}
                      </Badge>
                    ) : null}
                    {runtimeMetrics.last_seeded_autonomy_at ? (
                      <Badge variant="neutral">
                        {translateText("seeded at")} {String(runtimeMetrics.last_seeded_autonomy_at)}
                      </Badge>
                    ) : null}
                  </div>
                ) : null}
              </SurfaceTile>
            ) : null}
            {typeof runtimeMetrics.last_reflection_verified_signal === "boolean" ? (
              <SurfaceTile className="mt-3 px-3 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={runtimeMetrics.last_reflection_verified_signal ? "info" : "warning"}>
                    {runtimeMetrics.last_reflection_verified_signal
                      ? translateText("verified reflection")
                      : translateText("memory only")}
                  </Badge>
                </div>
                {Array.isArray(runtimeMetrics.last_reflection_verification_signals) &&
                runtimeMetrics.last_reflection_verification_signals.length ? (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {runtimeMetrics.last_reflection_verification_signals.map((signal) => (
                      <Badge key={signal} variant="neutral">
                        {String(signal)}
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </SurfaceTile>
            ) : null}
          </div>
        ) : null}

        {runtimeMetrics?.last_recovery_task_id ? (
          <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold text-white">{translateText("Recovery loop")}</p>
              {runtimeMetrics.last_recovery_task_at ? (
                <Badge variant="neutral">{String(runtimeMetrics.last_recovery_task_at)}</Badge>
              ) : null}
            </div>
            <p className="mt-2 text-sm text-surface-300">
              {translateText("Autonomy most recently opened recovery task")} #{String(runtimeMetrics.last_recovery_task_id)}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {runtimeMetrics.last_recovery_failure_class ? (
                <Badge variant="warning">{String(runtimeMetrics.last_recovery_failure_class)}</Badge>
              ) : null}
              <Badge variant="info">
                {translateText("task")} #{String(runtimeMetrics.last_recovery_task_id)}
              </Badge>
            </div>
          </div>
        ) : null}

        {runtimeMetrics?.provider_pause_until ? (
          <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold text-white">{translateText("Provider backpressure")}</p>
              <Badge variant="warning">{String(runtimeMetrics.provider_pause_until)}</Badge>
            </div>
            <p className="mt-2 text-sm text-surface-300">
              {translateText("Autonomy is throttling provider-driven turns because the model endpoint recently pushed back.")}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {runtimeMetrics.last_provider_failure_class ? (
                <Badge variant="warning">{String(runtimeMetrics.last_provider_failure_class)}</Badge>
              ) : null}
              {runtimeMetrics.provider_backpressure_count ? (
                <Badge variant="neutral">
                  {translateText("count")} {String(runtimeMetrics.provider_backpressure_count)}
                </Badge>
              ) : null}
            </div>
          </div>
        ) : null}

        {runtimeMetrics?.workflow_mode ? (
          <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold text-white">{translateText("Workflow orchestrator")}</p>
              <Badge variant="brand">{String(runtimeMetrics.workflow_mode)}</Badge>
            </div>
            {Array.isArray(runtimeMetrics.workflow_skills) && runtimeMetrics.workflow_skills.length ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {runtimeMetrics.workflow_skills.map((skill) => (
                  <Badge key={skill} variant="info">{skill}</Badge>
                ))}
              </div>
            ) : null}
            {Array.isArray(runtimeMetrics.workflow_rationale) && runtimeMetrics.workflow_rationale.length ? (
              <div className="mt-3 space-y-1">
                {runtimeMetrics.workflow_rationale.map((item) => (
                  <p key={item} className="text-sm text-surface-300">- {item}</p>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

        {runtimeMetrics?.experience_quality?.posture ? (
          <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold text-white">{translateText("Experience quality")}</p>
              <div className="flex flex-wrap gap-2">
                <Badge variant="brand">{String(runtimeMetrics.experience_quality.posture)}</Badge>
                {typeof runtimeMetrics.experience_quality.score === "number" ? (
                  <Badge variant="neutral">{translateText("score")} {String(runtimeMetrics.experience_quality.score)}</Badge>
                ) : null}
              </div>
            </div>
            {Array.isArray(runtimeMetrics.experience_quality.notes) && runtimeMetrics.experience_quality.notes.length ? (
              <div className="mt-3 space-y-1">
                {runtimeMetrics.experience_quality.notes.map((item) => (
                  <p key={item} className="text-sm text-surface-300">- {item}</p>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

        {runtimeMetrics?.policy_learning ? (
          <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
            <p className="text-sm font-semibold text-white">{translateText("Policy learning")}</p>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              {Object.entries(runtimeMetrics.policy_learning).map(
                ([category, values]) => (
                  <SurfaceTile key={category} className="px-3 py-3">
                    <p className="text-sm font-medium text-white">{category}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {Object.entries(values).map(([label, count]) => (
                        <Badge key={`${category}-${label}`} variant="neutral">
                          {label}: {count}
                        </Badge>
                      ))}
                    </div>
                  </SurfaceTile>
                ),
              )}
            </div>
          </div>
        ) : null}

        <section className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-white">{translateText("Automation Jobs")}</p>
            <Badge variant="neutral">{jobs.length} {translateText("tracked")}</Badge>
          </div>
          {onCreateAutomation ? (
            <div className="assistant-thread-shell rounded-2xl border border-white/8 grid gap-3 px-4 py-4 md:grid-cols-2">
              <Input
                label={translateText("Automation name")}
                value={jobName}
                onChange={(event) => setJobName(event.target.value)}
                placeholder={translateText("nightly-runtime-review")}
              />
              <Select
                label={translateText("Job type")}
                value={jobType}
                onChange={(event) => setJobType(event.target.value)}
                options={[
                  { value: "cron", label: translateText("Cron") },
                  { value: "heartbeat", label: translateText("Heartbeat") },
                  { value: "reflection", label: translateText("Reflection") },
                ]}
              />
              <Select
                label={translateText("Schedule")}
                value={scheduleKind}
                onChange={(event) => setScheduleKind(event.target.value)}
                options={[
                  { value: "interval", label: translateText("Interval") },
                  { value: "manual", label: translateText("Manual") },
                  { value: "heartbeat", label: translateText("Heartbeat cadence") },
                ]}
              />
              <Input
                label={translateText("Interval seconds")}
                type="number"
                value={intervalSec}
                onChange={(event) => setIntervalSec(event.target.value)}
                disabled={scheduleKind !== "interval"}
              />
              <div className="md:col-span-2">
                <Textarea
                  label={translateText("Prompt template")}
                  value={promptTemplate}
                  onChange={(event) => setPromptTemplate(event.target.value)}
                  placeholder={translateText("Optional automation prompt")}
                  rows={3}
                />
              </div>
              <div className="md:col-span-2 flex justify-end">
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={!jobName.trim()}
                  onClick={() => {
                    onCreateAutomation({
                      name: jobName.trim(),
                      job_type: jobType,
                      schedule_kind: scheduleKind,
                      interval_sec: scheduleKind === "interval" ? Number(intervalSec || "0") || 900 : undefined,
                      prompt_template: promptTemplate.trim() || undefined,
                      target_scope: jobType === "reflection" ? "automation" : jobType,
                    });
                    setJobName("");
                    setPromptTemplate("");
                  }}
                >
                  {translateText("Create automation")}
                </Button>
              </div>
            </div>
          ) : null}
          <div className="space-y-3">
            {jobs.length ? jobs.map((job) => (
              <AutomationRow
                key={job.id}
                job={job}
                running={runningAutomationJobId === job.id}
                onRun={onRunAutomation}
                onToggle={onToggleAutomation}
              />
            )) : (
              <p className="text-sm text-surface-400">{translateText("No automations have been created yet.")}</p>
            )}
          </div>
          {selectedAutomation && onUpdateAutomation ? (
            <div className="assistant-thread-shell rounded-2xl border border-white/8 grid gap-3 px-4 py-4 md:grid-cols-2">
              <Select
                label={translateText("Selected automation")}
                value={String(selectedAutomationId ?? "")}
                onChange={(event) => {
                  const nextId = Number(event.target.value);
                  setSelectedAutomationId(nextId);
                  const nextJob = jobs.find((job) => job.id === nextId);
                  setAutomationPrompt(nextJob?.prompt_template ?? "");
                  setAutomationScheduleKind(nextJob?.schedule_kind ?? "manual");
                  setAutomationIntervalSec(String(nextJob?.interval_sec ?? 900));
                }}
                options={jobs.map((job) => ({ value: String(job.id), label: job.name }))}
              />
              <Select
                label={translateText("Schedule kind")}
                value={automationScheduleKind}
                onChange={(event) => setAutomationScheduleKind(event.target.value)}
                options={[
                  { value: "manual", label: translateText("Manual") },
                  { value: "interval", label: translateText("Interval") },
                  { value: "heartbeat", label: translateText("Heartbeat cadence") },
                ]}
              />
              <Input
                label={translateText("Interval seconds")}
                type="number"
                value={automationIntervalSec}
                onChange={(event) => setAutomationIntervalSec(event.target.value)}
                disabled={automationScheduleKind !== "interval"}
              />
              <div className="md:col-span-2">
                <Textarea
                  label={translateText("Automation prompt")}
                  value={automationPrompt}
                  onChange={(event) => setAutomationPrompt(event.target.value)}
                  rows={3}
                />
              </div>
              <div className="md:col-span-2 flex justify-end">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() =>
                    onUpdateAutomation(selectedAutomation.id, {
                      schedule_kind: automationScheduleKind,
                      interval_sec:
                        automationScheduleKind === "interval"
                          ? Number(automationIntervalSec || "0") || 900
                          : undefined,
                      prompt_template: automationPrompt.trim() || undefined,
                      target_scope: selectedAutomation.target_scope ?? undefined,
                    })
                  }
                >
                  {translateText("Save automation")}
                </Button>
              </div>
            </div>
          ) : null}
        </section>

        <section className="grid gap-4 xl:grid-cols-2">
          <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-white">{translateText("Recent Reflections")}</p>
              <div className="flex items-center gap-2">
                <Badge variant="brand">{reflections?.length ?? 0}</Badge>
                {onRunReflection && activeSessionId ? (
                  <Button size="sm" variant="ghost" loading={reflectionRunning} onClick={() => onRunReflection(activeSessionId)}>
                    {translateText("Run now")}
                  </Button>
                ) : null}
              </div>
            </div>
            <div className="mt-3 space-y-3">
              {recentReflections.length ? recentReflections.map((reflection) => {
                const reflectionPayload = reflection.payload as {
                  verified_signal?: boolean;
                  verification_signals?: unknown[];
                };
                return (
                  <SurfaceTile key={reflection.id} className="px-3 py-3">
                    <div className="flex items-center gap-2">
                      <Badge variant="info">{reflection.output_kind}</Badge>
                      <Badge variant="neutral">{translateText(reflection.reflection_status)}</Badge>
                      {typeof reflectionPayload.verified_signal === "boolean" ? (
                        <Badge variant={reflectionPayload.verified_signal ? "brand" : "warning"}>
                          {reflectionPayload.verified_signal
                            ? translateText("verified skill")
                            : translateText("memory only")}
                        </Badge>
                      ) : null}
                    </div>
                    <p className="mt-2 text-sm text-surface-200">{reflection.summary ?? translateText("Reflection captured BOS Code context.")}</p>
                    {Array.isArray(reflectionPayload.verification_signals) &&
                    reflectionPayload.verification_signals.length ? (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {reflectionPayload.verification_signals.map((signal) => (
                          <Badge key={`${reflection.id}-${String(signal)}`} variant="neutral">
                            {String(signal)}
                          </Badge>
                        ))}
                      </div>
                    ) : null}
                  </SurfaceTile>
                );
              }) : (
                <p className="text-sm text-surface-400">{translateText("No reflections yet.")}</p>
              )}
            </div>
          </div>

          <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-white">{translateText("Skill Drafts")}</p>
              <Badge variant="neutral">{skills?.length ?? 0}</Badge>
            </div>
            <div className="mt-3 space-y-3">
              {recentSkills.length ? recentSkills.map((skill) => (
                <SurfaceTile key={skill.id} className="px-3 py-3">
                  <div className="flex items-center gap-2">
                    <Badge variant="brand">{translateText(skill.skill_status)}</Badge>
                    <Badge variant="neutral">{skill.slug}</Badge>
                  </div>
                  <p className="mt-2 text-sm text-surface-200">{skill.name}</p>
                  {skill.description ? <p className="mt-1 text-sm text-surface-400">{skill.description}</p> : null}
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Badge variant="neutral">{translateText("uses")} {skill.usage_count}</Badge>
                    <Badge variant="neutral">+{skill.positive_feedback_count}</Badge>
                    <Badge variant="neutral">-{skill.negative_feedback_count}</Badge>
                    {skill.last_used_at ? <Badge variant="neutral">{translateText("last used")} {skill.last_used_at}</Badge> : null}
                  </div>
                  {onFeedbackSkill ? (
                    <div className="mt-3 space-y-2">
                      <Textarea
                        value={feedbackNotesBySkill[skill.id] ?? ""}
                        onChange={(event) =>
                          setFeedbackNotesBySkill((current) => ({
                            ...current,
                            [skill.id]: event.target.value,
                          }))
                        }
                        placeholder={translateText("Optional feedback note")}
                        rows={2}
                      />
                      <div className="flex gap-2">
                        <Button
                          size="xs"
                          variant="ghost"
                          leftIcon={<ThumbsUp className="h-3.5 w-3.5" />}
                          onClick={() => {
                            onFeedbackSkill(skill.id, "positive", feedbackNotesBySkill[skill.id]);
                            setFeedbackNotesBySkill((current) => ({ ...current, [skill.id]: "" }));
                          }}
                        >
                          {translateText("Useful")}
                        </Button>
                        <Button
                          size="xs"
                          variant="ghost"
                          leftIcon={<ThumbsDown className="h-3.5 w-3.5" />}
                          onClick={() => {
                            onFeedbackSkill(skill.id, "negative", feedbackNotesBySkill[skill.id]);
                            setFeedbackNotesBySkill((current) => ({ ...current, [skill.id]: "" }));
                          }}
                        >
                          {translateText("Not useful")}
                        </Button>
                      </div>
                      </div>
                    ) : null}
                </SurfaceTile>
              )) : (
                <p className="text-sm text-surface-400">{translateText("No skill drafts yet.")}</p>
              )}
            </div>
            {selectedSkill && onUpdateSkill ? (
              <div className="mt-4 rounded-2xl border border-white/8 bg-surface-950/70 px-4 py-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-white">{translateText("Edit draft")}</p>
                  <Badge variant="brand">{selectedSkill.slug}</Badge>
                </div>
                <div className="mt-3">
                  <Select
                    label={translateText("Selected skill")}
                    value={String(selectedSkillId ?? "")}
                    onChange={(event) => {
                      const nextId = Number(event.target.value);
                      setSelectedSkillId(nextId);
                      const nextSkill = recentSkills.find((skill) => skill.id === nextId);
                      setSkillContent(nextSkill?.latest_revision?.content_markdown ?? "");
                      setSupportingFilesJson(JSON.stringify(nextSkill?.latest_revision?.supporting_files ?? {}, null, 2));
                    }}
                    options={recentSkills.map((skill) => ({ value: String(skill.id), label: skill.name }))}
                  />
                </div>
                <div className="mt-3">
                  <Textarea
                    label={translateText("Draft content")}
                    value={skillContent}
                    onChange={(event) => setSkillContent(event.target.value)}
                    rows={8}
                    autoResize
                  />
                </div>
                <div className="mt-3">
                  <Textarea
                    label={translateText("Supporting files JSON")}
                    value={supportingFilesJson}
                    onChange={(event) => setSupportingFilesJson(event.target.value)}
                    helperText={translateText('Use JSON like {"references/checklist.md":"...","templates/prompt.md":"..."}')}
                    rows={6}
                    autoResize
                  />
                </div>
                <div className="mt-3 flex justify-end gap-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    loading={skillSaving}
                    onClick={() =>
                      onUpdateSkill(selectedSkill.id, {
                        skill_status: "active",
                        change_summary: translateText("Promoted from cockpit."),
                      })
                    }
                  >
                    {translateText("Promote active")}
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    loading={skillSaving}
                    onClick={() => {
                      let parsedSupportingFiles = {};
                      try {
                        parsedSupportingFiles = JSON.parse(supportingFilesJson || "{}");
                      } catch {
                        parsedSupportingFiles = {};
                      }
                      onUpdateSkill(selectedSkill.id, {
                        content_markdown: skillContent,
                        supporting_files: parsedSupportingFiles,
                        change_summary: translateText("Edited from cockpit."),
                        skill_status: "draft",
                      });
                    }}
                  >
                    {translateText("Save draft")}
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        </section>

        <section className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-white">{translateText("Subagent Runs")}</p>
            <Badge variant="neutral">{runtime?.active_subagents?.length ?? 0}</Badge>
          </div>
          <div className="mt-3 space-y-3">
            {(runtime?.active_subagents?.length ?? 0) > 0 ? (
              runtime?.active_subagents.map((run) => (
                <SurfaceTile key={run.id} className="px-3 py-3">
                  <div className="flex items-center gap-2">
                    <Badge variant="info">{translateText(run.run_status)}</Badge>
                    {run.task_id ? <Badge variant="neutral">{translateText("task")} #{run.task_id}</Badge> : null}
                    {typeof run.metadata_json?.dispatch_mode === "string" ? (
                      <Badge variant="neutral">{String(run.metadata_json.dispatch_mode)}</Badge>
                    ) : null}
                  </div>
                  <p className="mt-2 text-sm text-surface-200">{run.objective}</p>
                  {run.result_summary ? (
                    <p className="mt-2 text-sm text-surface-400">{run.result_summary}</p>
                  ) : null}
                </SurfaceTile>
              ))
            ) : (
              <p className="text-sm text-surface-400">{translateText("Active executor-side subagent runs will appear here.")}</p>
            )}
          </div>
        </section>
      </CardBody>
    </CockpitPanel>
  );
}

function RuntimeStat({
  icon,
  label,
  value,
  hint,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
      <div className="flex items-center gap-2 text-[0.68rem] uppercase tracking-[0.22em] text-surface-500">
        {icon}
        <span>{translateText(label)}</span>
      </div>
      <p className="mt-3 text-lg font-semibold text-white">{value}</p>
      <p className="mt-1 text-sm text-surface-400">{hint}</p>
    </div>
  );
}

function AutomationRow({
  job,
  running,
  onRun,
  onToggle,
}: {
  job: CodeAutomationJob;
  running: boolean;
  onRun?: (jobId: number) => void;
  onToggle?: (jobId: number, enabled: boolean) => void;
}) {
  return (
    <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap gap-2">
            <Badge variant={job.enabled ? "info" : "neutral"}>{translateText(job.job_type)}</Badge>
            <Badge variant="neutral">{translateText(job.schedule_kind)}</Badge>
            {job.last_status ? <Badge variant="neutral">{translateText(job.last_status)}</Badge> : null}
          </div>
          <p className="mt-3 text-sm font-semibold text-white">{job.name}</p>
          <p className="mt-1 text-sm text-surface-400">
            {job.prompt_template ?? translateText("No prompt template set.")}
          </p>
        </div>
        {onRun ? (
          <div className="flex gap-2">
            {onToggle ? (
              <Button size="sm" variant="ghost" onClick={() => onToggle(job.id, !job.enabled)}>
                {translateText(job.enabled ? "Disable" : "Enable")}
              </Button>
            ) : null}
            <Button
              size="sm"
              variant="secondary"
              loading={running}
              leftIcon={<PlayCircle className="h-4 w-4" />}
              onClick={() => onRun(job.id)}
            >
              {translateText("Run")}
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
