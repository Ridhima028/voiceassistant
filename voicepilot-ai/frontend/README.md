# VoicePilot AI — Frontend

React 18 + Vite + TypeScript client for the VoicePilot backend: upload or record
a lecture, watch it transcribe, then read the transcript and generate summaries,
notes, quizzes, flashcards, key concepts, a mind map and chapters.

## Run locally

1. Start the backend (from `voicepilot-ai/`):
   ```bash
   docker compose up -d db redis minio backend worker
   ```
   The API must be reachable at http://localhost:8000.
2. In `frontend/`:
   ```bash
   npm install
   npm run dev
   ```
3. Open http://localhost:5173

## Run with Docker

From `voicepilot-ai/`:

```bash
docker compose up --build
```

Then open http://localhost:5173.

## How API calls work

The browser only talks to the Vite dev server. Any request to `/api/*` is
proxied to the backend with the `/api` prefix removed
(`/api/lectures` → `http://localhost:8000/lectures`), so there are no CORS
issues. Inside Docker the target is `http://backend:8000`, set through the
`API_TARGET` environment variable.

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Dev server on port 5173 with hot reload |
| `npm run build` | Type-check (`tsc -b`) and build to `dist/` |
| `npm run preview` | Serve the production build locally |

## Structure

```
src/
  services/api.ts        all backend calls, shared types, formatTime()
  context/AuthContext.tsx login / signup / logout, token in localStorage
  hooks/usePolling.ts    interval polling while lectures are processing
  layouts/AppLayout.tsx  top bar: brand, backend health, email, log out
  pages/                 AuthPage, Dashboard, LecturePage
  components/            UploadCard, StatusBadge, Transcript, Markdown,
                         MermaidDiagram, Quiz, Flashcards, KeyConcepts, Chapters
  styles.css             plain CSS, light + dark theme
```
