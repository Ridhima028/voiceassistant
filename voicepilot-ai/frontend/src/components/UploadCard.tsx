import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage, formatTime } from "../services/api";

// Mirrors ALLOWED_EXTENSIONS in backend/config.py.
const EXTENSIONS = [".wav", ".mp3", ".m4a", ".webm", ".ogg", ".flac"];

function looksLikeAudio(file: File): boolean {
  const name = file.name.toLowerCase();
  return EXTENSIONS.some((ext) => name.endsWith(ext)) || file.type.startsWith("audio/");
}

export default function UploadCard() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Recording state
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const discardRef = useRef(false);
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!recording) return;
    const started = Date.now();
    const id = window.setInterval(() => setElapsed((Date.now() - started) / 1000), 250);
    return () => window.clearInterval(id);
  }, [recording]);

  // Stop the microphone if the user navigates away mid-recording.
  useEffect(
    () => () => {
      const rec = recorderRef.current;
      if (rec && rec.state !== "inactive") {
        discardRef.current = true;
        rec.stop();
      }
    },
    [],
  );

  async function upload(file: File) {
    setError(null);
    if (!looksLikeAudio(file)) {
      setError(`Unsupported file type. Allowed: ${EXTENSIONS.join(", ")}`);
      return;
    }
    setUploading(file.name);
    try {
      const lecture = await api.upload(file);
      navigate(`/lectures/${lecture.id}`);
    } catch (err) {
      // 413 too large, 400 bad type / empty, 503 storage down — the backend's
      // detail message already says which.
      setError(errorMessage(err));
      setUploading(null);
    }
  }

  function onPick(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow picking the same file again after an error
    if (file) void upload(file);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) void upload(file);
  }

  async function startRecording() {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Recording isn't supported in this browser.");
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError("Microphone access was denied.");
      return;
    }

    const recorder = new MediaRecorder(stream);
    chunksRef.current = [];
    discardRef.current = false;
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      setRecording(false);
      if (discardRef.current) return;
      const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
      const stamp = new Date().toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
      void upload(new File([blob], `Recording ${stamp}.webm`, { type: blob.type }));
    };

    recorderRef.current = recorder;
    recorder.start(1000);
    setElapsed(0);
    setRecording(true);
  }

  function stopRecording(discard: boolean) {
    discardRef.current = discard;
    recorderRef.current?.stop();
  }

  const busy = uploading !== null;

  return (
    <section className="card">
      <h2 className="card-title">New lecture</h2>

      {recording ? (
        <div className="recorder">
          <span className="rec-dot" aria-hidden="true" />
          <span className="rec-time" aria-live="polite">
            {formatTime(elapsed)}
          </span>
          <button type="button" className="btn btn-primary" onClick={() => stopRecording(false)}>
            Stop &amp; upload
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => stopRecording(true)}>
            Cancel
          </button>
        </div>
      ) : (
        <>
          <div
            className={`dropzone${dragging ? " dragging" : ""}${busy ? " disabled" : ""}`}
            role="button"
            tabIndex={0}
            aria-disabled={busy}
            onClick={() => !busy && inputRef.current?.click()}
            onKeyDown={(e) => {
              if (!busy && (e.key === "Enter" || e.key === " ")) {
                e.preventDefault();
                inputRef.current?.click();
              }
            }}
            onDragOver={(e) => {
              e.preventDefault();
              if (!busy) setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => (busy ? e.preventDefault() : onDrop(e))}
          >
            {busy ? (
              <>
                <span className="spinner" aria-hidden="true" />
                <p>Uploading “{uploading}”…</p>
              </>
            ) : (
              <>
                <p className="dropzone-main">Drop an audio file here, or click to choose</p>
                <p className="muted small">{EXTENSIONS.join("  ")}</p>
              </>
            )}
          </div>
          <input
            ref={inputRef}
            type="file"
            accept={[...EXTENSIONS, "audio/*"].join(",")}
            onChange={onPick}
            hidden
          />
          <div className="upload-actions">
            <button type="button" className="btn btn-ghost" onClick={startRecording} disabled={busy}>
              🎤 Record in browser
            </button>
          </div>
        </>
      )}

      {error && (
        <p className="alert alert-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
