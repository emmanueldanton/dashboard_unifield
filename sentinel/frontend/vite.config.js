import { defineConfig } from 'vite';

export default defineConfig({
  base: '/sentinel/',
  build: {
    outDir: 'dist',
  },
  server: {
    proxy: {
      '/sentinel/api': {
        target: 'http://localhost:3005',
        changeOrigin: true,
      },
      '/sentinel/auth': {
        target: 'http://localhost:3005',
        changeOrigin: true,
      },
    },
  },
});
