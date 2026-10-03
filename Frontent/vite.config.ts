import { defineConfig } from 'vitest/config'
import { loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const agentProxyTarget = env.VITE_AGENT_PROXY_TARGET

  return {
    plugins: [react(), tailwindcss()],
    server: agentProxyTarget
      ? { proxy: { '/agent': { target: agentProxyTarget, changeOrigin: true } } }
      : {},
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
      css: true,
    },
  }
})
