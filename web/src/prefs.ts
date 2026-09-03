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

export type ThemeName = "light" | "dark";

export type Profile = {
  name: string;
};

const THEME_KEY = "mp.theme";
const PROFILE_KEY = "mp.profile";

type ThemeContextValue = {
  theme: ThemeName;
  toggleTheme: () => void;
};

type ProfileContextValue = {
  profile: Profile | null;
  signIn: (name: string) => void;
  signOut: () => void;
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

function readProfile(): Profile | null {
  try {
    const raw = localStorage.getItem(PROFILE_KEY);
    if (!raw) {
      return null;
    }
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      "name" in parsed &&
      typeof parsed.name === "string" &&
      parsed.name.trim()
    ) {
      return { name: parsed.name.trim() };
    }
  } catch {
    /* ignore */
  }
  return null;
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
  const [profile, setProfile] = useState<Profile | null>(readProfile);
  const signIn = useCallback((name: string) => {
    const next = { name: name.trim() };
    if (!next.name) {
      return;
    }
    localStorage.setItem(PROFILE_KEY, JSON.stringify(next));
    setProfile(next);
  }, []);
  const signOut = useCallback(() => {
    localStorage.removeItem(PROFILE_KEY);
    setProfile(null);
  }, []);
  const value = useMemo(
    () => ({ profile, signIn, signOut }),
    [profile, signIn, signOut],
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
