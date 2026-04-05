/**
 * BOS Pipeline v9.0 �� Dashboard Hooks
 *
 * React Query hooks for dashboard data fetching.
 */

import { useQuery } from "@tanstack/react-query";
import client from "@/api/client";
import type {
  DashboardSummary,
  SERTrendResponse,
  SpeciesDistributionResponse,
  GradeDistributionResponse,
  RecentActivityResponse,
  SpeciesDistributionItem,
  GradeDistributionItem,
  ActivityItem,
} from "@/types/dashboard";

// ���� Query Keys ����
export const dashboardKeys = {
  all: ["dashboard"] as const,
  summary: () => [...dashboardKeys.all, "summary"] as const,
  serTrend: (days: number) =>
    [...dashboardKeys.all, "ser-trend", days] as const,
  speciesDistribution: () =>
    [...dashboardKeys.all, "species-distribution"] as const,
  gradeDistribution: () =>
    [...dashboardKeys.all, "grade-distribution"] as const,
  recentActivity: (limit: number) =>
    [...dashboardKeys.all, "recent-activity", limit] as const,
};

type UnknownRecord = Record<string, unknown>;

function toNumber(value: unknown, fallback = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

function toSpeciesDistribution(
  payload: unknown,
): SpeciesDistributionResponse {
  const raw = (payload ?? {}) as UnknownRecord;
  const source = raw.distribution;

  if (Array.isArray(source)) {
    const distribution = source
      .map((item) => item as UnknownRecord)
      .map(
        (item): SpeciesDistributionItem => ({
          species: String(item.species ?? "Unknown"),
          count: toNumber(item.count),
          percentage: toNumber(item.percentage),
        }),
      );

    const total = distribution.reduce((sum, item) => sum + item.count, 0);
    const normalized = total > 0
      ? distribution.map((item) => ({
          ...item,
          percentage: item.percentage > 0
            ? item.percentage
            : (item.count / total) * 100,
        }))
      : distribution;

    return { distribution: normalized, total: toNumber(raw.total, total) };
  }

  if (source && typeof source === "object") {
    const entries = Object.entries(source as Record<string, unknown>);
    const total = entries.reduce((sum, [, value]) => sum + toNumber(value), 0);
    const distribution = entries.map(
      ([species, value]): SpeciesDistributionItem => {
        const count = toNumber(value);
        return {
          species,
          count,
          percentage: total > 0 ? (count / total) * 100 : 0,
        };
      },
    );
    return { distribution, total: toNumber(raw.total, total) };
  }

  return { distribution: [], total: 0 };
}

function toGradeDistribution(payload: unknown): GradeDistributionResponse {
  const raw = (payload ?? {}) as UnknownRecord;
  const source = raw.items;

  if (Array.isArray(source)) {
    const items = source
      .map((item) => item as UnknownRecord)
      .map(
        (item): GradeDistributionItem => ({
          grade: String(item.grade ?? "N/A"),
          count: toNumber(item.count),
          percentage: toNumber(item.percentage),
        }),
      );
    const total = items.reduce((sum, item) => sum + item.count, 0);
    return { items, total: toNumber(raw.total, total) };
  }

  const legacySource = raw.distribution;
  if (legacySource && typeof legacySource === "object") {
    const entries = Object.entries(legacySource as Record<string, unknown>);
    const total = entries.reduce((sum, [, value]) => sum + toNumber(value), 0);
    const items = entries.map(
      ([grade, value]): GradeDistributionItem => {
        const count = toNumber(value);
        return {
          grade,
          count,
          percentage: total > 0 ? (count / total) * 100 : 0,
        };
      },
    );
    return { items, total: toNumber(raw.total, total) };
  }

  return { items: [], total: 0 };
}

function toSummary(payload: unknown): DashboardSummary {
  const raw = (payload ?? {}) as UnknownRecord;
  const batches = (raw.batches ?? {}) as UnknownRecord;
  const ser = (raw.ser ?? {}) as UnknownRecord;
  const calculations = (raw.calculations ?? {}) as UnknownRecord;

  return {
    total_batches: toNumber(raw.total_batches, toNumber(batches.total)),
    active_batches: toNumber(raw.active_batches, toNumber(batches.active)),
    completed_batches: toNumber(
      raw.completed_batches,
      toNumber(batches.completed),
    ),
    avg_ser: toNumber(raw.avg_ser, toNumber(ser.average)),
    avg_pass_rate: toNumber(raw.avg_pass_rate, toNumber(calculations.pass_rate)),
    total_twins: toNumber(raw.total_twins, 0),
    batches_this_week: toNumber(raw.batches_this_week, 0),
    ser_improvement_pct:
      raw.ser_improvement_pct == null ? null : toNumber(raw.ser_improvement_pct),
  };
}

function toTrend(payload: unknown, days: number): SERTrendResponse {
  const raw = (payload ?? {}) as UnknownRecord;
  const source = Array.isArray(raw.data_points)
    ? raw.data_points
    : Array.isArray(raw.trend)
      ? raw.trend
      : [];

  return {
    period_days: toNumber(raw.period_days, days),
    data_points: source
      .map((item) => item as UnknownRecord)
      .map((item) => ({
        date: String(item.date ?? ""),
        ser_value: toNumber(item.ser_value, toNumber(item.ser)),
        batch_count: toNumber(item.batch_count, 1),
      })),
  };
}

function toRecentActivity(payload: unknown): RecentActivityResponse {
  const raw = (payload ?? {}) as UnknownRecord;
  const source = Array.isArray(raw.activities)
    ? raw.activities
    : Array.isArray(raw.batches)
      ? raw.batches
      : [];

  const activities = source
    .map((item) => item as UnknownRecord)
    .map(
      (item, idx): ActivityItem => ({
        id: toNumber(item.id, idx + 1),
        action: "batch_created",
        user_name: String(item.user_name ?? item.operator ?? "System"),
        description: String(
          item.description ??
            `updated batch ${String(item.batch_id ?? item.id ?? "")}`.trim(),
        ),
        entity_type: String(item.entity_type ?? "batch"),
        entity_id:
          item.entity_id == null ? toNumber(item.id, 0) : toNumber(item.entity_id, 0),
        timestamp: String(item.timestamp ?? item.created_at ?? new Date().toISOString()),
      }),
    );

  return { activities };
}

// ���� Summary KPIs ����
export function useDashboardSummary() {
  return useQuery({
    queryKey: dashboardKeys.summary(),
    queryFn: async () => {
      const { data } = await client.get<unknown>(
        "/dashboard/summary",
      );
      return toSummary(data);
    },
    staleTime: 2 * 60_000,
  });
}

// ���� SER Trend ����
export function useSERTrend(days: number) {
  return useQuery({
    queryKey: dashboardKeys.serTrend(days),
    queryFn: async () => {
      const { data } = await client.get<unknown>(
        "/dashboard/ser-trend",
        { params: { days } },
      );
      return toTrend(data, days);
    },
    staleTime: 2 * 60_000,
  });
}

// ���� Species Distribution ����
export function useSpeciesDistribution() {
  return useQuery({
    queryKey: dashboardKeys.speciesDistribution(),
    queryFn: async () => {
      const { data } = await client.get<unknown>(
        "/dashboard/species-distribution",
      );
      return toSpeciesDistribution(data);
    },
    staleTime: 5 * 60_000,
  });
}

// ���� Grade Distribution ����
export function useGradeDistribution() {
  return useQuery({
    queryKey: dashboardKeys.gradeDistribution(),
    queryFn: async () => {
      const { data } = await client.get<unknown>(
        "/dashboard/grade-distribution",
      );
      return toGradeDistribution(data);
    },
    staleTime: 5 * 60_000,
  });
}

// ���� Recent Activity ����
export function useRecentActivity(limit: number = 10) {
  return useQuery({
    queryKey: dashboardKeys.recentActivity(limit),
    queryFn: async () => {
      const { data } = await client.get<unknown>(
        "/dashboard/recent-activity",
        { params: { limit } },
      );
      return toRecentActivity(data);
    },
    staleTime: 60_000,
  });
}
