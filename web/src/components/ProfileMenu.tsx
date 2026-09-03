import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { initials, useProfile } from "../prefs";

export function ProfileMenu() {
  const { profile, ready, signOut } = useProfile();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const authPage =
    location.pathname === "/signin" || location.pathname === "/signup";

  useEffect(() => {
    if (!open) {
      return;
    }
    function onPointer(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!ready) {
    return <div className="g-account" />;
  }

  if (!profile && authPage) {
    return null;
  }

  return (
    <div className="g-account" ref={rootRef}>
      {profile ? (
        <button
          type="button"
          className="g-avatar-btn"
          aria-label={`${profile.name} account`}
          aria-expanded={open}
          onClick={() => setOpen((current) => !current)}
        >
          <span className="avatar" aria-hidden="true">
            {initials(profile.name)}
          </span>
        </button>
      ) : (
        <Link className="g-signin" to="/signin?next=/chat">
          <PersonIcon />
          Sign in
        </Link>
      )}
      {open && profile ? (
        <div className="g-account-pop" role="dialog" aria-label="Account">
          <span className="avatar lg" aria-hidden="true">
            {initials(profile.name)}
          </span>
          <p className="g-account-name">{profile.name}</p>
          <p className="g-account-plan">{profile.email}</p>
          <button
            type="button"
            className="g-account-out"
            onClick={() => {
              void signOut();
              setOpen(false);
            }}
          >
            Sign out
          </button>
        </div>
      ) : null}
    </div>
  );
}

function PersonIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="8" r="3.2" />
      <path d="M5.4 18.4c1.2-2.8 3.3-4.2 6.6-4.2s5.4 1.4 6.6 4.2" />
    </svg>
  );
}
