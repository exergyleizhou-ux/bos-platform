/**
 * BOS Pipeline v9.0 �� Dashboard API Client
 *
 * HTTP functions for dashboard data endpoints.
 * Note: Most dashboard data is fetched directly in useDashboard hooks.
 * This module provides standalone functions for reuse outside hooks.
 */

import client from "@/api/client";
import type {
  DashboardSummary,
  SERTrendResponse,
  SpeciesDistributionResponse,
  GradeDistributionResponse,
  RecentActivityResponse,
} from "@/types/dashboard";

export const dashboardApi = {
  // ���� Summary KPIs ����
  summary: async (): Promise<DashboardSummary> => {
    const { data } = await client.get<DashboardSummary>(
      "/dashboard/summary",
    );
    return data;
  },

  // ���� SER Trend ����
  serTrend: async (days: number): Promise<SERTrendResponse> => {
    const { data } = await client.get<SERTrendResponse>(
      "/dashboard/ser-trend",
      { params: { days } },
    );
    return data;
  },

  // ���� Species Distribution ����
  speciesDistribution: async (): Promise<SpeciesDistributionResponse> => {
    const { data } = await client.get<SpeciesDistributionResponse>(
      "/dashboard/species-distribution",
    );
    return data;
  },

  // ���� Grade Distribution ����
  gradeDistribution: async (): Promise<GradeDistributionResponse> => {
    const { data } = await client.get<GradeDistributionResponse>(
      "/dashboard/grade-distribution",
    );
    return data;
  },

  // ���� Recent Activity ����
  recentActivity: async (
    limit: number = 10,
  ): Promise<RecentActivityResponse> => {
    const { data } = await client.get<RecentActivityResponse>(
      "/dashboard/recent-activity",
      { params: { limit } },
    );
    return data;
  },
};
