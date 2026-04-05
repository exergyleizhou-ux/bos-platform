/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  readonly VITE_APP_TITLE?: string;
  readonly VITE_ENABLE_DIGITAL_TWINS?: string;
  readonly VITE_ENABLE_SUSTAINABILITY?: string;
  readonly VITE_ENABLE_FORECAST?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
