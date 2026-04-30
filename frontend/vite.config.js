import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// vite config - we set up the react plugin and proxy API calls to Flask
export default defineConfig({
    plugins: [react()],
    server: {
        port: 5173,
        // proxy so we don't have to hardcode localhost:5000 everywhere
        // any request to /api will get forwarded to our Flask backend
        proxy: {
            '/api': {
                target: 'http://localhost:5001',
                changeOrigin: true,
                rewrite: (path) => path.replace(/^\/api/, ''),
            },
        },
    },
});
