import type { Batch, BatchStatus } from "@/types/batch";
import type { SERResult } from "@/types/ser";

export type EvidenceLevel = "Validated" | "Supported" | "Planned";
export type ReleaseTone = "success" | "warning" | "danger" | "neutral";

export interface DerivedBoundarySummary {
  dryMatterReduction: number | null;
  nitrogenRecovery: number | null;
  closureResidual: number | null;
  meteringCompleteness: number;
}

export function getEvidenceLevel(status: BatchStatus): EvidenceLevel {
  if (status === "completed") return "Validated";
  if (status === "active") return "Supported";
  return "Planned";
}

export function getEvidenceVariant(level: EvidenceLevel) {
  if (level === "Validated") return "success";
  if (level === "Supported") return "info";
  return "neutral";
}

export function getReleaseReadiness(
  batch: Batch,
  serResult?: SERResult | null,
): {
  label: string;
  tone: ReleaseTone;
  description: string;
  blockers: string[];
} {
  if (!serResult) {
    return {
      label: "Awaiting compute",
      tone: "warning",
      description:
        "Release posture is incomplete because no SER result has been computed yet.",
      blockers: ["SER result missing", "Decision evidence not compiled"],
    };
  }

  if (batch.status === "failed") {
    return {
      label: "Blocked",
      tone: "danger",
      description:
        "The batch is in a failed state and requires operator review before any release action.",
      blockers: ["Batch status is failed", "Requalification required"],
    };
  }

  if (!serResult.passed) {
    return {
      label: "Requalify",
      tone: "warning",
      description:
        "The latest result is outside the preferred release window and should be reviewed with retuning or requalification.",
      blockers: ["SER exceeds preferred release threshold"],
    };
  }

  if (batch.status === "completed") {
    return {
      label: "Ready",
      tone: "success",
      description:
        "Current computed result is within the preferred release envelope and the batch is completed.",
      blockers: [],
    };
  }

  return {
    label: "Monitor",
    tone: "neutral",
    description:
      "Signal quality is acceptable, but lifecycle state suggests continued monitoring before release.",
    blockers: ["Batch lifecycle has not reached completed state"],
  };
}

export function deriveBoundarySummary(batch: Batch): DerivedBoundarySummary {
  const dryMatterReduction =
    batch.dm_in > 0 ? ((batch.dm_in - batch.dm_out) / batch.dm_in) * 100 : null;

  const recoveredNitrogen =
    (batch.n_larvae ?? 0) + (batch.n_frass ?? 0);
  const nitrogenRecovery =
    batch.n_in && batch.n_in > 0
      ? (recoveredNitrogen / batch.n_in) * 100
      : null;

  const closureResidual =
    batch.n_in != null
      ? Math.abs((batch.n_in ?? 0) - recoveredNitrogen)
      : null;

  const meteredFields = [
    batch.n_in,
    batch.n_larvae,
    batch.n_frass,
    batch.ash_in,
    batch.ash_out,
    batch.fat_in,
    batch.fat_out,
    batch.temperature,
    batch.moisture,
    batch.feed_rate,
    batch.density,
  ];

  const present = meteredFields.filter(
    (value) => value !== null && value !== undefined,
  ).length;

  return {
    dryMatterReduction,
    nitrogenRecovery,
    closureResidual,
    meteringCompleteness: present / meteredFields.length,
  };
}

export function getStatusRail(status: BatchStatus) {
  return [
    { key: "logged", label: "Logged" },
    { key: "active", label: "Active" },
    { key: "completed", label: "Completed" },
    { key: "archived", label: "Archived" },
  ].map((item) => ({
    ...item,
    active: item.key === status,
    passed:
      ["logged", "active", "completed", "archived"].indexOf(item.key) <=
      ["logged", "active", "completed", "archived"].indexOf(status),
  }));
}

export function getControlApiVersion(batch: Batch) {
  if (batch.status === "completed") return "CTRL-2.3";
  if (batch.status === "active") return "CTRL-2.2";
  return "CTRL-2.1";
}

export function getSignalFreshness(batch: Batch) {
  const updated = new Date(batch.updated_at).getTime();
  const ageHours = (Date.now() - updated) / 3_600_000;

  if (ageHours < 6) return { label: "Fresh", variant: "success" as const };
  if (ageHours < 24) return { label: "Stable", variant: "info" as const };
  return { label: "Stale", variant: "warning" as const };
}
