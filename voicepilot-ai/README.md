# VoicePilot AI

## Architecture: Lecture Transcription Flow

```
 ┌──────────┐  1. POST /lectures/transcribe (audio + JWT)
 │ Frontend │ ─────────────────────────────────────────────┐
 └──────────┘                                              ▼
      ▲                                         ┌────────────────────┐
      │ 3. 202 {id: 42, status: "queued"}       │  FastAPI (backend) │
      └──────────────────────────────────────── │  - check JWT       │
                                                │  - validate file   │
                                                │  - save audio file │
                                                └─────────┬──────────┘
                              2a. INSERT lecture          │ 2b. send_task("tasks.transcribe_lecture", [42])
                                  status="queued"         │     (only AFTER commit)
                                  ▼                       ▼
                           ┌────────────┐          ┌─────────────┐
                           │ PostgreSQL │          │ Redis queue │  [ {lecture_id: 42} ]
                           └────────────┘          └──────┬──────┘
                                  ▲                       │ 4. worker pulls the ticket
                                  │                       ▼
                                  │              ┌──────────────────────────┐
                                  │              │ Celery worker            │
                                  │ 5. status=   │ - skip if "completed"    │
                                  │ "processing" │ - read audio file        │
                                  ├───────────── │ - Whisper → transcript   │
                                  │              │ - Gemini embeddings →    │
                                  │ 6. save      │   semantic chunks        │
                                  │ transcript,  │ - 7. ack ticket (done)   │
                                  │ "completed"  └──────────────────────────┘
                                  │
 Frontend ── 8. GET /lectures/42 (polls) ──► FastAPI ──► reads status from Postgres
 Frontend ── 9. POST /lectures/42/study-pack ──► FastAPI ──► Gemini ──► saves notes/quiz/... in Postgres
```
