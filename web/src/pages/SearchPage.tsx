import { FormEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ApiError, searchMaterials } from "../api/client";
import type { MaterialType, SearchResponse } from "../api/types";
import { MaterialCard } from "../components/MaterialCard";

const TYPES: Array<MaterialType | ""> = [
  "",
  "project",
  "document",
  "dataset",
  "code",
  "unknown",
];

export function SearchPage() {
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  const page = Math.max(1, Number(params.get("page") ?? "1") || 1);
  const type = (params.get("type") ?? "") as MaterialType | "";
  const [draft, setDraft] = useState(query);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SearchResponse | null>(null);

  const requestKey = useMemo(
    () => `${query}|${page}|${type}`,
    [query, page, type],
  );

  useEffect(() => {
    setDraft(query);
  }, [query]);

  useEffect(() => {
    if (!query.trim()) {
      setResult(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    searchMaterials({
      query,
      page,
      material_type: type,
    })
      .then((data) => {
        if (!cancelled) {
          setResult(data);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setResult(null);
          setError(err instanceof ApiError ? err.message : "Search failed");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [requestKey, query, page, type]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const next = draft.trim();
    if (!next) {
      return;
    }
    const nextParams = new URLSearchParams();
    nextParams.set("q", next);
    nextParams.set("page", "1");
    if (type) {
      nextParams.set("type", type);
    }
    setParams(nextParams);
  }

  function setPage(next: number) {
    const nextParams = new URLSearchParams(params);
    nextParams.set("page", String(next));
    setParams(nextParams);
  }

  function setType(next: MaterialType | "") {
    const nextParams = new URLSearchParams(params);
    nextParams.set("page", "1");
    if (next) {
      nextParams.set("type", next);
    } else {
      nextParams.delete("type");
    }
    setParams(nextParams);
  }

  return (
    <section className="search">
      <h1>Search materials</h1>
      <p className="lede">
        Hop-1 material cards. Citations stay in Deep Research.
      </p>
      <form className="search-form" onSubmit={submit}>
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Search indexed materials"
          aria-label="Search query"
          autoFocus
        />
        <select
          value={type}
          onChange={(event) => setType(event.target.value as MaterialType | "")}
          aria-label="Material type"
        >
          {TYPES.map((item) => (
            <option key={item || "all"} value={item}>
              {item || "all types"}
            </option>
          ))}
        </select>
        <button type="submit">Search</button>
      </form>
      {loading ? <p className="status">Searching…</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {!loading && query && result && result.results.length === 0 ? (
        <p className="status">No materials matched.</p>
      ) : null}
      <ol className="results">
        {(result?.results ?? []).map((hit) => (
          <li key={hit.material_id}>
            <MaterialCard hit={hit} />
          </li>
        ))}
      </ol>
      {result && (page > 1 || result.has_more) ? (
        <div className="pager">
          <button
            type="button"
            disabled={page <= 1 || loading}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </button>
          <span>Page {result.page}</span>
          <button
            type="button"
            disabled={!result.has_more || loading}
            onClick={() => setPage(page + 1)}
          >
            Next
          </button>
        </div>
      ) : null}
    </section>
  );
}
