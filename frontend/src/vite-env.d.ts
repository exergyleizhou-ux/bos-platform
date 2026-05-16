/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  readonly VITE_APP_TITLE?: string;
  readonly VITE_ENABLE_DIGITAL_TWINS?: string;
  readonly VITE_ENABLE_SUSTAINABILITY?: string;
  readonly VITE_ENABLE_FORECAST?: string;
  readonly VITE_ENABLE_BOS_SIMULATION_LAB?: string;
  readonly VITE_SCENE_RENDERER_MODE?: "auto" | "procedural" | "gaussian";
  readonly VITE_GAUSSIAN_SCENE_MANIFEST?: string;
  readonly VITE_GAUSSIAN_SPLATS_CDN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
