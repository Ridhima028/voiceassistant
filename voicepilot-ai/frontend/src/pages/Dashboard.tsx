import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import StatusBadge from "../components/StatusBadge";
import UploadCard from "../components/UploadCard";
import { usePolling } from "../hooks/usePolling";
import { api, errorMessage, formatTime, parseServerDate } from "../services/api";
import type { LectureListItem } from "../services/api";

const CHIPS: [keyof LectureListItem, string][] = [
  ["has_summary", "Summary"],
  ["has_notes", "Notes"],
  ["has_quiz", "Quiz"],
  ["has_flashcards", "Flashcards"],
  ["has_key_concepts", "Concepts"],
  ["has_mindmap", "Mind map"],
  ["has_chapters", "Chapters"],
];

export default function Dashboard() {
  const [lectures, setLectures] = useState<LectureListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .listLectures()
      .then((list) => {
        setLectures(list); // backend already orders newest first
        setError(null);
      })
      .catch((err) => setError(errorMessage(err)));
  }, []);

  useEffect(load, [load]);

  const anyBusy = (lectures ?? []).some((l) => l.status === "queued" || l.status === "processing");
  usePolling(load, 3000, anyBusy);

  return (
    <div className="stack">
      <UploadCard />

      <section className="card">
        <h2 className="card-title">Your lectures</h2>

        {error && (
          <p className="alert alert-error" role="alert">
            {error}
          </p>
        )}

        {lectures === null && !error && (
          <p className="muted">
            <span className="spinner spinner-xs" aria-hidden="true" /> Loading…
          </p>
        )}

        {lectures?.length === 0 && (
          <p className="muted">No lectures yet. Upload or record one above to get started.</p>
        )}

        {lectures && lectures.length > 0 && (
          <ul className="lecture-list">
            {lectures.map((l) => (
              <li key={l.id}>
                <Link to={`/lectures/${l.id}`} className="lecture-row">
                  <div className="lecture-row-top">
                    <span className="lecture-title">{l.title}</span>
                    <StatusBadge status={l.status} />
                  </div>
                  <div className="lecture-meta muted small">
                    <span>{parseServerDate(l.created_at).toLocaleString()}</span>
                    {l.duration_seconds != null && <span>{formatTime(l.duration_seconds)}</span>}
                    {l.language && <span>{l.language.toUpperCase()}</span>}
                  </div>
                  {CHIPS.some(([key]) => l[key]) && (
                    <div className="chips">
                      {CHIPS.filter(([key]) => l[key]).map(([key, label]) => (
                        <span key={key} className="chip">
                          {label}
                        </span>
                      ))}
                    </div>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
