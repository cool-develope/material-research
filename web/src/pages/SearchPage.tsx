import { FormEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ApiError, searchMaterials } from "../api/client";
import type { MaterialType, SearchResponse } from "../api/types";
import { AppTabs } from "../components/AppTabs";
import { BrandMark } from "../components/BrandMark";
import { GooglePager } from "../components/GooglePager";
import { SearchBox } from "../components/SearchBox";
import { SearchResult } from "../components/SearchResult";
import {
  getCachedSearch,
  rememberSearch,
  searchKey,
  setCachedSearch,
} from "../searchSession";

export function SearchPage() {
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  const page = Math.max(1, Number(params.get("page") ?? "1") || 1);
  const type = (params.get("type") ?? "") as MaterialType | "";
  const requestKey = useMemo(
    () => searchKey(query, page, type),
    [query, page, type],
  );
  const [draft, setDraft] = useState(query);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SearchResponse | null>(
    () => getCachedSearch(requestKey) ?? null,
  );

  useEffect(() => {
    setDraft(query);
  }, [query]);

  useEffect(() => {
    if (!query.trim()) {
      setResult(null);
      setError(null);
      setLoading(false);
      return;
    }
    rememberSearch(query, page, type);
    const cached = getCachedSearch(requestKey);
    if (cached) {
      setResult(cached);
      setError(null);
      setLoading(false);
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
          setCachedSearch(requestKey, data);
          rememberSearch(query, page, type);
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

  function applyQuery(next: string, nextType: MaterialType | "" = type) {
    const trimmed = next.trim();
    if (!trimmed) {
      return;
    }
    rememberSearch(trimmed, 1, nextType);
    const nextParams = new URLSearchParams();
    nextParams.set("q", trimmed);
    nextParams.set("page", "1");
    if (nextType) {
      nextParams.set("type", nextType);
    }
    setParams(nextParams);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    applyQuery(draft);
  }

  function setPage(next: number) {
    rememberSearch(query, next, type);
    const nextParams = new URLSearchParams(params);
    nextParams.set("page", String(next));
    setParams(nextParams);
  }

  const home = !query.trim();
  const count = result?.results.length ?? 0;
  const total = result?.total ?? count;
  const pageCount = result?.page_count ?? 0;
  const box = (
    <SearchBox
      value={draft}
      onChange={setDraft}
      onSubmit={submit}
      placeholder={
        home ? "Search papers, code, and datasets" : "Search materials"
      }
      autoFocus={home}
    />
  );

  return (
    <section className={home ? "google home" : "google results"}>
      {home ? (
        <div className="google-home">
          <BrandMark />
          {box}
          <AppTabs active="" modes="main" />
        </div>
      ) : (
        <>
          <header className="g-chrome">
            <BrandMark compact />
            <div className="g-chrome-main">
              {box}
              <AppTabs
                active={type}
                onType={(next) => applyQuery(query, next)}
              />
            </div>
          </header>
          <div className="g-body">
            {loading ? <p className="status">Searching…</p> : null}
            {error ? <p className="error">{error}</p> : null}
            {!loading && result && count === 0 ? (
              <p className="status">
                No materials matched <strong>{query}</strong>.
              </p>
            ) : null}
            {!loading && result && count > 0 ? (
              <p className="stats">
                {total > count ? "About " : ""}
                {total} result{total === 1 ? "" : "s"}
              </p>
            ) : null}
            <ol className="serp-list">
              {(result?.results ?? []).map((hit) => (
                <li key={hit.material_id}>
                  <SearchResult hit={hit} fromQuery={query} />
                </li>
              ))}
            </ol>
            {!loading && result ? (
              <GooglePager
                page={page}
                pageCount={pageCount}
                onPage={setPage}
              />
            ) : null}
          </div>
        </>
      )}
    </section>
  );
}
