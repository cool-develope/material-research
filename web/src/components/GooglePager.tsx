type Props = {
  page: number;
  pageCount: number;
  onPage: (page: number) => void;
};

const WINDOW = 6;
const LETTERS = ["e", "s", "e", "a", "r", "c"] as const;
const TONES = ["g-r", "g-b", "g-y", "g-r", "g-g", "g-b"] as const;

export function GooglePager({ page, pageCount, onPage }: Props) {
  if (pageCount <= 1) {
    return null;
  }
  const pages = pageWindow(page, pageCount);
  return (
    <nav className="g-pager" aria-label="Pagination">
      {page > 1 ? (
        <button
          type="button"
          className="g-step"
          onClick={() => onPage(page - 1)}
        >
          <span className="g-chevron" aria-hidden="true">
            ‹
          </span>
          Previous
        </button>
      ) : (
        <span className="g-step spacer" />
      )}
      <div className="g-word">
        <span className="g-cap g-g" aria-hidden="true">
          R
        </span>
        {LETTERS.map((letter, index) => {
          const item = pages[index];
          if (item == null) {
            return (
              <span
                key={`letter-${index}`}
                className={`g-cap ${TONES[index]}`}
                aria-hidden="true"
              >
                {letter}
              </span>
            );
          }
          const current = item === page;
          return (
            <button
              key={item}
              type="button"
              className={current ? "g-o current" : "g-o"}
              onClick={() => {
                if (!current) {
                  onPage(item);
                }
              }}
              aria-current={current ? "page" : undefined}
              aria-label={`Page ${item}`}
            >
              <span
                className={current ? "g-r" : TONES[index]}
                aria-hidden="true"
              >
                {letter}
              </span>
              <span className="g-num">{item}</span>
            </button>
          );
        })}
        <span className="g-tail" aria-hidden="true">
          <span className="g-cap g-r">h</span>
        </span>
      </div>
      {page < pageCount ? (
        <button
          type="button"
          className="g-step"
          onClick={() => onPage(page + 1)}
        >
          <span className="g-chevron" aria-hidden="true">
            ›
          </span>
          Next
        </button>
      ) : (
        <span className="g-step spacer" />
      )}
    </nav>
  );
}

function pageWindow(current: number, total: number): number[] {
  if (total <= WINDOW) {
    return range(1, total);
  }
  if (current < WINDOW) {
    return range(1, WINDOW);
  }
  return range(current, Math.min(current + WINDOW - 1, total));
}

function range(start: number, end: number): number[] {
  const out: number[] = [];
  for (let value = start; value <= end; value += 1) {
    out.push(value);
  }
  return out;
}
