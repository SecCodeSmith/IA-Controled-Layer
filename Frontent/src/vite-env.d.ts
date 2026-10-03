/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CONTROL_LAYER_URL?: string
  readonly VITE_AGENT_URL?: string
  readonly VITE_ADMIN_TOKEN?: string
  readonly VITE_USE_MOCKS?: string
  readonly VITE_AGENT_PROXY_TARGET?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
