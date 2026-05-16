export type RemotionRenderKind = "still" | "video";

export interface RemotionTemplateField {
  key: string;
  label: string;
  kind: "text" | "textarea" | "color" | "number" | "select";
  required: boolean;
  default: string | number | null;
  helper_text?: string | null;
  options?: Array<{ value: string; label: string }> | null;
  min?: number | null;
  max?: number | null;
  step?: number | null;
}

export interface RemotionTemplate {
  id: string;
  name: string;
  description: string;
  supported_kinds: RemotionRenderKind[];
  default_width: number;
  default_height: number;
  default_duration_in_frames: number;
  default_fps: number;
  fields: RemotionTemplateField[];
}

export interface RemotionHealth {
  enabled: boolean;
  ready: boolean;
  runtime_dir: string;
  output_dir: string;
  node_executable: string;
  details: string[];
}

export interface RemotionRenderRequest {
  kind: RemotionRenderKind;
  template_id: string;
  title: string;
  subtitle?: string;
  caption?: string;
  accent_color?: string;
  background_color?: string;
  width?: number;
  height?: number;
  fps?: number;
  duration_in_frames?: number;
  extra_props?: Record<string, unknown>;
}

export interface RemotionSuggestRequest {
  brief: string;
  preferred_kind?: RemotionRenderKind;
  preferred_template_id?: string;
  audience?: string;
  brand_voice?: string;
}

export interface RemotionSuggestResponse {
  source: "heuristic" | "model";
  template_id: string;
  kind: RemotionRenderKind;
  title: string;
  subtitle: string;
  caption: string;
  accent_color: string;
  background_color: string;
  width: number;
  height: number;
  fps: number;
  duration_in_frames: number;
  extra_props: Record<string, unknown>;
  rationale: string[];
}

export interface RemotionRenderResponse {
  job_id: string;
  kind: RemotionRenderKind;
  template_id: string;
  file_name: string;
  mime_type: string;
  width: number;
  height: number;
  fps?: number | null;
  duration_in_frames?: number | null;
  created_at: string;
  asset_url: string;
  download_url: string;
}

export interface RemotionAssistantRunRequest {
  prompt: string;
  preferred_kind?: RemotionRenderKind;
  preferred_template_id?: string;
  audience?: string;
  brand_voice?: string;
}

export interface RemotionAssistantRunResponse {
  summary: string;
  suggestion: RemotionSuggestResponse;
  render: RemotionRenderResponse;
}

export interface RemotionPreset {
  id: string;
  name: string;
  tags: string[];
  snapshot_file_name?: string | null;
  snapshot_kind?: RemotionRenderKind | null;
  template_id: string;
  kind: RemotionRenderKind;
  export_recipe_id: string;
  creative_brief: string;
  audience: string;
  brand_voice: string;
  title: string;
  subtitle: string;
  caption: string;
  accent_color: string;
  background_color: string;
  width: string;
  height: string;
  fps: string;
  duration_in_frames: string;
  dynamic_fields: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export interface RemotionPresetCreateRequest {
  name: string;
  tags: string[];
  snapshot_file_name?: string;
  snapshot_kind?: RemotionRenderKind;
  template_id: string;
  kind: RemotionRenderKind;
  export_recipe_id: string;
  creative_brief: string;
  audience: string;
  brand_voice: string;
  title: string;
  subtitle: string;
  caption: string;
  accent_color: string;
  background_color: string;
  width: string;
  height: string;
  fps: string;
  duration_in_frames: string;
  dynamic_fields: Record<string, string>;
}

export type RemotionPresetUpdateRequest = RemotionPresetCreateRequest;
