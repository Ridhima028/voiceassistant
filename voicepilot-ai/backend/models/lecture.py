from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from database import Base


class Lecture(Base):

    __tablename__ = "lectures"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Original filename the user uploaded, kept for display purposes only.
    title = Column(String, nullable=False)

    # Actual path on disk — a UUID-based name, never the raw uploaded filename,
    # so two users (or the same user) uploading "lecture.wav" never collide.
    audio_path = Column(String, nullable=False)

    transcript = Column(Text, nullable=True)
    segments = Column(JSONB, nullable=True)
    processed_segments = Column(JSONB, nullable=True)
    language = Column(String, nullable=True)

    # "processing" -> "completed" -> or "failed"
    status = Column(String, nullable=False, default="processing")
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
