/**
 * BOS Pipeline v9.0 SER types.
 *
 * Type definitions for SER computation, results, and grading.
 */

export interface SERComputeRequest {
  dm_in: number;
  dm_out: number;
  n_in?: number;
  n_larvae?: number;
  n_frass?: number;
  ash_in?: number;
  ash_out?: number;
  fat_in?: number;
  fat_out?: number;
  batch_id?: number;
}

export interface SERComputeResponse {
  ser_value: number;
  eer: number;
  mcr: number;
  bcr: number;
  grade: string;
  passed: boolean;
  recommendations: string[];
  batch_id: number | null;
  computed_at: string;
}

export interface SERResult {
  id: number;
  batch_id: number;
  ser_value: number;
  eer: number;
  mcr: number;
  bcr: number;
  grade: string;
  passed: boolean;
  recommendations: string[];
  computed_at: string;
}

export interface SERHistoryResponse {
  items: SERHistoryItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface SERHistoryItem {
  id: number;
  batch_id: string | null;
  ser_value: number;
  eer: number;
  mcr: number;
  bcr: number;
  grade: string;
  passed: boolean;
  computed_at: string;
}

export const GRADE_THRESHOLDS = [
  { grade: "A+", min: 0.25 },
  { grade: "A", min: 0.2 },
  { grade: "B", min: 0.15 },
  { grade: "C", min: 0.1 },
  { grade: "D", min: 0.05 },
] as const;

export function scoreToGrade(ser: number | null): string {
  if (ser === null || ser === undefined) return "--";
  for (const { grade, min } of GRADE_THRESHOLDS) {
    if (ser >= min) return grade;
  }
  return "F";
}

export function getGradeColor(grade: string): string {
  const colors: Record<string, string> = {
    "A+": "#059669",
    A: "#22c55e",
    B: "#84cc16",
    C: "#f59e0b",
    D: "#f97316",
    F: "#ef4444",
  };
  return colors[grade] ?? "#94a3b8";
}

export function serPasses(ser: number): boolean {
  return ser >= 0.15;
}
