import { FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { ApiError, signUp } from "../api/client";
import { AuthCard, nextPath, withNext } from "../components/AuthCard";
import { useProfile } from "../prefs";

export function SignUpPage() {
  const { profile, ready, refresh } = useProfile();
  const location = useLocation();
  const navigate = useNavigate();
  const next = nextPath(location.search);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (ready && profile) {
    return <Navigate to={next} replace />;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    if (password !== passwordConfirm) {
      setError("Passwords do not match");
      setPending(false);
      return;
    }
    try {
      await signUp({
        name,
        email,
        password,
        password_confirm: passwordConfirm,
      });
      await refresh();
      navigate(next, { replace: true });
    } catch (err: unknown) {
      setError(
        err instanceof ApiError ? err.message : "Could not create account",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthCard
      title="Create your Account"
      subtitle="Enter your name, email, and a password"
      switchLabel="Sign in instead"
      switchTo={withNext("/signin", next)}
      submitLabel="Next"
      error={error}
      pending={pending}
      onSubmit={submit}
    >
      <label className="auth-field">
        Name
        <input
          type="text"
          value={name}
          onChange={(event) => setName(event.target.value)}
          autoComplete="name"
          autoFocus
          required
        />
      </label>
      <label className="auth-field">
        Email
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          autoComplete="email"
          required
        />
      </label>
      <label className="auth-field">
        Password
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="new-password"
          minLength={8}
          required
        />
      </label>
      <label className="auth-field">
        Confirm password
        <input
          type="password"
          value={passwordConfirm}
          onChange={(event) => setPasswordConfirm(event.target.value)}
          autoComplete="new-password"
          minLength={8}
          required
        />
      </label>
    </AuthCard>
  );
}
