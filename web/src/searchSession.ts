import type { MaterialType, SearchResponse } from "./api/types";

const LAST_KEY = "mp:last-search";
const results = new Map<string, SearchResponse>();

export type LastSearch = {
  q: string;
  page: number;
  type: MaterialType | "";
};

export function searchKey(
  query: string,
  page: number,
  type: MaterialType | "",
): string {
  return `${query}|${page}|${type}`;
}

export function rememberSearch(
  query: string,
  page: number,
  type: MaterialType | "",
): void {
  const trimmed = query.trim();
  if (!trimmed) {
    return;
  }
  writeLast({ q: trimmed, page, type });
}

export function lastSearchHref(): string {
  return searchHref();
}

export function searchHref(type?: MaterialType | ""): string {
  const last = readLast();
  if (last === null) {
    return type ? `/?type=${encodeURIComponent(type)}` : "/";
  }
  const params = new URLSearchParams();
  params.set("q", last.q);
  if (type) {
    params.set("type", type);
  } else if (type === undefined && last.type) {
    params.set("type", last.type);
  }
  if (type === undefined && last.page > 1) {
    params.set("page", String(last.page));
  }
  return `/?${params.toString()}`;
}

export function getCachedSearch(key: string): SearchResponse | undefined {
  return results.get(key);
}

export function setCachedSearch(key: string, data: SearchResponse): void {
  results.set(key, data);
}

function readLast(): LastSearch | null {
  try {
    const raw = sessionStorage.getItem(LAST_KEY);
    if (!raw) {
      return null;
    }
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) {
      return null;
    }
    const q = "q" in parsed ? parsed.q : null;
    const page = "page" in parsed ? parsed.page : 1;
    const type = "type" in parsed ? parsed.type : "";
    if (typeof q !== "string" || !q.trim()) {
      return null;
    }
    return {
      q: q.trim(),
      page: typeof page === "number" && page >= 1 ? page : 1,
      type: typeof type === "string" ? (type as MaterialType | "") : "",
    };
  } catch {
    return null;
  }
}

function writeLast(value: LastSearch): void {
  try {
    sessionStorage.setItem(LAST_KEY, JSON.stringify(value));
  } catch {
    return;
  }
}
