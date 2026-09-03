import { FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { ApiError, signIn } from "../api/client";
import { AuthCard, nextPath, withNext } from "../components/AuthCard";
import { useProfile } from "../prefs";

export function SignInPage() {
  const { profile, ready, refresh } = useProfile();
  const location = useLocation();
  const navigate = useNavigate();
  const next = nextPath(location.search);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (ready && profile) {
    return <Navigate to={next} replace />;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await signIn({ email, password });
      await refresh();
      navigate(next, { replace: true });
    } catch (err: unknown) {
      setError(
        err instanceof ApiError ? err.message : "Could not sign in",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthCard
      title="Sign in"
      subtitle="Use your Deep Research Account"
      switchLabel="Create account"
      switchTo={withNext("/signup", next)}
      submitLabel="Next"
      error={error}
      pending={pending}
      onSubmit={submit}
    >
      <label className="auth-field">
        Email
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          autoComplete="email"
          autoFocus
          required
        />
      </label>
      <label className="auth-field">
        Password
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          required
        />
      </label>
    </AuthCard>
  );
}
