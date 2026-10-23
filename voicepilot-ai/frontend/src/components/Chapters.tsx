import { formatTime } from "../services/api";
import type { Chapter } from "../services/api";

interface Props {
  chapters: Chapter[];
  onSeek: (seconds: number) => void;
}

export default function Chapters({ chapters, onSeek }: Props) {
  return (
    <ol className="chapter-list">
      {chapters.map((ch, i) => (
        <li key={i}>
          <button type="button" className="chapter" onClick={() => onSeek(ch.start_seconds)}>
            <span className="timestamp">{formatTime(ch.start_seconds)}</span>
            <span className="chapter-body">
              <span className="chapter-title">{ch.title}</span>
              {ch.summary && <span className="muted small">{ch.summary}</span>}
            </span>
          </button>
        </li>
      ))}
    </ol>
  );
}
