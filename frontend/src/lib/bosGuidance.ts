import type {
  BatchGuidanceResponse,
  GuidanceItem,
  PortabilityAudit,
  ReleaseDecision,
  SignalBatch,
} from "@/types/bos";

export interface BosNextBestActionItem {
  code: string;
  title: string;
  message: string;
  recommendedAction: string;
  severity: "info" | "warning" | "critical";
  blocking: boolean;
  actionIntent?: BosActionIntent;
}

export type BosActionIntent =
  | "compile_signal"
  | "refresh_signal"
  | "evaluate_release"
  | "export_audit_packet"
  | "compute_ser"
  | "edit_batch"
  | "open_signal_lab"
  | "open_decision_console";

const REASON_CODE_ACTIONS: Record<string, string> = {
  missing_signal_batch: "Compile a signal batch before evaluating release again.",
  stale_signal: "Refresh or recompile the signal before evaluating release again.",
  missing_potency: "Capture potency or recompile the signal before making a release decision.",
  invalid_potency: "Correct the signal potency inputs before making a release decision.",
  potency_out_of_contract: "Retune the control profile or compile a signal that fits the dose window.",
  missing_stability_window: "Refresh the signal state or compile a signal with a stability window.",
  stability_critically_below_mtt: "Increase the stability window or lower the contract MTT before release.",
  stability_below_mtt: "Review the MTT mismatch and retune the handover plan before release.",
  metering_too_sparse: "Capture the missing metering before evaluating release again.",
};

const GUIDANCE_OVERRIDES: Partial<Record<GuidanceItem["code"], Partial<BosNextBestActionItem>>> = {
  missing_signal_batch: {
    title: "Compile the signal first",
    message: "This batch does not have a usable signal yet. Generate one first, then continue with the release decision.",
    recommendedAction: "Compile the signal first",
    severity: "critical",
    blocking: true,
  },
  stale_signal_window: {
    title: "Refresh or recompile the signal first",
    message: "The current signal is outside the trusted freshness window, so downstream release confidence is reduced.",
    recommendedAction: "Refresh or recompile the signal first",
    severity: "critical",
    blocking: true,
  },
  no_portability_check: {
    title: "Run the portability check first",
    message: "No portability check has been run yet. Confirm the target executor and locality conditions first.",
    recommendedAction: "Run the portability check first",
  },
  missing_potency: {
    title: "Fill in signal potency first",
    message: "The current signal is missing potency information, so a release decision would be overly conservative.",
    recommendedAction: "Fill in signal potency or recompile the signal",
    severity: "critical",
    blocking: true,
  },
  missing_n_larvae: {
    title: "Capture larvae nitrogen recovery data",
    message: "Larvae nitrogen data is missing and reduces the evidence completeness for this batch.",
    recommendedAction: "Capture larvae nitrogen recovery data",
  },
  missing_n_frass: {
    title: "Capture frass nitrogen recovery data",
    message: "Frass nitrogen data is missing, so the closed-loop evidence is still incomplete.",
    recommendedAction: "Capture frass nitrogen recovery data",
  },
  metering_too_sparse: {
    title: "Evidence is incomplete; do not decide yet",
    message: "Key metering for this batch is still too sparse to support a release decision.",
    recommendedAction: "Evidence is incomplete; do not decide yet",
    severity: "critical",
    blocking: true,
  },
  locality_not_selected: {
    title: "Add locality conditions",
    message: "The current judgment is missing locality context, so the recommendation will stay conservative.",
    recommendedAction: "Add locality conditions before evaluating again",
  },
  missing_control_profile: {
    title: "Select a control profile first",
    message: "This batch is not attached to a usable control profile yet, so release confidence stays low.",
    recommendedAction: "Select or create a control profile first",
  },
  missing_stability_window: {
    title: "Refresh signal status first",
    message: "The current signal is missing stability-window information. Refresh the status or compile a new one first.",
    recommendedAction: "Refresh signal status first",
  },
  release_not_evaluated: {
    title: "Run the release evaluation",
    message: "A signal exists, but there is still no formal release decision.",
    recommendedAction: "Continue with the release evaluation",
  },
  release_insufficient_evidence: {
    title: "Evidence is incomplete; do not decide yet",
    recommendedAction: "Fill the evidence gaps and re-evaluate release.",
    severity: "critical",
    blocking: true,
  },
  release_blocked: {
    title: "Release is currently blocked",
    severity: "critical",
    blocking: true,
  },
  release_retuning_required: {
    title: "Retune before release",
    recommendedAction: "Retune the release conditions and evaluate again before scale-up.",
    severity: "warning",
  },
  portability_failed: {
    title: "Portability failed for this target",
    recommendedAction: "Retune the executor or locality pairing before release.",
    severity: "critical",
    blocking: true,
  },
  portability_retuning_required: {
    title: "Retune portability before release",
    recommendedAction: "Retune the executor or locality settings before release.",
    severity: "warning",
  },
};

export function mapBosGuidanceItem(item: GuidanceItem): BosNextBestActionItem {
  const override = GUIDANCE_OVERRIDES[item.code] ?? {};
  const mappedItem = {
    code: item.code,
    title: override.title ?? item.title,
    message: override.message ?? item.message,
    recommendedAction: override.recommendedAction ?? item.recommended_action,
    severity: override.severity ?? item.severity,
    blocking: override.blocking ?? item.blocking,
  };
  return {
    ...mappedItem,
    actionIntent: getBosActionIntent(mappedItem),
  };
}

export function getBosActionIntent(
  item: Pick<BosNextBestActionItem, "code" | "recommendedAction">,
): BosActionIntent {
  const normalized = `${item.code} ${item.recommendedAction}`.toLowerCase();

  if (normalized.includes("export audit") || normalized.includes("audit packet")) {
    return "export_audit_packet";
  }
  if (normalized.includes("refresh signal") || normalized.includes("stale signal")) {
    return "refresh_signal";
  }
  if (
    normalized.includes("compile the signal") ||
    normalized.includes("recompile the signal") ||
    normalized.includes("fill in signal potency") ||
    normalized.includes("refresh signal status")
  ) {
    return "compile_signal";
  }
  if (
    normalized.includes("run the release evaluation") ||
    normalized.includes("evaluate release") ||
    normalized.includes("release evaluation")
  ) {
    return "evaluate_release";
  }
  if (
    normalized.includes("metering") ||
    normalized.includes("evidence is incomplete") ||
    normalized.includes("release score") ||
    normalized.includes("ser")
  ) {
    return "compute_ser";
  }
  if (
    normalized.includes("control profile") ||
    normalized.includes("control contract") ||
    normalized.includes("locality conditions")
  ) {
    return "edit_batch";
  }
  if (normalized.includes("decision console")) {
    return "open_decision_console";
  }
  return "open_signal_lab";
}

export function getBosActionLabel(
  intent: BosActionIntent,
  surface: "batch" | "signal_lab",
): string {
  if (intent === "compute_ser" && surface === "signal_lab") {
    return "Open batch command center";
  }
  if (intent === "open_signal_lab" && surface === "signal_lab") {
    return "Open decision console";
  }
  if (intent === "open_signal_lab") {
    return "Open signal lab";
  }
  if (intent === "open_decision_console") {
    return "Open decision console";
  }
  return ACTION_LABELS[intent];
}

const ACTION_LABELS: Record<BosActionIntent, string> = {
  compile_signal: "Compile signal",
  refresh_signal: "Refresh signal",
  evaluate_release: "Evaluate release",
  export_audit_packet: "Export audit packet",
  compute_ser: "Compute SER",
  edit_batch: "Edit batch",
  open_signal_lab: "Open signal lab",
  open_decision_console: "Open decision console",
};

export function deriveBosNextBestActions({
  guidance,
  signal,
  releaseDecision,
  portabilityAudits = [],
  hasControlProfile = true,
  hasLocalityProfile = true,
}: {
  guidance?: BatchGuidanceResponse | null;
  signal?: SignalBatch | null;
  releaseDecision?: ReleaseDecision | null;
  portabilityAudits?: PortabilityAudit[];
  hasControlProfile?: boolean;
  hasLocalityProfile?: boolean;
}): BosNextBestActionItem[] {
  if (guidance?.gap_items?.length) {
    return guidance.gap_items.map(mapBosGuidanceItem).slice(0, 3);
  }

  const items: BosNextBestActionItem[] = [];
  const freshness = (signal?.freshness_state ?? "").toLowerCase();
  const decision = (releaseDecision?.decision ?? "").toUpperCase();

  if (!signal) {
    pushAction(items, {
      code: "fallback_compile_signal",
      title: "Compile the signal first",
      message: "This batch does not have a usable signal yet. Generate one first, then continue with release qualification.",
      recommendedAction: "Compile the signal first",
      severity: "critical",
      blocking: true,
    });
  } else if (freshness.includes("stale")) {
    pushAction(items, {
      code: "fallback_stale_signal",
      title: "Refresh or recompile the signal first",
      message: "The current signal is aging out of its freshness window. Refresh the status or recompile before continuing.",
      recommendedAction: "Refresh or recompile the signal first",
      severity: "critical",
      blocking: true,
    });
  }

  if (!hasControlProfile) {
    pushAction(items, {
      code: "fallback_missing_control_profile",
      title: "Select a control profile first",
      message: "Release confidence stays low until a Control-API profile is attached to this review context.",
      recommendedAction: "Select or create a control profile first",
      severity: "warning",
      blocking: false,
    });
  }

  if (!hasLocalityProfile) {
    pushAction(items, {
      code: "fallback_missing_locality",
      title: "Add locality conditions",
      message: "The current review is missing locality context, so portability and release judgments stay conservative.",
      recommendedAction: "Add locality conditions before evaluating again",
      severity: "info",
      blocking: false,
    });
  }

  if (signal) {
    if (decision === "FAIL") {
      pushAction(items, {
        code: "fallback_release_blocked",
        title: "Release is currently blocked",
        message:
          releaseDecision?.blocking_factors?.[0] ??
          "The latest release evaluation found a blocking condition.",
        recommendedAction:
          primaryReasonCodeAction(releaseDecision?.reason_codes) ??
          "Resolve the blocking condition and evaluate release again.",
        severity: "critical",
        blocking: true,
      });
    } else if (decision === "PASS_WITH_RETUNING") {
      pushAction(items, {
        code: "fallback_release_retuning_required",
        title: "Retune before release",
        message:
          releaseDecision?.warning_factors?.[0] ??
          "The latest release evaluation recommends retuning or closer monitoring.",
        recommendedAction:
          primaryReasonCodeAction(releaseDecision?.reason_codes) ??
          "Retune the release conditions and evaluate again before scale-up.",
        severity: "warning",
        blocking: false,
      });
    } else if (decision === "INSUFFICIENT_EVIDENCE") {
      pushAction(items, {
        code: "fallback_release_insufficient_evidence",
        title: "Evidence is incomplete; do not decide yet",
        message:
          releaseDecision?.rationale ??
          "The latest release evaluation could not reach a confident decision.",
        recommendedAction:
          primaryReasonCodeAction(releaseDecision?.reason_codes) ??
          "Fill the evidence gaps and re-evaluate release.",
        severity: "critical",
        blocking: true,
      });
    } else if (!releaseDecision) {
      pushAction(items, {
        code: "fallback_release_not_evaluated",
        title: "Run the release evaluation",
        message: "A signal exists, but there is still no formal release decision.",
        recommendedAction: "Continue with the release evaluation",
        severity: "info",
        blocking: false,
      });
    }
  }

  const failingAudit = portabilityAudits.find((audit) => audit.outcome === "FAIL");
  if (failingAudit) {
    pushAction(items, {
      code: "fallback_portability_failed",
      title: "Portability failed for this target",
      message: "At least one persisted portability audit failed for the selected target context.",
      recommendedAction: "Retune the executor or locality pairing before release.",
      severity: "critical",
      blocking: true,
    });
  } else if (portabilityAudits.some((audit) => audit.retuning_required || audit.outcome === "PASS_WITH_RETUNING")) {
    pushAction(items, {
      code: "fallback_portability_retuning_required",
      title: "Retune portability before release",
      message: "A persisted portability audit indicates the target context can work only with retuning.",
      recommendedAction: "Retune the executor or locality settings before release.",
      severity: "warning",
      blocking: false,
    });
  } else if (signal && !portabilityAudits.length) {
    pushAction(items, {
      code: "fallback_no_portability_check",
      title: "Run the portability check first",
      message: "No persisted portability audit matches the current executor and locality context yet.",
      recommendedAction: "Run the portability check first",
      severity: "warning",
      blocking: false,
    });
  }

  return items.slice(0, 3);
}

function primaryReasonCodeAction(reasonCodes?: string[] | null) {
  for (const reasonCode of reasonCodes ?? []) {
    const action = REASON_CODE_ACTIONS[reasonCode];
    if (action) return action;
  }
  return null;
}

function pushAction(items: BosNextBestActionItem[], item: BosNextBestActionItem) {
  if (items.some((existing) => existing.code === item.code)) {
    return;
  }
  items.push({
    ...item,
    actionIntent: item.actionIntent ?? getBosActionIntent(item),
  });
}
