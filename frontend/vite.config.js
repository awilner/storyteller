import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Allow access from any host (e.g. other devices on the network)
    allowedHosts: true,
    hmr: {
      // Ensure HMR WebSocket connects directly to the Vite dev server,
      // even when the page is accessed through a proxy or different host.
      protocol: "ws",
      host: "localhost",
      port: 5173,
    },
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      // Django Channels WebSocket (permission notifications, presence)
      "/ws": {
        target: "ws://127.0.0.1:8000",
        ws: true,
      },
      // HocusPocus WebSocket (collaborative editing via Yjs)
      "/yjs": {
        target: "ws://127.0.0.1:1234",
        ws: true,
      },
    },
  },
});
