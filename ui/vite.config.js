import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load BASE_URL_PATH from parent .env file (same one backend uses)
  const env = loadEnv(mode, '../', 'BASE_URL')

  return {
    base: env.BASE_URL_PATH || '/',
    plugins: [react()],
  }
})
