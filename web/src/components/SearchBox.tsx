import { FormEvent } from "react";

type Props = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
  placeholder: string;
  autoFocus?: boolean;
};

export function SearchBox({
  value,
  onChange,
  onSubmit,
  placeholder,
  autoFocus = false,
}: Props) {
  return (
    <form className="omnibox" onSubmit={onSubmit}>
      <span className="omni-icon" aria-hidden="true">
        <SearchIcon />
      </span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label="Search query"
        autoFocus={autoFocus}
      />
    </form>
  );
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24">
      <circle cx="11" cy="11" r="6.2" />
      <path d="M16 16.4 20.2 20.6" />
    </svg>
  );
}
