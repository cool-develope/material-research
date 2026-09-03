import { useTheme } from "../prefs";

type Props = {
  className?: string;
};

export function ThemeToggle({ className = "theme-icon" }: Props) {
  const { theme, toggleTheme } = useTheme();
  const dark = theme === "dark";
  return (
    <button
      type="button"
      className={className}
      onClick={toggleTheme}
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      title={dark ? "Light theme" : "Dark theme"}
    >
      {dark ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        stroke="none"
        d="M20 14.4A8.2 8.2 0 0 1 9.6 4 7.2 7.2 0 1 0 20 14.4z"
      />
    </svg>
  );
}

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="4.2" />
      <path d="M12 3.2v1.8M12 19v1.8M4.9 4.9l1.3 1.3M17.8 17.8l1.3 1.3M3.2 12h1.8M19 12h1.8M4.9 19.1l1.3-1.3M17.8 6.2l1.3-1.3" />
    </svg>
  );
}
