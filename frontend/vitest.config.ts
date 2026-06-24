import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Dedicated test config — intentionally does NOT load the Tailwind or Sentry
// vite plugins (not needed under jsdom; they only add build noise). Component
// tests run against the React plugin alone.
export default defineConfig({
  plugins: [react()],
  envDir: '..',
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
})
