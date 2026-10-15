import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  // In docker-compose the backend is reachable as http://backend:8000.
  const target = env.VITE_PROXY_TARGET || 'http://localhost:8000'
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      proxy: {
        '/api': { target, changeOrigin: false },
        '/media': { target, changeOrigin: false },
      },
    },
    build: { sourcemap: true },
  }
})
