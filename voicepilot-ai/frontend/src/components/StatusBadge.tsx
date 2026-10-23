import type { LectureStatus } from "../services/api";

const LABELS: Record<LectureStatus, string> = {
  queued: "Queued",
  processing: "Transcribing…",
  completed: "Ready",
  failed: "Failed",
};

export default function StatusBadge({ status }: { status: LectureStatus }) {
  const busy = status === "queued" || status === "processing";
  return (
    <span className={`badge badge-${status}`}>
      {busy && <span className="spinner spinner-xs" aria-hidden="true" />}
      {LABELS[status] ?? status}
    </span>
  );
}
