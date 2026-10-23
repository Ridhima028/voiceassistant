import { useState } from "react";
import type { Flashcard } from "../services/api";

export default function Flashcards({ cards }: { cards: Flashcard[] }) {
  const [flipped, setFlipped] = useState<Set<number>>(new Set());
  const allFlipped = flipped.size === cards.length && cards.length > 0;

  function toggle(i: number) {
    setFlipped((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  }

  return (
    <div className="stack">
      <div className="quiz-bar">
        <span className="muted small">Click a card to flip it.</span>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => setFlipped(allFlipped ? new Set() : new Set(cards.map((_, i) => i)))}
        >
          {allFlipped ? "Show fronts" : "Flip all"}
        </button>
      </div>

      <div className="flash-grid">
        {cards.map((card, i) => {
          const isFlipped = flipped.has(i);
          return (
            <button
              key={i}
              type="button"
              className={`flashcard${isFlipped ? " flipped" : ""}`}
              onClick={() => toggle(i)}
              aria-pressed={isFlipped}
              aria-label={isFlipped ? `Answer: ${card.back}` : `Question: ${card.front}`}
            >
              <span className="flash-inner">
                <span className="flash-face flash-front" aria-hidden={isFlipped}>
                  <span className="flash-topic">{card.topic}</span>
                  <span className="flash-text">{card.front}</span>
                  {card.hint && <span className="flash-hint">Hint: {card.hint}</span>}
                </span>
                <span className="flash-face flash-back" aria-hidden={!isFlipped}>
                  <span className="flash-topic">{card.topic}</span>
                  <span className="flash-text">{card.back}</span>
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
