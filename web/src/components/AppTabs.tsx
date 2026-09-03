import { Link } from "react-router-dom";

import type { MaterialType } from "../api/types";
import { useProfile } from "../prefs";
import { searchHref } from "../searchSession";

const TYPES: Array<MaterialType | ""> = [
  "",
  "document",
  "project",
  "dataset",
  "code",
];

type Props = {
  active: "research" | MaterialType | "";
  onType?: (type: MaterialType | "") => void;
  modes?: "all" | "main";
};

export function AppTabs({
  active,
  onType,
  modes = "all",
}: Props) {
  const types: Array<MaterialType | ""> =
    modes === "main" ? [""] : TYPES;
  const { profile } = useProfile();
  const researchTo = profile ? "/chat" : "/signin?next=/chat";
  return (
    <nav className="g-tabs" aria-label="Mode">
      <Link
        className={active === "research" ? "g-tab on research" : "g-tab research"}
        to={researchTo}
      >
        <Sparkle />
        Research
      </Link>
      {types.map((item) => {
        const label = item || "All";
        const on = active === item;
        if (onType) {
          return (
            <button
              key={label}
              type="button"
              className={on ? "g-tab on" : "g-tab"}
              onClick={() => onType(item)}
            >
              {label}
            </button>
          );
        }
        return (
          <Link
            key={label}
            className={on ? "g-tab on" : "g-tab"}
            to={searchHref(item)}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

function Sparkle() {
  return (
    <svg className="sparkle" viewBox="0 0 16 16" aria-hidden="true">
      <path
        fill="url(#sparkle-fill)"
        d="M8 1.1c.35 2.6 1.55 3.8 4.15 4.15C9.55 6.6 8.35 7.8 8 10.4 7.65 7.8 6.45 6.6 3.85 5.25 6.45 4.9 7.65 3.7 8 1.1z"
      />
      <path
        fill="url(#sparkle-fill)"
        d="M12.6 9.4c.18 1.15.7 1.67 1.85 1.85-.1.18-.7.7-1.85 1.85-.18-1.15-.7-1.67-1.85-1.85 1.15-.18 1.67-.7 1.85-1.85z"
      />
      <defs>
        <linearGradient id="sparkle-fill" x1="1" y1="2" x2="15" y2="14">
          <stop stopColor="#4285f4" />
          <stop offset="0.45" stopColor="#ea4335" />
          <stop offset="0.7" stopColor="#fbbc05" />
          <stop offset="1" stopColor="#34a853" />
        </linearGradient>
      </defs>
    </svg>
  );
}
