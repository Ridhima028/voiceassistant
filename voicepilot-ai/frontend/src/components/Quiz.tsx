import { useState } from "react";
import type { QuizQuestion } from "../services/api";

export default function Quiz({ questions }: { questions: QuizQuestion[] }) {
  // question index -> chosen option index. Answering locks the question.
  const [answers, setAnswers] = useState<Record<number, number>>({});

  const answered = Object.keys(answers).length;
  const correct = questions.filter((q, i) => answers[i] === q.correct_index).length;

  return (
    <div className="stack">
      <div className="quiz-bar">
        <span className="quiz-score" aria-live="polite">
          Score: <strong>{correct}</strong> / {answered}
          <span className="muted"> ({questions.length} questions)</span>
        </span>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => setAnswers({})}
          disabled={answered === 0}
        >
          Reset
        </button>
      </div>

      {questions.map((q, qi) => {
        const picked = answers[qi];
        const locked = picked !== undefined;
        return (
          <div key={qi} className="card quiz-card">
            <div className="quiz-head">
              <span className="muted small">Question {qi + 1}</span>
              <span className={`tag tag-${q.difficulty}`}>{q.difficulty}</span>
            </div>
            <p className="quiz-question">{q.question}</p>
            <div className="quiz-options">
              {q.options.map((opt, oi) => {
                let state = "";
                if (locked && oi === q.correct_index) state = " correct";
                else if (locked && oi === picked) state = " wrong";
                return (
                  <button
                    key={oi}
                    type="button"
                    className={`quiz-option${state}`}
                    disabled={locked}
                    aria-pressed={picked === oi}
                    onClick={() => setAnswers((a) => ({ ...a, [qi]: oi }))}
                  >
                    <span className="quiz-letter">{String.fromCharCode(65 + oi)}</span>
                    {opt}
                  </button>
                );
              })}
            </div>
            {locked && (
              <p className={`quiz-explanation ${picked === q.correct_index ? "ok" : "bad"}`}>
                <strong>{picked === q.correct_index ? "Correct. " : "Not quite. "}</strong>
                {q.explanation}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
