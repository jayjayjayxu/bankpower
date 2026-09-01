import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

function redirectLegacyLogin() {
  const handle = (req, res, next) => {
    if (req.url?.split('?')[0] === '/login') {
      res.statusCode = 302
      res.setHeader('Location', '/')
      res.end()
      return
    }
    next()
  }
  return {
    name: 'redirect-legacy-login',
    configureServer(server) { server.middlewares.use(handle) },
    configurePreviewServer(server) { server.middlewares.use(handle) },
  }
}

export default defineConfig({
  plugins: [vue(), redirectLegacyLogin()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8081',
        changeOrigin: true,
      },
      '/ai-api': {
        target: 'http://127.0.0.1:8090',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/ai-api/, '/api'),
      },
    },
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
    strictPort: true,
  },
})
