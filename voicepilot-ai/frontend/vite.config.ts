import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  // Prefix "" loads every variable, including the real process environment,
  // so API_TARGET set by docker compose is picked up here.
  const env = loadEnv(mode, ".", "");
  const target = env.API_TARGET || "http://localhost:8000";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      host: true,
      // The browser only ever talks to Vite; Vite forwards /api/* to FastAPI
      // server-side, so there is no cross-origin request and no CORS.
      proxy: {
        "/api": {
          target,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
      },
    },
  };
});
