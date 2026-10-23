import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Chapters from "../components/Chapters";
import Flashcards from "../components/Flashcards";
import KeyConcepts from "../components/KeyConcepts";
import Markdown from "../components/Markdown";
import MermaidDiagram from "../components/MermaidDiagram";
import Quiz from "../components/Quiz";
import StatusBadge from "../components/StatusBadge";
import Transcript from "../components/Transcript";
import { usePolling } from "../hooks/usePolling";
import { api, errorMessage, formatTime } from "../services/api";
import type { AiField, Lecture, StudyPackStatus } from "../services/api";

type Tab = "transcript" | AiField;

const TABS: { id: Tab; label: string }[] = [
  { id: "transcript", label: "Transcript" },
  { id: "summary", label: "Summary" },
  { id: "notes", label: "Notes" },
  { id: "quiz", label: "Quiz" },
  { id: "flashcards", label: "Flashcards" },
  { id: "key_concepts", label: "Key concepts" },
  { id: "mindmap", label: "Mind map" },
  { id: "chapters", label: "Chapters" },
];

const FIELD_LABEL: Record<string, string> = Object.fromEntries(TABS.map((t) => [t.id, t.label]));

const SEMANTIC_WARNING = "Semantic segmentation skipped";
const QUEUED_HINT_AFTER_MS = 30_000;

function hasContent(lecture: Lecture, field: AiField): boolean {
  const value = lecture[field];
  return Array.isArray(value) ? value.length > 0 : Boolean(value);
}

export default function LecturePage() {
  const { id: idParam } = useParams();
  const id = Number(idParam);
  const navigate = useNavigate();

  const [lecture, setLecture] = useState<Lecture | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("transcript");

  const [audioSrc, setAudioSrc] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const audioRetried = useRef(false);

  const [busyField, setBusyField] = useState<Record<string, boolean>>({});
  const [fieldError, setFieldError] = useState<Record<string, string>>({});
  const [packBusy, setPackBusy] = useState(false);
  const [packResult, setPackResult] = useState<StudyPackStatus | null>(null);
  const [retrying, setRetrying] = useState(false);

  const queuedSince = useRef<number | null>(null);

  const load = useCallback(() => {
    api
      .getLecture(id)
      .then((l) => {
        setLecture(l);
        setLoadError(null);
      })
      .catch((err) => setLoadError(errorMessage(err)));
  }, [id]);

  const loadAudio = useCallback(() => {
    // The player is optional: if storage is down or the object is missing,
    // just don't show it.
    api
      .audioUrl(id)
      .then((a) => setAudioSrc(a.url))
      .catch(() => setAudioSrc(null));
  }, [id]);

  useEffect(() => {
    setLecture(null);
    setPackResult(null);
    audioRetried.current = false;
    load();
    loadAudio();
  }, [load, loadAudio]);

  const inFlight = lecture?.status === "queued" || lecture?.status === "processing";
  usePolling(load, 3000, inFlight);

  if (lecture?.status === "queued") queuedSince.current ??= Date.now();
  else queuedSince.current = null;
  const stuckInQueue =
    queuedSince.current !== null && Date.now() - queuedSince.current > QUEUED_HINT_AFTER_MS;

  function seek(seconds: number) {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = seconds;
    void audio.play().catch(() => {
      /* autoplay can be refused; the position is still set */
    });
  }

  async function generate(field: AiField, regenerate: boolean) {
    setBusyField((b) => ({ ...b, [field]: true }));
    setFieldError((e) => ({ ...e, [field]: "" }));
    try {
      setLecture(await api.generate(id, field, regenerate));
    } catch (err) {
      // 502 carries the backend's explanation (model error, rate limit...).
      setFieldError((e) => ({ ...e, [field]: errorMessage(err) }));
    } finally {
      setBusyField((b) => ({ ...b, [field]: false }));
    }
  }

  async function generateEverything() {
    setPackBusy(true);
    setActionError(null);
    setPackResult(null);
    // Old per-tab errors are about to be superseded by this run's results.
    setFieldError({});
    try {
      const result = await api.studyPack(id);
      setPackResult(result);
      // Show any failure on its own tab too, not only in the summary above.
      setFieldError(result.failed);
      load();
    } catch (err) {
      setActionError(errorMessage(err));
    } finally {
      setPackBusy(false);
    }
  }

  async function exportPack() {
    setActionError(null);
    // Open the tab synchronously inside the click, or popup blockers kill it.
    const win = window.open("", "_blank");
    if (win) win.document.title = "Preparing export…";
    try {
      const html = await api.exportHtml(id);
      const url = URL.createObjectURL(new Blob([html], { type: "text/html" }));
      if (win) win.location.href = url;
      else window.location.href = url;
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      win?.close();
      setActionError(errorMessage(err));
    }
  }

  async function remove() {
    if (!lecture || !window.confirm(`Delete “${lecture.title}”? This also deletes its audio.`)) return;
    setActionError(null);
    try {
      await api.remove(id);
      navigate("/");
    } catch (err) {
      setActionError(errorMessage(err));
    }
  }

  async function retry() {
    setRetrying(true);
    setActionError(null);
    try {
      setLecture(await api.retry(id));
    } catch (err) {
      setActionError(errorMessage(err));
    } finally {
      setRetrying(false);
    }
  }

  if (loadError && !lecture) {
    return (
      <div className="stack">
        <Link to="/" className="back-link">
          ← All lectures
        </Link>
        <p className="alert alert-error" role="alert">
          {loadError}
        </p>
      </div>
    );
  }

  if (!lecture) {
    return (
      <p className="muted">
        <span className="spinner spinner-xs" aria-hidden="true" /> Loading lecture…
      </p>
    );
  }

  const completed = lecture.status === "completed";
  const semanticWarning = completed && lecture.error_message?.startsWith(SEMANTIC_WARNING);

  function renderAiTab(field: AiField, content: ReactNode) {
    const label = FIELD_LABEL[field] ?? field;
    const busy = Boolean(busyField[field]);
    const error = fieldError[field];
    const filled = lecture !== null && hasContent(lecture, field);

    return (
      <div className="stack">
        {error && (
          <p className="alert alert-error" role="alert">
            {error}
          </p>
        )}
        {busy && (
          <p className="muted generating">
            <span className="spinner spinner-xs" aria-hidden="true" /> Generating {label.toLowerCase()}… this
            can take up to a minute.
          </p>
        )}
        {packBusy && (
          <p className="alert alert-info">
            <span className="spinner spinner-xs" aria-hidden="true" /> “Generate everything” is running. This
            tab fills in when it finishes, and its buttons unlock then.
          </p>
        )}
        {!filled && !busy && (
          <div className="empty-ai">
            <p className="muted">No {label.toLowerCase()} yet.</p>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => generate(field, false)}
              disabled={packBusy}
            >
              Generate {label.toLowerCase()}
            </button>
          </div>
        )}
        {filled && (
          <>
            <div className="regen-row">
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => generate(field, true)}
                disabled={busy || packBusy}
              >
                ↻ Regenerate
              </button>
            </div>
            <div className={busy ? "dimmed" : undefined}>{content}</div>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="stack">
      <Link to="/" className="back-link">
        ← All lectures
      </Link>

      <section className="card">
        <div className="lecture-header">
          <h1 className="lecture-heading">{lecture.title}</h1>
          <StatusBadge status={lecture.status} />
        </div>
        <div className="lecture-meta muted small">
          {lecture.duration_seconds != null && <span>{formatTime(lecture.duration_seconds)}</span>}
          {lecture.language && <span>{lecture.language.toUpperCase()}</span>}
        </div>

        {audioSrc && (
          <audio
            ref={audioRef}
            className="player"
            controls
            preload="metadata"
            src={audioSrc}
            onError={() => {
              // The presigned URL expires (15 min); fetch a fresh one once.
              if (audioRetried.current) return setAudioSrc(null);
              audioRetried.current = true;
              loadAudio();
            }}
          />
        )}

        <div className="actions">
          <button
            type="button"
            className="btn btn-primary"
            onClick={generateEverything}
            disabled={!completed || packBusy}
          >
            {packBusy ? (
              <>
                <span className="spinner spinner-xs" aria-hidden="true" /> Generating…
              </>
            ) : (
              "✨ Generate everything"
            )}
          </button>
          <button type="button" className="btn btn-ghost" onClick={exportPack} disabled={!completed}>
            Export
          </button>
          <button type="button" className="btn btn-danger" onClick={remove}>
            Delete
          </button>
        </div>

        {actionError && (
          <p className="alert alert-error" role="alert">
            {actionError}
          </p>
        )}

        {packResult && (
          <div className="pack-result">
            {packResult.generated.length > 0 && (
              <p>
                <strong>Generated:</strong> {packResult.generated.map((f) => FIELD_LABEL[f] ?? f).join(", ")}
              </p>
            )}
            {packResult.skipped.length > 0 && (
              <p className="muted">
                <strong>Already had:</strong> {packResult.skipped.map((f) => FIELD_LABEL[f] ?? f).join(", ")}
              </p>
            )}
            {Object.entries(packResult.failed).map(([f, msg]) => (
              <p key={f} className="alert alert-error">
                <strong>{FIELD_LABEL[f] ?? f} failed:</strong> {msg}
              </p>
            ))}
          </div>
        )}
      </section>

      {inFlight && (
        <section className="card processing">
          <span className="spinner spinner-lg" aria-hidden="true" />
          <div>
            <p>
              <strong>{lecture.status === "queued" ? "Waiting in the queue…" : "Transcribing…"}</strong>
            </p>
            <p className="muted">
              The Celery worker is transcribing this lecture with Whisper. This page updates on its own; long
              lectures can take a few minutes.
            </p>
            {stuckInQueue && (
              <p className="alert alert-warning">
                Still queued after 30 seconds. Is the worker running? Check <code>docker compose logs worker</code>
              </p>
            )}
          </div>
        </section>
      )}

      {lecture.status === "failed" && (
        <section className="card">
          <p className="alert alert-error" role="alert">
            <strong>Transcription failed.</strong> {lecture.error_message ?? "Unknown error."}
          </p>
          <button type="button" className="btn btn-primary" onClick={retry} disabled={retrying}>
            {retrying ? "Retrying…" : "Retry"}
          </button>
        </section>
      )}

      {semanticWarning && <p className="alert alert-warning small">{lecture.error_message}</p>}

      {completed && (
        <section className="card">
          <div className="tabs" role="tablist">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={tab === t.id}
                className={`tab${tab === t.id ? " active" : ""}`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
                {busyField[t.id] && <span className="spinner spinner-xs" aria-hidden="true" />}
              </button>
            ))}
          </div>

          <div className="tab-panel" role="tabpanel">
            {tab === "transcript" && <Transcript lecture={lecture} onSeek={seek} />}
            {tab === "summary" && renderAiTab("summary", <Markdown source={lecture.summary ?? ""} />)}
            {tab === "notes" && renderAiTab("notes", <Markdown source={lecture.notes ?? ""} />)}
            {tab === "quiz" && renderAiTab("quiz", <Quiz key={lecture.quiz?.[0]?.question} questions={lecture.quiz ?? []} />)}
            {tab === "flashcards" &&
              renderAiTab("flashcards", <Flashcards key={lecture.flashcards?.[0]?.front} cards={lecture.flashcards ?? []} />)}
            {tab === "key_concepts" &&
              renderAiTab("key_concepts", <KeyConcepts concepts={lecture.key_concepts ?? []} />)}
            {tab === "mindmap" &&
              renderAiTab("mindmap", <MermaidDiagram code={lecture.mindmap ?? ""} />)}
            {tab === "chapters" &&
              renderAiTab("chapters", <Chapters chapters={lecture.chapters ?? []} onSeek={seek} />)}
          </div>
        </section>
      )}
    </div>
  );
}
