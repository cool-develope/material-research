import { Link } from "react-router-dom";

const LETTERS = [
  ["D", "g-b"],
  ["e", "g-r"],
  ["e", "g-y"],
  ["p", "g-b"],
  ["\u00a0", ""],
  ["R", "g-g"],
  ["e", "g-r"],
  ["s", "g-b"],
  ["e", "g-y"],
  ["a", "g-r"],
  ["r", "g-g"],
  ["c", "g-b"],
  ["h", "g-r"],
] as const;

type Props = {
  compact?: boolean;
  glyph?: boolean;
  to?: string | false;
};

export function BrandMark({
  compact = false,
  glyph = false,
  to = "/",
}: Props) {
  const word = glyph ? (
    <svg
      className="logo-glyph"
      viewBox="0 0 48 48"
      aria-label="Deep Research"
    >
      <path
        className="g-b"
        d="M13 7h13.5C35.4 7 43 15 43 24s-7.6 17-16.5 17H13V7zm9.5 8.5v17h4c5.2 0 9-3.7 9-8.5s-3.8-8.5-9-8.5h-4z"
      />
    </svg>
  ) : (
    <span
      className={compact ? "logo-sm" : "logo"}
      aria-label="Deep Research"
    >
      {LETTERS.map(([letter, tone], index) => (
        <span key={`${letter}-${index}`} className={tone}>
          {letter}
        </span>
      ))}
    </span>
  );
  if (!compact && !glyph) {
    return <h1 className="logo-wrap">{word}</h1>;
  }
  if (to === false) {
    return word;
  }
  return (
    <Link to={to} className={glyph ? "logo-glyph-link" : "logo-link"}>
      {word}
    </Link>
  );
}
