/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// The API runs on this machine only (docs/frontend.md §14): `npm run dev` proxies /api and the live socket to it.
const api = 'http://127.0.0.1:8765'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  build: {
    // the API serves this folder (frontend/dist); it is not committed: CI builds it and the installer copies it
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
  },
  server: { port: 5173, proxy: { '/api': { target: api, ws: true, changeOrigin: false } } },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    testTimeout: 20_000, // whole-app tests mount the router, Radix and the query cache

    exclude: ['e2e/**', 'node_modules/**'],
    env: { TZ: 'America/Sao_Paulo' }, // dates show in the station's time zone, the same on every machine and in CI
  },
})
