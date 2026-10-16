import tempfile
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
import httpx
import re
from .schemas import TranscriptionResponse
from ..database import get_db, Conversation, Message
from ..graph.voice_graph import run_voice_graph

router = APIRouter(prefix="/api/voice", tags=["voice"])

@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(request: Request, audio: UploadFile = File(...)):
    suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
    data = await audio.read()
    if not data:
        raise HTTPException(400, "Audio upload is empty.")
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise HTTPException(503, "Server transcription is optional and faster-whisper is not installed. Use browser speech recognition or install the voice extras.")
    settings = request.app.state.settings
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
            tmp.write(data)
            tmp.flush()
            model = WhisperModel(settings.stt_model_size, device=settings.stt_device, compute_type=settings.stt_compute_type)
            segments, info = model.transcribe(tmp.name, vad_filter=True)
            text = " ".join(segment.text.strip() for segment in segments).strip()
        return TranscriptionResponse(text=text, engine=f"faster-whisper:{settings.stt_model_size}")
    except Exception as exc:
        raise HTTPException(422, f"Audio transcription failed: {exc}") from exc


class VoiceCommandRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=20000)
    conversation_id: str | None = None
    provider: str | None = None


@router.post("/command")
async def voice_command(body: VoiceCommandRequest, request: Request, db: Session = Depends(get_db)):
    """Understand natural language, route it through LangGraph, and invoke an MCP agent tool."""
    text = body.transcript.strip()
    if not text:
        raise HTTPException(422, "Please say or type a command.")
    conversation = db.get(Conversation, body.conversation_id) if body.conversation_id else None
    if body.conversation_id and conversation is None:
        raise HTTPException(404, "Conversation not found.")
    if conversation is None:
        conversation = Conversation(id=str(uuid4()), title=text[:80])
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    now = datetime.now(timezone.utc)
    user_row = Message(id=str(uuid4()), conversation_id=conversation.id, role="user", content=text, created_at=now)
    db.add(user_row)
    db.commit()
    pending_store = getattr(request.app.state, "pending_voice_commands", None)
    if pending_store is None:
        pending_store = request.app.state.pending_voice_commands = {}
    pending = pending_store.get(conversation.id)
    normalized = re.sub(r"[\s,.!?]+", " ", text.casefold()).strip()
    yes_phrases = {"ok", "okay", "ok do that", "okay do that", "yes", "yes do that", "do it", "do that", "confirm", "confirmed", "proceed", "go ahead", "haan", "han", "haan kar do", "kar do", "theek hai", "ठीक है", "हाँ", "हाँ कर दो"}
    cancel_phrases = {"cancel", "cancel it", "no", "no thanks", "stop", "don't do that", "do not do that", "nahi", "नहीं", "रद्द करो"}
    try:
        if pending and normalized in cancel_phrases:
            pending_store.pop(conversation.id, None)
            routed = {"transcript": text, "intent": pending["intent"], "agent": pending["agent"], "arguments": pending["arguments"], "result": None,
                      "reply": "Cancelled. I have not executed the pending task.", "needs_clarification": False, "requires_approval": False, "requires_confirmation": False, "orchestration": "voice-confirmation"}
        elif pending and pending.get("awaiting_detail"):
            intent, args = pending["intent"], dict(pending.get("arguments", {}))
            if intent == "youtube":
                args["query"] = text.strip()
                args["play_requested"] = True
            elif intent == "email":
                match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
                if match: args["to_address"] = match.group(0)
                elif not args.get("instruction"): args["instruction"] = text
                else: args["instruction"] = f"{args['instruction']}\nAdditional detail: {text}"
            elif intent == "meetings": args["query"] = text.strip()
            elif intent == "desktop":
                target = text.strip()
                args["action_type"] = "open_url" if target.startswith(("http://", "https://")) else "open_app"
                args["target"] = target
            elif intent == "calculator": args["expression"] = text.strip()
            elif intent == "presentations": args["topic"] = text.strip()
            elif intent == "coding": args["issue"] = f"{args.get('issue', '')}\nAdditional detail: {text}".strip()
            elif intent == "documents": args["question"] = text.strip()
            from ..graph.voice_graph import _prepare_fallback, _confirmation_preview
            prep = await _prepare_fallback({"intent": intent, "arguments": args})
            if prep.get("needs_clarification"):
                pending_store[conversation.id] = {**pending, "arguments": args, "clarification_question": prep.get("reply", "Please provide one more detail.")}
                routed = {"transcript": text, "intent": intent, "agent": pending["agent"], "arguments": args, "result": None,
                          "reply": prep.get("reply", "Please provide one more detail."), "needs_clarification": True, "requires_approval": False, "requires_confirmation": False, "orchestration": "voice-clarification"}
            else:
                pending_store[conversation.id] = {**pending, "arguments": args, "awaiting_detail": False}
                routed = {"transcript": text, "intent": intent, "agent": pending["agent"], "arguments": args, "result": None,
                          "reply": f"Thanks. I understood your request: {_confirmation_preview(intent, args)}. Should I do that? Say ‘OK, do that’ to confirm, or ‘cancel’ to stop.",
                          "needs_clarification": False, "requires_approval": False, "requires_confirmation": True, "orchestration": "voice-clarification"}
        elif pending and (normalized in yes_phrases or normalized.startswith("ok do that") or normalized.startswith("okay do that") or normalized.startswith("yes do that") or normalized.startswith("yes please do that")):
            # Pop first to prevent accidental double execution on duplicate speech-recognition events.
            pending_store.pop(conversation.id, None)
            intent, args = pending["intent"], pending["arguments"]
            from ..services.mcp_client import call_agent_tool
            result = await call_agent_tool(intent, args)
            # The user's explicit voice confirmation authorizes this one proposed desktop/YouTube launch.
            if intent in {"desktop", "youtube"} and isinstance(result, dict) and result.get("status") == "pending_approval" and result.get("id"):
                base = str(request.app.state.settings.ava_api_base_url).rstrip("/")
                # Use the local API directly; no shell command is constructed.
                async with httpx.AsyncClient(timeout=20) as client:
                    approved = await client.post(f"{base}/api/desktop/actions/{result['id']}/approve", json={"approved": True})
                    if approved.is_success: result = approved.json()
                    else: result = {**result, "approval_error": approved.text[:500]}
            from ..graph.voice_graph import _human_reply, AGENTS
            reply = _human_reply(intent, result)
            if intent == "desktop" and isinstance(result, dict) and result.get("status") == "executed": reply = f"Done. Opened {result.get('target', args.get('target', 'the requested app'))}."
            if intent == "youtube" and isinstance(result, dict) and result.get("status") == "executed": reply = f"Done. Opened YouTube for ‘{args.get('query') or 'YouTube'}’. If your browser blocks autoplay, press Play in the video tab."
            routed = {"transcript": text, "intent": intent, "agent": AGENTS.get(intent, pending["agent"]), "arguments": args, "result": result,
                      "reply": reply, "needs_clarification": bool(isinstance(result, dict) and result.get("needs_clarification")),
                      "requires_approval": intent == "email", "requires_confirmation": False, "orchestration": "voice-confirmation+mcp"}
        elif pending and (normalized in yes_phrases or normalized in cancel_phrases):
            routed = {"transcript": text, "intent": pending["intent"], "agent": pending["agent"], "arguments": pending["arguments"], "result": None,
                      "reply": "Please say ‘OK, do that’ to confirm, or ‘cancel’ to stop.", "needs_clarification": False, "requires_approval": False, "requires_confirmation": True, "orchestration": "voice-confirmation"}
        else:
            routed = await run_voice_graph(request.app.state.models, text, body.provider, plan_only=True)
            if routed.get("requires_confirmation") and not routed.get("needs_clarification"):
                pending_store[conversation.id] = {"intent": routed["intent"], "agent": routed["agent"], "arguments": routed.get("arguments", {}), "provider": body.provider, "transcript": text}
            elif routed.get("needs_clarification"):
                pending_store[conversation.id] = {"intent": routed["intent"], "agent": routed["agent"], "arguments": routed.get("arguments", {}), "provider": body.provider, "transcript": text, "awaiting_detail": True, "clarification_question": routed.get("reply", "Please provide one more detail.")}
    except Exception as exc:
        raise HTTPException(500, f"Voice orchestration failed: {exc}") from exc
    assistant_row = Message(id=str(uuid4()), conversation_id=conversation.id, role="assistant", content=routed["reply"], created_at=datetime.now(timezone.utc))
    db.add(assistant_row)
    db.commit()
    routed["conversation_id"] = conversation.id
    routed["assistant"] = {"id": assistant_row.id, "role": "assistant", "content": assistant_row.content, "created_at": assistant_row.created_at.isoformat()}
    routed["message"] = {"id": user_row.id, "role": "user", "content": user_row.content, "created_at": user_row.created_at.isoformat()}
    return routed
