import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const BACKEND = 'http://localhost:8000';

export default defineConfig(({ mode }) => {
  const swaBuild = mode === 'swa';

  return {
    plugins: [react()],
    build: {
      outDir: swaBuild ? 'dist' : '../backend/norn/static',
      emptyOutDir: true,
    },
    server: {
      port: 5173,
      proxy: {
        '/auth': BACKEND,
        '/chat': BACKEND,
        '/webhook': BACKEND,
        '/reviews': BACKEND,
        '/dashboard': BACKEND,
        '/healthz': BACKEND,
        '/readyz': BACKEND,
      },
    },
  };
});
