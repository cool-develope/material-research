import { FormEvent, useEffect, useRef, useState } from "react";

import { initials, useProfile } from "../prefs";

export function ProfileMenu() {
  const { profile, signIn, signOut } = useProfile();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(profile?.name ?? "");
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setName(profile?.name ?? "");
  }, [profile]);

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

  function submit(event: FormEvent) {
    event.preventDefault();
    signIn(name);
    setOpen(false);
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
        <button
          type="button"
          className="g-signin"
          aria-expanded={open}
          onClick={() => setOpen((current) => !current)}
        >
          <PersonIcon />
          Sign in
        </button>
      )}
      {open ? (
        <div
          className="g-account-pop"
          role="dialog"
          aria-label={profile ? "Account" : "Sign in"}
        >
          {profile ? (
            <>
              <span className="avatar lg" aria-hidden="true">
                {initials(profile.name)}
              </span>
              <p className="g-account-name">{profile.name}</p>
              <p className="g-account-plan">Deep Research</p>
              <button
                type="button"
                className="g-account-out"
                onClick={() => {
                  signOut();
                  setOpen(false);
                }}
              >
                Sign out
              </button>
            </>
          ) : (
            <form className="g-account-form" onSubmit={submit}>
              <p className="g-account-name">Sign in</p>
              <p className="g-account-plan">Use a display name for this workspace.</p>
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Your name"
                aria-label="Display name"
                autoComplete="name"
                autoFocus
              />
              <button type="submit" disabled={!name.trim()}>
                Continue
              </button>
            </form>
          )}
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
