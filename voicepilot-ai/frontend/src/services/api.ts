// Every backend call goes through request(). Paths are prefixed with /api,
// which the Vite dev server proxies to FastAPI (see vite.config.ts).

// ---------------------------------------------------------------------------
// Types — mirror backend/schemas/*.py
// ---------------------------------------------------------------------------

export type LectureStatus = "queued" | "processing" | "completed" | "failed";

export interface Segment {
  start: number;
  end: number;
  text: string;
}

export interface QuizQuestion {
  question: string;
  options: string[];
  correct_index: number;
  explanation: string;
  difficulty: "easy" | "medium" | "hard" | string;
}

export interface Flashcard {
  front: string;
  back: string;
  hint: string | null;
  topic: string;
}

export interface KeyConcept {
  term: string;
  definition: string;
  importance: "core" | "supporting" | "mentioned" | string;
  related_terms: string[];
}

export interface Chapter {
  start_seconds: number;
  title: string;
  summary: string;
}

/** GET /lectures — LectureListItem */
export interface LectureListItem {
  id: number;
  title: string;
  status: LectureStatus;
  language: string | null;
  duration_seconds: number | null;
  created_at: string;
  has_summary: boolean;
  has_notes: boolean;
  has_quiz: boolean;
  has_flashcards: boolean;
  has_key_concepts: boolean;
  has_mindmap: boolean;
  has_chapters: boolean;
}

/** LectureResponse */
export interface Lecture {
  id: number;
  user_id: number;
  title: string;
  status: LectureStatus;
  language: string | null;
  duration_seconds: number | null;
  transcript: string | null;
  segments: Segment[] | null;
  processed_segments: Segment[] | null;
  summary: string | null;
  notes: string | null;
  quiz: QuizQuestion[] | null;
  flashcards: Flashcard[] | null;
  key_concepts: KeyConcept[] | null;
  mindmap: string | null;
  chapters: Chapter[] | null;
  error_message: string | null;
  created_at: string;
}

export interface StudyPackStatus {
  lecture_id: number;
  generated: string[];
  skipped: string[];
  failed: Record<string, string>;
}

export interface AudioUrl {
  url: string;
  expires_in: number;
}

export interface Health {
  status: "ok" | "degraded";
  database: boolean;
}

export type AiField =
  | "summary"
  | "notes"
  | "quiz"
  | "flashcards"
  | "key_concepts"
  | "mindmap"
  | "chapters";

// ---------------------------------------------------------------------------
// Storage (localStorage can throw in private mode / with blocked storage)
// ---------------------------------------------------------------------------

export const storage = {
  get(key: string): string | null {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  set(key: string, value: string): void {
    try {
      localStorage.setItem(key, value);
    } catch {
      /* not persisted; the session still works in memory */
    }
  },
  remove(key: string): void {
    try {
      localStorage.removeItem(key);
    } catch {
      /* ignore */
    }
  },
};

export const TOKEN_KEY = "voicepilot.token";
export const EMAIL_KEY = "voicepilot.email";

// ---------------------------------------------------------------------------
// request()
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
    this.name = "ApiError";
  }
}

export const UNREACHABLE = "Can't reach the backend. Is it running on port 8000?";

let unauthorizedHandler: (() => void) | null = null;

/** AuthContext registers logout() here so any 401 signs the user out. */
export function setUnauthorizedHandler(fn: (() => void) | null): void {
  unauthorizedHandler = fn;
}

interface FastApiValidationError {
  loc?: (string | number)[];
  msg?: string;
}

/** FastAPI's `detail` is a string, or an array of validation errors. */
function detailToMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: FastApiValidationError) => {
        // loc looks like ["body", "email"]; the first part is noise to a user.
        const field = (d.loc ?? []).filter((p) => p !== "body").join(".");
        return field ? `${field}: ${d.msg ?? "invalid"}` : d.msg ?? "Invalid input";
      })
      .join("; ");
  }
  return null;
}

type ResponseKind = "json" | "text" | "none";

interface RequestOptions {
  method?: string;
  json?: unknown;
  form?: FormData;
  expect?: ResponseKind;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = storage.get(TOKEN_KEY);
  if (token) headers.Authorization = `Bearer ${token}`;

  let body: BodyInit | undefined;
  if (opts.form) {
    body = opts.form; // browser sets the multipart boundary itself
  } else if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  }

  let res: Response;
  try {
    res = await fetch(`/api${path}`, { method: opts.method ?? "GET", headers, body });
  } catch {
    throw new ApiError(UNREACHABLE, 0);
  }

  if (!res.ok) {
    if (res.status === 401 && token) unauthorizedHandler?.();

    const text = await res.text().catch(() => "");
    let message: string | null = null;
    try {
      message = detailToMessage(JSON.parse(text).detail);
    } catch {
      // Not JSON. When the backend is down, the Vite proxy answers with an
      // empty 5xx itself — FastAPI's own errors always carry a body.
      if (res.status >= 500 && !text.trim()) message = UNREACHABLE;
    }
    throw new ApiError(message ?? `Request failed (${res.status} ${res.statusText})`, res.status);
  }

  const expect = opts.expect ?? "json";
  if (expect === "none" || res.status === 204) return undefined as T;
  if (expect === "text") return (await res.text()) as T;
  return (await res.json()) as T;
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

const AI_PATHS: Record<AiField, string> = {
  summary: "summary",
  notes: "notes",
  quiz: "quiz",
  flashcards: "flashcards",
  key_concepts: "key-concepts",
  mindmap: "mindmap",
  chapters: "chapters",
};

export const api = {
  signup: (username: string, email: string, password: string) =>
    request<{ id: number; username: string; email: string }>("/auth/signup", {
      method: "POST",
      json: { username, email, password },
    }),

  login: (email: string, password: string) =>
    request<{ access_token: string; token_type: string }>("/auth/login", {
      method: "POST",
      json: { email, password },
    }),

  health: () => request<Health>("/health"),

  listLectures: () => request<LectureListItem[]>("/lectures"),

  getLecture: (id: number) => request<Lecture>(`/lectures/${id}`),

  /** 202 Accepted — the lecture comes back with status "queued". */
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Lecture>("/lectures/transcribe", { method: "POST", form });
  },

  generate: (id: number, field: AiField, regenerate = false) =>
    request<Lecture>(`/lectures/${id}/${AI_PATHS[field]}?regenerate=${regenerate}`, {
      method: "POST",
    }),

  studyPack: (id: number, regenerate = false) =>
    request<StudyPackStatus>(`/lectures/${id}/study-pack?regenerate=${regenerate}`, {
      method: "POST",
    }),

  audioUrl: (id: number) => request<AudioUrl>(`/lectures/${id}/audio-url`),

  exportHtml: (id: number) => request<string>(`/lectures/${id}/export`, { expect: "text" }),

  retry: (id: number) => request<Lecture>(`/lectures/${id}/retry`, { method: "POST" }),

  remove: (id: number) => request<void>(`/lectures/${id}`, { method: "DELETE", expect: "none" }),
};

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

/** 75 -> "1:15", 3725 -> "1:02:05" */
export function formatTime(seconds: number | null | undefined): string {
  const total = Math.max(0, Math.floor(seconds ?? 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = String(total % 60).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

/**
 * The backend stores naive UTC datetimes (datetime.utcnow), so created_at
 * arrives without a timezone. Mark it as UTC so the browser converts it to
 * local time instead of treating it as local already.
 */
export function parseServerDate(value: string): Date {
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`);
}

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
