from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LectureResponse(BaseModel):

    id: int
    user_id: int
    title: str
    status: str
    transcript: str | None = None
    segments: list | None = None
    processed_segments: list | None = None
    language: str | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)