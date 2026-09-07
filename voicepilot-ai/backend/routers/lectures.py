import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from dependencies import get_current_user
from models.lecture import Lecture
from models.user import User
from schemas.lecture import LectureResponse
from services.stt_service import transcribe_audio
from services.semantic_segmenter import semantic_chunk

router = APIRouter(
    prefix="/lectures",
    tags=["Lectures"]
)

AUDIO_DIR = Path("uploads/audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def run_transcription(lecture_id: int, audio_path: str):
    """
    Runs in a background thread (FastAPI/Starlette runs sync BackgroundTasks
    in a threadpool), so it does NOT block the event loop for other requests.

    It opens its own DB session because the request's session is closed by
    the time this runs.
    """
    db = SessionLocal()
    try:
        lecture = db.query(Lecture).filter(Lecture.id == lecture_id).first()
        if not lecture:
            return

        result = transcribe_audio(audio_path)

        lecture.transcript = result["text"]
        lecture.segments = result["segments"]
        lecture.processed_segments = semantic_chunk(result["segments"])
        lecture.language = result["language"]
        lecture.status = "completed"
        db.commit()

    except Exception as e:
        db.rollback()
        lecture = db.query(Lecture).filter(Lecture.id == lecture_id).first()
        if lecture:
            lecture.status = "failed"
            lecture.error_message = str(e)
            db.commit()

    finally:
        db.close()


@router.post("/transcribe", response_model=LectureResponse, status_code=202)
async def transcribe_lecture(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.content_type or not file.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a valid audio file."
        )

    # Unique storage name so uploads never overwrite each other.
    # Original name is kept only as the display "title".
    extension = Path(file.filename).suffix
    unique_name = f"{uuid.uuid4()}{extension}"
    file_path = AUDIO_DIR / unique_name

    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    lecture = Lecture(
        user_id=current_user.id,
        title=file.filename,
        audio_path=str(file_path),
        status="processing",
    )
    db.add(lecture)
    db.commit()
    db.refresh(lecture)

    # Returns immediately with status="processing" — transcription happens
    # in the background instead of blocking this request.
    background_tasks.add_task(run_transcription, lecture.id, str(file_path))

    return lecture


@router.get("/{lecture_id}", response_model=LectureResponse)
def get_lecture(
    lecture_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lecture = (
        db.query(Lecture)
        .filter(Lecture.id == lecture_id, Lecture.user_id == current_user.id)
        .first()
    )

    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")

    return lecture


@router.get("", response_model=list[LectureResponse])
def get_lectures(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Lecture)
        .filter(Lecture.user_id == current_user.id)
        .order_by(Lecture.created_at.desc())
        .all()
    )
