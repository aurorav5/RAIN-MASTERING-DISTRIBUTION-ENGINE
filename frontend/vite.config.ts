import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    host: true,
    port: 5173,
  },
  build: {
    rollupOptions: {
      // posthog-js is an optional runtime dep loaded dynamically only when
      // VITE_POSTHOG_KEY is configured. Mark external so Rollup doesn't try
      // to bundle it. The dynamic import() will simply fail gracefully at
      // runtime on deploys without the key (analytics.ts catches the error).
      external: ['posthog-js'],
    },
  },
})
