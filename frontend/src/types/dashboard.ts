/**
 * BOS Pipeline v9.0 -Dashboard Types
 *
 * Type definitions for dashboard summaries, trends, and activity.
 */

// Summary KPIs 

export interface DashboardSummary {
 total_batches: number;
 active_batches: number;
 completed_batches: number;
 avg_ser: number;
 avg_pass_rate: number;
 total_twins: number;
 batches_this_week: number;
 ser_improvement_pct: number | null;
}

export interface BOSLedgerSummary {
 total_dm_in: number;
 total_dm_out: number;
 avg_d_prime: number | null;
 avg_g_prime: number | null;
 avg_ser: number | null;
 avg_metering_completeness: number | null;
 avg_closure_residual: number | null;
 boundary_records: number;
 release_pass_rate: number;
 decision_counts: Record<string, number>;
 evidence_distribution: Record<string, number>;
 total_audit_packets: number;
}

// SER Trend 

export interface SERTrendResponse {
 data_points: SERTrendPoint[];
 period_days: number;
}

export interface SERTrendPoint {
 date: string;
 ser_value: number;
 batch_count: number;
}

// Species Distribution 

export interface SpeciesDistributionResponse {
 distribution: SpeciesDistributionItem[];
 total: number;
}

export interface SpeciesDistributionItem {
 species: string;
 count: number;
 percentage: number;
}

// Grade Distribution 

export interface GradeDistributionResponse {
 items: GradeDistributionItem[];
 total: number;
}

export interface GradeDistributionItem {
 grade: string;
 count: number;
 percentage: number;
}

// Recent Activity 

export interface RecentActivityResponse {
 activities: ActivityItem[];
}

export interface ActivityItem {
 id: number;
 action: ActivityAction;
 user_name: string;
 description: string;
 entity_type: string;
 entity_id: number | null;
 timestamp: string;
}

export type ActivityAction =
 | "batch_created"
 | "batch_updated"
 | "batch_completed"
 | "batch_deleted"
 | "ser_computed"
 | "twin_created"
 | "twin_simulated"
 | "simulation_run"
 | "user_login";

/**
 * Returns a Tailwind text-color class for a given activity action.
 */
export function getActivityColor(action: ActivityAction): string {
 const map: Record<ActivityAction, string> = {
 batch_created: "text-blue-500",
 batch_updated: "text-amber-500",
 batch_completed: "text-green-500",
 batch_deleted: "text-red-500",
 ser_computed: "text-purple-500",
 twin_created: "text-cyan-500",
 twin_simulated: "text-indigo-500",
 simulation_run: "text-pink-500",
 user_login: "text-surface-400",
 };
 return map[action] ?? "text-surface-400";
}
