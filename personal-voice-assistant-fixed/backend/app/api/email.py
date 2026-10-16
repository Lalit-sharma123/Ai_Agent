import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database import EmailDraft, get_db
from ..core.model_adapters import ModelError

router = APIRouter(prefix="/api/email", tags=["email"])

class DraftRequest(BaseModel):
    instruction: str = Field(min_length=3, max_length=5000)
    to_address: str = Field(min_length=3, max_length=500)
    subject: str = Field(default="", max_length=500)
    context: str = Field(default="", max_length=12000)

class UpdateDraft(BaseModel):
    to_address: str = Field(min_length=3, max_length=500)
    subject: str = Field(max_length=500)
    body: str = Field(min_length=1, max_length=50000)

class SendApproval(BaseModel):
    approved: bool

def _out(row: EmailDraft):
    return {"id": row.id, "to_address": row.to_address, "subject": row.subject,
            "body": row.body, "status": row.status, "created_at": row.created_at.isoformat(),
            "approved_at": row.approved_at.isoformat() if row.approved_at else None,
            "provider_message_id": row.provider_message_id}

@router.get("/drafts")
def list_drafts(db: Session = Depends(get_db)):
    return [_out(x) for x in db.scalars(select(EmailDraft).order_by(EmailDraft.created_at.desc())).all()]

@router.post("/drafts")
async def create_draft(body: DraftRequest, request: Request, db: Session = Depends(get_db)):
    prompt = ("Write an email draft based on the user's request. Do not send it. "
              "Return only the email body; do not invent facts.\nRequest: " + body.instruction +
              "\nRequested subject (if any): " + body.subject + "\nContext: " + body.context)
    try:
        result = await request.app.state.models.chat([{"role":"user","content":prompt}])
        email_body = result["content"].strip()
    except ModelError as exc:
        raise HTTPException(503, str(exc)) from exc
    row = EmailDraft(id=str(uuid4()), to_address=body.to_address.strip(),
                     subject=body.subject.strip() or "Draft email", body=email_body,
                     status="draft", created_at=datetime.now(timezone.utc))
    db.add(row); db.commit(); db.refresh(row)
    return _out(row)

@router.put("/drafts/{draft_id}")
def update_draft(draft_id: str, body: UpdateDraft, db: Session = Depends(get_db)):
    row = db.get(EmailDraft, draft_id)
    if row is None: raise HTTPException(404, "Email draft not found.")
    if row.status == "sent": raise HTTPException(409, "Sent emails cannot be edited.")
    row.to_address = body.to_address.strip(); row.subject = body.subject.strip(); row.body = body.body
    row.status = "draft"; db.commit(); db.refresh(row)
    return _out(row)

@router.post("/drafts/{draft_id}/send")
def send_draft(draft_id: str, body: SendApproval, request: Request, db: Session = Depends(get_db)):
    row = db.get(EmailDraft, draft_id)
    if row is None: raise HTTPException(404, "Email draft not found.")
    if not body.approved:
        raise HTTPException(400, "Explicit user approval is required to send.")
    if row.status == "sent": raise HTTPException(409, "Email has already been sent.")
    settings = request.app.state.settings
    if not (settings.smtp_host and settings.smtp_username and settings.smtp_password and settings.email_from_address):
        raise HTTPException(503, "SMTP is not configured. Set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, EMAIL_FROM_ADDRESS.")
    message = EmailMessage()
    message["From"] = settings.email_from_address
    message["To"] = row.to_address
    message["Subject"] = row.subject
    message.set_content(row.body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
        row.status = "sent"; row.approved_at = datetime.now(timezone.utc)
        row.provider_message_id = message.get("Message-ID")
        db.commit(); db.refresh(row)
        return _out(row)
    except Exception as exc:
        row.status = "send_failed"; db.commit()
        raise HTTPException(502, f"SMTP send failed: {exc}") from exc
