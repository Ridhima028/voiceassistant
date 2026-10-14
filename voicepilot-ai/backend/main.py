from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine
from models.user import User
from models.lecture import Lecture
from database import Base

from migrations import run_additive_migrations
from routers import auth, lectures
from services.storage import ensure_bucket

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    # Adds any columns introduced after the tables were first created.
    run_additive_migrations()
    # Create the audio bucket on first boot so uploads never hit "no such bucket".
    ensure_bucket()
    yield


app = FastAPI(
    title="VoicePilot AI",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Development ke liye
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(lectures.router)

@app.get("/")
def home():
    return {
        "message": "Welcome to VoicePilot AI 🚀"
    }


@app.get("/health")
def health():
    """Liveness probe — confirms the API is up and the DB is reachable."""
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return {"status": "ok" if db_ok else "degraded", "database": db_ok}
