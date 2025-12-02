import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
// Use a function to access mode for loading .env files if needed, and configure the proxy.
export default defineConfig(({ mode }) => {
    // Load environment variables from .env file (optional, but good practice)
    const env = loadEnv(mode, process.cwd(), '');

    // Define the backend URL, prioritizing the environment variable or defaulting to localhost:8000
    const API_TARGET = env.VITE_API_URL || 'http://127.0.0.1:8000';

    console.log(`Vite running in ${mode} mode. Proxying /api requests to: ${API_TARGET}`);

    return {
        plugins: [react()],
        server: {
            // Set the development server to run on the standard frontend port 3000
            port: 3000, 
            proxy: {
                // When the frontend requests '/api/v1/markov/matrix/SPY', it will be redirected to:
                // 'http://127.0.0.1:8000/api/v1/markov/matrix/SPY'
                '/api': {
                    target: API_TARGET,
                    changeOrigin: true,
                    secure: false,
                },
            },
        },
        // Ensure the build output is placed in the project root if needed, otherwise default is 'dist'
        // build: {
        //     outDir: '../dist', 
        //     emptyOutDir: true,
        // },
    };
});
