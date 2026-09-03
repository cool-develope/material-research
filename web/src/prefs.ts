import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { loadMe, signOut as apiSignOut } from "./api/client";
import type { User } from "./api/types";

export type ThemeName = "light" | "dark";

export type Profile = User;

const THEME_KEY = "mp.theme";

type ThemeContextValue = {
  theme: ThemeName;
  toggleTheme: () => void;
};

type ProfileContextValue = {
  profile: Profile | null;
  ready: boolean;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);
const ProfileContext = createContext<ProfileContextValue | null>(null);

export function readTheme(): ThemeName {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === "light" || stored === "dark") {
      return stored;
    }
  } catch {
    /* ignore */
  }
  if (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  ) {
    return "dark";
  }
  return "light";
}

export function applyTheme(theme: ThemeName) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<ThemeName>(readTheme);
  useEffect(() => {
    localStorage.setItem(THEME_KEY, theme);
    applyTheme(theme);
  }, [theme]);
  const toggleTheme = useCallback(() => {
    setTheme((current) => (current === "light" ? "dark" : "light"));
  }, []);
  const value = useMemo(
    () => ({ theme, toggleTheme }),
    [theme, toggleTheme],
  );
  return createElement(ThemeContext.Provider, { value }, children);
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme needs ThemeProvider");
  }
  return ctx;
}

export function ProfileProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [ready, setReady] = useState(false);
  const refresh = useCallback(async () => {
    try {
      setProfile(await loadMe());
    } catch {
      setProfile(null);
    }
  }, []);
  useEffect(() => {
    void refresh().finally(() => setReady(true));
  }, [refresh]);
  const signOut = useCallback(async () => {
    try {
      await apiSignOut();
    } catch {
      /* still clear local session */
    }
    setProfile(null);
  }, []);
  const value = useMemo(
    () => ({ profile, ready, refresh, signOut }),
    [profile, ready, refresh, signOut],
  );
  return createElement(ProfileContext.Provider, { value }, children);
}

export function useProfile(): ProfileContextValue {
  const ctx = useContext(ProfileContext);
  if (!ctx) {
    throw new Error("useProfile needs ProfileProvider");
  }
  return ctx;
}

export function initials(name: string): string {
  const parts = name.split(/\s+/).filter(Boolean);
  const first = parts[0];
  const second = parts[1];
  if (!first) {
    return "?";
  }
  if (!second) {
    return first.slice(0, 2).toUpperCase();
  }
  return `${first[0]}${second[0]}`.toUpperCase();
}
