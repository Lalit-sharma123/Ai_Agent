from datetime import datetime
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    conversation_id: str | None = None
    provider: str | None = None

class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime

class ChatResponse(BaseModel):
    conversation_id: str
    message: MessageOut
    assistant: MessageOut
    provider: str
    model: str

class TranscriptionResponse(BaseModel):
    text: str
    engine: str
