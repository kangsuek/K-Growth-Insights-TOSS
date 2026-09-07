import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // K-Growth-Insights(V2)의 5173과 겹치지 않게 분리.
    port: 5273,
  },
});
