import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load BASE_URL_PATH from parent .env file (same one backend uses)
  // In Docker, process.env.BASE_URL_PATH is set via build ARG
  const env = loadEnv(mode, '../', 'BASE_URL')
  const basePath = process.env.BASE_URL_PATH || env.BASE_URL_PATH || '/'
  // Ensure basePath ends with / for proper URL construction
  const baseWithSlash = basePath.endsWith('/') ? basePath : basePath + '/'

  return {
    base: baseWithSlash,
    plugins: [react()],
    server: {
      proxy: {
        // Proxy API calls to the backend in dev mode
        [`${baseWithSlash}query`]: 'http://localhost:8000',
        [`${baseWithSlash}health`]: 'http://localhost:8000',
        [`${baseWithSlash}documents`]: 'http://localhost:8000',
        [`${baseWithSlash}upload`]: 'http://localhost:8000',
        [`${baseWithSlash}config`]: 'http://localhost:8000',
      }
    }
  }
})
