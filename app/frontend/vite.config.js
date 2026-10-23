import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist" },
  // VITE_* (domyślnie) + DISCORD_WEBHOOK_URL (webhook formularza kontaktowego)
  envPrefix: ["VITE_", "DISCORD_WEBHOOK_URL"],
});
