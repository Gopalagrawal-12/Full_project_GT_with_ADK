/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ADK_API_BASE?: string;
  readonly VITE_ADK_API_PREFIX?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
