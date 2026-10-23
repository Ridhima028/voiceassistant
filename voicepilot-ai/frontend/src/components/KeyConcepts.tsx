import type { KeyConcept } from "../services/api";

export default function KeyConcepts({ concepts }: { concepts: KeyConcept[] }) {
  return (
    <div className="concept-grid">
      {concepts.map((c, i) => (
        <article key={i} className={`card concept concept-${c.importance}`}>
          <div className="concept-head">
            <h3>{c.term}</h3>
            <span className={`tag tag-${c.importance}`}>{c.importance}</span>
          </div>
          <p>{c.definition}</p>
          {c.related_terms.length > 0 && (
            <div className="chips">
              {c.related_terms.map((t) => (
                <span key={t} className="chip">
                  {t}
                </span>
              ))}
            </div>
          )}
        </article>
      ))}
    </div>
  );
}
