import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError, loadMaterial } from "../api/client";
import { AppTabs } from "../components/AppTabs";
import { BrandMark } from "../components/BrandMark";
import { cleanKeywords } from "../components/SearchResult";
import type { MaterialDetail } from "../api/types";
import { lastSearchHref } from "../searchSession";

export function MaterialPage() {
  const { materialId } = useParams();
  const back = lastSearchHref();
  const [detail, setDetail] = useState<MaterialDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!materialId) {
      return;
    }
    let cancelled = false;
    loadMaterial(materialId)
      .then((data) => {
        if (!cancelled) {
          setDetail(data);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Material not found");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [materialId]);

  return (
    <section className="google results">
      <header className="g-chrome">
        <BrandMark compact />
        <div className="g-chrome-main">
          <AppTabs active="" />
        </div>
      </header>
      <div className="g-body detail">
        <p className="crumb">
          <Link to={back}>All</Link>
          {detail ? <span> / {detail.title}</span> : null}
        </p>
      {error ? <p className="error">{error}</p> : null}
      {!detail && !error ? <p className="status">Loading…</p> : null}
      {detail ? (
        <>
          <p className="serp-url">
            <span className={`badge ${detail.material_type}`}>
              {detail.material_type}
            </span>
            {detail.root_path}
          </p>
          <h1>{detail.title}</h1>
          {detail.purpose ? <p className="purpose">{detail.purpose}</p> : null}
          {detail.summary ? <p className="lede">{detail.summary}</p> : null}
          <TagList label="Keywords" items={cleanKeywords(detail.keywords)} />
          <TagList label="Topics" items={cleanKeywords(detail.topics)} />
          <TagList
            label="Technologies"
            items={cleanKeywords(detail.technologies)}
          />
          {detail.units.length > 0 ? (
            <div className="unit-block">
              <h2>Passages</h2>
              <p className="status">
                {detail.units.length} locators · bodies stay in the index
              </p>
              <ul className="units">
                {detail.units.map((unit) => (
                  <li key={`${unit.unit_type}-${unit.citation}`}>
                    <span className="serp-kind">{unit.unit_type || "unit"}</span>
                    {unit.citation || detail.root_path}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      ) : null}
      </div>
    </section>
  );
}

function TagList({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) {
    return null;
  }
  return (
    <div className="tag-block">
      <h2>{label}</h2>
      <ul className="chips">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
