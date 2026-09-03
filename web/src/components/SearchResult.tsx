import { Link } from "react-router-dom";

import type { SearchHit } from "../api/types";

type Props = {
  hit: SearchHit;
  fromQuery: string;
};

export function SearchResult({ hit, fromQuery }: Props) {
  const href = `/materials/${hit.material_id}`;
  const keywords = cleanKeywords(hit.keywords);
  return (
    <article className="serp">
      <p className="serp-url">
        <span className={`serp-fav ${hit.material_type}`} aria-hidden="true">
          {(hit.title || hit.root_path || "M").slice(0, 1).toUpperCase()}
        </span>
        <span>
          <span className="serp-kind">{hit.material_type}</span>
          {hit.root_path}
        </span>
      </p>
      <h3>
        <Link to={href} state={{ query: fromQuery }}>
          {hit.title || hit.root_path}
        </Link>
      </h3>
      {hit.snippet ? (
        <p className="serp-snippet">{highlight(hit.snippet, fromQuery)}</p>
      ) : null}
      {keywords.length > 0 ? (
        <ul className="chips">
          {keywords.map((word) => (
            <li key={word}>{word}</li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}

export function cleanKeywords(words: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of words) {
    const word = raw.trim();
    const key = word.toLowerCase();
    if (
      word.length < 3 ||
      word.startsWith("-") ||
      word.endsWith("-") ||
      (word.includes("-") && word.length < 8)
    ) {
      continue;
    }
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    out.push(word);
    if (out.length >= 8) {
      break;
    }
  }
  return out;
}

function highlight(text: string, query: string) {
  const terms = query
    .split(/\s+/)
    .map((item) => item.trim())
    .filter((item) => item.length > 1);
  if (terms.length === 0) {
    return text;
  }
  const pattern = new RegExp(
    `(${terms.map(escapeRegExp).join("|")})`,
    "gi",
  );
  const parts = text.split(pattern);
  return parts.map((part, index) =>
    terms.some((term) => part.toLowerCase() === term.toLowerCase()) ? (
      <strong key={`${part}-${index}`}>{part}</strong>
    ) : (
      part
    ),
  );
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
