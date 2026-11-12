import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
const T = process.env.API_TARGET || "http://127.0.0.1:8088";
export default defineConfig({ plugins: [react()], server: { host: true, watch: { usePolling: !!process.env.API_TARGET }, proxy: { "/api": T, "/auth": T } } });
