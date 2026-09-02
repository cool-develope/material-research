import type { SearchHit } from "../api/types";

type Props = {
  hit: SearchHit;
};

export function MaterialCard({ hit }: Props) {
  return (
    <article className="card">
      <div className="card-meta">
        <span className="kind">{hit.material_type}</span>
        <span className="score">{hit.score.toFixed(3)}</span>
      </div>
      <h2>{hit.title || hit.root_path}</h2>
      <p className="path">{hit.root_path}</p>
      {hit.siblings.length > 0 ? (
        <p className="siblings">Siblings: {hit.siblings.join(", ")}</p>
      ) : null}
    </article>
  );
}
