/**
 * BOS Pipeline v9.0 �� SER Types
 *
 * Type definitions for SER computation, results, and grading.
 */

// ���� Compute Request ����
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

// ���� Compute Response ����
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

// ���� Stored Result (from DB) ����
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

// ���� History Response ����
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

// ���� Grade Helpers ����

export const GRADE_THRESHOLDS = [
  { grade: "A+", max: 0.05 },
  { grade: "A", max: 0.08 },
  { grade: "B", max: 0.12 },
  { grade: "C", max: 0.18 },
  { grade: "D", max: 0.25 },
] as const;

/**
 * Map SER value to letter grade.
 */
export function scoreToGrade(ser: number | null): string {
  if (ser === null || ser === undefined) return "��";
  for (const { grade, max } of GRADE_THRESHOLDS) {
    if (ser <= max) return grade;
  }
  return "F";
}

/**
 * Get color for a given grade.
 */
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

/**
 * Whether a SER value passes (grade B or better, i.e. �� 0.12).
 */
export function serPasses(ser: number): boolean {
  return ser <= 0.12;
}

