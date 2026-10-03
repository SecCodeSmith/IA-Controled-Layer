/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CONTROL_LAYER_URL?: string
  readonly VITE_AGENT_URL?: string
  readonly VITE_ADMIN_TOKEN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
