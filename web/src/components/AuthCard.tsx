import { FormEvent, ReactNode } from "react";
import { Link } from "react-router-dom";

import { BrandMark } from "./BrandMark";

type Props = {
  title: string;
  subtitle: string;
  switchLabel: string;
  switchTo: string;
  submitLabel: string;
  error: string | null;
  pending: boolean;
  onSubmit: (event: FormEvent) => void;
  children: ReactNode;
};

export function AuthCard({
  title,
  subtitle,
  switchLabel,
  switchTo,
  submitLabel,
  error,
  pending,
  onSubmit,
  children,
}: Props) {
  return (
    <main className="auth-page">
      <form className="auth-card" onSubmit={onSubmit}>
        <BrandMark compact to="/" />
        <h1>{title}</h1>
        <p className="auth-sub">{subtitle}</p>
        {children}
        {error ? <p className="error">{error}</p> : null}
        <div className="auth-actions">
          <Link className="auth-switch" to={switchTo}>
            {switchLabel}
          </Link>
          <button type="submit" className="auth-primary" disabled={pending}>
            {submitLabel}
          </button>
        </div>
      </form>
    </main>
  );
}

export function nextPath(search: string): string {
  const raw = new URLSearchParams(search).get("next");
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) {
    return "/chat";
  }
  if (raw.startsWith("/signin") || raw.startsWith("/signup")) {
    return "/chat";
  }
  return raw;
}

export function withNext(path: string, next: string): string {
  if (!next || next === "/chat") {
    return path;
  }
  return `${path}?next=${encodeURIComponent(next)}`;
}
