from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from database import Base


class Lecture(Base):

    __tablename__ = "lectures"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Original filename the user uploaded, kept for display purposes only.
    title = Column(String, nullable=False)

    # NOTE: despite the name, this now holds an S3 OBJECT KEY, not a disk path,
    # e.g. "audio/{user_id}/{uuid}.webm" (see services/storage.py). Kept as
    # "audio_path" to avoid a column rename without Alembic. UUID-based, never
    # the raw uploaded filename, so two uploads of "lecture.wav" never collide.
    # Old dev rows may still contain a local path; those simply aren't found.
    audio_path = Column(String, nullable=False)

    transcript = Column(Text, nullable=True)

    # Whisper's raw, pause-based segments — unchanged source of truth.
    segments = Column(JSONB, nullable=True)

    # Semantically re-grouped segments (see services/semantic_segmenter.py).
    # Kept separate so the raw Whisper output is never lost.
    processed_segments = Column(JSONB, nullable=True)

    language = Column(String, nullable=True)

    # Audio length in seconds, from Whisper's info object.
    duration_seconds = Column(Float, nullable=True)

    # AI-generated study material, built from the transcript on demand.
    # Nullable — only populated once the user actually requests each one,
    # so we don't pay for an LLM call nobody asked for.
    summary = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)            # Markdown, incl. Mermaid blocks
    quiz = Column(JSONB, nullable=True)
    flashcards = Column(JSONB, nullable=True)
    key_concepts = Column(JSONB, nullable=True)
    mindmap = Column(Text, nullable=True)          # raw Mermaid source
    chapters = Column(JSONB, nullable=True)

    # "processing" -> "completed" -> or "failed"
    status = Column(String, nullable=False, default="processing")
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
