import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import fs from 'node:fs'

export default defineConfig({
  plugins: [vue(), {
    name: 'easyfix-cloudflare-cutover',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const marker = path.resolve(__dirname, '../backend/config/cloudflare-cutover.json')
        if (req.method === 'GET' && req.headers.accept?.includes('text/html') && fs.existsSync(marker)) {
          const state = JSON.parse(fs.readFileSync(marker, 'utf8'))
          if (state.state === 'complete' && state.cloud_url === 'https://easyfix-bl2.pages.dev') {
            res.writeHead(302, { Location: state.cloud_url + req.url, 'Cache-Control': 'no-store' })
            res.end()
            return
          }
        }
        next()
      })
    },
  }],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
