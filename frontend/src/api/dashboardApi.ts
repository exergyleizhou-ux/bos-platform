/**
 * BOS Pipeline v9.0 dashboard API client.
 *
 * HTTP helpers for dashboard endpoints.
 */

import client from "@/api/client";
import type {
  DashboardSummary,
  GradeDistributionResponse,
  RecentActivityResponse,
  SERTrendResponse,
  SpeciesDistributionResponse,
} from "@/types/dashboard";

export const dashboardApi = {
  // Summary KPIs
  summary: async (): Promise<DashboardSummary> => {
    const { data } = await client.get<DashboardSummary>("/dashboard/summary");
    return data;
  },

  // SER trend
  serTrend: async (days: number): Promise<SERTrendResponse> => {
    const { data } = await client.get<SERTrendResponse>("/dashboard/ser-trend", {
      params: { days },
    });
    return data;
  },

  // Species distribution
  speciesDistribution: async (): Promise<SpeciesDistributionResponse> => {
    const { data } = await client.get<SpeciesDistributionResponse>(
      "/dashboard/species-distribution",
    );
    return data;
  },

  // Grade distribution
  gradeDistribution: async (): Promise<GradeDistributionResponse> => {
    const { data } = await client.get<GradeDistributionResponse>(
      "/dashboard/grade-distribution",
    );
    return data;
  },

  // Recent activity
  recentActivity: async (limit: number = 10): Promise<RecentActivityResponse> => {
    const { data } = await client.get<RecentActivityResponse>(
      "/dashboard/recent-activity",
      { params: { limit } },
    );
    return data;
  },
};
