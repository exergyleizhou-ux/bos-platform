import type { BosGraphName } from "@/lib/bosGraph/contracts";

export type AssistantBosIntent =
  | "overview"
  | "executive_summary"
  | "riskiest_batch"
  | "batch_analysis"
  | "batch_compare"
  | "batches_table"
  | "signals_table"
  | "audit_table"
  | "twins_table"
  | "ser_trend_chart"
  | "grade_chart"
  | "species_chart"
  | "brain_summary"
  | "release_summary"
  | "release_risks"
  | "native_runtime"
  | "simulation_lab"
  | "research_review"
  | "batch_guidance"
  | "export_audit_packet"
  | "evaluate_supervisor"
  | "handover_recommendation"
  | "species_catalog"
  | "feedstocks_catalog"
  | "manuscript_catalog"
  | "compile_signal"
  | "refresh_signal"
  | "evaluate_release"
  | "open_signal_lab"
  | "open_brain"
  | "open_release"
  | "open_dashboard"
  | "open_twins"
  | "help";

export interface AssistantStructuredMetric {
  label: string;
  value: string;
  hint?: string;
}

export interface AssistantStructuredTable {
  title?: string;
  columns: string[];
  rows: string[][];
}

export type AssistantStructuredChart =
  | {
      kind: "ser-trend";
      title?: string;
      data: Array<{ date: string; ser_value: number; batch_count: number }>;
    }
  | {
      kind: "grade-distribution";
      title?: string;
      data: Array<{ grade: string; count: number; percentage: number }>;
    }
  | {
      kind: "species-distribution";
      title?: string;
      data: Array<{ species: string; count: number; percentage: number }>;
    }
  | {
      kind: "twin-trajectory";
      title?: string;
      data: Array<{
        time: number;
        biomass: number;
        substrate: number;
        growth_rate: number;
        temperature: number;
        moisture: number;
      }>;
    };

export interface AssistantStructuredAction {
  label: string;
  to: string;
}

export interface AssistantStructuredResult {
  title: string;
  summary?: string;
  metrics?: AssistantStructuredMetric[];
  table?: AssistantStructuredTable;
  chart?: AssistantStructuredChart;
  sections?: Array<{
    title: string;
    items: string[];
  }>;
  notes?: string[];
  actions?: AssistantStructuredAction[];
}

function hasAny(text: string, patterns: string[]) {
  return patterns.some((pattern) => text.includes(pattern));
}

function looksLikeResearchDecisionQuestion(text: string) {
  const hasDecisionLanguage = hasAny(text, [
    "哪个",
    "哪种",
    "更适合",
    "适不适合",
    "是否适合",
    "比较",
    "对比",
    "选择",
    "优先",
    "建议",
    "方案",
    "处理",
    "compare",
    "versus",
    "vs",
    "better",
    "best",
    "choose",
    "suitable",
    "which",
  ]);
  const hasResearchDomain = hasAny(text, [
    "黄粉虫",
    "蛴螬",
    "黑水虻",
    "幼虫",
    "虫",
    "酒糟",
    "餐厨",
    "厨余",
    "基质",
    "饲料",
    "发酵",
    "污染",
    "氨气",
    "臭味",
    "有机废弃物",
    "bsf",
    "larvae",
    "mealworm",
    "feedstock",
    "substrate",
    "food waste",
    "organic waste",
    "contamination",
    "ammonia",
    "odor",
  ]);
  return hasDecisionLanguage && hasResearchDomain;
}

export const BOS_ASSISTANT_INTENT_GRAPH_MAP: Partial<Record<AssistantBosIntent, BosGraphName>> = {
  riskiest_batch: "batch_triage_graph",
  batch_analysis: "batch_triage_graph",
  batch_guidance: "batch_triage_graph",
  batch_compare: "batch_triage_graph",
  executive_summary: "release_review_graph",
  release_summary: "release_review_graph",
  release_risks: "release_review_graph",
  evaluate_release: "release_review_graph",
  export_audit_packet: "release_review_graph",
  compile_signal: "signal_runtime_graph",
  refresh_signal: "signal_runtime_graph",
  evaluate_supervisor: "signal_runtime_graph",
  handover_recommendation: "signal_runtime_graph",
};

export function getBosAssistantGraphName(intent: AssistantBosIntent): BosGraphName | null {
  return BOS_ASSISTANT_INTENT_GRAPH_MAP[intent] ?? null;
}

export function isBosAssistantGraphBackedIntent(intent: AssistantBosIntent) {
  return getBosAssistantGraphName(intent) !== null;
}

export function detectBosAssistantIntent(message: string): AssistantBosIntent | null {
  const text = message.trim().toLowerCase();
  if (!text) return null;

  if (
    hasAny(text, [
      "research review",
      "protocol review",
      "research protocol",
      "scientific review",
      "chief scientist",
      "expert team",
      "specialist cards",
      "mechanistic analyst",
      "evidence auditor",
      "课题评审",
      "课题方案",
      "方案评审",
      "研究评审",
      "研究方案",
      "科研评审",
      "专家团队",
      "机制分析师",
    ]) ||
    looksLikeResearchDecisionQuestion(text)
  ) {
    return "research_review";
  }

  if (
    hasAny(text, [
      "simulation lab",
      "simulation scenario",
      "simulate",
      "run scenario",
      "moisture drift",
      "temperature spike",
      "underfeeding",
      "compare policies",
      "policy comparison",
      "export appendix",
      "release appendix",
      "attach release packet",
      "attach simulation appendix",
      "run benchmark",
      "benchmark",
      "request model review",
      "model review",
      "governance review",
      "compliance",
      "release gate",
      "quality gate",
      "lca",
      "co2e",
      "carbon",
      "tea",
      "techno-economic",
      "value proof",
      "sustainability proof",
      "仿真",
      "模拟",
      "湿度漂移",
      "温度",
      "欠投喂",
      "比较策略",
    ]) ||
    (hasAny(text, ["scenario", "simulation"]) && hasAny(text, ["run", "create", "compare"]))
  ) {
    return "simulation_lab";
  }

  if (
    hasAny(text, [
      "怎么用",
      "help",
      "帮助",
      "能做什么",
      "可以做什么",
      "show commands",
      "what can you do",
    ])
  ) {
    return "help";
  }

  if (
    hasAny(text, ["老板摘要", "汇报摘要", "executive summary", "boss summary", "高层摘要"]) ||
    (hasAny(text, ["摘要", "summary"]) && hasAny(text, ["老板", "高层", "executive", "汇报"]))
  ) {
    return "executive_summary";
  }
  if (
    hasAny(text, ["最危险的批次", "风险最高的批次", "riskiest batch", "highest risk batch"]) ||
    ((hasAny(text, ["批次", "batch"]) && hasAny(text, ["最危险", "风险最高", "highest risk", "riskiest"])) ||
      (hasAny(text, ["找", "find"]) && hasAny(text, ["危险", "风险", "risk"]) && hasAny(text, ["批次", "batch"])))
  ) {
    return "riskiest_batch";
  }

  if (hasAny(text, ["打开signal", "open signal", "signal lab", "信号实验室"])) {
    return "open_signal_lab";
  }
  if (hasAny(text, ["打开brain", "open brain", "brain dashboard", "brain runtime"])) {
    return "open_brain";
  }
  if (hasAny(text, ["打开release", "open release", "release center", "发布中心"])) {
    return "open_release";
  }
  if (hasAny(text, ["打开dashboard", "open dashboard", "仪表盘", "总览页"])) {
    return "open_dashboard";
  }
  if (hasAny(text, ["打开twin", "open twin", "open twins", "孪生"])) {
    return "open_twins";
  }

  if (
    hasAny(text, ["compile signal", "编译信号"]) ||
    (hasAny(text, ["compile", "生成"]) && hasAny(text, ["signal", "信号"]))
  ) {
    return "compile_signal";
  }
  if (
    hasAny(text, ["refresh signal", "刷新信号"]) ||
    (hasAny(text, ["refresh", "刷新"]) && hasAny(text, ["signal", "信号"]))
  ) {
    return "refresh_signal";
  }
  if (
    hasAny(text, ["evaluate release", "评估发布"]) ||
    (hasAny(text, ["evaluate", "评估"]) && hasAny(text, ["release", "发布"]))
  ) {
    return "evaluate_release";
  }
  if (
    hasAny(text, ["export audit", "导出审计", "导出 audit", "audit export"]) ||
    (hasAny(text, ["audit", "审计"]) && hasAny(text, ["export", "导出", "download", "下载"]))
  ) {
    return "export_audit_packet";
  }
  if (
    hasAny(text, ["evaluate supervisor", "supervisor 评估", "评估 supervisor"]) ||
    (hasAny(text, ["supervisor"]) && hasAny(text, ["evaluate", "评估", "检查"]))
  ) {
    return "evaluate_supervisor";
  }
  if (
    hasAny(text, ["handover recommendation", "evaluate handover", "handover 评估", "handover recommendation"]) ||
    (hasAny(text, ["handover"]) && hasAny(text, ["recommendation", "评估", "建议"]))
  ) {
    return "handover_recommendation";
  }

  if (
    (hasAny(text, ["batch", "批次"]) && hasAny(text, ["分析", "analyze", "风险", "risk"])) ||
    hasAny(text, ["batch analysis", "批次分析", "批次风险"])
  ) {
    return "batch_analysis";
  }
  if (
    (hasAny(text, ["batch", "批次"]) && hasAny(text, ["比较", "compare", "对比"])) ||
    hasAny(text, ["batch compare", "批次对比"])
  ) {
    return "batch_compare";
  }
  if (
    hasAny(text, ["batch guidance", "批次 guidance", "批次建议", "next actions"]) ||
    (hasAny(text, ["batch", "批次"]) && hasAny(text, ["guidance", "建议", "动作"]))
  ) {
    return "batch_guidance";
  }

  if (hasAny(text, ["brain", "项目脑", "decision journal", "run ledger"])) {
    return "brain_summary";
  }
  if (
    (hasAny(text, ["release", "发布"]) && hasAny(text, ["risk", "风险", "blocking", "阻塞"])) ||
    hasAny(text, ["release risks", "发布风险"])
  ) {
    return "release_risks";
  }
  if (hasAny(text, ["release", "发布", "release summary", "发布总结", "ready"])) {
    return "release_summary";
  }
  if (hasAny(text, ["native runtime", "runtime status", "模型运行时", "本地模型", "native model"])) {
    return "native_runtime";
  }
  if (hasAny(text, ["species catalog", "物种库", "物种目录", "species list"])) {
    return "species_catalog";
  }
  if (hasAny(text, ["feedstock", "原料库", "底物库", "feedstocks"])) {
    return "feedstocks_catalog";
  }
  if (hasAny(text, ["manuscript", "campaign", "参考实验", "文献实验", "references"])) {
    return "manuscript_catalog";
  }
  if (
    hasAny(text, [
      "ser trend",
      "趋势图",
      "ser图",
      "ser trend chart",
      "trend chart",
      "走势图",
    ])
  ) {
    return "ser_trend_chart";
  }
  if (hasAny(text, ["grade chart", "等级图", "grade distribution", "等级分布"])) {
    return "grade_chart";
  }
  if (hasAny(text, ["species chart", "物种图", "species distribution", "物种分布"])) {
    return "species_chart";
  }
  if (hasAny(text, ["signals table", "信号表", "signal table"])) {
    return "signals_table";
  }
  if (hasAny(text, ["audit table", "audit packet", "审计表", "审计包"])) {
    return "audit_table";
  }
  if (hasAny(text, ["twins table", "孪生表", "twin table"])) {
    return "twins_table";
  }
  if (hasAny(text, ["batches table", "批次表", "batch table", "列表"])) {
    return "batches_table";
  }
  if (hasAny(text, ["所有数据", "总览", "overview", "dashboard", "全局情况"])) {
    return "overview";
  }
  if (hasAny(text, ["表格", "出表"])) {
    return "batches_table";
  }
  if (hasAny(text, ["画图", "图表", "chart"])) {
    return "ser_trend_chart";
  }

  return null;
}

export function buildBosAssistantHelpResult(): AssistantStructuredResult {
  return {
    title: "BOS Assistant command surface",
    summary:
      "This page can now answer BOS data requests directly, in addition to BOS Code threads and media generation.",
    table: {
      columns: ["What to ask", "What BOS returns"],
      rows: [
        ["看 BOS 总览 / show overview", "Executive metrics plus the fastest next pages to open"],
        ["出批次表 / show batches table", "A compact batch table inside the chat thread"],
        ["看信号表 / show signals table", "Signal freshness, potency, and stability window"],
        ["看审计表 / show audit table", "Audit packet readiness and evidence posture"],
        ["画 SER 趋势图 / show SER trend", "A live SER trend chart in the conversation"],
        ["画等级分布图 / show grade chart", "Grade distribution chart for recent results"],
        ["画物种分布图 / show species chart", "Species mix chart from dashboard data"],
        ["看项目脑 / show brain summary", "Brain runtime document counts and freshness"],
        ["看发布总结 / show release summary", "Release readiness summary and quick jump"],
        ["找最危险的批次 / riskiest batch", "Find the batch with the heaviest current BOS risk posture"],
        ["分析批次 12 / analyze batch 12", "A focused batch health summary with next actions"],
        ["比较最近两个批次 / compare latest batches", "A side-by-side comparison of the newest batches"],
        ["给我老板摘要 / executive summary", "A concise management-ready BOS summary"],
        ["看发布风险 / show release risks", "Blocking and warning factors ranked from release packets"],
        ["看 native runtime / show runtime status", "Local model runtime and adapter readiness"],
        ["看批次建议 12 / show batch guidance 12", "Gap items and recommended actions for a batch"],
        ["导出审计包 12 / export audit 12", "Export the audit packet for a batch right from chat"],
        ["评估 supervisor 12 / evaluate supervisor 12", "Run BOS supervisor against the newest signal for a batch"],
        ["评估 handover 12 / evaluate handover 12", "Get BOS handover recommendation for the newest signal"],
        ["看参考实验 / show references", "Campaign and manuscript reference table"],
        ["编译信号 12 / compile signal 12", "Trigger BOS signal compilation for a batch"],
        ["刷新信号 12 / refresh signal 12", "Refresh the newest signal state for a batch"],
        ["评估发布 12 / evaluate release 12", "Run release evaluation for a batch"],
        ["attach release packet", "Attach a Simulation Lab appendix to the latest or specified release decision"],
        ["run benchmark", "Run the Simulation Lab regression benchmark and return BMR evidence"],
        ["request model review", "Register a model candidate and create a pending HAR review request"],
        ["看孪生表 / show twins table", "Twin state and version overview"],
      ],
    },
    notes: [
      "If your request is about code changes, BOS will still route it into the live BOS Code thread.",
      "If your request is about posters, covers, animations, or images, BOS will still route it into the media flow.",
    ],
    actions: [
      { label: "Open dashboard", to: "/dashboard" },
      { label: "Open signal lab", to: "/bos/signal-lab" },
      { label: "Open release center", to: "/release" },
    ],
  };
}
