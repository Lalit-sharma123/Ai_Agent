from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database import get_db, Conversation, Message
from .schemas import ChatRequest, ChatResponse, MessageOut
from ..core.model_adapters import ModelError

router = APIRouter(prefix="/api", tags=["chat"])

def as_message(row: Message) -> MessageOut:
    return MessageOut(id=row.id, role=row.role, content=row.content, created_at=row.created_at)

@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request, db: Session = Depends(get_db)):
    conversation = db.get(Conversation, body.conversation_id) if body.conversation_id else None
    if body.conversation_id and conversation is None:
        raise HTTPException(404, "Conversation not found.")
    if conversation is None:
        conversation = Conversation(id=str(uuid4()), title=body.message[:80])
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    prior = db.scalars(select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at)).all()
    history = [{"role": m.role, "content": m.content} for m in prior]
    user_row = Message(id=str(uuid4()), conversation_id=conversation.id, role="user",
                       content=body.message, created_at=datetime.now(timezone.utc))
    db.add(user_row)
    db.commit()
    try:
        result = await request.app.state.orchestrator.respond(body.message, history, body.provider)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ModelError as exc:
        raise HTTPException(503, str(exc)) from exc
    assistant_row = Message(id=str(uuid4()), conversation_id=conversation.id, role="assistant",
                            content=result["content"], created_at=datetime.now(timezone.utc))
    db.add(assistant_row)
    db.commit()
    return ChatResponse(conversation_id=conversation.id, message=as_message(user_row),
                        assistant=as_message(assistant_row), provider=result["provider"], model=result["model"])

@router.get("/conversations")
def conversations(db: Session = Depends(get_db)):
    rows = db.scalars(select(Conversation).order_by(Conversation.created_at.desc())).all()
    return [{"id": r.id, "title": r.title, "created_at": r.created_at.isoformat()} for r in rows]

@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: str, db: Session = Depends(get_db)):
    if db.get(Conversation, conversation_id) is None:
        raise HTTPException(404, "Conversation not found.")
    rows = db.scalars(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)).all()
    return [as_message(r).model_dump(mode="json") for r in rows]
