from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import get_settings
from .database import init_db
from .core.model_adapters import ModelAdapter
from .core.orchestrator import Orchestrator
from .api import health, chat, voice, tasks, research, meetings, coding, email, documents, presentations, desktop

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.models = ModelAdapter(settings)
    app.state.orchestrator = Orchestrator(app.state.models)
    # Pending voice plans are scoped to a conversation and only executed after explicit confirmation.
    app.state.pending_voice_commands = {}
    init_db()
    yield

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(voice.router)
app.include_router(tasks.router)
app.include_router(research.router)
app.include_router(meetings.router)
app.include_router(coding.router)
app.include_router(desktop.router)
app.include_router(presentations.router)
app.include_router(documents.router)
app.include_router(email.router)

@app.get("/")
async def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/health"}
