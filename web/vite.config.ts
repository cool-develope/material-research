import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const api = "http://127.0.0.1:8000";

function spa(req: { headers: { accept?: string } }) {
  if (req.headers.accept?.includes("text/html")) {
    return "/index.html";
  }
}

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/search": api,
      "/health": api,
      "/chats": api,
      "/materials": { target: api, bypass: spa },
      "/chat": { target: api, bypass: spa },
    },
  },
});
