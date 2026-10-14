"""
Celery tasks. Only the worker imports this module — the API enqueues jobs
by name via celery_app.send_task(), so Whisper never loads in the API.
"""

import os
import random

from sqlalchemy.exc import OperationalError

from celery_app import celery_app
from database import SessionLocal
from models.lecture import Lecture
from services import storage
import models.user  # noqa: F401 — registers "users" so Lecture.user_id's ForeignKey resolves

MAX_RETRIES = 3
RETRY_BASE_SECONDS = 10


def _backoff_with_jitter(retries: int) -> int:
    """Exponential backoff (10s, 20s, 40s) with full jitter, so several
    failing jobs don't all hammer the DB again at the same instant."""
    return random.randint(0, RETRY_BASE_SECONDS * (2 ** retries))


@celery_app.task(name="tasks.transcribe_lecture", bind=True, max_retries=MAX_RETRIES)
def transcribe_lecture(self, lecture_id: int):
    # Imported here rather than at module level so the Whisper model loads
    # inside the worker's child process (on the first job), not in the
    # parent before Celery forks it.
    from services.stt_service import transcribe_audio
    from services.semantic_segmenter import semantic_chunk

    db = SessionLocal()
    audio_tmp = None
    try:
        lecture = db.query(Lecture).filter(Lecture.id == lecture_id).first()

        # Idempotency guard: with acks_late a message can be delivered more
        # than once, so a duplicate must not redo finished work.
        if not lecture:
            return
        if lecture.status == "completed":
            return

        lecture.status = "processing"
        db.commit()

        # Whisper needs a real file, so pull the object down to a temp file
        # local to THIS worker. Any worker on any machine can do this.
        audio_tmp = storage.download_to_tempfile(lecture.audio_path)
        result = transcribe_audio(audio_tmp)

        lecture.transcript = result["text"]
        lecture.segments = result["segments"]
        lecture.language = result["language"]
        lecture.duration_seconds = result.get("duration")

        # Semantic chunking calls an external API, so it gets its own guard:
        # if it fails we still keep a perfectly usable raw transcript rather
        # than marking the whole lecture as failed.
        try:
            lecture.processed_segments = semantic_chunk(result["segments"])
        except Exception as e:
            lecture.processed_segments = None
            lecture.error_message = f"Semantic segmentation skipped: {e}"

        lecture.status = "completed"
        db.commit()

    except OperationalError as e:
        # Transient: DB connection dropped / restarting. Worth retrying.
        db.rollback()
        if self.request.retries >= MAX_RETRIES:
            _mark_failed(lecture_id, f"Database unavailable after {MAX_RETRIES} retries: {e}")
            raise
        raise self.retry(exc=e, countdown=_backoff_with_jitter(self.request.retries))

    except storage.TRANSIENT_ERRORS as e:
        # Transient: object storage unreachable (restarting, network blip).
        # Same backoff as the DB case — the file is still there, retry later.
        db.rollback()
        if self.request.retries >= MAX_RETRIES:
            _mark_failed(lecture_id, f"File storage unavailable after {MAX_RETRIES} retries: {e}")
            raise
        raise self.retry(exc=e, countdown=_backoff_with_jitter(self.request.retries))

    except Exception as e:
        # Permanent: AudioTooLongError, undecodable audio, AudioObjectNotFound
        # (object deleted, or an old row still holding a local disk path)...
        # Retrying would fail the same way, so record it and stop.
        db.rollback()
        lecture = db.query(Lecture).filter(Lecture.id == lecture_id).first()
        if lecture:
            lecture.status = "failed"
            lecture.error_message = str(e)
            db.commit()

    finally:
        # Always remove the temp copy — success, failure or retry — or every
        # job would leak one audio file onto the worker's disk.
        if audio_tmp:
            try:
                os.unlink(audio_tmp)
            except FileNotFoundError:
                pass
        db.close()


def _mark_failed(lecture_id: int, message: str):
    """Best-effort: the DB may still be down, in which case this fails too."""
    db = SessionLocal()
    try:
        lecture = db.query(Lecture).filter(Lecture.id == lecture_id).first()
        if lecture:
            lecture.status = "failed"
            lecture.error_message = message
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
