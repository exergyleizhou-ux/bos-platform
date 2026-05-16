import { describe, expect, it } from "vitest";

import {
  buildBosAssistantHelpResult,
  detectBosAssistantIntent,
  getBosAssistantGraphName,
  isBosAssistantGraphBackedIntent,
} from "@/lib/bosAssistant";

describe("bosAssistant", () => {
  it("detects overview and table intents from Chinese prompts", () => {
    expect(detectBosAssistantIntent("帮我看一下所有数据总览")).toBe("overview");
    expect(detectBosAssistantIntent("给我出批次表格")).toBe("batches_table");
    expect(detectBosAssistantIntent("看审计表")).toBe("audit_table");
  });

  it("detects chart and page-opening intents", () => {
    expect(detectBosAssistantIntent("画 SER 趋势图")).toBe("ser_trend_chart");
    expect(detectBosAssistantIntent("打开 release center")).toBe("open_release");
    expect(detectBosAssistantIntent("看项目脑")).toBe("brain_summary");
  });

  it("detects analysis and runtime intents from natural language", () => {
    expect(detectBosAssistantIntent("分析批次 12 的风险和建议")).toBe("batch_analysis");
    expect(detectBosAssistantIntent("帮我找最近最危险的批次并给建议")).toBe("riskiest_batch");
    expect(detectBosAssistantIntent("看 native runtime")).toBe("native_runtime");
    expect(detectBosAssistantIntent("看参考实验")).toBe("manuscript_catalog");
    expect(detectBosAssistantIntent("比较最近两个批次")).toBe("batch_compare");
    expect(detectBosAssistantIntent("给我一个老板摘要")).toBe("executive_summary");
    expect(detectBosAssistantIntent("看发布风险")).toBe("release_risks");
    expect(detectBosAssistantIntent("编译信号 12")).toBe("compile_signal");
    expect(detectBosAssistantIntent("刷新信号 12")).toBe("refresh_signal");
    expect(detectBosAssistantIntent("评估发布 12")).toBe("evaluate_release");
    expect(detectBosAssistantIntent("看批次建议 12")).toBe("batch_guidance");
    expect(detectBosAssistantIntent("导出审计包 12")).toBe("export_audit_packet");
    expect(detectBosAssistantIntent("评估 supervisor 12")).toBe("evaluate_supervisor");
    expect(detectBosAssistantIntent("评估 handover 12")).toBe("handover_recommendation");
  });

  it("detects Simulation Lab assistant control-plane prompts", () => {
    expect(detectBosAssistantIntent("create a moisture drift scenario, run 6 cycles, compare policies")).toBe(
      "simulation_lab",
    );
    expect(detectBosAssistantIntent("run simulation scenario temperature spike")).toBe("simulation_lab");
    expect(detectBosAssistantIntent("attach release packet and run benchmark")).toBe("simulation_lab");
    expect(detectBosAssistantIntent("request model review from benchmark evidence")).toBe("simulation_lab");
    expect(getBosAssistantGraphName("simulation_lab")).toBeNull();
  });

  it("detects Research Review assistant control-plane prompts", () => {
    expect(detectBosAssistantIntent("research review this protocol with an expert team")).toBe("research_review");
    expect(detectBosAssistantIntent("请做课题方案评审，并让机制分析师检查反例")).toBe("research_review");
    expect(detectBosAssistantIntent("请做课题方案评审：餐厨垃圾替代饲料基质的污染风险控制")).toBe("research_review");
    expect(detectBosAssistantIntent("你觉得黄粉虫和蛴螬 哪个更适合处理酒糟")).toBe("research_review");
    expect(detectBosAssistantIntent("比较黑水虻和黄粉虫处理餐厨垃圾的污染风险")).toBe("research_review");
    expect(detectBosAssistantIntent("scientific review a digital twin validation plan")).toBe("research_review");
    expect(getBosAssistantGraphName("research_review")).toBeNull();
  });

  it("builds a help result with table rows and actions", () => {
    const result = buildBosAssistantHelpResult();

    expect(result.title).toContain("BOS Assistant");
    expect(result.table?.rows.length).toBeGreaterThan(5);
    expect(result.actions?.some((item) => item.to === "/dashboard")).toBe(true);
  });

  it("maps graph-backed intents to assistant graph names", () => {
    expect(getBosAssistantGraphName("riskiest_batch")).toBe("batch_triage_graph");
    expect(getBosAssistantGraphName("executive_summary")).toBe("release_review_graph");
    expect(getBosAssistantGraphName("evaluate_release")).toBe("release_review_graph");
    expect(getBosAssistantGraphName("compile_signal")).toBe("signal_runtime_graph");
    expect(getBosAssistantGraphName("overview")).toBeNull();
    expect(isBosAssistantGraphBackedIntent("handover_recommendation")).toBe(true);
    expect(isBosAssistantGraphBackedIntent("overview")).toBe(false);
  });

  it("keeps every implementation-package assistant action graph-backed", () => {
    const requiredGraphBackedIntents = [
      "compile_signal",
      "refresh_signal",
      "evaluate_release",
      "evaluate_supervisor",
      "handover_recommendation",
      "batch_guidance",
      "export_audit_packet",
      "executive_summary",
      "riskiest_batch",
    ] as const;

    for (const intent of requiredGraphBackedIntents) {
      expect(getBosAssistantGraphName(intent), intent).not.toBeNull();
    }
  });
});
