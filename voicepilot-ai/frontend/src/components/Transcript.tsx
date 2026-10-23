import { useState } from "react";
import { formatTime } from "../services/api";
import type { Lecture } from "../services/api";

interface Props {
  lecture: Lecture;
  onSeek: (seconds: number) => void;
}

export default function Transcript({ lecture, onSeek }: Props) {
  const [plain, setPlain] = useState(false);
  // Semantic segments read better; fall back to Whisper's raw ones.
  const segments = lecture.processed_segments?.length ? lecture.processed_segments : lecture.segments ?? [];

  if (!lecture.transcript && segments.length === 0) {
    return <p className="muted">No transcript available.</p>;
  }

  return (
    <div className="stack">
      <div className="quiz-bar">
        <span className="muted small">
          {plain
            ? "Full text"
            : `${segments.length} segments${lecture.processed_segments?.length ? " · grouped by meaning" : ""}`}
        </span>
        <label className="toggle">
          <input type="checkbox" checked={plain} onChange={(e) => setPlain(e.target.checked)} />
          Plain text
        </label>
      </div>

      {plain || segments.length === 0 ? (
        <p className="transcript-plain">{lecture.transcript}</p>
      ) : (
        <ul className="segments">
          {segments.map((seg, i) => (
            <li key={i} className="segment">
              <button
                type="button"
                className="timestamp"
                onClick={() => onSeek(seg.start)}
                title="Play from here"
              >
                {formatTime(seg.start)}
              </button>
              <p>{seg.text}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
