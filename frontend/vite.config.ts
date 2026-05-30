import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const BACKEND = 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../backend/norn/static',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/chat': BACKEND,
      '/webhook': BACKEND,
      '/reviews': BACKEND,
      '/dashboard': BACKEND,
      '/healthz': BACKEND,
      '/readyz': BACKEND,
    },
  },
});
