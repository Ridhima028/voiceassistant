import asyncio
import os
import tempfile
import uuid
from pathlib import Path

from fastapi import (
    APIRouter, Depends, File, HTTPException, Query, Request, UploadFile,
)
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from celery_app import celery_app
from database import get_db
from dependencies import get_current_user
from models.lecture import Lecture
from models.user import User
from schemas.lecture import LectureResponse, LectureListItem, StudyPackStatus, AudioUrlResponse
from services import storage
from services.llm_service import (
    generate_summary, generate_notes, generate_quiz, generate_flashcards,
    generate_key_concepts, generate_mindmap, generate_chapters,
    LLMGenerationError,
)
from services.export_service import render_study_pack_html
from config import (
    MAX_UPLOAD_SIZE_BYTES, MAX_UPLOAD_SIZE_MB, ALLOWED_EXTENSIONS, S3_PRESIGNED_EXPIRY_SECONDS,
)

router = APIRouter(
    prefix="/lectures",
    tags=["Lectures"]
)

def _storage_unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="File storage is temporarily unavailable. Please try again shortly."
    )


# ==========================================================================
# Upload / transcription
# ==========================================================================

@router.post("/transcribe", response_model=LectureResponse, status_code=202)
async def transcribe_lecture(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # --- Type validation: MIME type isn't fully trustworthy on its own —
    # browsers recording audio in-browser often send "video/webm" or
    # "application/octet-stream" even for audio-only content — so we also
    # check the file extension as a second signal. Reject only if BOTH look wrong.
    extension = Path(file.filename or "").suffix.lower()
    looks_like_audio_mime = bool(file.content_type) and (
        file.content_type.startswith("audio/") or file.content_type.startswith("video/")
    )
    if extension not in ALLOWED_EXTENSIONS and not looks_like_audio_mime:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # --- Fast reject using Content-Length header, if the client sent one.
    # Not guaranteed to be present or accurate, so this is a quick early
    # check only — the real enforcement happens below while streaming.
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max allowed size is {MAX_UPLOAD_SIZE_MB}MB."
        )

    # Unique object key so uploads never overwrite each other. Prefixed by
    # user id so one user's files are grouped (easy to list/delete/audit).
    # Original name is kept only as the display "title".
    object_key = f"audio/{current_user.id}/{uuid.uuid4()}{extension}"

    # Short-lived local temp file: only lives for the duration of this
    # request, and is always deleted in the finally below.
    fd, tmp_path = tempfile.mkstemp(suffix=extension)
    os.close(fd)

    try:
        # --- Stream to the temp file in chunks, enforcing the size cap as we
        # go. This protects us even if Content-Length was missing, wrong, or
        # lying — we never trust the header alone to keep a huge file off disk.
        total_bytes = 0
        chunk_size = 1024 * 1024  # 1MB per read

        with open(tmp_path, "wb") as buffer:
            while chunk := await file.read(chunk_size):
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_SIZE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Max allowed size is {MAX_UPLOAD_SIZE_MB}MB."
                    )
                buffer.write(chunk)

        if total_bytes == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        # boto3 is blocking — run it in a thread so a big upload doesn't
        # freeze every other request on the event loop.
        try:
            await run_in_threadpool(
                storage.upload_file,
                tmp_path, object_key, file.content_type or "application/octet-stream",
            )
        except storage.TRANSIENT_ERRORS:
            raise _storage_unavailable()
    finally:
        os.unlink(tmp_path)

    lecture = Lecture(
        user_id=current_user.id,
        title=file.filename,
        audio_path=object_key,
        status="queued",
    )
    db.add(lecture)
    # Commit BEFORE enqueueing: the worker can pick the job up instantly, and
    # it must be able to see this row when it does.
    try:
        db.commit()
    except Exception:
        # No row points at the object, so remove it rather than orphan it.
        db.rollback()
        try:
            storage.delete_object(object_key)
        except Exception:
            pass
        raise
    db.refresh(lecture)

    # Returns immediately with status="queued" — the worker container does
    # the transcription. Sent by name so the API never imports Whisper.
    celery_app.send_task("tasks.transcribe_lecture", args=[lecture.id])

    return lecture


# ==========================================================================
# Retrieval
# ==========================================================================

@router.get("", response_model=list[LectureListItem])
def get_lectures(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lectures = (
        db.query(Lecture)
        .filter(Lecture.user_id == current_user.id)
        .order_by(Lecture.created_at.desc())
        .all()
    )

    # Map heavy fields down to booleans so the list stays small.
    return [
        LectureListItem(
            id=lec.id,
            title=lec.title,
            status=lec.status,
            language=lec.language,
            duration_seconds=lec.duration_seconds,
            created_at=lec.created_at,
            has_summary=bool(lec.summary),
            has_notes=bool(lec.notes),
            has_quiz=bool(lec.quiz),
            has_flashcards=bool(lec.flashcards),
            has_key_concepts=bool(lec.key_concepts),
            has_mindmap=bool(lec.mindmap),
            has_chapters=bool(lec.chapters),
        )
        for lec in lectures
    ]


def _get_owned_lecture(lecture_id: int, db: Session, current_user: User) -> Lecture:
    """Confirms the lecture exists AND belongs to the caller."""
    lecture = (
        db.query(Lecture)
        .filter(Lecture.id == lecture_id, Lecture.user_id == current_user.id)
        .first()
    )
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")
    return lecture


def _get_owned_completed_lecture(lecture_id: int, db: Session, current_user: User) -> Lecture:
    """
    Shared lookup for the AI-generation endpoints: confirms the lecture
    exists, belongs to the caller, and actually has a transcript ready.
    """
    lecture = _get_owned_lecture(lecture_id, db, current_user)

    if lecture.status != "completed" or not lecture.transcript:
        raise HTTPException(
            status_code=409,
            detail=f"Lecture transcript isn't ready yet (status: {lecture.status})."
        )

    return lecture


@router.get("/{lecture_id}", response_model=LectureResponse)
def get_lecture(
    lecture_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_owned_lecture(lecture_id, db, current_user)


@router.get("/{lecture_id}/audio-url", response_model=AudioUrlResponse)
def get_audio_url(
    lecture_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Short-lived link the browser can use to play/download the original
    audio straight from storage. The bucket stays private; ownership is
    checked here, and the link expires on its own.
    """
    lecture = _get_owned_lecture(lecture_id, db, current_user)
    return AudioUrlResponse(
        url=storage.presigned_get_url(lecture.audio_path, S3_PRESIGNED_EXPIRY_SECONDS),
        expires_in=S3_PRESIGNED_EXPIRY_SECONDS,
    )


@router.get("/{lecture_id}/transcript")
def get_transcript(
    lecture_id: int,
    view: str = Query("semantic", pattern="^(raw|semantic|plain)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Three views of the same transcription:
      - plain:    the full text, no timing
      - raw:      Whisper's original pause-based segments
      - semantic: segments re-grouped by meaning (the default, and the
                  one worth actually reading)
    """
    lecture = _get_owned_completed_lecture(lecture_id, db, current_user)

    if view == "plain":
        payload = {"text": lecture.transcript}
    elif view == "raw":
        payload = {"segments": lecture.segments or []}
    else:
        # Fall back to raw if semantic chunking failed for this lecture.
        payload = {"segments": lecture.processed_segments or lecture.segments or []}

    return {
        "lecture_id": lecture.id,
        "title": lecture.title,
        "language": lecture.language,
        "duration_seconds": lecture.duration_seconds,
        "view": view,
        **payload,
    }


# ==========================================================================
# AI study material
# ==========================================================================
# Every generator below follows the same contract:
#   - lecture must be owned by the caller and fully transcribed
#   - cached by default; ?regenerate=true forces a fresh call
#   - LLM failures surface as 502, not a silent empty result

async def _generate_field(
    lecture: Lecture,
    field: str,
    generator,
    db: Session,
    regenerate: bool,
):
    if getattr(lecture, field) and not regenerate:
        return lecture

    try:
        setattr(lecture, field, await generator())
    except LLMGenerationError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"{field.replace('_', ' ').title()} generation failed: {e}"
        )

    db.commit()
    db.refresh(lecture)
    return lecture


@router.post("/{lecture_id}/summary", response_model=LectureResponse)
async def create_summary(
    lecture_id: int,
    regenerate: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lecture = _get_owned_completed_lecture(lecture_id, db, current_user)
    return await _generate_field(
        lecture, "summary",
        lambda: generate_summary(lecture.transcript),
        db, regenerate,
    )


@router.post("/{lecture_id}/notes", response_model=LectureResponse)
async def create_notes(
    lecture_id: int,
    regenerate: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rich Markdown notes including Mermaid diagrams, tables and LaTeX."""
    lecture = _get_owned_completed_lecture(lecture_id, db, current_user)
    return await _generate_field(
        lecture, "notes",
        lambda: generate_notes(lecture.transcript),
        db, regenerate,
    )


@router.post("/{lecture_id}/quiz", response_model=LectureResponse)
async def create_quiz(
    lecture_id: int,
    num_questions: int = Query(5, ge=1, le=20),
    regenerate: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lecture = _get_owned_completed_lecture(lecture_id, db, current_user)
    return await _generate_field(
        lecture, "quiz",
        lambda: generate_quiz(lecture.transcript, num_questions),
        db, regenerate,
    )


@router.post("/{lecture_id}/flashcards", response_model=LectureResponse)
async def create_flashcards(
    lecture_id: int,
    num_cards: int = Query(10, ge=1, le=40),
    regenerate: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lecture = _get_owned_completed_lecture(lecture_id, db, current_user)
    return await _generate_field(
        lecture, "flashcards",
        lambda: generate_flashcards(lecture.transcript, num_cards),
        db, regenerate,
    )


@router.post("/{lecture_id}/key-concepts", response_model=LectureResponse)
async def create_key_concepts(
    lecture_id: int,
    regenerate: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Glossary of terms with definitions, importance ranking and cross-links."""
    lecture = _get_owned_completed_lecture(lecture_id, db, current_user)
    return await _generate_field(
        lecture, "key_concepts",
        lambda: generate_key_concepts(lecture.transcript),
        db, regenerate,
    )


@router.post("/{lecture_id}/mindmap", response_model=LectureResponse)
async def create_mindmap(
    lecture_id: int,
    regenerate: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mermaid `mindmap` source for the lecture's topic hierarchy."""
    lecture = _get_owned_completed_lecture(lecture_id, db, current_user)
    return await _generate_field(
        lecture, "mindmap",
        lambda: generate_mindmap(lecture.transcript),
        db, regenerate,
    )


@router.post("/{lecture_id}/chapters", response_model=LectureResponse)
async def create_chapters(
    lecture_id: int,
    regenerate: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Timestamped chapter outline, built from the transcript's segments."""
    lecture = _get_owned_completed_lecture(lecture_id, db, current_user)
    segments = lecture.processed_segments or lecture.segments
    if not segments:
        raise HTTPException(
            status_code=409,
            detail="No timestamped segments available for this lecture."
        )
    return await _generate_field(
        lecture, "chapters",
        lambda: generate_chapters(segments),
        db, regenerate,
    )


# ==========================================================================
# Study pack — generate everything in one call
# ==========================================================================

@router.post("/{lecture_id}/study-pack", response_model=StudyPackStatus)
async def create_study_pack(
    lecture_id: int,
    regenerate: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generates every piece of study material in one request.

    Deliberately partial-tolerant: if one generator fails (a model hiccup,
    a rate limit), the others still get saved and the response reports
    exactly what succeeded, what was already cached, and what failed —
    rather than throwing the whole batch away.
    """
    lecture = _get_owned_completed_lecture(lecture_id, db, current_user)
    segments = lecture.processed_segments or lecture.segments

    jobs = [
        ("summary", lambda: generate_summary(lecture.transcript)),
        ("notes", lambda: generate_notes(lecture.transcript)),
        ("key_concepts", lambda: generate_key_concepts(lecture.transcript)),
        ("quiz", lambda: generate_quiz(lecture.transcript, 5)),
        ("flashcards", lambda: generate_flashcards(lecture.transcript, 10)),
        ("mindmap", lambda: generate_mindmap(lecture.transcript)),
    ]
    if segments:
        jobs.append(("chapters", lambda: generate_chapters(segments)))

    generated, skipped, failed = [], [], {}

    to_run = []
    for field, generator in jobs:
        if getattr(lecture, field) and not regenerate:
            skipped.append(field)
        else:
            to_run.append((field, generator))

    # The generators are independent network calls, so run them concurrently:
    # total time ≈ the slowest one, not the sum of all. return_exceptions keeps
    # one failure from cancelling the rest. Results are applied to the ORM
    # object only after gather, so the session is never touched concurrently.
    results = await asyncio.gather(
        *(generator() for _, generator in to_run),
        return_exceptions=True,
    )

    for (field, _), result in zip(to_run, results):
        if isinstance(result, BaseException):
            failed[field] = str(result)
        else:
            setattr(lecture, field, result)
            generated.append(field)

    db.commit()

    return StudyPackStatus(
        lecture_id=lecture.id,
        generated=generated,
        skipped=skipped,
        failed=failed,
    )


@router.get("/{lecture_id}/export", response_class=HTMLResponse)
def export_study_pack(
    lecture_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Renders everything generated so far into a single self-contained HTML
    study pack — Mermaid diagrams rendered, LaTeX typeset, quiz answers
    collapsible, flashcards flippable. Open in a browser or print to PDF.
    """
    lecture = _get_owned_lecture(lecture_id, db, current_user)
    return HTMLResponse(content=render_study_pack_html(lecture))


# ==========================================================================
# Lifecycle
# ==========================================================================

@router.post("/{lecture_id}/retry", response_model=LectureResponse, status_code=202)
def retry_transcription(
    lecture_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Re-runs transcription on a lecture that failed. The original audio is
    still in object storage (we intentionally don't delete it on failure),
    so the user never has to re-upload.
    """
    lecture = _get_owned_lecture(lecture_id, db, current_user)

    if lecture.status in ("queued", "processing"):
        raise HTTPException(status_code=409, detail=f"This lecture is already {lecture.status}.")

    # Old dev lectures still hold a local disk path here; that key doesn't
    # exist in the bucket, so they get a clean 410 too.
    try:
        audio_available = storage.object_exists(lecture.audio_path)
    except storage.TRANSIENT_ERRORS:
        raise _storage_unavailable()

    if not audio_available:
        raise HTTPException(
            status_code=410,
            detail="The original audio file is no longer available. Please re-upload."
        )

    lecture.status = "queued"
    lecture.error_message = None
    db.commit()
    db.refresh(lecture)

    celery_app.send_task("tasks.transcribe_lecture", args=[lecture.id])
    return lecture


@router.delete("/{lecture_id}", status_code=204)
def delete_lecture(
    lecture_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deletes the lecture row AND its audio object — no orphaned files left behind."""
    lecture = _get_owned_lecture(lecture_id, db, current_user)

    # Object first, then row: if storage is down we keep the row (and
    # return 503) so the user can retry, instead of losing track of the file.
    try:
        storage.delete_object(lecture.audio_path)
    except storage.TRANSIENT_ERRORS:
        raise _storage_unavailable()

    db.delete(lecture)
    db.commit()
    return None
