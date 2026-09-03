import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { ChatPage } from "./pages/ChatPage";
import { MaterialPage } from "./pages/MaterialPage";
import { SearchPage } from "./pages/SearchPage";
import { ProfileProvider, ThemeProvider } from "./prefs";
import "./index.css";

const root = document.getElementById("root");
if (!root) {
  throw new Error("root element missing");
}

createRoot(root).render(
  <StrictMode>
    <ThemeProvider>
      <ProfileProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<SearchPage />} />
            <Route path="/materials/:materialId" element={<MaterialPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/chat/:threadId" element={<ChatPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
      </ProfileProvider>
    </ThemeProvider>
  </StrictMode>,
);
