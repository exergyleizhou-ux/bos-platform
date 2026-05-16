export interface VisionDetection {
  label: string;
  confidence: number;
  bbox: number[];
}

export interface VisionObservation {
  image_id: string;
  detected_classes: string[];
  detections: VisionDetection[];
  dominant_label: string | null;
  confidence_mean: number | null;
  anomaly_flag: boolean;
  observation_summary: string;
  bbox_coverage_ratio?: number | null;
}

export interface VisionDetectionResponse {
  run_id: string;
  created_at: string;
  image_id: string;
  file_name: string;
  content_type: string | null;
  model_name: string;
  model_status: string;
  fallback_used: boolean;
  observation: VisionObservation;
  warnings: string[];
  artifact_path: string | null;
  metadata: Record<string, unknown>;
}

export interface VisionObservationAttachResponse {
  signal_batch_id: number;
  run_id: string;
  attached: boolean;
  observation: VisionObservation;
  audit_packet_refreshed: boolean;
}
