from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LectureResponse(BaseModel):
    """
    Full lecture payload. Deliberately does NOT expose audio_path — the
    client has no use for a server-side file path, and leaking internal
    storage layout is needless attack surface.
    """

    id: int
    user_id: int
    title: str
    status: str
    language: str | None = None
    duration_seconds: float | None = None

    transcript: str | None = None
    segments: list | None = None
    processed_segments: list | None = None

    summary: str | None = None
    notes: str | None = None
    quiz: list | None = None
    flashcards: list | None = None
    key_concepts: list | None = None
    mindmap: str | None = None
    chapters: list | None = None

    error_message: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LectureListItem(BaseModel):
    """
    Lightweight shape for the list endpoint. Returning full transcripts and
    every segment for every lecture makes the list response enormous once a
    user has a few long lectures — the flags below tell the client what
    exists without shipping the payload.
    """

    id: int
    title: str
    status: str
    language: str | None = None
    duration_seconds: float | None = None
    created_at: datetime

    has_summary: bool = False
    has_notes: bool = False
    has_quiz: bool = False
    has_flashcards: bool = False
    has_key_concepts: bool = False
    has_mindmap: bool = False
    has_chapters: bool = False

    model_config = ConfigDict(from_attributes=True)


class StudyPackStatus(BaseModel):
    """What the /study-pack endpoint generated, and what (if anything) failed."""

    lecture_id: int
    generated: list[str]
    skipped: list[str]
    failed: dict[str, str]


class AudioUrlResponse(BaseModel):
    """Presigned link to the original audio; stops working after expires_in seconds."""

    url: str
    expires_in: int
